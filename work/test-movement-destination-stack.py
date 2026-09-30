"""Compare actual destination-query source with DLL47 danger/stack scores offline.

VC9/x86 engine substitutes exercise temporary membership and invalidation; this
is a score/build-count regression, not a native game performance claim.
"""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
out = root / 'work/movement-destination-regression'
out.mkdir(exist_ok=True)
source = root / 'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
raw = source.read_bytes()
text = raw.decode('utf-8-sig').replace('\r\n', '\n')
control_commit = '3b008c0d4'
control = subprocess.check_output(['git', 'show', control_commit + ':CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'], cwd=root).decode('utf-8-sig').replace('\r\n', '\n')

# Reuse established engine/allocation substitutes, without executing that
# fixture's compilation/test/artifact writes. The production ranges are read
# afresh there, so this compiles the current real query/cache/builders.
base_source = (root / 'work/test-virtual-stack-scratch.py').read_text(encoding='utf-8')
base = {'__file__': str(root / 'work/test-virtual-stack-scratch.py')}
exec(compile(base_source[:base_source.index("suffix=r'''")], 'virtual-stack-fixture-definitions', 'exec'), base)

def section(value, start, end):
    begin = value.index(start)
    return value[begin:value.index(end, begin)]

original_danger = section(control, 'static int GetUnitDangerForPlot(', 'static unsigned char GetStackAttackThreatFlags(').replace('GetUnitDangerForPlot', 'DLL47UnitDanger')
original_score = section(control, 'static int ScoreStackPosition(', '// what is the rough state looking like after this assignment').replace('ScoreStackPosition', 'DLL47StackScore')
movement = section(text, 'static STacticalAssignment* ScorePlotForCombatUnitMove(', '//stacking with combat units is allowed here!')
original_movement = section(control, 'static STacticalAssignment* ScorePlotForCombatUnitMove(', '//stacking with combat units is allowed here!')
restored_movement = movement.replace('\tMovementDestinationStackQuery destinationStack;\n', '').replace(', &destinationStack)', ')').replace('  destinationStack.Release();\n', '')
assert restored_movement == original_movement, 'Movement body must match DLL47 apart from query plumbing'
assert movement.index('destinationStack.Release();') < movement.index('leavingProtection->Get('), 'Release destination before source-protection query'

builder = base['builder'].replace('{\n const CvTacticalPlot* tactical = position.getTactPlot(plot->GetPlotIndex());', '{\n ++virtualBuilds;\n const CvTacticalPlot* tactical = position.getTactPlot(plot->GetPlotIndex());', 1)
engine = base['engine'].replace('static unsigned int statsReads=0;', 'static unsigned int statsReads=0;static void(*statsCallback)()=NULL;').replace('const{++statsReads;map<int,SUnitStats>', 'const{++statsReads;if(statsCallback)statsCallback();map<int,SUnitStats>')

tests = r'''
static int checks=0,failures=0;
static void expect(const char*name,bool ok){++checks;if(!ok){++failures;if(failures<30)printf("FAIL %s\n",name);}}
static unsigned int seed=19829;
static unsigned int next(){seed=seed*1664525u+1013904223u;return seed;}
static void invalidateCallback(){CvStackingStrengthCache::Invalidate();}
static void nestedCallback(){player.danger.leafCallback=NULL;StackForecastScope nested;}
static DWORD WINAPI foreignQuery(void* context){
 const CvTacticalPosition*position=(const CvTacticalPosition*)context;CvPlot plot(1);StackForecastScope scope;
 MovementDestinationStackQuery query;size_t before=virtualBuilds;
 query.Get(*position,&plot,player.units[1],17);query.Get(*position,&plot,player.units[1],17);
 return !scope.owned&&!query.borrowed&&query.buffer!=&gStackDestinationScratch&&virtualBuilds==before+2?0:1;
}
int main(){
 expect("production x86",sizeof(void*)==4&&sizeof(size_t)==4);
 CvUnit pool[12];for(int i=0;i<12;++i){pool[i].id=i+1;player.units[i+1]=&pool[i];}
 CvUnit attackers[5];for(int i=0;i<5;++i){attackers[i].id=50+i;player.attackers.push_back(&attackers[i]);}
 CvPlot plot(1),otherPlot(2);
 {StackForecastScope scope;player.danger.dynamicLeaf=true;
  for(int trial=0;trial<24000;++trial){
   CvStackingStrengthCache::Invalidate();CvStacking::enabled=trial%17!=0;CvStacking::collateralPercent=trial%9==0?0:20;
   player.danger.fixed=trial%11==0;player.danger.fixedValue=trial%3==0?INT_MAX:trial%83;
   for(int i=0;i<5;++i){attackers[i].flank=next()%3==0;attackers[i].collateral=next()%4;attackers[i].dead=next()%7==0;attackers[i].delayed=next()%11==0;}
   CvTacticalPosition position;position.present=trial%13!=0;position.enemyDamage.SetValue(-1,(int)(next()%200));
   for(int i=0;i<8;++i){pool[i].domain=(int)(next()%3);pool[i].hp=(int)(next()%101);pool[i].maxHP=100+(int)(next()%50);pool[i].combat=next()%7!=0;pool[i].cargo=next()%7==0;pool[i].ranged=next()%2!=0;pool[i].anti=next()%3==0;if(next()%5)position.stats[i+1]=SUnitStats((int)(next()%180)-40);}
   unsigned int n=next()%8;for(unsigned int i=0;i<n;++i)position.tactical.fixed.push_back(&pool[next()%8]);
   n=next()%10;for(unsigned int i=0;i<n;++i)position.tactical.moving.push_back(STacticalUnit((int)(next()%12)+1));
   CvUnit* unit=&pool[trial%8];int wounds=(int)(next()%180)-40;plot.city=next()%2!=0;plot.cityData.protection=(int)(next()%91);plot.embark=next()%5==0;
   size_t before=virtualBuilds;
   const int expectedDanger=DLL47UnitDanger(unit,&plot,wounds,position);
   const int expectedScore=DLL47StackScore(unit,&plot,wounds,position);
   const size_t controlBuilds=virtualBuilds-before;
   before=virtualBuilds;MovementDestinationStackQuery destination;
   const int actualDanger=GetUnitDangerForPlot(unit,&plot,wounds,position,&destination);
   // Turn-end and flank calculations must still borrow the original scratch.
   {VirtualFriendlyStackQuery intervening;expect("generic scratch remains free during destination borrow",intervening.borrowed);}
   const int actualScore=ScoreStackPosition(unit,&plot,wounds,position,&destination);
   const size_t changedBuilds=virtualBuilds-before;
   expect("danger matches DLL47 including sentinel/domains/fixed",actualDanger==expectedDanger);
   expect("stack score matches DLL47 including HP/duplicates/roles/cities",actualScore==expectedScore);
   expect("stable pair builds destination once rather than twice",changedBuilds==(controlBuilds?1:0));
   destination.Release();expect("release precedes source helper",!gStackDestinationScratchBusy&&destination.buffer==NULL);
  }
  player.danger.dynamicLeaf=false;player.danger.fixed=false;CvStacking::enabled=true;CvStacking::collateralPercent=20;
 }
 expect("outer scope releases both scratch buffers",gStackVirtualScratch.candidates.capacity()==0&&gStackDestinationScratch.candidates.capacity()==0&&gStackDestinationScratch.damage.m_aExtraStorage.capacity()==0&&!gStackDestinationScratchBusy);
 for(int i=0;i<12;++i){pool[i].domain=DOMAIN_LAND;pool[i].combat=true;pool[i].cargo=false;pool[i].hp=100;pool[i].ranged=i%2!=0;}
 CvTacticalPosition position;position.tactical.fixed.push_back(&pool[1]);position.tactical.moving.push_back(STacticalUnit(3));position.stats[3]=SUnitStats(17);
 {StackForecastScope scope;MovementDestinationStackQuery q;size_t before=virtualBuilds;
  q.Get(position,&plot,&pool[0],7);q.Get(position,&plot,&pool[0],7);expect("same identity reuses exact roster",virtualBuilds==before+1);
  const vector<const CvUnit*> saved=q.buffer->candidates;const int wounds=q.buffer->damage.GetValue(1);
  {MovementDestinationStackQuery nested;nested.Get(position,&plot,&pool[4],23);expect("nested query uses private buffer",!nested.borrowed&&q.buffer->candidates==saved&&q.buffer->damage.GetValue(1)==wounds);}
  before=virtualBuilds;q.Get(position,&plot,&pool[0],8);expect("changed wounds rebuild",virtualBuilds==before+1&&q.buffer->damage.GetValue(1)==8);
  q.Get(position,&otherPlot,&pool[0],8);q.Get(position,&otherPlot,&pool[1],8);CvTacticalPosition copy=position;q.Get(copy,&otherPlot,&pool[1],8);
  expect("plot unit and position identity each rebuild",virtualBuilds==before+4);
  before=virtualBuilds;CvStackingStrengthCache::Invalidate();q.Get(copy,&otherPlot,&pool[1],8);expect("scene epoch invalidates membership reuse",virtualBuilds==before+1);
  before=virtualBuilds;InvalidateStackForecastScene();q.Get(copy,&otherPlot,&pool[1],8);expect("same scene forecast revision invalidates reuse",virtualBuilds==before+1);
  before=virtualBuilds;{StackForecastScope nested;}q.Get(copy,&otherPlot,&pool[1],8);expect("nested search invalidates outer reuse",virtualBuilds==before+1);
  {StackForecastScope nested;q.Get(copy,&otherPlot,&pool[1],8);expect("query resumed in nested context switches to private storage",!q.borrowed&&q.buffer!=&gStackDestinationScratch);}
  q.Release();q.Get(position,&plot,&pool[0],7);
  before=virtualBuilds;CvStackingStrengthCache::Invalidate();statsCallback=invalidateCallback;q.Get(position,&plot,&pool[0],7);q.Get(position,&plot,&pool[0],7);statsCallback=NULL;
  expect("builder callback invalidation prevents reuse admission",virtualBuilds==before+2&&!q.reusable);
  q.Get(position,&plot,&pool[0],7);const vector<const CvUnit*> foreignSaved=q.buffer->candidates;
  HANDLE thread=CreateThread(NULL,0,foreignQuery,&position,0,NULL);expect("foreign query thread created",thread!=NULL);
  if(thread){expect("foreign query completes",WaitForSingleObject(thread,10000)==WAIT_OBJECT_0);DWORD result=~0u;GetExitCodeThread(thread,&result);expect("foreign context rebuilds privately",result==0);CloseHandle(thread);}
  expect("foreign thread preserves outer destination",q.buffer->candidates==foreignSaved&&q.borrowed&&gStackDestinationScratchBusy);
  q.Release();{MovementDestinationStackQuery next;next.Get(position,&plot,&pool[0],7);expect("explicit release admits next borrower",next.borrowed);}
 }
 {MovementDestinationStackQuery q;size_t before=virtualBuilds;q.Get(position,&plot,&pool[0],7);q.Get(position,&plot,&pool[0],7);expect("outside context rebuilds privately",!q.borrowed&&virtualBuilds==before+2);}
 {StackForecastScope scope;player.danger.fixed=true;const int values[3]={0,27,INT_MAX};
  for(int i=0;i<3;++i){player.danger.fixedValue=values[i];MovementDestinationStackQuery q;size_t builds=virtualBuilds,allocs=allocationCalls;unsigned int reads=statsReads;
   expect("fixed danger keeps wrapper sentinel",GetUnitDangerForPlot(&pool[0],&plot,91,position,&q)==(values[i]==INT_MAX?10*pool[0].GetMaxHitPoints():values[i]));
   expect("fixed score unchanged",ScoreStackPosition(&pool[0],&plot,91,position,&q)==0);
   expect("fixed paths allocate and materialize nothing",q.buffer==NULL&&virtualBuilds==builds&&allocationCalls==allocs&&statsReads==reads&&!gStackDestinationScratchBusy);
  }player.danger.fixed=false;player.danger.leafValue=INT_MAX;MovementDestinationStackQuery q;
  expect("raw stack sentinel is not reused as converted danger",GetUnitDangerForPlot(&pool[0],&plot,0,position,&q)==10*pool[0].GetMaxHitPoints()&&ScoreStackPosition(&pool[0],&plot,0,position,&q)==DLL47StackScore(&pool[0],&plot,0,position));player.danger.leafValue=73;
 }
 {StackForecastScope scope;MovementDestinationStackQuery q;player.danger.leafCallback=invalidateCallback;size_t before=virtualBuilds;
  GetUnitDangerForPlot(&pool[0],&plot,0,position,&q);player.danger.leafCallback=NULL;ScoreStackPosition(&pool[0],&plot,0,position,&q);
  expect("danger callback scene mutation forces second roster",virtualBuilds==before+2);
 }
 {StackForecastScope scope;MovementDestinationStackQuery q;player.danger.leafCallback=nestedCallback;size_t before=virtualBuilds;
  GetUnitDangerForPlot(&pool[0],&plot,0,position,&q);ScoreStackPosition(&pool[0],&plot,0,position,&q);
  expect("danger nested search forces second roster",virtualBuilds==before+2);
 }
 {StackForecastScope scope;size_t oldBuilds=0,newBuilds=0,oldAllocs=0,newAllocs=0;
  for(int i=0;i<20000;++i){const int wounds=i%140;size_t before=virtualBuilds,controlAllocs=allocationCalls;DLL47UnitDanger(&pool[0],&plot,wounds,position);DLL47StackScore(&pool[0],&plot,wounds,position);oldBuilds+=virtualBuilds-before;oldAllocs+=allocationCalls-controlAllocs;
   before=virtualBuilds;size_t allocs=allocationCalls;{MovementDestinationStackQuery q;GetUnitDangerForPlot(&pool[0],&plot,wounds,position,&q);ScoreStackPosition(&pool[0],&plot,wounds,position,&q);}newBuilds+=virtualBuilds-before;newAllocs+=allocationCalls-allocs;
  }
  expect("actual stable paired queries halve membership builds",oldBuilds==40000&&newBuilds==20000);
  expect("sharing adds no per-query vector allocations",newAllocs<=oldAllocs+32);
  printf("destination membership build control: DLL47 %u, shared %u across20000pairs; vector allocations DLL47 %u, shared %u. Not a game-speed benchmark.\n",(unsigned int)oldBuilds,(unsigned int)newBuilds,(unsigned int)oldAllocs,(unsigned int)newAllocs);
 }
 expect("final outer scope releases destination capacity",gStackDestinationScratch.candidates.capacity()==0&&gStackDestinationScratch.damage.m_aExtraStorage.capacity()==0&&!gStackDestinationScratchBusy);
 printf("movement destination actual-source regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''

fixture = base['prefix'] + base['container'] + engine + base['cache'] + 'static size_t virtualBuilds=0;\n' + builder + base['danger'] + base['unit_danger'] + base['stack_score'] + original_danger + original_score + tests
fixture = fixture.replace('std::vector<value_type>', 'std::vector<value_type, CountingAllocator<value_type> >').replace('vector<const CvUnit*>', 'vector<const CvUnit*, CountingAllocator<const CvUnit*> >')
cpp = out / 'movement-destination-source-test.cpp'
cpp.write_text(fixture, encoding='utf-8')
vc = root / 'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0'
sdk = root / 'work/toolchain/sdk/windows'
env = os.environ.copy()
env['PATH'] = str(vc / 'Vc7/bin') + ';' + str(vc / 'Common7/IDE') + ';' + env.get('PATH', '')
env['INCLUDE'] = str(root / 'work/toolchain/sdk/vc9/include') + ';' + str(sdk / 'Include')
env['LIB'] = str(root / 'work/toolchain/sdk/vc9/lib') + ';' + str(sdk / 'Lib')
for name in ('CL', '_CL_', 'LINK'):
    env.pop(name, None)
exe = out / 'movement-destination-source-test.exe'
compiled = subprocess.run([str(vc / 'Vc7/bin/cl.exe'), '/nologo', '/EHsc', '/MT', '/O2', '/Z7', str(cpp), '/Fo' + str(out / 'movement-destination-source-test.obj'), '/Fe' + str(exe)], cwd=out, env=env, capture_output=True, text=True, timeout=60)
(out / 'compile.log').write_text(compiled.stdout + compiled.stderr, encoding='utf-8')
if compiled.returncode:
    print(compiled.stdout + compiled.stderr)
    sys.exit(compiled.returncode)
run = subprocess.run([str(exe)], cwd=out, env=env, capture_output=True, text=True, timeout=30)
print(run.stdout + run.stderr, end='')
result = dict(control_commit=control_commit, source_sha256=hashlib.sha256(raw).hexdigest().upper(), fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest().upper(), compile_returncode=compiled.returncode, test_returncode=run.returncode, output=run.stdout + run.stderr,
              scope='actual current cache/query/builders/danger/score with DLL47 reference bodies; full movement body differs only in query plumbing; VC9 x86 engine substitutes; no full DLL or game run')
(out / 'result.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
sys.exit(run.returncode)
