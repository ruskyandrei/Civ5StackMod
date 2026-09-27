"""Prepare short FireTuner commands for a reviewed, in-memory Lua observer."""
from pathlib import Path
import argparse
import hashlib
import json
import zlib

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--run', type=Path, required=True)
args = p.parse_args()
run = args.run.resolve()
run.relative_to((ROOT / 'work/test-runs').resolve())
source_path = ROOT / 'work/StackingAutoplayObserver.lua'
source = source_path.read_text(encoding='utf-8-sig')
assert source.isascii(), 'Console payload deliberately uses ASCII Lua'
commands = []
for i, offset in enumerate(range(0, len(source), 740), 1):
    part = source[offset:offset + 740]
    prefix = 'assert(StackAutoplaySource==nil);StackAutoplaySource="";' if i == 1 else ''
    command = (prefix + 'StackAutoplaySource=StackAutoplaySource..' + json.dumps(part)
               + ';print("STACKAUTOLOAD|' + str(i) + '|"..#StackAutoplaySource)')
    assert len(command) < 1000
    commands.append(command)
checksum = zlib.adler32(source.encode('ascii'))
commands.append('assert(#StackAutoplaySource==' + str(len(source)) + ');'
                'local a,b=1,0;for i=1,#StackAutoplaySource do '
                'a=(a+string.byte(StackAutoplaySource,i))%65521;b=(b+a)%65521 end;'
                'assert(b*65536+a==' + str(checksum) + ',"Observer checksum mismatch");'
                'local f,e=loadstring(StackAutoplaySource,"StackingAutoplayObserver");'
                'assert(f,e);f();StackAutoplaySource=nil;print("STACKAUTOLOAD|READY")')
assert all(len(c) < 1000 for c in commands)
out = run / 'injection'
out.mkdir(exist_ok=False)
for i, command in enumerate(commands, 1):
    (out / f'{i:02}.lua').write_text(command, encoding='ascii')
(run / 'StackingAutoplayObserver.runtime.lua').write_text(source, encoding='ascii')
manifest = {'source_sha256': hashlib.sha256(source.encode()).hexdigest().upper(),
            'source_bytes': len(source), 'adler32': checksum, 'commands': len(commands),
            'max_command_bytes': max(map(len, commands)),
            'scope': 'Prepared console text only; definitions-only loader. Start is a separate action.'}
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(json.dumps(manifest))
