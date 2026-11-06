"""Screen capture for screen sync.

Frames come from a system binary writing raw RGB to stdout, the same choice as
`openssl` for DTLS: nothing to build, no Python bindings to keep alive.

Backends, in the order `pick_backend` tries them:
  wlroots  `wf-recorder`. Hyprland and Sway only, but needs no permission
           dialog and no PipeWire round trip - by far the smoothest path.
  portal   xdg-desktop-portal ScreenCast feeding `gst-launch-1.0 pipewiresrc`.
           The universal one: GNOME, KDE, wlroots. Asks the user once, then a
           restore token keeps it quiet.
  x11      `ffmpeg -f x11grab`, for plain X11 sessions.

A backend is just a command plus how its pixels are laid out, so adding one
means adding a few strings, not a class hierarchy.
"""

import colorsys
import os
import shutil
import subprocess
import threading
import time

# Small on purpose: region averages need no detail, and 64x36 is ~7 KB a frame.
CAPTURE_W, CAPTURE_H = 64, 36


class CaptureError(RuntimeError):
    """No usable backend, or the capture command died."""


class FrameStream:
    """Runs a capture command and keeps only the newest frame.

    Dropping stale frames is the whole point. The lamps are driven at a fixed
    rate; if the consumer ever falls behind a queue would make it drift further
    behind the screen every second, so the reader overwrites instead of piling
    up.
    """

    def __init__(self, cmd, width, height, bpp, pass_fds=()):
        self.cmd = cmd
        self.width, self.height, self.bpp = width, height, bpp
        self.frame_size = width * height * bpp
        self._pass_fds = tuple(pass_fds)
        self._latest = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._proc = None
        self._reader = None
        self._stderr = b""
        self._frame_time = 0
        self.cancelled = lambda: False
        self._drainer = None

    def start(self):
        try:
            self._proc = subprocess.Popen(
                self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                pass_fds=self._pass_fds)
        except FileNotFoundError as e:
            raise CaptureError(f"{self.cmd[0]} not found") from e
        self._drainer = threading.Thread(target=self._drain_errors, daemon=True)
        self._drainer.start()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()
        return self

    def _drain_errors(self):
        proc = self._proc
        try:
            for line in iter(lambda: proc.stderr.read1(2048), b""):
                self._stderr = (self._stderr + line)[-2048:]
        except (OSError, ValueError):
            pass

    def _read(self):
        out = self._proc.stdout
        while not self._stop.is_set():
            buf = out.read(self.frame_size)     # blocks until full or EOF
            if buf is None or len(buf) < self.frame_size:
                break
            with self._lock:
                self._latest = buf
                self._frame_time = time.monotonic()

    def latest(self, timeout=5.0):
        """Newest frame, waiting for the first one to arrive."""
        deadline = time.monotonic() + timeout
        while True:
            if self.cancelled():
                raise CaptureError("capture cancelled")
            with self._lock:
                if self._latest is not None and self._proc.poll() is None:
                    if time.monotonic() - self._frame_time > timeout:
                        raise CaptureError("capture stopped producing frames")
                    return self._latest
            if self._proc.poll() is not None:
                if self._drainer:
                    self._drainer.join(timeout=.2)
                err = self._stderr.decode(errors="replace")[-400:]
                raise CaptureError(f"{self.cmd[0]} exited: {err.strip()}")
            if time.monotonic() >= deadline:
                raise CaptureError(f"no frame from {self.cmd[0]} in {timeout:g}s")
            time.sleep(0.01)

    def close(self):
        self._stop.set()
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2)
        for thread in (self._reader, self._drainer):
            if thread and thread is not threading.current_thread():
                thread.join(timeout=.5)
        if self._proc:
            for pipe in (self._proc.stdout, self._proc.stderr):
                if pipe:
                    pipe.close()


# -- pixel math ------------------------------------------------------------

def region_average(buf, width, bpp, box):
    """Mean (r, g, b) over a pixel box (x0, y0, x1, y1), end-exclusive.

    Sums whole byte slices so the per-pixel loop stays in C; a pure Python
    loop over even a small frame costs more than the capture itself.
    """
    x0, y0, x1, y1 = box
    span = x1 - x0
    if span <= 0 or y1 <= y0:
        return (0, 0, 0)
    row_bytes = width * bpp
    r = g = b = 0
    for y in range(y0, y1):
        start = y * row_bytes + x0 * bpp
        row = buf[start:start + span * bpp]
        r += sum(row[0::bpp])
        g += sum(row[1::bpp])
        b += sum(row[2::bpp])
    n = span * (y1 - y0)
    return (r // n, g // n, b // n)


def punch(rgb, saturation=1.0, gamma=1.0):
    """Push an averaged color towards something a lamp renders well.

    Averaging a screen pulls everything towards grey, which lamps show as dull
    white. Saturation is the knob worth having on real hardware; gamma darkens
    the dim end so a mostly black scene does not glow.
    """
    r, g, b = (c / 255.0 for c in rgb)
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(1.0, s * saturation)
    if gamma != 1.0:
        v = v ** gamma
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


# -- backends --------------------------------------------------------------

def _wlroots(output, fps, width, height):
    """wf-recorder pipes raw frames continuously - no per-frame process spawn.

    Measured 30 fps against ~8 fps for one `grim` per frame, where the cost is
    process spawn plus a compositor round trip and barely moves with scale.
    """
    if not shutil.which("wf-recorder") or not os.environ.get("WAYLAND_DISPLAY"):
        return None
    cmd = ["wf-recorder", "-c", "rawvideo", "-m", "rawvideo", "-x", "rgb0",
           "-F", f"scale={width}:{height}", "-D", "-r", str(fps), "-f", "pipe:1"]
    if output:
        cmd[1:1] = ["-o", output]
    return {"cmd": cmd, "bpp": 4}          # rgb0: R, G, B, padding


def _x11(output, fps, width, height):
    display = os.environ.get("DISPLAY")
    if os.environ.get("WAYLAND_DISPLAY") or not display:
        return None
    if not shutil.which("ffmpeg"):
        return None
    return {"cmd": ["ffmpeg", "-loglevel", "quiet", "-f", "x11grab",
                    "-framerate", str(fps), "-i", output or display,
                    "-vf", f"scale={width}:{height}", "-pix_fmt", "rgb24",
                    "-f", "rawvideo", "pipe:1"],
            "bpp": 3}


BACKENDS = {"wlroots": _wlroots, "x11": _x11}


def pick_backend(name=None, output=None, fps=30,
                 width=CAPTURE_W, height=CAPTURE_H):
    """First backend that is actually usable here, as a FrameStream spec.

    The portal backend lives in portal.py: it needs a D-Bus session and may
    prompt, so it is only reached through open_stream's explicit fallback.
    """
    order = [name] if name else list(BACKENDS)
    for key in order:
        fn = BACKENDS.get(key)
        if fn is None:
            continue
        spec = fn(output, fps, width, height)
        if spec:
            spec["backend"] = key
            return spec
    return None


def open_stream(name=None, output=None, fps=30,
                width=CAPTURE_W, height=CAPTURE_H, on_wait=None, cancelled=None):
    """Start capturing, falling back to the portal when no fast path fits.

    Returns a started FrameStream. The caller closes it.
    """
    spec = pick_backend(name, output, fps, width, height)
    fast_error = None
    if spec is not None:
        stream = FrameStream(spec["cmd"], width, height, spec["bpp"]).start()
        stream.cancelled = cancelled or (lambda: False)
        try:
            stream.latest(timeout=6.0)     # prove it really produces frames
            return stream
        except CaptureError as e:
            stream.close()
            if name or (cancelled and cancelled()):  # explicit choice or cancellation
                raise
            fast_error = e
    if name and name != "portal":
        raise CaptureError(f"backend '{name}' is not available here")
    if on_wait:
        on_wait()
    from .portal import open_portal_stream   # imported late: needs GDBus (PyGObject)
    try:
        return open_portal_stream(output, fps, width, height, cancelled=cancelled)
    except CaptureError as e:
        # report both, or the fast path's real reason stays invisible behind a
        # generic portal message
        if fast_error is not None:
            raise CaptureError(
                f"{spec['backend']} failed ({fast_error}); "
                f"portal failed ({e})") from e
        raise


if __name__ == "__main__":          # python -m huectl.capture
    # region_average is the one piece with real index arithmetic in it
    W, H, BPP = 4, 2, 3
    #  left half red, right half blue
    row = bytes([255, 0, 0] * 2 + [0, 0, 255] * 2)
    frame = row * H
    assert region_average(frame, W, BPP, (0, 0, 2, 2)) == (255, 0, 0), "left half"
    assert region_average(frame, W, BPP, (2, 0, 4, 2)) == (0, 0, 255), "right half"
    assert region_average(frame, W, BPP, (0, 0, 4, 2)) == (127, 0, 127), "whole"
    assert region_average(frame, W, BPP, (1, 0, 1, 2)) == (0, 0, 0), "empty box"

    # padded pixels (wf-recorder's rgb0) must be skipped, not averaged in
    padded = bytes([255, 0, 0, 0] * 2) * H
    assert region_average(padded, 2, 4, (0, 0, 2, 2)) == (255, 0, 0), "bpp=4 stride"

    assert punch((128, 128, 128), saturation=2.0) == (128, 128, 128), "grey has no hue"
    r, g, b = punch((200, 100, 100), saturation=2.0)
    assert r > 200 - 1 and g < 100 and b < 100, f"saturation should bite: {(r, g, b)}"
    assert punch((255, 255, 255), gamma=2.0)[0] == 255, "gamma keeps white white"
    assert punch((25, 25, 25), gamma=2.0)[0] < 25, "gamma darkens the dim end"

    print("capture self-check OK")
