"""Stage DLL93 resident even-key elision; no production application/build/game."""
from pathlib import Path
import argparse,difflib,hashlib,json,re,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];parser=argparse.ArgumentParser();parser.add_argument('--control',default='e38b19798');parser.add_argument('--output',default='work/resident-key-elision-staged');options=parser.parse_args();BASE=options.control;PATH='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp';OUT=ROOT/options.output;OUT.mkdir(exist_ok=True)
old=subprocess.check_output(['git','show',BASE+':'+PATH],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n');new=old;changes=[]
def function(s,sig):
 a=s.index(sig);b=s.index('{',a)+1;d=1
 while d:d+=(s[b]=='{')-(s[b]=='}');b+=1
 return s[a:b]
def once(a,b):
 global new
 assert new.count(a)==1,(a[:120],new.count(a));new=new.replace(a,b,1);changes.append((a,b))
subprocess.run([sys.executable,str(ROOT/'work/resident-scalar-handles-stage.py'),'--pinned'],check=True,capture_output=True)
oldclass=(ROOT/'work/resident-scalar-handles/control-IndexedStore.h').read_text(encoding='utf-8')
newclass=(ROOT/'work/resident-scalar-handles/IndexedStore.h').read_text(encoding='utf-8').replace('No serial is reset by Clear/Release/reInitialize.','No lifetime identity is reused by Clear/Release/reInitialize.')
assert oldclass in old;once(oldclass,newclass)
once('static unsigned long gStackDangerHits = 0, gStackDangerMisses = 0;',
 'static unsigned long gStackDangerHits = 0, gStackDangerMisses = 0;\nstatic unsigned long gResidentHits=0,gResidentCaptures=0,gResidentRejects=0,gPreparedBuilds=0,gPreparedReuses=0;')
once('  gStackDangerHits = gStackDangerMisses = gStackDefenderHits = gStackDefenderMisses = 0;',
 '  gStackDangerHits = gStackDangerMisses = gStackDefenderHits = gStackDefenderMisses = 0;\n  gResidentHits=gResidentCaptures=gResidentRejects=gPreparedBuilds=gPreparedReuses=0;')
lookup=function(new,'static bool FindStackDangerForecastScalar(')
edited=lookup.replace('int& result)','int& result,IndexedStore::ScalarHandle* certificate=NULL)',1)
edited=edited.replace('result=gIndexed.At(handle).scalar;return true;','result=gIndexed.At(handle).scalar;if(certificate)gIndexed.CaptureScalarHandle(handle,*certificate);return true;',1)
assert edited!=lookup;once(lookup,edited)
fragment=(ROOT/'work/resident-key-elision-fragment.cpp').read_text(encoding='utf-8-sig');helpers=(ROOT/'work/resident-key-elision-helpers.cpp').read_text(encoding='utf-8-sig')
once('static int GetCachedStackDanger(',fragment+'\nstatic int GetCachedStackDanger(')
body=function(new,'static int GetCachedStackDanger(')
start=body.index('  key.state.push_back(unit->GetID());');end=body.index('  cacheable = StackForecastContext()',start)
build='''  const int fixed[4]={unit->GetID(),plot->GetPlotIndex(),friendlyDamage.GetValue(unit->GetID()),CvStacking::GetCityProtection(plot->getPlotCity())};
  const bool canonical=!plot->isCity()&&CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled,1)!=0;
  const bool residentPrepared=PrepareResidentScalarKey(unit,plot,candidates,friendlyDamage,enemyDamage,fixed,canonical,query.scratch!=NULL,key);
  if(!residentPrepared)
  {
   for(int i=0;i<4;++i)key.state.push_back(fixed[i]);
   AppendStackCandidates(key,candidates,friendlyDamage,canonical);
   AppendStackDamageProjected(key,enemyDamage,unit,plot);
  }
'''
edited=body[:start]+build+body[end:]
needle='  ObserveDestinationDangerKey(unit,plot,candidates,friendlyDamage,key,cacheable); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY'
assert edited.count(needle)==1
edited=edited.replace(needle,'''  int residentResult=0;
  if(cacheable&&residentPrepared&&ReadPreparedResidentScalar(residentResult))
  {++gStackDangerHits;return residentResult;}
  if(residentPrepared)CompletePreparedResidentScalarKey(key);
'''+needle,1)
edited=edited.replace('  int cachedResult=0;','  int cachedResult=0;IndexedStore::ScalarHandle captured;',1)
edited=edited.replace('FindStackDangerForecastScalar(key,cachedResult))','FindStackDangerForecastScalar(key,cachedResult,query.scratch&&gResidentArrivalRequest&&HasResidentScalarCaptureContext(unit,plot,candidates,friendlyDamage,true)?&captured:NULL))',1)
edited=edited.replace('   ++gStackDangerHits;\n   return cachedResult;',
 '   ++gStackDangerHits;\n   CaptureResidentScalarKey(unit,plot,candidates,friendlyDamage,fixed,canonical,query.scratch!=NULL,key,captured);\n   return cachedResult;',1)
once(body,edited)
once('// No danger result or serialized key is retained. Borrowed query ownership is','// No danger result is retained. An optional resident even-key certificate uses\n// the existing table result only while its slot lifetime remains valid. Borrowed query ownership is')
once(' VirtualFriendlyStackBuffer base;\n ParentStackPreparationCell():', ' VirtualFriendlyStackBuffer base;\n ResidentScalarCertificate resident;\n ParentStackPreparationCell():')
once('{cells[i].base.candidates.clear();cells[i].base.damage.clear();cells[i].plotIndex=-1;}',
 '{cells[i].resident.valid=false;cells[i].base.candidates.clear();cells[i].base.damage.clear();cells[i].plotIndex=-1;}')
once('cells[i].base.damage.m_aExtraStorage.capacity()*sizeof(SUnitIDValueContainer::value_type);',
 'cells[i].base.damage.m_aExtraStorage.capacity()*sizeof(SUnitIDValueContainer::value_type)+cells[i].resident.Bytes();')
once('retainedBytes-=CellBytes(i);cells[i].base.release();','retainedBytes-=CellBytes(i);cells[i].base.release();cells[i].resident.Release();')
once('for(size_t i=0;i<MAX_CELLS;++i) cells[i].base.release();',
 'for(size_t i=0;i<MAX_CELLS;++i) {cells[i].base.release();cells[i].resident.Release();}')
once(' void Release(){ReleasePayload();busy=false;}', ''' void DiscardResidentPayload()
 {
  for(size_t i=0;i<MAX_CELLS;++i){retainedBytes-=cells[i].resident.Bytes();cells[i].resident.Release();}
 }
 void Release(){ReleasePayload();busy=false;}''')
once('    GetVirtualFriendlyStack(parent,plot,NULL,0,cell.base.candidates,cell.base.damage);',
 '    ++gPreparedBuilds;\n    GetVirtualFriendlyStack(parent,plot,NULL,0,cell.base.candidates,cell.base.damage);')
# Warm reuse counts attempts, not guaranteed successful materializations.
once('  if(lo<storage.count&&storage.lookup[lo].first==index) cellIndex=storage.lookup[lo].second;',
 '  if(lo<storage.count&&storage.lookup[lo].first==index) {cellIndex=storage.lookup[lo].second;++gPreparedReuses;}')
once('    if(storage.RetainedBytes()>gStackKeyPayloadLimit)\n    {storage.ReleasePayload();disabled=true;return false;}',
 '    if(storage.RetainedBytes()>gStackKeyPayloadLimit)storage.DiscardResidentPayload();\n    if(storage.RetainedBytes()>gStackKeyPayloadLimit)\n    {storage.ReleasePayload();disabled=true;return false;}')
once('static void MarkParentStackPreparationChild(',helpers+'\nstatic void MarkParentStackPreparationChild(')
body=function(new,'static int GetUnitDangerForPlot(')
needle='iDanger = GetCachedStackDanger(pUnit, pPlot, stack.candidates, stack.damage, assumedPosition.GetUnitDamageDealt());'
assert body.count(needle)==2
edited=body.replace(needle,'ResidentArrivalRequest residentArrival(pUnit,pPlot,iSelfDamage,assumedPosition,stack.candidates,stack.damage);\n    '+needle)
once(body,edited)
once('callbackSuspensions=%lu forecastBackend=%s forecastEstimatedBytes=%u; phase tick timing',
 'callbackSuspensions=%lu forecastBackend=%s forecastEstimatedBytes=%u residentHits=%lu residentCaptures=%lu residentRejects=%lu prepBuildAttempts=%lu prepReuseAttempts=%lu; phase tick timing')
once('gUseIndexed?"indexed":"legacy",(unsigned int)EstimatedStackForecastBytes());',
 'gUseIndexed?"indexed":"legacy",(unsigned int)EstimatedStackForecastBytes(),gResidentHits,gResidentCaptures,gResidentRejects,gPreparedBuilds,gPreparedReuses);')
restored=new
for a,b in reversed(changes):assert restored.count(b)==1,(b[:60],restored.count(b));restored=restored.replace(b,a,1)
assert restored==old
(OUT/'control.cpp').write_text(old,encoding='utf-8');(OUT/'CvTacticalAI.cpp').write_text(new,encoding='utf-8')
(OUT/'resident-key.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/'+PATH,tofile='b/'+PATH)),encoding='utf-8')
assert function(new,'static void AppendStackDamageProjected(')==function(old,'static void AppendStackDamageProjected(')
if 'static __declspec(noinline) int ResolveStackDangerForecastMiss(' in old:
 assert function(new,'static __declspec(noinline) int ResolveStackDangerForecastMiss(')==function(old,'static __declspec(noinline) int ResolveStackDangerForecastMiss(')
record=new[new.index('CvStackingDiagnostics::Record(1,ePlayer,"PLAN_PERF"'):]
record=record[:record.index(');')+2]
fmt=re.search(r'"PLAN_PERF","([^"\n]*)"',record).group(1)
conversions=re.findall(r'%(?:I64)?(?:l)?[duis]',fmt)
worst=re.sub(r'%(?:I64)?(?:l)?[duis]',lambda m:'indexed' if m.group()=='%s' else ('-2147483648' if m.group() in ('%d','%i') else '4294967295'),fmt)
arguments=record[record.index(',\n')+2:-2];depth=0;arity=1
for char in arguments:
 if char=='(':depth+=1
 elif char==')':depth-=1
 elif char==',' and depth==0:arity+=1
assert len(conversions)==arity,(len(conversions),arity)
assert len(worst)<2048,len(worst)
proof=dict(control=BASE,original_sha256=hashlib.sha256(old.encode()).hexdigest(),candidate_sha256=hashlib.sha256(new.encode()).hexdigest(),whole_reverse_exact=True,original_projection_body_unchanged=True,original_miss_helper_unchanged=True,formatter_arity=arity,formatter_worst_bytes=len(worst),production_untouched=True,scope='Existing resident even-key equality shortcut from qualified Parent UnitDanger arrivals only; exact current suffix and original fixed/Context gates; no new result table/FIFO/budget/search policy.')
(OUT/'manifest.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8');print(json.dumps(proof))
