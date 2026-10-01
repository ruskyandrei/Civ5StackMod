"""Guarded source-only application of the frozen allocation-free slot-key candidate."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];P=argparse.ArgumentParser(description=__doc__);P.add_argument('--apply',action='store_true');args=P.parse_args()
subprocess.run([sys.executable,str(ROOT/'work/stage-resident-slot-key.py')],check=True,capture_output=True)
stage=ROOT/'work/resident-slot-key-staged';test=ROOT/'work/resident-slot-key-regression';m=json.loads((stage/'manifest.json').read_text());p=json.loads((test/'result.json').read_text())
assert p['compile_returncode']==p['test_returncode']==0
assert re.search(r'RESIDENT SLOT-KEY ACTUAL97: \d+ checks, 0 failures;',p['output'])
assert p['candidate_sha256']==m['candidate_sha256'] and m['whole_reverse_exact'] and m['wrapper_projection_miss_body_unchanged']
assert hashlib.sha256((test/'test.cpp').read_text(encoding='utf-8').encode()).hexdigest()==p['fixture_sha256']
for n,h in p['unchanged_dependencies'].items():assert hashlib.sha256((ROOT/'CvGameCoreDLL_Expansion2'/n).read_text(encoding='utf-8-sig').encode()).hexdigest()==h,n
path=ROOT/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp';raw=path.read_bytes();old=raw.decode('utf-8-sig').replace('\r\n','\n');new=(stage/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
assert hashlib.sha256(old.encode()).hexdigest()==m['original_sha256']
assert hashlib.sha256(new.encode()).hexdigest()==m['candidate_sha256']
if args.apply:
 bom=b'\xef\xbb\xbf' if raw.startswith(b'\xef\xbb\xbf') else b'';newline='\r\n' if b'\r\n' in raw else '\n';path.write_bytes(bom+new.replace('\n',newline).encode())
print(json.dumps(dict(applied=args.apply,candidate_sha256=m['candidate_sha256'],checked_dependencies=len(p['unchanged_dependencies']),compiled_fixture_sha256=p['fixture_sha256'],whole_reverse_exact=True)))
