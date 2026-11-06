"""Vue web UI entry point: pywebview shell around huectl/webui_dist (the
Vue app, built by `npm run build` in webui/."""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import requests
import urllib3

# WebKitGTK's DMABUF renderer crashes on load (Wayland protocol error) on
# hybrid Intel+NVIDIA setups under Hyprland.
# Must be set before `webview` (and the GTK/WebKit libs it loads) import.
os.environ.setdefault("WEBKIT_DISABLE_DMABUF_RENDERER", "1")

import webview  # noqa: E402

from .bridge import discover_bridge_ip, load_bridge  # noqa: E402
from .config import CONFIG_PATH, APP_NAME, load_config, save_config  # noqa: E402
from .i18n import STRINGS  # noqa: E402
from . import entertainment, sync
from .mapping_api import MappingAPI  # noqa: E402

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


if getattr(sys, "_MEIPASS", None):
    DIST_INDEX = Path(sys._MEIPASS) / "webui_dist" / "index.html"
else:
    DIST_INDEX = Path(__file__).resolve().parent / "webui_dist" / "index.html"

# Set by `npm run dev` workflow to point at the Vite dev server for hot-reload
# instead of the built dist/, e.g. LUMEN_WEBUI_DEV_URL=http://localhost:5173
DEV_SERVER_URL = os.environ.get("LUMEN_WEBUI_DEV_URL")


class Api:
    """Methods exposed to the Vue app as window.pywebview.api.*"""

    def __init__(self):
        self._mapping = MappingAPI()
        self._pair_state = {"status": "idle"}
        self._pair_lock = threading.Lock()

    def ping(self):
        return "pong"

    def get_strings(self):
        """Both full dictionaries, loaded once - switching language client
        side is then instant, no round trip needed (see huectl/i18n.py)."""
        return {"en": STRINGS["en"], "fr": STRINGS["fr"]}

    def get_config(self):
        """Sanitized config for the Setup page - never the secrets themselves."""
        cfg = load_config()
        return {
            "bridge_ip": cfg.get("bridge_ip"),
            "has_client_key": bool(cfg.get("client_key")),
            "columns": cfg.get("columns", 2),
            "language": cfg.get("language", "en"),
            "start_minimized": cfg.get("start_minimized", False),
            "sync_area_id": cfg.get("sync_area_id"),
            "sync_output": cfg.get("sync_output", ""),
            "sync_saturation": cfg.get("sync_saturation", 1.6),
            "sync_fps": cfg.get("sync_fps", 30),
        }

    def save_settings(self, patch):
        allowed = {"columns", "language", "start_minimized", "sync_output", "sync_saturation", "sync_fps", "sync_area_id"}
        save_config({k: v for k, v in patch.items() if k in allowed})
        return {"ok": True}

    def set_bridge_ip(self, ip):
        """Change IP only - same physical bridge, keeps app_key/client_key
        (matches huectl/app.py's set_ip: a DHCP lease change, not a re-pair)."""
        save_config({"bridge_ip": ip})
        return {"ok": True}

    def disconnect(self):
        try:
            os.remove(CONFIG_PATH)
        except OSError:
            pass
        return {"ok": True}

    def discover_bridge(self):
        try:
            return {"ip": discover_bridge_ip()}
        except Exception as e:
            return {"error": str(e)}

    def start_pairing(self, ip):
        """Kicks off a background poll loop (mirrors huectl/workers.py's
        PairTask) and returns immediately; the Vue side polls pair_status()
        once a second for the live countdown, since a js_api call is a
        request/response round trip, not a stream."""
        with self._pair_lock:
            if self._pair_state.get("status") == "waiting":
                return {"error": "already_pairing"}
            self._pair_state = {"status": "waiting", "seconds_left": 30}
        threading.Thread(target=self._pair_worker, args=(ip,), daemon=True).start()
        return {"ok": True}

    def _pair_worker(self, ip):
        payload = {"devicetype": APP_NAME, "generateclientkey": True}
        for i in range(30):
            try:
                r = requests.post(f"https://{ip}/api", json=payload, verify=False, timeout=5)
                res = r.json()
            except Exception as e:
                with self._pair_lock:
                    self._pair_state = {"status": "error", "message": str(e)}
                return
            if isinstance(res, list) and res:
                item = res[0]
                if "success" in item:
                    s = item["success"]
                    cfg = {"bridge_ip": ip, "app_key": s["username"], "client_key": s.get("clientkey")}
                    save_config(cfg)
                    with self._pair_lock:
                        self._pair_state = {"status": "success"}
                    return
                err = item.get("error", {})
                if str(err.get("type")) != "101":  # 101 = button not pressed yet
                    with self._pair_lock:
                        self._pair_state = {"status": "error", "message": err.get("description", "?")}
                    return
            with self._pair_lock:
                self._pair_state = {"status": "waiting", "seconds_left": 30 - i - 1}
            time.sleep(1)
        with self._pair_lock:
            self._pair_state = {"status": "error", "message": "Timed out waiting for the button press."}

    def pair_status(self):
        with self._pair_lock:
            return dict(self._pair_state)

    def get_snapshot(self):
        """Read-only bridge snapshot for the Vue store. Runs on pywebview's
        own worker thread (js_api calls are already off the UI thread), so no
        extra Task/QThread wrapping is needed here unlike the PySide6 GUI."""
        bridge = load_bridge()
        if bridge is None:
            return {"error": "not_configured"}
        try:
            return {"data": bridge.snapshot()}
        except Exception as e:
            return {"error": str(e)}

    def _write(self, fn):
        bridge = load_bridge()
        if bridge is None:
            return {"error": "not_configured"}
        try:
            fn(bridge)
            return {"ok": True}
        except Exception as e:
            return {"error": str(e)}

    def put_light(self, light_id, payload):
        """payload is a raw CLIP v2 body, e.g. {"on": {"on": true}} or
        {"color": {"xy": {"x": ..., "y": ...}}} - the Vue store builds it."""
        return self._write(lambda b: b.put("light", light_id, payload))

    def put_grouped_light(self, grouped_light_id, payload):
        return self._write(lambda b: b.put("grouped_light", grouped_light_id, payload))

    def recall_scene(self, scene_id):
        return self._write(lambda b: b.put("scene", scene_id, {"recall": {"action": "active"}}))

    def save_group(self, kind, group_id, name, light_ids):
        if kind not in ("room", "zone"):
            return {"error": "invalid_kind"}
        bridge = load_bridge()
        if bridge is None:
            return {"error": "not_configured"}
        try:
            if kind == "room":
                lights_by_id = {light["id"]: light for light in bridge.get("light")}
                device_ids, seen = [], set()
                for lid in light_ids:
                    light = lights_by_id.get(lid)
                    if not light:
                        continue
                    device_id = light["owner"]["rid"]
                    if device_id not in seen:
                        seen.add(device_id)
                        device_ids.append(device_id)
                children = [{"rid": d, "rtype": "device"} for d in device_ids]
            else:
                children = [{"rid": lid, "rtype": "light"} for lid in light_ids]

            payload = {"metadata": {"name": name, "archetype": "other"}, "children": children}
            if group_id:
                bridge.put(kind, group_id, payload)
                return {"ok": True, "id": group_id}
            result = bridge.post(kind, payload)
            return {"ok": True, "id": result["data"][0]["rid"]}
        except Exception as e:
            return {"error": str(e)}

    def delete_group(self, kind, group_id):
        if kind not in ("room", "zone"):
            return {"error": "invalid_kind"}
        return self._write(lambda b: b.delete(kind, group_id))

    def save_scene(self, scene_id, name, group_id, group_kind):
        bridge = load_bridge()
        if bridge is None:
            return {"error": "not_configured"}
        try:
            lights = _lights_of_group(bridge, group_kind, group_id)
            payload = {"metadata": {"name": name}, "actions": [_light_to_action(light) for light in lights]}
            if scene_id:
                bridge.put("scene", scene_id, payload)
                return {"ok": True, "id": scene_id}
            payload["group"] = {"rid": group_id, "rtype": group_kind}
            result = bridge.post("scene", payload)
            return {"ok": True, "id": result["data"][0]["rid"]}
        except Exception as e:
            return {"error": str(e)}

    def delete_scene(self, scene_id):
        return self._write(lambda b: b.delete("scene", scene_id))

    def list_entertainment_configs(self):
        bridge = load_bridge()
        if bridge is None:
            return {"error": "not_configured"}
        try:
            configs = entertainment.list_configs(bridge)
            return {"data": [
                {"id": c["id"], "name": entertainment.config_name(c), "channels": entertainment.channel_count(c)}
                for c in configs
            ]}
        except Exception as e:
            return {"error": str(e)}

    def get_channel_names(self, config_id=None):
        bridge = load_bridge()
        if bridge is None:
            return {"error": "not_configured"}
        try:
            config = entertainment.pick_config(bridge, config_id)
            if config is None:
                return {"data": []}
            lights = bridge.get("light")
            devices = bridge.get("device")
            lights_by_owner = {}
            for light in lights:
                lights_by_owner.setdefault(light["owner"]["rid"], []).append(light)
            device_by_ent_service = {}
            for d in devices:
                for s in d.get("services", []):
                    if s["rtype"] == "entertainment":
                        device_by_ent_service[s["rid"]] = d["id"]

            names = []
            for ch in sorted(config.get("channels", []), key=lambda c: c["channel_id"]):
                name = "?"
                members = ch.get("members", [])
                if members:
                    device_id = device_by_ent_service.get(members[0]["service"]["rid"])
                    lamps = lights_by_owner.get(device_id, [])
                    if lamps:
                        name = lamps[0]["metadata"]["name"]
                names.append({"channel_id": ch["channel_id"], "name": name})
            return {"data": names}
        except Exception as e:
            return {"error": str(e)}

    def list_outputs(self):
        return {"data": [m["name"] for m in _hyprctl_monitors()] or ["portal-selection"]}

    def get_sync_mapping(self, area, output):
        try:
            result = self._mapping.get(area, output)
            monitor = next((m for m in _hyprctl_monitors() if m["name"] == output), None)
            if monitor:
                w, h = monitor["width"], monitor["height"]
                if monitor.get("transform", 0) % 2:
                    w, h = h, w
                result["aspect"] = w / h
            return result
        except Exception as e:
            return {"error": str(e)}

    def preview_sync_mapping(self, area, output, profile):
        try:
            return self._mapping.preview(area, output, profile)
        except Exception as e:
            return {"error": str(e)}

    def save_sync_mapping(self, area, output, profile, revision):
        try:
            return self._mapping.save(area, output, profile, revision, web_sync)
        except Exception as e:
            return {"error": str(e)}

    def identify_sync_channel(self, area, channel):
        return web_sync.identify(area, channel)

    def start_sync(self, output, saturation, fps, config_id=None):
        return web_sync.start(output, saturation, fps, config_id)

    def stop_sync(self):
        return web_sync.stop()

    def set_sync_output(self, output):
        web_sync.set_output(output)
        return {"ok": True}

    def set_sync_saturation(self, saturation):
        web_sync.set_saturation(saturation)
        return {"ok": True}

    def sync_status(self):
        return web_sync.status()

    def sync_preview(self):
        return {"colors": web_sync.preview_colors()}


def _process_events(events):
    """Mirrors huectl/sse.py's process_events - duplicated rather than
    imported so hue-webui doesn't pull PySide6 into a Qt-less process just
    for this pure-Python parsing (sse.py's EventStream subclasses QThread)."""
    light_updates = []
    structural = False
    for ev in events:
        etype = ev.get("type")
        data = ev.get("data", [])
        if etype in ("add", "delete"):
            structural = True
        if etype == "update":
            for res in data:
                if res.get("type") == "light":
                    light_updates.append(res)
    return light_updates, structural


class WebSSE(threading.Thread):
    """Bridge event stream (SSE) for the web UI. Same protocol handling as
    huectl/sse.py's EventStream, as a plain daemon thread calling plain
    callbacks instead of a QThread emitting Qt signals - this process has no
    Qt event loop.

    Re-reads load_bridge() on every reconnect attempt instead of binding to a
    fixed Bridge at construction time, so it survives (and picks up) a
    disconnect/re-pair/change-IP happening in the same running process - the
    Setup page's job, this step - without needing to be torn down and
    recreated."""

    def __init__(self, on_update, on_change):
        super().__init__(daemon=True)
        self.on_update = on_update
        self.on_change = on_change
        self._stop = False
        self._resp = None

    def run(self):
        while not self._stop:
            bridge = load_bridge()
            if bridge is None:
                time.sleep(1.5)
                continue
            url = bridge.base + "/eventstream/clip/v2"
            headers = dict(bridge.headers)
            headers["Accept"] = "text/event-stream"
            try:
                self._resp = requests.get(url, headers=headers, stream=True, verify=False, timeout=(5, 90))
                self._read(self._resp)
            except Exception:
                pass  # network hiccup / read timeout -> reconnect
            finally:
                self._close()
            if not self._stop:
                time.sleep(1.5)  # small backoff before reconnecting

    def _read(self, resp):
        buffer = []
        for raw in resp.iter_lines(decode_unicode=True):
            if self._stop:
                return
            line = raw if raw is not None else ""
            if line == "":  # blank line ends an SSE block
                if buffer:
                    self._dispatch("\n".join(buffer))
                    buffer = []
                continue
            if line.startswith(":"):  # comment / keep-alive
                continue
            if line.startswith("data:"):
                buffer.append(line[5:].lstrip())

    def _dispatch(self, payload):
        try:
            events = json.loads(payload)
        except ValueError:
            return
        lights, structural = _process_events(events)
        if lights:
            self.on_update(lights)
        if structural:
            self.on_change()

    def _close(self):
        try:
            if self._resp is not None:
                self._resp.close()
        except Exception:
            pass
        self._resp = None

    def stop(self):
        self._stop = True
        self._close()


def _lights_of_group(bridge, kind, group_id):
    """Mirrors huectl/window.py's _lights_of_group (room children are
    devices, resolved via each light's own owner.rid; zone children are
    lights directly) - duplicated because it takes a Bridge, not the data
    dict window.py keeps in memory, and because color.py (below) can't be
    imported without pulling in PySide6."""
    groups = bridge.get(kind)
    group = next((g for g in groups if g["id"] == group_id), None)
    if group is None:
        return []
    lights = bridge.get("light")
    if kind == "zone":
        light_ids = {c["rid"] for c in group.get("children", []) if c["rtype"] == "light"}
        return [light for light in lights if light["id"] in light_ids]
    device_ids = {c["rid"] for c in group.get("children", []) if c["rtype"] == "device"}
    return [light for light in lights if light.get("owner", {}).get("rid") in device_ids]


def _light_to_action(light):
    """Mirrors huectl/color.py's light_to_action - duplicated rather than
    imported since color.py does `from PySide6.QtGui import QColor` at module
    level, which would pull PySide6 into this Qt-less process just to reuse
    ten lines of plain-dict logic."""
    action = {"on": {"on": bool(light.get("on", {}).get("on"))}}
    if light.get("dimming", {}).get("brightness") is not None:
        action["dimming"] = {"brightness": light["dimming"]["brightness"]}
    xy = light.get("color", {}).get("xy")
    ct = light.get("color_temperature", {}).get("mirek")
    if xy:
        action["color"] = {"xy": xy}
    elif ct:
        action["color_temperature"] = {"mirek": ct}
    return {"target": {"rid": light["id"], "rtype": "light"}, "action": action}


def _hyprctl_monitors():
    try:
        out = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, timeout=3, check=True)
        return json.loads(out.stdout)
    except Exception:
        return []


def _default_output():
    """Best guess at the primary monitor. capture.py has no way to ask this 
    itself, so webapp.py resolves it via hyprctl instead. Picks the focused one, or the
    first, or None."""
    monitors = _hyprctl_monitors()
    if not monitors:
        return None
    focused = next((m for m in monitors if m.get("focused")), None)
    return (focused or monitors[0])["name"]


def _rgb_to_hex(rgb):
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


class _PreviewCapture(sync.ScreenCapture):
    """Same as sync.ScreenCapture, stashing each sampled frame's colours for
    the mapping card's live preview (sync_preview)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.last_colors = []

    def sample(self, n):
        colors = super().sample(n)
        self.last_colors = colors
        return colors


class WebSync:
    """Screen-sync session for the web UI: runs sync.run_stream in a daemon
    thread. Owns one session at a time, including channel identification."""

    def __init__(self):
        self._thread = None
        self._stop = threading.Event()
        self._source = None
        self._error = None
        self._running = False
        self._fps = 30
        self._lock = threading.RLock()
        self._state = "idle"
        self._area = None
        self._output = None

    def _state_changed(self, state):
        with self._lock:
            if not self._stop.is_set():
                self._state = state

    def start(self, output, saturation, fps, config_id=None):
        with self._lock:
            if self._running:
                return {"error": "already_running"}
            if type(fps) is not int or not 1 <= fps <= 60:
                return {"error": "Invalid frame rate"}
            if type(saturation) not in (int, float) or not 0 <= saturation <= 4:
                return {"error": "Invalid colour boost"}
            available = {m["name"] for m in _hyprctl_monitors()} or {"portal-selection"}
            if output and output not in available:
                return {"error": "Selected monitor is unavailable"}
            self._stop.clear()
            self._state = "starting"
            self._error = None
            self._fps = fps
            resolved_output = output or _default_output() or "portal-selection"
            if not resolved_output:
                return {"error": "Select a monitor"}
            config_id = config_id or load_config().get("sync_area_id")
            self._area, self._output = config_id, resolved_output
            self._source = _PreviewCapture(output=resolved_output, fps=fps, saturation=saturation,
                                           on_state=self._state_changed, cancelled=self._stop.is_set)
            self._running = True
        self._thread = threading.Thread(target=self._run, args=(config_id,), daemon=True)
        self._thread.start()
        return {"ok": True}

    def _run(self, config_id):
        try:
            sync.run_stream(self._source, config_id=config_id, fps=self._fps,
                             should_run=lambda: not self._stop.is_set())
        except Exception as e:
            with self._lock:
                if not self._stop.is_set():
                    self._error = str(e)
        finally:
            with self._lock:
                self._running = False
                self._source = None
                self._state = "error" if self._error else "idle"

    def stop(self):
        with self._lock:
            if self._running:
                self._state = "stopping"
        self._stop.set()
        for _ in range(30):  # up to ~3s for the loop to notice and clean up
            with self._lock:
                if not self._running:
                    break
            time.sleep(0.1)
        return {"ok": True, "stopping": self._running}

    def shutdown(self):
        self._stop.set()
        thread = self._thread
        if thread and thread is not threading.current_thread():
            thread.join(timeout=15)

    def set_output(self, output):
        with self._lock:
            if self._running:
                raise ValueError("Stop sync before changing monitor")

    def set_saturation(self, saturation):
        if type(saturation) not in (int, float) or not 0 <= saturation <= 4:
            raise ValueError("Invalid colour boost")
        with self._lock:
            if self._source:
                self._source.saturation = saturation

    def status(self):
        with self._lock:
            return {"running": self._running, "state": self._state, "error": self._error,
                    "fps": self._fps, "area": self._area, "output": self._output,
                    "revision": self._source.mapping_revision if self._source else None,
                    "frames_sent": self._source.frames_sent if self._source else 0}

    def identify(self, area, channel):
        with self._lock:
            if self._running:
                return {"error": "Stop sync before identifying a segment"}
            if type(channel) is not int or not 0 <= channel <= 255:
                return {"error": "Invalid channel"}
            self._running, self._state, self._error = True, "identifying", None
            self._stop.clear()
            self._area, self._output = area, None
        worker = self
        class Identify(sync.ColorSource):
            def configure(self, config):
                self.ids = entertainment.channel_ids(config)
                if channel not in self.ids:
                    raise ValueError("Channel is not in the selected area")
            def sample(self, n):
                return [(40, 40, 40) if cid == channel else (0, 0, 0) for cid in self.ids]
        def run():
            deadline = time.monotonic() + 3
            try:
                sync.run_stream(Identify(), config_id=area, fps=10,
                    should_run=lambda: not worker._stop.is_set() and time.monotonic() < deadline)
            except Exception as e:
                with worker._lock:
                    worker._error = str(e)
            finally:
                with worker._lock:
                    worker._running = False
                    worker._state = "error" if worker._error else "idle"
        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        return {"ok": True}

    def preview_colors(self):
        with self._lock:
            if not self._source:
                return []
            return [_rgb_to_hex(c) for c in self._source.last_colors]


web_sync = WebSync()


def _run_js(window, script):
    window.run_js(script + "; 0")


def _push(window, payload):
    _run_js(window, f"window.__lumenSSE && window.__lumenSSE({json.dumps(payload)})")


def _start_sse(window):
    """Runs in a background thread once the window is ready (webview.start's
    func/args). One WebSSE for the whole process lifetime: it idles (and
    retries) whenever there's no bridge configured yet, so this starts
    correctly even before first-run pairing completes."""
    WebSSE(
        on_update=lambda lights: _push(window, {"type": "update", "lights": lights}),
        on_change=lambda: _push(window, {"type": "change"}),
    ).start()


LOCK_PATH = os.path.expanduser("~/.config/huectl/webapp.lock")


def _acquire_single_instance():
    """Best-effort single-instance guard: a PID file, checked with a signal-0
    kill (no-op, just tests whether the pid is alive). A second launch pokes
    the running instance with SIGUSR2 so it raises its window """
    try:
        with open(LOCK_PATH, encoding="utf-8") as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
    except (OSError, ValueError):
        pass  # no lock file, unreadable, or that pid is dead - safe to start
    else:
        try:
            os.kill(pid, signal.SIGUSR2)
        except OSError:
            pass
        return False
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    with open(LOCK_PATH, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True


def _install_show_signal(window):
    from gi.repository import GLib, GLibUnix

    def raise_window():
        window.show()
        window.restore()
        return True

    GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR2, raise_window)
    def quit_cleanly():
        threading.Thread(target=window._lumen_quit, daemon=True).start()
        return False
    GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, quit_cleanly)
    GLibUnix.signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, quit_cleanly)


def _release_single_instance():
    try:
        os.remove(LOCK_PATH)
    except OSError:
        pass


def _tray_image():
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((13, 6, 51, 44), fill="#f0b429")  # bulb, matches AppMark.vue
    d.rounded_rectangle((23, 46, 41, 58), radius=3, fill="#8b909a")  # base
    return img


def _setup_tray(window):
    """pystray's AppIndicator backend shares the process's GTK/GLib main loop
    rather than running its own - run_detached() attaches to it instead of
    blocking, so this must run before webview.start() takes over that loop."""
    import pystray

    quitting = threading.Event()
    quit_lock = threading.Lock()

    def off_main(fn):
        return lambda icon, item: threading.Thread(
            target=fn, args=(icon, item), daemon=True
        ).start()

    def on_open(icon, item):
        window.show()
        window.restore()

    def on_refresh(icon, item):
        _run_js(window, "window.__lumenTrayRefresh && window.__lumenTrayRefresh()")

    def on_settings(icon, item):
        window.show()
        window.restore()
        _run_js(window, "window.__lumenTraySettings && window.__lumenTraySettings()")

    def on_quit(icon, item):
        with quit_lock:
            if quitting.is_set():
                return
            quitting.set()
        web_sync.shutdown()
        icon.stop()
        _release_single_instance()
        window.destroy()

    def on_closing():

        if quitting.is_set():
            return True  # let the real close through (tray Quit)
        window.hide()
        return False  # cancel: minimize to tray instead of exiting

    window.events.closing += on_closing
    window._lumen_quit = lambda: on_quit(icon, None)

    menu = pystray.Menu(
        pystray.MenuItem("Open", off_main(on_open), default=True),
        pystray.MenuItem("Refresh", off_main(on_refresh)),
        pystray.MenuItem("Settings", off_main(on_settings)),
        pystray.MenuItem("Quit", off_main(on_quit)),
    )
    icon = pystray.Icon("lumen", _tray_image(), "Lumen", menu)
    icon.run_detached()
    return icon


def main():
    url = DEV_SERVER_URL or str(DIST_INDEX)
    if not DEV_SERVER_URL and not DIST_INDEX.exists():
        sys.exit(
            f"{DIST_INDEX} not found - run `npm run build` in webui/, "
            "or set LUMEN_WEBUI_DEV_URL to a running `npm run dev` server."
        )
    if not _acquire_single_instance():
        sys.exit("Lumen is already running.")

    start_minimized = bool(load_config().get("start_minimized", False))
    window = webview.create_window(
        "Lumen", url, width=560, height=720, js_api=Api(), hidden=start_minimized
    )
    _setup_tray(window)
    _install_show_signal(window)
    try:
        webview.start(_start_sse, (window,))
    finally:
        web_sync.shutdown()
        _release_single_instance()


if __name__ == "__main__":
    main()
