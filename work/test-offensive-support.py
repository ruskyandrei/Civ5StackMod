"""Actual offensive module under deterministic VC9 engine services; no game launch."""
from pathlib import Path
import ast, re, os, subprocess, sys, json, hashlib
root=Path(__file__).resolve().parents[1]
if not (root/'CvGameCoreDLL_Expansion2').exists(): root=Path(r'E:\Projects\Civ5StackMod')
core=root/'CvGameCoreDLL_Expansion2';out=root/'work/offensive-support-regression';out.mkdir(exist_ok=True)
raw=(root/'work/test-military-allocation.py').read_text(encoding='utf-8-sig')
tree=ast.parse(raw)
stubs=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='stubs' for x in n.targets))
stubs=stubs.replace('using namespace std;','''using namespace std;
typedef int AIOperationTypes;
const int AI_OPERATION_CITY_ATTACK_LAND=10,AI_OPERATION_CITY_ATTACK_NAVAL=11,AI_OPERATION_CITY_ATTACK_COMBINED=12;
const int AI_ABORT_LOST_PATH=3,AI_ABORT_TIMED_OUT=15;
''')
stubs=stubs.replace('MOVEFLAG_AI_ABORT_IN_DANGER=8','MOVEFLAG_AI_ABORT_IN_DANGER=8,MOVEFLAG_APPROX_TARGET_RING1=16,MOVEFLAG_SAFE_EMBARK_ONLY=32')
stubs=stubs.replace('bool GeneratePath(CvPlot*,int,int){return pathOK;}','''int baseMoves(bool)const{return 2;}bool isNativeDomain(const CvPlot*p)const{return domain==DOMAIN_SEA?p->water:!p->water;}
 bool GeneratePath(CvPlot*,int,int,int*turns=NULL){++pathCalls;if(turns)*turns=eta;return pathOK;}
 CvPlot*GetPathLastPlot(){return end;}
''')
stubs=stubs.replace('int GetID()const{return id;}int GetOperationID()', 'int GetMovementRate()const{return 2;}int GetID()const{return id;}int GetOperationID()')
stubs=stubs.replace('int id,owner,enemy,started,state;bool offensive;', 'int id,owner,enemy,started,state;int type,training;CvArmyAI*army;bool offensive;')
stubs=stubs.replace('state(0),offensive(true)', 'state(0),type(AI_OPERATION_CITY_ATTACK_LAND),training(0),army(NULL),offensive(true)')
stubs=stubs.replace('bool IsNavalOperation()const{return false;}','''bool IsNavalOperation()const{return type!=AI_OPERATION_CITY_ATTACK_LAND;}
 int GetOperationType()const{return type;}int GetDeployRange()const{return 3;}CvArmyAI*GetArmy(int)const{return army;}
 int GetNumUnitsCommittedToBeBuilt()const{return training;}
 int GetStepDistanceBetweenPlots(CvPlot*a,CvPlot*b)const{return a->route?abs(a->x-b->x):-1;}
 CvPlot*GetPlotXInStepPath(CvPlot*a,CvPlot*b,int,bool)const{return a->route?b:NULL;}
 bool RecruitUnit(CvUnit*u){if(!army)return false;for(size_t i=0;i<army->slots.size();++i)if(!army->slots[i].IsUsed()){army->slots[i].id=u->id;u->army=army->id;return true;}return false;}
''')
stubs=stubs.replace('int getNumUnits()const{return (int)units.size();}\n CvUnit*firstUnit','''size_t getNumAIOperations()const{return op?1:0;}CvAIOperation*getAIOperationByIndex(size_t){return op;}
 CvArmyAI*getArmyAI(int id){for(size_t i=0;i<armies.size();++i)if(armies[i]->id==id)return armies[i];return NULL;}
 int getNumUnits()const{return (int)units.size();}
 CvUnit*firstUnit''')
stubs+='''
namespace CvStackingAI {
 bool Enabled(int owner){return stackEnabled && !players[owner].human && CvStacking::GetInt("AIMilitaryAllocationEnabled",1)!=0;}
 int UnitStrength(const CvUnit*u){return max(u->cs,u->rs)*u->hp/u->maxhp;}
 bool RetainCityUnit(const CvUnit*u){return u->IsGarrisoned();}
}
int retaliation=20;
namespace TacticalAIHelpers {int GetSimulatedDamageFromAttackOnCity(const CvCity*,const CvUnit*,const CvPlot*,int&received,int&,bool,int,int){received=retaliation;return 1;}}
'''
def clean(s):return re.sub(r'^#(?:include|pragma)[^\n]*\n','',s,flags=re.M)
source=(core/'CvStackingOffensiveAI.cpp').read_text(encoding='utf-8-sig')
header=clean((core/'CvStackingOffensiveAI.h').read_text(encoding='utf-8-sig'))
policy=clean((core/'CvStackingAIPolicy.h').read_text(encoding='utf-8-sig'))
tests=r'''
int checks=0,failed=0;
void check(bool ok,const char*n){++checks;if(!ok){++failed;printf("FAIL: %s\n",n);}}
void put(CvUnit&u,CvPlot&p){u.position=&p;p.units.push_back(&u);players[u.owner].units.push_back(&u);GC.map.plots[p.id]=&p;}
void init(){CvStackingOffensiveAI::Reset();for(int i=0;i<MAX_PLAYERS;++i){players[i]=CvPlayer();players[i].id=i;}GC.game.turn=100;GC.map.plots.clear();options.clear();stackEnabled=true;retaliation=20;}
void setup(CvAIOperation&op,CvArmyAI&a,CvPlot&t,CvPlot&s){op.target=&t;op.muster=&s;op.army=&a;a.center=&s;a.state=ARMYAISTATE_MOVING_TO_DESTINATION;players[0].op=&op;players[0].armies.push_back(&a);GC.map.plots[t.id]=&t;GC.map.plots[s.id]=&s;t.owner=1;}
void policyTests(){using namespace CvStackingAIPolicy;
 check(CityProtection(160,90,300,300,true)==90,"cap before scaling");
 check(CityProtection(160,90,150,300,true)==45,"half HP gives half capped protection");
 check(CityProtection(160,90,0,300,true)==0,"zero HP no protection");
 check(CityProtection(160,90,1,300,true)==0,"integer floor");
 check(CityProtection(0,90,300,300,true)==0,"no fortifications");
 check(CityProtection(50,90,450,300,true)==50,"HP over maximum clamped");
 check(CityProtection(160,90,0,300,false)==90,"XML restores legacy protection");
 check(CityProtection(50,90,1,0,true)==0,"invalid max guarded");
 check(!OpeningReady(3,5,1,1,100,40,4,75,1,150),"too few staged");
 check(!OpeningReady(4,8,1,1,100,40,4,75,1,150),"too dispersed");
 check(!OpeningReady(4,5,0,1,100,40,4,75,1,150),"missing capturer");
 check(!OpeningReady(4,5,1,0,100,40,4,75,1,150),"missing fire support");
 check(!OpeningReady(4,5,1,1,59,40,4,75,1,150),"insufficient strength");
 check(OpeningReady(4,5,1,1,60,40,4,75,1,150),"ready boundary");
 check(!MovingStalled(12,true,12,20),"contact grace");check(MovingStalled(12,false,12,20),"ordinary deadline");
}
void routeTests(){init();CvPlot t(10,20),s(1),uplot(2,1);CvCity city(10,&t);CvAIOperation op;CvArmyAI a;setup(op,a,t,s);CvUnit u;put(u,uplot);a.slots.push_back(CvArmyFormationSlot(u.id));u.army=a.id;
 check(!CvStackingOffensiveAI::RouteBlocked(0,&t,false),"initial target available");
 options["AIOperationRouteRetryTurns"]=0;CvStackingOffensiveAI::OperationAborted(&op,AI_ABORT_LOST_PATH);check(!CvStackingOffensiveAI::RouteBlocked(0,&t,false),"XML disables retry cooldown");options.clear();
 CvStackingOffensiveAI::OperationAborted(&op,AI_ABORT_LOST_PATH);
 check(CvStackingOffensiveAI::RouteBlocked(0,&t,false),"failed target delayed");check(!CvStackingOffensiveAI::RouteBlocked(0,&t,true),"independent naval retry");
 ++t.owner;check(!CvStackingOffensiveAI::RouteBlocked(0,&t,false),"ownership change invalidates failure");--t.owner;
 GC.game.turn+=5;check(CvStackingOffensiveAI::RouteBlocked(0,&t,false),"last cooldown turn");++GC.game.turn;check(!CvStackingOffensiveAI::RouteBlocked(0,&t,false),"retry deadline");
 s.route=false;check(CvStackingOffensiveAI::RepairRoute(&op,&a,&s,&t)==&t,"repair from actual unit, not disconnected centroid");
 uplot.route=false;check(!CvStackingOffensiveAI::RepairRoute(&op,&a,&s,&t),"all unit origins disconnected");uplot.route=true;
 options["AIOperationRouteRepairCandidates"]=0;check(!CvStackingOffensiveAI::RepairRoute(&op,&a,&s,&t),"repair path budget");
 CvStackingOffensiveAI::OperationAborted(&op,AI_ABORT_LOST_PATH);CvStackingOffensiveAI::Reset();check(!CvStackingOffensiveAI::RouteBlocked(0,&t,false),"same-turn reload clears route history");
}
void openingTests(){init();CvPlot t(10,6),s(1);CvCity city(10,&t);CvAIOperation op;CvArmyAI a;setup(op,a,t,s);CvUnit units[5];
 for(int i=0;i<5;++i){units[i].id=i;units[i].army=1;put(units[i],s);a.slots.push_back(CvArmyFormationSlot(i));}units[4].ranged=true;units[4].capture=false;
 check(CvStackingOffensiveAI::OpeningReady(&op,&a),"healthy core opening ready");
 check(CvStackingOffensiveAI::ReadyToDeclare(0,1),"voluntary declaration revalidates force");players[0].op=NULL;check(!CvStackingOffensiveAI::ReadyToDeclare(0,1),"stale readiness flag cannot declare after force disappeared");players[0].op=&op;
 s.route=false;check(!CvStackingOffensiveAI::OpeningReady(&op,&a),"neutral closed border path blocks readiness");s.route=true;
 t.x=20;check(!CvStackingOffensiveAI::OpeningReady(&op,&a),"discovery at distance does not authorize declaration");t.x=6;
 for(int i=0;i<4;++i)units[i].capture=false;check(!CvStackingOffensiveAI::OpeningReady(&op,&a),"ranged-only force not ready");units[0].capture=true;
 for(int i=0;i<3;++i)units[i].hp=30;check(!CvStackingOffensiveAI::OpeningReady(&op,&a),"wounded core not ready");
 options["AIWarPreparationEnabled"]=0;check(CvStackingOffensiveAI::OpeningReady(&op,&a),"preparation XML toggle delegates");
}
void supportTests(){init();CvPlot t(10,20),s(1,10),rear(2),front(3,19);CvCity city(10,&t);CvAIOperation op;CvArmyAI a;setup(op,a,t,s);CvUnit units[20];
 for(int i=0;i<6;++i){units[i].id=i;units[i].army=1;put(units[i],s);a.slots.push_back(CvArmyFormationSlot(i));}
 units[6].id=6;put(units[6],rear);units[7].id=7;put(units[7],rear);
 vector<CvStackingOffensiveAI::Demand>d;CvStackingOffensiveAI::AddDemands(&units[6],d);check(!d.empty(),"full healthy formation requests proactive reserve");
 check(d[0].target==t.id&&d[0].staging==s.id,"objective separate from moving staging");
 units[7].position=&s;CvStackingOffensiveAI::RecordTransfer(&units[7],t.id,op.id,0);check(CvStackingOffensiveAI::HoldReserve(&units[7]),"arrived reserve retained beside full army");units[7].position=&rear;units[7].processed=false;
 CvStackingOffensiveAI::RecordTransfer(&units[6],t.id,op.id,5);check(CvStackingOffensiveAI::HasCommitment(&units[6],&t),"commitment stored by unit ID");
 check(!CvStackingOffensiveAI::HasCommitment(&units[6],&s),"staging not mistaken for target");
 check(CvStackingOffensiveAI::PrioritizeExisting(0,&t,false),"active attack precedes competing army");
 op.state=AI_OPERATION_STATE_SUCCESSFUL_FINISH;players[0].op=NULL;++GC.game.turn;
 d.clear();CvStackingOffensiveAI::AddDemands(&units[7],d);check(!d.empty()&&d[0].staging==t.id,"objective survives tactical handoff");
 players[0].war=false;++GC.game.turn;d.clear();CvStackingOffensiveAI::AddDemands(&units[7],d);check(d.empty(),"peace cancels handed-off demand");check(!CvStackingOffensiveAI::HasCommitment(&units[6]),"peace cancels inbound reservation");
 players[0].war=true;players[0].op=&op;op.state=0;CvStackingOffensiveAI::ObserveOperation(&op);CvStackingOffensiveAI::RecordTransfer(&units[6],t.id,op.id,4);t.owner=0;check(!CvStackingOffensiveAI::HasCommitment(&units[6]),"same-turn city capture invalidates commitment");t.owner=1;CvStackingOffensiveAI::CancelCommitment(&units[6]);check(!CvStackingOffensiveAI::HasCommitment(&units[6]),"defensive reassignment removes offensive credit immediately");
 init();setup(op,a,t,s);op.state=0;a.slots.clear();CvUnit v(30);put(v,s);a.slots.push_back(CvArmyFormationSlot());CvStackingOffensiveAI::ObserveOperation(&op);CvStackingOffensiveAI::RecordTransfer(&v,t.id,op.id,0);
 check(CvStackingOffensiveAI::JoinArrived(&v)&&v.army==a.id,"arrived support actually joins open formation");check(!CvStackingOffensiveAI::HasCommitment(&v),"joined support not double counted inbound");
 CvUnit w(31);put(w,rear);CvStackingOffensiveAI::RecordTransfer(&w,t.id,op.id,8);GC.game.turn+=6;check(!CvStackingOffensiveAI::HasCommitment(&w),"stalled transfer expires");
}
void capsTests(){init();CvPlot t(10,20),s(1,19),rear(2);CvCity city(10,&t);CvAIOperation op;CvArmyAI a;setup(op,a,t,s);CvUnit units[20];
 for(int i=0;i<18;++i){units[i].id=i;put(units[i],s);}units[18].id=18;put(units[18],rear);
 vector<CvStackingOffensiveAI::Demand>d;CvStackingOffensiveAI::AddDemands(&units[18],d);check(d.empty(),"commitment hard cap");
 for(int i=0;i<18;++i)units[i].dead=true;op.training=18;d.clear();CvStackingOffensiveAI::AddDemands(&units[18],d);check(d.empty(),"training counts toward cap");
 op.training=0;options["AIOffensiveSupportEnabled"]=0;d.clear();CvStackingOffensiveAI::AddDemands(&units[18],d);check(d.empty(),"support XML disabled");
}
void captureTests(){init();CvPlot t(10,5),s(1),adj(2,4);CvCity city(10,&t);city.owner=1;t.owner=1;GC.map.plots[t.id]=&t;CvUnit u(1);put(u,s);u.end=&adj;
 check(CvStackingOffensiveAI::CanCapture(&u,&t),"land melee eligible");u.capture=false;check(!CvStackingOffensiveAI::CanCapture(&u,&t),"no capture promotion rejected");u.capture=true;
 u.domain=DOMAIN_SEA;check(!CvStackingOffensiveAI::CanCapture(&u,&t),"ship cannot take inland city");t.coastal=true;check(CvStackingOffensiveAI::CanCapture(&u,&t),"naval melee coastal capture");u.domain=DOMAIN_LAND;
 u.hp=59;check(!CvStackingOffensiveAI::CanCapture(&u,&t),"unhealthy capturer rejected");u.hp=100;
 city.damage=290;check(CvStackingOffensiveAI::ContinueSiege(0,&city),"viable path supports low HP siege");
 u.pathOK=false;for(int n=0;n<9;++n){++GC.game.turn;CvStackingOffensiveAI::ContinueSiege(0,&city);}
 check(!CvStackingOffensiveAI::ContinueSiege(0,&city),"closed/inaccessible path eventually stops futile low HP fire");
 u.pathOK=true;++GC.game.turn;check(CvStackingOffensiveAI::ContinueSiege(0,&city),"new route resumes siege");
 retaliation=100;for(int n=0;n<9;++n){++GC.game.turn;CvStackingOffensiveAI::ContinueSiege(0,&city);}check(!CvStackingOffensiveAI::ContinueSiege(0,&city),"suicidal capturer not credited");
 CvUnit defender(3);defender.owner=1;put(defender,t);++GC.game.turn;check(CvStackingOffensiveAI::ContinueSiege(0,&city),"useful collateral fire retained");defender.hp=50;++GC.game.turn;check(!CvStackingOffensiveAI::ContinueSiege(0,&city),"victim floor is not useful collateral");
 city.damage=0;++GC.game.turn;check(CvStackingOffensiveAI::ContinueSiege(0,&city),"healthy city preparatory fire retained");
 city.damage=290;retaliation=100;options["AICapturePlanPathQueriesPerTurn"]=1;CvUnit v(4);put(v,s);v.end=&adj;++GC.game.turn;
 check(CvStackingOffensiveAI::ContinueSiege(0,&city),"exhausted path budget is unknown, not an impossible capture verdict");

}
void navalTests(){init();CvPlot cityPlot(20,6),water(21,5),stage(1);CvCity city(20,&cityPlot);cityPlot.coastal=true;cityPlot.owner=1;water.water=true;stage.water=true;water.ring.push_back(&cityPlot);GC.map.plots[20]=&cityPlot;
 CvAIOperation op;CvArmyAI a;setup(op,a,water,stage);op.type=AI_OPERATION_CITY_ATTACK_NAVAL;a.domain=DOMAIN_SEA;CvUnit ships[5];
 for(int i=0;i<5;++i){ships[i].id=i;ships[i].domain=DOMAIN_SEA;ships[i].army=1;put(ships[i],stage);a.slots.push_back(CvArmyFormationSlot(i));}ships[4].ranged=true;ships[4].capture=false;
 check(CvStackingOffensiveAI::CityTarget(&op)==&cityPlot,"naval water waypoint resolves adjacent city");
 check(CvStackingOffensiveAI::OpeningReady(&op,&a),"naval opening readiness uses real city, not null water city");
 CvStackingOffensiveAI::ObserveOperation(&op);CvStackingOffensiveAI::Handoff(&op);
 check(CvStackingOffensiveAI::HasCommitment(&ships[0],&water),"naval recruitment recognizes water waypoint of committed city");
 check(CvStackingOffensiveAI::HasCommitment(&ships[0],&cityPlot),"handoff retains actual city objective");
 CvStackingOffensiveAI::OperationAborted(&op,AI_ABORT_LOST_PATH);check(CvStackingOffensiveAI::RouteBlocked(0,&cityPlot,true),"naval failure keys actual city for request gate");
 water.ring.clear();check(CvStackingOffensiveAI::CityTarget(&op)==NULL,"unknown coastal target safely rejected");check(!CvStackingOffensiveAI::OpeningReady(&op,&a),"missing city cannot dereference null");
}
void marchTests(){init();CvPlot t(10,20),s(1);CvCity city(10,&t);CvAIOperation op;CvArmyAI a;setup(op,a,t,s);
 check(!CvStackingOffensiveAI::MovingStalled(&op,&a,false),"new march grace");
 for(int n=0;n<11;++n){++GC.game.turn;check(!CvStackingOffensiveAI::MovingStalled(&op,&a,false),"deadline not premature");}
 ++GC.game.turn;check(CvStackingOffensiveAI::MovingStalled(&op,&a,false),"stagnant march reassessed");
 ++GC.game.turn;s.x=3;check(!CvStackingOffensiveAI::MovingStalled(&op,&a,false),"progress resets clock");
 CvUnit u;put(u,s);a.slots.push_back(CvArmyFormationSlot(u.id));check(!CvStackingOffensiveAI::HoldForContact(&op,&a,&t),"irrelevant skirmish does not pin safe core");u.danger=110;check(CvStackingOffensiveAI::HoldForContact(&op,&a,&t),"exposed core holds");
}
int main(){policyTests();routeTests();openingTests();supportTests();capsTests();captureTests();navalTests();marchTests();printf("offensive support: %d checks, %d failures\n",checks,failed);return failed?1:0;}
'''
cpp=out/'offensive-source-test.cpp';cpp.write_text(stubs+header+policy+clean(source)+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'offensive-source-test.exe'
c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'offensive.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr)
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps({'returncode':r.returncode,'output':r.stdout+r.stderr,'source_sha256':hashlib.sha256((core/'CvStackingOffensiveAI.cpp').read_bytes()).hexdigest(),'scope':'Actual offensive module and pure policy, deterministic engine services. No real pathfinding, gameplay or campaign efficacy proof.'},indent=2))
sys.exit(r.returncode)
