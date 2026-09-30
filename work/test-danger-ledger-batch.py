"""Actual prepared batch and scalar wrapper regression, without production edits.

Uses production source, or --candidate for an isolated prepared copy. Actual
outcome APIs, complete danger sequences and batch/cache wrapper are compiled;
engine damage/selection, synchronization and scalar-map services are deterministic.
"""
from pathlib import Path
import hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];source=root/'work/danger-ledger-candidate' if '--candidate' in sys.argv else root/'CvGameCoreDLL_Expansion2';out=root/'work/danger-ledger-batch-regression';out.mkdir(exist_ok=True)
danger=(source/'CvDangerPlots.cpp').read_text();tactical=(source/'CvTacticalAI.cpp').read_text()
def function(text,signature):
 start=text.index(signature);end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]
def struct(text,signature):
 start=text.index(signature);end=text.index('{',start)+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[start:end]+';'
# The prototype emitted both pinned original math and prepared refactor bodies.
base=(root/'work/danger-ledger-prototype/test.cpp').read_text().split('struct Outcome{')[0]
base=base.replace('typedef vector<pair<PlayerTypes,int> >DangerUnitVector;', 'struct CvDangerPlots;\ntypedef vector<pair<PlayerTypes,int> >DangerUnitVector;',1)
base=base.replace('struct CvPlayer{\n', 'struct CvPlayer{\n CvDangerPlots*GetDangerPlots()const;\n',1)
base=base.replace('static long fieldLeafs=0,cityLeafs=0;', 'static void MaybeMutate();\nstatic long fieldLeafs=0,cityLeafs=0;')
base=base.replace('++fieldLeafs;retaliation=6;', '++fieldLeafs;MaybeMutate();retaliation=6;')
base=base.replace('bool IsCivilianUnit()const{return civilian;}', 'bool IsCombatUnit()const{return !civilian;}bool IsStackingUnit()const{return false;}bool isCargo()const{return false;}bool isNativeDomain(const CvPlot*)const{return true;}bool IsCanDefend()const{return true;}bool IsCivilianUnit()const{return civilian;}')
setup=r'''
const int NO_PLAYER=-1;
static bool ownerThread=true,active=true,moveEvent=false;
static unsigned depth=1;static long liveScene=1,gStackForecastSceneEpoch=1;
static unsigned long gStackForecastRevision=1;
static unsigned long gStackDangerHits=0,gStackDangerMisses=0;
static unsigned long gStackOutcomeBuilds=0,gStackOutcomeReuses=0,gStackOutcomeBypasses=0;
static size_t gStackOutcomeCurrentBytes=0,gStackOutcomePeakBytes=0,gStackKeyPayloadLimit=100000;
#define MOD_EVENTS_CAN_MOVE_INTO moveEvent
struct StackForecastKey{vector<int>state;bool operator<(const StackForecastKey&o)const{return state<o.state;}};
typedef map<StackForecastKey,int>StackDangerForecasts;
static StackDangerForecasts gStackDangerForecasts;
static int stores=0;
static bool IsStackForecastOwner(){return ownerThread;}
static bool StackForecastContext(){
 if(!ownerThread||!active||depth!=1)return false;
 if(liveScene!=gStackForecastSceneEpoch){gStackForecastSceneEpoch=liveScene;++gStackForecastRevision;gStackDangerForecasts.clear();}
 return true;
}
static StackForecastKey gStackDangerScratch;static bool gStackDangerScratchBusy=false;
struct StackForecastQuery{StackForecastKey own;StackForecastKey&key;StackForecastQuery(StackForecastKey&,bool&):key(own){}};
struct StackForecastPairQuery{vector<pair<int,int> >entries;};
static void StoreStackDangerForecast(const StackForecastKey&k,int r){gStackDangerForecasts.insert(make_pair(k,r));++stores;}
struct CvDangerPlots{
 bool m_bDirty;vector<CvDangerPlotContents>m_DangerPlots;int updates;
 CvDangerPlots():m_bDirty(false),updates(0){m_DangerPlots.resize(1);}
 bool IsDirty()const{return m_bDirty;}void UpdateDanger(){m_bDirty=false;++updates;++liveScene;}
 int GetStackDanger(const CvPlot&,const CvUnit*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&);
 bool GetStackDangerOutcome(const CvPlot&,const CvUnit*,const vector<const CvUnit*>&,const SUnitIDValueContainer&,const SUnitIDValueContainer&,SUnitIDValueContainer&,bool&,int&);
 bool TryGetStackDangerFromOutcome(const CvPlot&,const CvUnit*,const SUnitIDValueContainer&,const SUnitIDValueContainer&,bool,int&);
 bool TryGetFixedStackDanger(const CvPlot&,const CvUnit*,int&);
 const vector<int>*GetStackDangerDamageIDs(const CvPlot&);
};
static CvDangerPlots maps[4];CvDangerPlots*CvPlayer::GetDangerPlots()const{return &maps[id];}
'''
wrappers='\n'.join(function(danger,s) for s in ('int CvDangerPlots::GetStackDanger(', 'bool CvDangerPlots::GetStackDangerOutcome(', 'bool CvDangerPlots::TryGetStackDangerFromOutcome(', 'bool CvDangerPlots::TryGetFixedStackDanger(', 'const std::vector<int>* CvDangerPlots::GetStackDangerDamageIDs(', 'bool CvDangerPlotContents::TryGetFixedStackDanger(', 'const std::vector<int>& CvDangerPlotContents::GetStackDangerDamageIDs('))
append='\n'.join(function(tactical,s) for s in ('static void AppendStackCandidates(', 'static void AppendStackDamage(', 'static void AppendStackDamageProjected('))
batch=struct(tactical,'struct StackDangerOutcomeBatch\n');cached=function(tactical,'static int GetCachedStackDanger(')
controlTactical=subprocess.run(['git','show','1f9ef85a9a8700aec794dbb14b3cce44eddb0533:CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root,capture_output=True,text=True,check=True).stdout
protection='\nstatic bool StackPreferencesEnabled(){return true;}\n'+function(controlTactical,'static bool HasSurvivingStackProtection(').replace('HasSurvivingStackProtection','OriginalHasSurvivingStackProtection',1)+'\n'+function(tactical,'static bool HasSurvivingStackProtection(')
sourceServices=r"""
struct SUnitStats{const CvUnit*pUnit;int iPlotIndex,iSelfDamage;SUnitStats():pUnit(NULL),iPlotIndex(0),iSelfDamage(0){}};
struct STacticalUnit{int iUnitID;};
struct CvTacticalPlot{vector<const CvUnit*>fixed;vector<STacticalUnit>moving;const vector<const CvUnit*>&getFixedFriendlyUnits()const{return fixed;}const vector<STacticalUnit>&getUnitsAtPlot()const{return moving;}};
struct CvTacticalPosition{CvTacticalPlot tactical;map<int,SUnitStats>stats;SUnitIDValueContainer enemy;const CvTacticalPlot*getTactPlot(int)const{return &tactical;}int getPlayer()const{return 0;}const SUnitStats*GetUnitStats(int i)const{map<int,SUnitStats>::const_iterator p=stats.find(i);return p==stats.end()?NULL:&p->second;}const SUnitIDValueContainer&GetUnitDamageDealt()const{return enemy;}};
struct VirtualFriendlyStackQuery{vector<const CvUnit*>candidates;SUnitIDValueContainer damage;};
struct Globals{struct Map{const CvPlot*current;Map():current(NULL){}const CvPlot*plotByIndexUnchecked(int)const{return current;}}map;const Map&getMap()const{return map;}}GC;
"""
sourceServices+=function(tactical,'static void GetVirtualFriendlyStack(')+'\n'+function(controlTactical,'static int CalculateLeavingStackProtectionScore(').replace('CalculateLeavingStackProtectionScore','OriginalCalculateLeavingStackProtectionScore',1)+'\n'+function(tactical,'static int CalculateLeavingStackProtectionScore(')

tests=r'''
static int checks=0,failures=0,mutation=0;
static CvUnit*actor=NULL;static CvPlot*targetPtr=NULL;static StackDangerOutcomeBatch*reenterBatch=NULL;
static const vector<const CvUnit*>*reenterRoster=NULL;static const SUnitIDValueContainer*reenterFriendly=NULL,*reenterEnemy=NULL;
static void expect(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<20)printf("FAIL %s\n",n);}}
static void MaybeMutate(){
 const int action=mutation;mutation=0;
 if(action==1)++liveScene;
 if(action==2){++depth;++liveScene;--depth;}
 if(action==3){++depth;++liveScene;GetCachedStackDanger(actor,targetPtr,*reenterRoster,*reenterFriendly,*reenterEnemy,reenterBatch);--depth;}
}
static void Reset(){
 expect("all local payload released",gStackOutcomeCurrentBytes==0);
 ++liveScene;StackForecastContext();ownerThread=active=true;depth=1;moveEvent=false;
 gStackDangerForecasts.clear();gStackDangerHits=gStackDangerMisses=0;
 gStackOutcomeBuilds=gStackOutcomeReuses=gStackOutcomeBypasses=0;gStackOutcomePeakBytes=0;
 stores=mutation=0;fieldLeafs=cityLeafs=0;gStackKeyPayloadLimit=100000;
 for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=p;players[p].team=p;maps[p].m_bDirty=false;maps[p].updates=0;
  for(int q=0;q<4;++q){teams[p].open[q]=false;if(q!=p)players[p].enemies.push_back(q);}}
}
int main(){
 CvPlot target(0),near(1);CvCity city(11,0,&target);CvUnit members[5],attacker(34,1,&near);
 vector<const CvUnit*>roster;SUnitIDValueContainer empty,friendly;friendly.SetValue(87,0);friendly.SetValue(88,-4);
 Reset();attacker.ranged=true;attacker.collateralLimit=0;players[1].units[34]=&attacker;
 for(int i=0;i<5;++i){members[i]=CvUnit(10+i,0,&target);members[i].strength=1000;roster.push_back(&members[i]);}
 actor=&members[0];targetPtr=&target;
 for(int p=0;p<4;++p){maps[p].m_DangerPlots[0].m_pPlot=&target;maps[p].m_DangerPlots[0].m_apUnits.push_back(make_pair(1,34));}
 CvDangerPlotContents&c=maps[0].m_DangerPlots[0];
 {StackDangerOutcomeBatch b(&target,roster,friendly,empty);
  for(int i=0;i<5;++i){int expected=c.GetStackDangerControl(&members[i],roster,friendly,empty);long before=fieldLeafs;
   expect("actual cached scalar exact member result",GetCachedStackDanger(&members[i],&target,roster,friendly,empty,&b)==expected);
   expect("only first scalar miss builds attack outcome",fieldLeafs-before==(i==0?1:0));}
  expect("five scalar misses preserved",gStackDangerMisses==5&&gStackDangerHits==0&&stores==5);
  expect("one build four exact reuses",gStackOutcomeBuilds==1&&gStackOutcomeReuses==4);
  expect("payload retained bounded",gStackOutcomeCurrentBytes>0&&gStackOutcomeCurrentBytes<=gStackKeyPayloadLimit);
 }
 expect("helper return releases local payload",gStackOutcomeCurrentBytes==0);
 // Scalar hits cannot build or traverse an outcome even with a new local batch.
 {StackDangerOutcomeBatch b(&target,roster,friendly,empty);long builds=gStackOutcomeBuilds,leaves=fieldLeafs;
  for(int i=0;i<5;++i)GetCachedStackDanger(&members[i],&target,roster,friendly,empty,&b);
  expect("all five existing scalar hits remain early",gStackDangerHits==5&&gStackOutcomeBuilds==builds&&fieldLeafs==leaves&&!b.ready);}
 Reset();players[1].units[34]=&attacker;
 {StackDangerOutcomeBatch b(&target,roster,friendly,empty);int result=0;
  expect("warm direct batch",b.TryGet(actor,&target,roster,friendly,empty,result));
  long builds=gStackOutcomeBuilds;size_t bytes=gStackOutcomeCurrentBytes;ownerThread=false;
  expect("foreign callback rejects without touching owning payload",!b.TryGet(actor,&target,roster,friendly,empty,result)&&b.ready&&gStackOutcomeBuilds==builds&&gStackOutcomeCurrentBytes==bytes);
  ownerThread=true;++depth;expect("nested callback private fallback",!b.TryGet(actor,&target,roster,friendly,empty,result)&&!b.ready);--depth;
  ++liveScene;expect("outer resumes exact fresh outcome",b.TryGet(actor,&target,roster,friendly,empty,result)&&result==c.GetStackDangerControl(actor,roster,friendly,empty));
  maps[0].m_bDirty=true;builds=gStackOutcomeBuilds;
  expect("dirty refresh forces new outcome",b.TryGet(actor,&target,roster,friendly,empty,result)&&maps[0].updates==1&&gStackOutcomeBuilds==builds+1);
  CvUnit other=*actor;other.owner=2;other.team=2;
  expect("owner team context cannot reuse",b.TryGet(&other,&target,roster,friendly,empty,result)&&result==c.GetStackDangerControl(&other,roster,friendly,empty));
  target.city=&city;other.combatOwner=0;
  expect("combatowner changes exact friendly city branch",b.TryGet(&other,&target,roster,friendly,empty,result)&&result==c.GetStackDangerControl(&other,roster,friendly,empty));
  other.combatOwner=2;teams[0].open[2]=true;
  expect("open borders native branch exact",b.TryGet(&other,&target,roster,friendly,empty,result)&&result==c.GetStackDangerControl(&other,roster,friendly,empty));
  teams[0].open[2]=false;
  expect("closed border branch forces field outcome",b.TryGet(&other,&target,roster,friendly,empty,result)&&result==c.GetStackDangerControl(&other,roster,friendly,empty));
  target.city=NULL;
 }
 Reset();players[1].units[34]=&attacker;
 // Invalidation after a real leaf returns that leaf once and drops admission.
 {StackDangerOutcomeBatch b(&target,roster,friendly,empty);int expected=c.GetStackDangerControl(actor,roster,friendly,empty);fieldLeafs=0;mutation=1;
  expect("post-build scene invalidation returns computed value once",GetCachedStackDanger(actor,&target,roster,friendly,empty,&b)==expected&&fieldLeafs==1&&!b.ready&&stores==0);
  expect("next call computes once after stale batch rejected",GetCachedStackDanger(actor,&target,roster,friendly,empty,&b)==expected&&fieldLeafs==2&&b.ready&&stores==1);}
 Reset();players[1].units[34]=&attacker;
 {StackDangerOutcomeBatch b(&target,roster,friendly,empty);int expected=c.GetStackDangerControl(actor,roster,friendly,empty);fieldLeafs=0;mutation=2;
  expect("nested generation during build cancels admission once",GetCachedStackDanger(actor,&target,roster,friendly,empty,&b)==expected&&fieldLeafs==1&&!b.ready&&stores==0);}
 Reset();players[1].units[34]=&attacker;
 {StackDangerOutcomeBatch b(&target,roster,friendly,empty);reenterBatch=&b;reenterRoster=&roster;reenterFriendly=&friendly;reenterEnemy=&empty;
  int expected=c.GetStackDangerControl(actor,roster,friendly,empty);fieldLeafs=0;mutation=3;
  expect("in-flight ledger survives nested self reentry fallback",GetCachedStackDanger(actor,&target,roster,friendly,empty,&b)==expected&&fieldLeafs==2&&!b.ready&&stores==0);reenterBatch=NULL;}
 Reset();players[1].units[34]=&attacker;
 {StackDangerOutcomeBatch b(&target,roster,friendly,empty);int expected=c.GetStackDangerControl(actor,roster,friendly,empty);fieldLeafs=0;moveEvent=true;
  expect("scripted CanMoveInto conservatively bypasses new reuse",GetCachedStackDanger(actor,&target,roster,friendly,empty,&b)==expected&&fieldLeafs==1&&gStackOutcomeBuilds==0&&!b.ready);moveEvent=false;}
 Reset();players[1].units[34]=&attacker;
 {StackDangerOutcomeBatch b(&target,roster,friendly,empty);active=false;int expected=c.GetStackDangerControl(actor,roster,friendly,empty);fieldLeafs=0;
  expect("inactive forecast uses exact original scalar",GetCachedStackDanger(actor,&target,roster,friendly,empty,&b)==expected&&fieldLeafs==1&&gStackOutcomeBuilds==0&&!b.ready);active=true;}
 Reset();players[1].units[34]=&attacker;
 {StackDangerOutcomeBatch b(&target,roster,friendly,empty);gStackKeyPayloadLimit=8;int result=0;
  expect("capacity ceiling keeps first computed value",b.TryGet(actor,&target,roster,friendly,empty,result)&&result==c.GetStackDangerControl(actor,roster,friendly,empty)&&!b.ready&&gStackOutcomeCurrentBytes==0);
  long builds=gStackOutcomeBuilds;expect("oversized payload not retained or reused",b.TryGet(actor,&target,roster,friendly,empty,result)&&gStackOutcomeBuilds==builds+1&&!b.ready&&gStackOutcomeCurrentBytes==0);}
 Reset();players[1].units[34]=&attacker;
 {vector<const CvUnit*>after=roster;after.erase(after.begin());StackDangerOutcomeBatch beforeB(&target,roster,friendly,empty),afterB(&target,after,friendly,empty);int result=0;
  expect("before source outcome independent",beforeB.TryGet(actor,&target,roster,friendly,empty,result));
  expect("after source outcome independent",afterB.TryGet(&members[1],&target,after,friendly,empty,result));
  expect("simultaneous outcome payload bounded",gStackOutcomeCurrentBytes==gStackOutcomePeakBytes&&gStackOutcomeCurrentBytes<=gStackKeyPayloadLimit);
  SUnitIDValueContainer changed=friendly;changed.ChangeValue(93,100);StackDangerOutcomeBatch fresh(&target,roster,changed,empty);
  expect("new immutable full wounds lifetime builds separately",fresh.TryGet(actor,&target,roster,changed,empty,result)&&result==c.GetStackDangerControl(actor,roster,changed,empty));}
 Reset();players[1].units[34]=&attacker;
 {int result=777;bool fall=false;SUnitIDValueContainer output;long leaves=fieldLeafs;CvPlot bad(-1);
  expect("public outcome rejects null unit",!maps[0].GetStackDangerOutcome(target,NULL,roster,friendly,empty,output,fall,result)&&result==777&&fieldLeafs==leaves);
  expect("public outcome rejects negative index",!maps[0].GetStackDangerOutcome(bad,actor,roster,friendly,empty,output,fall,result)&&fieldLeafs==leaves);
  bad.index=1;expect("public outcome rejects out of bounds",!maps[0].GetStackDangerOutcome(bad,actor,roster,friendly,empty,output,fall,result)&&fieldLeafs==leaves);
  c.m_pPlot=NULL;expect("public outcome rejects null plot contents",!maps[0].GetStackDangerOutcome(target,actor,roster,friendly,empty,output,fall,result)&&fieldLeafs==leaves);c.m_pPlot=&target;
  maps[0].m_bDirty=true;int updates=maps[0].updates;
  expect("outcome extraction refuses dirty map without callbacks",!maps[0].TryGetStackDangerFromOutcome(target,actor,friendly,output,false,result)&&maps[0].updates==updates&&fieldLeafs==leaves);
  expect("build performs required dirty refresh",maps[0].GetStackDangerOutcome(target,actor,roster,friendly,empty,output,fall,result)&&maps[0].updates==updates+1);
 }
 Reset();players[1].units[34]=&attacker;
 {vector<const CvUnit*>after=roster;after.erase(after.begin());StackDangerOutcomeBatch first(&target,roster,friendly,empty),second(&target,after,friendly,empty);int result=0;
  expect("first concurrent payload retained",first.TryGet(actor,&target,roster,friendly,empty,result)&&first.ready);
  gStackKeyPayloadLimit=gStackOutcomeCurrentBytes;long builds=gStackOutcomeBuilds;
  expect("second payload shares local ceiling and returns original value",second.TryGet(&members[1],&target,after,friendly,empty,result)&&result==c.GetStackDangerControl(&members[1],after,friendly,empty)&&!second.ready&&gStackOutcomeCurrentBytes==gStackKeyPayloadLimit&&first.ready&&gStackOutcomeBuilds==builds+1);
  expect("concurrent retained capacity never exceeds ceiling",gStackOutcomePeakBytes<=gStackKeyPayloadLimit);
 }
 Reset();players[1].units[34]=&attacker;
 // Exercise the actual protection caller rather than only batch.Get directly.
 {members[0].ranged=true;members[0].strength=10;fieldLeafs=0;
  bool control=OriginalHasSurvivingStackProtection(actor,&target,roster,friendly,empty,999);long oldLeaves=fieldLeafs;
  gStackDangerForecasts.clear();fieldLeafs=0;gStackDangerHits=gStackDangerMisses=0;stores=0;
  bool candidate=HasSurvivingStackProtection(actor,&target,roster,friendly,empty,999);long newLeaves=fieldLeafs;
  expect("actual protection policy result preserved",candidate==control&&candidate);
  expect("actual full-roster caller original six attack sequences",oldLeaves==6);
  expect("actual protection caller two distinct roster sequences",newLeaves==2);
  expect("actual protection one batch build four reuses",gStackOutcomeBuilds==1&&gStackOutcomeReuses==4);
  expect("protection helper return releases payload",gStackOutcomeCurrentBytes==0);
  printf("actual protector caller: originalLeafs=%ld outcomeLeafs=%ld\n",oldLeaves,newLeaves);
  members[0].ranged=false;members[0].strength=1000;
 }
 Reset();players[1].units[34]=&attacker;
 {members[0].strength=6000;for(int i=1;i<5;++i)members[i].ranged=true;
  CvTacticalPosition position;position.tactical.fixed=roster;SUnitStats unit;unit.pUnit=actor;GC.map.current=&target;
  fieldLeafs=0;int control=OriginalCalculateLeavingStackProtectionScore(unit,position);long oldLeaves=fieldLeafs;
  gStackDangerForecasts.clear();fieldLeafs=0;gStackDangerHits=gStackDangerMisses=0;stores=0;
  int candidate=CalculateLeavingStackProtectionScore(unit,position);long newLeaves=fieldLeafs;
  expect("actual source leave-protector score preserved",candidate==control&&candidate<0);
  expect("four ranged old/new source needs eight control sequences",oldLeaves==8);
  expect("source old/new rosters need two outcome sequences",newLeaves==2);
  expect("source caller two builds six reuses",gStackOutcomeBuilds==2&&gStackOutcomeReuses==6);
  expect("source helper releases both payloads",gStackOutcomeCurrentBytes==0);
  printf("actual source-leaving caller: originalLeafs=%ld outcomeLeafs=%ld\n",oldLeaves,newLeaves);
  members[0].strength=1000;for(int i=1;i<5;++i)members[i].ranged=false;
 }
 Reset();players[1].units[34]=&attacker;
 {c.m_apUnits.clear();c.InvalidateStackDangerDamageIDs();c.m_iImprovementDamage=9;c.m_iFogCount=5;StackDangerOutcomeBatch b(&target,roster,friendly,empty);
  expect("fixed hazard shortcut has no outcome build",GetCachedStackDanger(actor,&target,roster,friendly,empty,&b)==14&&gStackOutcomeBuilds==0&&gStackDangerMisses==0&&!b.ready);}
 expect("all payload released on final return",gStackOutcomeCurrentBytes==0);
 printf("actual outcome batch/cache regression: %d checks, %d failures\n",checks,failures);return failures?1:0;
}
'''
fixture=base+setup+wrappers+append+batch+cached+protection+sourceServices+tests
cpp=out/'test.cpp';cpp.write_text(fixture,encoding='utf-8')
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
exe=out/'test.exe';c=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7',str(cpp),'/Fo'+str(out/'test.obj'),'/Fe'+str(exe)],cwd=out,env=env,capture_output=True,text=True,timeout=60)
(out/'compile.log').write_text(c.stdout+c.stderr,encoding='utf-8')
if c.returncode:print(c.stdout+c.stderr);sys.exit(c.returncode)
r=subprocess.run([str(exe)],cwd=out,capture_output=True,text=True,timeout=60);print(r.stdout+r.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(source_sha256=hashlib.sha256((danger+tactical).encode()).hexdigest(),fixture_sha256=hashlib.sha256(fixture.encode()).hexdigest(),returncode=r.returncode,output=r.stdout+r.stderr,scope='Actual complete danger/outcome APIs and batch/scalar wrapper. Pinned original scalar oracle. Deterministic engine numerical services, scalar map and scope synchronization. No production changes, native DLL build or game run.'),indent=2),encoding='utf-8')
sys.exit(r.returncode)
