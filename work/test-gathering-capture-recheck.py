"""Safe assembly fire must be followed by a real, surviving capture opportunity check."""
from pathlib import Path
import ast,hashlib,json,os,re,subprocess,sys
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2'
out=root/'work/gathering-capture-recheck-regression';out.mkdir(exist_ok=True)
tactical=(core/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
offensive=(core/'CvStackingOffensiveAI.cpp').read_text(encoding='utf-8-sig')
unit=(core/'CvUnit.cpp').read_text(encoding='utf-8-sig')
def block(text,start):
 end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
def function(text,signature):return block(text,text.index(signature))
def gathering(text):return block(text,text.index('if(!land.ready && !sea.ready)',text.index('void CvTacticalAI::ExecuteCaptureCityMoves(')))
actual='\n'.join(function(tactical,s) for s in ('bool CvTacticalAI::TryReservedCityCapture(', 'int CvTacticalAI::ExecuteMoveToPlot('))
stage_start=offensive.index('bool StageUnit(')
safe=block(offensive,offensive.index('if(unit->IsCanAttackRanged()',stage_start))
hold=block(offensive,offensive.index('if(currentDanger<=dangerLimit',stage_start))
source_methods='\n'.join(function(offensive,s) for s in ('bool IsAssemblyHeld(', 'void ReleaseAssemblyHold(', 'CvPlot* GetCaptureApproachNow(', 'bool CanCapture('))
usable=function(offensive,'bool Usable(')
a=unit.index('\t// Added in Civ 5: Destination plots',unit.index('bool CvUnit::canMoveInto('))
b=unit.index('\n\telse\n\t{',unit.index('\tif (plot.isEnemyCity(*this))',a));city_guard=unit[a:b]
# Reuse only the literal engine services from the movement fixture, never run
# that Python script or its tests. The production functions below stay literal.
tree=ast.parse((root/'work/test-reserved-capture-execution.py').read_text(encoding='utf-8'))
prefix=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='prefix' for t in n.targets))
prefix=prefix.replace('#include <map>','#include <map>\n#include <vector>\n#include <algorithm>')
prefix=prefix.replace('const int NO_PLAYER=-1,DOMAIN_AIR=2,', 'const int DOMAIN_LAND=0,DOMAIN_SEA=1;\nconst int NO_PLAYER=-1,DOMAIN_AIR=2,')
prefix=prefix.replace('bool isCity()const{return city!=NULL;}', 'bool isCoastalLand()const{return true;}bool isCity()const{return city!=NULL;}')
prefix=prefix.replace('struct CvPlot;struct CvUnit;','struct CvPlot;struct CvUnit;\nstruct CvPathNodeArray{size_t size()const{return 1;}CvPlot*GetPlotByIndex(int)const{return NULL;}};')
prefix=prefix.replace('struct CvCity{int owner,hp,maxHP;','struct CvCity{CvPlot*location;CvPlot*plot()const{return location;}int owner,hp,maxHP;')
prefix=prefix.replace('MISSION_PILLAGE=3','MISSION_PILLAGE=3,MISSION_RANGE=4')
prefix=prefix.replace('namespace CvTypes{','namespace CvTypes{int getMISSION_RANGE_ATTACK(){return MISSION_RANGE;}')
prefix=prefix.replace('struct CvUnit{','struct CvUnit{bool ranged;CvPathNodeArray path;')
prefix=prefix.replace('CvUnit(int i=7):id(i)','CvUnit(int i=7):ranged(false),id(i)')
prefix=prefix.replace('void PushMission(int,int=0',r'''
 bool IsCombatUnit()const{read();return true;}bool IsStackingUnit()const{read();return false;}bool isCargo()const{read();return false;}
 bool IsCanAttackWithMove()const{read();return !ranged;}bool IsCanAttackRanged()const{read();return ranged;}
 int GetMaxHitPoints()const{read();return 100;}bool isNativeDomain(const CvPlot*)const{read();return true;}
 int GetDanger()const{read();return 0;}
 int baseMoves(bool)const{read();return 2;}
 bool canUseNow()const{read();return moves>0&&!processed;}void SetTurnProcessed(bool value){read();processed=value;}
 bool canRangeStrikeAt(int,int)const{read();return ranged;}const CvPathNodeArray&GetLastPath()const{read();return path;}
 CvPlot*GetPathEndFirstTurnPlot()const{read();return position;}
 void PushMission(int,int=0''')
prefix=prefix.replace('static CvPlot*moveTarget=NULL;', 'static int softeningDamage=20,focusDeletes=0;static bool removeRange=false,removeCapturer=false;\nstatic CvPlot*moveTarget=NULL;')
prefix=prefix.replace('read();if(mission==MISSION_MOVE)',r'''read();if(mission==MISSION_RANGE){moveTarget->city->hp=max(1,moveTarget->city->hp-softeningDamage);moves=0;if(removeRange){player.units.erase(id);stale=true;}}
 else if(mission==MISSION_MOVE)''')
ns_start=prefix.index('namespace CvStackingOffensiveAI{');ns_end=prefix.index('namespace TacticalAIHelpers{',ns_start)
prefix=prefix[:ns_start]+r'''
typedef pair<int,int> Key;static map<Key,int>assemblyHolds;static int currentTurn=1,captureQueries[4]={0};
static int Setting(const char*,int value){return value;}static void Refresh(){}
namespace CvStackingOffensiveAI{
 struct AssaultPlan{bool ready;AssaultPlan():ready(false){}};
 CvUnit*GetReservedCapturer(int,CvCity*){return player.getUnit(7);}
 bool IsAssemblyHeld(const CvUnit*);void ReleaseAssemblyHold(CvUnit*);CvPlot*GetCaptureApproachNow(CvUnit*,CvCity*);bool CanCapture(const CvUnit*,const CvPlot*);
 bool ContinueSiege(int,CvCity*){return true;}bool HasCommitment(CvUnit*,const CvPlot*){return true;}void RecordTransfer(CvUnit*,int,int,int){}
}
''' +prefix[ns_end:]
prefix=prefix.replace('struct CvTacticalAI{',r'''
struct MoveUnit{int id;MoveUnit(int n):id(n){}int GetID()const{return id;}};
struct CvTacticalAI{vector<MoveUnit>m_CurrentMoveUnits;
 void PositionUnitsAroundTarget(const vector<CvUnit*>&,CvPlot*);void DeleteFocusArea(CvPlot*){++focusDeletes;}
 void GatheringCapturePass(CvPlot*);
''')
prefix=re.sub(r'\bplayer\b','worldPlayer',prefix)
stage=r'''
static bool StageService(CvUnit*unit,const CvPlot*cityTarget){
 using namespace CvStackingOffensiveAI;
 if(!Usable(unit)||!unit->canUseNow())return false;
 const int owner=unit->getOwner(),currentDanger=0,dangerLimit=0,radius=2;CvPlayer&player=GET_PLAYER(owner);CvPlot*stage=unit->plot();
'''+safe+hold+r'''
 return false;
}
void CvTacticalAI::PositionUnitsAroundTarget(const vector<CvUnit*>&units,CvPlot*target){
 for(size_t i=0;i<units.size();++i)StageService(units[i],target);
 if(removeCapturer){CvUnit*u=worldPlayer.getUnit(7);if(u){worldPlayer.units.erase(7);u->stale=true;}}
}
'''
def pass_code(branch):
 return r'''
void CvTacticalAI::GatheringCapturePass(CvPlot*pPlot){
 if(TryReservedCityCapture(pPlot)){DeleteFocusArea(pPlot);return;}
 CvStackingOffensiveAI::AssaultPlan land,sea;
 for(int once=0;once<1;++once){
''' +branch+'\n}\n}\n'
tests=r'''
static int checks=0,failures=0;static void expect(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<15)printf("FAIL %s\n",n);}}
struct Fixture{
 CvCity city;CvPlot from,target;CvUnit capturer,ranged;CvTacticalAI tactical;
 Fixture(bool rangedFirst=true):from(0),target(1),capturer(7),ranged(8){
  player.units.clear();assemblyHolds.clear();currentTurn=1;captureQueries[0]=0;target.owner=1;target.city=&city;city.location=&target;city.hp=21;
  capturer.position=ranged.position=&from;ranged.ranged=true;player.units[7]=&capturer;player.units[8]=&ranged;moveTarget=&target;
  staleReads=mode=moveCalls=pillageCalls=skipCalls=opportunityCalls=holdReleases=focusDeletes=0;lastFlags=0;processedID=-1;unitShot=17;retaliation=33;softeningDamage=20;removeRange=removeCapturer=false;approachReady=firstPath=true;secondPath=pushBlock=false;
  tactical.m_CurrentMoveUnits.push_back(MoveUnit(rangedFirst?8:7));tactical.m_CurrentMoveUnits.push_back(MoveUnit(rangedFirst?7:8));
 }
};
int main(){
 for(int order=0;order<2;++order){Fixture f(order!=0);expect("initial17damage cannot capture21HPcity",!f.tactical.TryReservedCityCapture(&f.target)&&moveCalls==0);
  f.tactical.GatheringCapturePass(&f.target);expect("safe staging shot opens same-turn actualcapture",f.target.owner==0&&moveCalls==1&&focusDeletes==1);
  expect("actual assemblyhold released only for executablecapture",!f.capturer.processed&&!CvStackingOffensiveAI::IsAssemblyHeld(&f.capturer));expect("no staleunit reads",staleReads==0);
 }
 {Fixture f;softeningDamage=0;f.tactical.GatheringCapturePass(&f.target);expect("no sufficient softening no capture",f.target.owner==1&&moveCalls==0&&focusDeletes==0);expect("insufficientdamage preserves assemblyhold",f.capturer.processed&&CvStackingOffensiveAI::IsAssemblyHeld(&f.capturer));}
 {Fixture f;retaliation=100;f.tactical.GatheringCapturePass(&f.target);expect("lethalcapture retaliation remainsblocked",f.target.owner==1&&moveCalls==0&&focusDeletes==0);expect("lethalcapture leaves hold",CvStackingOffensiveAI::IsAssemblyHeld(&f.capturer));}
 {Fixture f;f.capturer.processed=true;f.tactical.GatheringCapturePass(&f.target);expect("arbitraryprocessed unit cannot be reused aftersoftening",f.target.owner==1&&f.city.hp==1&&moveCalls==0&&!CvStackingOffensiveAI::IsAssemblyHeld(&f.capturer));}
 {Fixture f;mode=4;f.tactical.GatheringCapturePass(&f.target);expect("abortedcapture has no false focuscleanup",f.target.owner==1&&moveCalls==1&&focusDeletes==0);}
 {Fixture f;removeCapturer=true;f.tactical.GatheringCapturePass(&f.target);expect("capturer removed by stagingcallback safelyskipped",f.target.owner==1&&moveCalls==0&&staleReads==0);}
 {Fixture f;removeRange=true;f.tactical.GatheringCapturePass(&f.target);expect("rangedshooter removal preserves newopportunity and identitysafety",f.target.owner==0&&moveCalls==1&&staleReads==0);}
 printf("gathering capture recheck actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
tests=re.sub(r'\bplayer\b','worldPlayer',tests)
base=prefix+city_guard+'\n return true;\n}\n'+usable+'\nnamespace CvStackingOffensiveAI{\n'+source_methods+'\n}\n'+actual+stage
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
def run(label,branch):
 fixture=base+pass_code(branch)+tests;cpp=out/(label+'.cpp');cpp.write_text(fixture,encoding='utf-8');exe=out/(label+'.exe')
 c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/(label+'.obj')),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60);(out/(label+'-compile.log')).write_text(c.stdout+c.stderr,encoding='utf-8')
 if c.returncode:print(c.stdout+c.stderr);raise SystemExit(c.returncode)
 r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);(out/(label+'-output.log')).write_text(r.stdout+r.stderr,encoding='utf-8');return r,fixture
r,fixture=run('current',gathering(tactical));print(r.stdout+r.stderr,end='')
before=subprocess.check_output(['git','show','effbe594a:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig')
control,_=run('control',gathering(before));print('Pre-recheck assembly branch rejected as expected' if control.returncode==1 else 'FAIL missing recheck control did not return the expected assertion failure')
result=r.returncode or (0 if control.returncode==1 else 1)
(out/'result.json').write_text(json.dumps(dict(fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),returncode=result,output=r.stdout+r.stderr,control_commit='effbe594a',control_returncode=control.returncode,control_output=control.stdout+control.stderr,scope='Actual gathering branch, safe stagingfire/hold branches, captureexecutor/movement, legalcapture/hold release and foreigncity legality fragment. Deterministic path/mission services; actual ownership and deletion safety. No DLLbuild/game launch.'),indent=2),encoding='utf-8');sys.exit(result)
