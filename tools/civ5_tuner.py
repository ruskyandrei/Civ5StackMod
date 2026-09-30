"""Local Civ V Lua automation using the installed game's debug protocol.

No SDK assemblies, GUI automation, third-party Python packages or DLL changes.
Keep one `serve` process alive; repeated short-lived engine connections can stall
Civ V's tuner. Commands are never retried after an ambiguous timeout.
"""
from __future__ import annotations

import argparse
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import socket
import struct
import threading
import time
import urllib.error
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SESSION = ROOT / "work" / "tuner-session.json"
MAX_PACKET = 524288  # Receive limit in the installed Civ V SDK.
MAX_SOURCE = 65536
MAX_RESULT = 262144
BROADCAST = 0xFFFFFFFF


class TunerError(RuntimeError):
    pass


def encode_packet(text: str, ident: int) -> bytes:
    if "\0" in text:
        raise TunerError("NUL is not allowed in a protocol command")
    body = text.encode("utf-8") + b"\0"
    if len(body) > MAX_PACKET:
        raise TunerError("Command exceeds the packet limit")
    return struct.pack("<II", len(body), ident) + body


def recv_exact(sock: socket.socket, count: int) -> bytes:
    parts = bytearray()
    while len(parts) < count:
        part = sock.recv(count - len(parts))
        if not part:
            raise TunerError("Game disconnected")
        parts.extend(part)
    return bytes(parts)


def recv_packet(sock: socket.socket) -> tuple[int, list[str]]:
    size, ident = struct.unpack("<II", recv_exact(sock, 8))
    if not 1 <= size <= MAX_PACKET:
        raise TunerError(f"Invalid engine packet size: {size}")
    data = recv_exact(sock, size)
    if not data.endswith(b"\0"):
        raise TunerError("Engine packet is not NUL terminated")
    return ident, data[:-1].decode("utf-8", errors="replace").split("\0")


def parse_states(strings: list[str]) -> list[dict]:
    if len(strings) % 2:
        raise TunerError("Malformed Lua context list")
    result = []
    for i in range(0, len(strings), 2):
        try:
            ident = int(strings[i])
        except ValueError as exc:
            raise TunerError("Invalid Lua context ID") from exc
        if not 0 <= ident <= 0xFFFFFFFF:
            raise TunerError("Invalid Lua context ID")
        result.append({"id": ident, "name": strings[i + 1]})
    return result


def lua_string(text: str) -> str:
    # Lua 5.1 accepts decimal byte escapes, not JSON's Unicode escapes.
    return '"' + ''.join("\\%03d" % b for b in text.encode("utf-8")) + '"'


def wrap_lua(source: str, marker: str) -> str:
    if len(source.encode("utf-8")) > MAX_SOURCE:
        raise TunerError("Lua source exceeds 64 KiB")
    template = (ROOT / "tools" / "tuner_result.lua").read_text(encoding="utf-8")
    return template + "\nCiv5StackAutomationRun(" + lua_string(source) + "," + lua_string(marker) + ")"


def decode_result(chunks: list[str]) -> dict:
    parts = {}
    expected = None
    for chunk in chunks:
        header, hex_data = chunk.split(":", 1)
        index, total = map(int, header.split("/", 1))
        if not 1 <= index <= total <= (MAX_RESULT + 255) // 256 or index in parts:
            raise TunerError("Invalid or duplicate result chunk")
        if expected is not None and total != expected:
            raise TunerError("Inconsistent result chunk count")
        expected = total
        part = bytes.fromhex(hex_data)
        if not 1 <= len(part) <= 256:
            raise TunerError("Invalid result chunk size")
        parts[index] = part
    if expected is None or len(parts) != expected:
        raise TunerError("Incomplete structured Lua result")
    return json.loads(b"".join(parts[i] for i in range(1, expected + 1)).decode("utf-8"))


class TunerConnection:
    def __init__(self, port: int = 4318, connect_timeout: float = 3):
        self.sock = socket.create_connection(("127.0.0.1", port), connect_timeout)
        self.sock.settimeout(None)
        self.condition = threading.Condition()
        self.serial = threading.Lock()
        self.next_id = 1
        self.pending_id = None
        self.reply = None
        self.output = deque(maxlen=128)
        self.output_bytes = 0
        self.output_dropped = 0
        self.marker = None
        self.structured = []
        self.initialized_contexts = set()
        self.error = None
        threading.Thread(target=self._reader, daemon=True).start()

    def close(self):
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.sock.close()

    def _reader(self):
        try:
            while True:
                ident, strings = recv_packet(self.sock)
                with self.condition:
                    if ident == self.pending_id:
                        self.reply = strings
                    elif ident == BROADCAST and strings and strings[0] == "O":
                        if self.pending_id is not None:
                            for text in strings[1:]:
                                size = len(text.encode("utf-8"))
                                if self.marker and self.marker in text:
                                    if len(self.structured) < (MAX_RESULT + 255) // 256 and size <= 1024:
                                        self.structured.append(text.split(self.marker, 1)[1])
                                    else:
                                        self.error = "Invalid or duplicate structured result"
                                elif len(self.output) == self.output.maxlen or self.output_bytes + size > MAX_RESULT:
                                    self.output_dropped += 1
                                else:
                                    self.output.append(text)
                                    self.output_bytes += size
                    elif ident == BROADCAST and strings == ["Closing"]:
                        raise TunerError("Game is closing")
                    self.condition.notify_all()
        except (OSError, TunerError) as exc:
            with self.condition:
                self.error = str(exc)
                self.condition.notify_all()

    def request(self, command: str, timeout: float = 15, marker=None) -> dict:
        with self.serial:
            with self.condition:
                if self.error:
                    raise TunerError(self.error)
                ident = self.next_id
                self.next_id += 1
                self.pending_id = ident
                self.reply = None
                self.output.clear()
                self.structured.clear()
                self.marker = marker
                self.output_bytes = self.output_dropped = 0
                packet = encode_packet(command, ident)
                self.sock.sendall(packet)
                deadline = time.monotonic() + timeout
                while self.reply is None and not self.error:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self.error = "Engine reply timed out; execution outcome is unknown. Command was not retried."
                        self.close()
                        break
                    self.condition.wait(remaining)
                self.pending_id = None
                if self.error and self.reply is None:
                    raise TunerError(self.error)
                return {"reply": self.reply, "output": list(self.output), "output_dropped": self.output_dropped,
                        "structured": list(self.structured)}

    def states(self, timeout=15):
        return parse_states(self.request("LSQ:", timeout)["reply"])

    def execute(self, context: str, source: str, timeout=15):
        deadline = time.monotonic() + timeout
        def budget():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TunerError("Total command budget expired before sending the next request")
            return remaining
        if len(source.encode("utf-8")) > MAX_SOURCE:
            raise TunerError("Lua source exceeds 64 KiB")
        states = self.states(budget())
        found = [s for s in states if s["name"] == context]
        if len(found) != 1:
            raise TunerError(f"Expected one context named {context!r}, found {len(found)}. List contexts first.")
        marker = "C5RESULT_" + uuid.uuid4().hex + ":"
        ident = found[0]["id"]
        if ident not in self.initialized_contexts:
            self.upload(ident, (ROOT / "tools" / "tuner_result.lua").read_text(encoding="utf-8"), budget())
            self.raw(ident, "local f,e=loadstring(Civ5StackAutomationUpload,'Civ5AutomationResults');Civ5StackAutomationUpload=nil;assert(f,e)()", budget())
            self.initialized_contexts.add(ident)
        self.upload(ident, source, budget())
        command = "local s=Civ5StackAutomationUpload;Civ5StackAutomationUpload=nil;Civ5StackAutomationRun(s," + lua_string(marker) + ")"
        result = self.raw(ident, command, budget(), marker)
        parsed = decode_result(result["structured"])
        parsed["context"] = found[0]
        parsed["output"] = [line for line in result["output"] if marker not in line]
        parsed["output_dropped"] = result["output_dropped"]
        return parsed

    def raw(self, ident, code, timeout, marker=None):
        # The Civ V console has a much smaller source buffer than its packets.
        if len(code.encode("utf-8")) > 1400:
            raise TunerError("Internal console command exceeds its safe size")
        result = self.request(f"CMD:{ident}:{code}", timeout, marker)
        if any(value.startswith("ERR") for value in result["reply"]):
            raise TunerError(f"Engine rejected Lua command: {result['reply']!r}")
        return result

    def upload(self, ident, source, timeout):
        deadline = time.monotonic() + timeout
        self.raw(ident, "Civ5StackAutomationUpload=''", timeout)
        data = source.encode("utf-8")
        for offset in range(0, len(data), 256):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TunerError("Source upload budget expired; the uploaded source was not executed")
            chunk = '"' + ''.join("\\%03d" % b for b in data[offset:offset + 256]) + '"'
            self.raw(ident, "Civ5StackAutomationUpload=Civ5StackAutomationUpload.." + chunk, remaining)


def serve(args):
    session = Path(args.session)
    if session.exists():
        raise TunerError("Session file already exists. Stop the previous service, or remove its stale file after checking its PID.")
    token = secrets.token_urlsafe(32)
    deadline = time.monotonic() + args.wait
    while True:
        try:
            connection = TunerConnection(args.game_port)
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    try:
        print(json.dumps({"connected": True, "contexts": connection.states()}), flush=True)
    except Exception:
        connection.close()
        raise
    # Serialise context resolution and execution as one transaction.
    command_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            if self.headers.get("Authorization") != "Bearer " + token:
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= MAX_PACKET:
                    raise TunerError("Invalid request size")
                job = json.loads(self.rfile.read(length))
                if not isinstance(job, dict):
                    raise TunerError("Expected a JSON request object")
                timeout = float(job.get("timeout", 15))
                if not 0 < timeout <= 120:
                    raise TunerError("Timeout must be greater than zero and at most 120 seconds")
                if not command_lock.acquire(blocking=False):
                    raise TunerError("Another command is running; this request was not queued or executed")
                try:
                    if self.path == "/states":
                        result = {"ok": True, "contexts": connection.states(timeout)}
                    elif self.path == "/exec":
                        if not isinstance(job.get("context"), str) or not isinstance(job.get("source"), str):
                            raise TunerError("Context and source must be strings")
                        result = connection.execute(job["context"], job["source"], timeout)
                    elif self.path == "/stop":
                        result = {"ok": True, "stopping": True}
                        threading.Thread(target=server.shutdown, daemon=True).start()
                    else:
                        raise TunerError("Unknown endpoint")
                finally:
                    command_lock.release()
                payload = json.dumps(result, ensure_ascii=True).encode()
                self.send_response(200)
            except (TunerError, ValueError, KeyError, TypeError, OSError) as exc:
                payload = json.dumps({"ok": False, "error": str(exc)}).encode()
                self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    server.daemon_threads = True
    import os
    session.parent.mkdir(parents=True, exist_ok=True)
    session.write_text(json.dumps({"port": server.server_port, "token": token, "pid": os.getpid()}), encoding="utf-8")
    print(json.dumps({"ready": True, "port": server.server_port, "session": str(session)}), flush=True)
    try:
        server.serve_forever()
    finally:
        connection.close()
        server.server_close()
        session.unlink(missing_ok=True)


def call_service(session, endpoint, job, timeout=15):
    data = json.loads(Path(session).read_text(encoding="utf-8"))
    request = urllib.request.Request(f"http://127.0.0.1:{int(data['port'])}/{endpoint}",
        data=json.dumps(job).encode(), headers={"Authorization": "Bearer " + data["token"], "Content-Type": "application/json"})
    try:
        response = urllib.request.urlopen(request, timeout=timeout + 5)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        result = json.load(response)
    return result


def client(args, endpoint, job):
    result = call_service(args.session, endpoint, job, args.timeout)
    if endpoint == "stop" and result.get("ok"):
        deadline = time.monotonic() + 5
        while Path(args.session).exists() and time.monotonic() < deadline:
            time.sleep(.05)
        if Path(args.session).exists():
            raise TunerError("Service accepted stop but has not removed its session file yet")
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0 if result.get("ok") else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", default=str(DEFAULT_SESSION))
    parser.add_argument("--timeout", type=float, default=15)
    sub = parser.add_subparsers(dest="command", required=True)
    service = sub.add_parser("serve")
    service.add_argument("--port", type=int, default=0)
    service.add_argument("--game-port", type=int, default=4318)
    service.add_argument("--wait", type=float, default=90, help="Wait for the game to open its tuner port")
    sub.add_parser("states")
    sub.add_parser("stop")
    execute = sub.add_parser("exec")
    execute.add_argument("--context", default="InGame")
    source = execute.add_mutually_exclusive_group(required=True)
    source.add_argument("--code")
    source.add_argument("--file", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            serve(args)
            return 0
        if args.command in ("states", "stop"):
            return client(args, args.command, {"timeout": args.timeout})
        code = args.code if args.code is not None else args.file.read_text(encoding="utf-8-sig")
        return client(args, "exec", {"context": args.context, "source": code, "timeout": args.timeout})
    except (TunerError, OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
