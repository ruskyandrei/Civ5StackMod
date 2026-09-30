"""Exercise the real capture executor and movement guard with Civ V's city-legality fragment."""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/reserved-capture-execution-regression';out.mkdir(exist_ok=True)
tactical=(core/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
unit=(core/'CvUnit.cpp').read_text(encoding='utf-8-sig')
def function(text,signature):
 start=text.index(signature);end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
actual='\n'.join(function(tactical,s) for s in ('bool CvTacticalAI::TryReservedCityCapture(', 'int CvTacticalAI::ExecuteMoveToPlot('))
start=unit.index('\t// Added in Civ 5: Destination plots',unit.index('bool CvUnit::canMoveInto('))
end=unit.index('\n\telse\n\t{',unit.index('\tif (plot.isEnemyCity(*this))',start))
city_guard=unit[start:end]
prefix=r'''
#define _SECURE_SCL 0
#define _HAS_ITERATOR_DEBUGGING 0
#include <cstdio>
#include <climits>
#include <map>
#include <utility>
#include <cstdarg>
using namespace std;
typedef int PromotionTypes;
const int NO_PLAYER=-1,DOMAIN_AIR=2,MISSIONAI_TACTMOVE=1;
#define GD_INT_GET(x) 60
struct CvPlot;struct CvUnit;
struct CvString{void Format(const char*,...){}const char*GetCString()const{return "fixture";}};
struct CvCity{int owner,hp,maxHP;CvCity():owner(1),hp(1),maxHP(300){}int getOwner()const{return owner;}int getDamage()const{return maxHP-hp;}int GetMaxHitPoints()const{return maxHP;}};
struct CvPlot{int id,owner;CvCity*city;CvPlot(int i=0):id(i),owner(0),city(NULL){}bool isCity()const{return city!=NULL;}int getOwner()const{return owner;}CvCity*getPlotCity()const{return city;}int GetPlotIndex()const{return id;}int getX()const{return id;}int getY()const{return 0;}bool isEnemyCity(const CvUnit&)const;CvUnit*getBestDefender(int)const{return NULL;}};
static int plotDistance(const CvPlot&a,const CvPlot&b){return a.id>b.id?a.id-b.id:b.id-a.id;}
enum{MISSION_MOVE=1,MISSION_SKIP=2,MISSION_PILLAGE=3};
namespace CvTypes{int getMISSION_MOVE_TO(){return MISSION_MOVE;}int getMISSION_SKIP(){return MISSION_SKIP;}int getMISSION_PILLAGE(){return MISSION_PILLAGE;}}
static int staleReads=0,mode=0,moveCalls=0,pillageCalls=0,skipCalls=0,opportunityCalls=0,holdReleases=0,lastFlags=0,processedID=-1,unitShot=10,retaliation=20;
static bool approachReady=true,firstPath=true,secondPath=false,pushBlock=false;
struct CvUnit{
 enum{MOVEFLAG_DESTINATION=1,MOVEFLAG_ATTACK=2,MOVEFLAG_SAFE_EMBARK_ONLY=4,MOVEFLAG_APPROX_TARGET_RING1=8,MOVEFLAG_APPROX_TARGET_RING2=16,MOVEFLAG_IGNORE_STACKING_SELF=32};
 int id,owner,hp,moves,domain;bool stale,pillage,processed;CvPlot*position;
 CvUnit(int i=7):id(i),owner(0),hp(100),moves(2),domain(0),stale(false),pillage(false),processed(false),position(NULL){}
 void read()const{if(stale)++staleReads;}
 int GetID()const{read();return id;}int getOwner()const{read();return owner;}int GetCurrHitPoints()const{read();return hp;}
 CvPlot*plot()const{read();return position;}bool canEndTurnAtPlot(const CvPlot*)const{read();return true;}bool canMove()const{read();return moves>0;}
 bool IsCivilianUnit()const{read();return false;}bool CanStackUnitAtPlot(const CvPlot*)const{read();return true;}bool isOutOfAttacks()const{read();return false;}
 bool IsCityAttackSupport()const{read();return false;}bool isNoCapture()const{read();return false;}int getDomainType()const{read();return domain;}
 bool isHasPromotion(int)const{read();return false;}bool canMoveInto(const CvPlot&,int)const;
 void SetMissionAI(int,CvPlot*,void*){read();}bool GeneratePath(CvPlot*,int flags,int,int*turns=NULL){read();lastFlags=flags;if(turns)*turns=(flags&MOVEFLAG_IGNORE_STACKING_SELF)&&pushBlock?0:1;return flags&MOVEFLAG_IGNORE_STACKING_SELF?secondPath:firstPath;}
 bool shouldPillage(CvPlot*,bool,bool)const{read();return pillage;}bool hasFreePillageMove()const{read();return false;}int GetMovementPointsAtCachedTarget()const{read();return 60;}
 bool at(int x,int)const{read();return position&&position->id==x;}int getArmyID()const{read();return -1;}bool isDelayedDeath()const{read();return false;}
 CvUnit*GetPotentialUnitToPushOut(const CvPlot&)const{read();return pushBlock?const_cast<CvUnit*>(this):NULL;}
 bool PushBlockingUnitOutOfPlot(const CvPlot&){read();return pushBlock;}CvPlot*GetLastValidDestinationPlotInCachedPath()const{read();return position;}
 CvString getName()const{read();return CvString();}int getX()const{read();return position->id;}int getY()const{read();return 0;}
 void PushMission(int,int=0,int=0,int=0,bool=false,bool=false,int=0,CvPlot* = NULL);
};
bool CvPlot::isEnemyCity(const CvUnit&u)const{return city&&owner!=u.owner;}
struct CvPlayer{map<int,CvUnit*>units;int GetID()const{return 0;}bool IsAtWarWith(int owner)const{return owner==1;}CvUnit*getUnit(int i){map<int,CvUnit*>::iterator it=units.find(i);return it==units.end()?NULL:it->second;}}player;
#define GET_PLAYER(owner) player
static CvPlot*moveTarget=NULL;static CvUnit*replacement=NULL;
void CvUnit::PushMission(int mission,int,int,int flags,bool,bool,int,CvPlot*){
 read();if(mission==MISSION_MOVE){++moveCalls;lastFlags=flags;if(mode!=4){position=moveTarget;moveTarget->owner=owner;if(moveTarget->city)moveTarget->city->owner=owner;}
  if(mode==1||mode==2){player.units.erase(id);stale=true;}else if(mode==3){player.units[id]=replacement;replacement->position=position;stale=true;}
 }else if(mission==MISSION_PILLAGE){++pillageCalls;if(mode==5){player.units.erase(id);stale=true;}}
 else if(mission==MISSION_SKIP){++skipCalls;if(mode==6){player.units.erase(id);stale=true;}}
}
struct Globals{bool getLogging()const{return false;}bool getAILogging()const{return false;}}GC;
namespace CvStackingDiagnostics{void Record(int,int,const char*,const char*,...) {}}
namespace CvStackingOffensiveAI{
 CvUnit*GetReservedCapturer(int,CvCity*){return player.getUnit(7);}
 CvPlot*GetCaptureApproachNow(CvUnit*u,CvCity*){return approachReady&&u?u->plot():NULL;}
 void ReleaseAssemblyHold(CvUnit*u){++holdReleases;u->processed=false;}
}
namespace TacticalAIHelpers{
 int GetSimulatedDamageFromAttackOnCity(CvCity*,CvUnit*,CvPlot*,int&r,int&g){r=retaliation;g=0;return unitShot;}
 void PerformRangedOpportunityAttack(CvUnit*u){++opportunityCalls;u->read();if(mode==7){player.units.erase(u->id);u->stale=true;}}
 pair<CvPlot*,int>FindSafestPlotInReach(CvUnit*u,bool){return make_pair(u->plot(),0);}
}
struct CvTacticalAI{
 CvPlayer*m_pPlayer;CvTacticalAI():m_pPlayer(&player){}
 bool TryReservedCityCapture(CvPlot*);int ExecuteMoveToPlot(CvUnit*,CvPlot*,bool,int);
 void LogTacticalMessage(const CvString&){}void UnitProcessed(int id){processedID=id;CvUnit*u=player.getUnit(id);if(u)u->processed=true;}
};
bool CvUnit::canMoveInto(const CvPlot&plot,int iMoveFlags)const{
 read();
'''
tests=r'''
static int checks=0,failures=0;static void expect(const char*n,bool ok){++checks;if(!ok){++failures;printf("FAIL %s\n",n);}}
struct Fixture{
 CvCity city;CvPlot from,target;CvUnit unit,next;CvTacticalAI tactical;
 Fixture():from(0),target(1),unit(7),next(7){player.units.clear();target.owner=1;target.city=&city;unit.position=&from;next.position=&from;player.units[7]=&unit;moveTarget=&target;replacement=&next;staleReads=mode=moveCalls=pillageCalls=skipCalls=opportunityCalls=holdReleases=0;lastFlags=0;processedID=-1;unitShot=10;retaliation=20;approachReady=firstPath=true;secondPath=pushBlock=false;}
};
int main(){
 {Fixture f;expect("actual Civ V foreigncity destination guard rejects noATTACK",!f.unit.canMoveInto(f.target,CvUnit::MOVEFLAG_DESTINATION));expect("actual Civ V foreigncity attack guard accepts ATTACK",f.unit.canMoveInto(f.target,CvUnit::MOVEFLAG_ATTACK|CvUnit::MOVEFLAG_DESTINATION));}
 {Fixture f;expect("real movement withoutattack retains foreigncity rejection",f.tactical.ExecuteMoveToPlot(&f.unit,&f.target,false,0)==INT_MAX&&moveCalls==0);}
 {Fixture f;expect("reserved capture reaches actual mission and ownership",f.tactical.TryReservedCityCapture(&f.target)&&moveCalls==1&&f.target.owner==0);expect("execution retains validated safeembark attack flags",lastFlags==(CvUnit::MOVEFLAG_ATTACK|CvUnit::MOVEFLAG_DESTINATION|CvUnit::MOVEFLAG_SAFE_EMBARK_ONLY));expect("no stale reads",staleReads==0);}
 {Fixture f;f.unit.pillage=true;expect("capture urgency does not spend validated movement on pillage",f.tactical.TryReservedCityCapture(&f.target)&&pillageCalls==0&&moveCalls==1);}
 {Fixture f;f.target.owner=0;f.city.owner=0;f.unit.pillage=true;expect("normal movement preserves automaticpillage",f.tactical.ExecuteMoveToPlot(&f.unit,&f.target,false,0)==0&&pillageCalls==1&&moveCalls==1);}
 {Fixture f;mode=1;expect("capture mission removal survives aftermission lookup",f.tactical.TryReservedCityCapture(&f.target)&&moveCalls==1&&staleReads==0&&player.getUnit(7)==NULL);}
 {Fixture f;mode=3;expect("capture mission replacement is re-resolved",f.tactical.TryReservedCityCapture(&f.target)&&player.getUnit(7)==&f.next&&staleReads==0);}
 {Fixture f;mode=4;expect("issued but aborted mission is notreportedcapture",!f.tactical.TryReservedCityCapture(&f.target)&&moveCalls==1&&f.target.owner==1);}
 {Fixture f;firstPath=false;secondPath=true;pushBlock=true;expect("blocker workaround returnzero is notreportedcapture",!f.tactical.TryReservedCityCapture(&f.target)&&moveCalls==0&&f.target.owner==1);}
 {Fixture f;unitShot=0;expect("insufficientcity damage issues no mission",!f.tactical.TryReservedCityCapture(&f.target)&&moveCalls==0&&holdReleases==0);}
 {Fixture f;retaliation=100;expect("lethalretaliation issues no mission",!f.tactical.TryReservedCityCapture(&f.target)&&moveCalls==0);}
 {Fixture f;f.city.hp=0;unitShot=0;expect("zeroHP legalcapture still executes",f.tactical.TryReservedCityCapture(&f.target)&&moveCalls==1);}
 {Fixture f;approachReady=false;expect("unreachablecapture no execution",!f.tactical.TryReservedCityCapture(&f.target)&&moveCalls==0);}
 {Fixture f;mode=5;f.target.owner=f.city.owner=0;f.unit.pillage=true;expect("pillage removal safelystopsmovement",f.tactical.ExecuteMoveToPlot(&f.unit,&f.target,true,0)==INT_MAX&&pillageCalls==1&&moveCalls==0&&staleReads==0);}
 {Fixture f;mode=7;
  expect("opportunity removal safelystopsalreadythere skip",f.tactical.ExecuteMoveToPlot(&f.unit,&f.from,true,0)==0&&skipCalls==0&&staleReads==0);
 }
 {Fixture f;mode=6;expect("skipremoval no postmission dereference",f.tactical.ExecuteMoveToPlot(&f.unit,&f.from,true,0)==0&&skipCalls==1&&staleReads==0);}
 expect("nulltarget",!Fixture().tactical.TryReservedCityCapture(NULL));
 printf("reserved capture execution actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
fixture=prefix+city_guard+'\n return true;\n}\n'+actual+tests
cpp=out/'test.cpp';cpp.write_text(fixture,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=out/'test.exe';c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='')
# The same fixture must reject the real pre-fix source, including the omitted
# attack flag and stale pointer reads. This proves it crosses the mock boundary
# that previously let the foreign-city execution bug pass offline checks.
before=subprocess.check_output(['git','show','ca5bf974d:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
before_actual='\n'.join(function(before,s) for s in ('bool CvTacticalAI::TryReservedCityCapture(', 'int CvTacticalAI::ExecuteMoveToPlot('))
control_cpp=out/'control.cpp';control_cpp.write_text(prefix+city_guard+'\n return true;\n}\n'+before_actual+tests,encoding='utf-8')
control_exe=out/'control.exe';cc=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(control_cpp),'/Fo'+str(out/'control.obj'),'/Fe'+str(control_exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'control-compile.log').write_text(cc.stdout+cc.stderr,encoding='utf-8')
if cc.returncode:print(cc.stdout+cc.stderr);sys.exit(cc.returncode)
control=subprocess.run([str(control_exe)],cwd=out,capture_output=True,text=True,timeout=30)
(out/'control-output.log').write_text(control.stdout+control.stderr,encoding='utf-8')
print('Pre-fix source control rejected as expected' if control.returncode else 'FAIL pre-fix source unexpectedly passed')
result_code=r.returncode or (0 if control.returncode else 1)
(out/'result.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256(actual.encode()).hexdigest(),city_guard_sha256=hashlib.sha256(city_guard.encode()).hexdigest(),returncode=result_code,output=r.stdout+r.stderr,control_commit='ca5bf974d',control_returncode=control.returncode,control_output=control.stdout+control.stderr,scope='Actual reservedcapture and ExecuteMoveToPlot bodies plus actual Civ V foreigncity legality fragment; deterministic path/mission services; same fixture rejects pre-fix source; no DLLbuild/game launch.'),indent=2),encoding='utf-8');sys.exit(result_code)
