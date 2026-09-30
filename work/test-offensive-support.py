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
 void SetToAbort(int){state=AI_OPERATION_STATE_ABORTED;}
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
namespace CvStacking {int GetCityProtection(const CvCity*,int=0){return 0;}}
namespace CvStackingAI {
 bool Enabled(int owner){return stackEnabled && !players[owner].human && CvStacking::GetInt("AIMilitaryAllocationEnabled",1)!=0;}
 int UnitStrength(const CvUnit*u){return max(u->cs,u->rs)*u->hp/u->maxhp;}
 bool RetainCityUnit(const CvUnit*u){return u->IsGarrisoned();}
}
int retaliation=20,captureDamage=1;
namespace TacticalAIHelpers {int GetSimulatedDamageFromAttackOnCity(const CvCity*city,const CvUnit*u,const CvPlot*,int&received,int&,bool=false,int=0,int extra=0,int=0,bool=false,bool=false,const CvUnit*=NULL){received=retaliation;return extra?captureDamage:u->cityShot;}}
'''
stubs=stubs.replace('const CvUnit*=NULL','const CvUnit* =NULL')
stubs=stubs.replace('using namespace std;','using namespace std;\n#define MOD_BALANCE_VP 1')
stubs=stubs.replace('CvPlot*position;CvPlot*end;UnitInfo info;','int cityShot;bool canFire,moveLegal;CvPlot*position;CvPlot*end;UnitInfo info;')
stubs=stubs.replace('position(NULL),end(NULL)','cityShot(30),canFire(true),moveLegal(true),position(NULL),end(NULL)')
stubs=stubs.replace('MOVEFLAG_SAFE_EMBARK_ONLY=32','MOVEFLAG_SAFE_EMBARK_ONLY=32,MOVEFLAG_ATTACK=64,MOVEFLAG_DESTINATION=128')
stubs=stubs.replace('bool canUseNow()const{return !processed&&!dead;}','''bool canMove()const{return !processed&&!dead;}bool isOutOfAttacks()const{return !attacks;}
 bool canMoveInto(const CvPlot&p,int=0)const{return moveLegal&&p.placeable;}
 bool canEverRangeStrikeAt(int,int,const CvPlot*,bool)const{return ranged&&canFire;}
 bool canRangeStrikeAt(int,int)const{return ranged&&canFire&&eta==0;}
 bool canUseNow()const{return !processed&&!dead;}''')
stubs=stubs.replace('bool capital,siege,fall,needs;','bool capital,siege,fall,needs,blocked;')
stubs=stubs.replace('needs(true),p(pp)','needs(true),blocked(false),p(pp)')
stubs=stubs.replace('bool isCapital()const{return capital;}','bool isCapital()const{return capital;}bool IsBlockadedWaterAndLand()const{return blocked;}int getPopulation()const{return 5;}')
stubs=stubs.replace('struct CvPlayer{','''typedef vector<pair<int,int> > SUnitIDValueContainer;
struct CvDangerPlots {int checks;CvDangerPlots():checks(0){}int GetStackDanger(const CvPlot&p,const CvUnit*u,const vector<const CvUnit*>&v,const SUnitIDValueContainer&,const SUnitIDValueContainer&){++checks;return p.route?u->danger:100;}} dangerMap;
struct CvPlayer{''')
stubs=stubs.replace('int GetID()const{return id;}int getTeam()const{return id;}','CvDangerPlots*GetDangerPlots()const{return &dangerMap;}int GetID()const{return id;}int getTeam()const{return id;}')
stubs=stubs.replace('const int MAX_PLAYERS=4,NO_PLAYER=-1,','const int NO_UNIT=-1,UNITAI_ATTACK=1,UNITAI_COUNTER=2,UNITAI_FAST_ATTACK=3,UNITAI_ATTACK_SEA=7;\nconst int MAX_PLAYERS=4,NO_PLAYER=-1,')
stubs=stubs.replace('struct CvUnitEntry{int GetDomainType()const{return DOMAIN_LAND;}};','''struct CvUnitEntry{int domain,combat,ranged,role,moves;CvUnitEntry():domain(DOMAIN_LAND),combat(30),ranged(0),role(UNITAI_DEFENSE),moves(2){}
 int GetDomainType()const{return domain;}int GetCombat()const{return combat;}int GetRangedCombat()const{return ranged;}int GetDefaultUnitAIType()const{return role;}int GetMoves()const{return moves;}};''')
stubs=stubs.replace('CvUnitEntry info;Game&','CvUnitEntry entries[8];Game&').replace('return i<0?NULL:&info;','return i<0||i>=8?NULL:&entries[i];')
stubs=stubs.replace('int domain,combat,ranged,role,moves;','int domain,combat,ranged,role,moves,range;').replace('role(UNITAI_DEFENSE),moves(2)','role(UNITAI_DEFENSE),moves(2),range(2)')
stubs=stubs.replace('int GetRangedCombat()const{return ranged;}','int GetRangedCombat()const{return ranged;}int GetRange()const{return range;}')
stubs=stubs.replace('int cityShot;bool canFire','int type,cityShot;bool canFire').replace('cityShot(30),canFire','type(0),cityShot(30),canFire')
stubs=stubs.replace('int getArmyID()const{return army;}','int getUnitType()const{return type;}void AI_setUnitAIType(int r){role=r;}int getArmyID()const{return army;}')
stubs=stubs.replace('bool IsCanAttackWithMove()const{return capture;}','bool IsCanAttackWithMove()const{return combat&&capture&&!ranged;}')
stubs=stubs.replace('namespace CvTypes{int getMISSION_MOVE_TO(){return 1;}}','namespace CvTypes{int getMISSION_MOVE_TO(){return 1;}int getMISSION_RANGE_ATTACK(){return 2;}}')
stubs=stubs.replace('int type,cityShot;bool canFire','int missionCount,lastMission,type,cityShot;bool dynamicEnd,canFire')
stubs=stubs.replace('type(0),cityShot(30),canFire','missionCount(0),lastMission(0),type(0),cityShot(30),dynamicEnd(false),canFire')
stubs=stubs.replace('bool GeneratePath(CvPlot*,int,int,int*turns=NULL){++pathCalls;if(turns)*turns=eta;return pathOK;}',
                    'bool GeneratePath(CvPlot*p,int,int,int*turns=NULL){++pathCalls;if(dynamicEnd&&!p->isCity())end=p;if(turns)*turns=eta;return pathOK;}')
stubs=stubs.replace('void PushMission(int,int,int,int,bool,bool,int){if(end){',
                    'void PushMission(int mission,int,int,int,bool,bool,int){++missionCount;lastMission=mission;if(mission==2){processed=true;return;}if(end){')
stubs=stubs.replace('struct CvDangerPlots {int checks;', 'struct CvDangerPlots {map<int,int>danger;int checks;')
stubs=stubs.replace('return p.route?u->danger:100;', 'return danger.count(p.id)?danger[p.id]:p.route?u->danger:100;')
stubs=stubs.replace('int id,owner,m_eOwner,strength,damage,maxhp;','int id,owner,m_eOwner,strength,damage,maxhp,productionType,productionTurns;')
stubs=stubs.replace('maxhp(300),capital(false)','maxhp(300),productionType(NO_UNIT),productionTurns(1),capital(false)')
stubs=stubs.replace('CvUnit*GetGarrisonedUnit()const','int getProductionUnit()const{return productionType;}int getProductionTurnsLeft()const{return productionTurns;}int getProductionTurnsLeft(int,int)const{return productionTurns;}CvUnit*GetGarrisonedUnit()const')
stubs=stubs.replace('int getProductionUnit()const','bool IsBuildingUnitForOperation()const{return productionOperation>=0;}int GetUnitProductionOperation()const{return productionOperation;}int getProductionUnit()const')
stubs=stubs.replace('maxhp,productionType,productionTurns;','maxhp,productionType,productionTurns,productionOperation;').replace('productionTurns(1),capital(false)','productionTurns(1),productionOperation(-1),capital(false)')
stubs=stubs.replace('CvCity*firstCity(int*i)','CvCity*getCity(int n)const{for(size_t i=0;i<cities.size();++i)if(cities[i]->id==n)return cities[i];return NULL;}CvCity*firstCity(int*i)')
def clean(s):return re.sub(r'^#(?:include|pragma)[^\n]*\n','',s,flags=re.M)
source=(core/'CvStackingOffensiveAI.cpp').read_text(encoding='utf-8-sig')
header=clean((core/'CvStackingOffensiveAI.h').read_text(encoding='utf-8-sig'))
policy=clean((core/'CvStackingAIPolicy.h').read_text(encoding='utf-8-sig'))
tactical=(core/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
capture_start=tactical.index('bool CvTacticalAI::TryReservedCityCapture(')
capture_end=tactical.index('\nvoid CvTacticalAI::ExecuteCaptureCityMoves()',capture_start)
capture_actual=tactical[capture_start:capture_end]
capture_harness=r'''
struct CvTacticalAI {
 CvPlayer*m_pPlayer;int commands,result;bool captureOnMove,removeOnMove;
 CvTacticalAI():m_pPlayer(&players[0]),commands(0),result(0),captureOnMove(false),removeOnMove(false){}
 bool TryReservedCityCapture(CvPlot*);
 int ExecuteMoveToPlot(CvUnit*u,CvPlot*p,bool,int){++commands;if(removeOnMove){players[0].units.erase(remove(players[0].units.begin(),players[0].units.end(),u),players[0].units.end());u->dead=true;}if(captureOnMove){p->owner=0;p->city->owner=0;}return result;}
};
'''
tests=r'''
int checks=0,failed=0;
void check(bool ok,const char*n){++checks;if(!ok){++failed;printf("FAIL: %s\n",n);}}
void put(CvUnit&u,CvPlot&p){u.position=&p;p.units.push_back(&u);players[u.owner].units.push_back(&u);GC.map.plots[p.id]=&p;}
void init(){CvStackingOffensiveAI::Reset();for(int i=0;i<MAX_PLAYERS;++i){players[i]=CvPlayer();players[i].id=i;}for(int i=0;i<8;++i)GC.entries[i]=CvUnitEntry();dangerMap.danger.clear();GC.game.turn=100;GC.map.plots.clear();options.clear();stackEnabled=true;retaliation=20;captureDamage=1;}
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
void capsTests(){init();options["AIOffensiveSupportMaximumUnits"]=18;CvPlot t(10,20),s(1,19),rear(2);CvCity city(10,&t);CvAIOperation op;CvArmyAI a;setup(op,a,t,s);CvUnit units[20];
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
 t.visible=false;++GC.game.turn;check(CvStackingOffensiveAI::ContinueSiege(0,&city),"unseen city health/occupants are not reassessed");t.visible=true;
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
void expiryProgressTests(){
 init();CvPlot t(10,20),s(1),rear(2,1),step(3,5),front(4,17);CvCity city(10,&t);CvAIOperation op;CvArmyAI a;setup(op,a,t,s);CvUnit u(40);put(u,rear);
 CvStackingOffensiveAI::ObserveOperation(&op);op.state=AI_OPERATION_STATE_SUCCESSFUL_FINISH;players[0].op=NULL;
 GC.game.turn=12;CvStackingOffensiveAI::RecordTransfer(&u,t.id,-1,1);++GC.game.turn;
 check(CvStackingOffensiveAI::HasCommitment(&u,&t),"last-memory-turn dispatch retains objective through promised arrival");
 GC.game.turn=16;u.position=&step;check(CvStackingOffensiveAI::HasCommitment(&u,&t),"real progress observed without another transfer call");
 GC.game.turn=20;u.position=&front;check(CvStackingOffensiveAI::HasCommitment(&u,&t),"progressing support reaches front without expiry");
 GC.game.turn=26;check(CvStackingOffensiveAI::HasCommitment(&u,&t),"arrived reserve remains available for shared assault");
 players[0].war=false;++GC.game.turn;check(!CvStackingOffensiveAI::HasCommitment(&u,&t),"peace releases progressed support and objective");
 CvStackingOffensiveAI::RecordTransfer(&u,t.id,-1,0);check(!CvStackingOffensiveAI::HasCommitment(&u),"dispatch cannot resurrect a peaceful objective");
}
void captureCommitmentTests(){
 init();CvPlot t(10,5),s(1),near(2,3),adj(3,4);CvCity city(10,&t);city.owner=t.owner=1;GC.map.plots[t.id]=&t;CvUnit far(1),fast(2);put(far,s);put(fast,near);far.end=fast.end=&adj;far.eta=5;fast.eta=1;
 check(CvStackingOffensiveAI::ContinueSiege(0,&city),"capture assessment maintains objective");
 check(CvStackingOffensiveAI::HasCommitment(&fast,&t),"shorter-ETA capturer reserved, not first unit iteration");
 check(!CvStackingOffensiveAI::HasCommitment(&far),"unselected candidate not claimed");
 ++GC.game.turn;CvStackingOffensiveAI::ContinueSiege(0,&city);check(CvStackingOffensiveAI::HasCommitment(&fast,&t),"valid capture commitment persists across turns");
 t.owner=0;check(!CvStackingOffensiveAI::HasCommitment(&fast),"capture invalidates reserved capturer without a dangling unit pointer");
 CvAIOperation op;CvArmyAI army;CvPlot muster(9);setup(op,army,t,muster);t.owner=0;CvStackingOffensiveAI::ObserveOperation(&op);
 check(!CvStackingOffensiveAI::HasCommitment(&fast),"operation observation cannot turn captured city into own offensive objective");players[0].op=NULL;
 t.owner=1;captureDamage=0;city.damage=290;for(int i=0;i<10;++i){++GC.game.turn;CvStackingOffensiveAI::ContinueSiege(0,&city);}
 check(!CvStackingOffensiveAI::ContinueSiege(0,&city),"surviving unit with zero city damage is not a credible capturer");captureDamage=1;
}
void assaultTests(){
 init();CvPlot target(10,10),field(1,7),adjacent(2,9);CvCity city(10,&target);city.owner=target.owner=1;city.strength=4000;target.ring.push_back(&adjacent);target.ring.push_back(&field);adjacent.route=false;GC.map.plots[target.id]=&target;
 CvUnit units[4];for(int i=0;i<4;++i){units[i].id=i+1;units[i].end=&adjacent;units[i].eta=2;put(units[i],field);if(i){units[i].ranged=true;units[i].rs=40;}}
 CvStackingOffensiveAI::ObserveSiege(0,&city);
 CvStackingOffensiveAI::AssaultPlan plan=CvStackingOffensiveAI::AssessAssault(0,&city,DOMAIN_LAND);
 check(!plan.ready&&plan.reason==2,"ordinary ranged units do not satisfy fortified assault siege requirement");
 check(plan.staging==field.id&&plan.routeKnown,"assembly selects safe reachable stage rather than attacked ring-one plot");
 check(CvStackingOffensiveAI::HoldForAssembly(&units[0],&target),"healthy safe capturer held during incomplete assembly");
 units[1].eta=0;check(!CvStackingOffensiveAI::HoldForAssembly(&units[1],&target),"useful ranged shot already available may proceed during assembly");units[1].eta=2;
 units[0].danger=80;check(!CvStackingOffensiveAI::HoldForAssembly(&units[0],&target),"endangered unit remains available for defensive or retreat actions");units[0].danger=0;
 const int before=units[0].pathCalls;CvStackingOffensiveAI::AssessAssault(0,&city,DOMAIN_LAND);check(units[0].pathCalls==before,"same-turn shared assessment does not repeat paths");
 GC.game.turn+=6;plan=CvStackingOffensiveAI::AssessAssault(0,&city,DOMAIN_LAND);check(plan.phase==2,"insufficient force enters reassessment after configured gather window");
 ++GC.game.turn;plan=CvStackingOffensiveAI::AssessAssault(0,&city,DOMAIN_LAND);check(plan.phase==2,"reassessment does not reset its gathering clock each turn");
 for(int i=1;i<4;++i)units[i].role=units[i].info.role=UNITAI_CITY_BOMBARD;
 options["AIAssaultBaseSiege"]=2;options["AIAssaultStrongCityExtraSiege"]=0;options["AIAssaultCapacityPerExtraSiege"]=10;GC.game.turn+=5;
 plan=CvStackingOffensiveAI::AssessAssault(0,&city,DOMAIN_LAND);check(!plan.ready&&plan.reason==3,"role-complete force still waits when healing defeats its damage budget");
 for(int i=0;i<4;++i)units[i].cityShot=110;GC.game.turn+=5;
 plan=CvStackingOffensiveAI::AssessAssault(0,&city,DOMAIN_LAND);check(plan.ready&&plan.phase==1,"healthy role-complete force with decisive damage commits");
 check(!CvStackingOffensiveAI::HoldForAssembly(&units[0],&target),"committed core is released to tactical attack search");
 units[0].position=&adjacent;units[0].eta=0;city.damage=299;units[0].hp=60;for(int i=1;i<4;++i)units[i].hp=30;++GC.game.turn;
 plan=CvStackingOffensiveAI::AssessAssault(0,&city,DOMAIN_LAND);check(plan.ready,"executable surviving capture bypasses gathering depleted reserves");
 target.visible=false;++GC.game.turn;check(CvStackingOffensiveAI::AssessAssault(0,&city,DOMAIN_LAND).ready,"hidden defenses retain ordinary VP scouting without hidden occupant assessment");
 target.visible=true;options["AIAssaultCoordinationEnabled"]=0;check(CvStackingOffensiveAI::AssessAssault(0,&city,DOMAIN_LAND).ready,"XML can disable coordination policy");
}
void productionTests(){
 init();CvPlot target(10,10),rear(1),field(2,8),adjacent(3,9),rear2(4,1);CvCity enemy(10,&target),producer(1,&rear),second(2,&rear2);enemy.owner=target.owner=1;enemy.strength=4000;players[0].cities.push_back(&producer);players[0].cities.push_back(&second);GC.map.plots[target.id]=&target;
 GC.entries[1].role=UNITAI_CITY_BOMBARD;GC.entries[1].ranged=40;GC.entries[2].role=UNITAI_DEFENSE;GC.entries[2].ranged=40;
 CvUnit core[4];for(int i=0;i<4;++i){core[i].id=i+1;core[i].end=&adjacent;put(core[i],field);}CvStackingOffensiveAI::ObserveSiege(0,&enemy);
 check(CvStackingOffensiveAI::ProductionBonus(&producer,(UnitTypes)1)>0,"fortified objective requests true siege beyond its current melee core");
 check(!CvStackingOffensiveAI::ProductionBonus(&producer,(UnitTypes)0),"extra generic melee cannot replace missing siege role");
 options["AIOffensiveProductionMaximumUnits"]=1;producer.productionType=1;CvStackingOffensiveAI::RecordProduction(&producer,(UnitTypes)1);
 check(!CvStackingOffensiveAI::ProductionBonus(&second,(UnitTypes)1),"single pending claim prevents duplicate over-cap production in another city");
 CvStackingOffensiveAI::RecordProduction(&producer,(UnitTypes)1);check(production.size()==1,"repeated chosen production maintains one exclusive city claim");
 CvUnit replacement(40);replacement.type=1;replacement.ranged=true;replacement.rs=40;replacement.role=replacement.info.role=UNITAI_CITY_BOMBARD;put(replacement,rear);
 CvStackingOffensiveAI::UnitProduced(&producer,&replacement);
 check(production.empty()&&CvStackingOffensiveAI::HasCommitment(&replacement,&target),"completion transfers pending credit to actual unit objective exactly once");
 producer.productionType=NO_UNIT;check(CvStackingOffensiveAI::ProductionBonus(&second,(UnitTypes)1)>0,"delivered reserve permits next proactive replacement");
 second.productionType=1;CvStackingOffensiveAI::RecordProduction(&second,(UnitTypes)1);players[0].war=false;++GC.game.turn;
 check(!CvStackingOffensiveAI::ProductionBonus(&producer,(UnitTypes)1),"peace cancels offensive production demand");
 init();target.owner=enemy.owner=1;players[0].cities.push_back(&producer);GC.map.plots[target.id]=&target;CvStackingOffensiveAI::ObserveSiege(0,&enemy);producer.productionTurns=13;
 check(!CvStackingOffensiveAI::ProductionBonus(&producer,(UnitTypes)0),"production beyond configured completion horizon rejected");
}
void stagedReserveTests(){
 init();CvPlot target(10,10),stage(1,4),adjacent(2,9);CvCity enemy(10,&target);enemy.owner=target.owner=1;enemy.strength=4000;GC.map.plots[target.id]=&target;target.ring.push_back(&adjacent);target.ring.push_back(&stage);adjacent.route=false;
 CvUnit units[4];for(int i=0;i<4;++i){units[i].id=i+1;units[i].end=&adjacent;units[i].eta=3;put(units[i],stage);if(i){units[i].ranged=true;units[i].rs=40;}CvStackingOffensiveAI::RecordTransfer(&units[i],target.id,-1,3);}
 CvStackingOffensiveAI::AssaultPlan plan=CvStackingOffensiveAI::AssessAssault(0,&enemy,DOMAIN_LAND);check(!plan.ready&&plan.staging==stage.id,"loose objective stages outside old local-force radius");
 ++GC.game.turn;check(CvStackingOffensiveAI::HasCommitment(&units[0]),"first assembly arrival retains reserved capturer");GC.game.turn+=7;
 check(CvStackingOffensiveAI::HasCommitment(&units[0]),"bounded gathering retains stationary safe staged unit beyond old five-turn stall");
 check(!CvStackingOffensiveAI::JoinArrived(&units[0]),"post-handoff assembly cannot recruit through a missing live operation");
 check(CvStackingOffensiveAI::HoldReserve(&units[0])&&units[0].processed,"post-handoff reserve remains staged without a live army");units[0].processed=false;
 vector<CvStackingOffensiveAI::TacticalForce> forces;CvStackingOffensiveAI::TacticalForces(0,forces);check(forces.size()==1&&forces[0].units.size()==4,"loose staged core has an explicit objective movement cohort");
 GC.game.turn=126;CvStackingOffensiveAI::ReviewObjectives(0);
 check(!CvStackingOffensiveAI::HasCommitment(&units[0]),"abandoned assault releases safe static reserves after bounded no-progress interval");
 check(CvStackingOffensiveAI::RouteBlocked(0,&target,false),"abandonment prevents immediate duplicate objective recreation");
 check(!CvStackingOffensiveAI::AssessAssault(0,&enemy,DOMAIN_LAND).ready,"abandonment cooldown does not fall through to an unsupported assault");
}
void preparationProductionTests(){
 init();CvPlot target(10,6),muster(1),adjacent(2,5);CvCity enemy(10,&target),factory(20,&muster);enemy.owner=target.owner=1;enemy.strength=4000;players[0].cities.push_back(&factory);CvAIOperation op;CvArmyAI army;setup(op,army,target,muster);players[0].war=false;
 CvUnit core[5];for(int i=0;i<5;++i){core[i].id=i+1;core[i].army=army.id;put(core[i],muster);army.slots.push_back(CvArmyFormationSlot(core[i].id));}core[4].ranged=true;core[4].rs=40;
 CvStackingOffensiveAI::ObserveOperation(&op);GC.entries[1].role=UNITAI_CITY_BOMBARD;GC.entries[1].ranged=40;
 check(!CvStackingOffensiveAI::OpeningReady(&op,&army),"voluntary fortified-city war waits for a staged true siege battery");
 CvUnit siege[5];for(int i=0;i<5;++i){factory.productionType=1;CvStackingOffensiveAI::RecordProduction(&factory,(UnitTypes)1);siege[i].id=i+20;siege[i].type=1;siege[i].ranged=true;siege[i].rs=40;siege[i].info.role=UNITAI_CITY_BOMBARD;siege[i].end=&adjacent;put(siege[i],muster);CvStackingOffensiveAI::UnitProduced(&factory,&siege[i]);factory.productionType=NO_UNIT;}
 check(CvStackingOffensiveAI::HasCommitment(&siege[0],&target),"prewar production delivers a reserve to its existing live preparation objective");
 check(CvStackingOffensiveAI::OpeningReady(&op,&army),"staged committed siege outside a full formation contributes to the opening force");
 options["AIOffensiveProductionMaximumUnits"]=1;factory.productionType=1;factory.productionOperation=op.id;
 CvStackingOffensiveAI::RecordProduction(&factory,(UnitTypes)1);check(production.empty(),"VP formation promise cannot receive a duplicate support-production claim");
 CvPlot rear(30,1);CvCity other(30,&rear);players[0].cities.push_back(&other);
 check(!CvStackingOffensiveAI::ProductionBonus(&other,(UnitTypes)1),"existing queued formation siege is credited to role and production allowance");
}
void stagePlacementTests(){
 init();CvPlot target(10,10),rear(2),stage(1,4),adjacent(3,9);CvCity enemy(10,&target);enemy.owner=target.owner=1;enemy.strength=4000;GC.map.plots[target.id]=&target;GC.map.plots[stage.id]=&stage;target.ring.push_back(&stage);target.ring.push_back(&adjacent);dangerMap.danger[rear.id]=80;dangerMap.danger[stage.id]=0;dangerMap.danger[adjacent.id]=100;
 CvUnit unit(1);put(unit,rear);unit.end=&adjacent;unit.eta=3;CvStackingOffensiveAI::RecordTransfer(&unit,target.id,-1,3);
 check(CvStackingOffensiveAI::AssessAssault(0,&enemy,DOMAIN_LAND).staging==stage.id,"assembly fixture selects explicit safe slot");
 unit.dynamicEnd=true;check(CvStackingOffensiveAI::StageUnit(&unit,&target)&&unit.position==&stage&&unit.processed,"gathering moves to safe slot instead of approximate exposed ring");
 unit.processed=false;int commands=unit.missionCount;check(CvStackingOffensiveAI::StageUnit(&unit,&target)&&unit.missionCount==commands,"safe cohesive arrival is held without repeat movement");
 unit.position=&rear;unit.processed=false;assaultQueries[0]=64;commands=unit.missionCount;
 check(!CvStackingOffensiveAI::StageUnit(&unit,&target)&&unit.missionCount==commands,"exhausted placement budget cannot issue unsupported movement");
 unit.position=NULL;check(!CvStackingOffensiveAI::CanCapture(&unit,&target),"unit without map location cannot become capture candidate");unit.position=&rear;unit.hp=0;
 check(!CvStackingOffensiveAI::StageUnit(&unit,&target),"zero-health transitional unit cannot receive assembly orders");
 init();CvPlot cityPlot(20,4),water(21,2);cityPlot.coastal=true;water.water=true;CvCity city(20,&cityPlot);city.owner=cityPlot.owner=1;cityPlot.ring.push_back(&water);GC.map.plots[cityPlot.id]=&cityPlot;CvUnit ship(1);ship.domain=DOMAIN_SEA;ship.ranged=true;ship.rs=40;ship.eta=0;ship.end=&water;put(ship,water);
 check(CvStackingOffensiveAI::StageUnit(&ship,&cityPlot)&&ship.lastMission==2,"gathering preserves safe legal naval bombardment already available");
}
void captureOrderTests(){
 init();CvPlot target(10,5),adjacent(1,4),far(2,2);CvCity city(10,&target);city.owner=target.owner=1;city.damage=290;GC.map.plots[target.id]=&target;CvUnit unit(1);unit.end=&adjacent;unit.eta=0;put(unit,adjacent);CvStackingOffensiveAI::ContinueSiege(0,&city);CvTacticalAI tactical;
 unit.cityShot=9;check(!tactical.TryReservedCityCapture(&target)&&!tactical.commands,"capture order waits for sufficient actual city damage");
 unit.cityShot=10;check(tactical.TryReservedCityCapture(&target)&&tactical.commands==1,"actual softening permits reserved capture command independently of gathering forecast");
 city.damage=300;unit.cityShot=0;check(tactical.TryReservedCityCapture(&target),"zero-HP city still permits legal melee capture with zero further damage");
 int before=tactical.commands;unit.moveLegal=false;check(!tactical.TryReservedCityCapture(&target)&&tactical.commands==before,"illegal final city entry cannot issue command");unit.moveLegal=true;
 unit.attacks=false;check(!tactical.TryReservedCityCapture(&target),"used attack allowance blocks duplicate capture");unit.attacks=true;
 unit.processed=true;check(!tactical.TryReservedCityCapture(&target),"processed unit cannot be reused for capture");unit.processed=false;
 retaliation=100;check(!tactical.TryReservedCityCapture(&target),"lethal current retaliation rejects capture command");retaliation=20;
 unit.position=&far;check(!tactical.TryReservedCityCapture(&target),"distant cached candidate is not an executable capturer");unit.position=&adjacent;
 unit.ranged=true;check(!tactical.TryReservedCityCapture(&target),"ranged-only actor cannot execute melee capture");unit.ranged=false;
 target.owner=0;check(!tactical.TryReservedCityCapture(&target),"already-owned city cannot receive hostile capture order");target.owner=1;
 check(!tactical.TryReservedCityCapture(NULL),"null target rejected");tactical.result=INT_MAX;check(!tactical.TryReservedCityCapture(&target),"failed movement not reported as issued capture");tactical.result=0;
 tactical.removeOnMove=true;check(tactical.TryReservedCityCapture(&target),"callback removal does not leave a post-command unit dereference");check(!tactical.TryReservedCityCapture(&target),"deleted cached capturer cannot be reused");
 check(EntryCapture(&GC.entries[0]),"ordinary melee build recognized as capturing role");GC.entries[0].ranged=8;GC.entries[0].range=0;
 check(EntryCapture(&GC.entries[0])&&!EntryRanged(&GC.entries[0]),"unique zero-range support fire does not mask melee capture capability");
}
void emptyApproximatePathTests(){
 init();CvPlot target(10,5),adjacent(1,4),firing(2,3);CvCity city(10,&target);city.owner=target.owner=1;GC.map.plots[target.id]=&target;CvUnit capturer(1),archer(2);put(capturer,adjacent);put(archer,firing);capturer.end=archer.end=NULL;archer.ranged=true;archer.rs=40;
 CvStackingOffensiveAI::ContinueSiege(0,&city);
 check(CvStackingOffensiveAI::GetReservedCapturer(0,&city)==&capturer,"zero-node approximate path preserves already-adjacent capturer");
 const CvStackingOffensiveAI::AssaultPlan plan=CvStackingOffensiveAI::AssessAssault(0,&city,DOMAIN_LAND);
 check(plan.readyUnits==2&&plan.ranged==1,"already-positioned melee and ranged units count despite empty successful path");
 capturer.position=&firing;capturer.end=NULL;archer.canFire=false;++GC.game.turn;CvStackingOffensiveAI::ContinueSiege(0,&city);
 check(!CvStackingOffensiveAI::GetReservedCapturer(0,&city),"empty endpoint cannot invent adjacent approach for a distant unit");
}
void reassignmentTests(){
 init();CvPlot target(10,5),other(20,8),stage(1);CvCity enemy(10,&target),another(20,&other);enemy.owner=target.owner=1;another.owner=other.owner=1;GC.map.plots[target.id]=&target;CvUnit unit(1);put(unit,stage);CvStackingOffensiveAI::RecordTransfer(&unit,target.id,-1,2);check(CvStackingOffensiveAI::HasCommitment(&unit),"free support initially reserved");
 CvAIOperation op;CvArmyAI army;setup(op,army,other,stage);unit.army=army.id;
 check(!CvStackingOffensiveAI::HasCommitment(&unit,&target),"new army targeting another city immediately supersedes old support commitment");
 ++GC.game.turn;CvStackingOffensiveAI::HasCommitment(&unit);check(commitments.empty(),"refresh releases reassigned operation duty without waiting for movement stall");
}
int main(){policyTests();routeTests();openingTests();supportTests();capsTests();captureTests();navalTests();marchTests();expiryProgressTests();captureCommitmentTests();assaultTests();productionTests();stagedReserveTests();preparationProductionTests();stagePlacementTests();captureOrderTests();emptyApproximatePathTests();reassignmentTests();printf("offensive support: %d checks, %d failures\n",checks,failed);return failed?1:0;}
'''
cpp=out/'offensive-source-test.cpp';cpp.write_text(stubs+header+policy+clean(source)+capture_harness+capture_actual+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'offensive-source-test.exe'
c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'offensive.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr)
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps({'returncode':r.returncode,'output':r.stdout+r.stderr,'source_sha256':hashlib.sha256((core/'CvStackingOffensiveAI.cpp').read_bytes()).hexdigest(),'capture_helper_sha256':hashlib.sha256(capture_actual.encode()).hexdigest(),'scope':'Actual offensive module, capture execution helper and pure policy, deterministic engine services. No real pathfinding, gameplay or campaign efficacy proof.'},indent=2))
sys.exit(r.returncode)
