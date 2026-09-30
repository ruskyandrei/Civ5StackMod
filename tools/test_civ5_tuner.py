"""Offline protocol/lifecycle tests and real Lua 5.1 result-wrapper checks."""
import importlib.util
import json
from pathlib import Path
import socket
import struct
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import civ5_tuner as tuner


class ProtocolTests(unittest.TestCase):
    def test_unicode_frame_and_nul_rejection(self):
        data = tuner.encode_packet("LSQ:caf\u00e9", 73)
        size, ident = struct.unpack("<II", data[:8])
        self.assertEqual((size, ident), (10, 73))
        self.assertEqual(data[8:], b"LSQ:caf\xc3\xa9\0")
        with self.assertRaises(tuner.TunerError):
            tuner.encode_packet("bad\0code", 1)

    def test_fragmented_frame(self):
        a, b = socket.socketpair()
        try:
            # Replies contain NUL-separated strings, unlike commands.
            body = b"3\0InGame\0"
            packet = struct.pack("<II", len(body), 9) + body
            def send():
                for byte in packet:
                    a.sendall(bytes([byte]))
            worker = threading.Thread(target=send)
            worker.start()
            self.assertEqual(tuner.recv_packet(b), (9, ["3", "InGame"]))
            worker.join()
        finally:
            a.close(); b.close()

    def test_invalid_packet_bound(self):
        a, b = socket.socketpair()
        try:
            a.sendall(struct.pack("<II", tuner.MAX_PACKET + 1, 1))
            with self.assertRaises(tuner.TunerError):
                tuner.recv_packet(b)
        finally:
            a.close(); b.close()

    def test_context_validation(self):
        self.assertEqual(tuner.parse_states(["2", "InGame", "4", "LoadMenu"]),
                         [{"id": 2, "name": "InGame"}, {"id": 4, "name": "LoadMenu"}])
        for data in (["3"], ["bad", "InGame"], ["-1", "InGame"]):
            with self.assertRaises(tuner.TunerError):
                tuner.parse_states(data)

    def test_chunk_validation_and_utf8_join(self):
        data = json.dumps({"ok": True, "values": ["caf\u00e9" * 150]}, ensure_ascii=False).encode()
        chunks = [f"{i//256+1}/{(len(data)+255)//256}:" + data[i:i+256].hex()
                  for i in range(0, len(data), 256)]
        self.assertEqual(tuner.decode_result(chunks)["values"], ["caf\u00e9" * 150])
        for bad in (chunks[:-1], chunks + [chunks[0]], ["0/1:aa"], ["1/1025:aa"]):
            with self.assertRaises(tuner.TunerError):
                tuner.decode_result(bad)

    def test_persistent_response_matching_and_output_bound(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0)); listener.listen(1)
        errors = []
        def engine():
            try:
                with listener.accept()[0] as sock:
                    for i in range(2):
                        ident, command = tuner.recv_packet(sock)
                        self.assertEqual(command, ["LSQ:"])
                        # A stale reply must not complete the new request.
                        sock.sendall(tuner.encode_packet("99", ident + 100))
                        for _ in range(150):
                            body = b"O\0trace\0"
                            sock.sendall(struct.pack("<II", len(body), tuner.BROADCAST) + body)
                        body = b"2\0InGame\0"
                        sock.sendall(struct.pack("<II", len(body), ident) + body)
            except Exception as exc:
                errors.append(exc)
        worker = threading.Thread(target=engine); worker.start()
        client = tuner.TunerConnection(listener.getsockname()[1])
        try:
            for _ in range(2):
                response = client.request("LSQ:")
                self.assertEqual(response["reply"], ["2", "InGame"])
                self.assertEqual(len(response["output"]), 128)
                self.assertEqual(response["output_dropped"], 22)
        finally:
            client.close(); worker.join(); listener.close()
        self.assertEqual(errors, [])

    def test_timeout_never_retries(self):
        listener = socket.socket(); listener.bind(("127.0.0.1", 0)); listener.listen(1)
        received = []
        def engine():
            with listener.accept()[0] as sock:
                received.append(tuner.recv_packet(sock))
                self.assertEqual(sock.recv(1), b"")
        worker = threading.Thread(target=engine); worker.start()
        client = tuner.TunerConnection(listener.getsockname()[1])
        try:
            with self.assertRaisesRegex(tuner.TunerError, "outcome is unknown"):
                client.request("CMD:2:change()", timeout=.05)
            with self.assertRaises(tuner.TunerError):
                client.request("CMD:2:change()")
        finally:
            client.close(); worker.join(); listener.close()
        self.assertEqual(len(received), 1)


class LuaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Same local Lua 5.1 validation runtime used by existing UI fixtures.
        sys.path.insert(0, str(tuner.ROOT / "work" / "lua-validation"))
        from lupa.lua51 import LuaRuntime
        cls.runtime_type = LuaRuntime

    def run_lua(self, source):
        lua = self.runtime_type(unpack_returned_tuples=True)
        output = []
        lua.globals().print = lambda s: output.append(s)
        lua.execute(tuner.wrap_lua(source, "RESULT:"))
        return tuner.decode_result([line.split("RESULT:", 1)[1] for line in output])

    def test_typed_results_and_nil_positions(self):
        self.assertEqual(self.run_lua("return 4,nil,false,{city='caf\u00e9',units={1,2}},'a\\n\\0'")["values"],
                         [4, None, False, {"city": "caf\u00e9", "units": [1, 2]}, "a\n\0"])

    def test_mutations_keep_context_globals(self):
        self.assertEqual(self.run_lua("Civ5FixtureGlobal=9;return Civ5FixtureGlobal")["values"], [9])

    def test_error_classes(self):
        for source, message in [
            ("this is not lua", ""), ("error('fixture error')", "fixture error"),
            ("local t={};t.self=t;return t", "Circular"), ("return function()end", "Unsupported"),
            ("return {[2]=7}", "Object keys"), ("return 0/0", "Non-finite"),
            ("local t={};local x=t;for i=1,20 do x.child={};x=x.child end;return t", "limits"),
            ("return string.rep('x',262145)", "256 KiB"),
        ]:
            with self.subTest(source=source):
                result = self.run_lua(source)
                self.assertFalse(result["ok"])
                self.assertIn(message, result["error"])

    def test_source_limit(self):
        with self.assertRaises(tuner.TunerError):
            tuner.wrap_lua("x" * 65537, "R:")


if __name__ == "__main__":
    unittest.main()
