"""Apply the exact source-bound DLL94 cold-miss candidate after validation."""
from pathlib import Path
import argparse, hashlib, importlib.util, json

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('packet_outline_stage', ROOT / 'work/prepare-packet-miss-outline.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
old, new, manifest = module.stage()
proof = json.loads((ROOT / 'work/packet-miss-outline-regression/result.json').read_text())
assert proof['compile_returncode'] == proof['test_returncode'] == 0
assert '23563 checks, 0 failures' in proof['output']
assert proof['candidate_sha256'] == manifest['candidate_sha256']
fixture = (ROOT / 'work/packet-miss-outline-regression/test.cpp').read_text()
assert hashlib.sha256(fixture.encode()).hexdigest() == proof['fixture_sha256']
for name, expected in proof['unchanged_dependencies'].items():
    content = (ROOT / 'CvGameCoreDLL_Expansion2' / name).read_text(encoding='utf-8-sig')
    assert hashlib.sha256(content.encode()).hexdigest() == expected, name
path = ROOT / module.PATH
raw = path.read_bytes()
assert raw.decode('utf-8-sig').replace('\r\n', '\n') == old
if args.apply:
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    newline = '\r\n' if b'\r\n' in raw else '\n'
    path.write_bytes(bom + new.replace('\n', newline).encode())
print(json.dumps({'applied': args.apply, 'candidate_sha256': manifest['candidate_sha256'],
                  'whole_reverse_exact': manifest['whole_reverse_exact'],
                  'checked_unchanged_dependencies': len(proof['unchanged_dependencies'])}))
