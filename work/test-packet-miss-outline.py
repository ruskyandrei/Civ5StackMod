"""Actual DLL94 scalar/packet/cache/math old-new split oracle; no core writes."""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,os,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('packet_miss_outline',ROOT/'work/prepare-packet-miss-outline.py');stager=importlib.util.module_from_spec(spec);spec.loader.exec_module(stager)
P=argparse.ArgumentParser(description=__doc__);P.add_argument('--emit-only',action='store_true');P.add_argument('--production',action='store_true');args=P.parse_args()
control,candidate,proof=stager.stage();BASE=stager.BASE;OUT=ROOT/'work/packet-miss-outline-regression';OUT.mkdir(exist_ok=True)
names=('CvTacticalAI.cpp','CvUnit.cpp','CvDangerPlots.cpp','CvStackingStrengthCache.h','CvStackingStrengthCache.cpp','CvDangerPlots.h','CvUnit.h','CvUnitCombat.cpp','CvPlot.cpp','CvStackingRules.h','CvStackingRules.cpp','CvStackingDiagnostics.h','CvStackingDiagnostics.cpp')
source={n:subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/'+n],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n') for n in names}
actual_hashes={}
if args.production:
 for n,s in source.items():
  actual=(ROOT/'CvGameCoreDLL_Expansion2'/n).read_text(encoding='utf-8-sig');assert actual==(candidate if n=='CvTacticalAI.cpp' else s),'Whole production candidate/dependency mismatch: '+n;actual_hashes[n]=hashlib.sha256(actual.encode()).hexdigest()

# Reuse tracked complete numerical extraction/services, pinned to frozen94.
# Skip its unrelated historical two-line equality assertion and all execution.
generator=(ROOT/'work/test-immediate-forecast-borrow.py').read_text(encoding='utf-8-sig')
prefix=generator[:generator.index('\ndef cache_module(')]
a=prefix.index("stage=root/'work/immediate-forecast-borrow-stage'");b=prefix.index('# Reuse only tracked extraction/services,',a)
setup="proof={'control':extraction_control}\noriginal=extraction_sources\ncandidate=dict(original)\nold=new=original['CvTacticalAI.cpp']\n"
prefix=prefix[:a]+setup+prefix[b:]
line="template=(root/'work/test-packet-probe.py').read_text(encoding='utf-8-sig')"
prefix=prefix.replace(line,line+"\nfor name in ('CvUnit.h','CvUnitCombat.cpp','CvStackingRules.cpp','CvStackingRules.h'):\n template=template.replace(\"(core/'\"+name+\"').read_text(encoding='utf-8-sig')\",\"current['\"+name+\"']\")\n",1)
scope={'__file__':str(ROOT/'work/test-immediate-forecast-borrow.py'),'extraction_control':BASE,'extraction_sources':source}
exec(compile(prefix,'tracked frozen94 numerical services','exec'),scope)
function=scope['function'];base=scope['base'];services=scope['services']
base=base.replace('if(failAllocation)throw std::bad_alloc();','if(failAllocation){failAllocation=false;throw std::bad_alloc();}',1)
services=services.replace('bool TryGetPlanSamplingContext(unsigned long&serial,long&epoch){','bool TryGetPlanSamplingContext(unsigned long&serial,long&epoch){',1)
# Minimal position services are solely for the unchanged disabled kernel probe.
engine=r'''
struct CvTacticalPosition{SUnitIDValueContainer damage;const SUnitIDValueContainer&GetUnitDamageDealt()const{return damage;}};
static bool traceLifecycle=false;static vector<int>lifecycle;
static void Lifecycle(int mark){if(traceLifecycle)lifecycle.push_back(mark);}
'''
scope_class=function(source['CvStackingDiagnostics.h'],'class PlanSampleScope\n')
scope_members=scope_class[scope_class.index('bool sampled;'):scope_class.rindex('}')].replace('PlanSamplePart','Part')
scope_stub='enum Part{PLAN_DANGER_KEY,PLAN_DANGER_LEAF};struct PlanSampleScope{'+scope_members+r'''__declspec(noinline) PlanSampleScope(Part p,bool=true):sampled(true),part(p),serial(0),epoch(0),started(0),threadState(NULL){Lifecycle(100+p);}void Finish(){if(sampled){sampled=false;Lifecycle(200+part);}}~PlanSampleScope(){Finish();Lifecycle(300+part);}};'''
services=services.replace('enum Part{PLAN_DANGER_KEY,PLAN_DANGER_LEAF};struct PlanSampleScope{PlanSampleScope(Part,bool=true){}void Finish(){}};',scope_stub,1)
def module(text):
 body=text[text.index('struct StackForecastKey\n'):text.index('// Bind immutable inputs only')]
 body+='\n'+function(text,'struct StackDangerOutcomeBatch\n')+';\n'
 body+='\n'+text[text.index('static bool AppendUniquePacketDamage('):text.index('static int GetCachedStackDanger(')]
 body+='\n'+function(text,'static int GetCachedStackDanger(')
 body+='\n'+function(text,'static const CvUnit* SelectCachedStackDefender(')
 # Parent preparation is never activated by these direct scalar calls. Its
 # release seam is an explicit unused-service substitute, not a new oracle.
 body+='\nstatic void ReleaseParentStackPreparationStorage(){}\n'
 # Diagnostic-only fixture markers retain each real destructor body/order.
 query=function(body,'~StackForecastQuery()');body=body.replace(query,query.replace('{','{\n Lifecycle(400);',1),1)
 packet=function(body,'~StackDangerPacketQuery()');body=body.replace(packet,packet.replace('{','{Lifecycle(500);',1),1)
 probe=function(body,'~PacketProbeCall()');body=body.replace(probe,probe.replace('{','{Lifecycle(600);',1),1)
 context=function(body,'static bool StackForecastContext(')
 body=body.replace(context,context.replace('{','{\n ++fixtureContextCalls;',1),1)
 return body
implementation=scope['common']
for name,text in [('Baseline',control),('Trial',candidate)]:implementation+='\nnamespace '+name+'{\nstatic unsigned fixtureContextCalls=0;\n'+module(text)+'\n}\n'
tests=r'''
static unsigned checks=0,failures=0,leafCalls=0,seed=718213,lookupMutation=0,leafMutation=0;
static bool throwLeaf=false,nestLeaf=false,throwLeafAllocation=false;static unsigned providerCalls=0,validationCalls=0;
static unsigned Next(){seed=seed*1664525u+1013904223u;return seed;}
static void Check(const char*n,bool ok){++checks;if(!ok){++failures;if(failures<25)printf("FAIL %s\n",n);}}
static void OnUnitLookup(){if(lookupMutation){lookupMutation=0;CvStackingStrengthCache::Invalidate();}}
static void OnLeaf(){++leafCalls;if(throwLeaf)throw 91;if(throwLeafAllocation){throwLeafAllocation=false;throw std::bad_alloc();}if(leafMutation){leafMutation=0;CvStackingStrengthCache::Invalidate();}if(nestLeaf){nestLeaf=false;CvStackingStrengthCache::Scope nested(128);}}
static bool ActualProvider(unsigned int&flags,bool scan){if(scan)++providerCalls;else ++validationCalls;return Baseline::StackPreviewCallbackCapabilities(flags,scan);}
static bool ActualInputs(const vector<const CvUnit*>&roster){vector<CvUnit*>in;for(size_t i=0;i<roster.size();++i)in.push_back(const_cast<CvUnit*>(roster[i]));return Baseline::StackPreviewInputsSupported(in);}
static void Reset(){gameLock=true;MOD_EVENTS_CAN_MOVE_INTO=MOD_EVENTS_AIRLIFT=MOD_EVENTS_SEALIFT=MOD_EVENTS_UNIT_RANGEATTACK=MOD_EVENTS_CITY_BOMBARD=MOD_EVENTS_REBASE=MOD_EVENTS_UNIT_ACTIONS=false;for(int p=0;p<4;++p){players[p]=CvPlayer();players[p].id=players[p].team=p;maps[p]=CvDangerPlots();for(int q=0;q<4;++q){teams[p].open[q]=false;if(p!=q)players[p].enemies.push_back(q);}}}
static void Limits(size_t e,size_t b){Baseline::gStackEntryLimit=Trial::gStackEntryLimit=e;Baseline::gStackKeyPayloadLimit=Trial::gStackKeyPayloadLimit=b;}
struct Entry{int kind,scalar;size_t defender;vector<int>key;vector<pair<int,int> >members;bool operator<(const Entry&o)const{return kind!=o.kind?kind<o.kind:key<o.key;}bool operator==(const Entry&o)const{return kind==o.kind&&scalar==o.scalar&&defender==o.defender&&key==o.key&&members==o.members;}};
struct Snapshot{vector<Entry>entries;vector<vector<int> >queue[2];vector<unsigned long>counters;bool operator==(const Snapshot&o)const{return entries==o.entries&&queue[0]==o.queue[0]&&queue[1]==o.queue[1]&&counters==o.counters;}};
#define SNAPSHOT(name,NS) static Snapshot name(){Snapshot s;for(size_t i=0;i<NS::gIndexed.Capacity();++i){const NS::IndexedStore::Slot&slot=NS::gIndexed.At((int)i);if(!slot.used)continue;Entry e;e.kind=slot.kind;e.scalar=slot.scalar;e.defender=(size_t)slot.defender;e.key.assign(slot.Data(),slot.Data()+slot.keyWords);for(size_t j=0;j<slot.members;++j)e.members.push_back(make_pair(slot.Data()[slot.keyWords+2*j],slot.Data()[slot.keyWords+2*j+1]));s.entries.push_back(e);}for(int kind=0;kind<2;++kind)for(int i=NS::gIndexed.Head(kind);i!=-1;i=NS::gIndexed.NextQueued(i)){const NS::IndexedStore::Slot&slot=NS::gIndexed.At(i);s.queue[kind].push_back(vector<int>(slot.Data(),slot.Data()+slot.keyWords));}sort(s.entries.begin(),s.entries.end());s.counters.push_back(NS::gStackDangerHits);s.counters.push_back(NS::gStackDangerMisses);s.counters.push_back(NS::gStackDangerEvictions);s.counters.push_back(NS::gStackDefenderHits);s.counters.push_back(NS::gStackDefenderMisses);s.counters.push_back(NS::gStackDefenderEvictions);s.counters.push_back(NS::gStackOutcomeBuilds);s.counters.push_back(NS::gStackOutcomeReuses);s.counters.push_back(NS::gStackOutcomeBypasses);s.counters.push_back(NS::gStackPacketHits);s.counters.push_back(NS::gStackPacketBuilds);s.counters.push_back(NS::gStackPacketBypasses);s.counters.push_back((unsigned long)NS::gStackKeyPayloadBytes);s.counters.push_back(NS::gStackInsertBypasses);s.counters.push_back((unsigned long)NS::gStackDangerScratch.state.capacity());s.counters.push_back((unsigned long)NS::gStackPacketScratch.key.state.capacity());s.counters.push_back((unsigned long)NS::gStackPacketScratch.source.capacity());s.counters.push_back((unsigned long)NS::gStackPacketScratch.members.capacity());s.counters.push_back((unsigned long)NS::gStackPacketScratch.value.memberScores.capacity());s.counters.push_back(NS::fixtureContextCalls);return s;}
SNAPSHOT(OldSnapshot,Baseline) SNAPSHOT(NewSnapshot,Trial)
static void Pair(const CvUnit*u,CvPlot*p,const vector<const CvUnit*>&r,const SUnitIDValueContainer&f,const SUnitIDValueContainer&e){bool oldBusy=Baseline::gStackDangerScratchBusy,newBusy=Trial::gStackDangerScratchBusy;unsigned before=leafCalls;int a=Baseline::GetCachedStackDanger(u,p,r,f,e);unsigned oldLeaves=leafCalls-before;before=leafCalls;int b=Trial::GetCachedStackDanger(u,p,r,f,e);Check("scalar/outcome mathematical value exact",a==b);Check("raw leaf graph count exact",oldLeaves==leafCalls-before);Check("exact keys/FIFO/capacity/Context/all work counters",OldSnapshot()==NewSnapshot());Check("packet/key loans restored at return",Baseline::gStackDangerScratchBusy==oldBusy&&Trial::gStackDangerScratchBusy==newBusy&&!Baseline::gStackPacketScratchBusy&&!Trial::gStackPacketScratchBusy);}
struct ForeignArgs{const CvUnit*u;CvPlot*p;const vector<const CvUnit*>*r;};
static DWORD WINAPI Foreign(void*ptr){ForeignArgs*a=(ForeignArgs*)ptr;SUnitIDValueContainer f;unsigned hits=Trial::gStackDangerHits;size_t bytes=Trial::gStackKeyPayloadBytes;Trial::GetCachedStackDanger(a->u,a->p,*a->r,f,f);return hits==Trial::gStackDangerHits&&bytes==Trial::gStackKeyPayloadBytes&&!Trial::gStackPacketScratchBusy?0:1;}
int main(){
 setvbuf(stdout,NULL,_IONBF,0);
 Check("native x86 sizes",sizeof(void*)==4&&sizeof(Baseline::StackDangerPacketBuffer)==sizeof(Trial::StackDangerPacketBuffer)&&sizeof(CvStackingDiagnostics::PlanSampleScope)==32);
 printf("packetBufferBytes=%u packetQueryBytes=%u probeFrameBytes=%u sampleScopeBytes=%u\n",(unsigned)sizeof(Trial::StackDangerPacketBuffer),(unsigned)sizeof(Trial::StackDangerPacketQuery),(unsigned)sizeof(Trial::DestinationKernelProbeFrame),(unsigned)sizeof(CvStackingDiagnostics::PlanSampleScope));
 CvPlot target(0),nearby(1);CvCity city(7,0,&target),enemyCity(8,1,&nearby);CvUnit units[6],actors[9];
 for(int state=0;state<280;++state){Reset();CvDangerPlotContents&c=maps[0].m_DangerPlots[0];c.m_pPlot=&target;c.m_iFogCount=state%5;c.m_iImprovementDamage=state%17;c.m_bFlatPlotDamage=state%2!=0;target.city=state%3==0?&city:NULL;city.hp=20+Next()%280;city.protection=Next()%91;CvStacking::enabled=state%11!=0;CvStacking::selectionEnabled=state%7!=0;vector<const CvUnit*>r;SUnitIDValueContainer f,e;
  for(int i=0;i<6;++i){units[i]=CvUnit(i==0?0:i==1?-8:10+i,0,&target);units[i].hp=25+Next()%100;units[i].maxHP=units[i].hp+Next()%50;units[i].ranged=Next()%2!=0;units[i].defense=10+Next()%70;units[i].anti=Next()%2!=0;units[i].flankTarget=Next()%2!=0;units[i].terrainIgnore=Next()%2!=0;units[i].featureIgnore=Next()%2!=0;units[i].chance=Next()%151;units[i].domain=state%2&&i==5?DOMAIN_AIR:DOMAIN_LAND;players[0].units[units[i].id]=&units[i];players[0].possible.push_back(make_pair(units[i].id,0));if(i<5)r.push_back(&units[i]);f.SetValue(units[i].id,(int)(Next()%141)-10);}city.garrison=&units[state%5];if(state%4==0)r.push_back(&units[1]);if(state%7==0)reverse(r.begin(),r.end());
  for(int i=0;i<9;++i){actors[i]=CvUnit(i%5,1+i%2,&nearby);actors[i].ranged=Next()%2!=0;actors[i].domain=state%2&&i%4==0?DOMAIN_AIR:DOMAIN_LAND;actors[i].flank=Next()%2!=0;actors[i].aoe=Next()%4;actors[i].collateralLimit=Next()%5;actors[i].evasion=Next()%101;actors[i].strength=30+Next()%80;players[actors[i].owner].units[actors[i].id]=&actors[i];c.m_apUnits.push_back(make_pair(actors[i].owner,actors[i].id));e.SetValue(actors[i].id,(int)(Next()%71));}players[1].cities[8]=&enemyCity;c.m_apCities.push_back(make_pair(1,8));if(state%5==0)c.m_apCities.push_back(make_pair(1,8));
  CvStackingStrengthCache::Scope proof(128,ActualProvider);bool supported=ActualInputs(r);Baseline::StackForecastScope old(supported);Trial::StackForecastScope now(supported);Limits(5+state%6,500+state%8*250);Baseline::fixtureContextCalls=Trial::fixtureContextCalls=0;
  for(int q=0;q<18;++q)Pair(&units[q%6],&target,r,f,e);
  {Baseline::StackDangerOutcomeBatch oldBatch(&target,r,f,e);Trial::StackDangerOutcomeBatch newBatch(&target,r,f,e);for(int q=0;q<12;++q){int a=Baseline::GetCachedStackDanger(&units[q%6],&target,r,f,e,&oldBatch),b=Trial::GetCachedStackDanger(&units[q%6],&target,r,f,e,&newBatch);Check("explicit outcome-batch path exact",a==b&&OldSnapshot()==NewSnapshot());}}
 }
 printf("randomized graphs completed checks%u failures%u\n",checks,failures);
 Reset();target.city=NULL;CvStacking::enabled=CvStacking::selectionEnabled=true;vector<const CvUnit*>r;SUnitIDValueContainer none;for(int i=0;i<5;++i){units[i]=CvUnit(10+i,0,&target);units[i].hp=units[i].maxHP=500;players[0].units[10+i]=&units[i];r.push_back(&units[i]);}CvDangerPlotContents&c=maps[0].m_DangerPlots[0];c.m_pPlot=&target;actors[0]=CvUnit(44,1,&nearby);actors[0].ranged=true;actors[0].collateralLimit=0;players[1].units[44]=&actors[0];c.m_apUnits.push_back(make_pair(1,44));
 {CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(true);Trial::StackForecastScope now(true);Baseline::fixtureContextCalls=Trial::fixtureContextCalls=0;Pair(r[0],&target,r,none,none);unsigned hits=Trial::gStackDangerHits;Pair(r[0],&target,r,none,none);Check("warm hit remains in hot caller",Trial::gStackDangerHits==hits+1);Baseline::gStackDangerScratchBusy=Trial::gStackDangerScratchBusy=true;Pair(r[0],&target,r,none,none);Baseline::gStackDangerScratchBusy=Trial::gStackDangerScratchBusy=false;
  {Baseline::StackForecastScope nestedOld(true);Trial::StackForecastScope nestedNew(true);Baseline::fixtureContextCalls=Trial::fixtureContextCalls=0;Pair(r[0],&target,r,none,none);}
  ForeignArgs a={r[0],&target,&r};HANDLE h=CreateThread(NULL,0,Foreign,&a,0,NULL);Check("foreign thread created",h!=NULL);if(h){Check("foreign bounded",WaitForSingleObject(h,5000)==WAIT_OBJECT_0);DWORD status=1;GetExitCodeThread(h,&status);CloseHandle(h);Check("foreign no owner cache mutation",status==0);}
 }
 // Warm scalar-hit and native miss/unwind diagnostic/query teardown order.
 lifecycle.reserve(32);
 for(int mode=0;mode<3;++mode){CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(mode==0);Trial::StackForecastScope now(mode==0);if(mode==0){Baseline::GetCachedStackDanger(r[0],&target,r,none,none);Trial::GetCachedStackDanger(r[0],&target,r,none,none);}vector<int>a,b;traceLifecycle=true;lifecycle.clear();throwLeaf=mode==2;try{Baseline::GetCachedStackDanger(r[0],&target,r,none,none);}catch(int){}a=lifecycle;lifecycle.clear();try{Trial::GetCachedStackDanger(r[0],&target,r,none,none);}catch(int){}b=lifecycle;throwLeaf=false;traceLifecycle=false;Check("sampler/packet/probe/key/query destructor trace identical",a==b);if(mode!=0){vector<int>expected;expected.push_back(100);expected.push_back(200);expected.push_back(101);expected.push_back(201);expected.push_back(301);expected.push_back(500);expected.push_back(600);expected.push_back(300);expected.push_back(400);Check("miss/unwind keeps exact old teardown sequence",b==expected);}else{vector<int>expected;expected.push_back(100);expected.push_back(200);expected.push_back(300);expected.push_back(400);Check("hit never constructs miss-only locals",b==expected);}}
 // Identical callback epoch drift is injected independently at each leaf.
 printf("warm/busy/nested/foreign completed\n");
 for(int mode=0;mode<3;++mode){printf("leaf callback mode%d\n",mode);CvStackingStrengthCache::Scope proof(128,ActualProvider);Baseline::StackForecastScope old(false);Trial::StackForecastScope now(false);leafMutation=mode==0;nestLeaf=mode==1;throwLeaf=mode==2;bool aThrow=false,bThrow=false;int a=0,b=0;try{a=Baseline::GetCachedStackDanger(r[0],&target,r,none,none);}catch(int v){aThrow=v==91;}leafMutation=mode==0;nestLeaf=mode==1;try{b=Trial::GetCachedStackDanger(r[0],&target,r,none,none);}catch(int v){bThrow=v==91;}throwLeaf=false;Check("callback/nested/exception result parity",aThrow==bThrow&&(aThrow||a==b));Check("exception destroys packet before caller key loan",!Baseline::gStackPacketScratchBusy&&!Trial::gStackPacketScratchBusy&&!Baseline::gStackDangerScratchBusy&&!Trial::gStackDangerScratchBusy);}
 // Original allocation faults still unwind both loans. Turn off actual packet
 // preallocation so the first native leaf allocation is the failing seam.
 for(int pass=0;pass<2;++pass){printf("allocation callback pass%d\n",pass);CvStackingStrengthCache::Scope proof(128,ActualProvider);bool threw=false;failAllocation=true;try{if(pass==0){Baseline::StackForecastScope f(false);Baseline::GetCachedStackDanger(r[0],&target,r,none,none);}else{Trial::StackForecastScope f(false);Trial::GetCachedStackDanger(r[0],&target,r,none,none);}}catch(std::bad_alloc&){threw=true;}failAllocation=false;Check("native allocation fault propagated",threw);Check("allocation fault releases packet/key owner loans",!Baseline::gStackDangerScratchBusy&&!Trial::gStackDangerScratchBusy&&!Baseline::gStackPacketScratchBusy&&!Trial::gStackPacketScratchBusy);}
 for(int pass=0;pass<2;++pass){CvStackingStrengthCache::Scope proof(128,ActualProvider);bool threw=false;throwLeafAllocation=true;try{if(pass==0){Baseline::StackForecastScope f(true);Baseline::GetCachedStackDanger(r[0],&target,r,none,none);}else{Trial::StackForecastScope f(true);Trial::GetCachedStackDanger(r[0],&target,r,none,none);}}catch(std::bad_alloc&){threw=true;}throwLeafAllocation=false;Check("owned packet leaf allocation exception propagated",threw);Check("owned packet exception unwinds miss and caller loans",!Baseline::gStackDangerScratchBusy&&!Trial::gStackDangerScratchBusy&&!Baseline::gStackPacketScratchBusy&&!Trial::gStackPacketScratchBusy);}
 Check("real capability module exercised",providerCalls>0&&validationCalls>0);Check("outer scratch/payload released",!Baseline::gStackDangerScratchBusy&&!Trial::gStackDangerScratchBusy&&Baseline::gStackKeyPayloadBytes==0&&Trial::gStackKeyPayloadBytes==0);
 printf("MISS OUTLINE ACTUAL94: %u checks, %u failures; no native speed claim\n",checks,failures);return failures?1:0;
}
'''
code=scope['headers']+scope['strength_header']+scope['strength_module']+scope['native_services']+base+engine+services+implementation+tests
(OUT/'test.cpp').write_text(code,encoding='utf-8',newline='\n')
report=dict(proof,production_bound=args.production,actual_whole_hashes=actual_hashes,unchanged_dependencies={n:hashlib.sha256(s.encode()).hexdigest() for n,s in source.items() if n!='CvTacticalAI.cpp'},complete_math_bindings=scope['math_bindings'],fixture_sha256=hashlib.sha256(code.encode()).hexdigest(),scope='actual94 Context/provider/strength/cache/backend/packet/selectors/collateral/danger math; deterministic engine services; no native run')
(OUT/'proof.json').write_text(json.dumps(report,indent=2)+'\n')
if args.emit_only:print(OUT/'test.cpp');sys.exit(0)
vc=ROOT/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=ROOT/'work/toolchain/sdk/windows';env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(ROOT/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(ROOT/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for name in ('CL','_CL_','LINK'):env.pop(name,None)
build=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/GS','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0','/FAs','/Fa'+str(OUT/'test.asm'),str(OUT/'test.cpp'),'/Fo'+str(OUT/'test.obj'),'/Fe'+str(OUT/'test.exe')],cwd=OUT,env=env,capture_output=True,text=True,timeout=90);(OUT/'compile.log').write_text(build.stdout+build.stderr)
if build.returncode:print(build.stdout+build.stderr);sys.exit(build.returncode)
run=subprocess.run([str(OUT/'test.exe')],cwd=OUT,capture_output=True,text=True,timeout=45);print(run.stdout+run.stderr,end='');report.update(compile_returncode=build.returncode,test_returncode=run.returncode,output=run.stdout+run.stderr);(OUT/'result.json').write_text(json.dumps(report,indent=2)+'\n');sys.exit(run.returncode)
