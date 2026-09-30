"""Compile the actual allocation module with deterministic engine services (native VC9).

No game process interaction. This checks policies/control flow, not real engine pathfinding.
"""
from pathlib import Path
import hashlib, json, os, re, subprocess, sys, xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
out=root/'work/military-allocation-regression';out.mkdir(exist_ok=True)
core=root/'CvGameCoreDLL_Expansion2'
source=(core/'CvStackingAI.cpp').read_text(encoding='utf-8-sig')
actual=re.sub(r'^#include[^\n]*\n','',source,flags=re.M)
def body(file,signature):
    text=(core/file).read_text(encoding='utf-8-sig')
    start=text.index(signature);opened=text.index('{',start);depth=1;end=opened+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
placement=body('CvCity.cpp','CvPlot* CvCity::GetPlotForNewUnit(')
muster=body('CvMilitaryAI.cpp','bool CvMilitaryAI::IsPossibleMusterCity(')
gather=body('CvAIOperation.cpp','int CvAIOperation::GetGatherTolerance(')
header=re.sub(r'^#(?:pragma|include)[^\n]*\n','',(core/'CvStackingAI.h').read_text(encoding='utf-8-sig'),flags=re.M)
policy=(core/'CvStackingAIPolicy.h').read_text(encoding='utf-8-sig').replace('#pragma once','')
settings=dict((n,int(v)) for n,v,lo,hi in re.findall(r'\{"(AI[^" ]+)", (\d+), (\d+), (\d+)\}',(core/'CvStackingRules.cpp').read_text(encoding='utf-8-sig')))
default_settings='\n'.join('options["%s"]=%d;'%(n,v) for n,v in settings.items())
xml=ET.parse(root/'(1) Community Patch/Database Changes/StackingConfig.xml')
xml_rows=xml.findall('./Stacking_Settings/Row')
xml_settings={r.get('Name'):int(r.get('Value')) for r in xml_rows}
assert len(xml_settings)==len(xml_rows), 'Duplicate XML settings'
for name in set(re.findall(r'Setting\("([^"]+)"',source)):
    assert name in settings and settings[name]==xml_settings[name], name

stubs=r'''
#include <vector>
#include <map>
#include <set>
#include <string>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <climits>
using namespace std;
typedef int PlayerTypes;typedef int TeamTypes;typedef int DomainTypes;typedef int UnitTypes;typedef int ArmyType;typedef int UnitAITypes;typedef unsigned int uint;
#define VALIDATE_OBJECT()
const int MAX_PLAYERS=4,NO_PLAYER=-1,DOMAIN_LAND=2,DOMAIN_SEA=0,DOMAIN_AIR=1,ISHUMAN_AI_UNITS=1;
#define GD_INT_GET(name) 70
const int UNITAI_CITY_BOMBARD=4,UNITAI_EXPLORE=10,UNITAI_DEFENSE=6;
const int ARMYAISTATE_WAITING_FOR_UNITS_TO_REINFORCE=0,ARMYAISTATE_WAITING_FOR_UNITS_TO_CATCH_UP=1,ARMYAISTATE_MOVING_TO_DESTINATION=2;
const int AI_OPERATION_STATE_ABORTED=6,AI_OPERATION_STATE_SUCCESSFUL_FINISH=5,MISSIONAI_TACTMOVE=1,RING2_PLOTS=19,RING1_PLOTS=7,ARMY_TYPE_ANY=-1;
struct Seed{int mix(int)const{return 0;}};
struct CvUnit;struct CvCity;struct CvArmyAI;struct CvAIOperation;
struct CvPlot{
 int id,x,y,owner;bool visible,revealed,coastal,placeable,route,water,deep;CvCity* city;vector<CvUnit*> units;vector<CvPlot*> ring;
 CvPlot(int n=0,int xx=0,int yy=0):id(n),x(xx),y(yy),owner(0),visible(true),revealed(true),coastal(false),placeable(true),route(true),water(false),deep(false),city(NULL){}
 int GetPlotIndex()const{return id;}int getX()const{return x;}int getY()const{return y;}int getOwner()const{return owner;}
 int getNumUnits()const{return (int)units.size();}CvUnit* getUnitByIndex(int i)const{return units[i];}
 bool isVisible(int)const{return visible;}bool isRevealed(int)const{return revealed;}bool isCity()const{return city!=NULL;}
 CvCity*getPlotCity()const{return city;}bool isCoastalLand()const{return coastal;}
 Seed GetPseudoRandomSeed()const{return Seed();}bool isValidRoute(void*)const{return route;}int GetNumEnemyUnitsAdjacent(int,int)const{return 0;}
 bool isWater()const{return water;}bool isDeepWater()const{return deep;}bool canPlaceCombatUnit(int)const{return placeable;}
};
struct UnitInfo{int role;UnitInfo():role(UNITAI_DEFENSE){}int GetDefaultUnitAIType()const{return role;}};
struct CvUnit{
 enum {MOVEFLAG_APPROX_TARGET_RING2=1,MOVEFLAG_APPROX_TARGET_NATIVE_DOMAIN=2,MOVEFLAG_NO_EMBARK=4,MOVEFLAG_AI_ABORT_IN_DANGER=8};
 int id,owner,domain,hp,maxhp,cs,rs,range,army,role,danger,eta,clears,pathCalls;bool combat,cargo,dead,stacking,embarked,invisible,ranged,attacks,capture,heal,cover,processed,pathOK,canOperation;
 CvPlot*position;CvPlot*end;UnitInfo info;
 CvUnit(int n=1):id(n),owner(0),domain(DOMAIN_LAND),hp(100),maxhp(100),cs(30),rs(0),range(2),army(-1),role(UNITAI_DEFENSE),danger(0),eta(1),clears(0),pathCalls(0),combat(true),cargo(false),dead(false),stacking(false),embarked(false),invisible(false),ranged(false),attacks(true),capture(true),heal(false),cover(false),processed(false),pathOK(true),canOperation(true),position(NULL),end(NULL){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getDomainType()const{return domain;}
 int GetCurrHitPoints()const{return hp;}int GetMaxHitPoints()const{return maxhp;}int GetBaseCombatStrength()const{return cs;}int GetBaseRangedCombatStrength()const{return rs;}
 bool IsCombatUnit()const{return combat;}bool isCargo()const{return cargo;}bool isDelayedDeath()const{return dead;}bool IsStackingUnit()const{return stacking;}
 bool isEmbarked()const{return embarked;}bool isInvisible(int,bool)const{return invisible;}bool IsCanAttack()const{return attacks;}
 bool IsCanAttackRanged()const{return ranged;}int GetRange()const{return range;}int AI_getUnitAIType()const{return role;}const UnitInfo&getUnitInfo()const{return info;}
 int getArmyID()const{return army;}bool IsCanAttackWithMove()const{return capture;}bool isNoCapture()const{return !capture;}
 CvPlot*plot()const{return position;}bool IsGarrisoned()const;bool shouldHeal(bool)const{return heal;}int GetDanger(const CvPlot*p=NULL)const{return danger;}
 bool canUseNow()const{return !processed&&!dead;}bool IsCoveringFriendlyCivilian()const{return cover;}bool canUseForAIOperation()const{return canOperation;}
 void ClearPathCache(){++clears;}int TurnsToReachTarget(CvPlot*,int,int){++pathCalls;return eta;}
 bool GeneratePath(CvPlot*,int,int){return pathOK;}CvPlot*GetPathEndFirstTurnPlot(){return end;}
 void PushMission(int,int,int,int,bool,bool,int){if(end){vector<CvUnit*>&v=position->units;v.erase(remove(v.begin(),v.end(),this),v.end());position=end;end->units.push_back(this);}}
 void SetTurnProcessed(bool b){processed=b;}
};
struct CvCity{
 int id,owner,m_eOwner,strength,damage,maxhp;bool capital,siege,fall,needs;CvPlot*p;CvUnit*garrison;
 CvCity(int n,CvPlot*pp):id(n),owner(0),m_eOwner(0),strength(2000),damage(0),maxhp(300),capital(false),siege(false),fall(false),needs(true),p(pp),garrison(NULL){pp->city=this;}
 int GetID()const{return id;}int getOwner()const{return owner;}CvPlot*plot()const{return p;}
 CvUnit*GetGarrisonedUnit()const{return garrison;}bool NeedsGarrison()const{return needs;}bool isUnderSiege()const{return siege;}bool isInDangerOfFalling()const{return fall;}
 int getStrengthValue()const{return strength;}int GetMaxHitPoints()const{return maxhp;}int getDamage()const{return damage;}bool isCapital()const{return capital;}
 int getTeam()const{return owner;}CvPlot* GetPlotForNewUnit(UnitTypes,bool)const;
};
bool CvUnit::IsGarrisoned()const{return position&&position->city&&position->city->garrison==this;}
struct CvArmyFormationSlot{int id;bool required;CvArmyFormationSlot(int i=-1,bool r=true):id(i),required(r){}bool IsUsed()const{return id>=0;}bool IsRequired()const{return required;}int GetUnitID()const{return id;}};
struct CvArmyAI{
 int id,op,owner,state,domain;CvPlot*center;vector<CvArmyFormationSlot>slots;
 CvArmyAI():id(1),op(1),owner(0),state(0),domain(DOMAIN_LAND),center(NULL){}
 int GetID()const{return id;}int GetOperationID()const{return op;}int GetArmyAIState()const{return state;}int GetDomainType()const{return domain;}
 int GetOwner()const{return owner;}bool IsAllOceanGoing()const{return true;}
 const vector<CvArmyFormationSlot>&GetSlotStatus()const{return slots;}int GetNumFormationEntries()const{return (int)slots.size();}
 int GetNumSlotsFilled()const{int n=0;for(size_t i=0;i<slots.size();++i)n+=slots[i].IsUsed();return n;}
 CvPlot*GetCenterOfMass(bool){return center;}int GetFurthestUnitDistance(CvPlot*);
 CvUnit*GetFirstUnit();CvUnit*GetNextUnit(CvUnit*);
};
struct CvAIOperation{
 int id,owner,enemy,started,state;bool offensive;CvPlot*target;CvPlot*muster;
 CvAIOperation():id(1),owner(0),enemy(1),started(0),state(0),offensive(true),target(NULL),muster(NULL){}
 int GetOwner()const{return owner;}int GetID()const{return id;}int GetEnemy()const{return enemy;}int GetTurnStarted()const{return started;}
 int GetOperationState(){return state;}bool IsOffensive()const{return offensive;}CvPlot*GetTargetPlot()const{return target;}CvPlot*GetMusterPlot()const{return muster;}
 int GetGatherTolerance(CvArmyAI*,CvPlot*)const;bool IsNavalOperation()const{return false;}
};
struct CvPlayer{
 int id;bool human,barbarian,early,war;vector<CvUnit*>units,attackers;vector<CvCity*>cities;vector<CvArmyAI*>armies;CvAIOperation*op;
 CvPlayer():id(0),human(false),barbarian(false),early(false),war(true),op(NULL){}
 int GetID()const{return id;}int getTeam()const{return id;}bool isBarbarian()const{return barbarian;}bool isHuman(int)const{return human;}bool IsEarlyExpansionPhase()const{return early;}
 bool IsAtWarWith(int p)const{return war&&p!=id;}bool IsAtWarAnyMajor()const{return war;}bool IsAtWarAnyMinor()const{return false;}
 vector<CvUnit*>GetPossibleAttackers(const CvPlot&,int){return attackers;}
 CvUnit*getUnit(int n)const{for(size_t i=0;i<units.size();++i)if(units[i]->id==n)return units[i];return NULL;}
 CvCity*firstCity(int*i){*i=0;return cities.empty()?NULL:cities[0];}CvCity*nextCity(int*i){++*i;return *i<(int)cities.size()?cities[*i]:NULL;}
 CvArmyAI*firstArmyAI(int*i){*i=0;return armies.empty()?NULL:armies[0];}CvArmyAI*nextArmyAI(int*i){++*i;return *i<(int)armies.size()?armies[*i]:NULL;}
 CvAIOperation*getAIOperation(int n){return op&&op->id==n?op:NULL;}
 int getNumUnits()const{return (int)units.size();}
 CvUnit*firstUnit(int*i){*i=0;return units.empty()?NULL:units[0];}CvUnit*nextUnit(int*i){++*i;return *i<(int)units.size()?units[*i]:NULL;}
 int GetNumOffensiveOperations(int domain)const{int count=0;for(size_t i=0;i<armies.size();++i)if(armies[i]->domain==domain)++count;return count;}
 bool CanCrossOcean()const{return true;}
}players[MAX_PLAYERS];
#define GET_PLAYER(n) players[n]
int plotDistance(const CvPlot&a,const CvPlot&b){return max(abs(a.x-b.x),abs(a.y-b.y));}
CvPlot*iterateRingPlots(const CvPlot*p,int i){if(i==0)return const_cast<CvPlot*>(p);return i<=(int)p->ring.size()?p->ring[i-1]:NULL;}
CvUnit*CvArmyAI::GetFirstUnit(){for(size_t i=0;i<slots.size();++i)if(slots[i].IsUsed())return players[owner].getUnit(slots[i].id);return NULL;}
CvUnit*CvArmyAI::GetNextUnit(CvUnit*u){bool seen=false;for(size_t i=0;i<slots.size();++i){if(seen&&slots[i].IsUsed())return players[owner].getUnit(slots[i].id);if(slots[i].id==u->id)seen=true;}return NULL;}
int CvArmyAI::GetFurthestUnitDistance(CvPlot*p){if(!p)return INT_MAX;int d=0;for(CvUnit*u=GetFirstUnit();u;u=GetNextUnit(u))d=max(d,plotDistance(*u->plot(),*p));return d;}
struct CvUnitEntry{int GetDomainType()const{return DOMAIN_LAND;}};
bool IsValidPlotForUnitType(CvPlot*p,int,CvUnitEntry*){return p->placeable;}
struct Game{int turn;Game():turn(100){}int getGameTurn()const{return turn;}uint urandLimitExclusive(int,int){return 0;}};
struct Map{map<int,CvPlot*>plots;CvPlot*plotByIndexUnchecked(int n){return plots[n];}};
struct Globals{Game game;Map map;CvUnitEntry info;Game&getGame(){return game;}Map&getMap(){return map;}CvUnitEntry*getUnitInfo(int i){return i<0?NULL:&info;}}GC;
struct AttackTarget{int m_armyType;CvPlot*p;AttackTarget(CvPlot*pp,int t):m_armyType(t),p(pp){}CvPlot*GetMusterPlot()const{return p;}};
struct CvMilitaryAI{CvPlayer*m_pPlayer;vector<AttackTarget>m_potentialAttackTargets;bool IsPossibleMusterCity(const CvCity*,ArmyType)const;};
namespace CvTypes{int getMISSION_MOVE_TO(){return 1;}}
map<string,int>options;bool stackEnabled=true;int capacity=5;
namespace CvStacking{
 bool IsEnabled(){return stackEnabled;}int GetInt(const char*n,int f){return options.count(n)?options[n]:f;}int GetCapacity(int,int,bool){return capacity;}
 int GetCollateralTargetLimit(const CvUnit*u){return u->role==UNITAI_CITY_BOMBARD?2:0;}bool IsAntiCavalry(const CvUnit*u){return u->role==UNITAI_DEFENSE;}bool CanFlank(const CvUnit*u){return u->role==5;}
}
namespace CvStackingDiagnostics{bool enabled=true;int records=0;void Record(int,int,const char*,const char*,...){if(enabled)++records;}}
'''

tests=r'''
int checks=0,failures=0;
void check(bool ok,const char*name){++checks;if(!ok){++failures;printf("FAIL %s\n",name);}}
void put(CvUnit&u,CvPlot&p){u.position=&p;p.units.push_back(&u);players[u.owner].units.push_back(&u);GC.map.plots[p.id]=&p;}
void reset(){CvStackingAI::Reset();for(int i=0;i<MAX_PLAYERS;++i){players[i]=CvPlayer();players[i].id=i;}GC.game.turn=100;GC.map.plots.clear();capacity=5;stackEnabled=true;options.clear();DEFAULTS}
void policyTests(){using namespace CvStackingAIPolicy;
 check(!BetterGarrison(100,100,0),"equal garrison never churns");check(!BetterGarrison(100,119,20),"below improvement threshold");check(BetterGarrison(100,120,20),"exact improvement threshold");
 check(ReachedDefense(1,30,1,3,0),"one safe defender sufficient");check(!ReachedDefense(1,30,1,3,60),"strength deficit needs another");check(ReachedDefense(3,90,1,3,150),"defender cap respected");
 check(!ReachedDefense(0,0,1,3,0),"minimum matters without threat");check(ReachedDefense(0,0,0,0,10),"disabled domain never retained");
 check(CoreReady(4,5,1,4,75,1,true,true,60,40,150),"viable incomplete formation");
 check(!CoreReady(4,5,1,4,75,1,false,true,60,40,150),"no capture unit cannot depart");
 check(!CoreReady(4,5,1,4,75,1,true,false,60,40,150),"missing fire support cannot depart");
 check(!CoreReady(4,5,1,4,75,1,true,true,59,40,150),"strength margin required");
 check(!CoreReady(4,6,2,4,75,1,true,true,100,40,150),"too many missing required slots");
 check(IsStationary(1,1,1,1),"ETA one can be stalled");check(!IsStationary(1,2,1,1),"actual movement counts");check(!IsStationary(1,1,2,1),"improved ETA counts");
 check(ScoreDemand(300,30,4,15,false,40)>ScoreDemand(200,30,4,15,false,40),"equal travel favors urgent defense");
 check(ScoreDemand(200,30,2,15,true,40)>ScoreDemand(200,30,2,15,false,40),"continuity favors same task");}
void cityTests(){reset();CvPlot cplot(0),enemyPlot(1,1),outside(2,2);CvCity city(1,&cplot);players[0].cities.push_back(&city);cplot.ring.push_back(&enemyPlot);
 CvUnit a(1),b(2),c(3),outsideUnit(4),e(5);put(a,cplot);put(b,cplot);put(c,cplot);put(outsideUnit,outside);city.garrison=&a;
 check(CvStackingAI::RetainCityUnit(&a),"actual safe garrison retained");check(!CvStackingAI::RetainCityUnit(&b)&&!CvStackingAI::RetainCityUnit(&c),"healthy duplicate defenders released");
 check(!CvStackingAI::NeedsCityDefender(&city),"safe three-unit city needs no recruit");check(!CvStackingAI::UsefulGarrison(&b,&city),"same tile gives no extra defense");check(!CvStackingAI::UsefulGarrison(&outsideUnit,&city),"rear city stops replacement search");
 e.owner=1;e.cs=100;put(e,enemyPlot);players[0].attackers.push_back(&e);++GC.game.turn;
 check(CvStackingAI::AssessCity(&city).immediate==1,"known reachable attacker used");
 check(CvStackingAI::RetainCityUnit(&a)&&!CvStackingAI::RetainCityUnit(&b)&&!CvStackingAI::RetainCityUnit(&c),"passive melee duplicates not all retained against strong threat");
 check(CvStackingAI::NeedsCityDefender(&city)&&CvStackingAI::WantsRangedDefender(&city),"melee-only city requests missing ranged role despite occupied slots");
 options["AICityRoleDefenseEnabled"]=0;++GC.game.turn;check(CvStackingAI::RetainCityUnit(&a)&&CvStackingAI::RetainCityUnit(&b)&&CvStackingAI::RetainCityUnit(&c)&&!CvStackingAI::NeedsCityDefender(&city),"XML-disabled role policy retains legacy capacity/strength behavior");options["AICityRoleDefenseEnabled"]=1;
 e.invisible=true;++GC.game.turn;check(CvStackingAI::AssessCity(&city).enemyStrength==0,"invisible attackers not read");
 e.invisible=false;enemyPlot.visible=false;players[0].attackers.clear();++GC.game.turn;check(CvStackingAI::AssessCity(&city).enemyStrength==0,"hidden nearby units ignored");
 enemyPlot.visible=true;++GC.game.turn;check(CvStackingAI::AssessCity(&city).nearby==1&&CvStackingAI::AssessCity(&city).enemyStrength==35,"uncertain approach is discounted");
 players[0].war=false;++GC.game.turn;check(CvStackingAI::AssessCity(&city).enemyStrength==0,"peace-time units not immediate enemies");
 a.hp=10;++GC.game.turn;check(!CvStackingAI::RetainCityUnit(&a)&&CvStackingAI::RetainCityUnit(&b),"healthy defender substitutes wounded garrison");
 b.army=1;++GC.game.turn;check(CvStackingAI::RetainCityUnit(&c)&&!CvStackingAI::RetainCityUnit(&b),"available defender frees army member");
 c.domain=DOMAIN_SEA;++GC.game.turn;check(!CvStackingAI::RetainCityUnit(&c),"safe-city ships not land reserves");
 players[0].early=true;++GC.game.turn;check(!CvStackingAI::RetainCityUnit(&a)&&!CvStackingAI::RetainCityUnit(&b),"early expansion releases baseline");
 players[0].early=false;capacity=1;city.siege=true;++GC.game.turn;check(CvStackingAI::AssessCity(&city).landMinimum==1&&CvStackingAI::AssessCity(&city).landMaximum==1,"emergency floor respects capacity one");
 stackEnabled=false;check(CvStackingAI::RetainCityUnit(&a)&&!CvStackingAI::RetainCityUnit(&b),"disabled allocation preserves legacy garrison predicate");
 stackEnabled=true;players[0].human=true;check(!CvStackingAI::Enabled(0),"human orders excluded");players[0].human=false;players[0].barbarian=true;check(!CvStackingAI::Enabled(0),"barbarians excluded");
}
void progressTests(){reset();CvPlot from(0,0),muster(1,10),target(2,15),moved(3,1);CvUnit u(1);put(u,from);CvArmyAI army;CvAIOperation op;op.muster=&muster;op.target=&target;players[0].op=&op;
 for(int t=0;t<=6;++t){GC.game.turn=100+t;bool released=CvStackingAI::ArmyUnitStalled(&u,&army,&muster,1);check(released==(t==6),"stationary ETA-one recovery grace");}
 check(u.clears==1,"path cleared once before release");
 CvStackingAI::DelayRecruitment(&u,&target);check(CvStackingAI::RecruitmentBlocked(&u,&target),"failed assignment cooldown begins");check(!CvStackingAI::RecruitmentBlocked(&u,&muster),"different objective still eligible");
 GC.game.turn+=4;check(!CvStackingAI::RecruitmentBlocked(&u,&target),"cooldown expires");
 CvStackingAI::Reset();u.clears=0;for(int t=0;t<8;++t){GC.game.turn=120+t;u.position=t%2?&from:&moved;check(!CvStackingAI::ArmyUnitStalled(&u,&army,&muster,1),"moving ETA-one unit is not stationary");}
 CvStackingAI::Reset();u.heal=true;for(int t=0;t<8;++t){GC.game.turn=140+t;check(!CvStackingAI::ArmyUnitStalled(&u,&army,&muster,1),"healing grace preserved");}
 u.heal=false;u.position=&muster;for(int t=0;t<8;++t){GC.game.turn=160+t;check(!CvStackingAI::ArmyUnitStalled(&u,&army,&muster,0),"assembled unit never expelled for waiting");}
}
void readinessTests(){reset();CvPlot base(1),dest(2,10);CvCity enemy(2,&dest);enemy.owner=1;dest.owner=1;CvUnit a(1),b(2),c(3),d(4);put(a,base);put(b,base);put(c,base);put(d,base);b.ranged=c.ranged=true;
 CvArmyAI army;CvAIOperation op;op.target=&dest;op.muster=&base;players[0].op=&op;army.slots.push_back(CvArmyFormationSlot(1));army.slots.push_back(CvArmyFormationSlot(2));army.slots.push_back(CvArmyFormationSlot(3));army.slots.push_back(CvArmyFormationSlot(4));army.slots.push_back(CvArmyFormationSlot());
 check(CvStackingAI::ReadyWithAvailableUnits(&op,&army),"viable incomplete real army can gather");
 a.capture=b.capture=c.capture=d.capture=false;check(!CvStackingAI::ReadyWithAvailableUnits(&op,&army),"no real capturer rejected");a.capture=true;
 b.ranged=false;check(!CvStackingAI::ReadyWithAvailableUnits(&op,&army),"insufficient fire support rejected");b.ranged=true;
 op.started=98;check(!CvStackingAI::ReadyWithAvailableUnits(&op,&army),"no early formation relaxation");op.started=0;
 dest.visible=false;check(!CvStackingAI::ReadyWithAvailableUnits(&op,&army),"unseen target cannot relax readiness even when revealed");dest.visible=true;
 enemy.strength=30000;check(!CvStackingAI::ReadyWithAvailableUnits(&op,&army),"overwhelming city blocks smaller assault");enemy.strength=2000;
 check(!CvStackingAI::AssemblyStalled(&op,&army),"new assembly not stalled");for(int t=1;t<=12;++t){++GC.game.turn;check(CvStackingAI::AssemblyStalled(&op,&army)==(t==12),"stage without progress eventually recovers");}
 check(CvStackingAI::RecruitmentBlocked(&a,&dest),"assembly release cannot immediately re-recruit same unit");
 army.state=ARMYAISTATE_WAITING_FOR_UNITS_TO_CATCH_UP;++GC.game.turn;check(!CvStackingAI::AssemblyStalled(&op,&army),"new stage gets new grace");
}
void transferTests(){reset();CvPlot sourcePlot(1),rally(2,10),target(3,14),step(4,2);GC.map.plots[2]=&rally;CvAIOperation op;op.muster=&rally;op.target=&target;players[0].op=&op;CvArmyAI army;army.center=&rally;army.slots.resize(6);players[0].armies.push_back(&army);
 CvUnit u(1);put(u,sourcePlot);u.end=&step;
 check(CvStackingAI::TryReinforceRearUnit(&u),"healthy rear reserve moves toward active army");check(u.plot()==&step&&u.processed,"actual progress and processing recorded");
 CvUnit hurt(2);put(hurt,sourcePlot);hurt.heal=true;hurt.end=&step;check(!CvStackingAI::TryReinforceRearUnit(&hurt),"healing unit not dispatched");
 hurt.heal=false;hurt.cover=true;check(!CvStackingAI::TryReinforceRearUnit(&hurt),"civilian escort retained");hurt.cover=false;
 hurt.canOperation=false;check(!CvStackingAI::TryReinforceRearUnit(&hurt),"contested source retained");hurt.canOperation=true;
 hurt.domain=DOMAIN_AIR;check(!CvStackingAI::TryReinforceRearUnit(&hurt),"aircraft retain native rebase logic");hurt.domain=DOMAIN_LAND;
 options["AIReinforcementPathQueriesPerTurn"]=0;check(!CvStackingAI::TryReinforceRearUnit(&hurt),"path budget enforced");options["AIReinforcementPathQueriesPerTurn"]=32;
 hurt.danger=50;check(!CvStackingAI::TryReinforceRearUnit(&hurt),"endangered source not treated as rear reserve");hurt.danger=0;
 hurt.end=NULL;check(!CvStackingAI::TryReinforceRearUnit(&hurt),"empty successful path never dereferenced");
 hurt.end=&step;hurt.eta=INT_MAX;check(!CvStackingAI::TryReinforceRearUnit(&hurt),"unreachable objective rejected");hurt.eta=1;
 players[0].war=false;check(!CvStackingAI::TryReinforceRearUnit(&hurt),"no active war no strategic transfer");
}
void integrationTests(){reset();CvPlot center(1),neighbor(2,1),other(3,2);CvCity city(1,&center),foreign(2,&other);foreign.owner=1;center.ring.push_back(&neighbor);
 check(city.GetPlotForNewUnit(0,true)==&center,"production permits city center");check(city.GetPlotForNewUnit(0,false)==&neighbor,"displacement excludes center even with free stack slots");
 neighbor.placeable=false;check(city.GetPlotForNewUnit(0,false)==NULL,"no legal exit never falls back to center");check(city.GetPlotForNewUnit(0,true)==&center,"production remains legal when neighbors full");
 center.placeable=false;check(city.GetPlotForNewUnit(0,true)==NULL,"all locations blocked");check(city.GetPlotForNewUnit(-1,true)==NULL,"invalid unit type handled");
 CvMilitaryAI ai;ai.m_pPlayer=&players[0];ai.m_potentialAttackTargets.push_back(AttackTarget(&center,1));
 check(ai.IsPossibleMusterCity(&city,1),"own muster recognized");check(ai.IsPossibleMusterCity(&city,ARMY_TYPE_ANY),"any-domain muster recognized");
 check(!ai.IsPossibleMusterCity(&city,2),"wrong domain rejected");check(!ai.IsPossibleMusterCity(&foreign,1),"foreign muster rejected");check(!ai.IsPossibleMusterCity(NULL,1),"null city rejected");
 CvAIOperation op;CvArmyAI army;CvUnit units[5];
 center.placeable=false;neighbor.placeable=true;
 for(int i=0;i<5;++i){units[i].id=i;units[i].army=army.id;put(units[i],center);army.slots.push_back(CvArmyFormationSlot(i));}
 check(op.GetGatherTolerance(&army,&center)==3,"assembled stack counts toward available gathering capacity");
 for(int i=0;i<5;++i)units[i].army=99;
 check(op.GetGatherTolerance(&army,&center)==4,"other army's full stack does not supply gathering space");
 stackEnabled=false;check(op.GetGatherTolerance(&army,&center)==4,"legacy gather tolerance unchanged when stacking disabled");
}
void budgetTests(){reset();CvPlot p(0);CvUnit units[8];
 for(int i=0;i<8;++i){units[i].id=i;units[i].domain=i<4?DOMAIN_LAND:DOMAIN_SEA;put(units[i],p);}
 check(CvStackingAI::CanStartAnotherOperation(0,DOMAIN_LAND),"four free land units can start operation");
 units[0].canOperation=false;check(!CvStackingAI::CanStartAnotherOperation(0,DOMAIN_LAND),"retained unit cannot fund new operation");
 check(CvStackingAI::CanStartAnotherOperation(0,DOMAIN_SEA),"ships fund independent sea operation");units[0].canOperation=true;
 units[0].hp=69;check(!CvStackingAI::CanStartAnotherOperation(0,DOMAIN_LAND),"operation health floor enforced");units[0].hp=70;
 check(CvStackingAI::CanStartAnotherOperation(0,DOMAIN_LAND),"exact operation health boundary accepted");
 units[0].army=7;check(!CvStackingAI::CanStartAnotherOperation(0,DOMAIN_LAND),"committed units cannot fund another army");units[0].army=-1;
 units[0].heal=true;check(!CvStackingAI::CanStartAnotherOperation(0,DOMAIN_LAND),"healing unit excluded");units[0].heal=false;
 units[0].cover=true;check(!CvStackingAI::CanStartAnotherOperation(0,DOMAIN_LAND),"civilian escort cannot fund another army");units[0].cover=false;
 CvArmyAI a,b;a.domain=b.domain=DOMAIN_LAND;players[0].armies.push_back(&a);players[0].armies.push_back(&b);
 check(!CvStackingAI::CanStartAnotherOperation(0,DOMAIN_LAND),"domain operation cap enforced");
 check(CvStackingAI::CanStartAnotherOperation(0,DOMAIN_SEA),"land operations cannot block fleet budget");
 options["AIOffensiveOperationsPerDomain"]=3;check(CvStackingAI::CanStartAnotherOperation(0,DOMAIN_LAND),"XML operation cap configurable");
 options["AIMilitaryAllocationEnabled"]=0;check(CvStackingAI::CanStartAnotherOperation(0,DOMAIN_LAND),"legacy budget delegates when disabled");
}
int diagnosticScenario(bool logging){reset();CvStackingDiagnostics::enabled=logging;CvPlot p(1),far(2,10);CvCity city(1,&p);CvUnit a(1),b(2);put(a,p);put(b,p);city.garrison=&a;
 int state=CvStackingAI::RetainCityUnit(&a)+2*CvStackingAI::RetainCityUnit(&b);
 CvStackingAI::DelayRecruitment(&b,&far);state+=4*CvStackingAI::RecruitmentBlocked(&b,&far);
 CvStackingAI::Reset();state+=8*CvStackingAI::RecruitmentBlocked(&b,&far);return state;
}
void loggingAndResetTests(){int logged=diagnosticScenario(true),quiet=diagnosticScenario(false);check(logged==quiet,"logging cannot affect native allocation decisions");check(logged==5,"reset removes failed-assignment history");
 reset();CvPlot p(1),q(2,1);p.ring.push_back(&q);CvCity city(1,&p);CvUnit e(1);e.owner=1;put(e,q);
 check(CvStackingAI::AssessCity(&city).enemyStrength>0,"pre-load threat cached");q.visible=false;CvStackingAI::Reset();check(CvStackingAI::AssessCity(&city).enemyStrength==0,"same-turn load reset discards threat cache");CvStackingDiagnostics::enabled=true;
}
void rangedCityTests(){
 reset();options["AICityMaximumDefenders"]=5;CvPlot center(0),enemyPlot(1,1),field(2,2);CvCity city(1,&center);players[0].cities.push_back(&city);center.ring.push_back(&enemyPlot);
 CvUnit melee[4],ranged[3],enemy(20),candidate(21);
 for(int i=0;i<4;++i){melee[i].id=i+1;put(melee[i],center);}melee[0].cs=60;city.garrison=&melee[0];
 for(int i=0;i<3;++i){ranged[i].id=i+10;ranged[i].ranged=true;ranged[i].rs=40;}put(ranged[0],center);put(candidate,field);
 enemy.owner=1;enemy.cs=100;put(enemy,enemyPlot);players[0].attackers.push_back(&enemy);
 check(CvStackingAI::WantsRangedDefender(&city),"four melee plus one ranged exposes a firepower deficit");
 check(CvStackingAI::RetainCityUnit(&melee[0])&&CvStackingAI::RetainCityUnit(&ranged[0]),"strong garrison and useful ranged defender retained");
 check(!CvStackingAI::RetainCityUnit(&melee[1])&&!CvStackingAI::RetainCityUnit(&melee[2]),"redundant passive melee available for field duties");
 check(!CvStackingAI::UsefulGarrison(&candidate,&city),"another ordinary melee cannot conceal ranged deficit");candidate.ranged=true;candidate.rs=40;
 check(CvStackingAI::UsefulGarrison(&candidate,&city),"ranged reinforcement is useful despite generic occupied strength");
 check(CvStackingAI::RangedDefenseProductionBonus(&city,UNITAI_DEFENSE,2)>0,"missing firepower creates production priority");
 check(!CvStackingAI::RangedDefenseProductionBonus(&city,UNITAI_CITY_BOMBARD,2),"offensive siege is not blanket city-defense production");
 for(int i=1;i<3;++i){center.units.erase(remove(center.units.begin(),center.units.end(),&melee[i]),center.units.end());melee[i].position=&field;field.units.push_back(&melee[i]);put(ranged[i],center);}++GC.game.turn;
 check(!CvStackingAI::WantsRangedDefender(&city)&&!CvStackingAI::NeedsCityDefender(&city),"ranged-heavy force satisfies roles and weighted defensive contribution");
 check(!CvStackingAI::RetainCityUnit(&melee[3]),"last unnecessary melee released with firepower present");
 ranged[2].role=ranged[2].info.role=UNITAI_CITY_BOMBARD;++GC.game.turn;check(CvStackingAI::WantsRangedDefender(&city),"siege-role unit does not silently replace ordinary ranged quota");
 enemyPlot.visible=false;players[0].attackers.clear();++GC.game.turn;check(!CvStackingAI::WantsRangedDefender(&city),"rear city does not perpetually request ranged units");
 check(CvStackingAI::RetainCityUnit(&melee[0])&&!CvStackingAI::RetainCityUnit(&ranged[0]),"safe city reserves only economical coverage");
 CvStackingOffensiveAI::committed.push_back(melee[0].id);++GC.game.turn;
 check(!CvStackingAI::RetainCityUnit(&melee[0]),"safe rear city releases designated melee garrison committed to an offensive when coverage exists");
 check(CvStackingAI::RetainCityUnit(&ranged[0]),"available ranged unit replaces departing offensive garrison");
 city.garrison=&ranged[0];CvStackingOffensiveAI::committed.clear();++GC.game.turn;
 check(CvStackingAI::RetainCityUnit(&ranged[0])&&!CvStackingAI::RetainCityUnit(&melee[0]),"ranged garrison alone provides economical rear coverage");
 center.units.erase(remove(center.units.begin(),center.units.end(),&ranged[0]),center.units.end());ranged[0].position=&field;
 check(CvStackingAI::RetainCityUnit(&melee[0]),"removed garrison is replaced by an eligible occupant without waiting for threat-cache expiry");
 city.garrison=&melee[0];city.fall=true;enemyPlot.visible=true;players[0].attackers.push_back(&enemy);++GC.game.turn;
 check(CvStackingAI::AssessCity(&city).meleeMaximum==5,"immediate falling-city emergency can use available melee reserves");
}
int main(){policyTests();cityTests();progressTests();readinessTests();transferTests();integrationTests();budgetTests();loggingAndResetTests();rangedCityTests();printf("military allocation: %d checks, %d failures\n",checks,failures);return failures?1:0;}
'''.replace('DEFAULTS',default_settings)
offense_stub=r'''
namespace CvStackingOffensiveAI {
 struct Demand{int staging,target,operation,strength,priority;};
 vector<int> committed;
 void Reset(){committed.clear();} bool Enabled(int){return false;}bool HasCommitment(const CvUnit*u,const CvPlot*){return u && find(committed.begin(),committed.end(),u->GetID())!=committed.end();}bool JoinArrived(CvUnit*){return false;}bool HoldReserve(CvUnit*){return false;}void CancelCommitment(const CvUnit*){}bool IsCityAttack(const CvAIOperation*){return false;}
 void AddDemands(CvUnit*,vector<Demand>&){}void RecordTransfer(CvUnit*,int,int,int){}
}
'''
cpp=out/'allocation-source-test.cpp';cpp.write_text(stubs+offense_stub+header+policy+actual+placement+muster+gather+tests,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','')
env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'allocation-source-test.exe'
c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'allocation.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps({'returncode':r.returncode,'output':r.stdout+r.stderr,'source_sha256':hashlib.sha256((core/'CvStackingAI.cpp').read_bytes()).hexdigest(),'scope':'Entire actual CvStackingAI.cpp and policy header under deterministic native VC9 engine stubs; not game pathfinding or live AI efficacy.'},indent=2),encoding='utf-8')
sys.exit(r.returncode)
