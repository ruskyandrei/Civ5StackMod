"""Test the actual production acquire read and original Interlocked fallback.

Compiles current production byte-for-byte after include extraction, an original
Interlocked-read control, and the production fallback with its guard test-forced
off or each Intel compatibility macro independently supplied around Read only.
All writes/checks/cache logic stay intact. This test never edits production.
Finite multithread tests are evidence, not a substitute for the memory-model
proof. Hot-loop timings exclude key construction and all engine/game work.
"""
from pathlib import Path
import hashlib, json, os, re, statistics, subprocess, sys

root=Path(__file__).resolve().parents[1]
core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/strength-cache-read-production';out.mkdir(exist_ok=True)
header=(core/'CvStackingStrengthCache.h').read_text().replace('#pragma once','')
raw=(core/'CvStackingStrengthCache.cpp').read_text()
module='\n'.join(line for line in raw.splitlines() if line not in ('#include "CvGameCoreDLLPCH.h"','#include "CvStackingStrengthCache.h"','#include "LintFree.h"'))
read_start=module.index('LONG Read(volatile LONG& value)')
read_open=module.index('{',read_start);read_end=read_open+1;read_depth=1
while read_depth:
 read_depth+=(module[read_end]=='{')-(module[read_end]=='}');read_end+=1
actual_read=module[read_start:read_end]
assert '_MSC_VER == 1500' in actual_read and 'defined(_M_IX86)' in actual_read
for compatibility in ('__clang__','__INTEL_COMPILER','__ICL'):
 assert '!defined('+compatibility+')' in actual_read,compatibility+' must retain conservative fallback'
assert 'return value;' in actual_read and 'return InterlockedCompareExchange(&value, 0, 0);' in actual_read
assert '__declspec(align(4)) volatile LONG owner = 0;' in module
assert '__declspec(align(4)) volatile LONG epoch = 0;' in module
old_read='LONG Read(volatile LONG& value) { return InterlockedCompareExchange(&value, 0, 0); }'
control=module[:read_start]+old_read+module[read_end:]
# Force only the actual guard off; the production fallback body stays exact.
forced_read=actual_read.replace('#if defined(_MSC_VER)', '#if !defined(FIXTURE_FORCE_READ_FALLBACK) && defined(_MSC_VER)',1)
assert forced_read!=actual_read
forced_fallback=module[:read_start]+forced_read+module[read_end:]
def compatibility_fallback(macro):
 # Define only around the unchanged Read: do not impersonate another compiler
 # while parsing CRT/Windows/STL headers or alter any other cache code.
 return module[:read_start]+'#define '+macro+' 1900\n'+actual_read+'\n#undef '+macro+'\n'+module[read_end:]
prefix=r'''
#define NOMINMAX
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <windows.h>
#include <cstdio>
#include <algorithm>
#include <climits>
'''
fixture=r'''
using namespace CvStackingStrengthCache;
static int checks=0,failures=0;
static void expect(const char*name,bool okay){++checks;if(!okay){++failures;if(failures<25)printf("FAIL %s\n",name);}}
static Key make(int id){Key key;for(size_t i=0;i<sizeof(key.values)/sizeof(key.values[0]);++i)key.values[i]=id*37+(int)i*71;key.values[0]=id%4;return key;}
// Keep one separately inspectable read symbol in the optimized assembly.
__declspec(noinline) LONG InspectRead(volatile LONG& value){return Read(value);}
struct Signal{HANDLE go,done;volatile LONG errors;Signal():go(CreateEvent(NULL,TRUE,FALSE,NULL)),done(CreateEvent(NULL,TRUE,FALSE,NULL)),errors(0){}~Signal(){CloseHandle(go);CloseHandle(done);}};
static DWORD WINAPI invalidateForeign(void*context){
 Signal*signal=(Signal*)context;WaitForSingleObject(signal->go,10000);long token=0;Scope rejected(16);int value=0;
 if(Context(token)||Lookup(make(1),token,value))InterlockedIncrement(&signal->errors);
 Store(make(1),token,-9);Invalidate();SetEvent(signal->done);return 0;
}
static DWORD WINAPI churnForeign(void*context){
 Signal*signal=(Signal*)context;WaitForSingleObject(signal->go,10000);Scope rejected(16);
 for(int i=0;i<100000;++i){long token=0;int value=0;if(Context(token)||Lookup(make(i%64),token,value)||GetStats().entries)InterlockedIncrement(&signal->errors);Store(make(i%64),token,-99);if(i%37==0)Invalidate();}
 SetEvent(signal->done);return 0;
}
struct Publication{
 __declspec(align(4)) volatile LONG sequence,ack;
 int payload,inverse;volatile LONG errors;Publication():sequence(0),ack(0),payload(0),inverse(~0),errors(0){}
};
static DWORD WINAPI publish(void*context){
 Publication*p=(Publication*)context;DWORD deadline=GetTickCount()+10000;
 for(LONG i=1;i<=20000;++i){
  while(Read(p->ack)!=i-1){if((LONG)(GetTickCount()-deadline)>=0)return 1;SwitchToThread();}
  p->payload=i;p->inverse=~i;InterlockedExchange(&p->sequence,i);
 }
 return 0;
}
int main(){
 expect("exact intended compiler and architecture",_MSC_VER==1500&&sizeof(void*)==4&&sizeof(LONG)==4);
 expect("cache owner and epoch aligned",((ULONG_PTR)&owner%4)==0&&((ULONG_PTR)&epoch%4)==0);
 printf("META msc=%d ix86=%d pointer=%u long=%u ownerAligned=%d epochAligned=%d\n",_MSC_VER,_M_IX86,(unsigned int)sizeof(void*),(unsigned int)sizeof(LONG),((ULONG_PTR)&owner%4)==0,((ULONG_PTR)&epoch%4)==0);
 long generation=0;int value=0;Key key=make(1);
 expect("inactive context remains rejected",!Context(generation));Store(key,generation,3);expect("inactive lookup rejected",!Lookup(key,generation,value));
 {Scope disabled(0);expect("zero budget remains rejected",!Context(generation));}
 {Scope scope(16);expect("owned context admitted",Context(generation));Store(key,generation,37);expect("exact stored hit",Lookup(key,generation,value)&&value==37);
  for(size_t i=0;i<sizeof(key.values)/sizeof(key.values[0]);++i){Key other=key;++other.values[i];expect("all key words retain equality",!Lookup(other,generation,value));}
  {Scope nested(16);expect("nested context rejected",!Context(generation));Store(key,generation,-99);}
  expect("outer context restored",Context(generation));expect("nested transition invalidates prior result",!Lookup(key,generation,value));Store(key,generation,41);
  long stale=generation;Invalidate();Store(key,stale,-1);expect("stale admission still canceled",Context(generation)&&!Lookup(key,generation,value));
  Store(key,generation,43);LONG previousEpoch=SceneEpoch();Signal signal;HANDLE thread=CreateThread(NULL,0,invalidateForeign,&signal,0,NULL);expect("foreign invalidator starts",thread!=NULL);SetEvent(signal.go);
  if(thread){expect("foreign invalidate done",WaitForSingleObject(signal.done,10000)==WAIT_OBJECT_0);WaitForSingleObject(thread,10000);CloseHandle(thread);}
  expect("foreign thread never accesses owned map",signal.errors==0);expect("completed foreign write observed",SceneEpoch()!=previousEpoch);expect("foreign invalidation removes stale cache",Context(generation)&&!Lookup(key,generation,value));
  for(int i=0;i<10000;++i){Key candidate=make(i);Context(generation);Store(candidate,generation,i+7);expect("FIFO exact values",Lookup(candidate,generation,value)&&value==i+7);expect("FIFO budget unchanged",GetStats().entries<=16);}
 }
 {Scope scope(16384);Signal signal;HANDLE thread=CreateThread(NULL,0,churnForeign,&signal,0,NULL);expect("foreign stressor starts",thread!=NULL);SetEvent(signal.go);
  for(int i=0;i<100000;++i){Key candidate=make(i%64);Context(generation);Store(candidate,generation,i%64+123);if(Lookup(candidate,generation,value))expect("concurrent invalidation never returns wrong result",value==i%64+123);}
  if(thread){expect("foreign stressor finishes",WaitForSingleObject(signal.done,10000)==WAIT_OBJECT_0);WaitForSingleObject(thread,10000);CloseHandle(thread);}expect("foreign stress never accesses table",signal.errors==0);
 }
 {Publication publication;expect("publication words aligned",((ULONG_PTR)&publication.sequence%4)==0&&((ULONG_PTR)&publication.ack%4)==0);HANDLE thread=CreateThread(NULL,0,publish,&publication,0,NULL);expect("publisher starts",thread!=NULL);DWORD deadline=GetTickCount()+10000;
  if(thread){for(LONG i=1;i<=20000;++i){while(Read(publication.sequence)!=i){if((LONG)(GetTickCount()-deadline)>=0){InterlockedIncrement(&publication.errors);break;}SwitchToThread();}
    if(publication.payload!=i||publication.inverse!=~i)InterlockedIncrement(&publication.errors);InterlockedExchange(&publication.ack,i);
   }expect("publisher completes",WaitForSingleObject(thread,10000)==WAIT_OBJECT_0);DWORD code=99;GetExitCodeThread(thread,&code);expect("publisher has no timeout",code==0);CloseHandle(thread);}
  expect("acquire reads observe interlocked-published payload",publication.errors==0);
 }
 {Scope scope(16384);Key keys[64];Context(generation);for(int i=0;i<64;++i){keys[i]=make(i);Store(keys[i],generation,i+123);}
  LARGE_INTEGER frequency;QueryPerformanceFrequency(&frequency);volatile unsigned long checksum=0;
  for(int sample=0;sample<5;++sample){LARGE_INTEGER begin,end;QueryPerformanceCounter(&begin);for(int i=0;i<1000000;++i){long token;int result=0;if(Context(token)&&Lookup(keys[i%64],token,result))checksum+=result;else ++failures;}QueryPerformanceCounter(&end);
   double milliseconds=1000.0*(double)(end.QuadPart-begin.QuadPart)/(double)frequency.QuadPart;printf("TIME sample=%d queries=1000000 bench_ms=%.3f checksum=%lu\n",sample,milliseconds,checksum);
  }expect("hot loop leaves exact shared limit",GetStats().limit==16384&&GetStats().entries==64);
 }
 expect("owner context released after scopes",!Context(generation));
 printf("CHECKS checks=%d failures=%d\n",checks,failures);return failures?1:0;
}
'''
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
results={}
for label,body,definitions in (('control',control,[]),('production-acquire',module,[]),('forced-fallback',forced_fallback,['/DFIXTURE_FORCE_READ_FALLBACK']),('intel-fallback',compatibility_fallback('__INTEL_COMPILER'),[]),('icl-fallback',compatibility_fallback('__ICL'),[])):
 source=prefix+header+body+fixture;cpp=out/(label+'.cpp');cpp.write_text(source,encoding='utf-8');exe=out/(label+'.exe');assembly=out/(label+'.asm')
 command=[str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MD','/Ox','/Z7','/FAs','/Fa'+str(assembly),*definitions,str(cpp),'/Fo'+str(out/(label+'.obj')),'/Fe'+str(exe)]
 compiled=subprocess.run(command,cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/(label+'-compile.log')).write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
 if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
 ran=subprocess.run([str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/(label+'-output.log')).write_text(ran.stdout+ran.stderr,encoding='utf-8');print(label+':\n'+ran.stdout+ran.stderr,end='')
 times=[float(value) for value in re.findall(r'bench_ms=([0-9.]+)',ran.stdout)]
 assembly_text=assembly.read_text();inspect=re.search(r'\?InspectRead[^\n]* PROC.*?\?InspectRead[^\n]* ENDP',assembly_text,re.S)
 assert inspect,'Separately inspectable read must survive optimization'
 read_assembly=inspect.group(0)
 is_interlocked='__imp__InterlockedCompareExchange@12' in read_assembly
 assert is_interlocked==(label!='production-acquire'),'Generated read differs from selected production/fallback semantics'
 if label=='production-acquire':assert re.search(r'mov\s+eax, DWORD PTR \[eax\]',read_assembly),'Acquire read should compile to aligned MOV'
 results[label]=dict(compile_returncode=compiled.returncode,test_returncode=ran.returncode,milliseconds=times,median_milliseconds=statistics.median(times) if times else None,assembly=str(assembly),read_assembly=read_assembly,source_sha256=hashlib.sha256(source.encode()).hexdigest(),actual_production_module=label=='production-acquire')
 if ran.returncode:sys.exit(ran.returncode)
assert (core/'CvStackingStrengthCache.cpp').read_text()==raw,'Test must never mutate production source'
summary=dict(production_source_unchanged_by_test=True,source_module_sha256=hashlib.sha256(raw.encode()).hexdigest(),variants=results,
             median_query_loop_ratio=results['production-acquire']['median_milliseconds']/results['control']['median_milliseconds'],
             limits='Actual production cache module under Win32 VC9 x86 with real Interlocked API/CreateThread/events. Production body tested unchanged after include extraction; control restores original Read; forced fallback uses actual guarded else; Intel compatibility guards independently forced around unchanged Read. Keys prebuilt; excludes game/key/leaf work; synthetic timing only. Finite thread tests do not prove every interleaving. Test changes no production compiler flags or source.')
(out/'result.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8');print(json.dumps(summary,indent=2))
