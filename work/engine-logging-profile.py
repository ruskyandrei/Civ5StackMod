"""Reversible, game-off engine logging experiment; native Summary is independent.

Usage (after Civilization V and desktop FireTuner are closed):
  python work/engine-logging-profile.py inspect
  python work/engine-logging-profile.py apply-native-only --run-dir <fresh-directory>
  python work/engine-logging-profile.py restore --run-dir <same-directory>

Only AILog/AIPerfLog/BuilderAILog become 0. LoggingEnabled and MessageLog retain
exact original values and all unrelated config bytes remain unchanged. A local
Python/Lua bridge service may stay available when Civilization itself is closed.
"""
from pathlib import Path
import argparse,csv,datetime,hashlib,io,json,os,re,subprocess,tempfile

DEFAULT_CONFIG=Path(r"C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\config.ini")
FLAGS=('LoggingEnabled','MessageLog','AILog','AIPerfLog','BuilderAILog')
LEGACY=('AILog','AIPerfLog','BuilderAILog')
BACKUP_NAME='config-before.ini'
METADATA_NAME='engine-logging-profile.json'
CANONICAL={key.lower():key for key in FLAGS}
KEY_LINE=re.compile(r'^[ \t]*(LoggingEnabled|MessageLog|AILog|AIPerfLog|BuilderAILog)[ \t]*=(.*)$',re.I)
VALUE=re.compile(r'([ \t]*)([01])([ \t]*(?:[;#].*)?)$')
BLOCKED=re.compile(r'^(?:civilization(?:v|5)(?:_[^.]+)?|firetuner(?:2)?)\.exe$',re.I)

class ProfileError(RuntimeError):pass

def sha256(data):return hashlib.sha256(data).hexdigest()
def decode_config(data):
    for bom,encoding in ((b'\xef\xbb\xbf','utf-8'),(b'\xff\xfe','utf-16-le'),(b'\xfe\xff','utf-16-be')):
        if data.startswith(bom):
            try:text=data[len(bom):].decode(encoding)
            except UnicodeError as e:raise ProfileError('Config encoding is invalid') from e
            if bom+text.encode(encoding)!=data:raise ProfileError('Config encoding roundtrip is not exact')
            return text,encoding,bom
    if b'\x00' in data:raise ProfileError('Config has unsupported NUL-containing encoding without BOM')
    # Reversible byte mapping; no interpretation/printing of unrelated settings.
    return data.decode('latin1'),'latin1',b''

def parse_flags(data):
    text,encoding,bom=decode_config(data);values={};spans={};offset=0
    for line in text.splitlines(keepends=True):
        content=line.rstrip('\r\n');match=KEY_LINE.fullmatch(content)
        if match:
            name=CANONICAL[match.group(1).lower()]
            if name in values:raise ProfileError('Duplicate config key: '+name)
            value=VALUE.fullmatch(match.group(2))
            if not value:raise ProfileError('Config key must have exactly one boolean value: '+name)
            values[name]=int(value.group(2));start=offset+match.start(2)+value.start(2)
            spans[name]=(start,start+1)
        offset+=len(line)
    missing=[name for name in FLAGS if name not in values]
    if missing:raise ProfileError('Missing config keys: '+', '.join(missing))
    return values,(text,encoding,bom,spans)

def native_only_bytes(data):
    before,state=parse_flags(data);text,encoding,bom,spans=state
    for name in sorted(LEGACY,key=lambda key:spans[key][0],reverse=True):
        a,b=spans[name];text=text[:a]+'0'+text[b:]
    changed=bom+text.encode(encoding);after,_=parse_flags(changed)
    expected=dict(before);expected.update({name:0 for name in LEGACY})
    if after!=expected:raise ProfileError('Readback flags disagree with narrow logging profile')
    # Replacing the three value spans is the only allowed byte transformation.
    return changed,before,after

def running_process_names():
    if os.name!='nt':raise ProfileError('Real config changes require the Windows game-off guard')
    result=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,check=True)
    return [row[0] for row in csv.reader(io.StringIO(result.stdout)) if row]

def require_game_off(process_names=None):
    names=running_process_names() if process_names is None else process_names
    blocked=sorted({str(name) for name in names if BLOCKED.fullmatch(str(name))})
    if blocked:raise ProfileError('Close Civilization V and desktop FireTuner first: '+', '.join(blocked))

def atomic_write(path,data,expected_hash=None):
    path=Path(path);temporary=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.'+path.name+'.engine-log-',suffix='.tmp',dir=path.parent,delete=False) as stream:
            temporary=Path(stream.name);stream.write(data);stream.flush();os.fsync(stream.fileno())
        if expected_hash is not None and sha256(path.read_bytes())!=expected_hash:
            raise ProfileError('Config changed concurrently; refusing to overwrite it')
        os.replace(temporary,path);temporary=None
        if path.read_bytes()!=data:raise ProfileError('Written file bytes did not match readback')
    finally:
        if temporary is not None:temporary.unlink(missing_ok=True)

def write_metadata(directory,metadata):
    atomic_write(Path(directory)/METADATA_NAME,(json.dumps(metadata,indent=2,sort_keys=True)+'\n').encode('utf-8'))

def inspect(config=DEFAULT_CONFIG,guard=require_game_off):
    guard();config=Path(config).resolve();data=config.read_bytes();flags,_=parse_flags(data)
    return dict(config=str(config),sha256=sha256(data),bytes=len(data),flags=flags)

def apply_native_only(config,run_dir,guard=require_game_off):
    guard();config=Path(config).resolve();run_dir=Path(run_dir).resolve()
    before_data=config.read_bytes();after_data,before_flags,after_flags=native_only_bytes(before_data)
    if before_data==after_data:raise ProfileError('Config is already native-only; no contrasting baseline to record')
    # This helper owns only a supplied fresh experiment directory.
    if run_dir.exists():
        if not run_dir.is_dir() or any(run_dir.iterdir()):raise ProfileError('Run directory must be fresh and empty')
    else:run_dir.mkdir(parents=True,exist_ok=False)
    backup=run_dir/BACKUP_NAME
    with backup.open('xb') as stream:stream.write(before_data);stream.flush();os.fsync(stream.fileno())
    if backup.read_bytes()!=before_data:raise ProfileError('Backup bytes did not match source config')
    metadata=dict(schema=1,profile='native-only',status='prepared',created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
      config=str(config),backup_file=BACKUP_NAME,
      baseline=dict(sha256=sha256(before_data),bytes=len(before_data),flags=before_flags),
      applied=dict(sha256=sha256(after_data),bytes=len(after_data),flags=after_flags),
      changed_keys=[name for name in LEGACY if before_flags[name]!=after_flags[name]])
    write_metadata(run_dir,metadata)
    guard();atomic_write(config,after_data,metadata['baseline']['sha256'])
    actual=inspect(config,guard)
    if actual['sha256']!=metadata['applied']['sha256'] or actual['flags']!=after_flags:raise ProfileError('Native-only profile readback failed')
    metadata['status']='applied';write_metadata(run_dir,metadata)
    return metadata

def restore(config,run_dir,guard=require_game_off):
    guard();config=Path(config).resolve();run_dir=Path(run_dir).resolve()
    metadata=json.loads((run_dir/METADATA_NAME).read_text(encoding='utf-8'))
    if metadata.get('schema')!=1 or metadata.get('profile')!='native-only' or metadata.get('backup_file')!=BACKUP_NAME:
        raise ProfileError('Unsupported logging experiment metadata')
    if metadata.get('config')!=str(config):raise ProfileError('Metadata config path differs from explicit requested target')
    backup=(run_dir/BACKUP_NAME).read_bytes();flags,_=parse_flags(backup)
    if sha256(backup)!=metadata['baseline']['sha256'] or len(backup)!=metadata['baseline']['bytes'] or flags!=metadata['baseline']['flags']:
        raise ProfileError('Backup integrity does not match recorded baseline')
    current=config.read_bytes();current_hash=sha256(current)
    if metadata.get('status')=='restored':
        if current_hash!=metadata['baseline']['sha256']:raise ProfileError('Config changed after restore; refusing to overwrite it')
        return metadata
    if metadata.get('status') not in ('prepared','applied'):raise ProfileError('Unsupported logging experiment status')
    if current_hash!=metadata['applied']['sha256']:
        raise ProfileError('Config changed since apply; refusing to overwrite concurrent user changes')
    current_flags,_=parse_flags(current)
    if current_flags!=metadata['applied']['flags']:raise ProfileError('Current flags do not match recorded native-only profile')
    guard();atomic_write(config,backup,metadata['applied']['sha256'])
    actual=inspect(config,guard)
    if actual['sha256']!=metadata['baseline']['sha256'] or actual['flags']!=flags:raise ProfileError('Baseline restore readback failed')
    metadata['status']='restored';metadata['restored_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();write_metadata(run_dir,metadata)
    return metadata

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('inspect','apply-native-only','restore'));parser.add_argument('--config',type=Path,default=DEFAULT_CONFIG);parser.add_argument('--run-dir',type=Path)
    args=parser.parse_args()
    try:
        if args.mode=='inspect':result=inspect(args.config)
        else:
            if args.run_dir is None:raise ProfileError('--run-dir is required for apply or restore')
            result=apply_native_only(args.config,args.run_dir) if args.mode=='apply-native-only' else restore(args.config,args.run_dir)
        print(json.dumps(result,indent=2,sort_keys=True))
    except (ProfileError,OSError,ValueError,subprocess.SubprocessError) as error:
        parser.exit(1,'Logging profile refused: '+str(error)+'\n')
if __name__=='__main__':main()
