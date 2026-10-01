"""Stage complete DLL86 forecast-storage replacement; never applies production."""
from pathlib import Path
import difflib, hashlib, json, subprocess
import re

ROOT=Path(__file__).resolve().parents[1]
BASELINE='ef274591d0f4f32e193959524faf953cf964bd86'
PATH='CvGameCoreDLL_Expansion2/CvTacticalAI.cpp'
OUT=ROOT/'work/indexed-forecast-store-staged'
TEMPLATES=ROOT/'work/indexed-forecast-store-template'
NAMES=('StackDangerForecastPayloadBytes','EvictOldestStackForecast','CanStoreStackForecast','EstimatedStackForecastBytes','UpdateStackForecastPeaks','StoreStackDangerForecast','StoreStackDangerPacketForecast','StoreStackDefenderForecast')
LOOKUPS='''// Backend queries copy results before any caller validation can clear storage.
static size_t StackDangerForecastSize(){return gUseIndexed?gIndexed.Count(IndexedStore::DANGER):gStackDangerForecasts.size();}
static size_t StackDefenderForecastSize(){return gUseIndexed?gIndexed.Count(IndexedStore::DEFENDER):gStackDefenderForecasts.size();}
static bool FindStackDangerForecastScalar(const StackForecastKey& key,int& result)
{
 if(gUseIndexed){int handle=gIndexed.Find(key,IndexedStore::DANGER);if(handle==-1)return false;result=gIndexed.At(handle).scalar;return true;}
 StackDangerForecasts::const_iterator hit=gStackDangerForecasts.find(key);
 if(hit==gStackDangerForecasts.end())return false;result=hit->second.scalar;return true;
}
static bool FindStackDangerForecastMember(const StackForecastKey& key,const CvUnit* unit,int& result)
{
 if(gUseIndexed)
 {
  int handle=gIndexed.Find(key,IndexedStore::DANGER);if(handle==-1)return false;
  const IndexedStore::Slot& slot=gIndexed.At(handle);
  for(size_t i=0;i<slot.members;++i)if(slot.Data()[slot.keyWords+2*i]==unit->GetID())
  {result=slot.Data()[slot.keyWords+2*i+1];return true;}
  return false;
 }
 StackDangerForecasts::const_iterator hit=gStackDangerForecasts.find(key);
 if(hit!=gStackDangerForecasts.end())for(size_t i=0;i<hit->second.memberScores.size();++i)
  if(hit->second.memberScores[i].first==unit->GetID()){result=hit->second.memberScores[i].second;return true;}
 return false;
}
static bool FindStackDefenderForecast(const StackForecastKey& key,const CvUnit*& result)
{
 if(gUseIndexed){int handle=gIndexed.Find(key,IndexedStore::DEFENDER);if(handle==-1)return false;result=gIndexed.At(handle).defender;return true;}
 StackDefenderForecasts::const_iterator hit=gStackDefenderForecasts.find(key);
 if(hit==gStackDefenderForecasts.end())return false;result=hit->second;return true;
}

'''


def scope_transform(actual):
    release='''   std::deque<const StackForecastKey*>().swap(gStackDangerOrder);
   std::deque<const StackForecastKey*>().swap(gStackDefenderOrder);
   StackDangerForecasts().swap(gStackDangerForecasts);
   StackDefenderForecasts().swap(gStackDefenderForecasts);
'''
    assert actual.count(release)==1
    changed=actual.replace(release,'   gIndexed.Release();gUseIndexed=false;\n'+release)
    end='  gStackKeyPayloadLimit = gStackEntryLimit * TACTSIM_MAX_UNITS * 2 * sizeof(int);\n }'
    assert changed.count(end)==1
    return changed.replace(end,'''  gStackKeyPayloadLimit = gStackEntryLimit * TACTSIM_MAX_UNITS * 2 * sizeof(int);
  gUseIndexed=false;
  try { if(gStackForecastsActive){gIndexed.Init(gStackEntryLimit);gUseIndexed=true;} }
  catch (const std::bad_alloc&)
  {
   // Pick the original representation before any query or admission.
   // Partial arrays are already rolled back by Init; no in-search fallback.
   gIndexed.Release();gUseIndexed=false;
  }
  catch (...)
  {
   // Constructor failure will not invoke this object's destructor.
   gIndexed.Release();gStackKeyPayloadBytes=0;gStackEntryLimit=gStackKeyPayloadLimit=0;
   gStackForecastDepth=0;gStackForecastsActive=false;owned=false;
   InterlockedExchange(&gStackForecastOwnerThread,0);throw;
  }
 }''')


def replace_once(text,old,new):
    assert text.count(old)==1,old[:100]
    return text.replace(old,new)


def transform(source):
    clear_start=source.index('static void ClearStackForecastEntries()')
    clear_end=source.index('static void InvalidateStackForecastScene()',clear_start)
    header=(TEMPLATES/'IndexedStore.h').read_text(encoding='utf-8')
    header=header.replace('// Work-only storage prototype. All input keys/values are the actual DLL86 types.','// Bounded owned forecast storage. Input key and result semantics remain unchanged.')
    header=header.replace('// Original Context/Invalidate functions are inserted here by the fixture builder.\n','')
    changed=source[:clear_start]+header+'\n'+source[clear_end:]
    changed=changed.replace('#include <new> // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY','#include <new>')
    changed=changed.replace('#include <cstring> // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY','#include <cstring>')
    scope_start=source.index('struct StackForecastScope\n')
    scope_end=source.index('// Retained capacities, including packet outputs',scope_start)
    changed=replace_once(changed,source[scope_start:scope_end],scope_transform(source[scope_start:scope_end]))
    start=source.index('static size_t StackDangerForecastPayloadBytes(')
    end=source.index('static void AppendStackCandidates(',start)
    actual_methods=source[start:end]
    legacy=actual_methods
    for name in NAMES:legacy=legacy.replace(name,'Legacy'+name)
    methods=(TEMPLATES/'IndexedMethods.h').read_text(encoding='utf-8').replace('BeforeQueuePush();','')
    methods=methods.replace('// Admission/control-flow mirrors the actual DLL86 storage helpers. Only the','// Admission/control flow preserves the original storage helpers. Only the')
    changed=replace_once(changed,actual_methods,legacy+'\n'+methods+'\n'+LOOKUPS)
    packet=''' StackDangerForecasts::const_iterator hit=gStackDangerForecasts.find(b.key);
 if(hit!=gStackDangerForecasts.end())
  for(size_t i=0;i<hit->second.memberScores.size();++i)if(hit->second.memberScores[i].first==unit->GetID())
  {
   // Copy before a validating context call, which may clear the owning table.
   const int cachedResult=hit->second.memberScores[i].second;
   if(!ValidateStackDangerPacket(query,unit,plot,revision,scene))return false;
   result=cachedResult;query.scalarValid=true;++gStackPacketHits;return true;
  }
'''
    changed=replace_once(changed,packet,''' int cachedResult=0;
 if(FindStackDangerForecastMember(b.key,unit,cachedResult))
 {
  // The backend copied the integer before validation may clear storage.
  if(!ValidateStackDangerPacket(query,unit,plot,revision,scene))return false;
  result=cachedResult;query.scalarValid=true;++gStackPacketHits;return true;
 }
''')
    scalar='''  StackDangerForecasts::const_iterator cached = cacheable ? gStackDangerForecasts.find(key) : gStackDangerForecasts.end();
  if (cacheable && cached != gStackDangerForecasts.end())
  {
   ++gStackDangerHits;
   return cached->second.scalar;
  }
'''
    changed=replace_once(changed,scalar,'''  int cachedResult=0;
  if (cacheable && FindStackDangerForecastScalar(key,cachedResult))
  {
   ++gStackDangerHits;
   return cachedResult;
  }
''')
    defender='''  StackDefenderForecasts::const_iterator cached = cacheable ? gStackDefenderForecasts.find(key) : gStackDefenderForecasts.end();
  if (cacheable && cached != gStackDefenderForecasts.end())
  {
   ++gStackDefenderHits;
   return cached->second;
  }
'''
    changed=replace_once(changed,defender,'''  const CvUnit* cachedResult=NULL;
  if (cacheable && FindStackDefenderForecast(key,cachedResult))
  {
   ++gStackDefenderHits;
   return cachedResult;
  }
''')
    tail_start=changed.index('static void GetVirtualFriendlyStack(')
    tail=changed[tail_start:].replace('gStackDangerForecasts.size()','StackDangerForecastSize()').replace('gStackDefenderForecasts.size()','StackDefenderForecastSize()')
    changed=changed[:tail_start]+tail
    changed=replace_once(changed,'callbackSuspensions=%lu; phase tick timing','callbackSuspensions=%lu forecastBackend=%s forecastEstimatedBytes=%u; phase tick timing')
    changed=replace_once(changed,'strength.capabilityScans,strength.capabilityFlags,strength.capabilityValidationBypasses,strength.capabilitySuspensions);','strength.capabilityScans,strength.capabilityFlags,strength.capabilityValidationBypasses,strength.capabilitySuspensions,gUseIndexed?"indexed":"legacy",(unsigned int)EstimatedStackForecastBytes());')
    assert 'BeforeQueuePush' not in changed
    assert changed.count('forecastBackend=%s')==1
    return changed


def formatter_proof(candidate):
    start=candidate.index('CvStackingDiagnostics::Record(1,ePlayer,"PLAN_PERF",')
    p=candidate.index('(',start);depth=0;quote=False;escape=False;end=None
    for i in range(p,len(candidate)):
        c=candidate[i]
        if quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c=='"':quote=False
        elif c=='"':quote=True
        elif c=='(':depth+=1
        elif c==')':
            depth-=1
            if not depth:end=i;break
    assert end is not None
    body=candidate[p+1:end];args=[];depth=0;quote=False;escape=False;last=0
    for i,c in enumerate(body):
        if quote:
            if escape:escape=False
            elif c=='\\':escape=True
            elif c=='"':quote=False
        elif c=='"':quote=True
        elif c in '([{':depth+=1
        elif c in ')]}':depth-=1
        elif c==',' and not depth:args.append(body[last:i].strip());last=i+1
    args.append(body[last:].strip())
    assert args[:3]==['1','ePlayer','"PLAN_PERF"']
    fmt=args[3][1:-1];fields=re.findall(r'%(?:l)?[dus]',fmt)
    assert len(fields)==len(args)-4
    assert fields[-2:]==['%s','%u']
    assert args[-2:]==['gUseIndexed?"indexed":"legacy"','(unsigned int)EstimatedStackForecastBytes()']
    maximum=len(re.sub(r'%(?:l)?[dus]','',fmt))+sum(7 if item=='%s' else 11 if item=='%d' else 10 for item in fields)
    assert maximum<2048
    return dict(placeholders=len(fields),valueArguments=len(args)-4,maximumMessageBytes=maximum,limit=2048,extraRows=0)


def main():
    source=subprocess.check_output(['git','show',BASELINE+':'+PATH],cwd=ROOT).decode('utf-8-sig')
    candidate=transform(source)
    assert (ROOT/PATH).read_text(encoding='utf-8-sig') in (source,candidate),'Current Tactical source has changed; rebase before staging'
    OUT.mkdir(parents=True,exist_ok=True)
    delta=list(difflib.ndiff(source.splitlines(True),candidate.splitlines(True)))
    restored=''.join(difflib.restore(delta,1))
    assert restored==source and ''.join(difflib.restore(delta,2))==candidate
    (OUT/'CvTacticalAI-control.cpp').write_text(source,encoding='utf-8')
    (OUT/'CvTacticalAI.cpp').write_text(candidate,encoding='utf-8')
    (OUT/'indexed-store.patch').write_text(''.join(difflib.unified_diff(source.splitlines(True),candidate.splitlines(True),'a/'+PATH,'b/'+PATH)),encoding='utf-8')
    (OUT/'indexed-store.reverse.patch').write_text(''.join(difflib.unified_diff(candidate.splitlines(True),source.splitlines(True),'a/'+PATH,'b/'+PATH)),encoding='utf-8')
    proof=dict(baseline=BASELINE,path=PATH,sourceSHA256=hashlib.sha256(source.encode()).hexdigest(),candidateSHA256=hashlib.sha256(candidate.encode()).hexdigest(),
               templates={name:hashlib.sha256((TEMPLATES/name).read_bytes()).hexdigest() for name in ('IndexedStore.h','IndexedMethods.h')},
               reverseWholeFileRestorationSHA256=hashlib.sha256(restored.encode()).hexdigest(),
               formatter=formatter_proof(candidate),
               scope='Storage+three backend lookup callers+explicit standard includes+existing count/physical-estimate diagnostics only. Keys/hash/Context/math guards unchanged. No core edits. Native speed unmeasured.')
    (OUT/'production-staging-proof.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(proof))


if __name__=='__main__':main()
