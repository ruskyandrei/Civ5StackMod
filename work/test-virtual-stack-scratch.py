"""Check actual virtual-stack storage/count code against the deployed DLL35 source."""
from pathlib import Path
import hashlib,json,os,subprocess,sys

root=Path(__file__).resolve().parents[1]
out=root/'work/virtual-stack-regression';out.mkdir(exist_ok=True)
source=root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp';raw=source.read_bytes()
text=raw.decode('utf-8-sig').replace('\r\n','\n')
unit=(root/'CvGameCoreDLL_Expansion2/CvUnit.h').read_text(encoding='utf-8-sig')
container=unit[unit.index('struct SUnitIDValueContainer\n'):unit.index('\nnamespace std {',unit.index('struct SUnitIDValueContainer\n'))]
cache=text[text.index('struct StackForecastKey\n'):text.index('static int GetCachedStackDanger(')]
builder=text[text.index('static void GetVirtualFriendlyStack('):text.index('// A same-tile escort counts only')]
danger=text[text.index('static int GetCachedStackDanger('):text.index('static const CvUnit* SelectCachedStackDefender(')]
unit_danger=text[text.index('static int GetUnitDangerForPlot('):text.index('// Value actual protection and its cost')]
prior=subprocess.check_output(['git','show','91054ec4c:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
reference=prior[prior.index('static void GetVirtualFriendlyStack('):prior.index('// A same-tile escort counts only')].replace('GetVirtualFriendlyStack','OriginalVirtualStack')

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
#include <climits>
#include <new>
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
const int DOMAIN_LAND=0,DOMAIN_SEA=1,DOMAIN_AIR=2;
struct CvCity{};
struct CvPlot{
 int index;bool city;CvPlot(int i=0):index(i),city(false){}
 int GetPlotIndex()const{return index;}bool isCity()const{return city;}
 const CvCity* getPlotCity()const{return NULL;}
};
struct CvUnit{
 int id,domain;bool combat,cargo;int hp;
 CvUnit(int n=0):id(n),domain(DOMAIN_LAND),combat(true),cargo(false),hp(100){}
 int GetID()const{return id;}int getOwner()const{return 0;}
 bool IsCombatUnit()const{return combat;}bool isCargo()const{return cargo;}
 int getDomainType()const{return domain;}int GetMaxHitPoints()const{return 100;}
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
 bool fixed;int fixedValue,leafValue,leafCalls;
 CvDangerPlots():fixed(false),fixedValue(0),leafValue(73),leafCalls(0){}
 bool TryGetFixedStackDanger(const CvPlot&,const CvUnit*,int&result){if(!fixed)return false;result=fixedValue;return true;}
 int GetStackDanger(const CvPlot&,const CvUnit*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&){++leafCalls;return leafValue;}
};
struct Player{
 map<int,CvUnit*> units;CvDangerPlots danger;
 const CvUnit* getUnit(int id)const{map<int,CvUnit*>::const_iterator i=units.find(id);return i==units.end()?NULL:i->second;}
 CvDangerPlots* GetDangerPlots(){return &danger;}
}player;
#define GET_PLAYER(id) player
struct CvStacking{
 static bool enabled;static bool IsEnabled(){return enabled;}
 static int GetInt(const char*,int v){return v;}
 static int GetCityProtection(const CvCity*){return 0;}
};bool CvStacking::enabled=true;
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
 printf("virtual stack source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
fixture=prefix+container+engine+cache+builder+reference+danger+unit_danger+suffix
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
