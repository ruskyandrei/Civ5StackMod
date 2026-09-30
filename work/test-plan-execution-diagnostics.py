"""Actual-source VC9 execution diagnostics; compare control gameplay and disabled work.

The control methods come from the recorded pre-diagnostic DLL50 source. Native
mission/path/combat services are deterministic stubs, not a campaign simulator.
"""
from pathlib import Path
import hashlib, json, os, subprocess, sys

root = Path(__file__).resolve().parents[1]
out = root / 'work/plan-execution-diagnostics-regression'
out.mkdir(exist_ok=True)
path = root / 'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
source = path.read_text(encoding='utf-8-sig')
control_revision = '21481844d'
control_source = subprocess.run(['git', 'show', control_revision + ':CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],
                                cwd=root, capture_output=True, text=True, check=True).stdout


def method(text, name):
    start = text.index('bool TacticalAIHelpers::' + name + '(')
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


helpers = source[source.index('// Summary-only execution evidence.'):source.index('bool TacticalAIHelpers::FindAndExecuteBestUnitAssignments(')]
actual = method(source, 'ExecuteUnitAssignments')
wrapper = method(source, 'FindAndExecuteBestUnitAssignments')
control = method(control_source, 'ExecuteUnitAssignments').replace('TacticalAIHelpers::ExecuteUnitAssignments(', 'TacticalAIHelpers::ExecuteUnitAssignmentsControl(', 1)
wrapper_control = method(control_source, 'FindAndExecuteBestUnitAssignments').replace('TacticalAIHelpers::FindAndExecuteBestUnitAssignments(', 'TacticalAIHelpers::FindAndExecuteBestUnitAssignmentsControl(', 1).replace('TacticalAIHelpers::ExecuteUnitAssignments(ePlayer,plan)', 'TacticalAIHelpers::ExecuteUnitAssignmentsControl(ePlayer,plan)')

fixture = r'''
#include <vector>
#include <map>
#include <set>
#include <string>
#include <sstream>
#include <algorithm>
#include <cstdio>
#include <cstdarg>
#include <cstring>
using namespace std;
typedef int PlayerTypes;typedef int BuildTypes;typedef int MissionTypes;typedef int eAggressionLevel;
const int NO_PLAYER=-1,NO_BUILD=-1,MISSIONAI_OPMOVE=4,TACTSIM_MAX_UNITS=13;
#define MOD_BALANCE_VP 0
enum eUnitAssignmentType{A_INITIAL,A_MOVE,A_MELEEATTACK,A_MELEEKILL,A_RANGEATTACK,A_RANGEKILL,A_FINISH,A_BLOCKED,A_PILLAGE,A_CAPTURE,A_MOVE_FORCED,A_RESTART,A_MELEEKILL_NO_ADVANCE,A_MOVE_SWAP,A_MOVE_SWAP_REVERSE,A_MOVE_DOUBLE,A_USE_POWER,A_FINISH_TEMP,A_HEAL,A_WAIT};
struct MissionData{int eMissionType,iData1,iData2,iFlags,iPushTurn;MissionData():eMissionType(-1),iData1(-1),iData2(-1),iFlags(0),iPushTurn(9){}};
struct CvUnit;struct CvCity;struct CvPlot{int id,x,y;bool enemyCity,enemyUnit;CvUnit*defender;CvCity*city;
 CvPlot(int n=0):id(n),x(n),y(0),enemyCity(false),enemyUnit(false),defender(NULL),city(NULL){}
 int GetPlotIndex()const{return id;}int getX()const{return x;}int getY()const{return y;}bool isCity()const{return city!=NULL;}int getOwner()const{return enemyCity?1:0;}
 bool isEnemyUnit(int,bool,bool)const;bool isEnemyCity(const CvUnit&)const{return enemyCity;}CvCity*getPlotCity()const{return city;}
 CvUnit*getBestDefender(int,int,const CvUnit*)const{return defender;}};
struct CvCity{int hp,damage;CvCity():hp(100),damage(0){}int GetMaxHitPoints()const{return hp;}int getDamage()const{return damage;}};
int diagnosticReads=0,lookupReads=0,pathClears=0,searchCalls=0,planScenario=0;bool diagnostics=false,allowCity=true,blockMove=false,removeOnOrder=false,replaceOnOrder=false,buildAllowed=false,repairAllowed=false,surpriseKill=false;
vector<string> missionLog;vector<CvUnit*> allocated;vector<CvPlot> plots;CvCity city;
namespace CvTypes{int getMISSION_MOVE_TO(){return 1;}int getMISSION_SWAP_UNITS(){return 2;}int getMISSION_RANGE_ATTACK(){return 3;}int getMISSION_PILLAGE(){return 4;}int getMISSION_BUILD(){return 5;}int getMISSION_REPAIR_FLEET(){return 6;}int getMISSION_SKIP(){return 7;}}
struct CvUnit{int id,owner,hp,moves,attacks,processed,activity,timer,queue,missionAI,army;CvPlot*p;MissionData mission;
 enum{MOVEFLAG_IGNORE_DANGER=1,MOVEFLAG_NO_STOPNODES=2,MOVEFLAG_ABORT_IF_NEW_ENEMY_REVEALED=4};
 CvUnit(int n):id(n),owner(0),hp(100),moves(120),attacks(0),processed(0),activity(0),timer(0),queue(0),missionAI(0),army(-1),p(&plots[0]){}
 int GetID()const{return id;}int getOwner()const{return owner;}CvPlot*plot()const{return p;}bool isDelayedDeath()const{return false;}bool canMove()const{return moves>0;}bool canUseNow()const{return canMove()&&!processed;}
 int getMoves()const{return moves;}int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{++diagnosticReads;return 100;}
 int getNumAttacksMadeThisTurn()const{++diagnosticReads;return attacks;}int getNumAttacks()const{++diagnosticReads;return 2;}
 bool TurnProcessed()const{return processed!=0;}int GetActivityType()const{++diagnosticReads;return activity;}int GetMissionTimer()const{++diagnosticReads;return timer;}
 int GetLengthMissionQueue()const{++diagnosticReads;return queue;}int GetMissionAIType()const{++diagnosticReads;return missionAI;}
 const MissionData*GetHeadMissionData()const{++diagnosticReads;return queue?&mission:NULL;}int getArmyID()const{++diagnosticReads;return army;}bool isEmbarked()const{++diagnosticReads;return false;}
 bool IsDead()const{return hp<=0;}void ClearPathCache(){++pathClears;}bool canBuild(CvPlot*,int)const{return buildAllowed;}bool canRepairFleet(CvPlot*)const{return repairAllowed;}
 bool shouldHeal(bool)const{return false;}bool isBarbarian()const{return false;}void PushMission(int,int=-1,int=-1,int=0,bool=false,bool=false,int=0);
};
bool CvPlot::isEnemyUnit(int,bool,bool)const{return enemyUnit && (!defender||!defender->IsDead());}
struct TacticalStub{void UnitProcessed(int);};
struct CvPlayer{map<int,CvUnit*>units;TacticalStub tactical;CvUnit*getUnit(int id){++lookupReads;map<int,CvUnit*>::iterator i=units.find(id);return i==units.end()?NULL:i->second;}TacticalStub*GetTacticalAI(){return &tactical;}} player;
#define GET_PLAYER(x) player
void TacticalStub::UnitProcessed(int id){CvUnit*u=player.getUnit(id);if(u)u->processed=1;}
void CvUnit::PushMission(int type,int a,int b,int flags,bool,bool,int ai){ostringstream log;log<<id<<":"<<type<<":"<<a<<":"<<b<<":"<<flags;missionLog.push_back(log.str());
 queue=1;mission.eMissionType=type;mission.iData1=a;mission.iData2=b;mission.iFlags=flags;missionAI=ai;
 if(type==1||type==2){if(!blockMove&&a>=0&&a<(int)plots.size()){p=&plots[a];moves=max(0,moves-60);}}
 else if(type==3){++attacks;moves=max(0,moves-60);CvUnit*d=a>=0&&a<(int)plots.size()?plots[a].defender:NULL;if(d)d->hp-=surpriseKill?200:20;}
 else if(type==7)activity=1;
 if(removeOnOrder){player.units.erase(id);removeOnOrder=false;}
 if(replaceOnOrder){CvUnit*r=new CvUnit(id);allocated.push_back(r);r->hp=37;r->p=&plots[3];player.units[id]=r;replaceOnOrder=false;}}
struct MapStub{CvPlot*plotByIndexUnchecked(int id){return id>=0&&id<(int)plots.size()?&plots[id]:NULL;}};
struct GCStub{MapStub map;MapStub&getMap(){return map;}int getInfoTypeForString(const char*){return 1;}}GC;
struct STacticalAssignment{int iUnitID,iFromPlotIndex,iToPlotIndex,iRemainingMoves;eUnitAssignmentType eAssignmentType;
 STacticalAssignment(int unit=1,int from=0,int to=1,eUnitAssignmentType type=A_MOVE):iUnitID(unit),iFromPlotIndex(from),iToPlotIndex(to),iRemainingMoves(0),eAssignmentType(type){}};
struct Row{string category,message;};vector<Row>rows;
namespace CvStackingDiagnostics{bool EnabledCategory(int,int,const char*){return diagnostics;}void Record(int,int,const char*category,const char*format,...){if(!diagnostics)return;char message[3072];va_list args;va_start(args,format);_vsnprintf_s(message,sizeof(message),_TRUNCATE,format,args);va_end(args);Row row;row.category=category;row.message=message;rows.push_back(row);}}
namespace CvStacking{int GetInt(const char*,int fallback){return fallback;}}
namespace CvStackingOffensiveAI{bool Enabled(int){return true;}bool HoldForAssembly(const CvUnit*,const CvPlot*){return false;}bool ConsumeAdditionalTacticalBatch(int){return true;}bool AllowCityAttack(const CvUnit*,CvCity*,const CvPlot*,bool){return allowCity;}}
set<int>gDistanceToTargetPlots;
namespace TacticalAIHelpers{
 bool ExecuteUnitAssignments(int,const vector<STacticalAssignment>&);bool ExecuteUnitAssignmentsControl(int,const vector<STacticalAssignment>&);
 bool FindAndExecuteBestUnitAssignments(int,vector<CvUnit*>&,CvPlot*,int);bool FindAndExecuteBestUnitAssignmentsControl(int,vector<CvUnit*>&,CvPlot*,int);
 void UpdatePlotDistanceToTarget(int,CvPlot*){gDistanceToTargetPlots.insert(1);}
 int GetSimulatedDamageFromAttackOnCity(CvCity*,CvUnit*,CvPlot*,int&,int&){return 1;}int GetSimulatedDamageFromAttackOnUnit(CvUnit*,CvUnit*,CvPlot*,CvPlot*,int&){return 1;}
 vector<STacticalAssignment>FindBestUnitAssignments(const vector<CvUnit*>&units,CvPlot*,int,set<int>&,bool){++searchCalls;vector<STacticalAssignment>r;
  if(!units.empty())r.push_back(STacticalAssignment(units.front()->GetID(),units.front()->plot()->id,1,A_RANGEATTACK));return r;}
}
int checks=0,failures=0;void check(bool ok,const char*name){++checks;if(!ok){++failures;printf("FAIL: %s\n",name);}}
void reset(){for(size_t i=0;i<allocated.size();++i)delete allocated[i];allocated.clear();player.units.clear();plots.clear();for(int i=0;i<5;++i)plots.push_back(CvPlot(i));
 diagnostics=false;allowCity=true;blockMove=removeOnOrder=replaceOnOrder=buildAllowed=repairAllowed=surpriseKill=false;diagnosticReads=lookupReads=pathClears=searchCalls=planScenario=0;missionLog.clear();rows.clear();gDistanceToTargetPlots.clear();city=CvCity();}
CvUnit*unit(int id){CvUnit*u=new CvUnit(id);allocated.push_back(u);player.units[id]=u;return u;}
bool contains(const string&s,const char*field){return s.find(field)!=string::npos;}
string outcome(bool result){ostringstream out;out<<result<<":"<<pathClears<<":"<<searchCalls;for(size_t i=0;i<missionLog.size();++i)out<<"|"<<missionLog[i];for(map<int,CvUnit*>::iterator i=player.units.begin();i!=player.units.end();++i){CvUnit*u=i->second;out<<";"<<u->id<<","<<u->p->id<<","<<u->hp<<","<<u->moves<<","<<u->attacks<<","<<u->processed<<","<<u->activity<<","<<u->queue<<","<<u->missionAI;}return out.str();}
vector<STacticalAssignment> scenario(int n){CvUnit*u=unit(1);vector<STacticalAssignment>a;a.push_back(STacticalAssignment());
 switch(n){case 0:break;case 1:blockMove=true;break;case 2:plots[1].enemyUnit=true;plots[1].defender=unit(2);a[0].eAssignmentType=A_RANGEATTACK;break;
 case 3:plots[1].enemyUnit=true;plots[1].defender=unit(2);surpriseKill=true;a[0].eAssignmentType=A_RANGEKILL;break;
 case 4:plots[1].enemyUnit=true;plots[1].defender=unit(2);surpriseKill=true;a[0].eAssignmentType=A_RANGEATTACK;break;
 case 5:plots[1].enemyCity=true;plots[1].city=&city;allowCity=false;a[0].eAssignmentType=A_RANGEATTACK;break;
 case 6:plots[1].enemyCity=true;plots[1].city=&city;allowCity=false;a[0].eAssignmentType=A_MELEEATTACK;break;
 case 7:a[0].eAssignmentType=A_RESTART;break;case 8:buildAllowed=true;a[0].eAssignmentType=A_USE_POWER;break;
 case 9:repairAllowed=true;a[0].eAssignmentType=A_USE_POWER;break;case 10:unit(2);a.push_back(STacticalAssignment(2,0,2,A_RANGEATTACK));break;
 case 11:buildAllowed=true;removeOnOrder=true;a[0].eAssignmentType=A_USE_POWER;break;case 12:buildAllowed=true;replaceOnOrder=true;a[0].eAssignmentType=A_USE_POWER;break;
 case 13:a[0].eAssignmentType=A_MOVE_SWAP_REVERSE;break;case 14:a.clear();break;case 15:player.units.erase(u->id);break;case 16:a[0].eAssignmentType=A_FINISH;break;}
 return a;}
'''

tests = r'''
int main(){
 for(int s=0;s<=16;++s){reset();vector<STacticalAssignment>a=scenario(s);string expected=outcome(TacticalAIHelpers::ExecuteUnitAssignmentsControl(0,a));int oldLookup=lookupReads;
  reset();a=scenario(s);string disabled=outcome(TacticalAIHelpers::ExecuteUnitAssignments(0,a));check(disabled==expected,"disabled diagnostic preserves actual control result/orders/state");check(rows.empty()&&diagnosticReads==0&&lookupReads==oldLookup,"disabled execution performs no snapshot reads/extra lookups/records");
  reset();a=scenario(s);diagnostics=true;string enabled=outcome(TacticalAIHelpers::ExecuteUnitAssignments(0,a));check(enabled==expected,"enabled diagnostic preserves actual control result/orders/state");
  bool succeeds=s==0||s==2||s==3||s==14||s==15||s==16;check(rows.size()==(succeeds?0:1),"exactly one compact row per failed execution");
  if(s==1)check(contains(rows[0].message,"pre=1 post=0")&&contains(rows[0].message,"currentOrderIssued=1")&&contains(rows[0].message,"beforePlot=0 afterPlot=0"),"blocked mission distinguished from no issued order");
  if(s==5||s==6)check(contains(rows[0].message,"reason=city_attack_gate")&&contains(rows[0].message,"issuedOrders=0"),"early city attack gate recorded once");
  if(s==7)check(contains(rows[0].message,"reason=visibility_restart"),"explicit restart recorded once");
  if(s==8||s==9)check(contains(rows[0].message,"type=16")&&contains(rows[0].message,"pre=0 post=0")&&contains(rows[0].message,"issuedOrders=1"),"legacy successful power still reports failure without a gameplay fix");
  if(s==10)check(contains(rows[0].message,"index=1 unit=2")&&contains(rows[0].message,"issuedOrders=1")&&contains(rows[0].message,"currentOrderIssued=0"),"partial execution preceding no-order failure preserved");
  if(s==11)check(contains(rows[0].message,"beforePresent=1 afterPresent=0")&&contains(rows[0].message,"afterHP=-1"),"removed actor after-state resolved by owned ID");
  if(s==12)check(contains(rows[0].message,"afterPlot=3")&&contains(rows[0].message,"afterHP=37"),"replacement actor after-state resolved by owned ID");
 }
 reset();CvUnit*u=unit(1);vector<CvUnit*>units(1,u);string expected=outcome(TacticalAIHelpers::FindAndExecuteBestUnitAssignmentsControl(0,units,&plots[1],2));int expectedSearch=searchCalls;
 reset();u=unit(1);units.assign(1,u);check(outcome(TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,units,&plots[1],2))==expected,"disabled wrapper preserves four retries and state");check(rows.empty()&&diagnosticReads==0&&searchCalls==expectedSearch,"disabled wrapper performs no diagnostic unit loops");
 reset();u=unit(1);units.assign(1,u);diagnostics=true;check(outcome(TacticalAIHelpers::FindAndExecuteBestUnitAssignments(0,units,&plots[1],2))==expected,"enabled wrapper preserves unchanged failed retry behavior");check(rows.size()==8&&searchCalls==4,"one execution failure plus retry record per failed attempt");
 for(size_t i=1;i<rows.size();i+=2)check(rows[i].category=="PLAN_RETRY"&&contains(rows[i].message,"sameBasicSignature=1")&&contains(rows[i].message,"idsShown=1 idsTruncated=0 ids=1"),"unchanged basic-state retry evidence stable and ordered");
 reset();diagnostics=true;unit(1);unit(2);vector<int>ids;ids.push_back(1);ids.push_back(2);unsigned __int64 a=StackPlanDiagnosticInputHash(0,ids);reverse(ids.begin(),ids.end());check(a!=StackPlanDiagnosticInputHash(0,ids),"signature preserves input order");reverse(ids.begin(),ids.end());player.units[1]->moves--;check(a!=StackPlanDiagnosticInputHash(0,ids),"signature observes basic movement change");player.units.erase(1);check(a!=StackPlanDiagnosticInputHash(0,ids),"signature includes missing input identity");
 reset();diagnostics=true;for(int i=1;i<=54;++i)units.push_back(unit(i));units.erase(units.begin());StackPlanRetryDiagnostic probe(0,&plots[1],2,3,units);player.units[54]->hp--;probe.Failed(57);
 check(rows.size()==1&&contains(rows[0].message,"input=54")&&contains(rows[0].message,"idsShown=40 idsTruncated=1")&&contains(rows[0].message,"sameBasicSignature=0"),"bounded ID list hashes changes beyond the displayed forty");
 printf("plan execution diagnostics: %d checks, %d failures\n",checks,failures);reset();return failures?1:0;
}
'''

cpp = out / 'test.cpp'
cpp.write_text(fixture + helpers + control + wrapper_control + actual + wrapper + tests, encoding='utf-8')
vc = root / 'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
sdk = root / 'work/toolchain/sdk/windows'
env = os.environ.copy()
env['PATH'] = str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
env['INCLUDE'] = str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include')
env['LIB'] = str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL', '_CL_', 'LINK'): env.pop(key, None)
exe = out / 'test.exe'
compile = subprocess.run([str(vc/'Vc7/bin/cl.exe'), '/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],
                         env=env,cwd=out,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compile.stdout+compile.stderr)
if compile.returncode:
    print(compile.stdout+compile.stderr)
    sys.exit(compile.returncode)
run = subprocess.run([str(exe)],capture_output=True,text=True,timeout=20)
print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,
    control_revision=control_revision,actual_function_sha256=hashlib.sha256((helpers+actual+wrapper).encode()).hexdigest(),
    scope='Actual diagnostics/execution/wrapper vs pre-diagnostic actual execution/wrapper, deterministic native services; no real campaign/pathfinding equivalence claim.'),indent=2)+'\n')
sys.exit(run.returncode)
