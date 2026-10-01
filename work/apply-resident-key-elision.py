"""Apply the frozen source-bound resident shortcut over outlined DLL96."""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, sys

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
subprocess.run([sys.executable, str(ROOT / 'work/stage-resident-key-elision.py'),
                '--control', '4cd0a4cfe', '--output', 'work/resident-key-elision-outline-staged'],
               check=True, capture_output=True)
stage = ROOT / 'work/resident-key-elision-outline-staged'
manifest = json.loads((stage / 'manifest.json').read_text())
proof = json.loads((ROOT / 'work/resident-key-elision-outline-regression/result.json').read_text())
assert proof['compile_returncode'] == proof['test_returncode'] == 0
assert re.search(r'RESIDENT ACTUAL93: \d+ checks, 0 failures;', proof['output'])
assert proof['candidate_sha256'] == manifest['candidate_sha256']
assert manifest['original_projection_body_unchanged'] and manifest['original_miss_helper_unchanged']
assert manifest['formatter_arity'] == 47 and manifest['formatter_worst_bytes'] < 2048
fixture = (ROOT / 'work/resident-key-elision-outline-regression/test.cpp').read_text()
assert hashlib.sha256(fixture.encode()).hexdigest() == proof['fixture_sha256']
for name, expected in proof['unchanged_dependencies'].items():
    source = (ROOT / 'CvGameCoreDLL_Expansion2' / name).read_text(encoding='utf-8-sig')
    assert hashlib.sha256(source.encode()).hexdigest() == expected, name
path = ROOT / 'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
raw = path.read_bytes()
old = raw.decode('utf-8-sig').replace('\r\n', '\n')
new = (stage / 'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
assert hashlib.sha256(old.encode()).hexdigest() == manifest['original_sha256']
assert hashlib.sha256(new.encode()).hexdigest() == manifest['candidate_sha256']
if args.apply:
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    newline = '\r\n' if b'\r\n' in raw else '\n'
    path.write_bytes(bom + new.replace('\n', newline).encode())
print(json.dumps({'applied': args.apply, 'candidate_sha256': manifest['candidate_sha256'],
                  'checked_unchanged_dependencies': len(proof['unchanged_dependencies']),
                  'whole_reverse_exact': manifest['whole_reverse_exact']}))
