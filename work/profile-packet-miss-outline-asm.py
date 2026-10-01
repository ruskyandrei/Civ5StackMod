"""Offline exact-function COFF frame/GS evidence; no compilation/attachment."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/packet-miss-outline-staged';LLVM=ROOT/'work/toolchain/llvm/bin/llvm-objdump.exe'
objects=[('native94',ROOT/'work/msvc-build/Release/20261001-114416/obj/CvTacticalAI.obj'),('fixture',ROOT/'work/packet-miss-outline-regression/test.obj')]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native-object',type=Path)
parser.add_argument('--label',default='native')
parser.add_argument('--output-dir',type=Path)
args=parser.parse_args()
if args.native_object:objects=[(args.label,args.native_object)]
if args.output_dir:OUT=args.output_dir
OUT.mkdir(parents=True,exist_ok=True)
report=[]
for label,obj in objects:
    symbols=subprocess.check_output([str(LLVM),'--syms',str(obj)],text=True)
    names=[]
    for line in symbols.splitlines():
        name=line.rsplit(' ',1)[-1]
        if name.startswith('?GetCachedStackDanger@') or name.startswith('?ResolveStackDangerForecastMiss@'):
            names.append(name)
    for index,name in enumerate(names):
        asm=subprocess.check_output([str(LLVM),'--disassemble','--reloc','--disassemble-symbols='+name,str(obj)],text=True)
        file=OUT/(label+'-'+str(index)+'.asm');file.write_text(asm,encoding='utf-8')
        frame=re.search(r'subl\s+\$0x([0-9a-fA-F]+), %esp',asm)
        source=asm.splitlines();instructions=[line for line in source if re.match(r'\s*[0-9a-f]+:',line)]
        report.append(dict(object=label,object_path=str(obj),object_sha256=hashlib.sha256(obj.read_bytes()).hexdigest(),symbol=name,local_frame_bytes=int(frame.group(1),16) if frame else None,gs_cookie_setup='___security_cookie' in asm,gs_cookie_check='@__security_check_cookie@4' in asm,eh_handler='__ehhandler' in asm,first_instructions=instructions[:20],asm=str(file),interpretation='Static optimized COFF evidence only; fixture engine/diagnostic services differ from full DLL; no native speed claim.'))
(OUT/'assembly-proof.json').write_text(json.dumps(report,indent=2)+'\n')
for row in report:print(row['object'],row['symbol'].split('@@')[0],'frame',row['local_frame_bytes'],'GS',row['gs_cookie_setup'],'EH',row['eh_handler'])
