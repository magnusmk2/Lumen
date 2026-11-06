"""Screen-sync orchestrator (Entertainment streaming over DTLS).

This wires the pieces together: set the entertainment configuration to 'start',
open the DTLS stream, then push frames at a fixed frame rate from a color source.

A ColorSource yields one (r, g, b) per channel. Two are provided:
  - TestColorSource: a moving rainbow, to validate the pipeline end to end.
  - ScreenCapture: real ambilight, averaging screen regions mapped onto the
    Entertainment channel positions (see capture.py for the backends).

CLI:
    hue-sync --list            list entertainment configurations
    hue-sync                   ambilight from the screen
    hue-sync --test            stream the rainbow test pattern instead
    hue-sync --config <id>     choose a configuration
    hue-sync --output DP-2     capture one monitor rather than the desktop
    hue-sync --fps 40          frame rate (default 50)
"""

import sys
import json
import time
import math
import argparse
import colorsys
import threading

from .config import load_config, stream_lock
from .bridge import Bridge
from . import capture, entertainment, huestream, mapping
from .dtls_stream import HueDTLS
from .blackbars import BlackBarDetector, remap_regions


class ColorSource:
    def configure(self, config):
        """Called once with the entertainment configuration before streaming.

        Sources that map channels onto something (the screen, say) need the
        channel positions, which only run_stream knows.
        """

    def sample(self, n):
        """Return a list of n (r, g, b) tuples, 8-bit."""
        raise NotImplementedError

    def close(self):
        pass


class TestColorSource(ColorSource):
    """Moving rainbow across channels - proves the whole path lights up."""

    def __init__(self, speed=0.15):
        self.speed = speed
        self._t0 = time.monotonic()

    def sample(self, n):
        t = (time.monotonic() - self._t0) * self.speed
        out = []
        for i in range(max(1, n)):
            hue = (t + i / max(1, n)) % 1.0
            r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
            out.append((int(r * 255), int(g * 255), int(b * 255)))
        return out[:n]


def channel_regions(config, width, height, band=0.4):
    """Screen box each Entertainment channel should follow, ordered by channel id.

    A channel's x (-1 left .. +1 right) maps straight onto a horizontal slice of
    the screen, which is exactly what ambilight needs. y (depth) and z (height)
    are ignored on purpose: most areas leave them flat, and guessing a vertical
    split out of them looks worse than averaging the full height.

    band is the fraction of screen width each channel averages, so neighbouring
    lamps overlap slightly instead of showing hard seams.
    """
    regions = []
    half = band / 2.0
    for cid, x, _y, _z in entertainment.channel_positions(config):
        centre = (x + 1.0) / 2.0
        x0 = int(round(max(0.0, centre - half) * width))
        x1 = int(round(min(1.0, centre + half) * width))
        if x1 <= x0:                      # never hand back an empty box
            x0 = min(x0, width - 1)
            x1 = x0 + 1
        regions.append((cid, (x0, 0, x1, height)))
    return regions


class ScreenCapture(ColorSource):
    """Averages screen regions, one per Entertainment channel.

    The capture backend is picked at first sample so constructing this is cheap
    and cannot fail; a missing binary or a refused portal surfaces when
    streaming actually starts.
    """

    def __init__(self, regions=None, backend=None, output=None, fps=30,
                 saturation=1.6, gamma=1.0,
                 width=capture.CAPTURE_W, height=capture.CAPTURE_H,
                 mapping_profile=None, topology=None, mapping_revision=0, on_state=None, cancelled=None):
        self._bar_detector = BlackBarDetector()
        self._ignore_black_bars = bool((mapping_profile or {}).get("ignore_black_bars", False))
        self.sampling_status = None
        self.mapping_profile = mapping_profile
        self.topology = topology
        self.mapping_revision = mapping_revision
        self.on_state = on_state or (lambda state: None)
        self.cancelled = cancelled or (lambda: False)
        self._mapping_lock = threading.Lock()
        self._pending_mapping = None
        self._bridge = None
        self.frames_sent = 0
        self.started_at = None
        self.regions = regions or []
        self._rectangles = None
        self.backend = "portal" if output == "portal-selection" else backend
        self.output = output
        self.fps = fps
        self.saturation = saturation
        self.gamma = gamma
        self.width, self.height = width, height
        self._stream = None
        self._opened_for = None

    def on_sent(self):
        if self.started_at is None:
            self.started_at = time.monotonic()
        self.frames_sent += 1

    def bind_bridge(self, bridge):
        self._bridge = bridge

    def configure(self, config):
        if self._bridge is not None and self.output:
            self.topology = mapping.discover(self._bridge, config["id"], cancelled=self.cancelled)
            if self.mapping_profile is None:
                self.mapping_profile, self.mapping_revision = mapping.load_profile(
                    load_config(), self.topology, self.output)
            rects, _ = mapping.resolve(self.mapping_profile, self.topology)
            self._rectangles = rects
            self.regions = mapping.pixels(rects, self.width, self.height)
            self._ignore_black_bars = self.mapping_profile.get("ignore_black_bars", False)
        elif not self.regions:
            self.regions = channel_regions(config, self.width, self.height)

    def queue_mapping(self, profile, revision):
        if self.topology is None:
            raise ValueError("Screen source is not ready")
        rects, _ = mapping.resolve(profile, self.topology)
        regions = mapping.pixels(rects, self.width, self.height)
        with self._mapping_lock:
            self._pending_mapping = (regions, rects, revision, profile.get("ignore_black_bars", False))

    def prepare(self):
        self._open().latest()

    def set_output(self, output):
        """Retarget the capture while streaming.

        Only records the wish - a plain attribute write, so the UI thread never
        blocks. The sampling thread owns the capture process and swaps it on its
        next frame, which keeps the Hue stream up and the lamps from blinking.
        """
        self.output = output

    def _open(self):
        if self._stream is not None and self._opened_for != self.output:
            self._stream.close()
            self._stream = None
        if self._stream is None:
            self._opened_for = self.output
            self._bar_detector.reset()
            self.sampling_status = None
            self._stream = capture.open_stream(
                self.backend, self._opened_for, self.fps, self.width, self.height,
                on_wait=lambda: self.on_state("waiting"), cancelled=self.cancelled)
        return self._stream

    def sample(self, n):
        with self._mapping_lock:
            if self._pending_mapping is not None:
                self.regions, self._rectangles, self.mapping_revision, enabled = self._pending_mapping
                if enabled != self._ignore_black_bars:
                    self._bar_detector.reset()
                self._ignore_black_bars = enabled
                self._pending_mapping = None
        stream = self._open()
        buf = stream.latest()
        crop = (0, 0, self.width, self.height)
        if self._ignore_black_bars:
            crop = self._bar_detector.process(buf, self.width, self.height, stream.bpp)
        regions = remap_regions(self.regions, self.width, self.height, crop, self._rectangles)
        # Publish a complete immutable-by-convention frame snapshot for the UI.
        self.sampling_status = {"enabled": self._ignore_black_bars,
            "crop": [crop[0]/self.width, crop[1]/self.height, crop[2]/self.width, crop[3]/self.height],
            "rectangles": {str(cid): [a/self.width, b/self.height, c/self.width, d/self.height]
                           for cid, (a,b,c,d) in regions}, "revision": self.mapping_revision}
        out = [capture.punch(
                   capture.region_average(buf, self.width, stream.bpp, box),
                   self.saturation, self.gamma)
               for _cid, box in regions[:n]]
        while len(out) < n:               # more channels than mapped regions
            out.append(out[-1] if out else (0, 0, 0))
        return out

    def close(self):
        if self._stream is not None:
            self._stream.close()
            self._stream = None
        self._opened_for = None
        self._bar_detector.reset()
        self.sampling_status = None


def run_stream(source, config_id=None, fps=50, should_run=None):
    with stream_lock():
        return _run_stream(source, config_id, fps, should_run)


def _run_stream(source, config_id=None, fps=50, should_run=None):
    """Start streaming until should_run() returns False (or Ctrl-C).

    should_run: optional callable returning True while streaming should continue.
    Returns None. Raises on setup errors (no config, missing key, etc.).
    """
    cfg = load_config()
    ip, app_key = cfg.get("bridge_ip"), cfg.get("app_key")
    client_key = cfg.get("client_key")
    if not ip or not app_key:
        raise RuntimeError("bridge not paired - run the app or `hue auth` first")
    if not client_key:
        raise RuntimeError("no client_key in config - re-pair the bridge "
                           "(it is created at pairing and needed for streaming)")

    bridge = Bridge(ip, app_key)
    config = entertainment.pick_config(bridge, config_id)
    if config is None:
        raise RuntimeError("no entertainment area found - create one in the "
                           "official Hue app first")
    if config.get("status") == "active":
        raise RuntimeError("Entertainment area is in use; stop the other sync app first")
    channels = entertainment.channel_ids(config)
    if not channels:
        raise RuntimeError("the entertainment area has no channels")

    dtls = HueDTLS(ip, app_key, client_key)
    started = False
    period = 1.0 / max(1, fps)
    seq = 0
    try:
        if hasattr(source, "bind_bridge"):
            source.bind_bridge(bridge)
        source.configure(config)
        if should_run is not None and not should_run():
            return
        if hasattr(source, "prepare"):
            source.prepare()
        if should_run is not None and not should_run():
            return
        if hasattr(source, "on_state"):
            source.on_state("starting")
        entertainment.start(bridge, config["id"])
        started = True
        dtls.connect()
        deadline = time.monotonic()
        while should_run is None or should_run():
            colors = source.sample(len(channels))
            frame = huestream.build_rgb_frame(config["id"], zip(channels, colors), seq)
            dtls.send(frame)
            if hasattr(source, "on_sent"):
                source.on_sent()
            if seq == 0 and hasattr(source, "on_state"):
                source.on_state("running")
            seq = (seq + 1) & 0xFF
            deadline += period
            delay = deadline - time.monotonic()
            if delay > 0:
                time.sleep(delay)
            else:
                deadline = time.monotonic()
    finally:
        dtls.close()
        source.close()
        if started:
            try:
                entertainment.stop(bridge, config["id"])
            except Exception:
                pass


def _list_configs():
    cfg = load_config()
    if not cfg.get("bridge_ip") or not cfg.get("app_key"):
        print("bridge not paired.", file=sys.stderr)
        return 1
    bridge = Bridge(cfg["bridge_ip"], cfg["app_key"])
    configs = entertainment.list_configs(bridge)
    if not configs:
        print("no entertainment area - create one in the Hue app.")
        return 0
    for c in configs:
        print(f"{c['id']}  {entertainment.config_name(c):<24} "
              f"{entertainment.channel_count(c)} channels")
    return 0


def main():
    p = argparse.ArgumentParser(prog="hue-sync",
                                description="Philips Hue screen sync (Entertainment)")
    p.add_argument("--list", action="store_true", help="list entertainment areas")
    p.add_argument("--config", help="entertainment configuration id")
    p.add_argument("--fps", type=int, help="frame rate (saved setting, otherwise 30)")
    p.add_argument("--test", action="store_true",
                   help="stream the rainbow test pattern instead of the screen")
    p.add_argument("--output", help="monitor to capture (e.g. DP-2)")
    p.add_argument("--backend", choices=sorted(capture.BACKENDS) + ["portal"],
                   help="force a capture backend")
    p.add_argument("--saturation", type=float,
                   help="color boost, screen averages look washed out (default 1.6)")
    p.add_argument("--gamma", type=float, default=1.0,
                   help="above 1 darkens dim scenes (default 1.0)")
    p.add_argument("--mapping", choices=["saved", "legacy", "desk"], default="saved")
    p.add_argument("--band-height", type=float, help="bottom band height in percent")
    p.add_argument("--bottom-inset", type=float, help="bottom inset in percent")
    p.add_argument("--show-mapping", action="store_true", help="print resolved regions without starting capture")
    args = p.parse_args()
    settings = load_config()
    args.fps = args.fps if args.fps is not None else settings.get("sync_fps", 30)
    args.saturation = args.saturation if args.saturation is not None else settings.get("sync_saturation", 1.6)
    if type(args.fps) is not int or not 1 <= args.fps <= 60:
        p.error("fps must be between 1 and 60")
    if not math.isfinite(args.saturation) or not 0 <= args.saturation <= 4:
        p.error("saturation must be between 0 and 4")
    if not math.isfinite(args.gamma) or not .1 <= args.gamma <= 5:
        p.error("gamma must be between 0.1 and 5")
    if args.test and args.show_mapping:
        p.error("--show-mapping cannot be combined with --test")

    if args.list:
        return _list_configs()

    try:
        profile = None
        topology = None
        if not args.test:
            cfg = load_config()
            args.output = args.output or cfg.get("sync_output")
            if not cfg.get("bridge_ip") or not cfg.get("app_key"):
                raise ValueError("Bridge not paired")
            args.config = args.config or cfg.get("sync_area_id")
            # Resolve one monitor on Hyprland; never accidentally capture all screens.
            if not args.output:
                import subprocess
                try:
                    monitors = json.loads(subprocess.check_output(
                        ["hyprctl", "monitors", "-j"], timeout=3))
                    args.output = next((m["name"] for m in monitors if m.get("focused")), monitors[0]["name"])
                except (OSError, ValueError, IndexError, subprocess.SubprocessError):
                    pass
            args.output = args.output or "portal-selection"
            if args.output:
                topology = mapping.discover(Bridge(cfg["bridge_ip"], cfg["app_key"]), args.config)
                if args.mapping == "saved":
                    profile, _ = mapping.load_profile(cfg, topology, args.output)
                else:
                    profile = mapping.default_profile(topology)
                    profile["mode"] = args.mapping
                if args.band_height is not None:
                    profile["height"] = args.band_height / 100
                if args.bottom_inset is not None:
                    profile["inset"] = args.bottom_inset / 100
                rects, _ = mapping.resolve(profile, topology)
                if args.show_mapping:
                    print(json.dumps({"output": args.output, "rectangles": rects}, indent=2))
                    return 0
            elif args.show_mapping or args.mapping != "saved":
                raise ValueError("Select a monitor with --output")
        if args.test:
            print("Starting test pattern - press Ctrl-C to stop.")
            source = TestColorSource()
        else:
            print("Starting screen sync - press Ctrl-C to stop.")
            source = ScreenCapture(backend=args.backend, output=args.output,
                                   fps=args.fps, saturation=args.saturation,
                                   gamma=args.gamma, mapping_profile=profile, topology=topology)
        run_stream(source, config_id=args.config, fps=args.fps)
    except KeyboardInterrupt:
        print("\nstopped.")
        return 0
    except Exception as e:  # noqa: BLE001
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
