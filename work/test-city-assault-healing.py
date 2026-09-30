"""Regression for blockade handling in the two approximate assault-healing forecasts."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/city-assault-healing-regression';out.mkdir(exist_ok=True)
offensive=(core/'CvStackingOffensiveAI.cpp').read_text(encoding='utf-8-sig')
tactical=(core/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
city=(core/'CvCity.cpp').read_text(encoding='utf-8-sig')
def forecast(text,kind):
 if kind=='offensive':
  a=text.index('int healing=',text.index('AssaultPlan AssessAssault('));b=text.index('const bool captureSoon=',a)
  return 'static int offensiveForecast(CvCity*city){\n'+text[a:b]+'return healing;\n}\n'
 a=text.index('int iCityHealRate =',text.index('void CvTacticalAI::ExecuteCaptureCityMoves('));b=text.index('//assume the city heals each turn',a)
 return 'static int tacticalForecast(CvCity*pCity){\n'+text[a:b]+'return iCityHealRate;\n}\n'
a=city.index('if (getDamage() > 0 && !IsBlockadedWaterAndLand())');b=city.index('{',a)+1;depth=1
while depth:depth+=(city[b]=='{')-(city[b]=='}');b+=1
native='void CvCity::nativeHeal(){\n'+city[a:b]+'\n}\n'
prefix=r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <cstdio>
#include <algorithm>
using namespace std;
static bool vp=true;
static int baseHeal=8,buildingReads=0,processReads=0,populationReads=0;
#define MOD_BALANCE_VP vp
#define GD_INT_GET(x) baseHeal
const int NO_PROCESS=-1,YIELD_PRODUCTION=0;
struct CvCityBuildings{
 int defense,modifier;CvCityBuildings():defense(0),modifier(0){}
 int GetBuildingDefense()const{++buildingReads;return defense;}
 int GetBuildingDefenseMod()const{return modifier;}
};
struct Citizens{bool blockaded;Citizens():blockaded(true){}bool AnyPlotBlockaded()const{return blockaded;}};
struct CvProcessInfo{
 int value,perTurn,cap;CvProcessInfo():value(100),perTurn(20),cap(150){}
 int getDefenseValue()const{return value;}int getDefenseValuePerTurn()const{return perTurn;}int getDefenseValueCap()const{return cap;}
};
struct Globals{CvProcessInfo process;CvProcessInfo*getProcessInfo(int){++processReads;return &process;}}GC;
struct CvCity{
 bool blockaded;int population,damage,lastDamage,process,processTurns,production,healed;
 CvCityBuildings buildings;CvCityBuildings*m_pCityBuildings;Citizens citizens;
 CvCity():blockaded(false),population(20),damage(1000),lastDamage(10),process(NO_PROCESS),processTurns(0),production(1000),healed(0),m_pCityBuildings(&buildings){}
 bool IsBlockadedWaterAndLand()const{return blockaded;}int getDamage()const{return damage;}
 int getPopulation()const{++populationReads;return population;}int getDamageTakenLastTurn()const{return lastDamage;}
 Citizens*GetCityCitizens(){return &citizens;}int getProductionProcess()const{return process;}
 int GetDefenseProcessTurns()const{return processTurns;}int getYieldRateTimes100(int)const{return production;}
 void changeDamage(int amount){damage+=amount;healed-=amount;}void nativeHeal();
};
'''
tests=r'''
static int checks=0,failures=0;static void expect(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<12)printf("FAIL %s\n",n);}}
int main(){
 int pops[4]={0,1,20,1000000},bases[3]={0,8,20};
 for(int v=0;v<2;++v)for(int b=0;b<3;++b)for(int p=0;p<4;++p)for(int blocked=0;blocked<2;++blocked){
  vp=v!=0;baseHeal=bases[b];CvCity city;city.blockaded=blocked!=0;city.population=pops[p];int wanted=blocked?0:baseHeal+(vp?city.population:0);
  populationReads=0;int assault=offensiveForecast(&city);expect("offensive forecast exact blockade/base/pop approximation",assault==wanted);expect("blockaded assault never reads population bonus",!blocked||populationReads==0);
  populationReads=0;int tactical=tacticalForecast(&city);expect("tactical forecast exact blockade/base/pop approximation",tactical==wanted);expect("blockaded tactical never reads population bonus",!blocked||populationReads==0);
  buildingReads=processReads=populationReads=0;city.nativeHeal();expect("native outerguard agrees when ordinary optional heals absent",city.healed==wanted);
  expect("native blockade skips buildings process and population",!blocked||(buildingReads==0&&processReads==0&&populationReads==0));
 }
 for(int v=0;v<2;++v){vp=v!=0;baseHeal=v?8:20;CvCity city;city.blockaded=true;city.population=1000000;city.buildings.defense=90000;city.buildings.modifier=50;city.process=0;city.processTurns=9;city.production=100000;city.lastDamage=0;city.citizens.blockaded=false;
  buildingReads=processReads=populationReads=0;city.nativeHeal();expect("native blocked city skips every optional healing source",city.healed==0&&buildingReads==0&&processReads==0&&populationReads==0);
  expect("both blocked forecasts remain zero with huge optional heals",offensiveForecast(&city)==0&&tacticalForecast(&city)==0);
 }
 {vp=true;baseHeal=8;CvCity city;city.buildings.defense=3000;city.process=0;city.lastDamage=0;city.citizens.blockaded=false;city.nativeHeal();
  expect("ordinary nonblockaded forecasts deliberately remain basepluspopulation",offensiveForecast(&city)==28&&tacticalForecast(&city)==28);
  expect("building quiettriple and defenseprocess approximation deferred",city.healed>28);
 }
 printf("city assault healing actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
def compile_run(label,off,tac):
 actual=forecast(off,'offensive')+forecast(tac,'tactical')+native
 fixture=prefix+actual+tests;cpp=out/(label+'.cpp');cpp.write_text(fixture,encoding='utf-8');exe=out/(label+'.exe')
 c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/(label+'.obj')),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
 (out/(label+'-compile.log')).write_text(c.stdout+c.stderr,encoding='utf-8')
 if c.returncode:print(c.stdout+c.stderr);raise SystemExit(c.returncode)
 r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);(out/(label+'-output.log')).write_text(r.stdout+r.stderr,encoding='utf-8')
 return r,actual
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
r,actual=compile_run('current',offensive,tactical);print(r.stdout+r.stderr,end='')
before_off=subprocess.check_output(['git','show','ca5bf974d:CvGameCoreDLL_Expansion2/CvStackingOffensiveAI.cpp'],cwd=root).decode('utf-8-sig')
before_tac=subprocess.check_output(['git','show','ca5bf974d:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
control,_=compile_run('control',before_off,before_tac);print('Pre-fix healing control rejected as expected' if control.returncode else 'FAIL pre-fix healing unexpectedly passed')
result_code=r.returncode or (0 if control.returncode else 1)
(out/'result.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(actual.encode()).hexdigest(),returncode=result_code,output=r.stdout+r.stderr,control_commit='ca5bf974d',control_returncode=control.returncode,control_output=control.stdout+control.stderr,scope='Actual two AI forecast statements and actual CvCity healing outer branch; deterministic building/process/citizen services; VP on/off, huge population, blockade excludes all optional heals. Ordinary unblocked forecast remains basepluspopulation approximation, with buildings/process/quiettriple deferred. No DLLbuild/game launch.'),indent=2),encoding='utf-8');sys.exit(result_code)
