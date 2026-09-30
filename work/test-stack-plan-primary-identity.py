"""Explicit primary-victim alternative under work; no production edits.

Compiles the complete current ExecuteUnitAssignments twice against deterministic
mission/plot/player substitutes. The candidate changes only victim/actor liveness
and city-garrison postconditions; original math and native mission calls remain.
Uses actual assignment and damage-container definitions, with two proposed
ephemeral identity fields initialized/reset/copied. No projected-HP gate.
Deleted objects are poisoned tombstones to detect stale reads without UB.
"""
from pathlib import Path
import hashlib, json, os, subprocess, sys

root=Path(__file__).resolve().parents[1]
path=root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
source=path.read_text(encoding='utf-8-sig')
start=source.index('bool TacticalAIHelpers::ExecuteUnitAssignments(')
opening=source.index('{',start);end=opening+1;depth=1
while depth:
 depth+=(source[end]=='{')-(source[end]=='}');end+=1
actual=source[start:end]
def struct(text,name):
 start=text.index('struct '+name);opening=text.index('{',start);end=opening+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]+';'
unit_header=(root/'CvGameCoreDLL_Expansion2/CvUnit.h').read_text(encoding='utf-8-sig')
tactical_header=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.h').read_text(encoding='utf-8-sig')
damage_type=struct(unit_header,'SUnitIDValueContainer')
original_assignment=struct(tactical_header,'STacticalAssignment')
proposed_assignment=original_assignment.replace('int iDamagedCityId; //city we damaged','int iDamagedCityId; //city we damaged\n\tint iPrimaryUnitID;\n\tPlayerTypes ePrimaryUnitOwner;')
proposed_assignment=proposed_assignment.replace('iDamagedCityId(0), iPlotScore','iDamagedCityId(0), iPrimaryUnitID(-1), ePrimaryUnitOwner(NO_PLAYER), iPlotScore')
assert proposed_assignment.count('iDamagedCityId = -1;')==2
proposed_assignment=proposed_assignment.replace('iDamagedCityId = -1;', 'iDamagedCityId = -1;\n\t\tiPrimaryUnitID = -1;\n\t\tePrimaryUnitOwner = NO_PLAYER;')
assert proposed_assignment.count('iPrimaryUnitID = -1;')==2 and 'iPrimaryUnitID(-1)' in proposed_assignment
proposed_assignment=proposed_assignment.replace('void wipe()\n\t{', 'void wipe()\n\t{\n\t\tiPrimaryUnitID = -1;\n\t\tePrimaryUnitOwner = NO_PLAYER;')
def function(text,name):
 start=text.index(name);opening=text.index('{',start);end=opening+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
value_equality=function(source,'static bool EqualAssignedUnitValues(')
original_equality=function(source,'bool STacticalAssignment::operator==(')
proposed_equality=original_equality.replace('iSelfDamage == rhs.iSelfDamage', 'iPrimaryUnitID == rhs.iPrimaryUnitID && ePrimaryUnitOwner == rhs.ePrimaryUnitOwner &&\n  iSelfDamage == rhs.iSelfDamage')
classification_start=source.index('\tif (bCityKill)\n\t\tresult->eAssignmentType = A_MELEEKILL;',source.index('bool ScoreAttackDamage('))
classification_end=source.index('\n\tresult->iSelfDamage',classification_start)
classification=source[classification_start:classification_end]
primary_record='result->iPrimaryUnitID = pEnemyUnit ? pEnemyUnit->GetID() : -1;\n result->ePrimaryUnitOwner = pEnemyUnit ? pEnemyUnit->getOwner() : (pEnemyCity ? pEnemyCity->getOwner() : NO_PLAYER);'
candidate=actual
def replace(old,new,count=1):
 global candidate
 assert candidate.count(old)==count,(old,candidate.count(old),count)
 candidate=candidate.replace(old,new)

replace('CvUnit* pEnemy = NULL;', 'CvUnit* pEnemy = NULL;\n\t\tStackPlanVictim expectedVictim;\n\t\tconst int actorID=pUnit->GetID();\n\t\tconst PlayerTypes actorOwner=pUnit->getOwner();')
replace('\n\t\t\tpEnemy = pToPlot->getBestDefender(NO_PLAYER, ePlayer, pUnit);',
        '\n\t\t\tpEnemy = StackPlanNativeVictim(pToPlot,pUnit,ePlayer);\n\t\t\texpectedVictim=StackPlanVictim(pEnemy);',2)
replace('CvUnit* pEnemy = pToPlot->getBestDefender(NO_PLAYER, ePlayer, pUnit);',
        'CvUnit* pEnemy = StackPlanNativeVictim(pToPlot,pUnit,ePlayer);\n\t\t\texpectedVictim=StackPlanVictim(pEnemy);')
refresh='\n\t\t\tpUnit=GET_PLAYER(actorOwner).getUnit(actorID);\n\t\t\tif (!pUnit || pUnit->isDelayedDeath() || !pUnit->plot()) return false;'
replace('pUnit->PushMission(CvTypes::getMISSION_RANGE_ATTACK(), pToPlot->getX(), pToPlot->getY());',
        'pUnit->PushMission(CvTypes::getMISSION_RANGE_ATTACK(), pToPlot->getX(), pToPlot->getY());'+refresh,2)
replace('pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pToPlot->getX(), pToPlot->getY());',
        'pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pToPlot->getX(), pToPlot->getY());'+refresh,2)
replace('bPostcondition = (!bCityBefore || pToPlot->isEnemyCity(*pUnit)) && (!bUnitBefore || (pEnemy && !pEnemy->IsDead()));',
        'bPostcondition = (!bCityBefore || pToPlot->isEnemyCity(*pUnit)) && (!expectedVictim.present || !StackPlanVictimDefeated(expectedVictim));')
replace('case A_RANGEKILL:\n', 'case A_RANGEKILL:\n\t\t{\n\t\t\tconst bool bCityBefore=pToPlot->isEnemyCity(*pUnit);\n\t\t\tif (bCityBefore && !CvStackingOffensiveAI::AllowCityAttack(pUnit,pToPlot->getPlotCity(),pFromPlot,false))\n\t\t\t{\n\t\t\t\tif (diagnose) RecordStackPlanExecutionFailure(ePlayer,vAssignments[i],i,"city_attack_gate",false,false,missionOrders,ordersBefore,diagnosticBefore);\n\t\t\t\treturn false;\n\t\t\t}\n')
replace('bPrecondition = (pUnit->plot() == pFromPlot) && pToPlot->isEnemyUnit(ePlayer,true,true); //defending unit present. does not apply to cities',
        'bPrecondition = (pUnit->plot() == pFromPlot) && (bCityBefore || pToPlot->isEnemyUnit(ePlayer,true,true));')
marker='expectedVictim=StackPlanVictim(pEnemy);\n\t\t\tif (bPrecondition)'
kill_start=candidate.index('case A_RANGEKILL:');kill_end=candidate.index('case A_MELEEATTACK:',kill_start)
kill_case=candidate[kill_start:kill_end];assert kill_case.count(marker)==1
candidate=candidate[:kill_start]+kill_case.replace(marker,'expectedVictim=StackPlanVictim(pEnemy);\n\t\t\tbPrecondition = bPrecondition && StackPlanKillVictimMatches(vAssignments[i],expectedVictim);\n\t\t\tif (bPrecondition)')+candidate[kill_end:]
replace('bPostcondition = pEnemy && pEnemy->IsDead(); //defending unit is gone\n\t\t\tbreak;\n\t\tcase A_MELEEATTACK:',
        'bPostcondition = StackPlanVictimDefeated(expectedVictim) && (!bCityBefore || pToPlot->isEnemyCity(*pUnit));\n\t\t\tbreak;\n\t\t}\n\t\tcase A_MELEEATTACK:')
replace('bPrecondition = (pUnit->plot() == pFromPlot) && (pToPlot->isEnemyUnit(ePlayer,true,true) || pToPlot->isEnemyCity(*pUnit)); //enemy present\n\t\t\tif (bPrecondition)',
        'pEnemy=StackPlanNativeVictim(pToPlot,pUnit,ePlayer);\n\t\t\texpectedVictim=StackPlanVictim(pEnemy);\n\t\t\tbPrecondition = (pUnit->plot() == pFromPlot) && (pToPlot->isEnemyUnit(ePlayer,true,true) || pToPlot->isEnemyCity(*pUnit)); //enemy present\n\t\t\tif (bPrecondition)')
replace('bPostcondition = (pUnit->plot() == pFromPlot) && (pToPlot->isEnemyUnit(ePlayer,true,true) || pToPlot->isEnemyCity(*pUnit)); //enemy still present',
        'bPostcondition = (pUnit->plot() == pFromPlot) && (pToPlot->isEnemyUnit(ePlayer,true,true) || pToPlot->isEnemyCity(*pUnit)) && (!expectedVictim.present || !StackPlanVictimDefeated(expectedVictim)); //expected enemy still present')
replace('bool bCityKill = false;\n\t\t\tbool bUnitKill = false;',
        'bool bCityKill = false;\n\t\t\tbool bUnitKill = false;\n\t\t\tconst bool bCityBefore=pToPlot->isEnemyCity(*pUnit);\n\t\t\tif (vAssignments[i].eAssignmentType==A_MELEEKILL_NO_ADVANCE)\n\t\t\t{\n\t\t\t\tif (bCityBefore && !CvStackingOffensiveAI::AllowCityAttack(pUnit,pToPlot->getPlotCity(),pFromPlot,false)) return false;\n\t\t\t\tbPrecondition=bPrecondition && StackPlanKillVictimMatches(vAssignments[i],expectedVictim);\n\t\t\t}\n\t\t\telse if (!bCityBefore) bPrecondition=bPrecondition && StackPlanKillVictimMatches(vAssignments[i],expectedVictim);')
replace('if (bPostcondition && bUnitKill)\n\t\t\t{\n\t\t\t\tbPostcondition = pEnemy->IsDead(); //defending unit is dead\n\t\t\t}',
        'if (bPostcondition && bCityBefore && vAssignments[i].eAssignmentType==A_MELEEKILL)\n\t\t\t\tbPostcondition = pToPlot->isCity() && pToPlot->getOwner()==ePlayer && !pToPlot->isEnemyCity(*pUnit) && !pToPlot->isEnemyUnit(ePlayer,true,true) && (!expectedVictim.present || StackPlanVictimDefeated(expectedVictim));\n\t\t\telse if (bPostcondition)\n\t\t\t\tbPostcondition = StackPlanVictimDefeated(expectedVictim) && (!bCityBefore || pToPlot->isEnemyCity(*pUnit));')
candidate=candidate.replace('TacticalAIHelpers::ExecuteUnitAssignments(', 'TacticalAIHelpers::ExecuteUnitAssignmentsCandidate(',1)
candidate=candidate.replace('StackPlanKillVictimMatches', 'StackPlanPrimaryMatches')
# Every attack checks the projected primary identity before native execution;
# no numeric damage/HP test changes whether a legal attack can be attempted.
candidate=candidate.replace('expectedVictim=StackPlanVictim(pEnemy);', 'expectedVictim=StackPlanVictim(pEnemy);\n\t\t\tbPrecondition=bPrecondition && StackPlanPrimaryMatches(vAssignments[i],expectedVictim);')
# A_MELEEATTACK computed bPrecondition later: put its identity check after that.
candidate=candidate.replace('bPrecondition=bPrecondition && StackPlanPrimaryMatches(vAssignments[i],expectedVictim);\n\t\t\tbPrecondition = (pUnit->plot()', 'bPrecondition = (pUnit->plot()')
candidate=candidate.replace('//enemy present\n\t\t\tif (bPrecondition)', '//enemy present\n\t\t\tbPrecondition=bPrecondition && StackPlanPrimaryMatches(vAssignments[i],expectedVictim);\n\t\t\tif (bPrecondition)')
candidate=candidate.replace('\n\t\t\tbPrecondition = bPrecondition && StackPlanPrimaryMatches(vAssignments[i],expectedVictim);','')
candidate=candidate.replace('\n\t\t\t\tbPrecondition=bPrecondition && StackPlanPrimaryMatches(vAssignments[i],expectedVictim);','')
candidate=candidate.replace('\n\t\t\telse if (!bCityBefore) bPrecondition=bPrecondition && StackPlanPrimaryMatches(vAssignments[i],expectedVictim);','')

fixture=r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <vector>
#include <map>
#include <set>
#include <string>
#include <algorithm>
#include <cstdio>
#include <climits>
using namespace std;
typedef int PlayerTypes;typedef int BuildTypes;
const int NO_PLAYER=-1,NO_BUILD=-1,MISSIONAI_OPMOVE=4;
#define MOD_BALANCE_VP 0
#define VALIDATE_OBJECT() ((void)0)
#define ASSERT(value,...) ((void)0)
const short TACTICAL_COMBAT_IMPOSSIBLE_SCORE=-1000;
enum eUnitMovementStrategy{MS_NONE,MS_FIRSTLINE,MS_SECONDLINE,MS_THIRDLINE,MS_SUPPORT,MS_EMBARKED};
enum eUnitAssignmentType{A_INITIAL,A_MOVE,A_MELEEATTACK,A_MELEEKILL,A_RANGEATTACK,A_RANGEKILL,A_FINISH,A_BLOCKED,A_PILLAGE,A_CAPTURE,A_MOVE_FORCED,A_RESTART,A_MELEEKILL_NO_ADVANCE,A_MOVE_SWAP,A_MOVE_SWAP_REVERSE,A_MOVE_DOUBLE,A_USE_POWER,A_FINISH_TEMP,A_HEAL,A_WAIT};
struct CvUnit;
struct CvCity{int hp,damage,owner;CvUnit*garrison;CvCity():hp(100),damage(0),owner(1),garrison(NULL){}int getOwner()const{return owner;}int GetMaxHitPoints()const{return hp;}int getDamage()const{return damage;}CvUnit*GetGarrisonedUnit()const{return garrison;}};
struct CvPlot{int id;bool enemyUnit;CvUnit*best;CvCity*city;CvPlot(int n=0):id(n),enemyUnit(false),best(NULL),city(NULL){}int getX()const{return id;}int getY()const{return 0;}bool isFortification(int)const{return false;}bool isCity()const{return city!=NULL;}int getOwner()const{return city?city->owner:0;}CvCity*getPlotCity()const{return city;}bool isEnemyCity(const CvUnit&)const;bool isEnemyUnit(int,bool,bool)const{return enemyUnit;}CvUnit*getBestDefender(int,int,const CvUnit*)const{return best;}};
int staleReads=0,orders=0,processed=0,forecastDamage=100,forecastGarrisonDamage=100,actualDamage=100;
bool allowCity=true,deleteVictim=false,deleteActor=false,wrongVictim=false,captureCity=false,forceNoAdvance=false,blockMove=false;
CvPlot plots[4];CvCity city;vector<CvUnit*>allocated;CvUnit*actualVictim=NULL,*secondary=NULL;
namespace CvTypes{int getMISSION_MOVE_TO(){return 1;}int getMISSION_SWAP_UNITS(){return 2;}int getMISSION_RANGE_ATTACK(){return 3;}int getMISSION_PILLAGE(){return 4;}int getMISSION_BUILD(){return 5;}int getMISSION_REPAIR_FLEET(){return 6;}int getMISSION_SKIP(){return 7;}}
struct CvUnit{int id,owner,hp,moves,attacks;CvPlot*p;bool poison,delayed;
 enum{MOVEFLAG_IGNORE_DANGER=1,MOVEFLAG_NO_STOPNODES=2,MOVEFLAG_ABORT_IF_NEW_ENEMY_REVEALED=4};
 CvUnit(int n,int o,CvPlot*q):id(n),owner(o),hp(100),moves(300),attacks(0),p(q),poison(false),delayed(false){}
 int GetID()const{return id;}int getOwner()const{return owner;}int getTeam()const{return owner;}CvPlot*plot()const{if(poison)++staleReads;return p;}bool isDelayedDeath()const{if(poison)++staleReads;return delayed;}
 bool canMove()const{return moves>0;}int getMoves()const{return moves;}int GetCurrHitPoints()const{return hp;}bool IsDead()const{if(poison){++staleReads;return false;}return hp<=0;}
 void ClearPathCache(){}bool canBuild(CvPlot*,int)const{return false;}bool canRepairFleet(CvPlot*)const{return false;}bool shouldHeal(bool)const{return false;}bool isBarbarian()const{return false;}
 void PushMission(int,int=-1,int=-1,int=0,bool=false,bool=false,int=0);
};
bool CvPlot::isEnemyCity(const CvUnit&unit)const{return city&&city->owner!=unit.owner;}
struct TacticalStub{void UnitProcessed(int){++processed;}};
struct CvPlayer{map<int,CvUnit*>units;TacticalStub tactical;CvUnit*getUnit(int id){map<int,CvUnit*>::iterator it=units.find(id);return it==units.end()?NULL:it->second;}TacticalStub*GetTacticalAI(){return &tactical;}}players[2];
#define GET_PLAYER(x) players[x]
void retire(CvUnit*victim){if(!victim)return;players[victim->owner].units.erase(victim->id);victim->poison=true;if(plots[1].best==victim)plots[1].best=secondary;if(city.garrison==victim)city.garrison=secondary;}
void CvUnit::PushMission(int type,int target,int,int,bool,bool,int){++orders;
 if(type==3 || type==1&&(plots[target].enemyUnit||plots[target].isEnemyCity(*this))){++attacks;moves-=60;
  if(plots[target].city)city.damage=min(city.hp-1,city.damage+20);
  CvUnit*v=wrongVictim?secondary:actualVictim;if(v){if(deleteVictim)retire(v);else {v->hp-=actualDamage;if(v->hp<=0&&city.garrison==v)city.garrison=secondary;}}
  if(captureCity){p=&plots[target];city.owner=owner;plots[target].enemyUnit=false;retire(actualVictim);retire(secondary);}
  else if(type==1&&!forceNoAdvance&&v&&v->hp<=0&&!secondary){p=&plots[target];plots[target].enemyUnit=false;}
  if(deleteActor)retire(this);
 }else if(type==1||type==2){if(!blockMove){p=&plots[target];moves-=60;}}
}
struct MapStub{CvPlot*plotByIndexUnchecked(int id){return &plots[id];}};
struct GCStub{MapStub map;MapStub&getMap(){return map;}int getInfoTypeForString(const char*){return 1;}}GC;
__ACTUAL_DAMAGE_CONTAINER__
__ASSIGNMENT_TYPES__
STacticalAssignment makeAssignment(int type){return STacticalAssignment(0,1,1,0,MS_NONE,(eUnitAssignmentType)type,0);}
namespace CvStackingDiagnostics{bool EnabledCategory(int,int,const char*){return false;}}
namespace CvStackingOffensiveAI{bool AllowCityAttack(const CvUnit*,CvCity*,const CvPlot*,bool){return allowCity;}}
struct StackPlanDiagnosticUnitState{};
StackPlanDiagnosticUnitState ReadStackPlanDiagnosticUnitState(CvUnit*){return StackPlanDiagnosticUnitState();}
void RecordStackPlanExecutionFailure(int,const STacticalAssignment&,size_t,const char*,bool,bool,unsigned int,unsigned int,const StackPlanDiagnosticUnitState&){}
namespace TacticalAIHelpers{bool ExecuteUnitAssignments(int,const vector<STacticalAssignment>&);bool ExecuteUnitAssignmentsCandidate(int,const vector<STacticalAssignment>&);
 int GetSimulatedDamageFromAttackOnCity(CvCity*,CvUnit*,CvPlot*,int&,int&garrison){garrison=forecastGarrisonDamage;return forecastDamage;}
 int GetSimulatedDamageFromAttackOnUnit(CvUnit*,CvUnit*,CvPlot*,CvPlot*,int&){return forecastDamage;}}
// Candidate helpers preserve one victim identity; the map lookup after combat
// never touches the saved victim pointer, which may have been freed by native code.
struct StackPlanVictim{PlayerTypes owner;int id;bool present;StackPlanVictim():owner(NO_PLAYER),id(-1),present(false){}explicit StackPlanVictim(const CvUnit*unit):owner(unit?unit->getOwner():NO_PLAYER),id(unit?unit->GetID():-1),present(unit!=NULL){}};
CvUnit*StackPlanNativeVictim(CvPlot*target,CvUnit*actor,PlayerTypes owner){return target->isEnemyCity(*actor)?target->getPlotCity()->GetGarrisonedUnit():target->getBestDefender(NO_PLAYER,owner,actor);}
bool StackPlanVictimDefeated(const StackPlanVictim&victim){if(!victim.present)return false;CvUnit*live=GET_PLAYER(victim.owner).getUnit(victim.id);return !live||live->IsDead()||live->isDelayedDeath();}
bool StackPlanPrimaryMatches(const STacticalAssignment&assignment,const StackPlanVictim&victim){if(assignment.ePrimaryUnitOwner==NO_PLAYER)return true;return assignment.iPrimaryUnitID<0?!victim.present:(victim.present&&assignment.iPrimaryUnitID==victim.id&&assignment.ePrimaryUnitOwner==victim.owner);}
int checks=0,failures=0;
void check(bool value,const char*name){++checks;if(!value){++failures;printf("FAIL %s\n",name);}}
CvUnit*unit(int id,int owner,CvPlot*plot){CvUnit*u=new CvUnit(id,owner,plot);players[owner].units[id]=u;allocated.push_back(u);return u;}
void reset(){for(size_t i=0;i<allocated.size();++i)delete allocated[i];allocated.clear();players[0].units.clear();players[1].units.clear();for(int i=0;i<4;++i)plots[i]=CvPlot(i);city=CvCity();staleReads=orders=processed=0;forecastDamage=forecastGarrisonDamage=actualDamage=100;allowCity=true;deleteVictim=deleteActor=wrongVictim=captureCity=forceNoAdvance=blockMove=false;actualVictim=secondary=NULL;unit(1,0,&plots[0]);}
STacticalAssignment prepare(int type,bool inCity,bool stacked){STacticalAssignment a=makeAssignment(type);actualVictim=unit(2,1,&plots[1]);plots[1].enemyUnit=true;plots[1].best=actualVictim;if(stacked){secondary=unit(3,1,&plots[1]);plots[1].best=secondary;}if(inCity){plots[1].city=&city;city.garrison=actualVictim;}a.unitDamage.SetValue(2,100);a.iPrimaryUnitID=2;a.ePrimaryUnitOwner=1;return a;}
bool execute(const STacticalAssignment&a,bool candidate){vector<STacticalAssignment>plan(1,a);return candidate?TacticalAIHelpers::ExecuteUnitAssignmentsCandidate(0,plan):TacticalAIHelpers::ExecuteUnitAssignments(0,plan);}
'''
fixture=fixture.replace('__ACTUAL_DAMAGE_CONTAINER__',damage_type).replace('__ASSIGNMENT_TYPES__',original_assignment.replace('STacticalAssignment','STacticalAssignmentOriginal')+'\n'+proposed_assignment)
fixture+='\nstruct CvTacticalPlot{vector<const CvUnit*>enemies;const vector<const CvUnit*>&getEnemyUnits()const{return enemies;}};\nvoid ClassifyProjectedAttack(bool bCityKill,bool bUnitKill,bool bRanged,const CvUnit*pEnemyUnit,const CvCity*pEnemyCity,const CvPlot*pTestPlot,int iPrevCityHitPoints,const CvTacticalPlot*tactPlot,STacticalAssignment*result){\n'+classification+'\n'+primary_record+'\n}\n'
tests=r'''
int main(){
 // Demonstrate the actual old failure before testing the proposed correction.
 reset();STacticalAssignment a=prepare(A_RANGEKILL,true,true);deleteVictim=true;
 check(!execute(a,false)&&orders==1,"old city range-kill wrongly checks unrelated best defender");
 reset();a=prepare(A_MELEEKILL,true,true);captureCity=deleteVictim=true;
 check(!execute(a,false)&&city.owner==0&&staleReads>0,"old successful capture reads deleted defender and fails");
 for(int mode=0;mode<2;++mode){
  reset();a=prepare(A_RANGEKILL,true,true);deleteVictim=mode!=0;
  check(execute(a,true)&&orders==1&&city.owner==1&&secondary->hp==100,"city garrison kill succeeds with another city defender present");check(staleReads==0,"garrison replacement never dereferences old victim");
  reset();a=prepare(A_RANGEKILL,false,true);plots[1].best=actualVictim;deleteVictim=mode!=0;
  check(execute(a,true)&&plots[1].enemyUnit&&secondary->hp==100,"ordinary ranged kill retains remaining stack");check(staleReads==0,"range deletion uses owner/ID lookup");
  reset();a=prepare(A_MELEEKILL_NO_ADVANCE,false,true);plots[1].best=actualVictim;forceNoAdvance=true;deleteVictim=mode!=0;
  check(execute(a,true)&&players[0].getUnit(1)->p==&plots[0]&&secondary->hp==100,"stacked melee kill correctly stays at origin");check(staleReads==0,"no-advance deletion uses owner/ID lookup");
  reset();a=prepare(A_MELEEKILL_NO_ADVANCE,true,true);forceNoAdvance=true;deleteVictim=mode!=0;forecastDamage=20;
  check(execute(a,true)&&city.owner==1&&secondary->hp==100,"melee garrison kill uses actual garrison and preserves city");check(staleReads==0,"melee garrison deletion uses owner/ID");
 }
 reset();a=prepare(A_MELEEKILL,true,true);captureCity=deleteVictim=true;unit(2,0,&plots[3]);
 check(execute(a,true)&&city.owner==0&&players[0].getUnit(1)->p==&plots[1],"captured city validates ownership and advance");check(staleReads==0&&players[0].getUnit(2)->hp==100,"deleted enemy identity does not collide with friendly same ID");
 reset();a=prepare(A_RANGEKILL,true,true);actualDamage=20;
 check(!execute(a,true)&&orders==1&&actualVictim->hp==80,"city damage without expected garrison death still replans");
 reset();a=prepare(A_RANGEKILL,false,true);plots[1].best=actualVictim;actualDamage=20;
 check(!execute(a,true)&&orders==1,"ordinary ranged damage-roll miss still replans");
 reset();a=prepare(A_MELEEKILL_NO_ADVANCE,false,true);plots[1].best=actualVictim;forceNoAdvance=true;forecastDamage=actualDamage=20;
 check(!execute(a,true)&&orders==1,"no-advance requires expected death even if fresh preview revises kill downward");
 reset();a=prepare(A_RANGEKILL,true,true);wrongVictim=true;
 check(!execute(a,true)&&actualVictim->hp==100&&secondary->hp<=0,"wrong city member dying cannot satisfy primary-victim kill");
 reset();a=prepare(A_RANGEKILL,true,true);a.iPrimaryUnitID=3;
 check(!execute(a,true)&&orders==0,"predicted victim disagrees with actual garrison: conservative precondition failure");
 reset();a=prepare(A_RANGEKILL,true,true);allowCity=false;
 check(!execute(a,true)&&orders==0,"city range-kill retains existing city-attack policy guard");
 reset();a=prepare(A_MELEEKILL_NO_ADVANCE,true,true);allowCity=false;
 check(!execute(a,true)&&orders==0,"city no-advance garrison attack retains policy guard");
 reset();a=prepare(A_RANGEATTACK,true,true);actualDamage=20;
 check(execute(a,true)&&city.owner==1&&actualVictim->hp==80,"ordinary city damage with surviving garrison remains valid");
 reset();a=prepare(A_RANGEATTACK,true,true);deleteVictim=true;
 check(!execute(a,true)&&staleReads==0,"unexpected garrison death retains necessary replan");
 reset();a=prepare(A_MELEEKILL,true,true);captureCity=deleteVictim=deleteActor=true;
 check(!execute(a,true)&&staleReads==0,"capturing actor removed by callback never dereferenced after mission");
 reset();a=prepare(A_RANGEKILL,false,false);deleteActor=true;
 check(!execute(a,true)&&staleReads==0,"ranged actor removed by callback never dereferenced after mission");
 reset();a=prepare(A_MELEEKILL,false,false);
 check(execute(a,true)&&players[0].getUnit(1)->p==&plots[1],"ordinary melee kill advances");
 reset();a=prepare(A_MELEEATTACK,false,true);plots[1].best=actualVictim;actualDamage=20;forceNoAdvance=true;
 check(execute(a,true),"ordinary surviving melee attack remains valid");
 reset();a=prepare(A_MELEEATTACK,false,true);plots[1].best=actualVictim;actualDamage=100;forceNoAdvance=true;
 check(!execute(a,true),"unexpected primary melee death triggers replan despite remaining stack");
 reset();STacticalAssignment movement=makeAssignment(A_MOVE);blockMove=true;
 check(!execute(movement,true)&&orders==1,"actual blocked movement remains a failure");
 reset();a=prepare(A_RANGEKILL,true,true);a.unitDamage.SetValue(2,20);actualDamage=100;
 check(execute(a,true)&&orders==1,"raw projected hit below live HP does not suppress favorable native kill");
 reset();a=prepare(A_RANGEKILL,true,true);a.ePrimaryUnitOwner=0;
 check(!execute(a,true)&&orders==0,"same ID from wrong owner cannot satisfy projected identity");
 reset();a=prepare(A_MELEEKILL,true,false);retire(actualVictim);actualVictim=NULL;city.garrison=NULL;plots[1].best=NULL;plots[1].enemyUnit=false;a.unitDamage.clear();a.iPrimaryUnitID=-1;a.ePrimaryUnitOwner=1;captureCity=true;
 check(execute(a,true)&&city.owner==0,"zero-entry city capture without garrison remains valid");
 reset();a=prepare(A_RANGEATTACK,true,false);a.iPrimaryUnitID=-1;a.ePrimaryUnitOwner=1;
 check(!execute(a,true)&&orders==0,"new native garrison contradicts projected no-victim city shot");
 STacticalAssignment blank;check(blank.iPrimaryUnitID==-1&&blank.ePrimaryUnitOwner==NO_PLAYER,"default construction initializes identity sentinel");
 for(int type=0;type<=A_WAIT;++type){STacticalAssignment value=makeAssignment(type);check(value.iPrimaryUnitID==-1&&value.ePrimaryUnitOwner==NO_PLAYER,"typed construction initializes identity sentinel");value.iPrimaryUnitID=91;value.ePrimaryUnitOwner=1;STacticalAssignment copy(value);vector<STacticalAssignment>copies(1,value);check(copy.iPrimaryUnitID==91&&copies[0].ePrimaryUnitOwner==1,"implicit copy and vector copy preserve identity");value.init(0,1,1,0,MS_NONE,(eUnitAssignmentType)type,0);check(value.iPrimaryUnitID==-1&&value.ePrimaryUnitOwner==NO_PLAYER,"reused assignment init resets identity");}
 reset();a=prepare(A_RANGEKILL,true,true);CvTacticalPlot tactical;tactical.enemies.push_back(actualVictim);tactical.enemies.push_back(secondary);ClassifyProjectedAttack(false,true,true,actualVictim,&city,&plots[1],80,&tactical,&a);
 check(a.eAssignmentType==A_RANGEKILL&&a.iPrimaryUnitID==2&&a.ePrimaryUnitOwner==1,"actual scorer classifier records selected garrison rather than generic best defender");
 ClassifyProjectedAttack(true,false,false,NULL,&city,&plots[1],80,&tactical,&a);check(a.eAssignmentType==A_MELEEKILL&&a.iPrimaryUnitID==-1&&a.ePrimaryUnitOwner==1,"actual city-capture classifier records known no-garrison identity");
 ClassifyProjectedAttack(false,true,false,actualVictim,NULL,&plots[1],0,&tactical,&a);check(a.eAssignmentType==A_MELEEKILL_NO_ADVANCE&&a.iPrimaryUnitID==2,"actual stacked melee classifier retains no-advance and selected primary");
 STacticalAssignment equal=a;check(equal==a,"equal assignment retains matching primary identity");equal.iPrimaryUnitID=3;check(!(equal==a),"different primary ID distinguishes semantic assignment equality");equal=a;equal.ePrimaryUnitOwner=0;check(!(equal==a),"different primary owner distinguishes semantic assignment equality");equal=a;equal.wipe();check(equal.iPrimaryUnitID==-1&&equal.ePrimaryUnitOwner==NO_PLAYER,"hard-reset wipe clears primary identity");
 printf("SIZE original=%u candidate=%u extra=%u pointer=%u damageContainer=%u\n",(unsigned int)sizeof(STacticalAssignmentOriginal),(unsigned int)sizeof(STacticalAssignment),(unsigned int)(sizeof(STacticalAssignment)-sizeof(STacticalAssignmentOriginal)),(unsigned int)sizeof(void*),(unsigned int)sizeof(SUnitIDValueContainer));
 check(sizeof(STacticalAssignment)==sizeof(STacticalAssignmentOriginal)+8,"ephemeral owner plus ID adds exactly eight bytes on VC9 x86");
 printf("executor explicit-primary prototype: %d checks, %d failures\n",checks,failures);reset();return failures?1:0;
}
'''
out=root/'work/stack-plan-primary-identity-prototype';out.mkdir(exist_ok=True)
(out/'original-executor.cpp').write_text(actual+'\n',encoding='utf-8')
(out/'candidate-executor.cpp').write_text(candidate+'\n',encoding='utf-8')
(out/'candidate-assignment.h').write_text(proposed_assignment+'\n',encoding='utf-8')
(out/'candidate-classification.cpp').write_text(classification+'\n'+primary_record+'\n',encoding='utf-8')
(out/'candidate-equality.cpp').write_text(proposed_equality+'\n',encoding='utf-8')
cpp=out/'test.cpp';cpp.write_text(fixture+value_equality+original_equality.replace('STacticalAssignment','STacticalAssignmentOriginal')+proposed_equality+actual+candidate+tests,encoding='utf-8')
if '--prepare-only' in sys.argv:print('Prepared ignored executor/assignment/classifier/equality artifacts; no compiler executed.');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'test.exe'
compiled=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(compiled.stdout+compiled.stderr,encoding='utf-8')
if compiled.returncode:print(compiled.stdout+compiled.stderr);sys.exit(compiled.returncode)
ran=subprocess.run([str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=20)
print(ran.stdout+ran.stderr,end='');assert path.read_text(encoding='utf-8-sig')==source,'Prototype must not edit production'
(out/'result.json').write_text(json.dumps(dict(returncode=ran.returncode,output=ran.stdout+ran.stderr,original_executor_sha256=hashlib.sha256(actual.encode()).hexdigest(),candidate_executor_sha256=hashlib.sha256(candidate.encode()).hexdigest(),production_unchanged=True,scope='Complete extracted executor with deterministic mission services; poison detects stale reads without UB. No native-game equivalence or timing claim.'),indent=2)+'\n')
sys.exit(ran.returncode)
