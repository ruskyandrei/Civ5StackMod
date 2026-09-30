"""Offline fixture configs only; no live config, game or process mutation."""
from pathlib import Path
import importlib.util
import json
import tempfile

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("threading_profile",ROOT/"work/gamecore-threading-profile.py")
profile=importlib.util.module_from_spec(spec);spec.loader.exec_module(profile)
OUT=Path(tempfile.mkdtemp(prefix="job-manager-profile-fixture-",dir=ROOT/"work/test-runs"))
checks=0
def expect(value,label):
    global checks
    checks+=1
    assert value,label
def denied(action,label):
    try: action()
    except (ValueError,RuntimeError):expect(True,label)
    else:expect(False,label)
base="; GameCoreThreadingUsesJobManager = 1\r\n[CONFIG]\r\nEnableGameCoreThreading = 1\r\n\tGameCoreThreadingUsesJobManager  =  0 ; preserve me\r\nOther = 77\r\n"
for codec,bom in (("latin-1",b""),("utf-8",b""),("utf-8",b"\xef\xbb\xbf"),("utf-16-le",b"\xff\xfe"),("utf-16-be",b"\xfe\xff")):
    original=bom+base.replace("preserve me","preserve \u00e9").encode(codec)
    changed,proof=profile.prepare(original)
    expect(sum(a!=b for a,b in zip(original,changed))==1 and len(original)==len(changed),"exact changed byte for encoding/BOM")
    restored,_=profile.prepare(changed,"1","0")
    expect(restored==original and proof["originalSHA256"]==profile.sha(original),"byte-exact reverse including comments/CRLF")
last=b"[ config ]\nGAMECORETHREADINGUSEsJOBMANAGER\t=\t0 # inline"
edited,_=profile.prepare(last);expect(edited.endswith(b"1 # inline"),"case/tabs/no terminal newline retained")
for bad in (b"[CONFIG]\n; GameCoreThreadingUsesJobManager=0\n",b"[OTHER]\nGameCoreThreadingUsesJobManager=0\n",
            b"[CONFIG]\nGameCoreThreadingUsesJobManager=0\nGameCoreThreadingUsesJobManager=0\n",
            b"[CONFIG]\nGameCoreThreadingUsesJobManager=2\n",b"[CONFIG]\nGameCoreThreadingUsesJobManager=10\n",
            b"[CONFIG]\nGameCoreThreadingUsesJobManager=1\n",b"[CONFIG]\nGameCoreThreadingUsesJobManager=0 unexpected\n"):
    denied(lambda:profile.prepare(bad),"ambiguous/comment-only/wrong section/value refused")
def case(name):
    folder=OUT/name;folder.mkdir();config=folder/"config.ini";config.write_bytes(base.encode("ascii"));return config,folder/"run"
calls=[]
def closed():calls.append("checked")
config,run=case("normal");original=config.read_bytes()
record=profile.apply(config,run,profile.sha(original),closed)
expect(record["status"]=="applied" and len(calls)==2,"process closure checked before backup and before mutation")
expect((run/profile.BACKUP).read_bytes()==original and config.read_bytes()==(run/profile.PROPOSED).read_bytes(),"immutable byte backup/proposal/readback")
denied(lambda:profile.apply(config,run,profile.sha(config.read_bytes()),closed),"repeat apply refused")
restored=profile.restore(config,run,closed)
expect(restored["restoreChanged"] and config.read_bytes()==original,"strict restore restores exact original bytes")
expect(profile.restore(config,run,closed)["restoreChanged"] is False,"already-original restore is idempotent")
config,run=case("running")
def running():raise RuntimeError("simulated existing Civ process")
denied(lambda:profile.apply(config,run,profile.sha(config.read_bytes()),running),"existing Civ refusal")
expect(not run.exists() and config.read_bytes()==original,"existing process refusal produces no artifacts or mutation")
config,run=case("wrong-sha")
denied(lambda:profile.apply(config,run,"0"*64,closed),"unexpected current source hash refused")
expect(not run.exists() and config.read_bytes()==original,"wrong source remains untouched")
config,run=case("started-between")
n=0
def race():
    global n
    n+=1
    if n==2:raise RuntimeError("simulated game launch after preparation")
denied(lambda:profile.apply(config,run,profile.sha(original),race),"late process appearance blocks apply")
expect(config.read_bytes()==original and json.loads((run/profile.MANIFEST).read_text())["status"]=="prepared","prepared record allows safe audit/recovery without target mutation")
expect(profile.restore(config,run,closed)["restoreChanged"] is False,"prepared original recovery works")
config,run=case("late-change")
n=0
def edit_during_guard():
    global n
    n+=1
    if n==2:config.write_bytes(original+b"; external edit\r\n")
denied(lambda:profile.apply(config,run,profile.sha(original),edit_during_guard),"source changed during preparation refused")
expect(config.read_bytes().endswith(b"; external edit\r\n"),"external bytes never overwritten")
config,run=case("restore-unrelated");profile.apply(config,run,profile.sha(original),closed)
external=config.read_bytes()+b"; unrelated change\r\n";config.write_bytes(external)
denied(lambda:profile.restore(config,run,closed),"restore unrelated bytes refused")
expect(config.read_bytes()==external,"strict restore preserves unrelated changes")
config,run=case("tampered-backup");profile.apply(config,run,profile.sha(original),closed)
(run/profile.BACKUP).write_bytes(original+b"; tampered")
denied(lambda:profile.restore(config,run,closed),"backup hash tampering refused")
config,run=case("interrupted-applied")
real_json=profile.json_atomic;writes=0
def fail_second(path,value):
    global writes
    writes+=1
    if writes==2:raise RuntimeError("simulated interruption after target replacement")
    return real_json(path,value)
profile.json_atomic=fail_second
try:denied(lambda:profile.apply(config,run,profile.sha(original),closed),"post-replacement interruption retained")
finally:profile.json_atomic=real_json
expect(json.loads((run/profile.MANIFEST).read_text())["status"]=="prepared" and config.read_bytes()!=(original),"prepared evidence plus target hash records unknown-outcome recovery")
expect(profile.restore(config,run,closed)["restoredSHA256"]==profile.sha(original),"interrupted applied config restores from verified byte backup")
print(json.dumps(dict(ok=True,checks=checks,offline=True,gameCalls=0,liveConfigMutations=0,fixtures=str(OUT))))
