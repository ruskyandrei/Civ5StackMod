"""Real tactical Update schedules current city opportunities ahead of army/withdraw duties."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/global-city-opportunities-regression';out.mkdir(exist_ok=True)
tactical=(core/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig');off=(core/'CvStackingOffensiveAI.cpp').read_text(encoding='utf-8-sig')
def function(text,s):
 a=text.index(s);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
methods='\n'.join(function(tactical,s) for s in ('bool CvTacticalAI::TryCityCaptureWithUnit(', 'bool CvTacticalAI::TryReservedCityCapture(', 'void CvTacticalAI::PlotImmediateCityOpportunities(', 'int CvTacticalAI::ExecuteMoveToPlot('))
off_methods='\n'.join(function(off,s) for s in ('bool TryStationaryCityFire(', 'bool CanCapture(', 'bool IsAssemblyHeld(', 'void ReleaseAssemblyHold(', 'CvPlot* GetCaptureApproachNow('))
update=function(tactical,'void CvTacticalAI::Update(')
prefix=r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <vector>
#include <map>
#include <utility>
#include <algorithm>
#include <cstring>
#include <cstdlib>
#include <cstdio>
#include <climits>
using namespace std;
typedef int PlayerTypes;
const int DOMAIN_LAND=2,DOMAIN_SEA=0,DOMAIN_AIR=1,NO_PLAYER=-1,MISSIONAI_TACTMOVE=0,RING1_PLOTS=7;
const int AI_TACTICAL_TARGET_ENEMY_CITY=1,AI_TACTICAL_SURGICAL_STRIKE=2;
#define GD_INT_GET(x) 60
struct CvUnit;struct CvCity;struct CvPlot;
struct CvString{void Format(const char*,...){}const char*GetCString()const{return "test";}};
struct CvPathNodeArray{size_t size()const{return 1;}CvPlot*GetPlotByIndex(int)const{return NULL;}};
struct CvPlot{
 int id,owner;bool visible;CvCity*city;vector<CvUnit*>units;vector<CvPlot*>neighbors;
 CvPlot(int i=0):id(i),owner(1),visible(true),city(NULL){}
 int GetPlotIndex()const{return id;}int getOwner()const{return owner;}bool isCity()const{return city!=NULL;}bool isVisible(int)const{return visible;}
 CvCity*getPlotCity()const{return city;}int getX()const{return id;}int getY()const{return 0;}bool isCoastalLand()const{return true;}
 int getNumUnits()const{return (int)units.size();}CvUnit*getUnitByIndex(int n)const{return units[n];}
};
static int plotDistance(const CvPlot&a,const CvPlot&b){return abs(a.id-b.id);}
static CvPlot*iterateRingPlots(CvPlot*p,int n){return n>0&&(size_t)n<=p->neighbors.size()?p->neighbors[n-1]:NULL;}
struct CvCity{CvPlot*location;int hp,maxHP;CvCity(CvPlot*p=NULL):location(p),hp(1),maxHP(300){}CvPlot*plot()const{return location;}int GetMaxHitPoints()const{return maxHP;}int getDamage()const{return maxHP-hp;}};
static bool enabled=true,retained=false,commitment=false,sameCommitment=false,allowSiege=true,removeShooter=false,removeCaptor=false,abortCapture=false;
static int shots=0,captures=0,withdrawals=0,armyHolds=0,observations=0,extraTacticalWork=0,staleReads=0,processedCalls=0,pathCalls=0,focusDeletes=0,retaliation=99,captureDamage=2,currentTurn=1;
static map<int,int>strategicObjectives;
static int cityLimit=8,unitLimit=32,dangerPercent=0,captureQueries[4]={0};
typedef pair<int,int>Key;static map<Key,int>assemblyHolds;
static void Refresh(){}static int Setting(const char*,int n){return n;}
namespace CvStacking{int GetInt(const char*key,int n){if(!strcmp(key,"AIOffensiveSupportMaximumObjectives"))return cityLimit;if(!strcmp(key,"AIOffensiveSupportMaximumUnits"))return unitLimit;if(!strcmp(key,"AIAssaultStageDangerPercent"))return dangerPercent;return n;}}
enum{MOVE_MISSION=1,RANGE_MISSION=2,SKIP_MISSION=3,PILLAGE_MISSION=4};
namespace CvTypes{int getMISSION_MOVE_TO(){return MOVE_MISSION;}int getMISSION_RANGE_ATTACK(){return RANGE_MISSION;}int getMISSION_SKIP(){return SKIP_MISSION;}int getMISSION_PILLAGE(){return PILLAGE_MISSION;}}
struct CvUnit{
 enum{MOVEFLAG_DESTINATION=1,MOVEFLAG_ATTACK=2,MOVEFLAG_SAFE_EMBARK_ONLY=4,MOVEFLAG_APPROX_TARGET_RING1=8,MOVEFLAG_APPROX_TARGET_RING2=16,MOVEFLAG_IGNORE_STACKING_SELF=32};
 int id,owner,hp,moves,danger,army,onlyTarget;bool ranged,processed,out,dead,stale,civilianCover,legal,canFire,combat,heal;CvPlot*position;CvPathNodeArray path;
 CvUnit(int i=7):id(i),owner(0),hp(100),moves(120),danger(0),army(-1),onlyTarget(-1),ranged(false),processed(false),out(false),dead(false),stale(false),civilianCover(false),legal(true),canFire(true),combat(true),heal(false),position(NULL){}
 void read()const{if(stale)++staleReads;}int GetID()const{read();return id;}int getOwner()const{read();return owner;}int getDomainType()const{read();return DOMAIN_LAND;}
 CvPlot*plot()const{read();return position;}int GetCurrHitPoints()const{read();return hp;}bool IsCombatUnit()const{read();return combat;}bool IsStackingUnit()const{read();return false;}bool isCargo()const{read();return false;}bool isDelayedDeath()const{read();return dead;}bool shouldHeal(bool)const{return heal;}
 bool canUseNow()const{read();return moves>0&&!processed&&!dead;}bool TurnProcessed()const{read();return processed;}bool isOutOfAttacks()const{read();return out;}bool canMove()const{read();return moves>0;}
 bool IsCanAttackWithMove()const{read();return !ranged;}bool isNoCapture()const{read();return false;}bool IsCanAttackRanged()const{read();return ranged;}int GetRange()const{read();return 2;}
 bool isNativeDomain(const CvPlot*)const{read();return true;}bool IsCoveringFriendlyCivilian()const{read();return civilianCover;}bool canRangeStrikeAt(int x,int)const{read();return ranged&&canFire&&!out&&!processed&&moves>0&&abs(position->id-x)<=2&&(onlyTarget<0||x==onlyTarget);}
 int GetDanger()const{read();return danger;}void SetTurnProcessed(bool b){read();processed=b;}int baseMoves(bool)const{read();return 2;}int getArmyID()const{read();return army;}
 bool canMoveInto(const CvPlot&p,int flags)const{read();return legal&&(!p.isCity()||p.owner==owner||(flags&MOVEFLAG_ATTACK));}
 bool canEndTurnAtPlot(const CvPlot*)const{read();return true;}void SetMissionAI(int,CvPlot*,void*){read();}
 bool GeneratePath(CvPlot*,int,int,int*turns=NULL){read();++pathCalls;if(turns)*turns=1;return legal;}CvPlot*GetPathEndFirstTurnPlot()const{read();return position;}const CvPathNodeArray&GetLastPath()const{read();return path;}
 bool shouldPillage(CvPlot*,bool,bool)const{read();return false;}bool hasFreePillageMove()const{read();return false;}int GetMovementPointsAtCachedTarget()const{read();return 0;}
 bool at(int x,int)const{read();return position->id==x;}CvUnit*GetPotentialUnitToPushOut(const CvPlot&)const{return NULL;}bool PushBlockingUnitOutOfPlot(const CvPlot&){return false;}CvPlot*GetLastValidDestinationPlotInCachedPath()const{return NULL;}
 CvString getName()const{return CvString();}int getX()const{return position->id;}int getY()const{return 0;}
 void PushMission(int,int=0,int=0,int=0,bool=false,bool=false,int=0,CvPlot* = NULL);
};
struct CvPlayer{
 vector<CvUnit*>owned;map<int,CvUnit*>units;int GetID()const{return 0;}int getTeam()const{return 0;}bool IsAtWarWith(int p)const{return p==1;}
 CvUnit*getUnit(int i){map<int,CvUnit*>::iterator it=units.find(i);return it==units.end()?NULL:it->second;}
 CvUnit*firstUnit(int*n){*n=0;return owned.empty()?NULL:owned[0];}CvUnit*nextUnit(int*n){return ++*n<(int)owned.size()?owned[*n]:NULL;}
}players[4];
#define GET_PLAYER(owner) players[owner]
struct Map{map<int,CvPlot*>plots;CvPlot*plot(int x,int){return plotByIndexUnchecked(x);}CvPlot*plotByIndexUnchecked(int i){map<int,CvPlot*>::iterator it=plots.find(i);return it==plots.end()?NULL:it->second;}};
struct Globals{Map map;Map&getMap(){return map;}bool getLogging()const{return false;}bool getAILogging()const{return false;}}GC;
void CvUnit::PushMission(int mission,int x,int,int,bool,bool,int,CvPlot*){read();CvPlot*target=GC.map.plot(x,0);if(mission==RANGE_MISSION){++shots;if(target&&target->city)target->city->hp=max(1,target->city->hp-20);moves=0;out=true;if(removeShooter){players[0].units.erase(id);stale=true;}}
 else if(mission==MOVE_MISSION){if(!abortCapture&&target){position=target;target->owner=owner;++captures;}moves=0;if(removeCaptor){players[0].units.erase(id);stale=true;}}
}
namespace CvStackingAI{bool RetainCityUnit(const CvUnit*){return retained;}}
namespace CvStackingDiagnostics{void Record(int,int,const char*,const char*,...) {}struct TurnPhaseScope{TurnPhaseScope(int,const char*){}void Finish(){}};}
namespace TacticalAIHelpers{int GetSimulatedDamageFromAttackOnCity(CvCity*,CvUnit*,CvPlot*,int&r,int&g){r=retaliation;g=0;return captureDamage;}void PerformRangedOpportunityAttack(CvUnit*){}pair<CvPlot*,int>FindSafestPlotInReach(CvUnit*u,bool){return make_pair(u->plot(),0);}}
namespace CvStackingOffensiveAI{
 bool Enabled(int){return enabled;}bool HasCommitment(const CvUnit*,const CvPlot*p=NULL){return commitment&&(!p||sameCommitment);}bool ContinueSiege(int,CvCity*){return allowSiege;}
 void ObserveSiege(int,CvCity*c){++observations;strategicObjectives[c->plot()->GetPlotIndex()]=1;}CvUnit*GetReservedCapturer(int,CvCity*){return NULL;} // Touch-equivalent persistent city objective; no reservation on purpose
 bool IsSiegeUnit(const CvUnit*u){return u&&u->ranged;}bool IsAssemblyHeld(const CvUnit*);void ReleaseAssemblyHold(CvUnit*);CvPlot*GetCaptureApproachNow(CvUnit*,CvCity*);bool CanCapture(const CvUnit*,const CvPlot*);
 bool TryStationaryCityFire(CvUnit*,const CvPlot*);
}
struct CvTacticalTarget{int x,type;CvTacticalTarget(int n):x(n),type(AI_TACTICAL_TARGET_ENEMY_CITY){}int GetTargetType()const{return type;}int GetTargetX()const{return x;}int GetTargetY()const{return 0;}};
struct CvTacticalAI{
 CvPlayer*m_pPlayer;vector<CvTacticalTarget>m_AllTargets;vector<int>currentFree;
 CvTacticalAI():m_pPlayer(&players[0]){}void Update();void PlotImmediateCityOpportunities();bool TryReservedCityCapture(CvPlot*);bool TryCityCaptureWithUnit(CvUnit*,CvPlot*);int ExecuteMoveToPlot(CvUnit*,CvPlot*,bool,int);
 void UpdateVisibility(){}void DropOldFocusAreas(){}void FindTacticalTargets(){}void ClearCurrentMoveUnits(int){}void DeleteFocusArea(CvPlot*){++focusDeletes;}void LogTacticalMessage(const CvString&){}
 void RecruitUnits(){currentFree.clear();for(size_t i=0;i<players[0].owned.size();++i)if(players[0].owned[i]->army<0)currentFree.push_back(players[0].owned[i]->id);}
 void ProcessDominanceZones(){extraTacticalWork+=(int)strategicObjectives.size();for(size_t i=0;i<players[0].owned.size();++i){CvUnit*u=players[0].getUnit(players[0].owned[i]->id);if(!u||u->processed||!u->canUseNow())continue;if(u->army>=0){++armyHolds;u->processed=true;}else{++withdrawals;u->moves=0;}}}
 void UnitProcessed(int id){++processedCalls;CvUnit*u=players[0].getUnit(id);if(u)u->processed=true;}
};
'''
tests=r'''
static int checks=0,failures=0;static void expect(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<15)printf("FAIL %s\n",n);}}
struct Fixture{
 CvPlot at,cityPlot,secondPlot;CvCity city,second;CvUnit unit;CvTacticalAI tactical;
 Fixture():at(29),cityPlot(30),secondPlot(31),city(&cityPlot),second(&secondPlot),unit(7){
  enabled=true;retained=commitment=sameCommitment=removeShooter=removeCaptor=abortCapture=false;allowSiege=true;shots=captures=withdrawals=armyHolds=observations=extraTacticalWork=staleReads=processedCalls=pathCalls=focusDeletes=0;retaliation=99;captureDamage=2;cityLimit=8;unitLimit=32;dangerPercent=0;assemblyHolds.clear();strategicObjectives.clear();captureQueries[0]=0;
  players[0].owned.clear();players[0].units.clear();GC.map.plots.clear();unit.position=&at;at.units.push_back(&unit);cityPlot.city=&city;secondPlot.city=&second;cityPlot.neighbors.push_back(&at);secondPlot.neighbors.push_back(&at);
  players[0].owned.push_back(&unit);players[0].units[7]=&unit;GC.map.plots[at.id]=&at;GC.map.plots[cityPlot.id]=&cityPlot;GC.map.plots[secondPlot.id]=&secondPlot;tactical.m_AllTargets.push_back(CvTacticalTarget(cityPlot.id));
 }
};
int main(){
 {Fixture f;f.tactical.Update();expect("realUpdate instantcapture runs before withdraw",captures==1&&withdrawals==0&&f.cityPlot.owner==0);expect("missingobjective still permits adjacent fallback",observations==0&&processedCalls==1);expect("instantcapture needs no new strategicobjective",strategicObjectives.empty()&&extraTacticalWork==0);expect("adjacentfallback creates no approachpath",pathCalls==1);}
 {Fixture f;f.city.hp=30;captureDamage=2;f.tactical.Update();expect("weakcity insufficient adjacentmelee cannot capture",captures==0&&shots==0&&f.cityPlot.owner==1);expect("insufficient attack creates no strategicobjective in eitherweakbranch",observations==0&&strategicObjectives.empty());expect("insufficient attack adds no subsequent tacticalplanning work",extraTacticalWork==0);expect("insufficient attack retains ordinarywithdraw without pathwork",withdrawals==1&&pathCalls==0);}
 {Fixture f;f.unit.ranged=true;f.unit.army=42;f.city.hp=300;f.tactical.Update();expect("armyexcluded battery fires before operationalhold",shots==1&&armyHolds==0&&f.tactical.currentFree.empty());expect("stationaryfire has zero pathwork",pathCalls==0);}
 {Fixture f;f.unit.ranged=true;f.unit.army=42;f.city.hp=300;f.unit.danger=49;f.tactical.Update();expect("exposedbattery still yields to armyprocessing",shots==0&&armyHolds==1);}
 {Fixture f;f.unit.processed=true;f.tactical.Update();expect("arbitraryprocessed capturer remains unavailable",captures==0&&pathCalls==0);}
 {Fixture f;f.unit.ranged=true;f.unit.processed=true;f.city.hp=300;f.tactical.Update();expect("arbitraryprocessed battery remains unavailable",shots==0);}
 {Fixture f;enabled=false;f.tactical.Update();expect("generic disabled module preserves originalwithdraw",captures==0&&shots==0&&withdrawals==1&&observations==0);}
 {Fixture f;f.cityPlot.visible=false;f.tactical.Update();expect("hidden enemycity is never inspected for actions",captures==0&&observations==0);}
 {Fixture f;f.cityPlot.owner=2;f.tactical.Update();expect("neutral city never targeted",captures==0&&observations==0);}
 {Fixture f;retaliation=100;f.tactical.Update();expect("lethal retaliation remains rejected",captures==0);}
 {Fixture f;f.unit.ranged=true;f.city.hp=300;commitment=true;sameCommitment=false;f.tactical.Update();expect("different explicit commitment not redirected",shots==0);}
 {Fixture f;f.unit.ranged=true;f.city.hp=300;retained=true;f.tactical.Update();expect("retained citydefender not commandeered",shots==0);}
 {Fixture f;f.unit.ranged=true;f.city.hp=300;f.unit.out=true;f.tactical.Update();expect("spent attack allowance not reused",shots==0);}
 {Fixture f;f.unit.ranged=true;f.city.hp=300;removeShooter=true;f.tactical.Update();expect("firing callback deletion safe through scheduler",shots==1&&staleReads==0);}
 {Fixture f;removeCaptor=true;f.tactical.Update();expect("capture callback deletion safelyre-resolved",captures==1&&staleReads==0&&withdrawals==0);}
 {Fixture f;f.unit.ranged=true;f.city.hp=f.second.hp=300;f.tactical.m_AllTargets.push_back(CvTacticalTarget(f.secondPlot.id));f.tactical.Update();expect("only highestpriorityeligiblecity shot once",shots==1&&f.city.hp==280&&f.second.hp==300);}
 {Fixture f;f.unit.ranged=true;f.city.hp=300;unitLimit=0;f.tactical.Update();expect("existing maximum-unit workbudget honored",shots==0);}
 {Fixture f;f.unit.ranged=true;f.city.hp=300;cityLimit=0;f.tactical.Update();expect("existing maximum-objective workbudget honored",shots==0);}
 {Fixture f;f.unit.processed=true;assemblyHolds[Key(0,7)]=currentTurn;expect("specific held adjacent fallback can finish capture",f.tactical.TryReservedCityCapture(&f.cityPlot)&&captures==1&&!CvStackingOffensiveAI::IsAssemblyHeld(&f.unit));}
 {Fixture f;abortCapture=true;expect("aborted capture not reported as ownership success",!f.tactical.TryReservedCityCapture(&f.cityPlot)&&captures==0&&f.cityPlot.owner==1);}
 {Fixture f;f.unit.ranged=true;f.unit.heal=true;f.unit.hp=77;f.city.hp=300;f.tactical.Update();expect("global nondeterminative shot does not steal woundedhealing priority",shots==0);}
 {Fixture f;f.unit.heal=true;f.unit.hp=99;retaliation=98;f.tactical.Update();expect("surviving wounded instantcapture remains eligible",captures==1&&withdrawals==0);}
 {Fixture f;CvUnit workers[33];f.at.units.clear();for(int i=0;i<33;++i){workers[i].id=100+i;workers[i].combat=false;workers[i].position=&f.at;f.at.units.push_back(&workers[i]);}f.at.units.push_back(&f.unit);unitLimit=1;expect("workers cannot exhaust adjacentcapturer workbudget",f.tactical.TryReservedCityCapture(&f.cityPlot)&&captures==1);}
 {Fixture f;f.unit.ranged=true;f.unit.onlyTarget=f.cityPlot.id;f.city.hp=f.second.hp=300;cityLimit=2;CvUnit next(8);next.ranged=true;next.onlyTarget=f.secondPlot.id;next.position=&f.at;players[0].owned.push_back(&next);players[0].units[8]=&next;f.tactical.m_AllTargets.push_back(CvTacticalTarget(f.cityPlot.id));f.tactical.m_AllTargets.push_back(CvTacticalTarget(f.secondPlot.id));f.tactical.Update();expect("duplicatecity targets do not exhaust citybudget",shots==2&&f.city.hp==280&&f.second.hp==280);}
 printf("global city opportunity actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
base=prefix+function(off,'bool Usable(')+'\nnamespace CvStackingOffensiveAI{\n'+off_methods+'\n}\n'+methods
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
def run(label,body,method_source=None):
 fixture=(base if method_source is None else base.replace(methods,method_source))+body+tests;cpp=out/(label+'.cpp');cpp.write_text(fixture,encoding='utf-8');exe=out/(label+'.exe')
 c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/(label+'.obj')),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/(label+'-compile.log')).write_text(c.stdout+c.stderr,encoding='utf-8')
 if c.returncode:print(c.stdout+c.stderr);raise SystemExit(c.returncode)
 r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);(out/(label+'-output.log')).write_text(r.stdout+r.stderr,encoding='utf-8');return r,fixture
r,fixture=run('current',update);print(r.stdout+r.stderr,end='')
old=subprocess.check_output(['git','show','86efe6178:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig');control,_=run('control',function(old,'void CvTacticalAI::Update('));print('Previous global scheduling control rejected as expected' if control.returncode==1 else 'FAIL prepass scheduling did not fail assertions')
objective_old=subprocess.check_output(['git','show','b9d60c04b:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
objective_methods=methods.replace(function(tactical,'void CvTacticalAI::PlotImmediateCityOpportunities('),function(objective_old,'void CvTacticalAI::PlotImmediateCityOpportunities('))
objective_control,_=run('objective-control',update,objective_methods);print('Previous objective-creating global pass rejected as expected' if objective_control.returncode==1 else 'FAIL objective-creating global pass did not fail assertions')
result=r.returncode or (0 if control.returncode==1 and objective_control.returncode==1 else 1)
(out/'result.json').write_text(json.dumps(dict(fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),returncode=result,output=r.stdout+r.stderr,control_commit='86efe6178',control_returncode=control.returncode,control_output=control.stdout+control.stderr,objective_control_commit='b9d60c04b',objective_control_returncode=objective_control.returncode,objective_control_output=objective_control.stdout+objective_control.stderr,scope='Actual tacticalUpdate/newglobalpass/capturefallback/captureexecutor/movement and stationaryfire/availability helpers; deterministic objective creation/planning-count, armyhold/withdraw/range/danger/path/mission services. ObserveSiege models Touch by persistent unique city IDs; follow-on planning count is a service stub, not a native time measurement. No native DLLbuild/game launch.'),indent=2),encoding='utf-8');sys.exit(result)
