"""Compare the actual local source-protection memo with DLL45's scoring body.

Only deterministic engine services come from the existing virtual-stack fixture;
no other test is executed. The helper, cache, source-stack builder, movement
guard, dispatch wrapper and ordinary sibling call statements are real source.
"""
from pathlib import Path
import ast, hashlib, json, os, subprocess, sys

root = Path(__file__).resolve().parents[1]
core = root / 'CvGameCoreDLL_Expansion2'
out = root / 'work/leaving-stack-protection-regression'
out.mkdir(exist_ok=True)
text = (core / 'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
old = subprocess.check_output(['git', 'show', 'e831746c6:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'], cwd=root).decode('utf-8-sig')

def function(source, signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

def scoring_guard(source):
    scorer = function(source, 'static STacticalAssignment* ScorePlotForCombatUnitMove(')
    start = scorer.rindex('if (StackPreferencesEnabled())')
    return function(scorer[start:], 'if (StackPreferencesEnabled())')

scaffold = {}
for node in ast.parse((root / 'work/test-virtual-stack-scratch.py').read_text()).body:
    if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
        for target in node.targets:
            if isinstance(target, ast.Name):
                scaffold[target.id] = node.value.value
prefix, engine = scaffold['prefix'], scaffold['engine']
engine = engine.replace('struct SUnitStats{int iSelfDamage;SUnitStats(int d=0):iSelfDamage(d){}};',
    'struct SUnitStats{int iSelfDamage,iPlotIndex,iMovesLeft;const CvUnit*pUnit;SUnitStats(int d=0):iSelfDamage(d),iPlotIndex(1),iMovesLeft(120),pUnit(NULL){}};')
engine = engine.replace('max(0,leafValue-(int)members.size()*11+friendly.GetValue(unit->GetID())-enemy.GetValue(-1)/5)',
    'SourceDanger(unit,members,friendly,enemy,leafValue)')
unit_header = (core / 'CvUnit.h').read_text(encoding='utf-8-sig')
container = unit_header[unit_header.index('struct SUnitIDValueContainer\n'):unit_header.index('\nnamespace std {', unit_header.index('struct SUnitIDValueContainer\n'))]
cache = text[text.index('struct StackForecastKey\n'):text.index('static int GetCachedStackDanger(')]
builder = function(text, 'static void GetVirtualFriendlyStack(').replace('{\n', '{\n ++stackBuilds;\n', 1)
danger = function(text, 'static int GetCachedStackDanger(').replace('{\n', '{\n ++dangerQueries;\n', 1)
memo = function(text, 'static int CalculateLeavingStackProtectionScore(') + '\n' + function(text, 'struct LeavingStackProtectionMemo') + ';\n'
dispatch = function(text, 'static STacticalAssignment* ScorePlotForMove(')
preferred = function(text, 'void CvTacticalPosition::getPreferredAssignmentsForUnit(')
assert preferred.count('LeavingStackProtectionMemo leavingProtection;') == 1
assert preferred.count('&leavingProtection') == 1
chunk_start = preferred.index('SUnitStats tempUnit = unit;', preferred.index('else //moving to a different plot'))
chunk_end = preferred.index('\n', preferred.index('STacticalAssignment* moveToPlot = ', chunk_start))
ordinary_call = preferred[chunk_start:chunk_end]
assert '*this, EM_INTERMEDIATE, &leavingProtection' in ordinary_call

services = r'''
static unsigned int stackBuilds=0,dangerQueries=0;
struct Globals{struct Map{CvPlot plot;Map():plot(1){}const CvPlot*plotByIndexUnchecked(int){return &plot;}}map;Map&getMap(){return map;}}GC;
static int ScoreStackPosition(const CvUnit*,const CvPlot*,int,const CvTacticalPosition&){return 0;}
'''
leaf = r'''
static int SourceDanger(const CvUnit*unit,const vector<const CvUnit*>&members,const SUnitIDValueContainer&friendly,const SUnitIDValueContainer&enemy,int base){
 int shield=0;for(size_t i=0;i<members.size();++i)if(!members[i]->IsCanAttackRanged())shield+=max(0,members[i]->GetCurrHitPoints()-friendly.GetValue(members[i]->GetID()))/4;
 return max(0,base-(int)members.size()*3-shield+friendly.GetValue(unit->GetID())-enemy.GetValue(-1)/5);
}
'''
guards = '\nstatic int OriginalScore(const SUnitStats&unit,const CvPlot*pTestPlot,const CvTacticalPosition&assumedPosition,bool bMoving,int initialBonus=0){const CvUnit*pUnit=unit.pUnit;int iDangerScore=0,iSelfDamage=0,iBonusScore=initialBonus;\n' + scoring_guard(old) + '\nreturn iBonusScore;}\n'
guards += '\nstatic int CurrentScore(const SUnitStats&unit,const CvPlot*pTestPlot,const CvTacticalPosition&assumedPosition,bool bMoving,LeavingStackProtectionMemo*leavingProtection,int initialBonus=0){const CvUnit*pUnit=unit.pUnit;int iDangerScore=0,iSelfDamage=0,iBonusScore=initialBonus;\n' + scoring_guard(text) + '\nreturn iBonusScore;}\n'
integration = r'''
enum eUnitMoveEvalMode{EM_INTERMEDIATE,EM_FINAL};
struct STacticalAssignment{int value;};
static STacticalAssignment assignment;
static bool IsCombatUnit(const SUnitStats&){return true;}
static STacticalAssignment*ScorePlotForCombatUnitMove(const SUnitStats&unit,const CvTacticalPlot*,const CvTacticalPosition&position,eUnitMoveEvalMode,LeavingStackProtectionMemo*leavingProtection){assignment.value=CurrentScore(unit,&GC.map.plot,position,true,leavingProtection);return &assignment;}
static STacticalAssignment*ScorePlotForNonFightingUnitMove(const SUnitStats&,const CvTacticalPlot*,const CvTacticalPosition&,eUnitMoveEvalMode){assignment.value=0;return &assignment;}
'''
integration += dispatch
integration += '\nstruct Enumerate: CvTacticalPosition{\nint Siblings(const SUnitStats&unit,int count){\nLeavingStackProtectionMemo leavingProtection;\nint sum=0;for(int i=0;i<count;++i){struct Reachable{int iMovesLeft;}reachable={i%121};Reachable*it=&reachable;const CvTacticalPlot*testPlot=&tactical;\n' + ordinary_call + '\nsum+=moveToPlot->value;}return sum;}\n};\n'
tests = r'''
static int checks=0,failures=0;
static void expect(const char*name,bool ok){++checks;if(!ok){++failures;if(failures<25)printf("FAIL %s\n",name);}}
static unsigned int rng=71577;static unsigned int next(){rng=rng*1664525u+1013904223u;return rng;}
static void invalidateCallback(){player.danger.leafCallback=NULL;CvStackingStrengthCache::Invalidate();}
static void nestedCallback(){player.danger.leafCallback=NULL;StackForecastScope nested;}
struct ForeignInput{SUnitStats unit;const CvTacticalPosition*position;};
static DWORD WINAPI foreignMemo(void*data){ForeignInput*p=(ForeignInput*)data;StackForecastScope scope;LeavingStackProtectionMemo memo;unsigned int start=stackBuilds;int first=memo.Get(p->unit,*p->position);int second=memo.Get(p->unit,*p->position);return !scope.owned&&!memo.ready&&first==second&&stackBuilds==start+2?0:1;}
static void setup(CvUnit*pool,Enumerate&position,SUnitStats&unit){
 player.units.clear();player.danger.fixed=false;player.danger.dynamicLeaf=true;player.danger.leafCallback=NULL;CvStacking::enabled=true;
 position.present=true;position.tactical.fixed.clear();position.tactical.moving.clear();position.stats.clear();position.enemyDamage.clear();
 for(int i=0;i<6;++i){pool[i]=CvUnit(i+1);pool[i].ranged=i>0;player.units[i+1]=&pool[i];}
 position.tactical.fixed.push_back(&pool[1]);position.tactical.fixed.push_back(&pool[2]);position.tactical.moving.push_back(STacticalUnit(1));position.stats[1]=SUnitStats(0);
 unit=SUnitStats();unit.pUnit=&pool[0];unit.iPlotIndex=1;
}
int main(){
 expect("production32bit",sizeof(void*)==4&&sizeof(size_t)==4);
 CvUnit pool[6];Enumerate position;SUnitStats unit;
 {StackForecastScope scope;setup(pool,position,unit);
  for(int trial=0;trial<12000;++trial){
   Enumerate state;state.present=trial%11!=0;unit.pUnit=&pool[trial%6];unit.iSelfDamage=(int)(next()%180)-40;
   for(int j=0;j<6;++j){pool[j].ranged=next()%3!=0;pool[j].domain=(int)(next()%3);pool[j].cargo=next()%7==0;pool[j].combat=next()%5!=0;pool[j].hp=(int)(next()%101);pool[j].maxHP=50+(int)(next()%151);if(next()%4)state.stats[j+1]=SUnitStats((int)(next()%180)-40);}
   for(int j=0,n=(int)(next()%10);j<n;++j)state.tactical.fixed.push_back(&pool[next()%6]);
   for(int j=0,n=(int)(next()%10);j<n;++j)state.tactical.moving.push_back(STacticalUnit((int)(next()%10)));
   state.enemyDamage.SetValue(-1,(int)(next()%300)-30);state.enemyDamage.SetValue(17,(int)(next()%200));
   player.danger.dynamicLeaf=trial%17!=0;player.danger.leafValue=trial%17==0?INT_MAX:40+(int)(next()%160);CvStackingStrengthCache::Invalidate();LeavingStackProtectionMemo memo;
   int bonus=(int)(next()%301)-150;int expected=OriginalScore(unit,&GC.map.plot,state,true,bonus);
   expect("exact original score across order duplicates unit/source/enemy wounds andsentinel",CurrentScore(unit,&GC.map.plot,state,true,&memo,bonus)==expected);
   unsigned int builds=stackBuilds,queries=dangerQueries;expect("same immutable state/movement siblings exact",CurrentScore(unit,&GC.map.plot,state,true,&memo,bonus)==expected);
   expect("repeat eliminates all source builds/forecast queries",stackBuilds==builds&&dangerQueries==queries);
  }
 }
 {StackForecastScope scope;setup(pool,position,unit);player.danger.leafValue=130;int expected=OriginalScore(unit,&GC.map.plot,position,true);unsigned int builds=stackBuilds,queries=dangerQueries;
  expect("actual ordinarycall statements preserve all sibling scores",position.Siblings(unit,20000)==expected*20000);
  expect("20000siblings perform one source rebuild",stackBuilds==builds+1);
  expect("20000siblings perform four forecasts total",dangerQueries==queries+4);
  printf("source memo repeated destinations: %u rebuilds, %u forecast queries vs DLL45 20000/80000; no game timing claim\n",stackBuilds-builds,dangerQueries-queries);
  LeavingStackProtectionMemo memo;int healthy=memo.Get(unit,position);builds=stackBuilds;unit.iSelfDamage=41;int wounded=memo.Get(unit,position);expect("protector wound change rejects reuse with distinct score",wounded==CalculateLeavingStackProtectionScore(unit,position)&&wounded!=healthy&&stackBuilds==builds+2);
  builds=stackBuilds;unit.iPlotIndex=2;memo.Get(unit,position);expect("source plot change rejects reuse",stackBuilds==builds+1);
  Enumerate different=position;builds=stackBuilds;memo.Get(unit,different);expect("different hypothetical position rejects reuse",stackBuilds==builds+1);
  different.enemyDamage.SetValue(-1,25);CvStackingStrengthCache::Invalidate();builds=stackBuilds;int expectedChanged=CalculateLeavingStackProtectionScore(unit,different);expect("enemy HP plus scene change recomputes exact score",memo.Get(unit,different)==expectedChanged&&stackBuilds==builds+2);
  different.stats[2]=SUnitStats(99);CvStackingStrengthCache::Invalidate();builds=stackBuilds;expectedChanged=CalculateLeavingStackProtectionScore(unit,different);expect("source companion wounds plus scene change recompute",memo.Get(unit,different)==expectedChanged&&stackBuilds==builds+2);
  builds=stackBuilds;CvStacking::enabled=false;expect("disabled preferences retain original zero scoring",CurrentScore(unit,&GC.map.plot,position,true,&memo)==OriginalScore(unit,&GC.map.plot,position,true)&&stackBuilds==builds);CvStacking::enabled=true;
  builds=stackBuilds;expect("staying never evaluates leaving protection",CurrentScore(unit,&GC.map.plot,position,false,&memo)==0&&stackBuilds==builds);
  pool[0].ranged=true;builds=stackBuilds;expect("ranged actor never evaluates leaving protection",CurrentScore(unit,&GC.map.plot,position,true,&memo)==0&&stackBuilds==builds);pool[0].ranged=false;
 }
 {setup(pool,position,unit);LeavingStackProtectionMemo memo;unsigned int builds=stackBuilds,queries=dangerQueries;int a=memo.Get(unit,position),b=memo.Get(unit,position);expect("inactive context computes independently",a==b&&!memo.ready&&stackBuilds==builds+2&&dangerQueries==queries+8);}
 {StackForecastScope outer;setup(pool,position,unit);LeavingStackProtectionMemo memo;memo.Get(unit,position);unsigned int builds=stackBuilds;
  {StackForecastScope nested;memo.Get(unit,position);memo.Get(unit,position);expect("nested context bypasses memo",!memo.ready&&stackBuilds==builds+2);}
  builds=stackBuilds;memo.Get(unit,position);memo.Get(unit,position);expect("outer resumes after invalidation with freshmemo",memo.ready&&stackBuilds==builds+1);
  CvStackingStrengthCache::Invalidate();player.danger.leafCallback=nestedCallback;builds=stackBuilds;memo.Get(unit,position);expect("nested leaf callback cancels admission",!memo.ready&&stackBuilds==builds+1);memo.Get(unit,position);expect("subsequent stable result admitted",memo.ready);
  CvStackingStrengthCache::Invalidate();player.danger.leafCallback=invalidateCallback;memo.Get(unit,position);expect("scene mutation during leaf cancels admission",!memo.ready);memo.Get(unit,position);expect("stable result admitted after scene mutation",memo.ready);
  ForeignInput input;input.unit=unit;input.position=&position;HANDLE thread=CreateThread(NULL,0,foreignMemo,&input,0,NULL);DWORD result=99;expect("foreign callback thread created",thread!=NULL);if(thread){WaitForSingleObject(thread,INFINITE);GetExitCodeThread(thread,&result);CloseHandle(thread);}expect("foreign context never shares memo/scratch",result==0);
 }
 printf("leaving source protection actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
base = prefix + container + leaf + engine + services + cache + builder + danger + memo + guards + integration
vc = root / 'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
sdk = root / 'work/toolchain/sdk/windows'
env = os.environ.copy()
env['PATH'] = str(vc / 'Vc7/bin') + ';' + str(vc / 'Common7/IDE') + ';' + env.get('PATH', '')
env['INCLUDE'] = str(root / 'work/toolchain/sdk/vc9/include') + ';' + str(sdk / 'Include')
env['LIB'] = str(root / 'work/toolchain/sdk/vc9/lib') + ';' + str(sdk / 'Lib')
for key in ('CL', '_CL_', 'LINK'):
    env.pop(key, None)

def run(label, source):
    cpp = out / (label + '.cpp')
    cpp.write_text(source, encoding='utf-8')
    exe = out / (label + '.exe')
    compile = subprocess.run([str(vc / 'Vc7/bin/cl.exe'), '/nologo', '/EHsc', '/MT', '/O2', '/Z7', str(cpp), '/Fo' + str(out / (label + '.obj')), '/Fe' + str(exe)], cwd=out, env=env, capture_output=True, text=True, timeout=60)
    (out / (label + '-compile.log')).write_text(compile.stdout + compile.stderr, encoding='utf-8')
    if compile.returncode:
        print(compile.stdout + compile.stderr)
        raise SystemExit(compile.returncode)
    result = subprocess.run([str(exe)], cwd=out, capture_output=True, text=True, timeout=30)
    (out / (label + '-output.log')).write_text(result.stdout + result.stderr, encoding='utf-8')
    return result

fixture = base + tests
current = run('current', fixture)
print(current.stdout + current.stderr, end='')
control_fixture = fixture.replace(scoring_guard(text), scoring_guard(old))
control = run('original-scorer-control', control_fixture)
print('DLL45 scorer control rejected expected work-count assertions' if control.returncode == 1 else 'FAIL original scorer did not fail work-count assertions')
result = current.returncode or (0 if control.returncode == 1 else 1)
(out / 'result.json').write_text(json.dumps(dict(returncode=result, fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(), output=current.stdout + current.stderr, control_commit='e831746c6', control_returncode=control.returncode, control_output=control.stdout + control.stderr, scope='Actual helper/memo/fullforecastcontext and cache/virtualstack builder/scoring preference guard/dispatch/ordinary sibling statements. Engine services are deterministic stubs; full getPreferredAssignmentsForUnit and other scoring contributions are not compiled. No DLLbuild or game run.'), indent=2), encoding='utf-8')
sys.exit(result)
