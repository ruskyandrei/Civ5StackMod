"""Check actual virtual-stack storage/count code against the deployed DLL35 source."""
from pathlib import Path
from plan_sample_fixture import without_plan_sample_probes
import hashlib,json,os,subprocess,sys

root=Path(__file__).resolve().parents[1]
out=root/'work/virtual-stack-regression';out.mkdir(exist_ok=True)
source=root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp';raw=source.read_bytes()
text=raw.decode('utf-8-sig').replace('\r\n','\n')
text = without_plan_sample_probes(text)
unit=(root/'CvGameCoreDLL_Expansion2/CvUnit.h').read_text(encoding='utf-8-sig')
container=unit[unit.index('struct SUnitIDValueContainer\n'):unit.index('\nnamespace std {',unit.index('struct SUnitIDValueContainer\n'))]
cache=text[text.index('struct StackForecastKey\n'):text.index('static int GetCachedStackDanger(')]
builder=text[text.index('static void GetVirtualFriendlyStack('):text.index('// A same-tile escort counts only')]
danger=text[text.index('static int GetCachedStackDanger('):text.index('static const CvUnit* SelectCachedStackDefender(')]
unit_danger=text[text.index('static int GetUnitDangerForPlot('):text.index('static unsigned char GetStackAttackThreatFlags(')]
stack_score=text[text.index('static unsigned char GetStackAttackThreatFlags('):text.index('// what is the rough state looking like after this assignment')]
previous_score=subprocess.check_output(['git','show','c0e19fcb3:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
previous_score=previous_score[previous_score.index('static int ScoreStackPosition('):previous_score.index('// what is the rough state looking like after this assignment')].replace('ScoreStackPosition','OriginalStackScore')
prior=subprocess.check_output(['git','show','91054ec4c:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
reference=prior[prior.index('static void GetVirtualFriendlyStack('):prior.index('// A same-tile escort counts only')].replace('GetVirtualFriendlyStack','OriginalVirtualStack')

prefix=r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#define NOMINMAX
#include <windows.h>
#include <algorithm>
#include <cstdio>
#include <vector>
#include <deque>
#include <unordered_map>
#include <map>
#include <cstddef>
#include <cstdlib>
#include <climits>
#include <new>
#include <cstring>
static size_t allocationCalls=0;
template<class T>struct CountingAllocator:std::allocator<T>{
 typedef typename std::allocator<T>::pointer pointer;typedef typename std::allocator<T>::size_type size_type;
 template<class U>struct rebind{typedef CountingAllocator<U> other;};
 CountingAllocator(){}template<class U>CountingAllocator(const CountingAllocator<U>&){}
 pointer allocate(size_type n,const void* hint=0){++allocationCalls;return std::allocator<T>::allocate(n,hint);}
};
template<class T,class U>bool operator==(const CountingAllocator<T>&,const CountingAllocator<U>&){return true;}
template<class T,class U>bool operator!=(const CountingAllocator<T>&,const CountingAllocator<U>&){return false;}
using namespace std;
namespace CvStackingStrengthCache {volatile LONG fixtureEpoch=1;long SceneEpoch(){return InterlockedCompareExchange(&fixtureEpoch,0,0);}void Invalidate(){InterlockedIncrement(&fixtureEpoch);}}
typedef int PlayerTypes;typedef int TeamTypes;
const int NO_PLAYER=-1;
#define MOD_EVENTS_CAN_MOVE_INTO false
const int DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_AIR=2;
struct CvCity{int protection;CvCity():protection(0){}};
struct CvPlot{
 int index;bool city,embark;CvCity cityData;CvPlot(int i=0):index(i),city(false),embark(false){}
 int GetPlotIndex()const{return index;}bool isCity()const{return city;}bool isFriendlyCity(const struct CvUnit&)const{return city;}
 const CvCity* getPlotCity()const{return city?&cityData:NULL;}
 bool needsEmbarkation(const struct CvUnit*)const{return embark;}
};
struct CvUnit{
 int id,domain,owner;bool combat,cargo,ranged,anti,flank,dead,delayed;int hp,maxHP,collateral;
 CvUnit(int n=0):id(n),domain(DOMAIN_LAND),owner(0),combat(true),cargo(false),ranged(false),anti(false),flank(false),dead(false),delayed(false),hp(100),maxHP(100),collateral(0){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getTeam()const{return owner;}
 bool IsCombatUnit()const{return combat;}bool isCargo()const{return cargo;}
 int getDomainType()const{return domain;}int GetMaxHitPoints()const{return maxHP;}
 int GetCurrHitPoints()const{return hp;}bool IsCanAttackRanged()const{return ranged;}
 int GetDanger(const CvPlot*,const struct SUnitIDValueContainer&,int)const{return 87;}
};
'''
engine=r'''
struct SUnitStats{int iSelfDamage;SUnitStats(int d=0):iSelfDamage(d){}};
struct STacticalUnit{int iUnitID;STacticalUnit(int id=0):iUnitID(id){}};
static unsigned int statsReads=0;
struct CvTacticalPlot{
 vector<const CvUnit*> fixed;vector<STacticalUnit> moving;
 const vector<const CvUnit*>& getFixedFriendlyUnits()const{return fixed;}
 const vector<STacticalUnit>& getUnitsAtPlot()const{return moving;}
};
struct CvTacticalPosition{
 CvTacticalPlot tactical;bool present;map<int,SUnitStats> stats;SUnitIDValueContainer enemyDamage;
 CvTacticalPosition():present(true){}
 const CvTacticalPlot* getTactPlot(int)const{return present?&tactical:NULL;}
 int getPlayer()const{return 0;}
 const SUnitStats* GetUnitStats(int id)const{++statsReads;map<int,SUnitStats>::const_iterator i=stats.find(id);return i==stats.end()?NULL:&i->second;}
 const SUnitIDValueContainer& GetUnitDamageDealt()const{return enemyDamage;}
};
struct CvDangerPlots{
 // Outcome behavior is checked separately with actual damage math services.
 bool IsDirty()const{return false;}
 bool GetStackDangerOutcome(const CvPlot&,const CvUnit*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&,SUnitIDValueContainer&,bool&,int&){return false;}
 bool TryGetStackDangerFromOutcome(const CvPlot&,const CvUnit*,const SUnitIDValueContainer&,const SUnitIDValueContainer&,bool,int&){return false;}
 bool fixed,dynamicLeaf;int fixedValue,leafValue,leafCalls;void(*leafCallback)();
 CvDangerPlots():fixed(false),dynamicLeaf(false),fixedValue(0),leafValue(73),leafCalls(0),leafCallback(NULL){}
 bool TryGetFixedStackDanger(const CvPlot&,const CvUnit*,int&result){if(!fixed)return false;result=fixedValue;return true;}
 const vector<int>*GetStackDangerDamageIDs(const CvPlot&){return NULL;}
 int GetStackDanger(const CvPlot&,const CvUnit* unit,const vector<const CvUnit*>&members,const SUnitIDValueContainer&friendly,const SUnitIDValueContainer&enemy){++leafCalls;if(leafCallback)leafCallback();return dynamicLeaf?max(0,leafValue-(int)members.size()*11+friendly.GetValue(unit->GetID())-enemy.GetValue(-1)/5):leafValue;}
};
struct Player{
 map<int,CvUnit*> units;CvDangerPlots danger;vector<CvUnit*> attackers;int attackerReads;void(*attackerCallback)();Player():attackerReads(0),attackerCallback(NULL){}
 const CvUnit* getUnit(int id)const{map<int,CvUnit*>::const_iterator i=units.find(id);return i==units.end()?NULL:i->second;}
 CvDangerPlots* GetDangerPlots(){return &danger;}
 vector<CvUnit*> GetPossibleAttackers(const CvPlot&,int){++attackerReads;if(attackerCallback)attackerCallback();vector<CvUnit*> result;for(size_t i=0;i<attackers.size();++i)if(attackers[i]&&!attackers[i]->delayed&&!attackers[i]->dead)result.push_back(attackers[i]);return result;}
}player;
#define GET_PLAYER(id) player
static const int NO_TEAM=-1;
static int flankReads=0,collateralReads=0,antiReads=0;
struct CvStacking{
 static bool enabled;static int collateralPercent;static bool IsEnabled(){return enabled;}
 static int GetInt(const char* name,int v){return !strcmp(name,"CollateralPercent")?collateralPercent:v;}
 static int GetCityProtection(const CvCity* city){return city?city->protection:0;}
 static bool CanFlank(const CvUnit*unit){++flankReads;return enabled&&unit&&unit->flank;}
 static int GetCollateralTargetLimit(const CvUnit*unit){++collateralReads;return enabled&&unit?unit->collateral:0;}
 static bool IsAntiCavalry(const CvUnit*unit){++antiReads;return enabled&&unit&&unit->anti;}
 static bool IsCollateralTargetDomain(int domain){return domain==DOMAIN_LAND;}
};bool CvStacking::enabled=true;int CvStacking::collateralPercent=20;
static bool StackPreferencesEnabled(){return CvStacking::enabled;}
struct DummyDangerCache{
 bool findDanger(int,int,int,const SUnitIDValueContainer&,int&)const{return false;}
 void storeDanger(int,int,int,const SUnitIDValueContainer&,int){}
};
struct Storage{DummyDangerCache cache;int getSizeLimit()const{return 6000;}DummyDangerCache&getDangerCache(){return cache;}}gTactPosStorage;
const int TACTSIM_MAX_UNITS=13;
'''
suffix=r'''
static int checks=0,failures=0;
static void expect(const char*name,bool ok){++checks;if(!ok){++failures;if(failures<30)printf("FAIL %s\n",name);}}
static unsigned int seed=71577;
static unsigned int next(){seed=seed*1664525u+1013904223u;return seed;}
static bool sameDamage(const SUnitIDValueContainer&a,const SUnitIDValueContainer&b){for(int id=-3;id<48;++id)if(a.GetValue(id)!=b.GetValue(id))return false;return true;}
static void invalidateCallback(){CvStackingStrengthCache::Invalidate();}
static void nestedLeafCallback(){player.danger.leafCallback=NULL;StackForecastScope nested;}
static void nestedThreatCallback(){player.attackerCallback=NULL;StackForecastScope nested;}
static DWORD WINAPI foreignThreat(void* context){const CvPlot*plot=(const CvPlot*)context;StackForecastScope scope;return GetStackAttackThreatFlags(player.units[1],plot)==3&&!scope.owned?0:1;}
int main(){
 expect("production32bit",sizeof(void*)==4&&sizeof(size_t)==4);
 CvUnit pool[24];for(int i=0;i<24;++i){pool[i].id=i+1;player.units[i+1]=&pool[i];}
 CvPlot plot(1);
 {StackForecastScope scope;
  for(int trial=0;trial<18000;++trial){
   CvTacticalPosition pos;pos.present=trial%11!=0;
   for(int i=0;i<24;++i){pool[i].domain=(int)(next()%3);pool[i].combat=next()%3!=0;pool[i].cargo=next()%5==0;pool[i].hp=(int)(next()%101);if(next()%4)pos.stats[i+1]=SUnitStats((int)(next()%180)-40);}
   unsigned int n=next()%14;for(unsigned int i=0;i<n;++i){unsigned int id=next()%26;pos.tactical.fixed.push_back(id<24?&pool[id]:NULL);}
   n=next()%19;for(unsigned int i=0;i<n;++i)pos.tactical.moving.push_back(STacticalUnit((int)(next()%31)));
   const CvUnit* arriving=trial%7==0?NULL:&pool[next()%24];int damage=(int)(next()%180)-40;
   vector<const CvUnit*> original;SUnitIDValueContainer originalDamage;OriginalVirtualStack(pos,&plot,arriving,damage,original,originalDamage);
   VirtualFriendlyStackQuery query;GetVirtualFriendlyStack(pos,&plot,arriving,damage,query.candidates,query.damage);
   expect("membership order and duplicates matchDLL35",query.candidates==original);
   expect("exact HP states and missing stats matchDLL35",sameDamage(query.damage,originalDamage));
   size_t before=allocationCalls;unsigned int reads=statsReads;size_t count=CountVirtualFriendlyStack(pos,&plot,arriving);
   expect("count matchesDLL35 size including fixed/movable duplicates",count==original.size());
   expect("count allocates nothing and reads no HP state",allocationCalls==before&&statsReads==reads);
  }
 }
 expect("outer scope releases virtual scratch",gStackVirtualScratch.candidates.capacity()==0&&gStackVirtualScratch.damage.m_aExtraStorage.capacity()==0&&!gStackVirtualScratchBusy);
 {StackForecastScope scope;CvTacticalPosition pos;pos.tactical.fixed.push_back(&pool[1]);pos.tactical.moving.push_back(STacticalUnit(3));pos.stats[3]=SUnitStats(17);
  VirtualFriendlyStackQuery outer;GetVirtualFriendlyStack(pos,&plot,&pool[1],23,outer.candidates,outer.damage);
  vector<const CvUnit*> saved=outer.candidates;SUnitIDValueContainer savedDamage=outer.damage;
  {VirtualFriendlyStackQuery nested;GetVirtualFriendlyStack(pos,&plot,&pool[4],-2,nested.candidates,nested.damage);expect("nested callback uses private storage",!nested.borrowed&&outer.candidates==saved&&sameDamage(outer.damage,savedDamage));}
  {StackForecastScope nestedScope;VirtualFriendlyStackQuery nested;expect("nested search uses private storage",!nested.borrowed&&!gStackForecastsActive);}
  expect("borrow remains owned through callback",gStackVirtualScratchBusy&&outer.candidates==saved&&sameDamage(outer.damage,savedDamage));
 }
 {VirtualFriendlyStackQuery query;expect("outside search private storage",!query.borrowed&&!gStackVirtualScratchBusy);}
 {StackForecastScope scope;CvTacticalPosition pos;for(int i=0;i<16;++i){pool[i].combat=true;pool[i].cargo=false;pool[i].domain=DOMAIN_LAND;pos.stats[i+1]=SUnitStats(i*7);if(i<8)pos.tactical.fixed.push_back(&pool[i]);else pos.tactical.moving.push_back(STacticalUnit(i+1));}
  size_t reused=0,old=0,countAllocs=0;
  for(int i=0;i<20000;++i){size_t before=allocationCalls;{VirtualFriendlyStackQuery query;GetVirtualFriendlyStack(pos,&plot,&pool[0],i%130,query.candidates,query.damage);}reused+=allocationCalls-before;
   before=allocationCalls;vector<const CvUnit*> original;SUnitIDValueContainer originalDamage;OriginalVirtualStack(pos,&plot,&pool[0],i%130,original,originalDamage);old+=allocationCalls-before;
   before=allocationCalls;size_t count=CountVirtualFriendlyStack(pos,&plot,&pool[0]);countAllocs+=allocationCalls-before;expect("count stable through changed arriving damage",count==16);
  }
  expect("reused storage allocation bounded after warmup",reused<30);expect("reference allocation measured",old>=100000);expect("exactcount allocationfree",countAllocs==0);
  printf("virtual stack allocation control: reused %u vsDLL35 %u across20000queries; count %u. Not a game-speed benchmark.\n",(unsigned int)reused,(unsigned int)old,(unsigned int)countAllocs);
 }
 {StackForecastScope scope;CvTacticalPosition pos;pool[0].combat=true;pool[0].domain=DOMAIN_LAND;vector<const CvUnit*> members(1,&pool[0]);SUnitIDValueContainer noDamage;
  player.danger.fixed=true;int values[3]={0,27,INT_MAX};for(int i=0;i<3;++i){player.danger.fixedValue=values[i];int calls=player.danger.leafCalls;
   expect("fixed danger bypasses key and leaf",GetCachedStackDanger(&pool[0],&plot,members,noDamage,noDamage)==values[i]&&player.danger.leafCalls==calls&&gStackDangerForecasts.empty());
   size_t before=allocationCalls;unsigned int reads=statsReads;int expected=values[i]==INT_MAX?1000:values[i];
   expect("fixed plot bypasses virtual stack and keeps sentinel conversion",GetUnitDangerForPlot(&pool[0],&plot,91,pos)==expected&&allocationCalls==before&&statsReads==reads);
  }
  player.danger.fixed=false;int calls=player.danger.leafCalls;expect("threatened plot retains leaf",GetCachedStackDanger(&pool[0],&plot,members,noDamage,noDamage)==73&&player.danger.leafCalls==calls+1);
  expect("threatened plot retains exact cache",GetCachedStackDanger(&pool[0],&plot,members,noDamage,noDamage)==73&&player.danger.leafCalls==calls+1);
  CvStacking::enabled=false;player.danger.fixed=true;calls=player.danger.leafCalls;expect("stacking disabled fixed shortcut bypass remains unchanged",GetCachedStackDanger(&pool[0],&plot,members,noDamage,noDamage)==73&&player.danger.leafCalls==calls); // existing exact cache serves the call
  CvStacking::enabled=true;
 }
 expect("all scratch storage released",gStackVirtualScratch.candidates.capacity()==0&&gStackVirtualScratch.damage.m_aExtraStorage.capacity()==0&&!gStackVirtualScratchBusy);
 {StackForecastScope scope;vector<const CvUnit*> members(1,&pool[0]);SUnitIDValueContainer noDamage;player.danger.fixed=false;
  player.danger.leafCallback=invalidateCallback;int calls=player.danger.leafCalls;
  expect("changed scene still returns uncached result",GetCachedStackDanger(&pool[0],&plot,members,noDamage,noDamage)==73);
  expect("in-flight epoch change prevents cache admission",gStackDangerForecasts.empty());GetCachedStackDanger(&pool[0],&plot,members,noDamage,noDamage);
  expect("epoch-changing callback computes each time",player.danger.leafCalls==calls+2&&gStackDangerForecasts.empty());
  player.danger.leafCallback=nestedLeafCallback;GetCachedStackDanger(&pool[0],&plot,members,noDamage,noDamage);
  expect("nested search cancels in-flight forecast admission",gStackDangerForecasts.empty()&&StackForecastContext());
  GetCachedStackDanger(&pool[0],&plot,members,noDamage,noDamage);expect("next stable forecast admitted",!gStackDangerForecasts.empty());
 }
 {StackForecastScope scope;player.attackers.clear();CvUnit flank(80),siege(81),dead(82),delayed(83);flank.flank=true;siege.collateral=3;dead.dead=true;dead.flank=true;dead.collateral=5;delayed.delayed=true;delayed.flank=true;delayed.collateral=5;
  player.attackers.push_back(&dead);player.attackers.push_back(&delayed);player.attackers.push_back(NULL);player.attackers.push_back(&flank);player.attackers.push_back(&siege);
  int reads=player.attackerReads;
  expect("combined flags keep native dead/delayed eligibility",GetStackAttackThreatFlags(&pool[0],&plot)==3);
  expect("same live scene reuses bounded threat memo",GetStackAttackThreatFlags(&pool[0],&plot)==3&&player.attackerReads==reads+1);
  pool[0].owner=1;GetStackAttackThreatFlags(&pool[0],&plot);expect("owner participates in threat key",player.attackerReads==reads+2);pool[0].owner=0;
  player.attackerCallback=invalidateCallback;CvStackingStrengthCache::Invalidate();reads=player.attackerReads;GetStackAttackThreatFlags(&pool[0],&plot);GetStackAttackThreatFlags(&pool[0],&plot);
  expect("changing epoch during threat read prevents admission",player.attackerReads==reads+2&&gStackThreatFlags.empty());player.attackerCallback=NULL;
  player.attackerCallback=nestedThreatCallback;GetStackAttackThreatFlags(&pool[0],&plot);expect("nested callback prevents threat admission",gStackThreatFlags.empty());
  GetStackAttackThreatFlags(&pool[0],&plot);expect("stable callback aftermath can memoize",gStackThreatFlags.size()==1);
  size_t entries=gStackThreatFlags.size();HANDLE thread=CreateThread(NULL,0,foreignThreat,&plot,0,NULL);expect("foreign threat thread created",thread!=NULL);
  if(thread){expect("foreign threat thread completes",WaitForSingleObject(thread,10000)==WAIT_OBJECT_0);DWORD result=~0u;GetExitCodeThread(thread,&result);expect("foreign thread computes without owning cache",result==0);CloseHandle(thread);}
  expect("foreign thread leaves main threat memo unchanged",gStackThreatFlags.size()==entries);
  InvalidateStackForecastScene();gStackEntryLimit=3;for(int i=0;i<20;++i){CvPlot candidate(i+20);expect("uncached overflow flags remain exact",GetStackAttackThreatFlags(&pool[0],&candidate)==3);}
  expect("threat memo cannot exceed shared search entry limit",gStackThreatFlags.size()==3);
 }
 {StackForecastScope scope;CvUnit attackers[5];player.attackers.clear();for(int i=0;i<5;++i){attackers[i].id=80+i;player.attackers.push_back(&attackers[i]);}
  player.danger.dynamicLeaf=true;
  for(int trial=0;trial<16000;++trial){
   CvStackingStrengthCache::Invalidate();CvStacking::collateralPercent=trial%9==0?0:20;
   for(int i=0;i<5;++i){attackers[i].flank=next()%3==0;attackers[i].collateral=next()%4;attackers[i].dead=next()%7==0;attackers[i].delayed=next()%11==0;}
   CvTacticalPosition position;position.enemyDamage.SetValue(-1,(int)(next()%200));
   for(int i=0;i<4;++i){pool[i].domain=(int)(next()%3);pool[i].hp=(int)(next()%101);pool[i].maxHP=100+(int)(next()%50);pool[i].cargo=next()%7==0;pool[i].ranged=next()%2!=0;pool[i].anti=next()%3==0;pool[i].combat=true;position.stats[i+1]=SUnitStats((int)(next()%180)-40);if(i<2)position.tactical.fixed.push_back(&pool[i]);else position.tactical.moving.push_back(STacticalUnit(i+1));}
   CvUnit* unit=&pool[trial%4];int wounds=(int)(next()%180)-40;plot.city=next()%2!=0;plot.cityData.protection=(int)(next()%91);plot.embark=next()%5==0;
   const int expected=OriginalStackScore(unit,&plot,wounds,position);
   const int actual=ScoreStackPosition(unit,&plot,wounds,position);expect("full score matches DLL38 across virtual HP/domain/roles/fortification",actual==expected);
   int reads=player.attackerReads;expect("repeated full score remains exact",ScoreStackPosition(unit,&plot,wounds,position)==expected);
   expect("repeat score reuses threat or skips singletons",player.attackerReads==reads);
  }
  player.danger.dynamicLeaf=false;CvStacking::collateralPercent=20;
  CvStackingStrengthCache::Invalidate();CvTacticalPosition singleton;singleton.present=false;int reads=player.attackerReads;
  expect("singleton score avoids threat read",ScoreStackPosition(&pool[0],&plot,0,singleton)==0&&player.attackerReads==reads);
  player.danger.fixed=true;singleton.present=true;singleton.tactical.fixed.push_back(&pool[0]);singleton.tactical.fixed.push_back(&pool[1]);
  expect("fixed-danger score avoids threat read",ScoreStackPosition(&pool[0],&plot,0,singleton)==0&&player.attackerReads==reads);player.danger.fixed=false;player.attackers.clear();
 }
 printf("virtual stack source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
fixture=prefix+container+engine+cache+builder+reference+danger+unit_danger+stack_score+previous_score+suffix
fixture=fixture.replace('std::vector<value_type>','std::vector<value_type, CountingAllocator<value_type> >')
fixture=fixture.replace('vector<const CvUnit*>','vector<const CvUnit*, CountingAllocator<const CvUnit*> >')
cpp=out/'virtual-stack-source-test.cpp';cpp.write_text(fixture,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'virtual-stack-source-test.exe'
compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'virtual-stack-source-test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=30);print(run.stdout+run.stderr,end='')
result=dict(source_file_sha256=hashlib.sha256(raw).hexdigest().upper(),fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest().upper(),compile_returncode=compiled.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr,scope='actual container/cache/scratch/builders and danger wrappers extracted with engine stubs; DLL35 reference; native32bitVC9 production iterators; no DLLbuild or game run')
(out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');sys.exit(run.returncode)
