"""Native source regression for the observed embarked same-plot move loop."""
from pathlib import Path
import os,subprocess,sys,json,hashlib
root=Path(__file__).resolve().parents[1];out=root/'work/ai-noop-regression';out.mkdir(exist_ok=True)
raw=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_bytes();s=raw.decode('utf-8-sig').replace('\r\n','\n')
def body(start):
 a=s.index(start);i=s.index('{',a)+1;depth=1
 while depth:depth+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[a:i]
actual=body('static STacticalAssignment* ScorePlotForNonFightingUnitMove(')
fix_start=actual.index('\n\t// Staying put is a terminal choice')
fix_end=actual.index('\n\tint iScore = 0;',fix_start)
legacy=(actual[:fix_start]+actual[fix_end:]).replace('ScorePlotForNonFightingUnitMove','LegacyScore')
a=s.index('\t// A movement assignment must change plots.',s.index('CvTacticalPosition::AddAssignmentResult CvTacticalPosition::addAssignment('))
b=s.index('\n\t//if we killed an enemy ZOC will change',a)
assert a < s.index('availableUnits.write()', a) < s.index('assignedMoves.write().push_back(newAssignment)', a)
guard='static bool Allows(const STacticalAssignment& newAssignment){\n'+s[a:b]+'\nreturn true;}\n'
case_start=s.index('\tcase A_FINISH:\n',s.index('CvTacticalPosition::AddAssignmentResult CvTacticalPosition::addAssignment('))
case_end=s.index('\tcase A_BLOCKED:',case_start)
finish='static bool Ends(const STacticalAssignment&a){bool bEndOfSim=false;switch(a.eAssignmentType){'+s[case_start:case_end]+'default:break;}return bEndOfSim;}\n'
prefix=r'''
#include <vector>
#include <algorithm>
#include <cstdio>
using namespace std;
enum eUnitAssignmentType{A_INITIAL,A_MOVE,A_MOVE_FORCED,A_MOVE_DOUBLE,A_MOVE_SWAP,A_MOVE_SWAP_REVERSE,A_FINISH_TEMP,A_FINISH,A_BLOCKED,A_HEAL,A_USE_POWER,A_RANGEATTACK,A_MELEEATTACK,A_PILLAGE,A_CAPTURE,A_WAIT};
enum eUnitMoveEvalMode{EM_INITIAL,EM_INTERMEDIATE,EM_FINAL};enum{MS_EMBARKED=5,MS_SUPPORT=4,RESULT_NOT_ADDED=0,MOVE_DENOMINATOR=60};
#define GD_INT_GET(x) (x)
#define OutputDebugString(x) ((void)0)
struct CvPlot{int id;CvPlot(int n=2040):id(n){}int GetPlotIndex()const{return id;}};
static int plotDistance(const CvPlot&a,const CvPlot&b){return a.id==b.id?0:2;}
struct SUnitIDValueContainer{};
struct CvUnit{int danger;CvUnit():danger(0){}int GetDanger(const CvPlot*,const SUnitIDValueContainer&,int)const{return danger;}};
struct SUnitStats{int iPlotIndex,iUnitID,iMovesLeft,eMoveStrategy;eUnitAssignmentType eLastAssignment;CvUnit*pUnit;SUnitStats(CvUnit*p):iPlotIndex(2040),iUnitID(7508),iMovesLeft(120),eMoveStrategy(MS_EMBARKED),eLastAssignment(A_INITIAL),pUnit(p){}};
struct CvTacticalPlot{CvPlot p;bool enemy,edge;int distance;CvTacticalPlot(int n=2040):p(n),enemy(false),edge(false),distance(4){}int getPlotIndex()const{return p.id;}const CvPlot*getPlot()const{return &p;}bool isEnemy()const{return enemy;}bool isEdgePlot()const{return edge;}int getEnemyDistance()const{return distance;}};
struct CvTacticalPosition{CvTacticalPlot target;SUnitIDValueContainer damage;CvTacticalPosition():target(10320){}const CvTacticalPlot*getTactPlot(int)const{return &target;}const CvPlot*getTarget()const{return target.getPlot();}const SUnitIDValueContainer&GetUnitDamageDealt()const{return damage;}};
struct STacticalAssignment{int iFromPlotIndex,iToPlotIndex,iUnitID,iRemainingMoves,score;eUnitAssignmentType eAssignmentType;
 void init(int a,int b,int id,int moves,int,eUnitAssignmentType type,int){iFromPlotIndex=a;iToPlotIndex=b;iUnitID=id;iRemainingMoves=moves;eAssignmentType=type;score=-1000;}
 void SetScore(int a,int b,int c){score=a+(b+c)*10;}bool IsAcceptable()const{return score>-1000;}};
struct Storage{STacticalAssignment a;STacticalAssignment*peekNext(){return &a;}}gAssignmentStorage;
static int GetPrevPlotScore(int,const CvTacticalPosition&){return 0;}
'''
suffix=r'''
static int checks=0,failures=0;static void check(const char*n,bool b){++checks;if(!b){++failures;printf("FAIL %s\n",n);}}
int main(){CvUnit u;SUnitStats state(&u);CvTacticalPlot current,next(2041);CvTacticalPosition p;
 STacticalAssignment old=*LegacyScore(state,&current,p,EM_INTERMEDIATE);
 check("unpatched observed shape",old.eAssignmentType==A_MOVE&&old.iFromPlotIndex==2040&&old.iToPlotIndex==2040&&old.iRemainingMoves==120&&old.IsAcceptable());
 int oldHistory=0;for(int i=0;i<3072;++i){old=*LegacyScore(state,&current,p,EM_INTERMEDIATE);if(Ends(old))break;++oldHistory;state.iPlotIndex=old.iToPlotIndex;state.iMovesLeft=old.iRemainingMoves;state.eLastAssignment=old.eAssignmentType;}
 check("unpatched scorer repeats3072 unchanged moves",oldHistory==3072&&state.iMovesLeft==120&&state.iPlotIndex==2040);
 STacticalAssignment fixed=*ScorePlotForNonFightingUnitMove(state,&current,p,EM_INTERMEDIATE);
 check("stationary becomes terminal finish",fixed.eAssignmentType==A_FINISH_TEMP&&Ends(fixed));
 check("finish preserves unit movement",fixed.iRemainingMoves==120&&fixed.iFromPlotIndex==fixed.iToPlotIndex);
 check("real move remains available",ScorePlotForNonFightingUnitMove(state,&next,p,EM_INTERMEDIATE)->eAssignmentType==A_MOVE);
 check("initial scoring type",ScorePlotForNonFightingUnitMove(state,&current,p,EM_INITIAL)->eAssignmentType==A_INITIAL);
 check("final scoring type",ScorePlotForNonFightingUnitMove(state,&current,p,EM_FINAL)->eAssignmentType==A_FINISH);
 state.eLastAssignment=A_USE_POWER;check("after power final semantics",ScorePlotForNonFightingUnitMove(state,&current,p,EM_FINAL)->eAssignmentType==A_FINISH);
 for(int moves=0;moves<=240;moves+=60){state.iMovesLeft=moves;STacticalAssignment a=*ScorePlotForNonFightingUnitMove(state,&current,p,EM_INTERMEDIATE);check("every remaining-move value retires stationary option",Ends(a)&&a.iRemainingMoves==moves);}
 state.eMoveStrategy=MS_SUPPORT;check("non-embarked nonfighter stay also terminates",Ends(*ScorePlotForNonFightingUnitMove(state,&current,p,EM_INTERMEDIATE)));
 eUnitAssignmentType motion[]={A_MOVE,A_MOVE_FORCED,A_MOVE_DOUBLE,A_MOVE_SWAP,A_MOVE_SWAP_REVERSE};
 for(int i=0;i<5;++i){STacticalAssignment a;a.init(2040,2040,7508,120,MS_EMBARKED,motion[i],0);check("invariant rejects same-plot movement",!Allows(a));a.iToPlotIndex=2041;check("invariant allows actual displacement",Allows(a));}
 eUnitAssignmentType stationary[]={A_INITIAL,A_FINISH_TEMP,A_FINISH,A_HEAL,A_RANGEATTACK,A_MELEEATTACK,A_PILLAGE,A_USE_POWER,A_BLOCKED,A_WAIT,A_CAPTURE};
 for(int i=0;i<11;++i){STacticalAssignment a;a.init(2040,2040,7508,120,MS_EMBARKED,stationary[i],0);check("invariant preserves nonmovement actions",Allows(a));}
 check("new invariant catches old producer bug",!Allows(old));
 int unchangedHistory=0,unchangedMoves=120;if(Allows(old)){++unchangedHistory;unchangedMoves=old.iRemainingMoves;}
 check("rejected no-op leaves state and history untouched",unchangedHistory==0&&unchangedMoves==120);
 current.enemy=true;check("enemy plot still rejected",!ScorePlotForNonFightingUnitMove(state,&current,p,EM_INTERMEDIATE)->IsAcceptable());current.enemy=false;
 int history=0;state.iMovesLeft=120;state.eMoveStrategy=MS_EMBARKED;for(int i=0;i<3072;++i){STacticalAssignment a=*ScorePlotForNonFightingUnitMove(state,&current,p,EM_INTERMEDIATE);if(!Allows(a))break;++history;if(Ends(a))break;state.iPlotIndex=a.iToPlotIndex;state.iMovesLeft=a.iRemainingMoves;}
 check("fixed stationary branch needs one assignment",history==1);
 printf("no-op source regression: %d checks, %d failures; legacy same-tile history=%d fixed=%d\n",checks,failures,oldHistory,history);return failures?1:0;}
'''
cpp=out/'noop-source-test.cpp';cpp.write_text(prefix+actual+'\n'+legacy+'\n'+guard+finish+suffix,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows';env=os.environ.copy()
env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
exe=out/'noop-source-test.exe';c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2',str(cpp),'/Fo'+str(out/'noop.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=30);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps({'source_sha256':hashlib.sha256(raw).hexdigest().upper(),'returncode':r.returncode,'output':r.stdout+r.stderr,'scope':'Actual nonfighting scorer, admission guard and finish cases extracted; controlled engine stubs. In-memory pre-fix negative control, no game/DLL test.'},indent=2),encoding='utf-8');sys.exit(r.returncode)
