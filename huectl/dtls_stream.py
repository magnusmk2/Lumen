"""DTLS-PSK transport to the bridge for Entertainment streaming.

The bridge listens for encrypted UDP on port 2100. Authentication is a
pre-shared key: the PSK identity is the application key (username) and the PSK
itself is the client_key (hex), both obtained at pairing.

Rather than depend on a Python DTLS binding (python-mbedtls is unmaintained and
breaks against Mbed TLS 3.x on modern distros), this drives the system
`openssl s_client`, which is actively maintained and supports DTLS-PSK. We spawn
it once, then write HueStream frames to its stdin - each write is sent as a DTLS
application record (one datagram).

Requires the `openssl` binary (present on virtually every Linux system).
`-ign_eof` keeps stdin binary-safe (disables s_client's R/Q command parsing).
"""

import shutil
import threading
import subprocess

HUE_DTLS_PORT = 2100
PSK_CIPHER = "PSK-AES128-GCM-SHA256"
_FAIL_MARKER = "Cipher is (NONE)"   # s_client prints this when the handshake fails


class HueDTLS:
    def __init__(self, ip, identity, psk_hex, port=HUE_DTLS_PORT):
        self.ip = ip
        self.identity = identity
        self.psk_hex = psk_hex
        self.port = port
        self._proc = None
        self._reader = None
        self._done = threading.Event()
        self._connected = False
        self._error = None

    def _cmd(self):
        return ["openssl", "s_client", "-dtls1_2",
                "-connect", f"{self.ip}:{self.port}",
                "-cipher", PSK_CIPHER,
                "-psk", self.psk_hex, "-psk_identity", self.identity,
                "-ign_eof"]

    def connect(self, timeout=6.0):
        if shutil.which("openssl") is None:
            raise RuntimeError("the 'openssl' binary is required for screen sync")
        self._proc = subprocess.Popen(
            self._cmd(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0)
        self._reader = threading.Thread(target=self._drain, args=(self._proc,), daemon=True)
        self._reader.start()
        if not self._done.wait(timeout):
            self.close()
            raise RuntimeError("DTLS handshake timed out")
        if not self._connected:
            self.close()
            raise RuntimeError(self._error or "DTLS handshake failed")

    def _drain(self, proc):
        """Watch s_client output: success = negotiated cipher name; failure =
        '(NONE)' cipher, or the process closing its output early."""
        out = proc.stdout
        try:
            for raw in iter(out.readline, b""):
                text = raw.decode("utf-8", "replace")
                if PSK_CIPHER in text:
                    self._connected = True
                    self._done.set()
                    continue
                if _FAIL_MARKER in text:
                    self._error = ("DTLS handshake failed - check the client_key "
                                   "(re-pair the bridge if needed)")
                    self._done.set()
                    return
        except Exception:  # noqa: BLE001
            pass
        if not self._connected:
            self._error = self._error or "DTLS connection closed"
            self._done.set()

    def send(self, frame):
        self._proc.stdin.write(frame)
        self._proc.stdin.flush()

    def close(self):
        if self._proc is not None:
            try:
                self._proc.stdin.close()
            except Exception:  # noqa: BLE001
                pass
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:  # noqa: BLE001
                try:
                    self._proc.kill()
                    self._proc.wait(timeout=2)
                except Exception:  # noqa: BLE001
                    pass
        if self._reader and self._reader is not threading.current_thread():
            self._reader.join(timeout=.5)
        if self._proc:
            for pipe in (self._proc.stdin, self._proc.stdout):
                try:
                    pipe.close()
                except (OSError, ValueError):
                    pass
        self._proc = None
