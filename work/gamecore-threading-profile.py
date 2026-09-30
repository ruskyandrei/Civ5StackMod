"""One-key, reversible GameCoreThreadingUsesJobManager 0->1 experiment.

Apply/restore refuse any running Civ V executable. Only the active key's value
changes; encoding/BOM/line endings/comments and unrelated bytes are retained.
Restore requires recorded original/applied bytes, never overwrites other edits.
No game launch, Lua, thread, priority, or engine mutation is performed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT=Path(__file__).resolve().parents[1]
ALLOWED=ROOT/"work/test-runs"
KEY="GameCoreThreadingUsesJobManager"
MANIFEST="gamecore-threading-profile.json"
BACKUP="config-original.ini"
PROPOSED="config-job-manager.ini"


def sha(data): return hashlib.sha256(data).hexdigest().upper()


def prepare(data, original="0", target="1"):
    if data.startswith(b"\xff\xfe"): prefix,codec=data[:2],"utf-16-le"
    elif data.startswith(b"\xfe\xff"): prefix,codec=data[:2],"utf-16-be"
    elif data.startswith(b"\xef\xbb\xbf"): prefix,codec=data[:3],"latin-1"
    else: prefix,codec=b"","latin-1"
    text=data[len(prefix):].decode(codec)
    section=None;offset=0;matches=[]
    for line in text.splitlines(keepends=True):
        content=line.rstrip("\r\n")
        header=re.fullmatch(r"[ \t]*\[([^\]\r\n]+)\][ \t]*(?:[;#].*)?",content)
        if header: section=header[1].strip().casefold()
        if re.match(r"[ \t]*"+KEY+r"[ \t]*=",content,re.I):
            parsed=re.fullmatch(r"[ \t]*"+KEY+r"[ \t]*=[ \t]*(?P<value>[01])[ \t]*(?:[;#].*)?",content,re.I)
            if parsed is None: raise ValueError("Active job-manager key has an unsupported value/tail")
            matches.append((section,offset+parsed.start("value"),parsed["value"]))
        offset+=len(line)
    if len(matches)!=1: raise ValueError("Exactly one active job-manager key is required; commented keys do not count")
    section,index,value=matches[0]
    if section!="config": raise ValueError("Job-manager key must be in [CONFIG]")
    if value!=original: raise ValueError(f"Expected job-manager value {original}, found {value}")
    changed=prefix+(text[:index]+target+text[index+1:]).encode(codec)
    differences=[i for i,(a,b) in enumerate(zip(data,changed)) if a!=b]
    if len(changed)!=len(data) or len(differences)!=1:
        raise ValueError("Expected exactly one changed value byte")
    return changed,dict(key=KEY,section="CONFIG",originalValue=original,targetValue=target,
        byteOffset=differences[0],originalSHA256=sha(data),targetSHA256=sha(changed),
        encoding="UTF16-LE" if codec=="utf-16-le" else "UTF16-BE" if codec=="utf-16-be" else "ASCII-compatible bytes",
        bomBytes=len(prefix),changedByteCount=1)


def running_civ_processes():
    # Constant read-only script: no interpolated paths, shell commands or tokens.
    source="""$ErrorActionPreference='Stop';$civProfileProcesses=@(Get-Process | Where-Object {$_.ProcessName -match '^CivilizationV(?:_DX11|_Tablet)?$'} | Select-Object Id,ProcessName);ConvertTo-Json -InputObject $civProfileProcesses -Compress"""
    result=subprocess.run(["powershell.exe","-NoProfile","-Command",source],capture_output=True,text=True,timeout=20)
    if result.returncode: raise RuntimeError("Civ process inventory failed; configuration mutation refused")
    data=json.loads(result.stdout.strip())
    if not isinstance(data,list): raise RuntimeError("Invalid Civ process inventory")
    return data


def require_game_closed():
    processes=running_civ_processes()
    if processes: raise RuntimeError("Civ V must be closed before configuration mutation: "+json.dumps(processes))


def checked_paths(config,run):
    config=config.resolve(strict=True);run=run.resolve()
    if config.name.casefold()!="config.ini" or not config.is_file(): raise ValueError("Explicit config.ini file required")
    if not run.is_relative_to(ALLOWED.resolve()) or run==ALLOWED.resolve(): raise ValueError("Run must be below project work/test-runs")
    return config,run


def exclusive_bytes(path,data):
    with path.open("xb") as stream: stream.write(data);stream.flush();os.fsync(stream.fileno())


def json_atomic(path,value):
    temporary=path.with_name(path.name+"."+uuid.uuid4().hex+".tmp")
    try:
        exclusive_bytes(temporary,(json.dumps(value,indent=2)+"\n").encode("utf-8"))
        os.replace(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()


def replace_config(path,data):
    temporary=path.with_name(path.name+".job-profile-"+uuid.uuid4().hex+".tmp")
    try:
        exclusive_bytes(temporary,data)
        os.replace(temporary,path)
    finally:
        if temporary.exists(): temporary.unlink()
    if path.read_bytes()!=data: raise RuntimeError("Configuration readback differs from intended bytes")


def apply(config,run,expected_sha,guard=require_game_closed):
    guard();config,run=checked_paths(config,run)
    if (run/MANIFEST).exists() or (run/BACKUP).exists() or (run/PROPOSED).exists():
        raise ValueError("Profile evidence already exists; do not repeat apply; inspect/restore it")
    original=config.read_bytes()
    if sha(original)!=expected_sha.upper(): raise ValueError("Current config SHA does not match expected pre-apply source")
    proposed,proof=prepare(original)
    run.mkdir(parents=True,exist_ok=True)
    exclusive_bytes(run/BACKUP,original);exclusive_bytes(run/PROPOSED,proposed)
    record=dict(schema=1,status="prepared",config=str(config),backup=BACKUP,proposed=PROPOSED,**proof)
    json_atomic(run/MANIFEST,record)
    guard() # A process started during preparation must prevent the mutation.
    if config.read_bytes()!=original: raise ValueError("Configuration changed after preparation; apply refused")
    replace_config(config,proposed)
    record.update(status="applied",readbackSHA256=sha(config.read_bytes()),readbackValue="1")
    json_atomic(run/MANIFEST,record)
    return record


def read_profile(config,run):
    config,run=checked_paths(config,run)
    record=json.loads((run/MANIFEST).read_text(encoding="utf-8-sig"))
    if record.get("schema")!=1 or Path(record.get("config","")).resolve()!=config:
        raise ValueError("Profile manifest does not identify the explicit config")
    if record.get("backup")!=BACKUP or record.get("proposed")!=PROPOSED:
        raise ValueError("Profile backup filenames changed")
    original=(run/BACKUP).read_bytes();proposed=(run/PROPOSED).read_bytes()
    if sha(original)!=record.get("originalSHA256") or sha(proposed)!=record.get("targetSHA256"):
        raise ValueError("Immutable configuration backup/proposal SHA mismatch")
    reconstructed,proof=prepare(original)
    if reconstructed!=proposed or any(record.get(key)!=value for key,value in proof.items()):
        raise ValueError("Profile proposal is not the exact one-key edit")
    return config,run,record,original,proposed


def restore(config,run,guard=require_game_closed):
    guard();config,run,record,original,proposed=read_profile(config,run)
    current=config.read_bytes()
    if current not in (original,proposed): raise ValueError("Unrelated config bytes changed; strict restore will not overwrite them")
    changed=current==proposed
    if changed:
        guard()
        if config.read_bytes()!=proposed: raise ValueError("Configuration changed before restore; restore refused")
        replace_config(config,original)
    record.update(status="restored",restoreChanged=changed,restoredSHA256=sha(config.read_bytes()),readbackValue="0")
    json_atomic(run/MANIFEST,record)
    return record


def status(config,run):
    config,run,record,original,proposed=read_profile(config,run)
    current=config.read_bytes()
    return dict(manifest=record,currentSHA256=sha(current),currentMatches="original" if current==original else "applied" if current==proposed else "unrelated_change",
        processInventory=running_civ_processes(),mutationPerformed=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode",choices=("plan","apply","restore","status"),required=True)
    parser.add_argument("--config",type=Path,required=True);parser.add_argument("--run-dir",type=Path)
    parser.add_argument("--expected-sha256")
    args=parser.parse_args()
    if args.mode!="plan" and args.run_dir is None: parser.error("--run-dir required")
    if args.mode=="apply" and (args.expected_sha256 is None or re.fullmatch(r"[0-9a-fA-F]{64}",args.expected_sha256) is None):
        parser.error("Apply requires --expected-sha256 from the read-only plan")
    try:
        if args.mode=="plan":
            data=args.config.resolve(strict=True).read_bytes();proposed,proof=prepare(data)
            result=dict(ok=True,mode="plan",config=str(args.config.resolve()),mutationPerformed=False,processInventory=running_civ_processes(),**proof)
        elif args.mode=="apply": result=apply(args.config,args.run_dir,args.expected_sha256)
        elif args.mode=="restore": result=restore(args.config,args.run_dir)
        else: result=status(args.config,args.run_dir)
    except (ValueError,RuntimeError,OSError,json.JSONDecodeError,UnicodeError,subprocess.SubprocessError) as exc:
        print(json.dumps(dict(ok=False,mode=args.mode,error=str(exc),automaticMutationRetry=False)));return 2
    print(json.dumps(result,indent=2));return 0


if __name__=="__main__":sys.exit(main())
