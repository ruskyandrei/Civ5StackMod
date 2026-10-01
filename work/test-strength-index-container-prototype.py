"""Ignored container-only adoption fixture, frozen DLL71 and identical public guards.

No production change, DLL build, deployment or game calls. Synthetic key traces
are distributions, not captured native keys; timing excludes unit getter/math cost.
Use --production --no-benchmark after root applies the reviewed staged patch.
"""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];out=root/'work/strength-index-container-prototype';out.mkdir(exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--production',action='store_true');parser.add_argument('--no-benchmark',action='store_true');parser.add_argument('--emit-only',action='store_true');args=parser.parse_args()
spec=importlib.util.spec_from_file_location('strength_index_stager',root/'work/prepare-strength-index-container.py');stager=importlib.util.module_from_spec(spec);spec.loader.exec_module(stager)
control=stager.CONTROL;source=subprocess.check_output(['git','show',control+':'+stager.PATH],cwd=root).decode('utf-8-sig')
header=subprocess.check_output(['git','show',control+':'+stager.HEADER_PATH],cwd=root).decode('utf-8-sig')
expected=stager.transform(source)
candidate_source=(root/stager.PATH).read_text(encoding='utf-8-sig') if args.production else (stager.OUT/'CvStackingStrengthCache.cpp').read_text(encoding='utf-8')
proof=json.loads((stager.OUT/'staging-proof.json').read_text(encoding='utf-8'))
assert source== (stager.OUT/'CvStackingStrengthCache-control.cpp').read_text(encoding='utf-8')
assert candidate_source==expected,'Current candidate is not the exact reviewed representation-only transform'
assert proof['source_sha256']==hashlib.sha256(source.encode()).hexdigest() and proof['candidate_sha256']==hashlib.sha256(candidate_source.encode()).hexdigest()
assert proof['unchanged_header_sha256']==hashlib.sha256(header.encode()).hexdigest()
assert (root/stager.HEADER_PATH).read_text(encoding='utf-8-sig')==header,'Public key/API/header changed'
assert candidate_source.startswith('#include "CvGameCoreDLLPCH.h"\n#include "CvStackingStrengthCache.h"\n#include <algorithm>\n#include <vector>\n#include <cstring>\n#include "LintFree.h"\n')
assert 'int values[22];' in header
omit=('#include "CvGameCoreDLLPCH.h"','#include "CvStackingStrengthCache.h"','#include "LintFree.h"')
module='\n'.join(line for line in source.splitlines() if line not in omit)
candidate='\n'.join(line for line in candidate_source.splitlines() if line not in omit)
def function(text,name):
 a=text.index(name);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
for name in ('bool Context(','void Invalidate(','long SceneEpoch(','bool IsOwner(','LONG Read(','bool Key::operator==(','size_t operator()('):
 assert function(candidate,name)==function(module,name),'Original ownership/epoch guard drifted: '+name
prefix=r'''
#define NOMINMAX
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <algorithm>
#include <vector>
#include <map>
#include <climits>
static int allocationPhase=0;
static int failAllocationCountdown=-1;
static size_t liveBytes[3]={0},peakBytes[3]={0},allocationCalls[3]={0};
struct AllocationHeader{size_t bytes;int phase;};
void* operator new(size_t bytes){if(failAllocationCountdown==0){failAllocationCountdown=-1;throw std::bad_alloc();}if(failAllocationCountdown>0)--failAllocationCountdown;AllocationHeader*h=(AllocationHeader*)malloc(bytes+sizeof(AllocationHeader));if(!h)throw std::bad_alloc();h->bytes=bytes;h->phase=allocationPhase;liveBytes[h->phase]+=bytes;peakBytes[h->phase]=std::max(peakBytes[h->phase],liveBytes[h->phase]);++allocationCalls[h->phase];return h+1;}
void operator delete(void*p){if(p){AllocationHeader*h=((AllocationHeader*)p)-1;liveBytes[h->phase]-=h->bytes;free(h);}}
void* operator new[](size_t n){return ::operator new(n);}void operator delete[](void*p){::operator delete(p);}
'''
tests=r'''
static int checks=0,failures=0;void Expect(const char*label,bool okay){++checks;if(!okay){++failures;if(failures<8)printf("FAIL %s\n",label);}}
unsigned rng=728291;unsigned Next(){rng^=rng<<13;rng^=rng>>17;rng^=rng<<5;return rng;}
Baseline::Key MakeKey(unsigned i,bool collision=false){Baseline::Key k;for(int w=0;w<22;++w)k.values[w]=0;k.values[0]=(i%100<54)?1:(i%100<86)?3:(i%100<99)?2:0;k.values[1]=(i/4096)%8;k.values[2]=i/64;k.values[3]=i%1900;k.values[4]=(i/16)%97;k.values[5]=100;k.values[6]=(i/123)%8;k.values[7]=i%81;k.values[8]=900+i%80;k.values[9]=(i/128)%97;k.values[10]=100;k.values[11]=-1;k.values[12]=-1;k.values[14]=i%80+900;k.values[15]=i%6+920;k.values[16]=5;k.values[17]=-(int)(i%34);k.values[18]=i%4;k.values[19]=i%2;
 if(collision){size_t h=0;for(int w=0;w<21;++w)h^=(size_t)k.values[w]+0x9e3779b9+(h<<6)+(h>>2);k.values[21]=(int)(h-0x9e3779b9-(h<<6)-(h>>2));}return k;}
Index::Key Indexed(const Baseline::Key&key){Index::Key result;memcpy(result.values,key.values,sizeof(key.values));return result;}
int Value(const Baseline::Key&key){unsigned value=0;for(int w=0;w<22;++w)value=value*33+(unsigned)key.values[w];return (int)value;}
void CompareStats(){Baseline::Stats b=Baseline::GetStats();Index::Stats c=Index::GetStats();Expect("hits/misses/evictions/entry cap unchanged",b.meleeHits==c.meleeHits&&b.meleeMisses==c.meleeMisses&&b.rangedHits==c.rangedHits&&b.rangedMisses==c.rangedMisses&&b.attackHits==c.attackHits&&b.attackMisses==c.attackMisses&&b.defenseHits==c.defenseHits&&b.defenseMisses==c.defenseMisses&&b.entries==c.entries&&b.peakEntries==c.peakEntries&&b.evictions==c.evictions&&b.invalidations==c.invalidations&&b.limit==c.limit);}
DWORD WINAPI Foreign(void*){Baseline::Key key=MakeKey(4);long b,c;int value;bool okay=!Baseline::Context(b)&&!Index::Context(c)&&!Baseline::Lookup(key,0,value)&&!Index::Lookup(Indexed(key),0,value);Baseline::Store(key,0,1);Index::Store(Indexed(key),0,1);return okay?0:1;}
void Differential(){unsigned caps[]={0,1,4,16,64,513,16384,65537};for(int test=0;test<8;++test){Baseline::Scope bs(caps[test]);Index::Scope cs(caps[test]);
 for(unsigned i=0;i<18000;++i){Baseline::Key key=MakeKey(Next()%(test==7?70000:((caps[test]?caps[test]:1)*2+9)),test==4);Index::Key other=Indexed(key);long b=0,c=0;bool bc=Baseline::Context(b),cc=Index::Context(c);Expect("context availability",bc==cc);if(i%97==0){Baseline::Invalidate();Index::Invalidate();}if(i%151==0){Baseline::Scope nestedB(64);Index::Scope nestedC(64);bool nestedBase=Baseline::Context(b),nestedIndex=Index::Context(c);Expect("nested ownership including disabled outer",nestedBase==nestedIndex&&(caps[test]==0?true:!nestedBase));}
 int bv=-9,cv=-9;bool bh=Baseline::Lookup(key,b,bv),ch=Index::Lookup(other,c,cv);Expect("full equality and FIFO hit agreement",bh==ch&&(!bh||bv==cv));if(!bh){Baseline::Store(key,b,Value(key));Index::Store(other,c,Value(key));}Baseline::Store(key,b,99999);Index::Store(other,c,99999);CompareStats();}
 HANDLE h=CreateThread(NULL,0,Foreign,NULL,0,NULL);Expect("foreign worker created",h!=NULL);if(h){WaitForSingleObject(h,10000);DWORD code=1;GetExitCodeThread(h,&code);Expect("foreign thread does not query/admit",code==0);CloseHandle(h);}CompareStats();}
 long b=0,c=0;Expect("outer destruction disables contexts",!Baseline::Context(b)&&!Index::Context(c));Expect("all retained candidate payload released",Index::nodes.empty()&&Index::buckets.empty()&&Index::nodes.capacity()==0&&Index::buckets.capacity()==0);
}
void FullCapacityCases(){unsigned caps[]={1,7,513,16384,65537};
 for(int test=0;test<5;++test){Baseline::Scope bs(caps[test]);Index::Scope cs(caps[test]);unsigned limit=caps[test]>65536?65536:caps[test];long b=0,c=0;
  Baseline::Context(b);Index::Context(c);
  for(unsigned i=0;i<limit;++i){Baseline::Key key=MakeKey(i);Baseline::Store(key,b,Value(key));Index::Store(Indexed(key),c,Value(key));}
  CompareStats();Expect("full bounded node capacity",Index::nodes.size()==limit&&Index::nodes.capacity()<=limit);size_t bucketCount=1;while(bucketCount<limit*2)bucketCount<<=1;Expect("bucket allocation bound",Index::buckets.size()==bucketCount&&Index::buckets.capacity()<=bucketCount);
  // A duplicate insert must neither update its value nor promote its FIFO age.
  Baseline::Key first=MakeKey(0);Baseline::Store(first,b,999999);Index::Store(Indexed(first),c,999999);
  int bv=0,cv=0;bool bh=Baseline::Lookup(first,b,bv),ch=Index::Lookup(Indexed(first),c,cv);Expect("duplicate value and residency exact",bh&&ch&&bv==Value(first)&&cv==bv);CompareStats();
  for(unsigned i=limit;i<limit+3;++i){Baseline::Key key=MakeKey(i);Baseline::Store(key,b,Value(key));Index::Store(Indexed(key),c,Value(key));CompareStats();}
  bh=Baseline::Lookup(first,b,bv);ch=Index::Lookup(Indexed(first),c,cv);Expect("oldest evicted despite duplicate insertion",!bh&&!ch);CompareStats();
  unsigned newest=limit+2;Baseline::Key recent=MakeKey(newest);bh=Baseline::Lookup(recent,b,bv);ch=Index::Lookup(Indexed(recent),c,cv);Expect("replacement linked correctly",bh&&ch&&bv==Value(recent)&&cv==bv);CompareStats();
  Baseline::Invalidate();Index::Invalidate();Baseline::Context(b);Index::Context(c);Expect("invalidation empties ring and buckets",Index::nodes.empty()&&Index::oldest==0);CompareStats();
  for(size_t i=0;i<Index::buckets.size();++i)if(Index::buckets[i]!=-1){Expect("all invalidated bucket heads clear",false);break;}
  Expect("retained capacity remains bounded after invalidation",Index::nodes.capacity()<=limit&&Index::buckets.capacity()<=bucketCount);
 }
 Expect("all full-capacity storage released on outer destruction",Index::nodes.capacity()==0&&Index::buckets.capacity()==0);
}
void ConstructorAllocationFailure(){
 // Only the new representation allocates in construction; this is not an
 // equivalence claim about a nonexistent baseline constructor-failure path.
 allocationPhase=2;size_t before=liveBytes[2];bool caught=false;failAllocationCountdown=0;
 try{Index::Scope failed(16384);Expect("injected allocation must throw",false);}catch(const std::bad_alloc&){caught=true;}
 failAllocationCountdown=-1;Expect("bucket allocation failure rethrown",caught);Expect("failed construction releases owner/depth",Index::Read(Index::owner)==0&&Index::depth==0);Expect("failed construction releases payload",Index::nodes.capacity()==0&&Index::buckets.capacity()==0&&liveBytes[2]==before);long generation=0;Expect("failed construction leaves context disabled",!Index::Context(generation));Expect("failed construction leaves public stats unavailable",Index::GetStats().limit==0);
 {Index::Scope reopened(7);Expect("ownership can reopen after constructor failure",Index::Context(generation));Baseline::Key key=MakeKey(91);Index::Store(Indexed(key),generation,Value(key));int value=0;Expect("reopened cache stores exact key",Index::Lookup(Indexed(key),generation,value)&&value==Value(key));}
 Expect("reopened scope releases all allocation",Index::nodes.capacity()==0&&Index::buckets.capacity()==0&&liveBytes[2]==before);allocationPhase=0;
}
struct Timing{double total,setup,loop;unsigned long hits,misses,evictions;size_t memory,allocations;};
template<class Key>Key CopyKey(const Baseline::Key&key){Key result;memcpy(result.values,key.values,sizeof(key.values));return result;}
struct BaseAPI{typedef Baseline::Key Key;typedef Baseline::Scope Scope;typedef Baseline::Stats Stats;static bool Context(long&g){return Baseline::Context(g);}static bool Lookup(const Key&k,long g,int&v){return Baseline::Lookup(k,g,v);}static void Store(const Key&k,long g,int v){Baseline::Store(k,g,v);}static Stats GetStats(){return Baseline::GetStats();}};
struct IndexAPI{typedef Index::Key Key;typedef Index::Scope Scope;typedef Index::Stats Stats;static bool Context(long&g){return Index::Context(g);}static bool Lookup(const Key&k,long g,int&v){return Index::Lookup(k,g,v);}static void Store(const Key&k,long g,int v){Index::Store(k,g,v);}static Stats GetStats(){return Index::GetStats();}};
volatile unsigned checksum=0;
template<class API>Timing Measure(const std::vector<Baseline::Key>&pool,const std::vector<unsigned>&trace,int phase){LARGE_INTEGER a,b,c,d,f;QueryPerformanceFrequency(&f);peakBytes[phase]=liveBytes[phase];allocationCalls[phase]=0;allocationPhase=phase;QueryPerformanceCounter(&a);Timing t;
 {typename API::Scope scope(16384);QueryPerformanceCounter(&b);unsigned sum=0;for(size_t i=0;i<trace.size();++i){typename API::Key key=CopyKey<typename API::Key>(pool[trace[i]]);long g;API::Context(g);int v=0;if(!API::Lookup(key,g,v)){v=Value(pool[trace[i]]);API::Store(key,g,v);}sum+=(unsigned)v;}checksum=sum;QueryPerformanceCounter(&c);typename API::Stats s=API::GetStats();t.hits=s.meleeHits+s.rangedHits+s.attackHits+s.defenseHits;t.misses=s.meleeMisses+s.rangedMisses+s.attackMisses+s.defenseMisses;t.evictions=s.evictions;t.memory=peakBytes[phase];t.allocations=allocationCalls[phase];}
 QueryPerformanceCounter(&d);allocationPhase=0;t.setup=1000.0*(b.QuadPart-a.QuadPart)/f.QuadPart;t.loop=1000.0*(c.QuadPart-b.QuadPart)/f.QuadPart;t.total=1000.0*(d.QuadPart-a.QuadPart)/f.QuadPart;Expect("candidate payload released, baseline empty-node storage bounded",phase==2?liveBytes[phase]==0:liveBytes[phase]<4096);return t;}
void Bench(const char*label,unsigned size,unsigned iterations,int pattern){std::vector<Baseline::Key>pool;for(unsigned i=0;i<size;++i)pool.push_back(MakeKey(i));std::vector<unsigned>trace;trace.reserve(iterations);for(unsigned i=0;i<iterations;++i)trace.push_back(pattern==0?i%size:pattern==1?Next()%size:(Next()%100<95?Next()%12000:12000+Next()%(size-12000)));
 for(int pass=0;pass<2;++pass){Timing b,c;if(pass==0){b=Measure<BaseAPI>(pool,trace,1);c=Measure<IndexAPI>(pool,trace,2);}else{c=Measure<IndexAPI>(pool,trace,2);b=Measure<BaseAPI>(pool,trace,1);}Expect("timing traces exact counts",b.hits==c.hits&&b.misses==c.misses&&b.evictions==c.evictions);printf("BENCH %s pass%d queries%u baseline_ms%.3f index_ms%.3f speedup%.3f loop_ms%.3f->%.3f setup_ms%.3f->%.3f hits%lu misses%lu evictions%lu peak_requested_bytes%u->%u allocation_calls%u->%u\n",label,pass,iterations,b.total,c.total,b.total/c.total,b.loop,c.loop,b.setup,c.setup,b.hits,b.misses,b.evictions,(unsigned)b.memory,(unsigned)c.memory,(unsigned)b.allocations,(unsigned)c.allocations);}
}
int main(int argc,char**argv){bool noBenchmark=argc>1&&strcmp(argv[1],"--no-benchmark")==0;printf("VC9 x86 Node bytes%u; Key bytes%u. Memory counters are allocator-requested payload, excluding heap/hook overhead. Synthetic keys are not native captures.\n",(unsigned)sizeof(Index::Node),(unsigned)sizeof(Index::Key));Differential();FullCapacityCases();ConstructorAllocationFailure();if(!noBenchmark){Bench("resident_repeat512",512,2000000,0);Bench("resident_random12000",12000,4000000,1);Bench("nearby_with_cold5pct",20000,4000000,2);Bench("fifo_churn24576",24576,500000,0);}printf("container differential %d checks, %d failures checksum%u\n",checks,failures,checksum);return failures?1:0;}
'''
fixture=prefix+header.replace('#pragma once','').replace('CvStackingStrengthCache','Baseline')+module.replace('CvStackingStrengthCache','Baseline')+header.replace('#pragma once','').replace('CvStackingStrengthCache','Index')+candidate.replace('CvStackingStrengthCache','Index')+tests
(out/'test.cpp').write_text(fixture,encoding='utf-8');(out/'candidate-module.cpp').write_text(candidate,encoding='utf-8')
if args.emit_only:print('Container prototype emitted; no compile/run');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe';compile=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compile.stdout+compile.stderr,encoding='utf-8')
if compile.returncode:print(compile.stdout+compile.stderr);sys.exit(compile.returncode)
run=subprocess.run([str(exe)]+(['--no-benchmark'] if args.no_benchmark else []),cwd=out,capture_output=True,text=True,timeout=60);print(run.stdout+run.stderr,end='');(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,control=control,production_applied=args.production,benchmark_executed=not args.no_benchmark,baseline_sha256=hashlib.sha256(source.encode()).hexdigest(),actual_source_sha256=hashlib.sha256(candidate_source.encode()).hexdigest(),unchanged_header_sha256=hashlib.sha256(header.encode()).hexdigest(),fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),scope='Actual frozen DLL71 baseline and exact candidate container/context/epoch semantics. Same22word keys/hash/equality, entry cap, FIFO and all stats. Current production bound when requested; synthetic VC9 functional traces; native ROI unmeasured; no game/DLL run.'),indent=2));sys.exit(run.returncode)
