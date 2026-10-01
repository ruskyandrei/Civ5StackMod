"""Pinned kernels/forecast graph + staged observer; deterministic engine model.

No core/game writes. Prerequisite stage-destination-kernel-probe.py and the
tracked immediate-borrow/packet numerical extraction helpers. This verifies
observation neutrality/censorship and deliberate footprint failure detection,
not native reuse completeness, benefit or full planner mutation coverage.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--stage-directory',type=Path,default=Path('work/destination-kernel-probe-staged'))
parser.add_argument('--output-directory',type=Path,default=Path('work/destination-kernel-probe-regression'))
parser.add_argument('--emit-only',action='store_true')
parser.add_argument('--bind-current',action='store_true',help='Bind whole current source to pinned control before emission')
parser.add_argument('--production',action='store_true',help='Bind whole current source to reviewed candidate before emission/compilation')
args=parser.parse_args()
stage=args.stage_directory if args.stage_directory.is_absolute() else ROOT/args.stage_directory
OUT=args.output_directory if args.output_directory.is_absolute() else ROOT/args.output_directory;OUT.mkdir(exist_ok=True)
manifest=json.loads((stage/'manifest.json').read_text())
control=(stage/'control.cpp').read_text(encoding='utf-8-sig');candidate=(stage/'CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
assert hashlib.sha256(control.encode()).hexdigest()==manifest['original_sha256']
assert hashlib.sha256(candidate.encode()).hexdigest()==manifest['candidate_sha256']
live=(ROOT/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
indexed=manifest.get('indexed_backend',False)
actual_whole_hashes={}
if args.bind_current or args.production:
 for name,digest in manifest['original_whole_files_sha256'].items():
  actual=(ROOT/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig')
  expected=manifest['candidate_sha256'] if args.production and name=='CvTacticalAI.cpp' else manifest['diagnostics_candidate_sha256'] if args.production and name=='CvStackingDiagnostics.cpp' else digest
  actual_whole_hashes[name]=hashlib.sha256(actual.encode()).hexdigest()
  assert actual_whole_hashes[name]==expected,'Whole current '+('candidate' if args.production else 'control')+' source mismatch: '+name
generator=(ROOT/'work/test-immediate-forecast-borrow.py').read_text(encoding='utf-8-sig')
prefix=generator[:generator.index("\ntests=r'''")]
setup_start=prefix.index("stage=root/'work/immediate-forecast-borrow-stage'")
setup_end=prefix.index('# Reuse only tracked extraction/services,',setup_start)
# Bind fresh Git sources directly. Never require an ignored stage manifest or
# a generated C++ scaffold merely to reproduce this new experiment.
fresh_setup='''proof={'control':extraction_control}
names=('CvTacticalAI.cpp','CvUnit.cpp','CvDangerPlots.cpp','CvStackingStrengthCache.h','CvStackingStrengthCache.cpp','CvDangerPlots.h','CvUnit.h','CvUnitCombat.cpp','CvPlot.cpp','CvStackingRules.h','CvStackingRules.cpp')
original={n:subprocess.check_output(['git','show',proof['control']+':CvGameCoreDLL_Expansion2/'+n],cwd=root).decode('utf-8-sig').replace('\\r\\n','\\n') for n in names}
candidate=dict(original);candidate['CvTacticalAI.cpp']=frozen86
old,new=original['CvTacticalAI.cpp'],candidate['CvTacticalAI.cpp']
if expect_indexed:assert old==new,'Indexed fixture control must be the complete pinned current source'
else:assert new.replace('bool cacheable = query.scratch != NULL || StackForecastContext();','bool cacheable = StackForecastContext();')==old
'''
prefix=prefix[:setup_start]+fresh_setup+prefix[setup_end:]
# The reused generator's numerical extraction must not silently read later
# production Unit/Combat/Rules files when reproducing a historical control.
template_line="template=(root/'work/test-packet-probe.py').read_text(encoding='utf-8-sig')"
assert prefix.count(template_line)==1
template_pin='''
for name in ('CvUnit.h','CvUnitCombat.cpp','CvStackingRules.cpp','CvStackingRules.h'):
 template=template.replace("(core/'"+name+"').read_text(encoding='utf-8-sig')","current['"+name+"']")
'''
prefix=prefix.replace(template_line,template_line+template_pin,1)
scope={'__file__':str(ROOT/'work/test-immediate-forecast-borrow.py'),'frozen86':control,
       'extraction_control':manifest['control'] if indexed else 'c92e941cfaf5db4577ac555262a938e52bc3f877','expect_indexed':indexed};arguments=sys.argv
try:
 sys.argv=[arguments[0],'--production'];exec(compile(prefix,'actual86 extraction/strong provider only','exec'),scope)
finally:sys.argv=arguments
assert scope['new']==control,'Extraction control must be byte-exact pinned Tactical source'
function=scope['function'];headers=scope['headers'];base=scope['base'];services=scope['services']
base=base.replace('int GetID()const{return id;}','int GetDanger(const CvPlot*,const struct SUnitIDValueContainer&,int)const{return 87;}\n int GetID()const{return id;}',1)
base=base.replace('namespace CvStacking{\n static bool enabled', 'static int fixtureJoinBonus=12;\nnamespace CvStacking{\n static bool enabled',1)
base=base.replace('int GetInt(const char*n,int d){return !strcmp(n,"DefenderSelectionEnabled")?', 'int GetInt(const char*n,int d){if(!strcmp(n,"AIStackJoinBonus"))return fixtureJoinBonus;return !strcmp(n,"DefenderSelectionEnabled")?',1)
assert 'static int fixtureJoinBonus=12;' in base
services=services.replace('struct Storage{int getSizeLimit()const{return 6000;}}',r'''struct DummyDangerCache{bool findDanger(int,int,int,const SUnitIDValueContainer&,int&)const{return false;}void storeDanger(int,int,int,const SUnitIDValueContainer&,int){}};
struct Storage{DummyDangerCache cache;int getSizeLimit()const{return 6000;}DummyDangerCache&getDangerCache(){return cache;}}''',1)
services=services.replace('enum Part{PLAN_DANGER_KEY,PLAN_DANGER_LEAF};','enum Part{PLAN_DANGER_KEY,PLAN_DANGER_LEAF,PLAN_UNIT_DANGER,PLAN_STACK_SCORE};',1)
services=services.replace('if(strcmp(category,"PLAN_PACKET_PROBE"))abort();','if(strcmp(category,"PLAN_PACKET_PROBE")&&strcmp(category,"PLAN_KERNEL_PROBE"))abort();',1)
services+='\nvector<CvUnit*>CvPlayer::GetPossibleAttackers(const CvPlot&plot,int)const{vector<CvUnit*>r;const CvDangerPlotContents&c=maps[id].m_DangerPlots[plot.GetPlotIndex()];for(size_t i=0;i<c.m_apUnits.size();++i){const CvUnit*u=GET_PLAYER(c.m_apUnits[i].first).getUnit(c.m_apUnits[i].second);if(u&&!u->IsDead()&&!u->isDelayedDeath())r.push_back(const_cast<CvUnit*>(u));}return r;}\n'
base=base.replace('CvDangerPlots*GetDangerPlots()const;int id,team;', 'CvDangerPlots*GetDangerPlots()const;vector<CvUnit*>GetPossibleAttackers(const CvPlot&,int)const;int id,team;',1)
engine=r'''
struct SUnitStats{int iUnitID,iSelfDamage,iMovesLeft;const CvUnit*pUnit;SUnitStats(int id=0,int wounds=0,const CvUnit*u=NULL):iUnitID(id),iSelfDamage(wounds),iMovesLeft(120),pUnit(u){}};
struct STacticalUnit{int iUnitID;STacticalUnit(int id=0):iUnitID(id){}};
struct CvTacticalPlot{vector<const CvUnit*>fixed;vector<STacticalUnit>moving;const vector<const CvUnit*>&getFixedFriendlyUnits()const{return fixed;}const vector<STacticalUnit>&getUnitsAtPlot()const{return moving;}};
template<class T>struct Field{T data;const T&read()const{return data;}};
struct CvTacticalPosition{
 Field<vector<SUnitStats> >availableUnits,notQuiteFinishedUnits,finishedUnits;SUnitIDValueContainer enemy;CvTacticalPlot tactical;bool present;
 const CvTacticalPosition*parent;unsigned long long identity;int generation;
 CvTacticalPosition():present(true),parent(NULL),identity(1),generation(0){}
 const CvTacticalPlot*getTactPlot(int)const{return present?&tactical:NULL;}int getPlayer()const{return 0;}
 const SUnitStats*GetUnitStats(int)const;const SUnitIDValueContainer&GetUnitDamageDealt()const{return enemy;}
 const CvTacticalPosition*getParent()const{return parent;}unsigned long long getID()const{return identity;}int getGeneration()const{return generation;}
};
'''
engine+='\n'+function(control,'const SUnitStats* CvBasePosition::GetUnitStats(').replace('CvBasePosition::','CvTacticalPosition::',1)
common=scope['common'];implementation=common
for name,text in [('Control',control),('Trial',candidate)]:
 body=scope['cache_module'](text)
 # Actual probe is inserted after packet helper definitions, before danger.
 builder=text[text.index('static void GetVirtualFriendlyStack('):text.index('// A same-tile escort counts only')]
 kernels='\n'.join(function(text,s) for s in ('static bool StackPreferencesEnabled(', 'static int GetUnitDangerForPlot(', 'static unsigned char GetStackAttackThreatFlags(', 'static int ScoreStackPositionMembers(', 'static int ScoreStackPosition('))
 implementation+='\nnamespace '+name+'{\n'+body+'\n'+builder+'\n'+kernels+'\n}\n'
# The complete source fragment needs to enter Trial at the actual source site.
fragment=(ROOT/'work/destination-kernel-probe-fragment.cpp').read_text(encoding='utf-8-sig')
assert fragment in candidate and fragment not in control
assert implementation.count('struct DestinationKernelProbeState\n')==1

tests=r'''
static unsigned checks=0,failures=0,leafCalls=0,mutation=0,seed=314159;
static void Check(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<25)printf("FAIL %s\n",n);}}
static unsigned Next(){seed=1664525u*seed+1013904223u;return seed;}
static void OnUnitLookup(){}
static void OnLeaf(){++leafCalls;if(mutation){mutation=0;CvStackingStrengthCache::Invalidate();}}
static bool ActualProvider(unsigned int&flags,bool scan){return Trial::StackPreviewCallbackCapabilities(flags,scan);}
static void Enable(bool enabled){CvStackingDiagnostics::planSamples.enabled=enabled;CvStackingDiagnostics::planSamples.depth=enabled?1:0;CvStackingDiagnostics::planSamples.serial=19;CvStackingDiagnostics::planSamples.epoch=CvStackingDiagnostics::ReadPlanSampleEpoch();}
static int Actor(unsigned kind,int remainder){for(int i=1;i<10000;++i){int words[4]={(int)kind,0,i,0};if((Trial::KernelProbeHash(words,4)&63)==0&&(remainder<0||i%7==remainder))return i;}return -1;}
struct ForeignData{Trial::DestinationKernelProbeFrame*frame;Trial::DestinationKernelProbeSession*session;};
static DWORD WINAPI Foreign(void*ptr){ForeignData*f=(ForeignData*)ptr;f->frame->Finish(37);f->session->Finish();return 0;}
int main(){
 Check("actual x86 metadata bound",sizeof(void*)==4&&sizeof(Trial::DestinationKernelProbeState)<=3*1024*1024);
 for(int p=0;p<4;++p){players[p].id=players[p].team=p;for(int q=0;q<4;++q)if(q!=p)players[p].enemies.push_back(q);}
 CvPlot target(0),nearby(1);CvUnit ranged(Actor(0,6),0,&target),melee(Actor(1,0),0,&target),attacker(44,1,&nearby);
 Check("coherent actor cohorts found",ranged.id>0&&melee.id>0);ranged.ranged=true;ranged.hp=100;ranged.maxHP=100;melee.hp=melee.maxHP=500;attacker.ranged=false;attacker.collateralLimit=0;
 players[0].units[ranged.id]=&ranged;players[0].units[melee.id]=&melee;players[1].units[44]=&attacker;
 CvDangerPlotContents&contents=maps[0].m_DangerPlots[0];contents.m_pPlot=&target;contents.m_apUnits.push_back(make_pair(1,44));
 CvTacticalPosition parent;parent.availableUnits.data.push_back(SUnitStats(melee.id,0,&melee));parent.availableUnits.data.push_back(SUnitStats(ranged.id,0,&ranged));parent.tactical.moving.push_back(STacticalUnit(melee.id));parent.tactical.moving.push_back(STacticalUnit(ranged.id));
 CvTacticalPosition child=parent;child.parent=&parent;child.identity=11;child.generation=1;child.availableUnits.data[0].iMovesLeft=60; // no destination-kernel input changed
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Trial::StackForecastScope forecast(true);Enable(false);size_t before=allocationCalls;unsigned records=CvStackingDiagnostics::records;Trial::DestinationKernelProbeSession off(0,0);int result=Trial::GetUnitDangerForPlot(&ranged,&target,0,parent);Check("disabled scope allocates no observer/source payload",off.state==NULL&&Trial::gDestinationKernelProbe==NULL&&CvStackingDiagnostics::records==records);before=allocationCalls;Trial::GetUnitDangerForPlot(&ranged,&target,0,parent);Check("disabled warmed original scalar hit no new allocation",allocationCalls==before&&result==Trial::GetUnitDangerForPlot(&ranged,&target,0,parent));}
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Control::StackForecastScope old(true);Trial::StackForecastScope current(true);Enable(true);Trial::DestinationKernelProbeSession observation(0,0);Trial::ObserveKernelStateMutation(&parent,NULL);Trial::ObserveKernelStateMutation(&child,&parent);
  unsigned oldLeaves=leafCalls;int a=Control::GetUnitDangerForPlot(&ranged,&target,0,parent);oldLeaves=leafCalls-oldLeaves;unsigned newLeaves=leafCalls;int b=Trial::GetUnitDangerForPlot(&ranged,&target,0,parent);newLeaves=leafCalls-newLeaves;Check("observer original mathematical graph/calls exact",a==b&&oldLeaves==newLeaves&&Control::gStackDangerHits==Trial::gStackDangerHits&&Control::gStackDangerMisses==Trial::gStackDangerMisses);
  a=Control::GetUnitDangerForPlot(&ranged,&target,0,child);b=Trial::GetUnitDangerForPlot(&ranged,&target,0,child);Check("real child destination result unchanged",a==b);Trial::DestinationKernelProbeCounts&counts=observation.state->kinds[0];Check("cross-parent footprint equality observed",counts.complete==2&&counts.groups==1&&counts.crossState==1&&counts.parentChild==1&&counts.mismatches==0&&counts.keyVisits==2);
  CvTacticalPosition reused=child;Trial::ObserveKernelStateMutation(&reused,&parent);Trial::GetUnitDangerForPlot(&ranged,&target,0,reused);unsigned __int64 same=counts.sameState,cross=counts.crossState;Trial::ObserveKernelStateMutation(&reused,&parent);Trial::GetUnitDangerForPlot(&ranged,&target,0,reused);Check("same pointer/ID/generation cannot identify reconstructed temp",counts.sameState==same&&counts.crossState==cross+1);
  // Match original controls after the additional two observation-only queries.
  Control::GetUnitDangerForPlot(&ranged,&target,0,reused);Control::GetUnitDangerForPlot(&ranged,&target,0,reused);
  for(int i=0;i<2000;++i){CvTacticalPosition changed=child;changed.identity=12+i;changed.availableUnits.data[0].iMovesLeft=i%120;changed.availableUnits.data[1].iSelfDamage=i%90;changed.enemy.SetValue(44,i%60);Trial::ObserveKernelStateMutation(&changed,&child);int expected=Control::GetUnitDangerForPlot(&ranged,&target,i%43,changed);int actual=Trial::GetUnitDangerForPlot(&ranged,&target,i%43,changed);Check("parent/child actual danger exact with wound deltas",expected==actual);Check("whole legacy lookup/work pressure untouched by observation",Control::gStackDangerHits==Trial::gStackDangerHits&&Control::gStackDangerMisses==Trial::gStackDangerMisses&&Control::gStackDangerEvictions==Trial::gStackDangerEvictions&&Control::gStackKeyPayloadBytes==Trial::gStackKeyPayloadBytes);}
  printf("shadow observation selected=%I64u complete=%I64u groups=%I64u repeats=%I64u oversized=%I64u unavailable=%I64u invalidated=%I64u evictions=%I64u\n",counts.selected,counts.complete,counts.groups,counts.repeats,observation.state->oversized,observation.state->unavailable,observation.state->invalidated,observation.state->evictions);
  Check("bounded FIFO censors metadata only",observation.state->evictions>0&&observation.state->keyBytes<=Trial::KERNEL_PROBE_SLOTS*Trial::KERNEL_PROBE_WORDS*sizeof(int));
  unsigned records=CvStackingDiagnostics::records;observation.Finish();Check("one bounded summary row",CvStackingDiagnostics::records==records+1&&CvStackingDiagnostics::maxRowBytes<3072&&strstr(CvStackingDiagnostics::lastRow,"not_certified_reuse_no_stride_scaling")!=NULL);Enable(false);
 }
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Control::StackForecastScope old(true);Trial::StackForecastScope current(true);Enable(true);Trial::DestinationKernelProbeSession observation(0,0);Trial::ObserveKernelStateMutation(&parent,NULL);Trial::ObserveKernelStateMutation(&child,&parent);vector<const CvUnit*>roster;roster.push_back(&melee);roster.push_back(&ranged);SUnitIDValueContainer none;
  int a=Control::ScoreStackPositionMembers(&melee,&target,parent,roster,none),b=Trial::ScoreStackPositionMembers(&melee,&target,parent,roster,none);Check("actual stack score/forecast graph unchanged",a==b&&Control::gStackDangerMisses==Trial::gStackDangerMisses&&Control::gStackDangerHits==Trial::gStackDangerHits);
  a=Control::ScoreStackPositionMembers(&melee,&target,child,roster,none);b=Trial::ScoreStackPositionMembers(&melee,&target,child,roster,none);Check("actual child stack score unchanged",a==b);Check("whole stack-key sequence detects parent match",observation.state->kinds[1].parentChild==1&&observation.state->kinds[1].mismatches==0);
  unsigned __int64 groups=observation.state->kinds[1].groups;ranged.hp=99;Trial::ScoreStackPositionMembers(&melee,&target,child,roster,none);Check("live HP is stronger than old projected scalar key",observation.state->kinds[1].groups==groups+1);ranged.hp=100;
  unsigned __int64 mismatch=observation.state->kinds[1].mismatches;Trial::ScoreStackPositionMembers(&melee,&target,parent,roster,none);fixtureJoinBonus+=3;Trial::ScoreStackPositionMembers(&melee,&target,child,roster,none);Check("deliberate unmodeled-setting footprint falsified",observation.state->kinds[1].mismatches==mismatch+1);fixtureJoinBonus=12;
  {Trial::DestinationKernelProbeFrame pending(1,&melee,&target,parent,0,&roster,&none);ForeignData data={&pending,&observation};HANDLE t=CreateThread(NULL,0,Foreign,&data,0,NULL);Check("foreign created",t!=NULL);if(t){Check("foreign bounded exit",WaitForSingleObject(t,5000)==WAIT_OBJECT_0);CloseHandle(t);}Check("foreign finish cannot release owner scratch",observation.state&&observation.state->busy&&pending.state==observation.state);pending.Finish(0);}
  {Trial::DestinationKernelProbeFrame outer(1,&melee,&target,parent,0,&roster,&none);unsigned count=observation.state->count;Trial::DestinationKernelProbeFrame inner(1,&melee,&target,child,0,&roster,&none);Check("nested footprint cannot overwrite pending buffer",!inner.state&&observation.state->count==count);outer.Finish(0);}
  mutation=1;unsigned __int64 invalid=observation.state->invalidated;Trial::ClearStackForecastEntries();Trial::GetUnitDangerForPlot(&ranged,&target,37,parent);Check("during-leaf scene drift discards observation",observation.state->invalidated>invalid&&!observation.state->busy);
  maps[0].m_bDirty=true;unsigned refresh=refreshCalls;Trial::DestinationKernelProbeFrame dirty(1,&melee,&target,parent,0,&roster,&none);Check("dirty descriptor never refreshes before original",!dirty.state&&refreshCalls==refresh&&maps[0].m_bDirty);maps[0].m_bDirty=false;
  vector<const CvUnit*>wide(200,&melee);Trial::DestinationKernelProbeFrame tooWide(1,&melee,&target,parent,0,&wide,&none);Check("bounded participant/word footprint explicitly censored",!tooWide.state&&observation.state->oversized>0&&!observation.state->busy);
  for(unsigned i=0;i<Trial::KERNEL_PROBE_STATES;++i)observation.state->states[i].state=reinterpret_cast<const CvTacticalPosition*>((size_t)0x40000000+32*i);unsigned __int64 unknown=observation.state->unknownStates;Check("full state registry has bounded censored lookup",Trial::KernelProbeIncarnation(*observation.state,&parent)==NULL&&observation.state->unknownStates==unknown+1&&Trial::KERNEL_PROBE_STATE_LOOKUP_LIMIT==64);
  observation.Finish();Enable(false);
 }
 Check("no retained metadata after session",Trial::gDestinationKernelProbe==NULL&&Trial::gDestinationKernelFrame==NULL);
 printf("DESTINATION KERNEL SHADOW:%u checks,%u failures; actual86 kernels+forecast graph/strong proof; conservative observed parent reuse, original work unchanged; no native ROI\n",checks,failures);return failures?1:0;
}
'''
if indexed:
 tests=tests.replace('unsigned oldLeaves=leafCalls;', 'Check("actual indexed backends active in both source kernels",Control::gUseIndexed&&Trial::gUseIndexed&&Control::gIndexed.Capacity()==6001&&Trial::gIndexed.Capacity()==6001);unsigned oldLeaves=leafCalls;',1)
 tests=tests.replace('Check("bounded FIFO censors metadata only",', 'Check("indexed original result pools remain numerically/work neutral",Control::gIndexed.Total()==Trial::gIndexed.Total()&&Control::gIndexed.FIFOCount(0)==Trial::gIndexed.FIFOCount(0)&&Control::gIndexed.FIFOCount(1)==Trial::gIndexed.FIFOCount(1));Check("bounded FIFO censors metadata only",',1)
 tests=tests.replace('actual86 kernels+forecast graph/strong proof','actual indexed kernels+forecast graph/strong proof')
code=headers+scope['strength_header']+scope['strength_module']+scope['native_services']+base+services+engine+implementation+tests
(OUT/'test.cpp').write_text(code,encoding='utf-8')
binding=dict(control=manifest['control'],diagnostics_control=manifest['diagnostics_control'],indexed_backend=indexed,
             production_untouched=True,bound_current_control=args.bind_current,bound_current_production=args.production,
             actual_whole_source_sha256=actual_whole_hashes,original_sha256=manifest['original_sha256'],candidate_sha256=manifest['candidate_sha256'],
             fixture_sha256=hashlib.sha256(code.encode()).hexdigest(),whole_gameplay_reverse_exact=manifest['whole_gameplay_reverse_exact'],
             complete_math_bindings=scope['math_bindings'],whole_strength_header_sha256=hashlib.sha256(scope['strength_header'].encode()).hexdigest(),
             whole_strength_module_sha256=hashlib.sha256(scope['strength_module'].encode()).hexdigest(),
             actual_context_and_provider=True,indexed_class_definition_count=code.count('class IndexedStore\n'),
             indexed_scalar_lookup_definition_count=code.count('static bool FindStackDangerForecastScalar('),compiled=False,game_used=False,
             scope='Complete pinned source kernels/cache/backend and strengthened capability module against explicit deterministic engine/position services. Source emission is not compilation or native neutrality/speed evidence.')
if indexed:assert binding['indexed_class_definition_count']==2 and binding['indexed_scalar_lookup_definition_count']==2,'Both complete native indexed modules must be emitted'
(OUT/('production-emission-proof.json' if args.production else 'emission-proof.json')).write_text(json.dumps(binding,indent=2)+'\n',encoding='utf-8')
if args.emit_only:print(json.dumps(dict(status='emitted_only',**binding)));sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for k in ('CL','_CL_','LINK'):env.pop(k,None)
build=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(OUT/'test.cpp'),'/Fe'+str(OUT/'test.exe')],cwd=OUT,env=env,capture_output=True,text=True,timeout=90);(OUT/'compile.log').write_text(build.stdout+build.stderr)
if build.returncode:print(build.stdout+build.stderr);sys.exit(build.returncode)
run=subprocess.run([str(OUT/'test.exe')],cwd=OUT,capture_output=True,text=True,timeout=40);print(run.stdout+run.stderr,end='')
report=dict(binding)
report.update(returncode=run.returncode,output=run.stdout+run.stderr,compiled=True,actual_kernel_source=True,source_sha256=manifest['candidate_sha256'],
              scope='Pinned actual virtual builder, first-match stats lookup, complete danger/stack kernels, complete selected forecast backend and mathematical leaves/strong capability module. Deterministic engine/position services explicitly substitute native objects; observer never replaces work/results. Parent-child footprint and deliberate missing-setting control are measurements, not full dependency certification/native performance.')
(OUT/('production-result.json' if args.production else 'result.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
sys.exit(run.returncode)
