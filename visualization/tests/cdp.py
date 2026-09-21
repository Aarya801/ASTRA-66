"""Minimal Chrome DevTools Protocol client (standard library only).

Used by the browser smoke test to drive the built visualiser in headless Chrome without
adding a Node test runner or any external dependency. If no Chrome/Edge binary is found the
caller skips the test rather than failing it.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_chrome() -> str | None:
    env = os.environ.get("CHROME_PATH")
    if env and Path(env).exists():
        return env
    for c in CANDIDATES:
        if Path(c).exists():
            return c
    for name in ("google-chrome", "chromium", "chrome", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class WS:
    """Tiny WebSocket client: text frames, client-masked, no extensions."""

    def __init__(self, url: str, timeout: float = 60.0):
        _, rest = url.split("://", 1)
        hostport, path = rest.split("/", 1)
        host, port = hostport.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=timeout)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall(
            f"GET /{path} HTTP/1.1\r\nHost: {hostport}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n".encode())
        buf = b""
        while b"\r\n\r\n" not in buf:
            buf += self.sock.recv(4096)
        if b"101" not in buf.split(b"\r\n", 1)[0]:
            raise RuntimeError("websocket handshake failed")
        self.rest = buf.split(b"\r\n\r\n", 1)[1]
        self._id = 0
        self.events: list[dict] = []

    def _read(self, n: int) -> bytes:
        while len(self.rest) < n:
            chunk = self.sock.recv(1 << 16)
            if not chunk:
                raise RuntimeError("connection closed")
            self.rest += chunk
        out, self.rest = self.rest[:n], self.rest[n:]
        return out

    def _send(self, payload: bytes) -> None:
        mask = os.urandom(4)
        n = len(payload)
        header = b"\x81"
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def _recv(self) -> dict:
        while True:
            frame = b""
            while True:
                b0, b1 = self._read(2)
                fin, opcode = b0 & 0x80, b0 & 0x0F
                length = b1 & 0x7F
                if length == 126:
                    length = struct.unpack(">H", self._read(2))[0]
                elif length == 127:
                    length = struct.unpack(">Q", self._read(8))[0]
                frame += self._read(length)
                if fin:
                    break
            if opcode in (0, 1):
                return json.loads(frame.decode("utf-8"))
            if opcode == 8:
                raise RuntimeError("websocket closed by peer")

    def call(self, method: str, params: dict | None = None, timeout: float = 60.0):
        self._id += 1
        want = self._id
        self._send(json.dumps({"id": want, "method": method, "params": params or {}}).encode())
        deadline = time.time() + timeout
        while time.time() < deadline:
            msg = self._recv()
            if msg.get("id") == want:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            self.events.append(msg)
        raise TimeoutError(method)

    def evaluate(self, expression: str, timeout: float = 60.0):
        """Evaluate JS (async allowed) and return the JSON value."""
        res = self.call("Runtime.evaluate", {
            "expression": expression, "awaitPromise": True, "returnByValue": True,
        }, timeout=timeout)
        if res.get("exceptionDetails"):
            raise RuntimeError(res["exceptionDetails"].get("text", "JS exception")
                               + " :: " + json.dumps(res["exceptionDetails"].get("exception", {}))[:300])
        return res.get("result", {}).get("value")


class Browser:
    """Headless Chrome, one page, closed on exit."""

    def __init__(self, chrome: str, width=1600, height=950):
        self.profile = tempfile.mkdtemp(prefix="astra66_ui_")
        self.port = free_port()
        self.proc = subprocess.Popen(
            [chrome, "--headless=new", f"--remote-debugging-port={self.port}",
             f"--user-data-dir={self.profile}", "--no-first-run", "--no-default-browser-check",
             "--disable-extensions", f"--window-size={width},{height}",
             "--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--disable-gpu-sandbox",
             "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.ws = None
        for _ in range(80):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{self.port}/json/list", timeout=2) as fh:
                    tabs = [t for t in json.load(fh) if t.get("type") == "page"]
                if tabs:
                    self.ws = WS(tabs[0]["webSocketDebuggerUrl"])
                    break
            except Exception:
                time.sleep(0.25)
        if not self.ws:
            self.close()
            raise RuntimeError("could not start headless Chrome")
        self.ws.call("Page.enable")
        self.ws.call("Runtime.enable")
        self.ws.call("Log.enable")

    def goto(self, url: str, settle: float = 1.5):
        self.ws.call("Page.navigate", {"url": url})
        deadline = time.time() + 60
        while time.time() < deadline:
            msg = self.ws._recv()
            if msg.get("method") == "Page.loadEventFired":
                break
            self.ws.events.append(msg)
        time.sleep(settle)

    def console_errors(self) -> list[str]:
        out = []
        for e in self.ws.events:
            if e.get("method") == "Runtime.exceptionThrown":
                out.append(str(e["params"]["exceptionDetails"].get("text")))
            if e.get("method") == "Runtime.consoleAPICalled" and e["params"].get("type") == "error":
                out.append(" ".join(str(a.get("value", a.get("description", ""))) for a in e["params"]["args"]))
            if e.get("method") == "Log.entryAdded" and e["params"]["entry"].get("level") == "error":
                out.append(str(e["params"]["entry"].get("text")))
        return out

    def set_viewport(self, width: int, height: int, mobile: bool = False):
        self.ws.call("Emulation.setDeviceMetricsOverride", {
            "width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile})

    def clear_viewport(self):
        self.ws.call("Emulation.clearDeviceMetricsOverride")

    def screenshot(self, path: Path):
        res = self.ws.call("Page.captureScreenshot", {"format": "png"})
        Path(path).write_bytes(base64.b64decode(res["data"]))

    def distinct_colours(self, sample_step: int = 3) -> int:
        """Decode a screenshot and count distinct colours - 1 means a blank frame.

        The capture is scaled down first: the PNG decoder below is pure Python, and a
        quarter-size image is as good for "is anything on screen?" while being much faster.
        """
        metrics = self.ws.evaluate("JSON.stringify([innerWidth, innerHeight])")
        w, h = json.loads(metrics)
        res = self.ws.call("Page.captureScreenshot", {
            "format": "png",
            "clip": {"x": 0, "y": 0, "width": w, "height": h, "scale": 0.25},
        })
        return png_distinct_colours(base64.b64decode(res["data"]), sample_step)

    def close(self):
        """Stop Chrome and its renderer children.

        terminate() alone leaves the child processes running on Windows, and they accumulate
        across repeated test runs until everything crawls.
        """
        if not self.proc:
            return
        try:
            self.proc.terminate()
            self.proc.wait(timeout=5)
        except Exception:
            pass
        if self.proc.poll() is None or os.name == "nt":
            try:
                if os.name == "nt":
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(self.proc.pid)],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                else:
                    self.proc.kill()
            except Exception:
                pass
        try:
            shutil.rmtree(self.profile, ignore_errors=True)
        except Exception:
            pass


# ------------------------------------------------------------------ tiny PNG reader
def png_distinct_colours(data: bytes, step: int = 6) -> int:
    """Count distinct colours in an 8-bit non-interlaced truecolour PNG (stdlib only).

    Chrome's Page.captureScreenshot returns exactly that, so no image library is needed.
    """
    import zlib

    if data[:8] != bytes([137, 80, 78, 71, 13, 10, 26, 10]):
        raise ValueError("not a PNG")
    pos, idat, width = 8, bytearray(), None
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        ctype = data[pos + 4:pos + 8]
        body = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", body[:13])
            if depth != 8 or colour not in (2, 6) or interlace:
                raise ValueError(f"unsupported PNG (depth {depth}, colour {colour})")
            channels = 3 if colour == 2 else 4
        elif ctype == b"IDAT":
            idat += body
        elif ctype == b"IEND":
            break
        pos += 12 + length

    raw = zlib.decompress(bytes(idat))
    stride = width * channels
    prev = bytearray(stride)
    colours = set()
    offset = 0
    for y in range(height):
        filt = raw[offset]
        line = bytearray(raw[offset + 1:offset + 1 + stride])
        offset += 1 + stride
        if filt == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filt == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif filt == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif filt == 4:
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 0xFF
        if y % step == 0:
            for x in range(0, width, step):
                i = x * channels
                colours.add((line[i] >> 3, line[i + 1] >> 3, line[i + 2] >> 3))
        prev = line
    return len(colours)
