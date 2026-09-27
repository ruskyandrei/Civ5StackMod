"""Compile actual placement predicate and production-AI block with deterministic stubs.
This is a work-only executable, not a VP DLL build or live production test.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1]
work=root/'work/production-regression';work.mkdir(exist_ok=True)
city=(root/'CvGameCoreDLL_Expansion2/CvCity.cpp').read_text(encoding='utf-8-sig')
ai=(root/'CvGameCoreDLL_Expansion2/CvUnitProductionAI.cpp').read_text(encoding='utf-8-sig')
plot_source=(root/'CvGameCoreDLL_Expansion2/CvPlot.cpp').read_text(encoding='utf-8-sig')
plot_start=plot_source.index('bool CvPlot::canPlaceCombatUnit(')
plot_end=plot_source.index('\nbool CvPlot::IsCivilization',plot_start)
plot_predicate=plot_source[plot_start:plot_end]
start=city.index('bool CvCity::IsValidPlotForUnitType(')
end=city.index('\nCvPlot* CvCity::GetPlotForNewUnit',start)
predicate=city[start:end]
start=ai.index('\t//don\'t build land/sea units if there\'s no place to put them')
end=ai.index('\n\tint iNumExplorers',start)
ai_block=ai[start:end]
prefix=r'''
#include <vector>
#include <cstdio>
using namespace std;
typedef int PlayerTypes;typedef int TeamTypes;enum {NO_PLAYER=-1};
enum DomainTypes {NO_DOMAIN=-1,DOMAIN_IMMOBILE,DOMAIN_AIR,DOMAIN_LAND,DOMAIN_SEA,DOMAIN_HOVER};
struct CvUnit {int owner;DomainTypes domain;bool combat,delayed,cargo,support;CvUnit(int o=0,DomainTypes d=DOMAIN_LAND):owner(o),domain(d),combat(true),delayed(false),cargo(false),support(false){} int getOwner()const{return owner;} int getTeam()const;DomainTypes getDomainType()const{return domain;}bool IsCombatUnit()const{return combat;}bool isDelayedDeath()const{return delayed;}bool isCargo()const{return cargo;}bool IsStackingUnit()const{return support;}};
struct CvPlayer {int team;int getTeam()const{return team;}};
struct CvTeam {bool wars[4];bool isAtWar(int t)const{return wars[t];}bool isMinorCiv()const{return false;}bool IsAllowsOpenBordersToTeam(int)const{return true;}};
static CvPlayer players[4];static CvTeam teams[4];
#define GET_PLAYER(x) players[x]
#define GET_TEAM(x) teams[x]
int CvUnit::getTeam()const{return players[owner].team;}
struct IDInfo {CvUnit* unit;IDInfo(CvUnit*u):unit(u){}};
CvUnit* GetPlayerUnit(const IDInfo&i){return i.unit;}
struct CvUnitEntry {DomainTypes domain;int combat;CvUnitEntry(DomainTypes d=DOMAIN_LAND,int c=10):domain(d),combat(c){}DomainTypes GetDomainType()const{return domain;}int GetCombat()const{return combat;}};
struct CvPlotCity {int owner;CvPlotCity():owner(0){}int getOwner()const{return owner;}};
struct CvPlot {bool valid,water,city,harbor;int owner;CvPlotCity cityData;vector<IDInfo> units;CvPlot():valid(true),water(false),city(false),harbor(false),owner(-1){}bool isValidMovePlot(int)const{return valid;}bool isCity()const{return city;}bool isWater()const{return water;}bool isCoastalCityOrPassableImprovement(int,bool,bool)const{return harbor;}const IDInfo*headUnitNode()const{return units.empty()?NULL:&units[0];}const IDInfo*nextUnitNode(const IDInfo*p)const{size_t i=p-&units[0]+1;return i<units.size()?&units[i]:NULL;}int GetNumCombatUnits()const{int n=0;for(size_t i=0;i<units.size();++i)if(units[i].unit->combat)++n;return n;}void add(CvUnit&u){units.push_back(IDInfo(&u));}int getOwner()const{return owner;}DomainTypes getDomain()const{return water?DOMAIN_SEA:DOMAIN_LAND;}int getUnitLimit()const{return 1;}const CvPlotCity*getPlotCity()const{return &cityData;}bool canPlaceCombatUnit(PlayerTypes)const;};
namespace CvStacking {static bool enabled=true;static int caps[4][5];static int cityBonus=0;bool IsEnabled(){return enabled;}int GetCapacity(int owner,DomainTypes domain,bool city){return caps[owner][domain]+(city?cityBonus:0);}}
struct CvCity {CvPlot*center;int owner;bool garrison;CvCity(CvPlot*p,int o=0):center(p),owner(o),garrison(true){}CvPlot*plot()const{return center;}int getOwner()const{return owner;}bool HasGarrison()const{return garrison;}static bool IsValidPlotForUnitType(CvPlot*,PlayerTypes,CvUnitEntry*);};
static vector<CvPlot*> ring;
enum {RING0_PLOTS=0,RING3_PLOTS=4,SR_IMPOSSIBLE=-1};
static CvPlot*iterateRingPlots(CvPlot*,int i){return i<(int)ring.size()?ring[i]:NULL;}
'''
wrapper='\nstatic int ProductionGate(CvCity* m_pCity,CvUnitEntry*pkUnitEntry,bool bCombat=true){\n'+ai_block+'\nreturn 0;\n}\n'
tests=r'''
static int checks=0,failures=0;
static void expect(const char*name,int actual,int expected){++checks;if(actual!=expected){++failures;printf("FAIL %s actual=%d expected=%d\n",name,actual,expected);}}
struct Fixture {CvPlot p;CvUnitEntry land,sea,air,civilian;CvUnit a,b,foreign,enemy,ship;CvCity city;
 Fixture():land(DOMAIN_LAND),sea(DOMAIN_SEA),air(DOMAIN_AIR,0),civilian(DOMAIN_LAND,0),a(0),b(0),foreign(1),enemy(2),ship(0,DOMAIN_SEA),city(&p){for(int i=0;i<4;++i){players[i].team=i;for(int j=0;j<4;++j)teams[i].wars[j]=false;for(int d=0;d<5;++d)CvStacking::caps[i][d]=2;}teams[0].wars[2]=teams[2].wars[0]=true;CvStacking::enabled=true;CvStacking::cityBonus=0;ring.assign(4,NULL);ring[0]=&p;}
 bool valid(CvUnitEntry*e=NULL){return CvCity::IsValidPlotForUnitType(&p,0,e?e:&land);}int gate(CvUnitEntry*e=NULL){return ProductionGate(&city,e?e:&land);}
};
int main(){
 {Fixture f;expect("empty land",f.valid(),1);f.p.add(f.a);expect("partially occupied own stack",f.valid(),1);expect("AI accepts a free own slot",f.gate(),0);f.p.add(f.b);expect("full own stack",f.valid(),0);expect("AI rejects all-full plots",f.gate(),SR_IMPOSSIBLE);}
 for(int cap=2;cap<=10;++cap){Fixture f;CvStacking::caps[0][DOMAIN_LAND]=cap;vector<CvUnit> units(cap,CvUnit());for(int i=0;i<cap-1;++i)f.p.add(units[i]);expect("cap range last free slot",f.valid(),1);f.p.add(units[cap-1]);expect("cap range full",f.valid(),0);}
 {Fixture f;f.p.add(f.foreign);expect("friendly foreign ordinary combat rejected",f.valid(),0);expect("AI rejects foreign stack",f.gate(),SR_IMPOSSIBLE);players[1].team=0;expect("same team other owner rejected",f.valid(),0);}
 {Fixture f;f.p.add(f.enemy);expect("enemy combat cannot be displaced by production",f.valid(),0);expect("AI rejects hostile stack",f.gate(),SR_IMPOSSIBLE);}
 {Fixture f;f.p.water=true;f.enemy.domain=DOMAIN_LAND;f.p.add(f.enemy);expect("sea production excludes enemy embarked land",f.valid(&f.sea),0);}
 {Fixture f;f.p.city=f.p.harbor=true;f.enemy.domain=DOMAIN_SEA;f.p.add(f.enemy);expect("land production excludes hostile harbor ship",f.valid(),0);}
 {Fixture f;f.p.water=true;f.p.add(f.a);f.p.add(f.b);expect("own embarked land does not consume sea slots",f.valid(&f.sea),1);f.p.units.clear();f.foreign.domain=DOMAIN_LAND;f.p.add(f.foreign);expect("friendly foreign different-domain policy retained",f.valid(&f.sea),1);}
 {Fixture f;f.p.city=f.p.harbor=true;f.p.add(f.a);f.p.add(f.b);expect("land-filled harbor still accepts sea",f.valid(&f.sea),1);expect("AI recognizes harbor sea slot",f.gate(&f.sea),0);}
 {Fixture f;f.p.add(f.a);f.p.add(f.b);CvStacking::cityBonus=1;expect("field has no city bonus",f.valid(),0);f.p.city=true;expect("city capacity uses bonus",f.valid(),1);}
 {Fixture f;f.p.add(f.a);f.p.add(f.b);CvStacking::caps[1][DOMAIN_LAND]=10;expect("other owner's cap does not grant slots",f.valid(),0);CvStacking::caps[0][DOMAIN_SEA]=10;expect("other domain cap does not grant slots",f.valid(),0);}
 {Fixture f;f.p.add(f.a);f.foreign.cargo=true;f.p.add(f.foreign);expect("cargo excluded",f.valid(),1);f.foreign.cargo=false;f.foreign.delayed=true;expect("delayed death excluded",f.valid(),1);f.foreign.delayed=false;f.foreign.support=true;expect("special stacking support excluded",f.valid(),1);f.foreign.support=false;f.foreign.combat=false;expect("civilian occupant excluded",f.valid(),1);}
 {Fixture f;f.p.add(f.a);f.p.add(f.b);expect("civilian production remains separately allowed",f.valid(&f.civilian),1);expect("air cannot spawn outside city",f.valid(&f.air),0);f.p.city=true;expect("air city capacity remains separate",f.valid(&f.air),1);}
 {Fixture f;f.p.valid=false;expect("impassable retained",f.valid(),0);expect("AI impassable retained",f.gate(),SR_IMPOSSIBLE);f.p.valid=true;f.p.water=true;expect("land cannot be produced embarked",f.valid(),0);f.p.water=false;expect("sea cannot be produced inland",f.valid(&f.sea),0);f.p.harbor=true;expect("passable improvement sea placement retained",f.valid(&f.sea),1);}
 {Fixture f;f.p.add(f.a);f.p.add(f.b);CvPlot edge;edge.add(f.a);ring[3]=&edge;expect("AI retains radius-three availability search",f.gate(),0);}
 {Fixture f;CvStacking::enabled=false;CvStacking::caps[0][DOMAIN_LAND]=10;f.p.add(f.a);expect("disabled placement remains one unit",f.valid(),0);expect("disabled AI keeps empty-plot rule",f.gate(),SR_IMPOSSIBLE);f.p.units.clear();expect("disabled empty land accepted",f.gate(),0);f.p.city=f.p.harbor=true;expect("disabled AI harbor behavior unchanged",f.gate(&f.sea),SR_IMPOSSIBLE);}
 {Fixture f;CvStacking::enabled=false;f.p.water=true;f.p.add(f.enemy);expect("disabled cross-domain legacy predicate unchanged",f.valid(&f.sea),1);}
 {Fixture f;f.p.add(f.a);f.p.add(f.b);f.city.garrison=false;expect("ungarrisoned AI outer gate unchanged",f.gate(),0);f.city.garrison=true;expect("air AI outer gate unchanged",f.gate(&f.air),0);}

 {Fixture f;expect("generic empty plot",f.p.canPlaceCombatUnit(0),1);f.p.add(f.a);expect("generic own free slot",f.p.canPlaceCombatUnit(0),1);f.p.add(f.b);expect("generic own full slot",f.p.canPlaceCombatUnit(0),0);}
 {Fixture f;f.p.add(f.foreign);expect("generic foreign same-domain rejected",f.p.canPlaceCombatUnit(0),0);players[1].team=0;expect("generic same-team foreign owner rejected",f.p.canPlaceCombatUnit(0),0);}
 {Fixture f;f.p.add(f.ship);f.ship.owner=1;expect("generic friendly other-domain unchanged",f.p.canPlaceCombatUnit(0),1);f.ship.owner=2;expect("generic hostile other-domain still rejected",f.p.canPlaceCombatUnit(0),0);}
 {Fixture f;f.p.add(f.foreign);f.foreign.cargo=true;expect("generic cargo still ignored",f.p.canPlaceCombatUnit(0),1);f.foreign.cargo=false;f.foreign.support=true;expect("generic special stacker still ignored",f.p.canPlaceCombatUnit(0),1);f.foreign.support=false;f.foreign.combat=false;expect("generic civilian still ignored",f.p.canPlaceCombatUnit(0),1);f.foreign.combat=true;f.foreign.delayed=true;expect("generic delayed unit still ignored",f.p.canPlaceCombatUnit(0),1);}
 {Fixture f;CvStacking::enabled=false;f.p.add(f.a);expect("generic disabled occupied remains blocked",f.p.canPlaceCombatUnit(0),0);f.p.units.clear();expect("generic disabled empty remains allowed",f.p.canPlaceCombatUnit(0),1);}
 {Fixture f;expect("generic no-player empty fallback",f.p.canPlaceCombatUnit(NO_PLAYER),1);f.p.add(f.a);expect("generic no-player legacy limit",f.p.canPlaceCombatUnit(NO_PLAYER),0);}
 {Fixture f;f.p.city=true;f.p.cityData.owner=1;expect("generic foreign city remains blocked",f.p.canPlaceCombatUnit(0),0);}
 printf("production placement regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
actual=predicate+plot_predicate+wrapper
cpp=work/'production-source-test.cpp';cpp.write_text(prefix+actual+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
inc=root/'work/toolchain/sdk/vc9/include';lib=root/'work/toolchain/sdk/vc9/lib';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
env['INCLUDE']=str(inc)+';'+str(sdk/'Include');env['LIB']=str(lib)+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=work/'production-source-test.exe'
cmd=[str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/Od','/Z7',str(cpp),'/Fo'+str(work/'production-source-test.obj'),'/Fe'+str(exe)]
compiled=subprocess.run(cmd,cwd=work,env=env,capture_output=True,text=True)
(work/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
run=subprocess.run([str(exe)],cwd=work,env=env,capture_output=True,text=True)
print(run.stdout+run.stderr,end='')
result={'source_sha256':{'CvCity.cpp':hashlib.sha256(city.encode()).hexdigest().upper(),'CvUnitProductionAI.cpp':hashlib.sha256(ai.encode()).hexdigest().upper(),'CvPlot.cpp':hashlib.sha256(plot_source.encode()).hexdigest().upper()},'extracted_sha256':hashlib.sha256(actual.encode()).hexdigest().upper(),'compile_returncode':compiled.returncode,'test_returncode':run.returncode,'output':run.stdout+run.stderr,'scope':'actual extracted city/plot predicates and AI availability block with deterministic engine stubs; no VP DLL build or live production proof'}
(work/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
sys.exit(run.returncode)
