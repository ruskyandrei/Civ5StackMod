"""Compare actual selectors to the preserved DLL29 selector across deterministic states."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root/'work/defender-fastpath-regression'
out.mkdir(exist_ok=True)
source = (root/'CvGameCoreDLL_Expansion2/CvUnitCombat.cpp').read_text(encoding='utf-8-sig')
start = source.index('static bool IsStackCombatCandidate(')
end = source.index('struct StackCollateralOrder', start)
actual = source[start:end]
reference_path = root/'work/perf-reference-selectors.cpp'
reference = reference_path.read_text().replace('CvUnitCombat::','ReferenceCombat::').replace('IsStackCombatCandidate','ReferenceCandidate').replace('GetStackExchange','ReferenceExchange')
prefix = r'''
#include <vector>
#include <map>
#include <algorithm>
#include <climits>
#include <cstdio>
using namespace std;
typedef __int64 int64;
enum {DOMAIN_LAND,DOMAIN_AIR,DOMAIN_SEA,FEATURE_ICE=3};
bool MOD_GLOBAL_SUBS_UNDER_ICE_IMMUNITY=false;
int mathCalls=0;
struct CvUnit;struct CvCity;
struct CvPlot {int feature;CvPlot():feature(0){}int getFeatureType()const{return feature;}};
struct SUnitIDValueContainer {map<int,int>d;int GetValue(int id)const{return d.count(id)?d.find(id)->second:0;}};
struct CvUnit {
 int id,owner,hp,maxHP,domain,attack,defense,invisibleType;bool defend,cargo,dead,delayed,flank,target,anti,invisible;CvPlot*position;
 CvUnit(int n=0):id(n),owner(1),hp(100),maxHP(100),domain(DOMAIN_LAND),attack(30),defense(25),invisibleType(-1),defend(true),cargo(false),dead(false),delayed(false),flank(false),target(false),anti(false),invisible(false),position(NULL){}
 bool IsCanDefend()const{return defend;}bool isCargo()const{return cargo;}int getDomainType()const{return domain;}bool IsDead()const{return dead;}bool isDelayedDeath()const{return delayed;}
 int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{return maxHP;}int GetID()const{return id;}int getOwner()const{return owner;}CvPlot*plot()const{return position;}
 bool isBetterDefenderThan(const CvUnit*u,const CvUnit*)const{return !u||defense>u->defense;}
 bool isEnemy(int team,const CvPlot*)const{return owner!=team;}bool isInvisible(int,bool)const{return invisible;}int getInvisibleType()const{return invisibleType;}
 int GetRangeCombatDamage(const CvUnit*d,const CvCity*,int,int&,bool,int extra,int other,const CvPlot*,const CvPlot*,bool,bool)const{++mathCalls;return max(0,attack-extra/5-d->defense/2+other/4);}
 int GetAirStrikeDefenseDamage(const CvUnit*,bool,const CvPlot*)const{++mathCalls;return defense/3;}
 int GetMaxAttackStrength(const CvPlot*,const CvPlot*,const CvUnit*,bool,bool,int extra,int)const{++mathCalls;return max(1,attack-extra/5);}
 int GetMaxDefenseStrength(const CvPlot*,const CvUnit*,const CvPlot*,bool,bool,int extra)const{++mathCalls;return max(1,defense-extra/5);}
 int getMeleeCombatDamage(int a,int d,int&ret,bool,const CvUnit*,int,int)const{++mathCalls;ret=max(0,d-a/2);return max(0,a-d/2);}
};
struct CvCity {int team,hit;CvCity():team(0),hit(30){}int getTeam()const{return team;}int rangeCombatDamage(const CvUnit*u,bool,const CvPlot*,bool,int extra)const{++mathCalls;return max(0,hit-u->defense/3+extra/4);}};
namespace CvStacking {bool enabled=true,selection=true;bool IsEnabled(){return enabled;}int GetInt(const char*,int){return selection;}bool CanFlank(const CvUnit*u){return u->flank;}bool IsFlankTarget(const CvUnit*u){return u->target;}bool IsAntiCavalry(const CvUnit*u){return u->anti;}}
struct CvUnitCombat {static const CvUnit*SelectStackDefender(const CvUnit*,const CvPlot*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,bool,int);static const CvUnit*SelectStackDefenderForCity(const CvCity*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&);};
struct ReferenceCombat {static const CvUnit*SelectStackDefender(const CvUnit*,const CvPlot*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,bool,int);static const CvUnit*SelectStackDefenderForCity(const CvCity*,const CvPlot*,const vector<const CvUnit*>&,const SUnitIDValueContainer&);};
'''
suffix = r'''
unsigned int seed=0x741123;unsigned int nextRandom(){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
int main(){int checks=0,failures=0;CvPlot plot;CvUnit attacker(99);attacker.owner=0;attacker.position=&plot;CvCity city;SUnitIDValueContainer damage;
 for(int n=0;n<20000;++n){CvUnit units[8];vector<const CvUnit*> candidates;damage.d.clear();CvStacking::enabled=nextRandom()%2;CvStacking::selection=nextRandom()%2;MOD_GLOBAL_SUBS_UNDER_ICE_IMMUNITY=nextRandom()%2;plot.feature=nextRandom()%4;attacker.domain=nextRandom()%3;attacker.flank=nextRandom()%2;attacker.attack=10+nextRandom()%120;attacker.hp=1+nextRandom()%120;
  int count=nextRandom()%9;for(int i=0;i<count;++i){CvUnit&u=units[i];u=CvUnit(i+1);u.owner=nextRandom()%3;u.hp=nextRandom()%140;u.maxHP=100+nextRandom()%40;u.domain=nextRandom()%3;u.defend=nextRandom()%6!=0;u.cargo=nextRandom()%7==0;u.dead=nextRandom()%8==0;u.delayed=nextRandom()%9==0;u.defense=5+nextRandom()%100;u.target=nextRandom()%2;u.anti=nextRandom()%3==0;u.invisible=nextRandom()%5==0;u.invisibleType=nextRandom()%3-1;damage.d[u.id]=nextRandom()%80;candidates.push_back(&u);}
  if(nextRandom()%5==0)candidates.push_back(NULL);if(nextRandom()%5==0)candidates.push_back(&attacker);
  bool ranged=nextRandom()%2;int extra=nextRandom()%60;
  const CvUnit*a=CvUnitCombat::SelectStackDefender(&attacker,NULL,&plot,candidates,damage,ranged,extra);const CvUnit*b=ReferenceCombat::SelectStackDefender(&attacker,NULL,&plot,candidates,damage,ranged,extra);++checks;if(a!=b){++failures;printf("unit mismatch %d\n",n);}
  a=CvUnitCombat::SelectStackDefenderForCity(&city,&plot,candidates,damage);b=ReferenceCombat::SelectStackDefenderForCity(&city,&plot,candidates,damage);++checks;if(a!=b){++failures;printf("city mismatch %d\n",n);}
 }
 CvStacking::enabled=CvStacking::selection=true;CvUnit only(1);vector<const CvUnit*> candidates(1,&only);damage.d.clear();attacker.domain=DOMAIN_LAND;attacker.flank=false;
 mathCalls=0;const CvUnit*a=CvUnitCombat::SelectStackDefender(&attacker,NULL,&plot,candidates,damage,false,0);int fastCalls=mathCalls;mathCalls=0;const CvUnit*b=ReferenceCombat::SelectStackDefender(&attacker,NULL,&plot,candidates,damage,false,0);++checks;if(a!=b||fastCalls!=0||mathCalls==0)++failures;
 printf("defender fast path: %d checks, %d failures; sole-defender leaf calculations %d versus %d\n",checks,failures,fastCalls,mathCalls);return failures?1:0;
}
'''
cpp=out/'test.cpp'
cpp.write_text(prefix+reference+actual+suffix)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include')
env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe'
c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr)
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30)
print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(returncode=r.returncode,output=r.stdout+r.stderr,actual_sha256=hashlib.sha256(actual.encode()).hexdigest(),reference_sha256=hashlib.sha256(reference_path.read_bytes()).hexdigest(),scope='Actual source versus preserved DLL29 source; deterministic leaf combat services, not full-game timing proof.'),indent=2))
sys.exit(r.returncode)
