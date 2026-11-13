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
from .config import load_config, update_config

BUS = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
SCREENCAST = "org.freedesktop.portal.ScreenCast"
REQUEST_IFACE = "org.freedesktop.portal.Request"
SESSION_IFACE = "org.freedesktop.portal.Session"


def capabilities():
    try:
        conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = conn.call_sync(BUS, PATH, 'org.freedesktop.DBus.Properties', 'GetAll',
            GLib.Variant('(s)', (SCREENCAST,)), None, Gio.DBusCallFlags.NONE, 3000, None)
        data = reply.unpack()[0]
        return {'types':int(data.get('AvailableSourceTypes',0)), 'version':int(data.get('version',0)),
                'cursors':int(data.get('AvailableCursorModes',0))}
    except GLib.Error:
        return {'types':0, 'version':0, 'cursors':0}


def take_restore_token(key):
    def update(cfg):
        tokens=cfg.setdefault('sync_portal_tokens',{})
        token=tokens.pop(key,None)
        return token if isinstance(token,str) and token else None
    return update_config(update)


def store_restore_token(key, token):
    def update(cfg):
        if cfg.get('sync_portal_remember',False):
            cfg.setdefault('sync_portal_tokens',{})[key]=token
    update_config(update)


class PortalSession:
    """A ScreenCast session: create, select sources, start, open the remote."""

    def __init__(self, timeout_ms=120000, cancelled=None, source_type=1, remember=False, token_key="portal-selection"):
        self.source_type, self.remember, self.token_key = source_type, remember, token_key
        self.source_size = None
        self.source_serial = None
        self.cancelled = cancelled or (lambda: False)
        self.timeout_ms = timeout_ms
        try:
            self.conn = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as e:
            raise capture.CaptureError(f"no D-Bus session bus: {e}") from e
        self._token = uuid.uuid4().hex[:8]
        self.handle = None

    def _call(self, method, signature, args, reply_type):
        try:
            reply = self.conn.call_sync(
                BUS, PATH, SCREENCAST, method, GLib.Variant(signature, args),
                GLib.VariantType(reply_type), Gio.DBusCallFlags.NONE, -1, None)
        except GLib.Error as e:
            raise capture.CaptureError(f"{method}: {e}") from e
        return reply.unpack()[0]

    def _request(self, method, signature, args):
        """Subscribe before the call; use a private context per worker request.

        Fast CreateSession responses can precede the method reply. Buffer by
        returned path (including legacy portal paths), and never let the GTK
        main context dispatch a quit before this request's loop starts.
        """
        context=GLib.MainContext.new()
        context.push_thread_default()
        loop=GLib.MainLoop.new(context,False)
        responses={}
        request_path=None
        sources=[]
        sub_id=None
        timed_out=[]
        def response(_conn,_sender,path,_iface,_sig,params,*_a):
            if len(responses)<16 or path==request_path:
                responses[path]=params.unpack()
            if path==request_path:loop.quit()
        try:
            sub_id=self.conn.signal_subscribe(BUS,REQUEST_IFACE,'Response',None,None,
                                              Gio.DBusSignalFlags.NONE,response)
            request_path=self._call(method,signature,args,'(o)')
            def timeout(*_a):
                timed_out.append(True);loop.quit();return False
            def cancel(*_a):
                if self.cancelled():loop.quit();return False
                return True
            for interval,callback in [(self.timeout_ms,timeout),(50,cancel)]:
                source=GLib.timeout_source_new(interval);source.set_callback(callback);source.attach(context)
                sources.append(source)
            if request_path not in responses and not self.cancelled():loop.run()
            if self.cancelled() or timed_out:
                try:
                    self.conn.call_sync(BUS,request_path,REQUEST_IFACE,'Close',None,None,
                                        Gio.DBusCallFlags.NONE,2000,None)
                except GLib.Error:pass
                if self.cancelled():raise capture.CaptureCancelled('capture cancelled')
                raise capture.CaptureError('the portal did not answer in time')
            code,result=responses[request_path]
            if code!=0:
                raise capture.CaptureError('screen capture was refused' if code==1 else 'the portal failed to start screen capture')
            return result
        finally:
            for source in sources:source.destroy()
            if sub_id is not None:self.conn.signal_unsubscribe(sub_id)
            context.pop_thread_default()

    def _opts(self, suffix):
        return {"handle_token": GLib.Variant("s", f"{self._token}_{suffix}")}

    def start(self):
        """Run the handshake. Returns (node_id, pipewire_fd)."""
        caps=capabilities()
        if not caps['types'] & self.source_type:
            raise capture.CaptureError('This desktop portal does not support the requested capture source')
        options = self._opts("create")
        options["session_handle_token"] = GLib.Variant("s", f"{self._token}_session")
        res = self._request("CreateSession", "(a{sv})", (options,))
        self.handle = res["session_handle"]

        sel_opts = self._opts("select")
        sel_opts["multiple"] = GLib.Variant("b", False)
        sel_opts['types'] = GLib.Variant('u', self.source_type)
        if caps['cursors'] & 1:
            sel_opts['cursor_mode'] = GLib.Variant('u',1)
        if self.remember and caps['version'] >= 4:
            sel_opts['persist_mode'] = GLib.Variant('u',2)
            token=take_restore_token(self.token_key)
            if token:
                sel_opts['restore_token'] = GLib.Variant('s',token)
        self._request("SelectSources", "(oa{sv})", (self.handle, sel_opts))

        res = self._request("Start", "(osa{sv})", (self.handle, "", self._opts("start")))
        node_id = _node_from_streams(res.get("streams"))
        if self.remember and caps['version'] >= 4 and res.get('restore_token'):
            store_restore_token(self.token_key,res['restore_token'])
        streams=res.get('streams') or []
        if streams:
            if self.source_type==2 and streams[0][1].get('source_type')!=2:
                raise capture.CaptureError('The sharing picker selected a monitor or region. Open its Window tab and select a window.')
            serial=streams[0][1].get('pipewire-serial')
            if isinstance(serial,(str,int)) and str(serial).isdigit():self.source_serial=str(serial)
            size=streams[0][1].get('size')
            if size and len(size)==2 and all(type(v) is int and v>0 for v in size):
                self.source_size=list(size)

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
    window = output == 'portal-window'
    session = PortalSession(cancelled=cancelled, source_type=2 if window else 1,
                            remember=load_config().get('sync_portal_remember',False),
                            token_key='portal-window' if window else 'portal-selection')
    try:
        node_id, fd = session.start()
    except Exception:
        session.close()
        raise

    target = f" target-object={session.source_serial}" if session.source_serial else (f" path={node_id}" if node_id else "")
    src = f"pipewiresrc fd={fd}" + target
    cmd = ["gst-launch-1.0", "-q", *src.split(),
           "!", "videoconvert", "!", "videoscale", "!",
           f"video/x-raw,format=RGB,width={width},height={height}", "!",
           "fdsink", "fd=1"]
    stream = _PortalStream(cmd, width, height, 3, pass_fds=(fd,),
                           session=session, fd=fd)
    try:
        stream.cancelled = cancelled or (lambda: False)
        stream.backend = 'portal-window' if window else 'portal-monitor'
        stream.source_size = session.source_size
        stream.start()
        stream.latest(timeout=8.0)
        return stream
    except Exception:
        stream.close()
        raise
