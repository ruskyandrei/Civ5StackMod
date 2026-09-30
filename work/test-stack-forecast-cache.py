"""Compile/run actual FIFO forecast storage and key builders with VC9 stubs."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1]
out=root/'work/stack-cache-regression';out.mkdir(exist_ok=True)
source=root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp';raw=source.read_bytes();text=raw.decode('utf-8-sig').replace('\r\n','\n')
actual=text[text.index('struct StackForecastKey\n'):text.index('static int GetCachedStackDanger(')]
reference=subprocess.check_output(['git','show','6ec8aae26:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
reference=reference[reference.index('static void AppendStackCandidates('):reference.index('static int GetCachedStackDanger(')].replace('AppendStackCandidates','OriginalCandidates').replace('AppendStackDamage','OriginalDamage')

prefix=r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <algorithm>
#include <cstdio>
#include <vector>
#include <deque>
#include <unordered_map>
#include <map>
#include <cstddef>
#include <cstdlib>
#include <new>
static size_t allocationCalls=0;
template<class T> struct CountingAllocator:std::allocator<T>{
 typedef typename std::allocator<T>::pointer pointer;typedef typename std::allocator<T>::size_type size_type;
 template<class U>struct rebind{typedef CountingAllocator<U> other;};
 CountingAllocator(){} template<class U>CountingAllocator(const CountingAllocator<U>&){}
 pointer allocate(size_type n,const void*hint=0){++allocationCalls;return std::allocator<T>::allocate(n,hint);}
};
template<class T,class U>bool operator==(const CountingAllocator<T>&,const CountingAllocator<U>&){return true;}
template<class T,class U>bool operator!=(const CountingAllocator<T>&,const CountingAllocator<U>&){return false;}
using namespace std;
struct CvUnit { int id; CvUnit(int v=0):id(v){} int GetID()const{return id;} };
struct SUnitIDValueContainer {
 typedef pair<int,int> value_type;typedef vector<value_type>::const_iterator const_iterator;
 vector<value_type> entries;
 const_iterator begin()const{return entries.begin();}const_iterator end()const{return entries.end();}
 int GetValue(int id)const{for(size_t i=0;i<entries.size();++i)if(entries[i].first==id)return entries[i].second;return 0;}
};
struct Storage { int getSizeLimit()const{return 6000;} }gTactPosStorage;
const int TACTSIM_MAX_UNITS=13;
'''
suffix=r'''
static int checks=0,failures=0;
static void expect(const char*name,bool ok){++checks;if(!ok){++failures;if(failures<30)printf("FAIL %s\n",name);}}
static StackForecastKey key(int a,int b=0){StackForecastKey k;k.state.push_back(a);k.state.push_back(b);return k;}
static StackForecastKey wideKey(int a,int n){StackForecastKey k;k.state.assign(n,a);return k;}
static int value(const StackForecastKey&k){unsigned int v=2166136261u;for(size_t i=0;i<k.state.size();++i)v=(v*16777619u)^(unsigned int)k.state[i];return (int)(v&0x7fffffffu);}
static int danger(const StackForecastKey&k,int&calls){if(gStackForecastsActive){StackDangerForecasts::const_iterator it=gStackDangerForecasts.find(k);if(it!=gStackDangerForecasts.end())return it->second;}++calls;int result=value(k);StoreStackDangerForecast(k,result);return result;}
static void invariant(const char*name){
 size_t bytes=0;bool ok=gStackDangerOrder.size()==gStackDangerForecasts.size()&&gStackDefenderOrder.size()==gStackDefenderForecasts.size();
 for(StackDangerForecasts::const_iterator i=gStackDangerForecasts.begin();i!=gStackDangerForecasts.end();++i)bytes+=i->first.state.capacity()*sizeof(int);
 for(StackDefenderForecasts::const_iterator i=gStackDefenderForecasts.begin();i!=gStackDefenderForecasts.end();++i)bytes+=i->first.state.capacity()*sizeof(int);
 ok=ok&&bytes==gStackKeyPayloadBytes&&bytes<=gStackKeyPayloadLimit&&gStackDangerForecasts.size()+gStackDefenderForecasts.size()<=gStackEntryLimit;
 for(size_t i=0;i<gStackDangerOrder.size();++i){StackDangerForecasts::const_iterator it=gStackDangerForecasts.find(*gStackDangerOrder[i]);ok=ok&&it!=gStackDangerForecasts.end()&& &it->first==gStackDangerOrder[i];}
 for(size_t i=0;i<gStackDefenderOrder.size();++i){StackDefenderForecasts::const_iterator it=gStackDefenderForecasts.find(*gStackDefenderOrder[i]);ok=ok&&it!=gStackDefenderForecasts.end()&& &it->first==gStackDefenderOrder[i];}
 expect(name,ok);
}
int main(){
 expect("native32bit",sizeof(void*)==4&&sizeof(size_t)==4);
 {StackForecastScope s;expect("default shared entry budget",gStackEntryLimit==6000);expect("default payload budget",gStackKeyPayloadLimit==624000);}
 {StackForecastScope s;gStackEntryLimit=3;gStackKeyPayloadLimit=128;int calls=0;
  expect("exact first miss",danger(key(1),calls)==value(key(1)));expect("exact hit",danger(key(1),calls)==value(key(1))&&calls==1);
  danger(key(2),calls);danger(key(3),calls);danger(key(1),calls);danger(key(4),calls);
  expect("FIFO oldest rather than last touched",gStackDangerForecasts.find(key(1))==gStackDangerForecasts.end()&&gStackDangerForecasts.find(key(2))!=gStackDangerForecasts.end());
  expect("one eviction",gStackDangerEvictions==1&&gStackInsertBypasses==0);invariant("FIFO accounting");
  StoreStackDangerForecast(key(4),value(key(4)));invariant("duplicate admission never duplicates queue");
 }
 {StackForecastScope s;gStackEntryLimit=16;gStackKeyPayloadLimit=64;
  StoreStackDangerForecast(wideKey(1,8),1);StoreStackDangerForecast(wideKey(2,8),2);StoreStackDangerForecast(wideKey(3,16),3);
  expect("payload evicts multiple entries",gStackDangerForecasts.size()==1&&gStackDangerEvictions==2&&gStackKeyPayloadBytes==64);
  expect("true peak separate from retained",gStackPeakEntries==2&&gStackDangerForecasts.size()==1&&gStackPeakKeyBytes==64);
  size_t entries=gStackDangerForecasts.size();unsigned long evictions=gStackDangerEvictions;
  StoreStackDangerForecast(wideKey(4,17),4);expect("oversize rejected before eviction",gStackDangerForecasts.size()==entries&&gStackDangerEvictions==evictions&&gStackInsertBypasses==1);invariant("payload accounting");
 }
 {StackForecastScope s;gStackEntryLimit=5;gStackKeyPayloadLimit=512;CvUnit u(77);StoreStackDefenderForecast(key(100),&u);
  for(int i=0;i<9;++i)StoreStackDangerForecast(key(i),i);
  expect("small selector pool retained",gStackDefenderForecasts.find(key(100))!=gStackDefenderForecasts.end());
  expect("larger danger pool refreshed",gStackDangerEvictions==5&&gStackDefenderEvictions==0);invariant("mixed pools");
 }
 {StackForecastScope s;gStackEntryLimit=6;gStackKeyPayloadLimit=512;CvUnit u(11);
  for(int i=0;i<6;++i)StoreStackDefenderForecast(key(100+i),&u);
  for(int i=0;i<6;++i)StoreStackDangerForecast(key(i),i);
  expect("selector pool cannot starve danger",gStackDangerForecasts.size()>=3&&gStackDefenderEvictions>=3);invariant("pool fairness");
  StoreStackDefenderForecast(key(200),NULL);expect("null defender is a cached result",gStackDefenderForecasts.find(key(200))!=gStackDefenderForecasts.end()&&gStackDefenderForecasts.find(key(200))->second==NULL);
 }
 {StackForecastScope s;gStackEntryLimit=4;gStackKeyPayloadLimit=512;StoreStackDangerForecast(key(1),99);size_t count=gStackDangerForecasts.size();
  {StackForecastScope inner;expect("nested memoization disabled",!gStackForecastsActive);StoreStackDangerForecast(key(2),2);expect("nested leaves outer table",gStackDangerForecasts.size()==count);
   {StackForecastScope third;StoreStackDefenderForecast(key(3),NULL);expect("third depth still bypassed",!gStackForecastsActive&&gStackDefenderForecasts.empty());}
   expect("nested exit not prematurely active",!gStackForecastsActive);
  }
  expect("outer memoization restored",gStackForecastsActive&&gStackDangerForecasts.find(key(1))->second==99&&gStackNestedBypasses==2);invariant("nested accounting");
 }
 expect("outer scope clears maps and queues",!gStackForecastsActive&&gStackForecastDepth==0&&gStackDangerForecasts.empty()&&gStackDefenderForecasts.empty()&&gStackDangerOrder.empty()&&gStackDefenderOrder.empty()&&gStackKeyPayloadBytes==0);
 {StackForecastScope s;gStackEntryLimit=2000;gStackKeyPayloadLimit=100000;
  for(int i=0;i<1000;++i){StackForecastKey k;size_t h=(size_t)i+0x9e3779b9;k.state.push_back(i);k.state.push_back((int)(h-0x9e3779b9-(h<<6)-(h>>2)));expect("forced hash collision",StackForecastKeyHash()(k)==0);StoreStackDangerForecast(k,i);}
  for(int i=0;i<1000;++i){StackForecastKey k;size_t h=(size_t)i+0x9e3779b9;k.state.push_back(i);k.state.push_back((int)(h-0x9e3779b9-(h<<6)-(h>>2)));expect("collision exact equality",gStackDangerForecasts.find(k)->second==i);}
  invariant("rehash keeps queued node references");gStackEntryLimit=7;StoreStackDangerForecast(key(-1),1);invariant("evict after many rehashes");expect("reduced test budget evicts safely",gStackDangerForecasts.size()==7);
 }
 {StackForecastScope s;int calls=0;
  for(int i=0;i<12050;++i){StackForecastKey k=key(i,i*7);expect("2x real capacity exact values",danger(k,calls)==value(k));if(i%997==0)invariant("real budget stress");}
  expect("real cap retained",gStackDangerForecasts.size()==6000&&gStackDangerEvictions==6050);invariant("real final accounting");
 }
 {StackForecastScope s;gStackEntryLimit=8;gStackKeyPayloadLimit=1024;int fifoCalls=0,oldCalls=0;map<vector<int>,int> old;
  for(int i=0;i<16000;++i){StackForecastKey k=key(i/2000,i%4);int expected=value(k);map<vector<int>,int>::iterator it=old.find(k.state);int prior;
   if(it!=old.end())prior=it->second;else{++oldCalls;prior=expected;if(old.size()<8)old[k.state]=expected;}
   expect("rolling trace decisions equal uncached",danger(k,fifoCalls)==expected&&prior==expected);
  }
  expect("late repeated states admitted",fifoCalls==32&&oldCalls==12008);printf("rolling-state control: FIFO %d computes, old stop-admission %d computes; this is not a game benchmark\n",fifoCalls,oldCalls);invariant("rolling trace budgets");
 }
 {CvUnit a(1),b(2);vector<const CvUnit*> left,right;left.push_back(&a);left.push_back(&b);right.push_back(&b);right.push_back(&a);SUnitIDValueContainer d;d.entries.push_back(make_pair(1,9));d.entries.push_back(make_pair(2,10));
  StackForecastKey x,y;AppendStackCandidates(x,left,d,true);AppendStackCandidates(y,right,d,true);expect("canonical unit candidates equivalent",x==y);
  x.state.clear();y.state.clear();AppendStackCandidates(x,left,d,false);AppendStackCandidates(y,right,d,false);expect("city/legacy order retained",!(x==y));
  SUnitIDValueContainer changed=d;changed.entries[0].second=10;x.state.clear();y.state.clear();AppendStackCandidates(x,left,d,true);AppendStackCandidates(y,left,changed,true);expect("exact1HP difference retained",!(x==y));
  SUnitIDValueContainer perm=d;reverse(perm.entries.begin(),perm.entries.end());x.state.clear();y.state.clear();AppendStackDamage(x,d);AppendStackDamage(y,perm);expect("damage state canonical",x==y);
 }

 {StackForecastScope s;
  {StackForecastQuery outer(gStackDangerScratch,gStackDangerScratchBusy);outer.key.state.push_back(991);
   {StackForecastQuery callback(gStackDangerScratch,gStackDangerScratchBusy);callback.key.state.push_back(123);expect("nested query buffer fallback",callback.scratch==NULL&&outer.key.state[0]==991);}
   {StackForecastScope callbackScope;StackForecastQuery callback(gStackDangerScratch,gStackDangerScratchBusy);expect("nested scope private query",callback.scratch==NULL);}
   expect("outer query still owned",gStackDangerScratchBusy&&outer.key.state[0]==991);
  }
  expect("query buffer returned",!gStackDangerScratchBusy&&gStackDangerScratch.state.size()==1);
  {StackForecastPairQuery outer;outer.entries.push_back(make_pair(7,9));{StackForecastPairQuery inner;inner.entries.push_back(make_pair(3,2));expect("nested sorting buffer fallback",!inner.borrowed&&outer.entries[0].first==7);}expect("sorting buffer still owned",gStackSortScratchBusy);}
  expect("sorting buffer returned",!gStackSortScratchBusy);
 }
 expect("query scratch storage released",gStackDangerScratch.state.capacity()==0&&gStackDefenderScratch.state.capacity()==0&&gStackSortScratch.capacity()==0);
 {StackForecastScope s;CvUnit a(4),b(9),c(2);vector<const CvUnit*> candidates;candidates.push_back(&a);candidates.push_back(NULL);candidates.push_back(&b);candidates.push_back(&c);
  SUnitIDValueContainer wounds;for(int i=0;i<18;++i)wounds.entries.push_back(make_pair(i,(i*17)%100));size_t optimized=0,original=0;
  for(int i=0;i<20000;++i){wounds.entries[0].second=i%100;if(i%7==0)reverse(wounds.entries.begin(),wounds.entries.end());if(i%3==0)reverse(candidates.begin(),candidates.end());bool canonical=i%2==0;
   size_t before=allocationCalls;StackForecastQuery query(gStackDangerScratch,gStackDangerScratchBusy);query.key.state.push_back(i%23);AppendStackCandidates(query.key,candidates,wounds,canonical);AppendStackDamage(query.key,wounds);optimized+=allocationCalls-before;
   before=allocationCalls;StackForecastKey old;old.state.push_back(i%23);OriginalCandidates(old,candidates,wounds,canonical);OriginalDamage(old,wounds);original+=allocationCalls-before;
   expect("reused key equals original through ordering/wounds",query.key==old);
  }
  expect("scratch allocation stays bounded after warmup",optimized<100);expect("reference really allocates per query",original>100000);
  printf("actual key-build allocation control: reused %u allocations, original %u across20000queries; not a game-speed benchmark\n",(unsigned int)optimized,(unsigned int)original);
 }
 printf("stack cache source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
cpp=out/'stack-cache-source-test.cpp'
fixture=prefix+actual+reference+suffix
# Delegate unchanged std::vector allocation to std::allocator, counting calls;
# this adapter instruments key/sort buffers in the fixture, not the game DLL.
fixture=fixture.replace('vector<int>','vector<int, CountingAllocator<int> >').replace('vector<pair<int,int> >','vector<pair<int,int>, CountingAllocator<pair<int,int> > >').replace('vector<pair<int, int> >','vector<pair<int, int>, CountingAllocator<pair<int, int> > >')
cpp.write_text(fixture,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'stack-cache-source-test.exe'
compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'stack-cache-source-test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=30);print(run.stdout+run.stderr,end='')
result=dict(source_file_sha256=hashlib.sha256(raw).hexdigest().upper(),extracted_cache_sha256=hashlib.sha256(actual.encode()).hexdigest().upper(),compile_returncode=compiled.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr,scope='actual cache storage/admission/FIFO/key builders extracted with engine stubs; native32bit VC9; no DLL build or game run')
(out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');sys.exit(run.returncode)
