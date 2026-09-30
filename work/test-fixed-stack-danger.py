"""Compare fixed-source shortcut to actual full stack danger, using VC9 services."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/fixed-stack-danger-regression';out.mkdir(exist_ok=True)
text=(core/'CvDangerPlots.cpp').read_text(encoding='utf-8-sig')
def function(signature):
 start=text.index(signature);end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
actual='\n'.join(function(s) for s in ('bool CvDangerPlots::TryGetFixedStackDanger(', 'bool CvDangerPlotContents::TryGetFixedStackDanger(', 'int CvDangerPlotContents::GetStackDanger('))
prefix=r'''
#include <vector>
#include <map>
#include <utility>
#include <algorithm>
#include <cstdio>
#include <climits>
using namespace std;
#define FOG_DEFAULT_DANGER (1)
#define DOMAIN_AIR 2
struct CvUnit;struct CvCity;struct CvDangerPlotContents;
struct CvPlot{
 int index,terrain,feature;bool friendly;CvCity* city;
 CvPlot():index(0),terrain(17),feature(9),friendly(false),city(NULL){}
 int GetPlotIndex()const{return index;}bool isFriendlyCity(const CvUnit&)const{return friendly;}
 CvCity*getPlotCity()const{return city;}
 int getTurnDamage(bool t,bool f,int et,int ef)const{return (t?0:terrain+et)+(f?0:feature+ef);}
};
struct CvCity{int getOwner()const{return 0;}int getTeam()const{return 0;}int GetMaxHitPoints()const{return 300;}int getDamage()const{return 0;}int rangeCombatDamage(const CvUnit*,bool,const CvPlot*,bool,int)const{return 7;}};
struct CvUnit{
 bool t,f;int et,ef,id,owner;CvPlot* location;
 CvUnit():t(false),f(false),et(0),ef(0),id(3),owner(0),location(NULL){}
 bool ignoreTerrainDamage()const{return t;}bool ignoreFeatureDamage()const{return f;}
 int extraTerrainDamage()const{return et;}int extraFeatureDamage()const{return ef;}
 int GetID()const{return id;}int getOwner()const{return owner;}int getTeam()const{return owner;}
 int GetCurrHitPoints()const{return 80;}int GetMaxHitPoints()const{return 100;}
 bool isDelayedDeath()const{return false;}bool IsDead()const{return false;}CvPlot* plot()const{return location;}
 int getDomainType()const{return 0;}bool IsCanAttackRanged()const{return false;}int GetRange()const{return 1;}int getAoEDamageOnMove()const{return 0;}
};
struct SUnitIDValueContainer{map<int,int> values;int GetValue(int i)const{map<int,int>::const_iterator it=values.find(i);return it==values.end()?0:it->second;}void ChangeValue(int i,int v){values[i]+=v;}};
typedef vector<pair<int,int> >DangerUnitVector;typedef DangerUnitVector DangerCityVector;
struct CvDangerPlotContents{
 CvPlot*m_pPlot;DangerUnitVector m_apUnits;DangerCityVector m_apCities;int m_iImprovementDamage,m_iFogCount;bool m_bFlatPlotDamage;
 CvDangerPlotContents():m_pPlot(NULL),m_iImprovementDamage(0),m_iFogCount(0),m_bFlatPlotDamage(false){}
 bool TryGetFixedStackDanger(const CvUnit*,int&)const;
 int GetStackDanger(const CvUnit*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&);
};
struct CvDangerPlots{
 bool m_bDirty;vector<CvDangerPlotContents>m_DangerPlots;int updates;bool injectAttacker;
 CvDangerPlots():m_bDirty(false),updates(0),injectAttacker(false){}
 void UpdateDanger(){++updates;m_bDirty=false;if(injectAttacker&&!m_DangerPlots.empty())m_DangerPlots[0].m_apUnits.push_back(make_pair(1,4));}
 bool TryGetFixedStackDanger(const CvPlot&,const CvUnit*,int&);
};
struct Player{CvUnit* getUnit(int)const{return NULL;}CvCity*getCity(int)const{return NULL;}}player;
#define GET_PLAYER(owner) player
int plotDistance(const CvPlot&,const CvPlot&){return 1;}
int StackAirStrikeChance(const CvUnit*,const CvPlot*,int,const vector<const CvUnit*>&,const SUnitIDValueContainer&,int,SUnitIDValueContainer&){return 10000;}
int StackExpectedStrikeDamage(int hit,int){return hit;}
void SimulateStackCityThreats(const CvDangerPlotContents&,const CvCity*,const vector<const CvUnit*>&,SUnitIDValueContainer&,const SUnitIDValueContainer&,int,bool& fall){fall=false;}
namespace CvUnitCombat{
 const CvUnit*SelectStackDefender(const CvUnit*,const CvPlot*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,bool,int){return NULL;}
 const CvUnit*SelectStackDefenderForCity(const CvCity*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&){return NULL;}
 vector<pair<const CvUnit*,int> >GetStackCollateralDamage(const CvUnit*,const CvPlot*,const CvUnit*,int,const vector<const CvUnit*>&,const SUnitIDValueContainer&){return vector<pair<const CvUnit*,int> >();}
}
namespace TacticalAIHelpers{
 int GetSimulatedDamageFromAttackOnUnit(const CvUnit*,const CvUnit*,const CvPlot*,const CvPlot*,int&,bool,int,int,bool,bool){return 0;}
}
'''
tests=r'''
int checks=0,failures=0;void check(bool ok,const char*name){++checks;if(!ok){++failures;if(failures<10)printf("FAIL %s\n",name);}}
int main(){
 CvPlot plot;CvCity city;plot.city=&city;CvUnit unit,other;unit.location=&plot;other.location=&plot;
 CvDangerPlotContents contents;contents.m_pPlot=&plot;vector<const CvUnit*> candidates;candidates.push_back(&unit);candidates.push_back(&other);
 SUnitIDValueContainer friendly,enemy;int result=99;
 for(int i=0;i<30000;++i){
  unit.t=i%2==0;unit.f=i%3==0;unit.et=i%17;unit.ef=i%11;plot.terrain=i%39;plot.feature=i%23;plot.friendly=i%5==0;
  contents.m_iFogCount=i%7;contents.m_iImprovementDamage=i%31;contents.m_bFlatPlotDamage=i%4!=0;
  friendly.values[unit.GetID()]=i%125;enemy.values[-7]=i%300;enemy.values[11]=i%100;
  check(contents.TryGetFixedStackDanger(&unit,result),"empty sources accepted");
  check(result==contents.GetStackDanger(&unit,candidates,friendly,enemy),"actual full danger agrees across city/fog/improvement/terrain/HP states");
 }
 result=881;contents.m_apUnits.push_back(make_pair(1,7));check(!contents.TryGetFixedStackDanger(&unit,result)&&result==881,"unit source always bypasses shortcut");contents.m_apUnits.clear();
 contents.m_apCities.push_back(make_pair(1,7));check(!contents.TryGetFixedStackDanger(&unit,result),"city source always bypasses shortcut");contents.m_apCities.clear();
 check(!contents.TryGetFixedStackDanger(NULL,result),"null unit bypasses");contents.m_pPlot=NULL;check(!contents.TryGetFixedStackDanger(&unit,result),"missing plot bypasses");contents.m_pPlot=&plot;
 CvDangerPlots cache;cache.m_DangerPlots.push_back(contents);cache.m_bDirty=true;
 check(cache.TryGetFixedStackDanger(plot,&unit,result)&&cache.updates==1&&!cache.m_bDirty,"dirty danger refreshed before shortcut");
 cache.injectAttacker=true;cache.m_bDirty=true;check(!cache.TryGetFixedStackDanger(plot,&unit,result)&&cache.updates==2,"dirty refresh discovers new source");
 cache.m_DangerPlots[0].m_apUnits.clear();plot.index=-1;check(!cache.TryGetFixedStackDanger(plot,&unit,result),"negative index rejected");plot.index=1;check(!cache.TryGetFixedStackDanger(plot,&unit,result),"out of range rejected");plot.index=0;check(!cache.TryGetFixedStackDanger(plot,NULL,result),"wrapper null rejected");cache.m_DangerPlots.clear();check(!cache.TryGetFixedStackDanger(plot,&unit,result),"empty danger map rejected");
 printf("fixed stack danger actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
cpp=out/'test.cpp';cpp.write_text(prefix+actual+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=out/'test.exe';c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/'compile.log').write_text(c.stdout+c.stderr)
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='');(out/'result.json').write_text(json.dumps(dict(actual_source_sha256=hashlib.sha256(actual.encode()).hexdigest(),returncode=r.returncode,output=r.stdout+r.stderr,scope='Actual fixed shortcut/wrapper and full danger body, deterministic engine services. Only no-known-attack cases compared; attack-source cases ensure bypass.'),indent=2));sys.exit(r.returncode)
