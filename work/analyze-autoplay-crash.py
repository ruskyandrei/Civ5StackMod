"""Offline reader for the preserved Turn245 dump and exact VC9 DLL/PDB. No live attach."""
from pathlib import Path
import struct,json,hashlib,bisect,subprocess,uuid
root=Path(__file__).resolve().parents[1];out=root/'work/test-runs/auto-test-1-20260927-065332/crash';out.mkdir(parents=True,exist_ok=True)
dump=Path("E:/SteamLibrary/steamapps/common/Sid Meier's Civilization V/crashlogs/CvMiniDump_20260927_085548_5.4.6-4-g5efb033_Release.dmp");folder=root/'work/msvc-output/Release/20260927-030606';pdb=folder/'CvGameCore_Expansion2.pdb';dll=folder/'CvGameCore_Expansion2.dll'
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
frame=u32(regs['ebp']);newvec=u32(frame-0x14);whereoff=u32(frame-0x18);vector=u32(frame-0x1c);count=u32(frame+0xc)
vec=None
try:vec=list(struct.unpack('<4I',read(vector,16)))
except ValueError:pass
returns=[0x85c41e5d,0x85c434b7,0x85c45f25,0x85c47160,0x85c479b8,0x85c260e4]
# Confirm each recovered return is actually in the captured active stack, not guessed from source.
stack=read(regs['esp'],0x400);trace=[]
for a in returns:
 packed=struct.pack('<I',a);assert packed in stack;v=sym(a-0x85540000);v['live_address']=hex(a);v['stack_address']=hex(regs['esp']+stack.index(packed));trace.append(v)
assert newvec==0 and whereoff*112+newvec==regs['esi']==params[1] and count==1
# PE imports identify the fallback used by the linked operator-new wrapper.
pe=dll.read_bytes();po=struct.unpack_from('<I',pe,0x3c)[0];ns,opsize=struct.unpack_from('<H',pe,po+6)[0],struct.unpack_from('<H',pe,po+20)[0];oo=po+24;sec=[]
for i in range(ns):
 q=oo+opsize+i*40;name=pe[q:q+8].split(b'\0')[0].decode();vsz,va,rsz,raw=struct.unpack_from('<4I',pe,q+8);sec.append((va,max(vsz,rsz),raw))
def peoff(va):
 for s,n,r in sec:
  if s<=va<s+n:return r+va-s
 raise ValueError(va)
def zstr(off):return pe[off:pe.index(b'\0',off)].decode(errors='replace')
imp=struct.unpack_from('<I',pe,oo+104)[0];io=peoff(imp);imports={}
while True:
 oft,stamp,chain,name,iat=struct.unpack_from('<5I',pe,io)
 if not any((oft,stamp,chain,name,iat)):break
 lib=zstr(peoff(name));t=peoff(oft or iat);i=0
 while True:
  v=struct.unpack_from('<I',pe,t+4*i)[0]
  if not v:break
  imports[hex(0x10000000+iat+4*i)]=lib+'!'+(('#'+str(v&65535)) if v&0x80000000 else zstr(peoff(v)+2));i+=1
 io+=20
res={'dump':str(dump),'dump_sha256':hashlib.sha256(b).hexdigest().upper(),'dll_sha256':hashlib.sha256(pe).hexdigest().upper(),'pdb_sha256':hashlib.sha256(pdb.read_bytes()).hexdigest().upper(),'pdb_guid':str(uuid.UUID(bytes_le=ss[1][12:28])).upper(),'pdb_age':struct.unpack_from('<I',ss[1],8)[0],'exception':{'tid':tid,'code':hex(code),'address':hex(address),'operation':params[0],'access_address':hex(params[1])},'registers':{k:hex(v) for k,v in regs.items()},'fault_symbol':sym(address-0x85540000),'recovered_returns':trace,'insert_frame':{'ebp':hex(frame),'saved_newvec':hex(newvec),'where_offset_elements':whereoff,'element_size':112,'insert_count':count,'vector_address':hex(vector),'captured_vector_words':[hex(x) for x in vec] if vec else None,'expected_fault_address':hex(newvec+whereoff*112)},'allocator_symbol':sym(0xf620),'fallback_import_0x10aa944c':imports.get('0x10aa944c'),'caveat':'Optimized manual return recovery, not complete native unwind. Null saved allocator result confirmed by disassembly; total-memory growth cause not identified.'}
(out/'offline-allocation-analysis.json').write_text(json.dumps(res,indent=2)+'\n',encoding='utf-8')
parts=[]
for a,z in [(0x106ff400,0x106ff447),(0x10705e30,0x10705f35),(0x1010a650,0x1010a6a0),(0x1000f620,0x1000f651),(0x106e60bc,0x106e60f0)]:
 p=subprocess.run([str(root/'work/toolchain/llvm/bin/llvm-objdump.exe'),'-d','--start-address='+hex(a),'--stop-address='+hex(z),str(dll)],capture_output=True,text=True);assert p.returncode==0;parts.append(p.stdout)
(out/'allocation-disassembly.txt').write_text('\n'.join(parts),encoding='utf-8');print(json.dumps(res,indent=2))
