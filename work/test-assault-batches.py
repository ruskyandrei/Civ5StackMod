"""Compile the actual batch coordinator with bounded deterministic VC9 services."""
from pathlib import Path
import hashlib, json, os, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'work/assault-batches-regression'
out.mkdir(exist_ok=True)
path = root / 'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
source = path.read_text(encoding='utf-8-sig')
start = source.index('bool TacticalAIHelpers::FindAndExecuteBestUnitAssignments(')
end = source.index('{', start) + 1
depth = 1
while depth:
    depth += (source[end] == '{') - (source[end] == '}')
    end += 1
actual = source[start:end]
fixture = r'''
#include <vector>
#include <map>
#include <set>
#include <string>
#include <algorithm>
#include <cstdio>
using namespace std;
typedef int PlayerTypes;typedef int eAggressionLevel;
const int TACTSIM_MAX_UNITS=13;
struct CvPlot{bool city;int owner;CvPlot():city(true),owner(1){}bool isCity()const{return city;}int getOwner()const{return owner;}int GetPlotIndex()const{return 100;}} target;
struct CvUnit{int id;bool processed;CvUnit(int i):id(i),processed(false){}int GetID()const{return id;}int getOwner()const{return 0;}bool isDelayedDeath()const{return false;}bool TurnProcessed()const{return processed;}bool canUseNow()const{return !processed;}};
struct CvPlayer{map<int,CvUnit*> units;CvUnit*getUnit(int id){map<int,CvUnit*>::iterator i=units.find(id);return i==units.end()?NULL:i->second;}} player;
#define GET_PLAYER(x) player
struct STacticalAssignment{int iUnitID;STacticalAssignment(int i):iUnitID(i){}};
map<string,int> options;bool enabled=true,capture=false,kill=false,retry=false,reject=false;int extra=0,calls=0,executions=0,dead=0;set<int> gDistanceToTargetPlots,held;
namespace CvStacking{int GetInt(const char*n,int f){return options.count(n)?options[n]:f;}}
namespace CvStackingOffensiveAI{bool Enabled(int){return enabled;}bool HoldForAssembly(const CvUnit*u,const CvPlot*){return held.count(u->id)!=0;}bool ConsumeAdditionalTacticalBatch(int){if(extra>=CvStacking::GetInt("AIAssaultExtraBatchesPerTurn",16))return false;++extra;return true;}}
namespace CvStackingDiagnostics{void Record(int,int,const char*,const char*,...) {}}
namespace TacticalAIHelpers{
 void UpdatePlotDistanceToTarget(int,CvPlot*){gDistanceToTargetPlots.insert(100);}
 vector<STacticalAssignment> FindBestUnitAssignments(const vector<CvUnit*>&u,CvPlot*,int,set<int>&bad,bool){++calls;vector<STacticalAssignment>r;if(reject){bad.insert(u.front()->id);reject=false;return r;}for(size_t i=0;i<u.size()&&i<13;++i)r.push_back(STacticalAssignment(u[i]->id));return r;}
 bool ExecuteUnitAssignments(int,const vector<STacticalAssignment>&r){++executions;for(size_t i=0;i<r.size();++i){CvUnit*u=player.getUnit(r[i].iUnitID);if(!u)continue;if(kill&&i==0){player.units.erase(u->id);delete u;++dead;kill=false;}else u->processed=true;if(retry){retry=false;return false;}}if(capture)target.owner=0;return true;}
 bool FindAndExecuteBestUnitAssignments(int,vector<CvUnit*>&,CvPlot*,int);
}
int checks=0,failures=0;
void check(bool ok,const char*n){++checks;if(!ok){++failures;printf("FAIL: %s\n",n);}}
vector<CvUnit*> make(int count){for(map<int,CvUnit*>::iterator i=player.units.begin();i!=player.units.end();++i)delete i->second;player.units.clear();options.clear();enabled=true;capture=kill=retry=reject=false;extra=calls=executions=dead=0;target=CvPlot();gDistanceToTargetPlots.clear();held.clear();vector<CvUnit*>v;for(int i=0;i<count;++i){CvUnit*u=new CvUnit(i);player.units[i]=u;v.push_back(u);}return v;}
int processed(){int n=0;for(map<int,CvUnit*>::const_iterator i=player.units.begin();i!=player.units.end();++i)n+=i->second->processed;return n;}
'''
tests = r'''
int main(){
 vector<CvUnit*>v=make(25);check(TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1),"large assault executes");check(processed()==25&&calls==2&&extra==1,"all 25 participate in two bounded batches");check(gDistanceToTargetPlots.empty(),"distance cache released after final batch");
 v=make(39);TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1);check(processed()==39&&calls==3,"39 units use three thirteen-unit batches");
 v=make(60);TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1);check(processed()==39&&calls==3,"per-objective work limit keeps remainder unprocessed");
 v=make(25);options["AIAssaultExtraBatchesPerTurn"]=0;TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1);check(processed()==13&&calls==1,"zero extra budget preserves first batch");
 v=make(25);enabled=false;TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1);check(processed()==13&&calls==1,"disabled stacking AI uses one bounded search");
 v=make(25);capture=true;TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1);check(processed()==13&&calls==1,"city captured in first batch stops further assaults");
 v=make(25);kill=true;TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1);check(dead==1&&processed()==24&&calls==2,"deleted participants resolved by ID before next batch");
 v=make(25);retry=true;TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1);check(processed()==25&&calls==3,"partial execution retry uses current board and available units");
 v=make(25);reject=true;TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1);check(processed()==24&&calls==3&&!player.getUnit(0)->processed,"unusable candidate filtered without discarding other units");
 v=make(12);TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1);check(processed()==12&&calls==1&&extra==0,"small group retains original single search");
 v=make(25);for(int i=0;i<14;++i)held.insert(i);TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1);check(processed()==11&&calls==1&&!player.getUnit(0)->processed,"assembling units excluded without discarding available field force");
 v=make(12);for(int i=0;i<12;++i)held.insert(i);check(!TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1)&&calls==0,"held assault does not run a futile combat search");
 v=make(0);check(!TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,&target,1),"empty group safely rejected");v=make(1);check(!TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,v,NULL,1),"null target safely rejected");
 printf("assault batches: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
cpp = out/'test.cpp'
cpp.write_text(fixture + actual + tests)
vc = root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
sdk = root/'work/toolchain/sdk/windows'
env = os.environ.copy()
env['PATH'] = str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
env['INCLUDE'] = str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include')
env['LIB'] = str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'): env.pop(key,None)
exe = out/'test.exe'
compile = subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],env=env,cwd=out,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compile.stdout+compile.stderr)
if compile.returncode: print(compile.stdout+compile.stderr);sys.exit(compile.returncode)
run = subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps({'returncode':run.returncode,'output':run.stdout+run.stderr,'actual_function_sha256':hashlib.sha256(actual.encode()).hexdigest(),'scope':'Real coordinator with deterministic search/execution services; not real tactical search, pathfinding or campaign efficacy.'},indent=2))
sys.exit(run.returncode)
