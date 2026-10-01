"""Stage diagnostic-only packet opportunity observation; never apply/build/run.

Only misses are probed, and the original scalar/result caches stay untouched.
The existing runtime tactical-sampling switch gates the metadata scope. No
gameplay XML, RNG, source refresh, result caching or search-limit changes.
"""
from pathlib import Path
import difflib,hashlib,json,re,subprocess
root=Path(__file__).resolve().parents[1];core=root/'CvGameCoreDLL_Expansion2';out=root/'work/packet-probe-candidate';out.mkdir(exist_ok=True)
files=['CvDangerPlots.h','CvDangerPlots.cpp','CvStackingDiagnostics.h','CvStackingDiagnostics.cpp','CvTacticalAI.cpp']
control='ddab3d93397871f5fb41e99169b06cecffadddfd' # Frozen DLL73, including immutable enemy scope.
original={name:subprocess.check_output(['git','show',control+':CvGameCoreDLL_Expansion2/'+name],cwd=root).decode('utf-8-sig').replace('\r\n','\n') for name in files};candidate=dict(original)
reader=r'''// BEGIN PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
bool CvDangerPlots::AppendStackDangerProbeSources(const CvPlot& plot,int* words,unsigned capacity,unsigned& used) const
{
 // Observation never triggers a lazy refresh or changes gameplay-owned data.
 const int index=plot.GetPlotIndex();
 if(m_bDirty||!words||used>capacity||index<0||(size_t)index>=m_DangerPlots.size()||!m_DangerPlots[index].m_pPlot)return false;
 const CvDangerPlotContents& contents=m_DangerPlots[index];
 const unsigned remaining=capacity-used;
 if(remaining<2)return false;
 const unsigned pairs=(remaining-2)/2;
 if(contents.m_apUnits.size()>pairs||contents.m_apCities.size()>pairs-contents.m_apUnits.size())return false;
 words[used++]=(int)contents.m_apUnits.size();
 for(size_t i=0;i<contents.m_apUnits.size();++i){words[used++]=contents.m_apUnits[i].first;words[used++]=contents.m_apUnits[i].second;}
 words[used++]=(int)contents.m_apCities.size();
 for(size_t i=0;i<contents.m_apCities.size();++i){words[used++]=contents.m_apCities[i].first;words[used++]=contents.m_apCities[i].second;}
 return true;
}
// END PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY

'''
anchor='\tconst std::vector<int>* GetStackDangerDamageIDs(const CvPlot& plot);'
assert candidate['CvDangerPlots.h'].count(anchor)==1
candidate['CvDangerPlots.h']=candidate['CvDangerPlots.h'].replace(anchor,anchor+'\n\tbool AppendStackDangerProbeSources(const CvPlot& plot, int* words, unsigned capacity, unsigned& used) const; // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY',1)
anchor='int CvDangerPlots::GetDanger(const CvPlot& Plot, const CvUnit* pUnit,'
assert candidate['CvDangerPlots.cpp'].count(anchor)==1
candidate['CvDangerPlots.cpp']=candidate['CvDangerPlots.cpp'].replace(anchor,reader+anchor,1)
anchor='    bool GetTacticalSamplingEnabled();'
assert candidate['CvStackingDiagnostics.h'].count(anchor)==1
candidate['CvStackingDiagnostics.h']=candidate['CvStackingDiagnostics.h'].replace(anchor,anchor+'\n    bool TryGetPlanSamplingContext(unsigned long& serial, long& epoch); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY',1)
token=r'''    // BEGIN PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
    bool TryGetPlanSamplingContext(unsigned long& serial,long& epoch)
    {
        // TLS/epoch reads only; no settings, lock, clock or thread-ID syscall.
        if(!planSamples.enabled||planSamples.depth!=1||planSamples.epoch!=ReadPlanSampleEpoch())return false;
        serial=planSamples.serial;epoch=planSamples.epoch;return true;
    }
    // END PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
'''
anchor='    PlanSampleSession::PlanSampleSession('
assert candidate['CvStackingDiagnostics.cpp'].count(anchor)==1
candidate['CvStackingDiagnostics.cpp']=candidate['CvStackingDiagnostics.cpp'].replace(anchor,token+anchor,1)
anchor='!strcmp(category,"PLAN_SAMPLE")) return 16;'
assert candidate['CvStackingDiagnostics.cpp'].count(anchor)==1
candidate['CvStackingDiagnostics.cpp']=candidate['CvStackingDiagnostics.cpp'].replace(anchor,'!strcmp(category,"PLAN_SAMPLE") || !strcmp(category,"PLAN_PACKET_PROBE")) return 16; // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY',1)
fragment=(root/'work/packet-probe-tactical-fragment.cpp').read_text(encoding='utf-8')
anchor='#include <deque>\n'
assert candidate['CvTacticalAI.cpp'].count(anchor)==1
candidate['CvTacticalAI.cpp']=candidate['CvTacticalAI.cpp'].replace(anchor,anchor+'#include <new> // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY\n#include <cstring> // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY\n',1)
anchor='static int GetCachedStackDanger('
assert candidate['CvTacticalAI.cpp'].count(anchor)==1
candidate['CvTacticalAI.cpp']=candidate['CvTacticalAI.cpp'].replace(anchor,fragment+'\n'+anchor,1)
anchor=' if (cacheable)\n  ++gStackDangerMisses;\n'
assert candidate['CvTacticalAI.cpp'].count(anchor)==1
candidate['CvTacticalAI.cpp']=candidate['CvTacticalAI.cpp'].replace(anchor,anchor+' PacketProbeCall packetProbeCall(unit,plot,candidates,friendlyDamage,enemyDamage,key,cacheable); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY\n',1)
anchor='  result = GET_PLAYER(unit->getOwner()).GetDangerPlots()->GetStackDanger(*plot, unit, candidates, friendlyDamage, enemyDamage);'
assert candidate['CvTacticalAI.cpp'].count(anchor)==1
candidate['CvTacticalAI.cpp']=candidate['CvTacticalAI.cpp'].replace(anchor,'  result = (packetProbeCall.MarkRaw(), GET_PLAYER(unit->getOwner()).GetDangerPlots()->GetStackDanger(*plot, unit, candidates, friendlyDamage, enemyDamage)); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY',1)
anchor=' leafSample.Finish(); // PLAN_SAMPLE_DIAGNOSTIC_ONLY\n'
assert candidate['CvTacticalAI.cpp'].count(anchor)==1
candidate['CvTacticalAI.cpp']=candidate['CvTacticalAI.cpp'].replace(anchor,anchor+' packetProbeCall.Finish(); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY\n',1)
anchor='\tCvStackingDiagnostics::PlanSampleSession sampleSession(ePlayer,pTarget->GetPlotIndex()); // PLAN_SAMPLE_DIAGNOSTIC_ONLY\n'
assert candidate['CvTacticalAI.cpp'].count(anchor)==1
candidate['CvTacticalAI.cpp']=candidate['CvTacticalAI.cpp'].replace(anchor,anchor+'\tPacketProbeScope packetProbeScope(ePlayer,pTarget->GetPlotIndex()); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY\n',1)
def strip(text):
 text=re.sub(r'^[ \t]*// BEGIN PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY\n.*?^[ \t]*// END PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY\n(?:\n)?','',text,flags=re.S|re.M)
 text=text.replace(' || !strcmp(category,"PLAN_PACKET_PROBE")','').replace('return 16; // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY','return 16;')
 text=re.sub(r'^([ \t]*)result = \(packetProbeCall\.MarkRaw\(\), (.*?)\); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY$',r'\1result = \2;',text,flags=re.M)
 text=''.join(line for line in text.splitlines(True) if 'PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY' not in line)
 return text
for name in files:
 # Ignore only the one blank introduced between helper fragment and original.
 normalized=strip(candidate[name])
 if name=='CvTacticalAI.cpp':normalized=normalized.replace('\n\nstatic int GetCachedStackDanger(','\nstatic int GetCachedStackDanger(',1) if '\n\nstatic int GetCachedStackDanger(' not in original[name] else normalized
 assert normalized==original[name], 'Diagnostic reverse-strip changed original gameplay body: '+name
 (out/name).write_text(candidate[name],encoding='utf-8')
patch=''.join(''.join(difflib.unified_diff(original[name].splitlines(True),candidate[name].splitlines(True),fromfile='a/CvGameCoreDLL_Expansion2/'+name,tofile='b/CvGameCoreDLL_Expansion2/'+name)) for name in files)
(out/'packet-probe.patch').write_text(patch,encoding='utf-8')
(out/'manifest.json').write_text(json.dumps(dict(control=control,production_untouched=True,only_diagnostic_changes=True,source_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in original.items()},candidate_sha256={name:hashlib.sha256(text.encode()).hexdigest() for name,text in candidate.items()},bounds=dict(slots=128,keyWords=512,pairs=128,maximumMetadataBytes=3*1024*1024),cohort=dict(prefilterBits=2,fullKeyBits=3,queryIDExcludedFromBoth=True),scope='Staged metadata-only probe from pinned DLL73; no source refresh/result admission/HP arithmetic/cache-capacity/RNG/search changes.'),indent=2))
print('Packet probe staged; five-file reverse-strip matches current production exactly; no build/game calls')
