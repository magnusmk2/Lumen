"""Universal screen capture through xdg-desktop-portal ScreenCast.

This is the backend that works everywhere - GNOME, KDE, wlroots - unlike the
compositor-specific binaries in capture.py. The portal hands out a PipeWire
node, and `gst-launch-1.0 pipewiresrc` turns it into the same raw RGB pipe every
other backend produces.

D-Bus goes through GDBus (`gi.repository.Gio`), not a new dependency: PyGObject
is already required for pywebview's GTK backend and pystray's AppIndicator
backend.

    # no persist_mode, so the portal asks which screen on every start.
"""

import json
import os
import shutil
import subprocess
import uuid

import gi
gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402

from . import capture

BUS = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
SCREENCAST = "org.freedesktop.portal.ScreenCast"
REQUEST_IFACE = "org.freedesktop.portal.Request"
SESSION_IFACE = "org.freedesktop.portal.Session"


class PortalSession:
    """A ScreenCast session: create, select sources, start, open the remote."""

    def __init__(self, timeout_ms=120000, cancelled=None):
        self.cancelled = cancelled or (lambda: False)
        self.timeout_ms = timeout_ms
        try:
            self.conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as e:
            raise capture.CaptureError(f"no D-Bus session bus: {e}") from e
        self._token = uuid.uuid4().hex[:8]
        self.handle = None

    def _await(self, request_path):
        """Block until org.freedesktop.portal.Request.Response fires on
        request_path."""
        loop = GLib.MainLoop()
        box = {}

        def on_signal(_conn, _sender, _path, _iface, _sig, params, *_a):
            box["code"], box["results"] = params.unpack()
            loop.quit()

        sub_id = self.conn.signal_subscribe(
            BUS, REQUEST_IFACE, "Response", request_path, None,
            Gio.DBusSignalFlags.NONE, on_signal)

        def on_timeout():
            loop.quit()
            return False

        timeout_id = GLib.timeout_add(self.timeout_ms, on_timeout)
        cancelled_by_timer = []
        def check_cancelled():
            if self.cancelled():
                cancelled_by_timer.append(True)
                loop.quit()
                return False
            return True
        cancel_id = GLib.timeout_add(50, check_cancelled)
        loop.run()
        if self.cancelled():
            # The request may still own a picker even after the worker stops.
            try:
                self.conn.call_sync(BUS, request_path, REQUEST_IFACE, "Close", None,
                                    None, Gio.DBusCallFlags.NONE, 2000, None)
            except GLib.Error:
                pass
        if not cancelled_by_timer:
            GLib.source_remove(cancel_id)
        self.conn.signal_unsubscribe(sub_id)
        if box:
            GLib.source_remove(timeout_id)
        if self.cancelled():
            if not box:
                GLib.source_remove(timeout_id)
            raise capture.CaptureError("capture cancelled")
        if not box:
            raise capture.CaptureError("the portal did not answer in time")
        if box["code"] != 0:            # 1 = user cancelled, 2 = failed
            raise capture.CaptureError(
                "screen capture was refused" if box["code"] == 1
                else "the portal failed to start screen capture")
        return box["results"]

    def _call(self, method, signature, args, reply_type):
        try:
            reply = self.conn.call_sync(
                BUS, PATH, SCREENCAST, method, GLib.Variant(signature, args),
                GLib.VariantType(reply_type), Gio.DBusCallFlags.NONE, -1, None)
        except GLib.Error as e:
            raise capture.CaptureError(f"{method}: {e}") from e
        return reply.unpack()[0]

    def _request(self, method, signature, args):
        """Call a method that returns a request object path, then await it."""
        request_path = self._call(method, signature, args, "(o)")
        return self._await(request_path)

    def _opts(self, suffix):
        return {"handle_token": GLib.Variant("s", f"{self._token}_{suffix}")}

    def start(self):
        """Run the handshake. Returns (node_id, pipewire_fd)."""
        options = self._opts("create")
        options["session_handle_token"] = GLib.Variant("s", f"{self._token}_session")
        res = self._request("CreateSession", "(a{sv})", (options,))
        self.handle = res["session_handle"]

        sel_opts = self._opts("select")
        sel_opts["multiple"] = GLib.Variant("b", False)
        self._request("SelectSources", "(oa{sv})", (self.handle, sel_opts))

        res = self._request("Start", "(osa{sv})", (self.handle, "", self._opts("start")))
        node_id = _node_from_streams(res.get("streams"))

        try:
            reply, fd_list = self.conn.call_with_unix_fd_list_sync(
                BUS, PATH, SCREENCAST, "OpenPipeWireRemote",
                GLib.Variant("(oa{sv})", (self.handle, {})),
                GLib.VariantType("(h)"), Gio.DBusCallFlags.NONE, -1, None, None)
        except GLib.Error as e:
            raise capture.CaptureError(f"OpenPipeWireRemote: {e}") from e
        fd = fd_list.get(reply.unpack()[0])
        if fd < 0:
            raise capture.CaptureError("the portal returned no PipeWire socket")
        # fd_list (and the fd it hands out) is only valid while fd_list itself
        # is alive; dup our own copy so it survives past this function.
        fd = os.dup(fd)
        if node_id is None:
            node_id = _node_from_pipewire()
        return node_id, fd

    def close(self):
        if self.handle is None:
            return
        try:
            self.conn.call_sync(BUS, self.handle, SESSION_IFACE, "Close", None, None,
                                Gio.DBusCallFlags.NONE, -1, None)
        except GLib.Error:
            pass
        self.handle = None


def _node_from_streams(streams):
    """Node id out of the Start response, when present.

    'streams' is a(ua{sv}) - an array of structs - GDBus demarshals this
    cleanly into a list of (int, dict) tuples. Kept defensive anyway (None on
    anything unexpected) since the fallback below is cheap and reliable.
    """
    if not isinstance(streams, (list, tuple)) or not streams:
        return None
    first = streams[0]
    try:
        return int(first[0])
    except (TypeError, ValueError, IndexError):
        return None


def _node_from_pipewire():
    """Ask PipeWire which video source the portal just published.

    Fallback for when the Start response carries no stream info. The portal
    node is the most recently created Video/Source, so the highest id wins.
    """
    if not shutil.which("pw-dump"):
        raise capture.CaptureError(
            "cannot read the PipeWire node id from the portal reply, and "
            "pw-dump is not installed to look it up")
    try:
        out = subprocess.run(["pw-dump"], capture_output=True, text=True,
                             timeout=10).stdout
        objects = json.loads(out or "[]")
    except (subprocess.SubprocessError, ValueError) as e:
        raise capture.CaptureError(f"pw-dump failed: {e}") from e
    ids = [o["id"] for o in objects
           if ((o.get("info") or {}).get("props") or {}).get("media.class")
           == "Video/Source"]
    if not ids:
        raise capture.CaptureError("no PipeWire video source to capture")
    return max(ids)


class _PortalStream(capture.FrameStream):
    """FrameStream that also tears down the portal session and the socket."""

    def __init__(self, *args, session=None, fd=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._session = session
        self._fd = fd

    def close(self):
        super().close()
        if self._session is not None:
            self._session.close()
            self._session = None
        if self._fd is not None:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None


def open_portal_stream(output=None, fps=30,
                       width=capture.CAPTURE_W, height=capture.CAPTURE_H, cancelled=None):
    """Negotiate with the portal and return a started FrameStream.

    `output` is ignored: which monitor gets shared is the user's choice in the
    portal dialog, not ours.
    """
    if not shutil.which("gst-launch-1.0"):
        raise capture.CaptureError(
            "gst-launch-1.0 is needed for portal capture "
            "(install gstreamer and gst-plugins-base)")
    session = PortalSession(cancelled=cancelled)
    try:
        node_id, fd = session.start()
    except Exception:
        session.close()
        raise

    src = f"pipewiresrc fd={fd}" + (f" path={node_id}" if node_id else "")
    cmd = ["gst-launch-1.0", "-q", *src.split(),
           "!", "videoconvert", "!", "videoscale", "!",
           f"video/x-raw,format=RGB,width={width},height={height}", "!",
           "fdsink", "fd=1"]
    stream = _PortalStream(cmd, width, height, 3, pass_fds=(fd,),
                           session=session, fd=fd)
    try:
        stream.cancelled = cancelled or (lambda: False)
        stream.start()
        stream.latest(timeout=8.0)
        return stream
    except Exception:
        stream.close()
        raise
