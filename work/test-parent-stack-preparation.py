"""Actual DLL91 preparation/danger/CoW bodies, old/new VC9 x86 oracle.

The forecast backend and native danger math are deterministic substitutes; full
key serialization, scalar helper gates, query loans, first-match stats and EFD
preview methods are extracted from the pinned source. No native speed claim.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,sys
import importlib.util
spec=importlib.util.spec_from_file_location('prepare_parent_stack_preparation',Path(__file__).with_name('prepare-parent-stack-preparation.py'));prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(prepare)
stage,ROOT,BASE,OUT=prepare.stage,prepare.ROOT,prepare.BASE,prepare.OUT
P=argparse.ArgumentParser(description=__doc__);P.add_argument('--emit-only',action='store_true');P.add_argument('--production',action='store_true');args=P.parse_args()
old,hpp,new,newhpp=stage();out=ROOT/'work/parent-stack-preparation-regression';out.mkdir(exist_ok=True)
dependencies=('CvUnit.h','CvUnit.cpp','CvUnitCombat.cpp','CvUnitCombat.h','CvDangerPlots.cpp','CvDangerPlots.h','CvStackingStrengthCache.cpp','CvStackingStrengthCache.h','CvStackingRules.cpp','CvStackingRules.h','CvPlot.cpp','CvPlot.h','CvPlayer.cpp','CvPlayer.h','CvUnitClasses.cpp','CvUnitClasses.h')
dependency_hashes={}
for name in dependencies:
    pinned=subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/'+name],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
    dependency_hashes[name]=hashlib.sha256(pinned.encode()).hexdigest()
    if args.production:
        assert (ROOT/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig')==pinned,'Unchanged production dependency mismatch: '+name
if args.production:
    for name,expected in [('CvTacticalAI.cpp',new),('CvTacticalAI.h',newhpp)]:
        live=(ROOT/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig')
        assert live==expected,'Whole production candidate mismatch: '+name
def section(s,a,b):
    i=s.index(a);return s[i:s.index(b,i)]
def clean(s):
    s=''.join(line for line in s.splitlines(True) if 'PLAN_SAMPLE_DIAGNOSTIC_ONLY' not in line and 'DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY' not in line)
    s=s.replace('return kernelProbe.Finish(iDanger == INT_MAX ? 10 * pUnit->GetMaxHitPoints() : iDanger); // DESTINATION_KERNEL_SHADOW_WRAP_ORIGINAL_RETURN','return iDanger == INT_MAX ? 10 * pUnit->GetMaxHitPoints() : iDanger;')
    return s
unit=subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/CvUnit.h'],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n')
container=section(unit,'struct SUnitIDValueContainer\n','\nnamespace std {')
cow=section(hpp,'template<typename T>\nstruct SCoWField','class CvBasePosition')
stats=section(old,'const SUnitStats* CvBasePosition::GetUnitStats(','const STacticalAssignment* CvBasePosition::getInitialAssignment(')
stats=stats.replace('{\n\tconst vector<SUnitStats>& availableUnits_r','{\n ++statsReads; if(statsCallback) statsCallback();\n\tconst vector<SUnitStats>& availableUnits_r',1)
shares=section(newhpp,'\tbool SharesVirtualStackInputs(','\n\tconst CvTacticalPlot* getTactPlot(')
for field in ('tactPlotLookup','tactPlots','availableUnits','notQuiteFinishedUnits','finishedUnits'):
    assert field+'.inheritFrom(parent.'+field+'.read());' in old
# Full scalar/danger body change is exactly one preparation call substitution.
dangerold=clean(section(old,'static int GetUnitDangerForPlot(','static unsigned char GetStackAttackThreatFlags('))
dangernew=clean(section(new,'static int GetUnitDangerForPlot(','static unsigned char GetStackAttackThreatFlags('))
assert dangernew.replace('GetPreparedVirtualFriendlyStack(assumedPosition, pPlot, pUnit, iSelfDamage, stack.candidates, stack.damage, stack.borrowed);','GetVirtualFriendlyStack(assumedPosition, pPlot, pUnit, iSelfDamage, stack.candidates, stack.damage);')==dangerold
assert section(old,'static int GetCachedStackDanger(','static const CvUnit* SelectCachedStackDefender(')==section(new,'static int GetCachedStackDanger(','static const CvUnit* SelectCachedStackDefender(')
prefix=r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <cstdio>
#include <vector>
#include <map>
#include <climits>
#include <new>
#include <cstring>
#include <cstdlib>
using namespace std;
static long fixtureFailAllocation=-1;static size_t fixtureAllocations=0,fixtureLiveBytes=0;
struct FixtureAllocationHeader{size_t bytes;};
void*operator new(size_t n){++fixtureAllocations;if(fixtureFailAllocation==0){fixtureFailAllocation=-1;throw std::bad_alloc();}if(fixtureFailAllocation>0)--fixtureFailAllocation;FixtureAllocationHeader*p=(FixtureAllocationHeader*)malloc(n+sizeof(FixtureAllocationHeader));if(!p)throw std::bad_alloc();p->bytes=n;fixtureLiveBytes+=n;return p+1;}
void operator delete(void*p){if(p){FixtureAllocationHeader*h=((FixtureAllocationHeader*)p)-1;fixtureLiveBytes-=h->bytes;free(h);}}void*operator new[](size_t n){return::operator new(n);}void operator delete[](void*p){::operator delete(p);}
namespace CvStackingStrengthCache{volatile LONG epoch=1;long SceneEpoch(){return InterlockedCompareExchange(&epoch,0,0);}void Invalidate(){InterlockedIncrement(&epoch);}}
typedef int PlayerTypes;const int DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_AIR=2;
struct CvCity{int protection;CvCity():protection(0){}};
struct CvPlot{int index;bool city;CvCity cityData;CvPlot(int i=0):index(i),city(false){}int GetPlotIndex()const{return index;}bool isCity()const{return city;}const CvCity*getPlotCity()const{return city?&cityData:NULL;}};
struct CvUnit{int id,domain,owner,maxHP;bool combat,cargo;CvUnit(int n=0):id(n),domain(0),owner(0),maxHP(100),combat(true),cargo(false){}int GetID()const{return id;}int getOwner()const{return owner;}bool IsCombatUnit()const{return combat;}bool isCargo()const{return cargo;}int getDomainType()const{return domain;}int GetMaxHitPoints()const{return maxHP;}int GetDanger(const CvPlot*,const struct SUnitIDValueContainer&,int)const{return 87;}};
'''
model=r'''
struct SUnitStats{int iUnitID,iSelfDamage;SUnitStats(int id=0,int d=0):iUnitID(id),iSelfDamage(d){}};
struct STacticalUnit{int iUnitID;STacticalUnit(int id=0):iUnitID(id){}};
struct CvTacticalPlot{int index;vector<const CvUnit*>fixed;vector<STacticalUnit>moving;CvTacticalPlot(int i=0):index(i){}const vector<const CvUnit*>&getFixedFriendlyUnits()const{return fixed;}const vector<STacticalUnit>&getUnitsAtPlot()const{return moving;}};
static unsigned long statsReads=0,unitReads=0,virtualBuilds=0,contextCalls=0,scalarHits=0,scalarMisses=0;
static void(*statsCallback)()=NULL;
static bool active=true;static DWORD owner=0;
static unsigned long gStackForecastRevision=1;static long gStackForecastSceneEpoch=1;static size_t gStackKeyPayloadLimit=624000;
static bool StackForecastContext(){++contextCalls;return active&&GetCurrentThreadId()==owner&&gStackForecastSceneEpoch==CvStackingStrengthCache::SceneEpoch();}
struct CvBasePosition{SCoWField<vector<SUnitStats> >availableUnits,notQuiteFinishedUnits,finishedUnits;PlayerTypes ePlayer;CvBasePosition():ePlayer(0){}const SUnitStats*GetUnitStats(int)const;};
struct CvTacticalPosition:public CvBasePosition{
 SCoWField<vector<pair<int,int> > >tactPlotLookup;SCoWField<vector<CvTacticalPlot> >tactPlots;SCoWField<SUnitIDValueContainer>unitDamageDealt;
 const CvTacticalPlot*getTactPlot(int i)const{const vector<CvTacticalPlot>&ps=tactPlots.read();for(size_t n=0;n<ps.size();++n)if(ps[n].index==i)return&ps[n];return NULL;}
 int getPlayer()const{return ePlayer;}const SUnitIDValueContainer&GetUnitDamageDealt()const{return unitDamageDealt.read();}
 void initFromParent(const CvTacticalPosition&parent){ePlayer=parent.ePlayer;tactPlotLookup.inheritFrom(parent.tactPlotLookup.read());tactPlots.inheritFrom(parent.tactPlots.read());availableUnits.inheritFrom(parent.availableUnits.read());notQuiteFinishedUnits.inheritFrom(parent.notQuiteFinishedUnits.read());finishedUnits.inheritFrom(parent.finishedUnits.read());unitDamageDealt.inheritFrom(parent.unitDamageDealt.read());}
 void ChangeUnitDamage(int id,int d){unitDamageDealt.write().ChangeValue(id,d);}void ChangeCityDamage(int id,int d){unitDamageDealt.write().ChangeValue(-id,d);}
 SHARES
};
struct STacticalAssignment{SUnitIDValueContainer unitDamage;int iDamagedCityId,iCityDamage;STacticalAssignment():iDamagedCityId(-1),iCityDamage(0){}};
struct CvDangerPlots{
 bool fixed;int fixedValue,leafCalls;vector<int>sourceIDs;bool hasSources;
 CvDangerPlots():fixed(false),fixedValue(0),leafCalls(0),hasSources(false){}
 bool TryGetFixedStackDanger(const CvPlot&,const CvUnit*,int&r){if(!fixed)return false;r=fixedValue;return true;}
 const vector<int>*GetStackDangerDamageIDs(const CvPlot&){return hasSources?&sourceIDs:NULL;}
 int GetStackDanger(const CvPlot&p,const CvUnit*u,const vector<const CvUnit*>&members,const SUnitIDValueContainer&fd,const SUnitIDValueContainer&ed){++leafCalls;unsigned int v=u->GetID()*13u+p.index;for(size_t i=0;i<members.size();++i){v=v*31+(members[i]?members[i]->GetID():111);if(members[i])v=v*17+fd.GetValue(members[i]->GetID());}for(SUnitIDValueContainer::const_iterator it=ed.begin();it!=ed.end();++it){v=v*7+(*it).first;v=v*23+(*it).second;}return v%89u==0?INT_MAX:(int)(v%217u);}
};
struct Player{map<int,CvUnit*>units;CvDangerPlots danger;const CvUnit*getUnit(int id)const{++unitReads;map<int,CvUnit*>::const_iterator it=units.find(id);return it==units.end()?NULL:it->second;}CvDangerPlots*GetDangerPlots(){return&danger;}}player;
#define GET_PLAYER(id) player
struct CvStacking{enum{HOT_DefenderSelectionEnabled};static bool enabled;static bool IsEnabled(){return enabled;}static int GetCityProtection(const CvCity*c){return c?c->protection:0;}static int GetIntByKey(int,int d){return d;}};bool CvStacking::enabled=true;
struct StackForecastKey{vector<int>state;};static StackForecastKey gStackDangerScratch;static bool gStackDangerScratchBusy=false,gStackSortScratchBusy=false;static vector<pair<int,int> >gStackSortScratch;
static vector<vector<int> >keys;static vector<size_t>keyCapacities;static map<vector<int>,int>cache;static unsigned long gStackDangerHits=0,gStackDangerMisses=0;
struct StackDangerOutcomeBatch{bool ready;StackDangerOutcomeBatch():ready(false){}bool TryGet(const CvUnit*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&,int&){return false;}};
struct StackDangerForecastValue{};struct StackDangerPacketBuffer{StackForecastKey key;StackDangerForecastValue value;};struct StackDangerPacketQuery{bool scalarValid,storePacket;StackDangerPacketBuffer buffer;StackDangerPacketQuery(bool):scalarValid(false),storePacket(false){}};
static bool ResolveStackDangerPacket(StackDangerPacketQuery&,const CvUnit*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&,const StackForecastKey&,unsigned long,long,StackDangerOutcomeBatch*,int&){return false;}
static bool ValidateStackDangerPacket(StackDangerPacketQuery&,const CvUnit*,const CvPlot*,unsigned long,long){return false;}
static void StoreStackDangerPacketForecast(const StackForecastKey&,const StackDangerForecastValue&){}
struct PacketProbeCall{PacketProbeCall(const CvUnit*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&,const StackForecastKey&,bool){}void MarkRaw(){}void Finish(){}};
static bool AppendImmutableEnemyDamage(StackForecastKey&,const SUnitIDValueContainer&,const vector<int>*){return false;}
static bool FindStackDangerForecastScalar(const StackForecastKey&key,int&r){keys.push_back(key.state);keyCapacities.push_back(key.state.capacity());map<vector<int>,int>::const_iterator it=cache.find(key.state);if(it==cache.end()){++scalarMisses;return false;}++scalarHits;r=it->second;return true;}
static void StoreStackDangerForecast(const StackForecastKey&key,int r){cache[key.state]=r;}
struct LegacyDangerCache{bool findDanger(int,int,int,const SUnitIDValueContainer&,int&){return false;}void storeDanger(int,int,int,const SUnitIDValueContainer&,int){}};struct Storage{LegacyDangerCache danger;LegacyDangerCache&getDangerCache(){return danger;}}gTactPosStorage;
'''
def build_namespace(s,h,name):
    query=section(s,'struct StackForecastQuery\n','// A const preferred-assignment call')
    buf=section(s,'struct VirtualFriendlyStackBuffer\n','// Warmed owned packet query storage;')
    builder=section(s,'static void GetVirtualFriendlyStack(','// A same-tile escort counts only')
    builder=builder.replace('{\n const CvTacticalPlot* tactical = position.getTactPlot(plot->GetPlotIndex());','{\n ++virtualBuilds;\n const CvTacticalPlot* tactical = position.getTactPlot(plot->GetPlotIndex());',1)
    append=section(s,'static void AppendStackCandidates(','// Bind immutable inputs only for this short helper call.')
    scalar=clean(section(s,'static int GetCachedStackDanger(','static const CvUnit* SelectCachedStackDefender('))
    danger=clean(section(s,'static int GetUnitDangerForPlot(','static unsigned char GetStackAttackThreatFlags('))
    nxt=section(s,'static void GetNextPosition(','// what does the unit look like after this assignment')
    setup=model.replace(' SHARES',shares)
    return 'namespace '+name+'{\n'+cow+setup+stats+query+buf+builder+append+scalar+danger+nxt+'\n}\n'
tests=r'''
static int checks=0,failures=0;static size_t maximumRetained=0;static void expect(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<20)printf("FAIL %s\n",n);}}
static void checkBytes(){size_t sum=0;for(size_t i=0;i<newer::ParentStackPreparationStorage::MAX_CELLS;++i)sum+=newer::gParentStackPreparationStorage.CellBytes(i);expect("incremental retained bytes equals all-cell capacity sum",sum==newer::gParentStackPreparationStorage.RetainedBytes());if(sum>maximumRetained)maximumRetained=sum;}
static unsigned int rng=1742127;static unsigned int next(){rng=rng*1664525u+1013904223u;return rng;}
static bool sameDamage(const SUnitIDValueContainer&a,const SUnitIDValueContainer&b){vector<pair<int,int> >x,y;for(SUnitIDValueContainer::const_iterator it=a.begin();it!=a.end();++it)x.push_back(*it);for(SUnitIDValueContainer::const_iterator it=b.begin();it!=b.end();++it)y.push_back(*it);return x==y;}
static void reset(){old::active=newer::active=true;old::owner=newer::owner=GetCurrentThreadId();old::gStackForecastSceneEpoch=newer::gStackForecastSceneEpoch=CvStackingStrengthCache::SceneEpoch();old::gStackForecastRevision=newer::gStackForecastRevision=1;old::cache.clear();newer::cache.clear();old::keys.clear();newer::keys.clear();old::keyCapacities.clear();newer::keyCapacities.clear();old::contextCalls=newer::contextCalls=0;old::virtualBuilds=newer::virtualBuilds=0;old::unitReads=newer::unitReads=0;old::statsReads=newer::statsReads=0;old::gStackDangerHits=newer::gStackDangerHits=0;old::gStackDangerMisses=newer::gStackDangerMisses=0;old::gStackDangerScratch.state.clear();newer::gStackDangerScratch.state.clear();old::CvStacking::enabled=newer::CvStacking::enabled=true;old::player.danger.fixed=newer::player.danger.fixed=false;}
static void compareDanger(CvUnit*u,CvPlot*p,int hp,const old::CvTacticalPosition&o,const newer::CvTacticalPosition&n){int a=old::GetUnitDangerForPlot(u,p,hp,o),b=newer::GetUnitDangerForPlot(u,p,hp,n);expect("actual danger including sentinel clamp",a==b);expect("exact serialized key sequence",old::keys==newer::keys);expect("scratch capacity/preflight unchanged",old::keyCapacities==newer::keyCapacities);expect("no extra Context calls",old::contextCalls==newer::contextCalls);expect("scalar hit/miss graph unchanged",old::gStackDangerHits==newer::gStackDangerHits&&old::gStackDangerMisses==newer::gStackDangerMisses);}
static void preparePositions(old::CvTacticalPosition&o,newer::CvTacticalPosition&n,CvUnit*pool,int count){old::CvTacticalPlot op(7);newer::CvTacticalPlot np(7);for(int i=0;i<count;++i){const int id=(int)(next()%19)+1;if(next()%2){op.fixed.push_back(&pool[id-1]);np.fixed.push_back(&pool[id-1]);}else{op.moving.push_back(old::STacticalUnit(id));np.moving.push_back(newer::STacticalUnit(id));}if(next()%4){int hp=(int)(next()%240)-70;o.availableUnits.write().push_back(old::SUnitStats(id,hp));n.availableUnits.write().push_back(newer::SUnitStats(id,hp));}int hp=(int)(next()%140);o.notQuiteFinishedUnits.write().push_back(old::SUnitStats(id,hp));n.notQuiteFinishedUnits.write().push_back(newer::SUnitStats(id,hp));hp=(int)(next()%140);o.finishedUnits.write().push_back(old::SUnitStats(id,hp));n.finishedUnits.write().push_back(newer::SUnitStats(id,hp));}o.tactPlots.write().push_back(op);n.tactPlots.write().push_back(np);}
static void bump(){CvStackingStrengthCache::Invalidate();}
static const newer::CvTacticalPosition*callbackParent=NULL;
static void invalidateBuild(){newer::statsCallback=NULL;newer::player.units[4]->cargo=true;CvStackingStrengthCache::Invalidate();}
static void nestBuild(){newer::statsCallback=NULL;newer::ParentStackPreparationView nested(*callbackParent);}
static DWORD WINAPI foreign(void*p){const newer::CvTacticalPosition*position=(const newer::CvTacticalPosition*)p;CvPlot plot(7);newer::ParentStackPreparationView view(*position);newer::VirtualFriendlyStackQuery q;newer::GetPreparedVirtualFriendlyStack(*position,&plot,NULL,0,q.candidates,q.damage,q.borrowed);return !q.borrowed&&!view.borrowed?0:1;}
int main(){
 expect("x86 production sizes",sizeof(void*)==4&&sizeof(int)==4&&sizeof(SUnitIDValueContainer::value_type)==8);
 CvUnit pool[24];for(int i=0;i<24;++i){pool[i].id=i+1;old::player.units[i+1]=newer::player.units[i+1]=&pool[i];}
 CvPlot plot(7),missing(9);
 for(int trial=0;trial<3500;++trial){reset();old::CvTacticalPosition o;newer::CvTacticalPosition n;
  for(int i=0;i<24;++i){pool[i].domain=next()%3;pool[i].combat=next()%5!=0;pool[i].cargo=next()%7==0;}
  preparePositions(o,n,pool,(int)(next()%23));plot.city=trial%3==0;plot.cityData.protection=next()%91;
  newer::ParentStackPreparationView view(n);
  for(int i=0;i<11;++i){CvUnit*u=&pool[next()%24];int hp=(int)(next()%250)-50;compareDanger(u,i%5==0?&missing:&plot,hp,o,n);}
  old::CvTacticalPosition oc;newer::CvTacticalPosition nc;old::STacticalAssignment oa;newer::STacticalAssignment na;
  oa.unitDamage.SetValue(0,17);na.unitDamage.SetValue(0,17);oa.unitDamage.SetValue(6,-7);na.unitDamage.SetValue(6,-7);oa.iDamagedCityId=na.iDamagedCityId=3;oa.iCityDamage=na.iCityDamage=26;
  old::GetNextPosition(o,&oa,oc);newer::GetNextPosition(n,&na,nc);
  expect("EFD child keeps exact first-match roster fields",nc.SharesVirtualStackInputs(n));expect("actual EFD preview damage unchanged",sameDamage(oc.GetUnitDamageDealt(),nc.GetUnitDamageDealt()));
  for(int i=0;i<5;++i)compareDanger(&pool[i],&plot,(int)(next()%101),oc,nc);
  expect("no additional native membership reads",newer::unitReads<=old::unitReads&&newer::statsReads<=old::statsReads);checkBytes();
 }
 // Explicit first-ID winner across available/unfinished/finished, duplicates, arrival overwrite.
 reset();for(int i=0;i<24;++i){pool[i].domain=0;pool[i].combat=true;pool[i].cargo=false;}
 old::CvTacticalPosition o;newer::CvTacticalPosition n;preparePositions(o,n,pool,0);
 o.tactPlots.write()[0].moving.push_back(old::STacticalUnit(4));n.tactPlots.write()[0].moving.push_back(newer::STacticalUnit(4));o.tactPlots.write()[0].moving.push_back(old::STacticalUnit(4));n.tactPlots.write()[0].moving.push_back(newer::STacticalUnit(4));
 o.availableUnits.write().push_back(old::SUnitStats(4,77));n.availableUnits.write().push_back(newer::SUnitStats(4,77));o.availableUnits.write().push_back(old::SUnitStats(4,18));n.availableUnits.write().push_back(newer::SUnitStats(4,18));o.finishedUnits.write().push_back(old::SUnitStats(4,9));n.finishedUnits.write().push_back(newer::SUnitStats(4,9));
 {newer::ParentStackPreparationView view(n);for(int i=0;i<8;++i)compareDanger(&pool[i],&plot,21,o,n);expect("repeat base roster resolves once",newer::virtualBuilds==1&&old::virtualBuilds==8);expect("first-match repeated reads removed",newer::statsReads==2&&old::statsReads==16);
  old::CvTacticalPosition oc;newer::CvTacticalPosition nc;old::STacticalAssignment oa;newer::STacticalAssignment na;old::GetNextPosition(o,&oa,oc);newer::GetNextPosition(n,&na,nc);compareDanger(&pool[0],&plot,21,oc,nc);expect("EFD-only child reuses base",newer::virtualBuilds==1);
  oc.availableUnits.write()[0].iSelfDamage=55;nc.availableUnits.write()[0].iSelfDamage=55;expect("roster-stat COW mutation rejects witness",!nc.SharesVirtualStackInputs(n));compareDanger(&pool[0],&plot,21,oc,nc);expect("changed child uses original builder",newer::virtualBuilds==2);
  old::CvTacticalPosition otherO;newer::CvTacticalPosition otherN;otherO.initFromParent(o);otherN.initFromParent(n);compareDanger(&pool[0],&plot,21,otherO,otherN);expect("unmarked child uses original builder",newer::virtualBuilds==3);
  {newer::ParentStackPreparationView nested(n);old::GetUnitDangerForPlot(&pool[0],&plot,21,o);newer::GetUnitDangerForPlot(&pool[0],&plot,21,n);expect("nested lexical scope permanently invalidates outer",view.disabled&&!nested.borrowed);}
  compareDanger(&pool[0],&plot,21,o,n);expect("after nested scope original builder",newer::virtualBuilds==5);
 }
 reset();{newer::ParentStackPreparationView view(n);compareDanger(&pool[0],&plot,21,o,n);++old::gStackForecastRevision;++newer::gStackForecastRevision;compareDanger(&pool[0],&plot,21,o,n);expect("revision invalidates view",view.disabled&&newer::virtualBuilds==2);}
 reset();{newer::ParentStackPreparationView view(n);compareDanger(&pool[0],&plot,21,o,n);bump();old::gStackForecastSceneEpoch=newer::gStackForecastSceneEpoch=CvStackingStrengthCache::SceneEpoch();compareDanger(&pool[0],&plot,21,o,n);expect("fresh scene drift invalidates before reuse",view.disabled&&newer::virtualBuilds==2);}
 reset();{newer::ParentStackPreparationView view(n);old::gStackVirtualScratchBusy=newer::gStackVirtualScratchBusy=true;for(int i=0;i<2;++i)compareDanger(&pool[0],&plot,21,o,n);expect("private busy loan cannot prepare",!view.borrowed&&newer::virtualBuilds==2);old::gStackVirtualScratchBusy=newer::gStackVirtualScratchBusy=false;}
 reset();{newer::ParentStackPreparationView view(n);old::active=newer::active=false;for(int i=0;i<2;++i)compareDanger(&pool[0],&plot,21,o,n);expect("off/foreign eligibility cannot prepare",!view.borrowed&&newer::virtualBuilds==2);}
 reset();{newer::ParentStackPreparationView view(n);old::player.danger.fixed=newer::player.danger.fixed=true;const int v[3]={0,42,INT_MAX};for(int i=0;i<3;++i){old::player.danger.fixedValue=newer::player.danger.fixedValue=v[i];compareDanger(&pool[0],&plot,21,o,n);}expect("fixed danger bypasses preparation",!view.borrowed&&newer::virtualBuilds==0);}
 reset();{newer::ParentStackPreparationView view(n);old::CvStacking::enabled=newer::CvStacking::enabled=false;compareDanger(&pool[0],&plot,21,o,n);expect("stacking-off bypass unchanged",!view.borrowed&&newer::virtualBuilds==0);}
 reset();{newer::ParentStackPreparationView view(n);old::MovementDestinationStackQuery oq;newer::MovementDestinationStackQuery nq;int a=old::GetUnitDangerForPlot(&pool[0],&plot,21,o,&oq),b=newer::GetUnitDangerForPlot(&pool[0],&plot,21,n,&nq);expect("destination danger exact",a==b);oq.Release();nq.Release();a=old::GetUnitDangerForPlot(&pool[1],&plot,22,o,&oq);b=newer::GetUnitDangerForPlot(&pool[1],&plot,22,n,&nq);expect("movement query rebuild uses prepared roster",a==b&&newer::virtualBuilds==1&&old::virtualBuilds==2);expect("movement admission gate counts identical",old::contextCalls==newer::contextCalls);}
 reset();{newer::ParentStackPreparationView view(n);HANDLE h=CreateThread(NULL,0,foreign,&n,0,NULL);expect("foreign thread created",h!=NULL);if(h){expect("foreign thread done",WaitForSingleObject(h,10000)==WAIT_OBJECT_0);DWORD r=1;GetExitCodeThread(h,&r);expect("foreign view cannot borrow owned storage",r==0);CloseHandle(h);}expect("foreign thread leaves parent optional storage idle",!view.borrowed&&!newer::gParentStackPreparationStorage.busy);}
 // No hard tactical cap: over metadata bound, old preparation still runs.
 reset();{newer::ParentStackPreparationView view(n);for(int i=0;i<260;++i){CvPlot p(100+i);compareDanger(&pool[0],&p,21,o,n);}expect("255 metadata cells then safe fallback",newer::gParentStackPreparationStorage.count==255&&newer::virtualBuilds==260);}
 reset();newer::ReleaseParentStackPreparationStorage();newer::gStackKeyPayloadLimit=0;{newer::ParentStackPreparationView view(n);compareDanger(&pool[0],&plot,21,o,n);expect("payload metadata exhaustion falls back",view.disabled&&newer::gParentStackPreparationStorage.count==0);}newer::gStackKeyPayloadLimit=624000;
 // Invalidation inside the first native base builder discards that cell/output.
 reset();newer::ReleaseParentStackPreparationStorage();pool[3].cargo=false;
 {newer::ParentStackPreparationView view(n);newer::VirtualFriendlyStackQuery q;newer::statsCallback=invalidateBuild;newer::GetPreparedVirtualFriendlyStack(n,&plot,NULL,0,q.candidates,q.damage,q.borrowed);vector<const CvUnit*>expected;SUnitIDValueContainer fd;old::GetVirtualFriendlyStack(o,&plot,NULL,0,expected,fd);expect("during-build scene change falls back to current roster",view.disabled&&newer::gParentStackPreparationStorage.count==0&&q.candidates==expected&&sameDamage(q.damage,fd));checkBytes();}
 reset();pool[3].cargo=false;newer::ReleaseParentStackPreparationStorage();callbackParent=&n;
 {newer::ParentStackPreparationView view(n);newer::VirtualFriendlyStackQuery q;newer::statsCallback=nestBuild;newer::GetPreparedVirtualFriendlyStack(n,&plot,NULL,0,q.candidates,q.damage,q.borrowed);expect("during-build nested view prevents publication",view.disabled&&newer::gParentStackPreparationStorage.count==0&&newer::virtualBuilds==2);checkBytes();}
 reset();newer::ReleaseParentStackPreparationStorage();
 {newer::ParentStackPreparationView view(n);newer::VirtualFriendlyStackQuery q;fixtureFailAllocation=0;newer::GetPreparedVirtualFriendlyStack(n,&plot,NULL,0,q.candidates,q.damage,q.borrowed);expect("optional first-base allocation failure retries original builder",view.disabled&&newer::gParentStackPreparationStorage.count==0&&newer::virtualBuilds==2&&q.candidates.size()==2&&q.damage.GetValue(4)==77);expect("allocation failure restores one-shot fault state",fixtureFailAllocation==-1);checkBytes();}
 reset();newer::ReleaseParentStackPreparationStorage();
 {newer::ParentStackPreparationView view(n);{newer::VirtualFriendlyStackQuery q;newer::GetPreparedVirtualFriendlyStack(n,&plot,NULL,0,q.candidates,q.damage,q.borrowed);}newer::VirtualFriendlyStackQuery q;vector<const CvUnit*>().swap(q.candidates);fixtureFailAllocation=0;newer::GetPreparedVirtualFriendlyStack(n,&plot,NULL,0,q.candidates,q.damage,q.borrowed);expect("copy-out allocation failure restores original full preparation",view.disabled&&q.candidates.size()==2&&q.damage.GetValue(4)==77&&newer::virtualBuilds==2);expect("copy allocation failure frees all optional retained payload before retry",newer::gParentStackPreparationStorage.RetainedBytes()==0&&newer::gParentStackPreparationStorage.count==0&&newer::gParentStackPreparationStorage.busy);checkBytes();}
 reset();try{newer::ParentStackPreparationView view(n);newer::VirtualFriendlyStackQuery q;newer::GetPreparedVirtualFriendlyStack(n,&plot,NULL,0,q.candidates,q.damage,q.borrowed);throw 19;}catch(int){}
 expect("exception unwinds TLS and scratch loans",newer::gParentStackPreparationView==NULL&&!newer::gParentStackPreparationStorage.busy&&!newer::gStackVirtualScratchBusy);checkBytes();
 newer::ReleaseParentStackPreparationStorage();expect("search teardown releases optional retained payload",newer::gParentStackPreparationStorage.RetainedBytes()==0&&!newer::gParentStackPreparationStorage.busy);
 printf("checks=%d failures=%d optionalMetadataBytes=%u maximumRetainedBytes=%u\n",checks,failures,(unsigned int)sizeof(newer::ParentStackPreparationStorage),(unsigned int)maximumRetained);return failures?1:0;
}
'''
fixture=prefix+container+build_namespace(old,hpp,'old')+build_namespace(new,newhpp,'newer')+tests
cpp=out/'test.cpp';cpp.write_text(fixture,encoding='utf-8',newline='\n')
proof={'baseline':BASE,'candidate_sha256':hashlib.sha256(new.encode()).hexdigest(),'fixture_sha256':hashlib.sha256(fixture.encode()).hexdigest(),'production_bound':args.production,'unchanged_dependency_hashes':dependency_hashes,'scope':'actual virtual/CoW/first-match/GetNextPosition/MovementQuery/GetUnitDanger/scalar/serialized-key bodies; deterministic native leaf and backend substitutes; no timings'}
(out/'proof.json').write_text(json.dumps(proof,indent=2)+'\n')
if args.emit_only:print(cpp);sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
compile_result=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(out/'test.exe')],cwd=out,env=env,capture_output=True,text=True,timeout=90)
(out/'compile.log').write_text(compile_result.stdout+compile_result.stderr)
if compile_result.returncode:print(compile_result.stdout+compile_result.stderr);sys.exit(compile_result.returncode)
run=subprocess.run([str(out/'test.exe')],cwd=out,capture_output=True,text=True,timeout=45);print(run.stdout+run.stderr,end='');proof.update(compile_returncode=compile_result.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr);(out/'result.json').write_text(json.dumps(proof,indent=2)+'\n');sys.exit(run.returncode)
