"""Actual rule, city eligibility, unit eligibility and danger registration functions."""
from pathlib import Path
import hashlib, json, os, subprocess, sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/city-bombardment-regression';out.mkdir(exist_ok=True)
def function(file,signature):
    s=(core/file).read_text(encoding='utf-8-sig');a=s.index(signature);end=s.index('{',a)+1;depth=1
    while depth:depth+=(s[end]=='{')-(s[end]=='}');end+=1
    return s[a:end]
parts=[function('CvStackingRules.cpp','bool CityRangedAttacksEnabled()').replace('bool CityRangedAttacksEnabled()','bool CvStacking::CityRangedAttacksEnabled()'),
       function('CvCity.cpp','bool CvCity::canRangeStrike() const'),function('CvUnit.cpp','bool CvUnit::canRangeStrike() const'),
       function('CvDangerPlots.cpp','void CvDangerPlots::AssignCityDangerValue(')]
fixture=r'''
#include <vector>
#include <utility>
#include <cstdio>
using namespace std;
#define VALIDATE_OBJECT()
bool enabled=true,disableCity=true,stockDisable=false;
#define MOD_BALANCE_NO_CITY_RANGED_ATTACK stockDisable
namespace CvStacking{bool IsEnabled(){return enabled;}int GetInt(const char*,int){return disableCity;}bool CityRangedAttacksEnabled();}
struct CvPlot{int GetPlotIndex()const{return 0;}} plot;
struct CvCity{bool resistance,razing;int sapped,damage;CvCity():resistance(false),razing(false),sapped(0),damage(0){}bool IsResistance()const{return resistance;}bool IsRazing()const{return razing;}int GetSappedTurns()const{return sapped;}int getDamage()const{return damage;}int GetMaxHitPoints()const{return 300;}int GetID()const{return 7;}int getOwner()const{return 1;}bool canRangeStrike()const;};
struct CvUnit{bool embarked,native,out,canEnd;int range,strength;CvUnit():embarked(false),native(true),out(false),canEnd(true),range(2),strength(20){}bool isEmbarked()const{return embarked;}int GetRange()const{return range;}int GetBaseRangedCombatStrength()const{return strength;}bool isOutOfAttacks()const{return out;}const CvPlot*plot()const{return &::plot;}bool isNativeDomain(const CvPlot*)const{return native;}bool canEndTurnAtPlot(const CvPlot*)const{return canEnd;}bool canRangeStrike()const;};
struct Danger{vector<pair<int,int> >m_apCities;};
struct CvDangerPlots{vector<Danger>m_DangerPlots;CvDangerPlots():m_DangerPlots(1){}void AssignCityDangerValue(const CvCity*,CvPlot*);};
int checks=0,failures=0;void check(bool ok,const char*n){++checks;if(!ok){++failures;printf("FAIL: %s\n",n);}}
'''
tests=r'''
int main(){CvCity city;CvUnit unit;CvDangerPlots danger;
 check(!city.canRangeStrike(),"default stacking rules remove city ranged attack");check(unit.canRangeStrike(),"ordinary ranged unit retains fire while city bombardment disabled");
 danger.AssignCityDangerValue(&city,&plot);check(danger.m_DangerPlots[0].m_apCities.empty(),"disabled city fire not registered as future ranged danger");
 disableCity=false;check(city.canRangeStrike(),"XML toggle restores native city ranged eligibility");danger.AssignCityDangerValue(&city,&plot);check(danger.m_DangerPlots[0].m_apCities.size()==1,"enabled city fire restored to danger map");
 city.resistance=true;check(!city.canRangeStrike(),"resistance still prevents city fire");city.resistance=false;city.razing=true;check(!city.canRangeStrike(),"razing still prevents city fire");city.razing=false;
 city.sapped=1;check(!city.canRangeStrike(),"sapped city cannot fire");city.sapped=0;city.damage=300;check(!city.canRangeStrike(),"zero-health city cannot fire");city.damage=0;
 stockDisable=true;check(!city.canRangeStrike(),"independent VP disable remains authoritative");stockDisable=false;enabled=false;disableCity=true;check(city.canRangeStrike(),"disabled stacking delegates native city behavior");
 enabled=true;unit.native=false;check(!unit.canRangeStrike(),"native-domain restriction for docked ships remains");unit.native=true;unit.embarked=true;check(!unit.canRangeStrike(),"embarked ranged unit remains ineligible");unit.embarked=false;unit.out=true;check(!unit.canRangeStrike(),"unit attack limits remain intact");
 printf("city bombardment toggle: %d checks, %d failures\n",checks,failures);return failures?1:0;}
'''
actual='\n'.join(parts);cpp=out/'test.cpp';cpp.write_text(fixture+actual+tests)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe';c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],env=env,cwd=out,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr)
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],capture_output=True,text=True,timeout=20);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps({'returncode':r.returncode,'output':r.stdout+r.stderr,'actual_functions_sha256':hashlib.sha256(actual.encode()).hexdigest(),'scope':'Actual eligibility and registration functions with deterministic engine state; no live UI, map/pathfinder or balance claim.'},indent=2))
sys.exit(r.returncode)
