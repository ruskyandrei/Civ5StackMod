"""Compose WORK-ONLY shared packet stage from frozen DLL77; never apply/build."""
from pathlib import Path
import difflib,hashlib,json,re,subprocess
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/shared-packet-candidate';out.mkdir(exist_ok=True)
control='cf8f842e2733841255a1d5bc741e4d95a387299b';names=['CvTacticalAI.cpp','CvDangerPlots.cpp','CvDangerPlots.h']
old={n:subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/'+n],cwd=root).decode('utf-8-sig').replace('\r\n','\n') for n in names}
new=dict(old);new['CvTacticalAI.cpp']=(root/'work/shared-packet-storage-staged/CvTacticalAI.cpp').read_text(encoding='utf-8-sig')
def once(text,before,after):
 assert text.count(before)==1,before[:100];return text.replace(before,after,1)
def function(text,start):
 a=text.index(start);b=text.index('{',a)+1;depth=1
 while depth:depth+=(text[b]=='{')-(text[b]=='}');b+=1
 return text[a:b]
buffer=(root/'work/shared-packet-query-buffer.cpp').read_text(encoding='utf-8-sig')
helpers=(root/'work/shared-packet-native-helpers.cpp').read_text(encoding='utf-8-sig')
buffer=buffer.replace('// WORK-ONLY native staging fragment; inserted before StackForecastScope.','// Warmed owned packet query storage; nested/foreign calls retain private fallback.')
helpers=helpers.replace('// WORK-ONLY native staging fragment; inserted after StackDangerOutcomeBatch.','// Exact shared packet keys and outcome resolution after ordinary scalar hits.')
new['CvTacticalAI.cpp']=once(new['CvTacticalAI.cpp'],'struct StackForecastScope\n',buffer+'\nstruct StackForecastScope\n')
new['CvTacticalAI.cpp']=once(new['CvTacticalAI.cpp'],'  gStackOutcomeCurrentBytes = gStackOutcomePeakBytes = 0;','  gStackOutcomeCurrentBytes = gStackOutcomePeakBytes = 0;\n  gStackPacketHits = gStackPacketBuilds = gStackPacketBypasses = 0;')
new['CvTacticalAI.cpp']=once(new['CvTacticalAI.cpp'],'   gStackDestinationScratch.release();','   gStackDestinationScratch.release();\n   gStackPacketScratch.release();')
new['CvTacticalAI.cpp']=once(new['CvTacticalAI.cpp'],'// BEGIN PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY\n',helpers+'\n// BEGIN PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY\n')
wrapper=function(new['CvTacticalAI.cpp'],'static int GetCachedStackDanger(');changed=once(wrapper,'return cached->second;','return cached->second.scalar;')
changed=once(changed,' int result = 0;',' int result = 0;\n StackDangerPacketQuery packetQuery(cacheable);')
start=' if (!outcome || !outcome->TryGet(unit, plot, candidates, friendlyDamage, enemyDamage, result))\n  result = (packetProbeCall.MarkRaw(), GET_PLAYER(unit->getOwner()).GetDangerPlots()->GetStackDanger(*plot, unit, candidates, friendlyDamage, enemyDamage)); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY'
replacement=''' const bool packetResolved = cacheable && ResolveStackDangerPacket(packetQuery,unit,plot,candidates,friendlyDamage,enemyDamage,key,revision,scene,outcome,result);
 if (!packetResolved)
 {
'''+start+'''
 }
'''
changed=once(changed,start,replacement.rstrip())
changed=once(changed,'  StoreStackDangerForecast(key, result);',''' {
  if (packetResolved)
  {
   if (packetQuery.scalarValid && ValidateStackDangerPacket(packetQuery,unit,plot,revision,scene))
   {
    if (packetQuery.storePacket) StoreStackDangerPacketForecast(packetQuery.buffer.key,packetQuery.buffer.value);
    // Only this queried even key is admitted, last under tiny shared budgets.
    if (ValidateStackDangerPacket(packetQuery,unit,plot,revision,scene)) StoreStackDangerForecast(key,result);
   }
  }
  else StoreStackDangerForecast(key,result);
 }''')
new['CvTacticalAI.cpp']=once(new['CvTacticalAI.cpp'],wrapper,changed)
# Probe v2 distinguishes shared result hits from existing local-batch reuse.
t=new['CvTacticalAI.cpp'];t=once(t,'unsigned __int64 freshQueries,batchReuseQueries,freshRepeatQueries,freshCrossMemberQueries;','unsigned __int64 freshQueries,batchReuseQueries,packetResultReuseQueries,freshRepeatQueries,freshCrossMemberQueries;')
t=once(t,'freshQueries(0),batchReuseQueries(0),freshRepeatQueries(0)','freshQueries(0),batchReuseQueries(0),packetResultReuseQueries(0),freshRepeatQueries(0)')
t=once(t,'version=1 prefilterBits=2 cohortBits=3','version=2 prefilterBits=2 cohortBits=3')
t=once(t,'batchReuseQueries=%I64u freshRepeatQueries=','batchReuseQueries=%I64u packetResultReuseQueries=%I64u freshRepeatQueries=')
t=once(t,'done->freshQueries,done->batchReuseQueries,done->freshRepeatQueries','done->freshQueries,done->batchReuseQueries,done->packetResultReuseQueries,done->freshRepeatQueries')
t=once(t,'unsigned long beforeBuilds,revision;','unsigned long beforeBuilds,beforePacketHits,revision;')
t=once(t,'beforeBuilds(0),revision(0)','beforeBuilds(0),beforePacketHits(0),revision(0)')
t=once(t,'beforeBuilds=gStackOutcomeBuilds;','beforeBuilds=gStackOutcomeBuilds;beforePacketHits=gStackPacketHits;')
t=once(t,'if(fresh)++done->freshQueries;else ++done->batchReuseQueries;','if(fresh)++done->freshQueries;else if(gStackPacketHits!=beforePacketHits)++done->packetResultReuseQueries;else ++done->batchReuseQueries;')
new['CvTacticalAI.cpp']=t
# Once-per-search observability only, through existing Summary performance
# logging. No new category/settings or per-query record is introduced.
new['CvTacticalAI.cpp']=once(new['CvTacticalAI.cpp'],'outcomePeakRetainedBytes=%u; phase tick timing','outcomePeakRetainedBytes=%u packetHits=%lu packetBuilds=%lu packetBypasses=%lu; phase tick timing')
new['CvTacticalAI.cpp']=once(new['CvTacticalAI.cpp'],'gStackOutcomeBuilds,gStackOutcomeReuses,gStackOutcomeBypasses,(unsigned int)gStackOutcomeCurrentBytes,(unsigned int)gStackOutcomePeakBytes);','gStackOutcomeBuilds,gStackOutcomeReuses,gStackOutcomeBypasses,(unsigned int)gStackOutcomeCurrentBytes,(unsigned int)gStackOutcomePeakBytes,\n\t\t\tgStackPacketHits,gStackPacketBuilds,gStackPacketBypasses);')
descriptor=(root/'work/stack-danger-cache-descriptor.cpp').read_text(encoding='utf-8-sig');descriptor=descriptor[descriptor.index('bool CvDangerPlots::'):]
descriptor_anchor='// BEGIN PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY\nbool CvDangerPlots::AppendStackDangerProbeSources('
new['CvDangerPlots.cpp']=once(new['CvDangerPlots.cpp'],descriptor_anchor,descriptor+'\n'+descriptor_anchor)
anchor='\tconst std::vector<int>* GetStackDangerDamageIDs(const CvPlot& plot);'
new['CvDangerPlots.h']=once(new['CvDangerPlots.h'],anchor,anchor+'\n\tbool AppendStackDangerCacheDescriptor(const CvPlot& plot, int* words, unsigned capacity, unsigned& used) const;')
# Bind preservation of existing fast-prefix and all original math/key helpers.
fast=lambda s:s[s.index(' int fixedDanger = 0;'):s.index(' keySample.Finish();')]
assert fast(wrapper).replace('return cached->second;','return cached->second.scalar;')==fast(changed),'Scalar-hit prefix drifted'
for signature in ['struct StackForecastKey\n','struct StackForecastKeyHash\n','struct StackForecastQuery\n',
 'static void AppendStackCandidates(','static void AppendStackDamage(','static void AppendStackDamageProjected(',
 'struct StackImmutableEnemyDamageScope\n','struct StackDangerOutcomeBatch\n']:
 assert function(old['CvTacticalAI.cpp'],signature)==function(new['CvTacticalAI.cpp'],signature),'Original helper changed: '+signature
for signature in ['int CvDangerPlotContents::GetStackDanger(','void CvDangerPlotContents::GetStackDangerOutcome(',
 'int CvDangerPlotContents::GetStackDangerFromOutcome(','bool CvDangerPlots::GetStackDangerOutcome(',
 'bool CvDangerPlots::TryGetStackDangerFromOutcome(']:
 assert function(old['CvDangerPlots.cpp'],signature)==function(new['CvDangerPlots.cpp'],signature),'Math/API changed: '+signature
perf=re.search(r'Record\(1,ePlayer,"PLAN_PERF","([^"]*)",(.*?)\);',new['CvTacticalAI.cpp'],re.S);assert perf
formats=re.findall(r'%(?:I64|ll|l|I)?[du]',perf[1]);args=[];begin=0;depth=0
for index,char in enumerate(perf[2]):
 if char=='(':depth+=1
 elif char==')':depth-=1
 elif char==',' and depth==0:args.append(perf[2][begin:index].strip());begin=index+1
args.append(perf[2][begin:].strip());assert len(formats)==len(args),'PLAN_PERF formatter arity mismatch'
maximum_perf_message=re.sub(r'%(?:I64|ll|l|I)?[du]','-2147483648',perf[1]);assert len(maximum_perf_message)<3072
for n,s in new.items():(out/n).write_text(s,encoding='utf-8')
patch=''.join(''.join(difflib.unified_diff(old[n].splitlines(True),new[n].splitlines(True),fromfile='a/CvGameCoreDLL_Expansion2/'+n,tofile='b/CvGameCoreDLL_Expansion2/'+n)) for n in names)
(out/'shared-packet.patch').write_text(patch,encoding='utf-8')
(out/'manifest.json').write_text(json.dumps(dict(control=control,production_untouched=True,source_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in old.items()},candidate_sha256={n:hashlib.sha256(s.encode()).hexdigest() for n,s in new.items()},same_entry_payload_budgets=True,scalar_prefix_exact_except_first_int_field=True,probe_schema_version=2,shared_descriptor_format_words='6+2*sources',packet_format_words='15+2*groups',PLAN_PERF_formatter_fields=len(formats),PLAN_PERF_formatter_arguments=len(args),PLAN_PERF_maximum_message_bytes=len(maximum_perf_message),scope='Ignored native integration stage; mathematical/source wrappers/key builders and scalar warm scratch preserved. Actual integrated fixture required; native ROI unproven.'),indent=2))
print('Shared packet native stage emitted; production untouched; scalar prefix/math/key helpers preserved')
