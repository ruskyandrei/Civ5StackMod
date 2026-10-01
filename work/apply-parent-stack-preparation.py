"""Apply only the fully checked DLL91 parent-preparation candidate."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json

spec = importlib.util.spec_from_file_location('parent_preparation_stage', Path(__file__).with_name('prepare-parent-stack-preparation.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
ROOT, OUT, stage = module.ROOT, module.OUT, module.stage

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply', action='store_true')
args = parser.parse_args()
oldcpp, oldhpp, cpp, hpp = stage()
proof = json.loads((ROOT / 'work/parent-stack-preparation-regression/result.json').read_text())
assert proof['compile_returncode'] == proof['test_returncode'] == 0
assert proof['candidate_sha256'] == hashlib.sha256(cpp.encode()).hexdigest()
assert 'checks=295462 failures=0' in proof['output']
fixture = (ROOT / 'work/parent-stack-preparation-regression/test.cpp').read_text()
assert hashlib.sha256(fixture.encode()).hexdigest() == proof['fixture_sha256']
for name, expected in proof['unchanged_dependency_hashes'].items():
    live = (ROOT / 'CvGameCoreDLL_Expansion2' / name).read_text(encoding='utf-8-sig')
    assert hashlib.sha256(live.encode()).hexdigest() == expected, name
changes = []
for name, old, new in [('CvTacticalAI.cpp', oldcpp, cpp), ('CvTacticalAI.h', oldhpp, hpp)]:
    path = ROOT / 'CvGameCoreDLL_Expansion2' / name
    raw = path.read_bytes()
    assert raw.decode('utf-8-sig').replace('\r\n', '\n') == old, name
    bom = b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b''
    newline = '\r\n' if b'\r\n' in raw else '\n'
    changes.append((path, bom + new.replace('\n', newline).encode('utf-8')))
if args.apply:
    for path, data in changes:
        path.write_bytes(data)
print(json.dumps({'applied': args.apply, 'files': [str(path) for path, _ in changes],
                  'candidate_sha256': proof['candidate_sha256'],
                  'checked_unchanged_dependencies': len(proof['unchanged_dependency_hashes'])}))
