"""Actual-source lexical previous-score differential; --prepare-only does not compile."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'work/previous-plot-score-regression';OUT.mkdir(exist_ok=True)
STAGE=ROOT/'work/previous-plot-score-staged';CONTROL='f194cff95'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--prepare-only',action='store_true');parser.add_argument('--production',action='store_true');args=parser.parse_args()

def block(source,signature,semicolon=False):
 start=source.index(signature);end=source.index('{',start)+1;depth=1
 while depth:depth+=(source[end]=='{')-(source[end]=='}');end+=1
 if semicolon:assert source[end]==';';end+=1
 return source[start:end]

old=subprocess.check_output(['git','show',CONTROL+':CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=ROOT).decode('utf-8-sig')
staged=(STAGE/'CvTacticalAI.cpp').read_text(encoding='utf-8')
new=(ROOT/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_text(encoding='utf-8-sig') if args.production else staged
assert new==staged,'Current production differs from reviewed previous-score stage'
header=subprocess.check_output(['git','show',CONTROL+':CvGameCoreDLL_Expansion2/CvTacticalAI.h'],cwd=ROOT).decode('utf-8-sig')
unit_header=subprocess.check_output(['git','show',CONTROL+':CvGameCoreDLL_Expansion2/CvUnit.h'],cwd=ROOT).decode('utf-8-sig')
utils=subprocess.check_output(['git','show',CONTROL+':CvGameCoreDLL_Expansion2/CvGameCoreUtils.h'],cwd=ROOT).decode('utf-8-sig')
proof=json.loads((STAGE/'staging-proof.json').read_text(encoding='utf-8'))
assert proof['source_sha256']==hashlib.sha256(old.encode()).hexdigest() and proof['candidate_sha256']==hashlib.sha256(new.encode()).hexdigest()
helper=block(new,'struct PreviousPlotScoreQuery',True)+'\n\n'+block(new,'static int GetPrevPlotScore(int unitID,')
added_start=new.index('// Preferred scoring holds one actor')
added_end=new.index('static STacticalAssignment* ScorePlotForPillageMove(',added_start)
restored=new[:added_start]+new[added_end:]
for name in proof['scorers_with_default_null']:
 original=block(old,'static STacticalAssignment* '+name+'(')
 candidate=block(new,'static STacticalAssignment* '+name+'(')
 expected=original.replace(')\n{',', PreviousPlotScoreQuery* previousScore = NULL)\n{',1)
 if name=='ScorePlotForMove':
  expected=expected.replace('evalMode, leavingProtection);','evalMode, leavingProtection, previousScore);').replace('evalMode);','evalMode, previousScore);')
 else:expected=expected.replace('GetPrevPlotScore(unit.iUnitID, assumedPosition)','GetPrevPlotScore(unit.iUnitID, assumedPosition, previousScore)')
 assert candidate==expected,name+' scorer changed beyond optional query plumbing'
 restored=restored.replace(candidate,original,1)
preferred_new=block(new,'void CvTacticalPosition::getPreferredAssignmentsForUnit(')
preferred_old=block(old,'void CvTacticalPosition::getPreferredAssignmentsForUnit(')
restored_pref=preferred_new.replace('\tPreviousPlotScoreQuery previousScore(unit.iUnitID, *this);\n','',1)
restored_pref=restored_pref.replace(', NULL, &previousScore)',')').replace(', &previousScore)',')')
assert restored_pref==preferred_old,'Preferred statements/order changed beyond explicit query plumbing'
restored=restored.replace(preferred_new,preferred_old,1)
assert restored==old,'Stage has unreviewed source changes'
values=block(unit_header,'struct SUnitIDValueContainer',True)
enums=header[header.index('enum CLOSED_ENUM eUnitMoveEvalMode'):header.index('struct STacticalAssignment')]
assignment=block(header,'struct STacticalAssignment',True)
cow='template<typename T>\n'+block(header,'struct SCoWField',True)
option='template<class T>\n'+block(utils,'struct OptionWithScore',True)
latest=block(old,'const STacticalAssignment* CvBasePosition::getLatestAssignment(')
latest_counted=latest.replace('{\n','{\n ++latestCalls;\n',1).replace('if (it->iUnitID == iUnitID)','if ((++latestRows, it->iUnitID == iUnitID))',1)
prefix=r'''
#define NOMINMAX
#define CLOSED_ENUM
#define VALIDATE_OBJECT() ((void)0)
#define ASSERT(...) ((void)0)
#include <windows.h>
#include <vector>
#include <algorithm>
#include <utility>
#include <cstdio>
#include <cstdlib>
#include <climits>
#include <new>
using namespace std;
typedef int PlayerTypes;const int NO_PLAYER=-1;
const short TACTICAL_COMBAT_IMPOSSIBLE_SCORE=-1000;
static int latestCalls=0,latestRows=0,contextCalls=0,sceneReads=0;
static bool gStackForecastsActive=true;static unsigned int gStackForecastDepth=1;
static unsigned long gStackForecastRevision=1;static bool contextAllowed=true,contextChangesRevision=false;
namespace CvStackingStrengthCache{long liveScene=1;long SceneEpoch(){++sceneReads;return liveScene;}}
static bool StackForecastContext(){++contextCalls;if(contextChangesRevision){++gStackForecastRevision;contextChangesRevision=false;}return contextAllowed&&gStackForecastsActive&&gStackForecastDepth==1;}
namespace CvStackingDiagnostics{enum{PLAN_PREFERRED_ASSIGNMENTS=1};struct PlanSampleScope{PlanSampleScope(int){}};}
namespace CvStacking{bool enabled=true;bool IsEnabled(){return enabled;}}
static size_t allocations=0;void*operator new(size_t n){++allocations;void*p=malloc(n?n:1);if(!p)throw bad_alloc();return p;}
void operator delete(void*p){free(p);}void*operator new[](size_t n){return ::operator new(n);}void operator delete[](void*p){::operator delete(p);}
'''
services=r'''
struct CvBasePosition{
 SCoWField<vector<STacticalAssignment> >assignedMoves;
 const vector<STacticalAssignment>&getAssignments()const{return assignedMoves.read();}
 const STacticalAssignment*getLatestAssignment(int)const;
};
const int DOMAIN_LAND=0,DOMAIN_SEA=1,UNITAI_CITY_BOMBARD=1,TACTICAL_COMBAT_MAX_TARGET_DISTANCE=2;
int scenarioSeed=0;bool noUnit=false;
struct CvPlot{int index;CvPlot(int n=0):index(n){}int GetPlotIndex()const{return index;}bool isAdjacent(const CvPlot*p)const{return abs(index-p->index)<4;}};
struct CvUnit{
 bool ranged,admiral,freeMoves,afterAttack;int range,domain,ai;
 CvUnit():ranged(false),admiral(false),freeMoves(false),afterAttack(false),range(2),domain(0),ai(0){}
 bool IsCanAttackRanged()const{return ranged;}bool IsGreatAdmiral()const{return admiral;}bool canRepairFleet(const CvPlot*)const{return true;}
 int getDomainType()const{return domain;}int GetRange()const{return range;}int AI_getUnitAIType()const{return ai;}
 bool IsFreeAttackMoves()const{return freeMoves;}bool canMoveAfterAttacking()const{return afterAttack;}
}worldUnit;
struct Player{CvUnit*getUnit(int)const{return noUnit?NULL:&worldUnit;}}player;
#define GET_PLAYER(id) player
struct CvTacticalPlot{
 CvPlot plot;bool enemy,city,blocking;int distance;
 CvTacticalPlot(int n=0):plot(n),enemy(false),city(false),blocking(false),distance(2){}
 int getPlotIndex()const{return plot.index;}const CvPlot*getPlot()const{return &plot;}
 bool isEnemy()const{return enemy;}bool isEnemyCity()const{return city;}
 bool IsSimUnitBlocking(int)const{return blocking;}int getEnemyDistance()const{return distance;}
};
struct SUnitStats{
 int iPlotIndex,iUnitID,iMovesLeft,iMaxMoves,iSelfDamage,iAttacksLeft;eUnitMovementStrategy eMoveStrategy;eUnitAssignmentType eLastAssignment;CvUnit*pUnit;
 SUnitStats():iPlotIndex(10),iUnitID(7),iMovesLeft(120),iMaxMoves(120),iSelfDamage(0),iAttacksLeft(1),eMoveStrategy(MS_FIRSTLINE),eLastAssignment(A_INITIAL),pUnit(&worldUnit){}
};
struct Reachable{int iPlotIndex,iMovesLeft;Reachable(int p=0,int m=0):iPlotIndex(p),iMovesLeft(m){}};
typedef vector<Reachable>ReachablePlots;
struct Globals{int getMOVE_DENOMINATOR()const{return 60;}}GC;
int GD_INT_GET_MOVE_DENOMINATOR=60;
#define GD_INT_GET(name) GD_INT_GET_##name
namespace TacticalAIHelpers{int GetPlotDistanceToTarget(int index,int){return abs(index-11);}}
static int DomainForUnit(const CvUnit*p){return p->getDomainType();}
struct LeavingStackProtectionMemo{};
struct BaseTacticalPosition:CvBasePosition{
 vector<CvTacticalPlot>plots;ReachablePlots reachable;vector<int>ranged;SUnitIDValueContainer damage;
 bool bTargetDistanceRelevant;CvPlot target;int endCalls;
 BaseTacticalPosition():bTargetDistanceRelevant(false),target(13),endCalls(0){}
 void initFromParent(const BaseTacticalPosition&p){assignedMoves.inheritFrom(p.assignedMoves.read());plots=p.plots;reachable=p.reachable;ranged=p.ranged;damage=p.damage;bTargetDistanceRelevant=p.bTargetDistanceRelevant;target=p.target;endCalls=0;}
 int getPlayer()const{return 0;}const CvPlot*getTarget()const{return &target;}
 const CvTacticalPlot*getTactPlot(int id)const{for(size_t i=0;i<plots.size();++i)if(plots[i].plot.index==id)return &plots[i];return NULL;}
 const ReachablePlots&getReachablePlotsForUnit(const SUnitStats&)const{return reachable;}
 const vector<int>&getRangeAttackPlotsForUnit(const SUnitStats&)const{return ranged;}
 const SUnitIDValueContainer&GetUnitDamageDealt()const{return damage;}
 bool canProbablyEndTurnAfterAssignment(const SUnitStats&u,const CvTacticalPlot*p,eUnitAssignmentType a)const{return ((scenarioSeed+p->getPlotIndex()+u.iSelfDamage+(int)a)%7)!=0;}
 void ChangeUnitDamage(int id,int change){damage.ChangeValue(id,change);}void ChangeCityDamage(int id,int change){damage.ChangeValue(-id,change);}
};
// The independently adopted enemy key-fragment holder is identical in both
// preferred bodies. Its engine/cache effects are outside this lexical history
// fixture; its constructor is a deterministic service with the same signature.
struct StackImmutableEnemyDamageScope{StackImmutableEnemyDamageScope(const SUnitIDValueContainer&){}};
'''

def scoring_services(source):
 result=[]
 for name in proof['scorers_with_default_null']:
  function=block(source,'static STacticalAssignment* '+name+'(')
  if name=='ScorePlotForMove':result.append(function);continue
  signature=function[:function.index('\n{')]
  initialize=re.search(r'result->init\([^;]+;',function).group(0)
  plot_arg='enemyPlot' if name in ('ScorePlotForRangedAttack','ScorePlotForMeleeAttack') else ('assumedUnitPlot' if name=='ScorePlotForAdmiralHeal' else 'testPlot')
  behavior=''
  if name=='ScorePlotForMeleeAttack':behavior='result->eAssignmentType=((scenarioSeed+p)%2)?A_MELEEKILL:A_MELEEATTACK;result->iRemainingMoves=iAssumedMovesLeft;result->unitDamage.ChangeValue(99,6);'
  elif name=='ScorePlotForRangedAttack':behavior='result->iRemainingMoves=(scenarioSeed%2)?0:60;result->unitDamage.ChangeValue(99,9);'
  elif name=='ScorePlotForPillageMove':behavior='result->iRemainingMoves=max(0,iAssumedMovesLeft-60);result->unitHealing.ChangeValue(unit.iUnitID,10);'
  elif name=='ScorePlotForAdmiralHeal':behavior='result->iRemainingMoves=iAssumedMovesLeft;'
  else:behavior='if(unit.iPlotIndex==p)result->eAssignmentType=A_FINISH_TEMP;'
  score='int base=((p+scenarioSeed)%5)*10;int bonus=(scenarioSeed%3)-1;int delta=assumedPosition.damage.GetValue(99)/3;'
  if name=='ScorePlotForAdmiralHeal':score='int base=0;int bonus=0;int delta=(scenarioSeed%2)?220:180;'
  result.append(signature+'\n{STacticalAssignment*result=gAssignmentStorage.peekNext();'+initialize+'int p='+plot_arg+'->getPlotIndex();'+behavior+score+'result->SetScore(base,bonus,delta);if((scenarioSeed+p)%19==0)result->SetImpossible();return result;}')
 return '\n'.join(result)

storage=r'''
struct Storage{STacticalAssignment slots[1024];int used;Storage():used(0){}void reset(){used=0;}STacticalAssignment*peekNext(){return &slots[used];}void consumeOne(){++used;}}gAssignmentStorage;
vector<OptionWithScore<STacticalAssignment*> >gPossibleMoves,gPossibleRangedAttacks;
struct CvTacticalPosition:BaseTacticalPosition{void getPreferredAssignmentsForUnit(const SUnitStats&,int)const;};
'''
parts=[prefix,values,enums,assignment,cow,option,services,latest_counted]
for label,source in [('Legacy',old),('Candidate',new)]:
 parts.append('namespace '+label+'{\n'+storage)
 parts.append(block(source,'static int GetPrevPlotScore('))
 if label=='Candidate':parts.append(helper)
 parts.append(block(source,'static void GetNextPosition('))
 parts.append(block(source,'static SUnitStats GetNextUnit('))
 parts.append(block(source,'bool IsCombatUnit('))
 parts.append(scoring_services(source))
 parts.append(block(source,'void CvTacticalPosition::getPreferredAssignmentsForUnit('))
 parts.append('}\n')
tests=r'''
int checks=0,failures=0;void check(bool ok,const char*label){++checks;if(!ok){if(failures<12)printf("FAIL %s\n",label);++failures;}}
unsigned long randomState=91761;unsigned long rnd(){randomState=randomState*1664525u+1013904223u;return randomState;}
STacticalAssignment record(int id,int score,eUnitAssignmentType type=A_INITIAL){STacticalAssignment a;a.init(2,3,id,60,MS_FIRSTLINE,type,0);a.SetScore(score,0,0);return a;}
bool same(const STacticalAssignment&a,const STacticalAssignment&b){
 if(a.eAssignmentType!=b.eAssignmentType||a.iUnitID!=b.iUnitID||a.Score()!=b.Score()||a.iFromPlotIndex!=b.iFromPlotIndex||a.iToPlotIndex!=b.iToPlotIndex||a.iRemainingMoves!=b.iRemainingMoves||a.eMoveType!=b.eMoveType||a.iSelfDamage!=b.iSelfDamage||a.GetPlotScore()!=b.GetPlotScore()||a.GetBonusScore()!=b.GetBonusScore()||a.GetDamageDelta()!=b.GetDamageDelta()||a.GetOldPlotScore()!=b.GetOldPlotScore()||a.iDamagedCityId!=b.iDamagedCityId||a.iCityDamage!=b.iCityDamage||a.iPrimaryUnitID!=b.iPrimaryUnitID||a.ePrimaryUnitOwner!=b.ePrimaryUnitOwner)return false;
 for(int i=-20;i<150;++i)if(a.unitDamage.GetValue(i)!=b.unitDamage.GetValue(i)||a.unitHealing.GetValue(i)!=b.unitHealing.GetValue(i))return false;return true;
}
void prepare(BaseTacticalPosition&p,int count){
 for(int i=0;i<count;++i)p.assignedMoves.write().push_back(record((int)(rnd()%31)-3,(int)(rnd()%140001)-70000,(eUnitAssignmentType)(rnd()%(A_RESTART+1))));
 p.plots.reserve(40);for(int i=0;i<24;++i){CvTacticalPlot plot(i);plot.enemy=(i==9||i==11||i==13||i==15);plot.city=(i==13);plot.blocking=(i==8||i==14);plot.distance=(i%4);p.plots.push_back(plot);p.reachable.push_back(Reachable(i,(i*37)%181));if(plot.enemy)p.ranged.push_back(i);}p.reachable.push_back(Reachable(999,0));p.bTargetDistanceRelevant=(scenarioSeed%3==0);
}
int main(){
 // Alias/lifetime tests use the actual copy-on-write field and accessor.
 CvBasePosition p;p.assignedMoves.write().push_back(record(0,140,A_INITIAL));p.assignedMoves.write().push_back(record(7,-400,A_BLOCKED));p.assignedMoves.write().push_back(record(7,SHRT_MAX,A_RESTART));
 latestCalls=latestRows=0;Candidate::PreviousPlotScoreQuery q(7,p);check(!q.ready,"lazy construction");check(latestCalls==0,"no eager scan");
 check(q.Get(7,p)==SHRT_MAX,"latest any assignment type");check(latestCalls==1,"one initial scan");
 CvBasePosition borrowed;borrowed.assignedMoves.inheritFrom(p.assignedMoves.read());check(q.Get(7,borrowed)==SHRT_MAX,"actual borrowed history identity");check(latestCalls==1,"borrowed preview reuses");
 CvBasePosition copied;copied.assignedMoves.write()=p.getAssignments();check(q.Get(7,copied)==SHRT_MAX,"equal but owned copy fallback");check(latestCalls==2,"copied fallback scans");
 copied.assignedMoves.write().back().SetScore(-250,0,0);check(q.Get(7,copied)==-250,"reused owned temporary fresh score");
 check(q.Get(0,p)==140,"different actor fallback");check(q.Get(-99,p)==0,"missing actor zero");
 check(Candidate::GetPrevPlotScore(7,p,NULL)==Legacy::GetPrevPlotScore(7,p),"null/default legacy accessor");
 ++gStackForecastRevision;p.assignedMoves.write().back().SetScore(99,0,0);check(q.Get(7,p)==99,"nested/yield revision fallback prevents same slot stale hit");
 Candidate::PreviousPlotScoreQuery nested(7,p);gStackForecastDepth=2;p.assignedMoves.write().back().SetScore(100,0,0);check(nested.Get(7,p)==100,"nested depth fallback");gStackForecastDepth=1;++gStackForecastRevision;
 contextAllowed=false;Candidate::PreviousPlotScoreQuery noOwner(7,p);contextAllowed=true;p.assignedMoves.write().back().SetScore(101,0,0);check(noOwner.Get(7,p)==101,"unowned construction stays fallback");
 contextAllowed=false;int readCount=sceneReads;Candidate::PreviousPlotScoreQuery foreign(7,p);foreign.Get(7,p);check(sceneReads==readCount,"foreign eligibility skips scene reads");contextAllowed=true;
 contextChangesRevision=true;Candidate::PreviousPlotScoreQuery refreshed(7,p);check(refreshed.Get(7,p)==101,"constructor captures refreshed revision");check(refreshed.ready,"refreshed context eligible");
 CvBasePosition epochPosition;epochPosition.assignedMoves.write().push_back(record(7,201,A_FINISH));Candidate::PreviousPlotScoreQuery epochMemo(7,epochPosition);check(epochMemo.Get(7,epochPosition)==201,"epoch memo starts ready");
 unsigned long revisionBefore=gStackForecastRevision;int contextBefore=contextCalls;++CvStackingStrengthCache::liveScene;epochPosition.assignedMoves.write().back().SetScore(202,0,0);
 check(epochMemo.Get(7,epochPosition)==202,"fresh scene drift rejects same-slot cache before revision updates");check(gStackForecastRevision==revisionBefore&&contextCalls==contextBefore,"fresh scene guard does not clear/mutate forecast context");
 CvBasePosition empty;Candidate::PreviousPlotScoreQuery absent(0,empty);int scans=latestCalls;for(int i=0;i<200;++i)check(absent.Get(0,empty)==0,"empty missing score cached");check(latestCalls==scans+1,"no-match zero only scans once");
 Candidate::PreviousPlotScoreQuery noAlloc(7,p);noAlloc.Get(7,p);size_t before=allocations;for(int i=0;i<1000;++i)check(noAlloc.Get(7,borrowed)==101,"warm borrowed read");check(allocations==before,"warm query no heap allocation");
 int totalOldCalls=0,totalNewCalls=0,totalOldRows=0,totalNewRows=0;
 for(int s=0;s<2000;++s){
  scenarioSeed=s;noUnit=(s%51==0);worldUnit.ranged=s%4==0;worldUnit.admiral=s%7==0;worldUnit.freeMoves=s%3==0;worldUnit.afterAttack=s%2==0;worldUnit.ai=s%2;worldUnit.domain=s%2;CvStacking::enabled=s%2==0;
  Legacy::CvTacticalPosition a;prepare(a,(s%4==0)?700:(s%70));Candidate::CvTacticalPosition b;b.initFromParent(a);SUnitStats u;u.iUnitID=s%31-3;u.iMovesLeft=(s%5)*60;u.iSelfDamage=s%50;u.iAttacksLeft=s%3;u.eMoveStrategy=(s%9==0)?MS_EMBARKED:MS_FIRSTLINE;u.eLastAssignment=(s%6==0)?A_MOVE:((s%6==1)?A_MOVE_SWAP:A_INITIAL);int cap=s%9+1;
  latestCalls=latestRows=0;Legacy::gAssignmentStorage.reset();a.getPreferredAssignmentsForUnit(u,cap);int legacyCalls=latestCalls,legacyRows=latestRows;
  latestCalls=latestRows=0;Candidate::gAssignmentStorage.reset();b.getPreferredAssignmentsForUnit(u,cap);
  check(Candidate::gAssignmentStorage.used==Legacy::gAssignmentStorage.used,"consumed storage count exact");check(Candidate::gPossibleMoves.size()==Legacy::gPossibleMoves.size(),"preferred candidate count exact");check(latestCalls<=(noUnit?0:1),"one history scan per pure preferred call");
  for(size_t i=0;i<Legacy::gPossibleMoves.size()&&i<Candidate::gPossibleMoves.size();++i){check(Legacy::gPossibleMoves[i].score==Candidate::gPossibleMoves[i].score,"stable score/order exact");check(same(*Legacy::gPossibleMoves[i].option,*Candidate::gPossibleMoves[i].option),"complete assignment payload exact");}
  for(int i=0;i<Legacy::gAssignmentStorage.used;++i)check(same(Legacy::gAssignmentStorage.slots[i],Candidate::gAssignmentStorage.slots[i]),"all consumed candidates exact");
  totalOldCalls+=legacyCalls;totalNewCalls+=latestCalls;totalOldRows+=legacyRows;totalNewRows+=latestRows;
  check(legacyCalls>=latestCalls,"does not add history scans");
 }
 printf("preferred workcount: old accessor calls%d rows%d; candidate calls%d rows%d; native gain unmeasured\n",totalOldCalls,totalOldRows,totalNewCalls,totalNewRows);
 printf("actual previous plot-score differential: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
fixture='\n'.join(parts)+'\n'+tests
(OUT/'test.cpp').write_text(fixture,encoding='utf-8')
scope='Actual complete old/new preferred body and move dispatcher; actual accessor, copy-on-write/value/assignment methods and six initializer statements. Remaining scorer/engine services are deterministic stubs, not full combat scorers. No production application/native timing claim.'
if args.prepare_only:
 (OUT/'scaffold.json').write_text(json.dumps(dict(prepared=True,compiled=False,control=CONTROL,production_applied=args.production,actual_source_sha256=hashlib.sha256(new.encode()).hexdigest(),fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),scope=scope),indent=2)+'\n',encoding='utf-8');print('Prepared actual-source previous-score scaffold; no compilation.');raise SystemExit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=OUT/'test.exe';compile=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(OUT/'test.cpp'),'/Fo'+str(OUT/'test.obj'),'/Fe'+str(exe)],cwd=OUT,env=env,capture_output=True,text=True,timeout=60)
(OUT/'compile.log').write_text(compile.stdout+compile.stderr,encoding='utf-8')
if compile.returncode:print(compile.stdout+compile.stderr);raise SystemExit(compile.returncode)
run=subprocess.run([str(exe)],cwd=OUT,capture_output=True,text=True,timeout=40);print(run.stdout+run.stderr,end='')
(OUT/'result.json').write_text(json.dumps(dict(control=CONTROL,production_applied=args.production,actual_source_sha256=hashlib.sha256(new.encode()).hexdigest(),compiled=True,returncode=run.returncode,output=run.stdout+run.stderr,fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),scope=scope),indent=2)+'\n',encoding='utf-8');raise SystemExit(run.returncode)
