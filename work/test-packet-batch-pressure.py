"""Actual-source original77/79 vs staged local-batch packet pressure policies.

Prerequisites: stage-packet-batch-pressure.py, the tracked whole packet fixture
and its extraction services. No production edits/native timing claim.
"""
from pathlib import Path
import ast,hashlib,json,os,subprocess,sys
root=Path(__file__).resolve().parents[1];out=root/'work/packet-batch-pressure-regression';out.mkdir(exist_ok=True);production='--production' in sys.argv
stage=root/'work/packet-batch-pressure-candidate';manifest=json.loads((stage/'manifest.json').read_text())
original=subprocess.check_output(['git','show',manifest['control']+':CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'],cwd=root).decode('utf-8-sig').replace('\r\n','\n')
assert hashlib.sha256(original.encode()).hexdigest()==manifest['original_sha256']
variants={k:(stage/(k+'.cpp')).read_text(encoding='utf-8-sig') for k in manifest['candidate_sha256']}
for name,text in variants.items():assert hashlib.sha256(text.encode()).hexdigest()==manifest['candidate_sha256'][name]
bound_hashes={}
if production:
 expected=json.loads((root/'work/shared-packet-candidate/manifest.json').read_text())['candidate_sha256']
 expected['CvTacticalAI.cpp']=manifest['candidate_sha256']['ready-and-local-no-seed']
 for name,digest in expected.items():
  text=(root/'CvGameCoreDLL_Expansion2'/name).read_text(encoding='utf-8-sig');bound_hashes[name]=hashlib.sha256(text.encode()).hexdigest()
  assert bound_hashes[name]==digest,'Current3file production does not match reviewed pressureB: '+name
 variants['ready-and-local-no-seed']=(root/'CvGameCoreDLL_Expansion2/CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
# Execute only the tracked generation prefix. The whole original math/module
# extractor remains pinned77, and the all79 control is separately pinned79.
generator=(root/'work/test-shared-packet-native-stage.py').read_text(encoding='utf-8-sig')
prefix=generator[:generator.index("\ntests=r'''")]
scope={'__file__':str(root/'work/test-shared-packet-native-stage.py')};arguments=sys.argv
try:
 # The reused generator binds its own historical79 stage, not this policyB.
 # Current adoption is checked above; never ask the old fixture to compare
 # new production against its intentionally unchanged old-stage hashes.
 sys.argv=[arg for arg in arguments if arg!='--production']
 exec(compile(prefix,'actual packet pressure source extraction','exec'),scope)
finally:sys.argv=arguments
cache_module=scope['cache_module'];base=scope['base'];headers=scope['headers'];services=scope['services'];common=scope['common']
assert scope['new']==original,'Reviewed79 stage changed; revisit baseline input bindings'
implementation=common+'\nnamespace Control{\n'+cache_module(scope['old'],False)+'\n}\n'
implementation+='\nnamespace Original79{\n'+cache_module(original,True)+'\n}\n'
implementation+='\nnamespace ReadyOnly{\n'+cache_module(variants['ready-only'],True)+'\n}\n'
implementation+='\nnamespace Trial{\n'+cache_module(variants['ready-and-local-no-seed'],True)+'\n}\n'
original_tests=None
for node in ast.parse(generator).body:
 if isinstance(node,ast.Assign) and any(isinstance(x,ast.Name) and x.id=='tests' for x in node.targets):original_tests=ast.literal_eval(node.value)
assert original_tests
original_tests=original_tests.replace('static void OnDescriptorCopy(){','static unsigned descriptorCalls=0;static void OnDescriptorCopy(){++descriptorCalls;',1)
extra=r'''
struct PressureResult{unsigned hits,misses,evictions,packetHits,packetBuilds,outcomeBuilds,outcomeReuses,oddNodes,descriptors,leaves;size_t bytes;PressureResult():hits(0),misses(0),evictions(0),packetHits(0),packetBuilds(0),outcomeBuilds(0),outcomeReuses(0),oddNodes(0),descriptors(0),leaves(0),bytes(0){}};
#define CACHE_ADAPTER(NAME,NS) struct NAME{typedef NS::StackForecastScope Scope;typedef NS::StackDangerOutcomeBatch Batch;static int Get(const CvUnit*u,const CvPlot*p,const vector<const CvUnit*>&r,const SUnitIDValueContainer&f,const SUnitIDValueContainer&e,Batch*b=NULL){return NS::GetCachedStackDanger(u,p,r,f,e,b);}static void Limits(size_t n,size_t bytes){NS::gStackEntryLimit=n;NS::gStackKeyPayloadLimit=bytes;}static PressureResult Stats(){PressureResult v;v.hits=NS::gStackDangerHits;v.misses=NS::gStackDangerMisses;v.evictions=NS::gStackDangerEvictions;v.outcomeBuilds=NS::gStackOutcomeBuilds;v.outcomeReuses=NS::gStackOutcomeReuses;v.bytes=NS::gStackKeyPayloadBytes;return v;}static unsigned Odd(){unsigned n=0;for(NS::StackDangerForecasts::const_iterator i=NS::gStackDangerForecasts.begin();i!=NS::gStackDangerForecasts.end();++i)if(i->first.state.size()%2)++n;return n;}static void Invariant(){size_t bytes=0;for(NS::StackDangerForecasts::const_iterator i=NS::gStackDangerForecasts.begin();i!=NS::gStackDangerForecasts.end();++i)bytes+=NS::StackDangerForecastPayloadBytes(*i);for(NS::StackDefenderForecasts::const_iterator i=NS::gStackDefenderForecasts.begin();i!=NS::gStackDefenderForecasts.end();++i)bytes+=i->first.state.capacity()*sizeof(int);Check("pressure actual capacity/FIFO remains bounded",bytes==NS::gStackKeyPayloadBytes&&bytes<=NS::gStackKeyPayloadLimit&&NS::gStackDangerForecasts.size()==NS::gStackDangerOrder.size()&&NS::gStackDangerForecasts.size()+NS::gStackDefenderForecasts.size()<=NS::gStackEntryLimit);}};
CACHE_ADAPTER(Cache79,Original79)
CACHE_ADAPTER(CacheReady,ReadyOnly)
CACHE_ADAPTER(CacheNoSeed,Trial)
template<class C> PressureResult RunPressure(const vector<const CvUnit*>&r,const CvPlot*p,size_t entries){typename C::Scope scope;C::Limits(entries,4000);PressureResult result;unsigned startLeaves=leafCalls,startDescriptors=descriptorCalls;SUnitIDValueContainer empty;
 for(int round=0;round<20;++round){SUnitIDValueContainer f;f.SetValue(r[0]->GetID(),round+1);typename C::Batch batch(p,r,f,empty);
  for(int q=0;q<5;++q){trace.clear();int expected=maps[0].m_DangerPlots[0].GetStackDanger(r[q],r,f,empty);vector<int>originalTrace=trace;trace.clear();unsigned before=leafCalls;int actual=C::Get(r[q],p,r,f,empty,&batch);result.leaves+=leafCalls-before;Check("all79 and staged local batch numbers match original leaf",actual==expected);Check("each performed strike graph equals original single leaf",trace.empty()||trace==originalTrace);result.oddNodes+=C::Odd();C::Invariant();}
 }
 PressureResult stats=C::Stats();result.hits=stats.hits;result.misses=stats.misses;result.evictions=stats.evictions;result.outcomeBuilds=stats.outcomeBuilds;result.outcomeReuses=stats.outcomeReuses;result.bytes=stats.bytes;result.descriptors=descriptorCalls-startDescriptors;return result;
}
template<class C> void TestReadyBatchNoMetadata(const vector<const CvUnit*>&r,const CvPlot*p){typename C::Scope scope;C::Limits(12,4000);SUnitIDValueContainer none;typename C::Batch b(p,r,none,none);int original=0;Check("pressure original local batch can be primed",b.TryGet(r[0],p,r,none,none,original)&&b.ready);unsigned descriptors=descriptorCalls,before=leafCalls;for(int i=0;i<5;++i)Check("ready batch uses original queried result",C::Get(r[i],p,r,none,none,&b)==maps[0].m_DangerPlots[0].GetStackDanger(r[i],r,none,none));Check("ready batch performs no packet metadata",descriptorCalls==descriptors&&C::Odd()==0&&leafCalls-before==5);C::Invariant();}
template<class C> void TestColdExistingPacket(const vector<const CvUnit*>&r,const CvPlot*p){typename C::Scope scope;C::Limits(12,4000);SUnitIDValueContainer none;C::Get(r[0],p,r,none,none);typename C::Batch b(p,r,none,none);unsigned before=leafCalls;int value=C::Get(r[1],p,r,none,none,&b);Check("cold batch keeps existing global packet reuse",leafCalls==before&&!b.ready&&value==maps[0].m_DangerPlots[0].GetStackDanger(r[1],r,none,none));C::Invariant();}
template<class C> void TestBatchGuards(const vector<const CvUnit*>&r,const CvPlot*p){SUnitIDValueContainer none;
 {typename C::Scope scope;C::Limits(12,4000);typename C::Batch b(p,r,none,none);C::Get(r[0],p,r,none,none,&b);CvStackingStrengthCache::Invalidate();unsigned before=leafCalls;int got=C::Get(r[1],p,r,none,none,&b);Check("ready stale scene rebuilds once and binds new scene",leafCalls==before+1&&b.ready&&b.scene==CvStackingStrengthCache::SceneEpoch()&&got==maps[0].m_DangerPlots[0].GetStackDanger(r[1],r,none,none));C::Invariant();}
 {typename C::Scope scope;C::Limits(12,4000);typename C::Batch b(p,r,none,none);C::Get(r[0],p,r,none,none,&b);maps[0].m_bDirty=true;unsigned before=leafCalls,refresh=refreshCalls;C::Get(r[1],p,r,none,none,&b);Check("ready dirty refresh remains once and one leaf",refreshCalls==refresh+1&&leafCalls==before+1);C::Invariant();}
 {typename C::Scope scope;C::Limits(12,4000);vector<const CvUnit*>same=r;typename C::Batch b(p,same,none,none);int ignored=0;b.TryGet(r[0],p,same,none,none,ignored);unsigned before=leafCalls;C::Get(r[1],p,r,none,none,&b);Check("ready mismatched lexical references preserve original fallback",leafCalls==before+1&&!b.ready);C::Invariant();}
 {typename C::Scope scope;C::Limits(12,4000);typename C::Batch b(p,r,none,none);C::Get(r[0],p,r,none,none,&b);MOD_EVENTS_CAN_MOVE_INTO=true;unsigned before=leafCalls;C::Get(r[1],p,r,none,none,&b);Check("ready scripted movement keeps original single fallback",leafCalls==before+1&&!b.ready);MOD_EVENTS_CAN_MOVE_INTO=false;C::Invariant();}
 {typename C::Scope scope;C::Limits(12,4000);typename C::Batch b(p,r,none,none);C::Get(r[0],p,r,none,none,&b);CvDangerPlotContents&contents=maps[0].m_DangerPlots[0];int oldFog=contents.m_iFogCount;contents.m_iFogCount+=9;int expected=contents.GetStackDanger(r[1],r,none,none);unsigned before=leafCalls;int got=C::Get(r[1],p,r,none,none,&b);Check("ready batch still extracts live no-epoch fog hazard",got==expected&&leafCalls==before);contents.m_iFogCount=oldFog;C::Invariant();}
}
static void RunPressureChecks(const vector<const CvUnit*>&r,const CvPlot*p){
 TestReadyBatchNoMetadata<CacheReady>(r,p);TestReadyBatchNoMetadata<CacheNoSeed>(r,p);TestColdExistingPacket<CacheReady>(r,p);TestColdExistingPacket<CacheNoSeed>(r,p);TestBatchGuards<Cache79>(r,p);TestBatchGuards<CacheReady>(r,p);TestBatchGuards<CacheNoSeed>(r,p);
 for(size_t entries=2;entries<=8;entries+=3){PressureResult old=RunPressure<Cache79>(r,p,entries),ready=RunPressure<CacheReady>(r,p,entries),noSeed=RunPressure<CacheNoSeed>(r,p,entries);Check("pressure variant reduces ready packet metadata",ready.descriptors<old.descriptors&&noSeed.descriptors<=ready.descriptors);Check("new local batch does not seed odd result nodes",noSeed.oddNodes==0&&ready.oddNodes>0);Check("pressure same simulation count for immutable batch loops",old.leaves==ready.leaves&&ready.leaves==noSeed.leaves);Check("same entry budget fewer packet FIFO evictions",ready.evictions<=old.evictions&&noSeed.evictions<=ready.evictions);
  printf("BATCH_PRESSURE entries=%u original79 evictions=%u descriptors=%u leaves=%u; ready-only evictions=%u descriptors=%u leaves=%u; no-seed evictions=%u descriptors=%u leaves=%u\n",(unsigned)entries,old.evictions,old.descriptors,old.leaves,ready.evictions,ready.descriptors,ready.leaves,noSeed.evictions,noSeed.descriptors,noSeed.leaves);
 }
}
'''
insert=original_tests.index('int main(){')
tests=original_tests[:insert]+extra+'\n'+original_tests[insert:]
anchor=' Check("outer scope releases native packet scratch"'
assert tests.count(anchor)==1
tests=tests.replace(anchor,' RunPressureChecks(r,&target);\n'+anchor,1)
code=headers+base+services+implementation+tests;(out/'test.cpp').write_text(code,encoding='utf-8')
if '--emit-only' in sys.argv:print('Actual pressure fixture emitted without compilation');sys.exit(0)
vc=root/'work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0';sdk=root/'work/toolchain/sdk/windows'
env=os.environ.copy();env['PATH']=str(vc/'Vc7/bin')+';'+str(vc/'Common7/IDE')+';'+env.get('PATH','');env['INCLUDE']=str(root/'work/toolchain/sdk/vc9/include')+';'+str(sdk/'Include');env['LIB']=str(root/'work/toolchain/sdk/vc9/lib')+';'+str(sdk/'Lib')
for key in ('CL','_CL_','LINK'):env.pop(key,None)
built=subprocess.run([str(vc/'Vc7/bin/cl.exe'),'/nologo','/EHsc','/MT','/O2','/Z7','/D_SECURE_SCL=0','/D_HAS_ITERATOR_DEBUGGING=0',str(out/'test.cpp'),'/Fe'+str(out/'test.exe')],cwd=out,env=env,capture_output=True,text=True,timeout=90)
(out/'compile.log').write_text(built.stdout+built.stderr)
if built.returncode:print(built.stdout+built.stderr);sys.exit(built.returncode)
run=subprocess.run([str(out/'test.exe')],cwd=out,capture_output=True,text=True,timeout=40);print(run.stdout+run.stderr,end='')
(out/'result.json').write_text(json.dumps(dict(returncode=run.returncode,output=run.stdout+run.stderr,
 control79=manifest['control'],original79_sha256=manifest['original_sha256'],candidate_sha256=manifest['candidate_sha256'],
 fixture_sha256=hashlib.sha256(code.encode()).hexdigest(),production_untouched=True,
 bound_current_production=production,actual_current_source_sha256=bound_hashes,
 scope='Actual77 scalar original plus complete79 and staged pressure wrappers/cache/storage/batch/math under deterministic engine services. Existing packet negative/FIFO/alias/callback tests plus exact ready/cold-batch and entry-pressure loops. No native ROI claim.'),indent=2));sys.exit(run.returncode)
