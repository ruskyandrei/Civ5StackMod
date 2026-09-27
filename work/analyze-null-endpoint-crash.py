"""Offline reader for the fixed-build null endpoint crash. Writes only work evidence; no live attach."""
from pathlib import Path
import struct,json,hashlib,bisect,subprocess,uuid
root=Path(__file__).resolve().parents[1];out=root/'work/test-runs/turn240-fixed-20260927/crash';out.mkdir(parents=True,exist_ok=True)
dump=Path("E:/SteamLibrary/steamapps/common/Sid Meier's Civilization V/crashlogs/CvMiniDump_20260927_103644_5.4.6-7-g13252af_Release.dmp");folder=root/'work/msvc-output/Release/20260927-102519';pdb=folder/'CvGameCore_Expansion2.pdb';dll=folder/'CvGameCore_Expansion2.dll'
b=pdb.read_bytes();B,_,_,nd,_,bm=struct.unpack_from('<6I',b,32);blocks=struct.unpack_from('<%dI'%((nd+B-1)//B),b,bm*B);d=b''.join(b[x*B:(x+1)*B] for x in blocks)[:nd];n=struct.unpack_from('<I',d)[0];sz=struct.unpack_from('<%dI'%n,d,4);off=4+4*n;ss=[]
for s in sz:
 n=0 if s==0xffffffff else (s+B-1)//B;bl=struct.unpack_from('<%dI'%n,d,off);off+=4*n;ss.append(b''.join(b[x*B:(x+1)*B] for x in bl)[:s])
sdata=ss[struct.unpack_from('<H',ss[3],20)[0]];o=0;syms=[]
while o+4<=len(sdata):
 l,t=struct.unpack_from('<HH',sdata,o)
 if not l:break
 if t==0x110e:
  _,a,s=struct.unpack_from('<IIH',sdata,o+4);name=sdata[o+14:o+l+2].split(b'\0')[0].decode(errors='replace');syms.append((s,a,name))
 o+=l+2
syms.sort()
def sym(rva):
 a=rva-0x1000;i=bisect.bisect(syms,(1,a,'\uffff'))-1;return {'rva':hex(rva),'symbol':syms[i][2],'offset':hex(a-syms[i][1])}
b=dump.read_bytes();n,dr=struct.unpack_from('<II',b,8);dirs={}
for i in range(n):
 t,s,r=struct.unpack_from('<III',b,dr+12*i);dirs[t]=(s,r)
r=dirs[5][1];ranges=[struct.unpack_from('<QII',b,r+4+16*i) for i in range(struct.unpack_from('<I',b,r)[0])]
def read(a,n):
 for va,s,off in ranges:
  va=va&0xffffffff
  if va<=a and a+n<=va+s:return b[off+a-va:off+a-va+n]
 raise ValueError('Address not captured: '+hex(a))
def u32(a):return struct.unpack('<I',read(a,4))[0]
r=dirs[6][1];tid=struct.unpack_from('<I',b,r)[0];code=struct.unpack_from('<I',b,r+8)[0];address=struct.unpack_from('<Q',b,r+24)[0]&0xffffffff;params=struct.unpack_from('<15Q',b,r+40);cs,cr=struct.unpack_from('<II',b,r+160);regoffs={'edi':156,'esi':160,'ebx':164,'edx':168,'ecx':172,'eax':176,'ebp':180,'eip':184,'esp':196};regs={k:struct.unpack_from('<I',b,cr+v)[0] for k,v in regoffs.items()}

# Match the embedded dump module signature to the actual artifact PDB.
r=dirs[4][1]
for i in range(struct.unpack_from('<I',b,r)[0]):
 q=r+4+i*108;base,size=struct.unpack_from('<QI',b,q);nr=struct.unpack_from('<I',b,q+20)[0];name=b[nr+4:nr+4+struct.unpack_from('<I',b,nr)[0]].decode('utf-16le')
 if 'CvGameCore_Expansion2' in name:
  cvs,cvr=struct.unpack_from('<II',b,q+76);cv=b[cvr:cvr+cvs];base&=0xffffffff;break
else:raise ValueError('Gamecore module missing from dump')
pdbGuid=str(uuid.UUID(bytes_le=ss[1][12:28])).upper();dumpGuid=str(uuid.UUID(bytes_le=cv[4:20])).upper();assert pdbGuid==dumpGuid
assert struct.unpack_from('<I',cv,20)[0]==struct.unpack_from('<I',ss[1],8)[0]==1
assert address-base==0x64a660 and params[:2]==(0,4) and regs['ecx']==0
pe=dll.read_bytes();dllHash=hashlib.sha256(pe).hexdigest().upper();assert dllHash=='C6FC9A64C422C231D03E40A8F438B8DF3C3E4B2C5F653C11E7D5423454752125'
assert pe[0x649a60:0x649a63]==b'\x8b\x41\x04' # mov eax,[ecx+4]
expected=[0x88ff5b18,0x88ff847b,0x88ff9205,0x88f41742,0x88c68f27];stack=read(regs['esp'],0x400);trace=[]
for a in expected:
 raw=struct.pack('<I',a);assert raw in stack;v=sym(a-base);v.update(live_address=hex(a),stack_address=hex(regs['esp']+stack.index(raw)));trace.append(v)
res={'dump':str(dump),'dump_sha256':hashlib.sha256(b).hexdigest().upper(),'dll':str(dll),'dll_sha256':dllHash,'pdb_sha256':hashlib.sha256(pdb.read_bytes()).hexdigest().upper(),'pdb_guid':pdbGuid,'dump_module_guid':dumpGuid,'age':1,'module_base':hex(base),'exception':{'thread':tid,'code':hex(code),'address':hex(address),'operation':'read','access_address':hex(params[1])},'registers':{k:hex(v) for k,v in regs.items()},'fault':sym(address-base),'recovered_returns':trace,'callee_mapping':[sym(x) for x in [0x791940,0x7a3220,0x7c8880]],'operand':'mov eax,[ecx+4]; ECX=0; read address4','source':'CvTacticalAI.cpp3466 in13252af: SIEGE_APPROACH argument pUnit->GetPathEndFirstTurnPlot()->GetPlotIndex()','memory_markers_KiB':{'committed':2704560,'reserved':490584,'free':999032,'largest_free':910592},'limits':'Unit/path heap not captured; cannot distinguish empty approximate path, no turn0 node or invalidated cache. Immediate fault/caller/operand verified; deeper returns are manual optimized-stack recovery.'}
(out/'offline-null-endpoint-analysis.json').write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8')
parts=[]
for a,z in [(0x1064a650,0x1064a670),(0x106f5a54,0x106f5b70)]:
 result=subprocess.run([str(root/'work/toolchain/llvm/bin/llvm-objdump.exe'),'-d','--start-address='+hex(a),'--stop-address='+hex(z),str(dll)],capture_output=True,text=True);assert result.returncode==0;parts.append(result.stdout)
(out/'null-endpoint-disassembly.txt').write_text('\n'.join(parts),encoding='utf-8')
print(json.dumps({'fault':res['fault'],'dump_sha256':res['dump_sha256'],'pdb_guid':pdbGuid,'output':str(out)},indent=2))
