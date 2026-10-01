"""Actual DLL86 old storage versus work-only indexed owned storage. No core edits."""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, subprocess, sys

ROOT=Path(__file__).resolve().parents[1]
BASELINE='ef274591d0f4f32e193959524faf953cf964bd86'
SOURCE='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
OUT=ROOT/'work/indexed-forecast-store-staged'
TEMPLATES=ROOT/'work/indexed-forecast-store-template'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--emit-only',action='store_true')
parser.add_argument('--no-benchmark',action='store_true')
parser.add_argument('--stage-production',action='store_true',help='Compile exact whole-source staged representation/callers')
parser.add_argument('--production',action='store_true',help='Require exact whole current production source and compile its representation/callers')
args=parser.parse_args()
source=subprocess.check_output(['git','show',BASELINE+':'+SOURCE],cwd=ROOT).decode('utf-8-sig')
start=source.index('struct StackForecastKey\n')
prefix_end=source.index('static StackForecastKey gStackDangerScratch',start)
prefix=source[start:prefix_end]
methods_start=source.index('static size_t StackDangerForecastPayloadBytes(',prefix_end)
methods_end=source.index('static void AppendStackCandidates(',methods_start)
methods=source[methods_start:methods_end]
# Test-only deterministic failure at the exact original FIFO push boundary.
instrumented=methods.replace('gStackDangerOrder.push_back(', 'BeforeQueuePush();gStackDangerOrder.push_back(').replace('gStackDefenderOrder.push_back(', 'BeforeQueuePush();gStackDefenderOrder.push_back(')
assert instrumented.replace('BeforeQueuePush();','')==methods
types=prefix[:prefix.index('typedef std::tr1::unordered_map<StackForecastKey')]
globals_start=prefix.index('typedef std::map<std::pair<int, int>, unsigned char> StackThreatFlags;')
globals_end=prefix.index('static void ClearStackForecastEntries()')
globals_and_owner=prefix[globals_start:globals_end]
legacy_tables=prefix[len(types):globals_start]
context=prefix[prefix.index('static void InvalidateStackForecastScene()'):]
scope_start=source.index('struct StackForecastScope\n')
scope_end=source.index('// Retained capacities, including packet outputs',scope_start)
actual_scope=source[scope_start:scope_end]
release_old='''   std::deque<const StackForecastKey*>().swap(gStackDangerOrder);
   std::deque<const StackForecastKey*>().swap(gStackDefenderOrder);
   StackDangerForecasts().swap(gStackDangerForecasts);
   StackDefenderForecasts().swap(gStackDefenderForecasts);
'''
assert actual_scope.count(release_old)==1
new_scope=actual_scope.replace(release_old,'   gIndexed.Release();gUseIndexed=false;\n'+release_old)
constructor_end='  gStackKeyPayloadLimit = gStackEntryLimit * TACTSIM_MAX_UNITS * 2 * sizeof(int);\n }'
assert new_scope.count(constructor_end)==1
new_scope=new_scope.replace(constructor_end,'''  gStackKeyPayloadLimit = gStackEntryLimit * TACTSIM_MAX_UNITS * 2 * sizeof(int);
  gUseIndexed=false;
  try { if(gStackForecastsActive){gIndexed.Init(gStackEntryLimit);gUseIndexed=true;} }
  catch (const std::bad_alloc&)
  {
   // Pick the original representation before any query or admission.
   // Partial arrays are already rolled back by Init; no in-search fallback.
   gIndexed.Release();gUseIndexed=false;
  }
  catch (...)
  {
   // Constructor failure will not invoke this object's destructor.
   gIndexed.Release();gStackKeyPayloadBytes=0;gStackEntryLimit=gStackKeyPayloadLimit=0;
   gStackForecastDepth=0;gStackForecastsActive=false;owned=false;
   InterlockedExchange(&gStackForecastOwnerThread,0);throw;
  }
 }''')
extras='''static unsigned long gStackPacketHits=0,gStackPacketBuilds=0,gStackPacketBypasses=0;
static StackForecastKey gStackDangerScratch,gStackDefenderScratch;
static vector<pair<int,int> > gStackSortScratch,gStackImmutableEnemyDamageScratch;
struct FixtureScratch{void release(){}};
static FixtureScratch gStackVirtualScratch,gStackDestinationScratch,gStackPacketScratch;
'''
indexed=(TEMPLATES/'IndexedStore.h').read_text(encoding='utf-8')
indexed_methods=(TEMPLATES/'IndexedMethods.h').read_text(encoding='utf-8')
legacy_methods=instrumented
legacy_names=('StackDangerForecastPayloadBytes','EvictOldestStackForecast','CanStoreStackForecast','EstimatedStackForecastBytes','UpdateStackForecastPeaks','StoreStackDangerForecast','StoreStackDangerPacketForecast','StoreStackDefenderForecast')
for name in legacy_names:legacy_methods=legacy_methods.replace(name,'Legacy'+name)
stager_spec=importlib.util.spec_from_file_location('indexed_store_stager',ROOT/'work/prepare-indexed-forecast-store.py')
stager=importlib.util.module_from_spec(stager_spec);stager_spec.loader.exec_module(stager)
lookup_helpers=stager.LOOKUPS
binding=None
if args.stage_production or args.production:
    expected_source=stager.transform(source)
    actual_source=(ROOT/SOURCE).read_text(encoding='utf-8-sig') if args.production else (OUT/'CvTacticalAI.cpp').read_text(encoding='utf-8')
    assert actual_source==expected_source,'Whole source differs from exact reviewed storage/caller/diagnostic transform'
    c=actual_source.index('class IndexedStore\n');d=actual_source.index('static void InvalidateStackForecastScene()',c)
    indexed=actual_source[c:d]
    c=actual_source.index('struct StackForecastScope\n');d=actual_source.index('// Retained capacities, including packet outputs',c)
    new_scope=actual_source[c:d]
    c=actual_source.index('static size_t LegacyStackDangerForecastPayloadBytes(');d=actual_source.index('// Admission/control flow preserves the original storage helpers.',c)
    legacy_methods=actual_source[c:d]
    for name in legacy_names:legacy_methods=legacy_methods.replace('Legacy'+name,name)
    assert legacy_methods.strip()==methods.strip()
    for name in legacy_names:legacy_methods=legacy_methods.replace(name,'Legacy'+name)
    legacy_methods=legacy_methods.replace('gStackDangerOrder.push_back(','BeforeQueuePush();gStackDangerOrder.push_back(').replace('gStackDefenderOrder.push_back(','BeforeQueuePush();gStackDefenderOrder.push_back(')
    c=d;d=actual_source.index('// Backend queries copy results before any caller validation',c)
    indexed_methods=actual_source[c:d].replace('gIndexed.QueuePush(handle);','BeforeQueuePush();gIndexed.QueuePush(handle);')
    c=d;d=actual_source.index('static void AppendStackCandidates(',c)
    lookup_helpers=actual_source[c:d]
    assert lookup_helpers.strip()==stager.LOOKUPS.strip()
    binding=dict(mode='current_production' if args.production else 'whole_staged_source',actualSourceSHA256=hashlib.sha256(actual_source.encode()).hexdigest(),fullSourceExactlyExpected=True)

fixture_prefix=r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <climits>
#include <new>
#include <vector>
#include <deque>
#include <map>
#include <unordered_map>
using namespace std;
static int allocationPhase=0,failAllocation=-1;
static size_t liveBytes[3]={0},peakBytes[3]={0},allocationCalls[3]={0},allocatedBytes[3]={0};
static bool captureAllocationSizes=false;
static size_t capturedSizes[3][16]={{0}};static unsigned capturedCounts[3]={0};
struct AllocationHeader{size_t bytes;int phase;};
void* operator new(size_t bytes){if(failAllocation==0){failAllocation=-1;throw std::bad_alloc();}if(failAllocation>0)--failAllocation;AllocationHeader* p=(AllocationHeader*)malloc(bytes+sizeof(AllocationHeader));if(!p)throw std::bad_alloc();p->bytes=bytes;p->phase=allocationPhase;liveBytes[allocationPhase]+=bytes;peakBytes[allocationPhase]=max(peakBytes[allocationPhase],liveBytes[allocationPhase]);++allocationCalls[allocationPhase];allocatedBytes[allocationPhase]+=bytes;if(captureAllocationSizes&&capturedCounts[allocationPhase]<16)capturedSizes[allocationPhase][capturedCounts[allocationPhase]++]=bytes;return p+1;}
void operator delete(void* p){if(p){AllocationHeader* h=((AllocationHeader*)p)-1;liveBytes[h->phase]-=h->bytes;free(h);}}
void* operator new[](size_t n){return ::operator new(n);}void operator delete[](void* p){::operator delete(p);}
static bool failQueue=false;
static void BeforeQueuePush(){if(failQueue){failQueue=false;throw std::bad_alloc();}}
static unsigned unitIDReads=0;
struct CvUnit{int id;CvUnit(int v=0):id(v){}int GetID()const{++unitIDReads;return id;}};
struct FixtureStorage{int limit;FixtureStorage():limit(6000){}int getSizeLimit()const{return limit;}}gTactPosStorage;
const int TACTSIM_MAX_UNITS=13;
namespace CvStackingStrengthCache{
 volatile LONG epoch=1;bool suspended=false,allowed=true;unsigned calls=0,flipAt=0;
 long SceneEpoch(){return InterlockedCompareExchange(&epoch,0,0);}
 bool IsPreviewSuspended(){return suspended;}
 bool Context(long& generation){++calls;if(flipAt&&calls==flipAt)InterlockedIncrement(&epoch);generation=SceneEpoch();return allowed;}
}
'''

fixture_tests=r'''
static int checks=0,failures=0;
void Expect(const char* label,bool value){++checks;if(!value){++failures;if(failures<12)printf("FAIL %s\n",label);}}
unsigned randomSeed=991293;unsigned Next(){randomSeed^=randomSeed<<13;randomSeed^=randomSeed>>17;randomSeed^=randomSeed<<5;return randomSeed;}
void ResetCounters(){
#define BOTH(v) Old::v=New::v=0
 BOTH(gStackDangerHits);BOTH(gStackDangerMisses);BOTH(gStackDefenderHits);BOTH(gStackDefenderMisses);BOTH(gStackInsertBypasses);BOTH(gStackNestedBypasses);BOTH(gStackDangerEvictions);BOTH(gStackDefenderEvictions);BOTH(gStackPeakEntries);BOTH(gStackPeakKeyBytes);BOTH(gStackPeakEstimatedBytes);
#undef BOTH
}
void ReleaseOld(){Old::ClearStackForecastEntries();Old::StackDangerForecasts().swap(Old::gStackDangerForecasts);Old::StackDefenderForecasts().swap(Old::gStackDefenderForecasts);deque<const Old::StackForecastKey*>().swap(Old::gStackDangerOrder);deque<const Old::StackForecastKey*>().swap(Old::gStackDefenderOrder);Old::gStackForecastOwnerThread=0;Old::gStackForecastDepth=0;Old::gStackForecastsActive=false;}
void ReleaseNew(){New::ClearStackForecastEntries();New::gIndexed.Release();New::gUseIndexed=false;New::StackDangerForecasts().swap(New::gStackDangerForecasts);New::StackDefenderForecasts().swap(New::gStackDefenderForecasts);deque<const New::StackForecastKey*>().swap(New::gStackDangerOrder);deque<const New::StackForecastKey*>().swap(New::gStackDefenderOrder);New::gStackForecastOwnerThread=0;New::gStackForecastDepth=0;New::gStackForecastsActive=false;}
void InitOld(size_t cap,size_t payload){Old::ClearStackForecastEntries();Old::gStackEntryLimit=cap;Old::gStackKeyPayloadLimit=payload;Old::gStackForecastOwnerThread=(LONG)GetCurrentThreadId();Old::gStackForecastDepth=1;Old::gStackForecastsActive=true;Old::gStackForecastSceneEpoch=CvStackingStrengthCache::SceneEpoch();}
void InitNew(size_t cap,size_t payload){New::gStackForecastsActive=false;New::gStackForecastOwnerThread=0;New::gUseIndexed=false;New::ClearStackForecastEntries();New::gIndexed.Init(cap);New::gUseIndexed=true;New::gStackEntryLimit=cap;New::gStackKeyPayloadLimit=payload;New::gStackForecastOwnerThread=(LONG)GetCurrentThreadId();New::gStackForecastDepth=1;New::gStackForecastsActive=true;New::gStackForecastSceneEpoch=CvStackingStrengthCache::SceneEpoch();}
void Init(size_t cap,size_t payload){ReleaseOld();ReleaseNew();InitOld(cap,payload);InitNew(cap,payload);ResetCounters();Old::gStackForecastRevision=New::gStackForecastRevision=0;}
struct KeyPair{Old::StackForecastKey a;New::StackForecastKey b;};
KeyPair MakeKey(int id,size_t length,size_t reserveExtra=0,bool collision=false){KeyPair result;result.a.state.reserve(length+reserveExtra);result.b.state.reserve(length+reserveExtra);for(size_t i=0;i<length;++i){int value=i?int(id*33+i*191):id;result.a.state.push_back(value);result.b.state.push_back(value);}if(collision&&length){size_t h=0;for(size_t i=0;i+1<length;++i)h^=(size_t)result.a.state[i]+0x9e3779b9+(h<<6)+(h>>2);int last=(int)(h-0x9e3779b9-(h<<6)-(h>>2));result.a.state.back()=result.b.state.back()=last;}return result;}
struct ValuePair{Old::StackDangerForecastValue a;New::StackDangerForecastValue b;};
ValuePair MakeValue(int scalar,size_t members){ValuePair result;result.a.scalar=result.b.scalar=scalar;for(size_t i=0;i<members;++i){pair<int,int> p(int(i%3)+1,i==1?INT_MAX:scalar+(int)i);result.a.memberScores.push_back(p);result.b.memberScores.push_back(p);}return result;}
struct Entry{int kind,scalar;size_t defender;vector<int> key;vector<pair<int,int> > members;bool operator<(const Entry& b)const{return kind!=b.kind?kind<b.kind:key<b.key;}bool operator==(const Entry& b)const{return kind==b.kind&&scalar==b.scalar&&defender==b.defender&&key==b.key&&members==b.members;}};
struct Snapshot{vector<Entry> entries;vector<vector<int> > dangerFIFO,defenderFIFO;};
Snapshot OldSnapshot(){Snapshot s;for(Old::StackDangerForecasts::const_iterator i=Old::gStackDangerForecasts.begin();i!=Old::gStackDangerForecasts.end();++i){Entry e;e.kind=0;e.scalar=i->second.scalar;e.defender=0;e.key=i->first.state;e.members=i->second.memberScores;s.entries.push_back(e);Expect("VC9 stored key/output capacities equal copied lengths",i->first.state.capacity()==i->first.state.size()&&i->second.memberScores.capacity()==i->second.memberScores.size());}for(Old::StackDefenderForecasts::const_iterator i=Old::gStackDefenderForecasts.begin();i!=Old::gStackDefenderForecasts.end();++i){Entry e;e.kind=1;e.scalar=0;e.defender=(size_t)i->second;e.key=i->first.state;s.entries.push_back(e);Expect("VC9 stored defender copied capacity",i->first.state.capacity()==i->first.state.size());}for(size_t i=0;i<Old::gStackDangerOrder.size();++i)s.dangerFIFO.push_back(Old::gStackDangerOrder[i]->state);for(size_t i=0;i<Old::gStackDefenderOrder.size();++i)s.defenderFIFO.push_back(Old::gStackDefenderOrder[i]->state);sort(s.entries.begin(),s.entries.end());return s;}
Snapshot NewSnapshot(){Snapshot s;if(!New::gUseIndexed){for(New::StackDangerForecasts::const_iterator i=New::gStackDangerForecasts.begin();i!=New::gStackDangerForecasts.end();++i){Entry e;e.kind=0;e.scalar=i->second.scalar;e.defender=0;e.key=i->first.state;e.members=i->second.memberScores;s.entries.push_back(e);}for(New::StackDefenderForecasts::const_iterator i=New::gStackDefenderForecasts.begin();i!=New::gStackDefenderForecasts.end();++i){Entry e;e.kind=1;e.scalar=0;e.defender=(size_t)i->second;e.key=i->first.state;s.entries.push_back(e);}for(size_t i=0;i<New::gStackDangerOrder.size();++i)s.dangerFIFO.push_back(New::gStackDangerOrder[i]->state);for(size_t i=0;i<New::gStackDefenderOrder.size();++i)s.defenderFIFO.push_back(New::gStackDefenderOrder[i]->state);}else{for(size_t i=0;i<New::gIndexed.Capacity();++i){const New::IndexedStore::Slot& slot=New::gIndexed.At((int)i);if(!slot.used)continue;Entry e;e.kind=slot.kind;e.scalar=slot.scalar;e.defender=(size_t)slot.defender;e.key.assign(slot.Data(),slot.Data()+slot.keyWords);for(size_t j=0;j<slot.members;++j)e.members.push_back(make_pair(slot.Data()[slot.keyWords+2*j],slot.Data()[slot.keyWords+2*j+1]));s.entries.push_back(e);}for(int kind=0;kind<2;++kind)for(int i=New::gIndexed.Head(kind);i!=-1;i=New::gIndexed.NextQueued(i)){const New::IndexedStore::Slot& slot=New::gIndexed.At(i);vector<int> key(slot.Data(),slot.Data()+slot.keyWords);(kind?s.defenderFIFO:s.dangerFIFO).push_back(key);}}sort(s.entries.begin(),s.entries.end());return s;}
void Compare(bool requireInvariant=true){Snapshot a=OldSnapshot(),b=NewSnapshot();Expect("full owned values and namespace equality",a.entries==b.entries);Expect("both FIFO insertion orders exact",a.dangerFIFO==b.dangerFIFO&&a.defenderFIFO==b.defenderFIFO);
#define SAME(v) Expect(#v " exact",Old::v==New::v)
 SAME(gStackDangerHits);SAME(gStackDangerMisses);SAME(gStackDefenderHits);SAME(gStackDefenderMisses);SAME(gStackInsertBypasses);SAME(gStackDangerEvictions);SAME(gStackDefenderEvictions);SAME(gStackKeyPayloadBytes);SAME(gStackPeakEntries);SAME(gStackPeakKeyBytes);SAME(gStackForecastRevision);SAME(gStackForecastSceneEpoch);
#undef SAME
 Expect("entry sizes exact",Old::gStackDangerForecasts.size()==(New::gUseIndexed?New::gIndexed.Count(0):New::gStackDangerForecasts.size())&&Old::gStackDefenderForecasts.size()==(New::gUseIndexed?New::gIndexed.Count(1):New::gStackDefenderForecasts.size()));if(requireInvariant)Expect("candidate bounded logical ownership",New::gUseIndexed?New::gIndexed.Invariant(New::gStackKeyPayloadBytes,New::gStackEntryLimit,New::gStackKeyPayloadLimit):(New::gIndexed.Capacity()==0&&New::gStackDangerForecasts.size()==New::gStackDangerOrder.size()&&New::gStackDefenderForecasts.size()==New::gStackDefenderOrder.size()&&New::gStackKeyPayloadBytes<=New::gStackKeyPayloadLimit));}
void Store(int kind,const KeyPair& key,const ValuePair& value,const CvUnit* unit=NULL){if(kind==0){Old::StoreStackDangerForecast(key.a,value.a.scalar);New::StoreStackDangerForecast(key.b,value.b.scalar);}else if(kind==1){Old::StoreStackDefenderForecast(key.a,unit);New::StoreStackDefenderForecast(key.b,unit);}else{Old::StoreStackDangerPacketForecast(key.a,value.a);New::StoreStackDangerPacketForecast(key.b,value.b);}}
bool OldDanger(const Old::StackForecastKey& key,int& result){if(!Old::StackForecastContext())return false;Old::StackDangerForecasts::const_iterator i=Old::gStackDangerForecasts.find(key);if(i==Old::gStackDangerForecasts.end()){++Old::gStackDangerMisses;return false;}++Old::gStackDangerHits;result=i->second.scalar;return true;}
bool NewDanger(const New::StackForecastKey& key,int& result){if(!New::StackForecastContext())return false;if(!New::FindStackDangerForecastScalar(key,result)){++New::gStackDangerMisses;return false;}++New::gStackDangerHits;return true;}
void Lookups(const KeyPair& key){int a=-991,b=-992;bool x=OldDanger(key.a,a),y=NewDanger(key.b,b);Expect("scalar hit/miss and full int exact",x==y&&(!x||a==b));Old::StackDefenderForecasts::const_iterator it=Old::gStackDefenderForecasts.find(key.a);const CvUnit* nv=NULL;bool nh=New::FindStackDefenderForecast(key.b,nv);if(it==Old::gStackDefenderForecasts.end())++Old::gStackDefenderMisses;else ++Old::gStackDefenderHits;if(nh)++New::gStackDefenderHits;else ++New::gStackDefenderMisses;Expect("null/pointer defender equality",(it!=Old::gStackDefenderForecasts.end())==nh&&(!nh||it->second==nv));for(int id=0;id<6;++id){CvUnit unit(id);bool ah=false;int av=0,bv=0;unitIDReads=0;Old::StackDangerForecasts::const_iterator p=Old::gStackDangerForecasts.find(key.a);if(p!=Old::gStackDangerForecasts.end())for(size_t j=0;j<p->second.memberScores.size();++j)if(p->second.memberScores[j].first==unit.GetID()){ah=true;av=p->second.memberScores[j].second;break;}unsigned oldReads=unitIDReads;unitIDReads=0;bool bh=New::FindStackDangerForecastMember(key.b,&unit,bv);Expect("actual helper packet first matching member exact",ah==bh&&(!ah||av==bv));Expect("actual helper preserves ID getter calls on miss/empty/first match",oldReads==unitIDReads);}}
void Differential(){CvUnit unit(71);size_t caps[]={0,1,2,5,16,64};size_t budgets[]={0,4,32,64,511,624000};size_t lengths[]={0,1,2,3,6,18,31,32,33,51,64,97,129};for(size_t c=0;c<6;++c)for(size_t budget=0;budget<6;++budget){Init(caps[c],budgets[budget]);vector<KeyPair> keys;for(int id=0;id<90;++id){keys.push_back(MakeKey(100+id,lengths[id%13],0,id%2==0));if(id%7==0){keys.back().a.state.reserve(lengths[id%13]+128);keys.back().b.state.reserve(lengths[id%13]+128);}}for(int op=0;op<900;++op){KeyPair& key=keys[Next()%keys.size()];ValuePair value=MakeValue(op%19==0?INT_MAX:op,Next()%8);int type=Next()%6;if(type<3)Store(type,key,value,op%3?&unit:NULL);else if(type==3)Lookups(key);else if(type==4){Old::ClearStackForecastEntries();New::ClearStackForecastEntries();}else{InterlockedIncrement(&CvStackingStrengthCache::epoch);Old::StackForecastContext();New::StackForecastContext();}Compare();}}ReleaseOld();ReleaseNew();}
void SourceCapacityAndFIFO(){Init(3,512);CvUnit u(1);KeyPair a=MakeKey(1,2),b=MakeKey(2,2),c=MakeKey(3,2),d=MakeKey(4,2);ValuePair v=MakeValue(10,2);Store(0,a,v);Store(0,b,v);Store(0,c,v);Lookups(a);Store(0,d,v);Expect("FIFO hit never promotes",Old::gStackDangerForecasts.find(a.a)==Old::gStackDangerForecasts.end());Compare();Store(0,d,MakeValue(999,2));Compare();Init(8,80);KeyPair retained=MakeKey(10,4);Store(0,retained,v);KeyPair reserved=MakeKey(20,2);reserved.a.state.reserve(20);reserved.b.state.reserve(20);Expect("source-capacity fixture retained reserve",reserved.a.state.capacity()>reserved.a.state.size());Store(0,reserved,v);Expect("source preflight capacity evicts although stored charge small",Old::gStackDangerEvictions==1&&Old::gStackKeyPayloadBytes==8);Compare();Init(2,64);Store(1,a,v,&u);Store(0,b,v);KeyPair packet=MakeKey(8,3);Store(2,packet,v);Expect("pending packet counted without FIFO and danger wins tied queues",Old::gStackDefenderForecasts.size()==1&&Old::gStackDangerEvictions==1);Compare();Store(2,packet,MakeValue(999,3));Compare();ReleaseOld();ReleaseNew();}
void SourceLifetime(){Init(16,8192);KeyPair inlineQuery=MakeKey(775,18),overflowQuery=MakeKey(776,65);{KeyPair source=inlineQuery;ValuePair value=MakeValue(INT_MAX,5);Store(0,source,value);source.a.state.assign(91,-1);source.b.state.assign(91,-1);value.a.memberScores.assign(9,make_pair(-1,-1));value.b.memberScores.assign(9,make_pair(-1,-1));}{KeyPair source=overflowQuery;ValuePair value=MakeValue(77,5);Store(2,source,value);vector<int>().swap(source.a.state);vector<int>().swap(source.b.state);vector<pair<int,int> >().swap(value.a.memberScores);vector<pair<int,int> >().swap(value.b.memberScores);}Lookups(inlineQuery);Lookups(overflowQuery);Compare();for(int i=0;i<30;++i){KeyPair key=MakeKey(900+i,18);Store(0,key,MakeValue(i,3));}Compare();ReleaseOld();ReleaseNew();}
void LookupBoundaryCases(){Init(16,8192);KeyPair key=MakeKey(141,18);ValuePair zero=MakeValue(0,0);Store(0,key,zero);Store(1,key,zero,NULL);int scalar=-99;const CvUnit* defender=(const CvUnit*)1;Expect("actual scalar helper retains a zero hit",New::FindStackDangerForecastScalar(key.b,scalar)&&scalar==0);Expect("actual defender helper retains a NULL hit",New::FindStackDefenderForecast(key.b,defender)&&defender==NULL);Lookups(key);KeyPair packet=MakeKey(142,65);Store(2,packet,MakeValue(77,5));CvUnit query(1);int member=-99;unitIDReads=0;Expect("actual packet helper takes first duplicate member",New::FindStackDangerForecastMember(packet.b,&query,member)&&member==77&&unitIDReads==1);Lookups(packet);KeyPair missing=MakeKey(143,65);unitIDReads=0;Expect("actual packet helper does not read ID on missing key",!New::FindStackDangerForecastMember(missing.b,&query,member)&&unitIDReads==0);Compare();InterlockedIncrement(&CvStackingStrengthCache::epoch);Old::StackForecastContext();New::StackForecastContext();Expect("copied helper output survives clearing Context",member==77&&scalar==0&&defender==NULL);Compare();ReleaseOld();ReleaseNew();}
void ActualScopeCases(){ReleaseOld();ReleaseNew();Old::gStackForecastRevision=New::gStackForecastRevision=0;ResetCounters();gTactPosStorage.limit=32;{Old::StackForecastScope a(true);New::StackForecastScope b(true);Compare();KeyPair key=MakeKey(741,18);Store(0,key,MakeValue(8,3));Compare();{Old::StackForecastScope x(true);New::StackForecastScope y(true);Expect("actual nested scopes invalidate/bypass",!Old::StackForecastContext()&&!New::StackForecastContext());Compare();}Expect("actual nested exit reopens outer context",Old::StackForecastContext()&&New::StackForecastContext());Compare();}Expect("actual outer destructors release owner/depth",Old::gStackForecastOwnerThread==0&&New::gStackForecastOwnerThread==0&&Old::gStackForecastDepth==0&&New::gStackForecastDepth==0&&New::gIndexed.Capacity()==0);{Old::StackForecastScope a(false);New::StackForecastScope b(false);Expect("unsupported actual scope reserves no new array",!Old::StackForecastContext()&&!New::StackForecastContext()&&New::gIndexed.Capacity()==0);Compare();}for(int failure=0;failure<2;++failure){ReleaseOld();ReleaseNew();Old::gStackForecastRevision=New::gStackForecastRevision=0;{Old::StackForecastScope control(true);size_t before=liveBytes[2];allocationPhase=2;failAllocation=failure;{New::StackForecastScope fallback(true);failAllocation=-1;allocationPhase=0;Expect("actual failed reservation frees partial arrays before original fallback",!New::gUseIndexed&&New::gIndexed.Capacity()==0&&New::gIndexed.Buckets()==0&&liveBytes[2]==before&&New::StackForecastContext()&&New::gStackForecastOwnerThread==(LONG)GetCurrentThreadId()&&New::gStackForecastDepth==1);KeyPair key=MakeKey(753,18);Store(0,key,MakeValue(8,3));Compare();KeyPair odd=MakeKey(755,51);Store(2,odd,MakeValue(INT_MAX,5));Compare();CvUnit u(17);for(int i=0;i<48;++i){int type=i%3;KeyPair next=MakeKey(820+i,type==2?51:18,0,i%2==0);Store(type,next,MakeValue(i,5),i%4?&u:NULL);Lookups(next);Compare();}Expect("fallback workload exercises original FIFO evictions",Old::gStackDangerEvictions+Old::gStackDefenderEvictions>0);Expect("representation remains original after admissions",!New::gUseIndexed);}}Expect("fallback outer destructor releases owner",New::gStackForecastOwnerThread==0&&New::gStackForecastDepth==0);{New::StackForecastScope reopened(true);Expect("new search can reopen indexed after original fallback",New::gUseIndexed&&New::StackForecastContext());}}ReleaseOld();ReleaseNew();Old::gStackForecastRevision=New::gStackForecastRevision=0;gTactPosStorage.limit=INT_MAX;{Old::StackForecastScope oldHuge(true);New::StackForecastScope newHuge(true);Expect("unrepresentable indexed reservation uses original before any query",!New::gUseIndexed&&New::StackForecastContext());Store(0,MakeKey(781,18),MakeValue(3,3));Compare();}gTactPosStorage.limit=6000;ReleaseOld();ReleaseNew();}
DWORD WINAPI Foreign(void*){KeyPair key=MakeKey(901,18);ValuePair value=MakeValue(3,4);Store(0,key,value);Store(1,key,value);Store(2,key,value);return (!Old::StackForecastContext()&&!New::StackForecastContext())?0:1;}
void ContextCases(){Init(8,1024);KeyPair key=MakeKey(901,51);ValuePair v=MakeValue(9,4);Store(0,key,v);HANDLE thread=CreateThread(NULL,0,Foreign,NULL,0,NULL);Expect("foreign fixture thread created",thread!=NULL);if(thread){WaitForSingleObject(thread,10000);DWORD code=1;GetExitCodeThread(thread,&code);Expect("foreign admission bypass",code==0);CloseHandle(thread);}Compare();Old::gStackForecastDepth=New::gStackForecastDepth=2;Store(2,key,v);Compare();Old::gStackForecastDepth=New::gStackForecastDepth=1;CvStackingStrengthCache::suspended=true;Store(1,key,v);Compare();CvStackingStrengthCache::suspended=false;InterlockedIncrement(&CvStackingStrengthCache::epoch);Old::StackForecastContext();New::StackForecastContext();Compare();Init(8,1024);CvStackingStrengthCache::calls=0;CvStackingStrengthCache::flipAt=2;Old::StoreStackDangerPacketForecast(key.a,v.a);long oldEpoch=CvStackingStrengthCache::SceneEpoch();InterlockedDecrement(&CvStackingStrengthCache::epoch);CvStackingStrengthCache::calls=0;New::StoreStackDangerPacketForecast(key.b,v.b);CvStackingStrengthCache::flipAt=0;Expect("packet copied scene drift rejects same admission",oldEpoch==CvStackingStrengthCache::SceneEpoch()&&Old::gStackInsertBypasses==1&&New::gStackInsertBypasses==1);Compare();ReleaseOld();ReleaseNew();}
void FailureCases(){KeyPair wide=MakeKey(39,65);ValuePair packet=MakeValue(8,5);for(int type=0;type<3;++type){Init(1,1024);KeyPair victim=MakeKey(8,6);Store(0,victim,packet);bool a=false,b=false;failAllocation=0;try{if(type==0)Old::StoreStackDangerForecast(wide.a,8);else if(type==1)Old::StoreStackDefenderForecast(wide.a,NULL);else Old::StoreStackDangerPacketForecast(wide.a,packet.a);}catch(const bad_alloc&){a=true;}failAllocation=-1;failAllocation=0;try{if(type==0)New::StoreStackDangerForecast(wide.b,8);else if(type==1)New::StoreStackDefenderForecast(wide.b,NULL);else New::StoreStackDangerPacketForecast(wide.b,packet.b);}catch(const bad_alloc&){b=true;}failAllocation=-1;Expect("first owned overflow allocation failure observed",a&&b);Compare();}
 for(int type=0;type<3;++type){Init(2,1024);bool a=false,b=false;failQueue=true;try{if(type==0)Old::StoreStackDangerForecast(wide.a,8);else if(type==1)Old::StoreStackDefenderForecast(wide.a,NULL);else Old::StoreStackDangerPacketForecast(wide.a,packet.a);}catch(const bad_alloc&){a=true;}failQueue=true;try{if(type==0)New::StoreStackDangerForecast(wide.b,8);else if(type==1)New::StoreStackDefenderForecast(wide.b,NULL);else New::StoreStackDangerPacketForecast(wide.b,packet.b);}catch(const bad_alloc&){b=true;}failQueue=false;Expect("fixture FIFO boundary failure observed",a&&b);Compare(type==2);}
 ReleaseOld();ReleaseNew();for(int stage=0;stage<2;++stage){size_t before=liveBytes[2];allocationPhase=2;failAllocation=stage;bool caught=false;try{InitNew(6000,624000);}catch(const bad_alloc&){caught=true;}failAllocation=-1;allocationPhase=0;Expect("new constructor failures release both buffers",caught&&New::gIndexed.Capacity()==0&&New::gIndexed.Buckets()==0&&liveBytes[2]==before&&!New::gStackForecastsActive&&New::gStackForecastOwnerThread==0);InitNew(8,1024);Expect("new store reopens after constructor failure",New::StackForecastContext());ReleaseNew();}}
void FullCapacity(){Init(6000,624000);CvUnit u(82);for(int i=0;i<6010;++i){KeyPair key=MakeKey(i,18);ValuePair v=MakeValue(i,4);Store(i%17==0?1:0,key,v,i%3?&u:NULL);if(i%500==0||i>=5998)Compare();}Expect("fixed slot count permits pending extra slot only",New::gIndexed.Capacity()==6001);Expect("physical inline reserved memory explicitly above logical budget",New::gIndexed.ReservedBytes()>New::gStackKeyPayloadLimit);KeyPair packet=MakeKey(8001,51);Store(2,packet,MakeValue(3,6));Compare();ReleaseOld();ReleaseNew();Expect("search destruction releases slot/bucket payload",New::gIndexed.Capacity()==0&&New::gIndexed.ReservedBytes()==0);}
void AllocationProof(){size_t lengths[]={18,64,51};for(int type=0;type<3;++type){Init(64,624000);KeyPair key=MakeKey(781+type,lengths[type]);ValuePair v=MakeValue(8,5);allocationCalls[1]=allocationCalls[2]=allocatedBytes[1]=allocatedBytes[2]=0;capturedCounts[1]=capturedCounts[2]=0;captureAllocationSizes=true;allocationPhase=1;if(type==2)Old::StoreStackDangerPacketForecast(key.a,v.a);else Old::StoreStackDangerForecast(key.a,8);allocationPhase=2;if(type==2)New::StoreStackDangerPacketForecast(key.b,v.b);else New::StoreStackDangerForecast(key.b,8);allocationPhase=0;captureAllocationSizes=false;printf("ALLOC_PROOF kind%s keyWords%u memberPairs%u baseline_calls%u candidate_calls%u baseline_requested_bytes%u candidate_requested_bytes%u\n",type==2?"packet":"scalar",(unsigned)lengths[type],type==2?5:0,(unsigned)allocationCalls[1],(unsigned)allocationCalls[2],(unsigned)allocatedBytes[1],(unsigned)allocatedBytes[2]);for(int phase=1;phase<=2;++phase){printf("ALLOC_SIZES phase%d",phase);for(unsigned i=0;i<capturedCounts[phase];++i)printf(" %u",(unsigned)capturedSizes[phase][i]);printf("\n");}Expect("actual old copies allocate more than direct owned storage",allocationCalls[1]>allocationCalls[2]);Compare();}ReleaseOld();ReleaseNew();}
struct Timing{double ms;size_t calls,bytes,peak,resident,logical;unsigned long hits,misses,evictions;};
Timing Measure(bool indexed,const vector<KeyPair>& keys,const vector<unsigned>& order,const ValuePair& packet,int packetEvery){ReleaseOld();ReleaseNew();int phase=indexed?2:1;Expect("prior measured storage fully released",liveBytes[phase]==0);allocationCalls[phase]=allocatedBytes[phase]=peakBytes[phase]=0;ResetCounters();LARGE_INTEGER a,b,f;QueryPerformanceFrequency(&f);QueryPerformanceCounter(&a);allocationPhase=phase;if(indexed)InitNew(6000,624000);else InitOld(6000,624000);for(size_t i=0;i<order.size();++i){unsigned k=order[i];bool isPacket=packetEvery&&k%packetEvery==0;int value=0;if(indexed){if(!NewDanger(keys[k].b,value)){if(isPacket)New::StoreStackDangerPacketForecast(keys[k].b,packet.b);else New::StoreStackDangerForecast(keys[k].b,(int)k);}}else{if(!OldDanger(keys[k].a,value)){if(isPacket)Old::StoreStackDangerPacketForecast(keys[k].a,packet.a);else Old::StoreStackDangerForecast(keys[k].a,(int)k);}}}Timing result;result.calls=allocationCalls[phase];result.bytes=allocatedBytes[phase];result.peak=peakBytes[phase];result.resident=liveBytes[phase];result.logical=indexed?New::gStackKeyPayloadBytes:Old::gStackKeyPayloadBytes;result.hits=indexed?New::gStackDangerHits:Old::gStackDangerHits;result.misses=indexed?New::gStackDangerMisses:Old::gStackDangerMisses;result.evictions=indexed?New::gStackDangerEvictions:Old::gStackDangerEvictions;if(indexed)ReleaseNew();else ReleaseOld();allocationPhase=0;QueryPerformanceCounter(&b);result.ms=1000.0*(b.QuadPart-a.QuadPart)/f.QuadPart;Expect("owned indexed arrays released; original fallback empty buffers bounded",liveBytes[phase]<4096);return result;}
void Bench(const char* label,unsigned count,unsigned queries,bool mixed){vector<KeyPair> keys;keys.reserve(count);for(unsigned i=0;i<count;++i)keys.push_back(MakeKey(i,mixed&&i%5==0?51:18));vector<unsigned> order;order.reserve(queries);for(unsigned i=0;i<queries;++i)order.push_back(i%count);ValuePair packet=MakeValue(7,5);for(int pass=0;pass<2;++pass){Timing a,b;if(pass==0){a=Measure(false,keys,order,packet,mixed?5:0);b=Measure(true,keys,order,packet,mixed?5:0);}else{b=Measure(true,keys,order,packet,mixed?5:0);a=Measure(false,keys,order,packet,mixed?5:0);}Expect("benchmark work and cache policy exact",a.hits==b.hits&&a.misses==b.misses&&a.evictions==b.evictions&&a.logical==b.logical);printf("BENCH %s pass%d queries%u ms%.3f->%.3f allocation_calls%u->%u requested_bytes%u->%u peak_requested_bytes%u->%u resident_requested_bytes%u->%u logical_bytes%u hits%lu misses%lu evictions%lu\n",label,pass,queries,a.ms,b.ms,(unsigned)a.calls,(unsigned)b.calls,(unsigned)a.bytes,(unsigned)b.bytes,(unsigned)a.peak,(unsigned)b.peak,(unsigned)a.resident,(unsigned)b.resident,(unsigned)a.logical,a.hits,a.misses,a.evictions);}}
int main(int argc,char** argv){bool noBenchmark=argc>1&&!strcmp(argv[1],"--no-benchmark");Expect("x86 VC9 widths and pair storage",sizeof(void*)==4&&sizeof(size_t)==4&&sizeof(pair<int,int>)==8);printf("Indexed Slot%uB inlineWords32. Reserved slots include pending extra slot. Physical requested bytes exclude CRT/header overhead. Synthetic traces are NOT native captures.\n",(unsigned)sizeof(New::IndexedStore::Slot));Differential();SourceCapacityAndFIFO();SourceLifetime();LookupBoundaryCases();ContextCases();FailureCases();ActualScopeCases();FullCapacity();AllocationProof();if(!noBenchmark){Bench("resident512_scalar",512,200000,false);Bench("churn17000_scalar",17000,200000,false);Bench("churn17000_mixed20pct",17000,200000,true);}printf("Indexed forecast-store oracle: %d checks, %d failures\n",checks,failures);return failures?1:0;}
'''

fixture=fixture_prefix+'\nnamespace Old{\n'+prefix+extras+actual_scope+instrumented+'\n}\nnamespace New{\n'+types+legacy_tables+globals_and_owner+indexed+context+extras+new_scope+legacy_methods+indexed_methods+lookup_helpers+'\n}\n'+fixture_tests
OUT.mkdir(exist_ok=True)
(OUT/'test.cpp').write_text(fixture,encoding='utf-8')
(OUT/'actual-old-storage.cpp').write_text(prefix+methods,encoding='utf-8')
proof=dict(baseline=BASELINE,path=SOURCE,actualSourceSHA256=hashlib.sha256(source.encode()).hexdigest(),
           oldStorageSHA256=hashlib.sha256((prefix+methods).encode()).hexdigest(),
           candidateStorageSHA256=hashlib.sha256((types+legacy_tables+globals_and_owner+indexed+context+legacy_methods+indexed_methods).encode()).hexdigest(),
           fixtureSHA256=hashlib.sha256(fixture.encode()).hexdigest(),
           originalContextByteIdentical=True,originalOldMethodsByteIdenticalAfterRemovingFixtureFIFOFailureHook=True,
           actualOriginalScopeSHA256=hashlib.sha256(actual_scope.encode()).hexdigest(),
           candidateScopeSHA256=hashlib.sha256(new_scope.encode()).hexdigest(),
           wholeSourceBinding=binding,
           templates={name:hashlib.sha256((TEMPLATES/name).read_bytes()).hexdigest() for name in ('IndexedStore.h','IndexedMethods.h')},
           scope='WORK ONLY: DLL86 actual store methods versus indexed inline32/owned overflow. No search limits/keys/admission/FIFO changes. Native speed unmeasured.')
(OUT/'source-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
if args.emit_only:
    print(json.dumps(dict(status='emitted_only',**proof)));sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
compile=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/GS','/Z7',str(OUT/'test.cpp'),'/Fo'+str(OUT/'test.obj'),'/Fe'+str(OUT/'test.exe')],cwd=OUT,env=env,capture_output=True,text=True,timeout=60)
(OUT/'compile.log').write_text(compile.stdout+compile.stderr,encoding='utf-8')
if compile.returncode:print(compile.stdout+compile.stderr);sys.exit(compile.returncode)
run=subprocess.run([str(OUT/'test.exe')]+(['--no-benchmark'] if args.no_benchmark else []),cwd=OUT,capture_output=True,text=True,timeout=90)
report=dict(**proof,returncode=run.returncode,output=run.stdout+run.stderr,benchmarkExecuted=not args.no_benchmark,
            allocationInterpretation='Requested store-owned allocations only; query-key and oracle/trace preparation outside measured phase. Physical reserved inline+overflow+transient copies counted; CRT bookkeeping excluded. Synthetic timings are not native speedups.')
(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(run.stdout+run.stderr,end='');sys.exit(run.returncode)
