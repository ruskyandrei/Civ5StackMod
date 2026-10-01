"""Adopt the explicitly frozen AI candidate after checking source-bound proofs."""
from pathlib import Path
import argparse, hashlib, json, subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--apply',action='store_true');p.add_argument('--verify-applied',action='store_true');a=p.parse_args()
assert not (a.apply and a.verify_applied)
stage=ROOT/'work/ai-followup-composed'
proof=json.loads((stage/'finished-proof.json').read_text())
hashes=proof['candidate_hashes'];targets={}
for name,expected in hashes.items():
    source=stage/name;text=source.read_text(encoding='utf-8-sig')
    assert hashlib.sha256(text.encode()).hexdigest()==expected,name
    assert not any(text.startswith(x) or '\n'+x in text for x in ('<<<<<<<','>>>>>>>','|||||||')),name
    targets[Path('CvGameCoreDLL_Expansion2')/name]=source
xml=Path('(1) Community Patch/Database Changes/StackingConfig.xml')
assert hashlib.sha256((stage/'StackingConfig.xml').read_text(encoding='utf-8-sig').encode()).hexdigest()==proof['xml_sha256']
targets[xml]=stage/'StackingConfig.xml'
for test in ('healing','production','wave'):
    result=json.loads((ROOT/('work/integration-'+test+'-regression/result.json')).read_text())
    assert result.get('compile_returncode',result.get('returncode'))==result.get('test_returncode',result.get('returncode'))==0,test
    bound=result.get('candidate_hashes',result.get('source_sha256',result.get('source_hashes')))
    # Tests bind finished-proof as well as the exact bodies executed in fixtures.
    if bound is None:
        bound=result.get('composition',{}).get('candidate_hashes')
    assert bound==hashes,(test,'stale/missing whole-candidate binding')
for rel,source in targets.items():
    original=subprocess.check_output(['git','show',proof['control']+':'+rel.as_posix()],cwd=ROOT)
    live=(ROOT/rel).read_bytes()
    if a.verify_applied:
        assert live.decode('utf-8-sig').replace('\r\n','\n')==source.read_text(encoding='utf-8-sig'),('Applied source changed',str(rel))
        continue
    assert live.decode('utf-8-sig').replace('\r\n','\n')==original.decode('utf-8-sig').replace('\r\n','\n'),('Live source changed',str(rel))
    if a.apply:
        text=source.read_text(encoding='utf-8-sig')
        eol='\r\n' if b'\r\n' in live else '\n'
        (ROOT/rel).write_bytes((b'\xef\xbb\xbf' if live.startswith(b'\xef\xbb\xbf') else b'')+text.replace('\n',eol).encode())
print(json.dumps({'validated':len(targets),'applied':a.apply,'verified_applied':a.verify_applied,'control':proof['control']}))
