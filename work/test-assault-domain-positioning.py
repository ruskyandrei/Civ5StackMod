"""Compile the actual mixed-domain gathering dispatcher with VC9 services."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
core = root / 'CvGameCoreDLL_Expansion2'
out = root / 'work/assault-domain-positioning-regression'
out.mkdir(exist_ok=True)
source = (core / 'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
start = source.index('bool CvTacticalAI::StageGatheringCityAssault(')
end = source.index('{', start) + 1
depth = 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
actual = source[start:end]
position_start = source.index('bool CvTacticalAI::PositionUnitsAroundTarget(')
position_end = source.index('\nvoid CvTacticalAI::ExecuteLandingOperation(', position_start)
position = source[position_start:position_end]
assert 'StageGatheringCityAssault(unitIDs,pTarget)' in position
assert 'return bTactSimSuccess || gathering;' in position
assert 'if(vUnits.empty()) return gathering;' in position

fixture = r'''
#include <algorithm>
#include <map>
#include <vector>
#include <cstdio>
using namespace std;
const int DOMAIN_LAND=2,DOMAIN_SEA=0,DOMAIN_AIR=1;
struct CvCity {} city;
struct CvPlot {
 bool enemy;CvPlot():enemy(true){}
 bool isCity()const{return enemy;}int getOwner()const{return enemy?1:0;}
 CvCity*getPlotCity()const{return &city;}
} target;
struct CvUnit {
 int id,owner,domain,danger;bool combat,dead,available;
 CvUnit(int i,int d):id(i),owner(0),domain(d),danger(0),combat(true),dead(false),available(true){}
 int getOwner()const{return owner;}int getDomainType()const{return domain;}
 bool IsCombatUnit()const{return combat;}bool isDelayedDeath()const{return dead;}
 bool canUseNow()const{return available&&!dead;}int GetDanger()const{return danger;}
};
struct CvPlayer {
 map<int,CvUnit*>units;int GetID()const{return 0;}bool IsAtWarWith(int p)const{return p==1;}
 CvUnit*getUnit(int id){map<int,CvUnit*>::iterator i=units.find(id);return i==units.end()?NULL:i->second;}
} player;
map<int,bool> readiness;map<int,int> assessments;vector<int> staged,safety;
bool stageOK=true;int removeOnStage=-1;
namespace CvStackingOffensiveAI {
 struct AssaultPlan{bool ready;};
 AssaultPlan AssessAssault(int,CvCity*,int domain){++assessments[domain];AssaultPlan p;p.ready=readiness[domain];return p;}
 bool StageUnit(CvUnit*u,const CvPlot*){staged.push_back(u->id);if(removeOnStage>=0)player.units.erase(removeOnStage);return stageOK;}
}
struct CvTacticalAI {
 CvPlayer*m_pPlayer;CvTacticalAI():m_pPlayer(&player){}
 bool StageGatheringCityAssault(vector<int>&,CvPlot*);
 void ExecuteMovesToSafestPlot(CvUnit*u){safety.push_back(u->id);}
};
int checks=0,failures=0;
void check(bool ok,const char*name){++checks;if(!ok){++failures;printf("FAIL: %s\n",name);}}
void reset(){player.units.clear();readiness.clear();assessments.clear();staged.clear();safety.clear();stageOK=true;removeOnStage=-1;target=CvPlot();}
void put(CvUnit&u){player.units[u.id]=&u;}
'''
tests = r'''
int main(){CvTacticalAI tactical;
 for(int order=0;order<2;++order){reset();CvUnit land(1,DOMAIN_LAND),sea(2,DOMAIN_SEA),air(3,DOMAIN_AIR),civilian(4,DOMAIN_LAND);civilian.combat=false;put(land);put(sea);put(air);put(civilian);
  readiness[DOMAIN_LAND]=false;readiness[DOMAIN_SEA]=true;
  vector<int>ids;ids.push_back(order?2:1);ids.push_back(order?1:2);ids.push_back(3);ids.push_back(4);
  check(tactical.StageGatheringCityAssault(ids,&target),"incomplete land assault is handled");
  check(ids.size()==3&&ids[0]==2&&ids[1]==3&&ids[2]==4,"ready fleet and ordinary air/civilian handling survive either input order");
  check(staged.size()==1&&staged[0]==1&&safety.empty(),"only gathering domain is staged");
  check(assessments[DOMAIN_LAND]==1&&assessments[DOMAIN_SEA]==1&&assessments[DOMAIN_AIR]==0,"assess each combat domain once");
 }
 reset();CvUnit land(1,DOMAIN_LAND),sea(2,DOMAIN_SEA);put(land);put(sea);readiness[DOMAIN_LAND]=true;readiness[DOMAIN_SEA]=false;
 vector<int>ids;ids.push_back(1);ids.push_back(2);check(tactical.StageGatheringCityAssault(ids,&target)&&ids.size()==1&&ids[0]==1&&staged[0]==2,"unready fleet cannot bypass gathering behind ready land units");
 reset();put(land);put(sea);readiness[DOMAIN_LAND]=readiness[DOMAIN_SEA]=true;ids.clear();ids.push_back(1);ids.push_back(2);
 check(!tactical.StageGatheringCityAssault(ids,&target)&&ids.size()==2&&staged.empty(),"ready domains retain normal positioning");
 reset();put(land);put(sea);ids.clear();ids.push_back(1);ids.push_back(2);
 check(tactical.StageGatheringCityAssault(ids,&target)&&ids.empty()&&staged.size()==2,"all gathering force avoids generic piecemeal approach");
 reset();put(land);stageOK=false;land.danger=50;ids.assign(1,1);
 check(tactical.StageGatheringCityAssault(ids,&target)&&ids.empty()&&safety.size()==1,"unsafe failed stage gets safety fallback");
 reset();put(land);stageOK=false;land.danger=0;ids.assign(1,1);
 check(tactical.StageGatheringCityAssault(ids,&target)&&ids.empty()&&safety.empty(),"safe failed stage is not sent through ordinary approach");
 reset();put(land);land.available=false;ids.assign(1,1);
 check(tactical.StageGatheringCityAssault(ids,&target)&&ids.empty()&&staged.empty(),"processed gatherer receives no extra order");land.available=true;
 reset();put(land);stageOK=false;removeOnStage=1;ids.assign(1,1);
 check(tactical.StageGatheringCityAssault(ids,&target)&&ids.empty()&&safety.empty(),"re-resolve identity after stage callback removes unit");
 reset();put(land);put(sea);land.dead=true;sea.owner=1;ids.clear();ids.push_back(1);ids.push_back(2);ids.push_back(99);
 check(!tactical.StageGatheringCityAssault(ids,&target)&&ids.empty()&&assessments.empty(),"dead foreign and missing identities are discarded");land.dead=false;sea.owner=0;
 reset();put(land);target.enemy=false;ids.assign(1,1);
 check(!tactical.StageGatheringCityAssault(ids,&target)&&ids.size()==1&&assessments.empty(),"ordinary positioning remains unchanged");
 check(!tactical.StageGatheringCityAssault(ids,NULL)&&ids.size()==1,"null target has no dispatch effects");
 reset();vector<CvUnit*>many;ids.clear();for(int i=0;i<300;++i){CvUnit*u=new CvUnit(i,i%2?DOMAIN_LAND:DOMAIN_SEA);put(*u);many.push_back(u);ids.push_back(i);}readiness[DOMAIN_SEA]=true;
 check(tactical.StageGatheringCityAssault(ids,&target)&&ids.size()==150&&staged.size()==150,"large mixed group preserves ready fleet");
 check(assessments[DOMAIN_LAND]==1&&assessments[DOMAIN_SEA]==1,"assessment work bounded by domains rather than unit count");
 for(size_t i=0;i<many.size();++i)delete many[i];
 printf("assault domain positioning: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
cpp = out / 'test.cpp'
cpp.write_text(fixture + actual + tests, encoding='utf-8')
vc = root / 'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
sdk = root / 'work/toolchain/sdk/windows'
env = os.environ.copy()
env['PATH'] = str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
env['INCLUDE'] = str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include')
env['LIB'] = str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL', '_CL_', 'LINK'):
    env.pop(key, None)
exe = out/'test.exe'
compiled = subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr)
if compiled.returncode:
    print(compiled.stdout+compiled.stderr)
    sys.exit(compiled.returncode)
result = subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
print(result.stdout+result.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(returncode=result.returncode,output=result.stdout+result.stderr,actual_function_sha256=hashlib.sha256(actual.encode()).hexdigest(),scope='Actual domain dispatcher with deterministic readiness/stage/movement services; no proof of engine pathfinding or campaign success.'),indent=2)+'\n')
sys.exit(result.returncode)
