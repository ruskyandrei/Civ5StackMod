"""Work-only first-wave/coherent-opening stage; root composes shared source."""
from pathlib import Path
import difflib,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE='d792b4bcb';OUT=ROOT/'work/first-wave-staged';OUT.mkdir(exist_ok=True)
files={n:subprocess.check_output(['git','show',BASE+':CvGameCoreDLL_Expansion2/'+n],cwd=ROOT).decode('utf-8-sig').replace('\r\n','\n') for n in ('CvStackingOffensiveAI.cpp','CvStackingOffensiveAI.h','CvStackingAI.cpp')};new=dict(files);changes={n:[] for n in files}
def fun(s,sig):
 a=s.index(sig);b=s.index('{',a)+1;d=1
 while d:d+=(s[b]=='{')-(s[b]=='}');b+=1
 return s[a:b]
def once(n,a,b):
 assert new[n].count(a)==1,(a[:80],new[n].count(a));new[n]=new[n].replace(a,b,1);changes[n].append((a,b))
cpp='CvStackingOffensiveAI.cpp';hpp='CvStackingOffensiveAI.h';ai='CvStackingAI.cpp'
types=(ROOT/'work/first-wave-types.cpp').read_text(encoding='utf-8-sig');policy=(ROOT/'work/first-wave-policy.cpp').read_text(encoding='utf-8-sig')
once(cpp,'    struct Objective\n',types+'\n    struct Objective\n')
once(cpp,'        bool captureKnown;', '        bool captureKnown;\n        std::vector<AssaultWaveUnit> waveRows;bool waveComplete,wavePathUnknown;')
once(cpp,'lowestHP(INT_MAX),captureKnown(false){}','lowestHP(INT_MAX),captureKnown(false),waveComplete(false),wavePathUnknown(false){}')
once(cpp,'    bool EntryRanged(',policy+'\n    bool EntryRanged(')
once(hpp,'        bool ready, routeKnown;', '        int waveUnits,waveSiege,waveCapturers,waveStrength,waveDamage,waveSustain,waveFirstETA,waveLastETA;unsigned failedMask;\n        bool ready, routeKnown,healingComplete;')
once(hpp,'reason(0),ready(false),routeKnown(false){}','reason(0),waveUnits(0),waveSiege(0),waveCapturers(0),waveStrength(0),waveDamage(0),waveSustain(0),waveFirstETA(-1),waveLastETA(-1),failedMask(0),ready(false),routeKnown(false),healingComplete(false){}')
once(hpp,'    bool OpeningReady(', '    bool TryReadyCoreForArmy(CvAIOperation* operation,CvArmyAI* army,bool& ready);\n    void ResetOpeningReadiness();\n    bool OpeningReady(')
body=fun(new[cpp],'    AssaultPlan AssessAssault(');changed=body
changed=changed.replace('        const int previousPhase=o.assault.phase;', '        const int previousPhase=o.assault.phase;\n        o.waveRows.clear();o.waveComplete=true;o.wavePathUnknown=false;')
changed=changed.replace('            if(!firing) { ++result.inbound;continue; }','            if(!firing) { if(assaultQueries[owner]>=budget)o.wavePathUnknown=true; ++result.inbound;continue; }')
changed=changed.replace('            result.cityDamage+=damage;', '''            result.cityDamage+=damage;
            if(o.waveComplete)
            {
                if(o.waveRows.size()>=(size_t)Setting("AIAssaultWaveMaximumRecords",64)) {o.waveComplete=false;o.waveRows.clear();}
                else try{o.waveRows.push_back(AssaultWaveUnit(u,eta,damage,retaliation,target));}
                catch(const std::bad_alloc&){o.waveComplete=false;o.waveRows.clear();}
            }''')
a=changed.index('        int healing=0;');b=changed.index('        const bool captureSoon=',a)
changed=changed[:a]+'''        int waveCaptureETA=o.captureOwner!=owner&&o.captureID>=0?o.captureEta:INT_MAX;
        for(size_t i=0;i<o.waveRows.size();++i)if((o.waveRows[i].roles&1)!=0)waveCaptureETA=min(waveCaptureETA,o.waveRows[i].eta);
        AssaultWave wave=SelectFirstWave(o.waveRows,Setting("AIAssaultMinimumReadyUnits",4),EssentialSiege(owner,city,domain),
            domain==DOMAIN_SEA?Setting("AIAssaultNavalMinimumRanged",4):0,result.enemyStrength,Setting("AIAssaultStrengthPercent",125),hp,
            waveCaptureETA,Setting("AIAssaultFirstWaveMaximumTurns",1),Setting("AIAssaultWaveArrivalSpreadTurns",1));
        const int healing=city->GetAssaultHealingForecast(owner,o.waveComplete?wave.damage:result.cityDamage,&result.healingComplete);
'''+changed[b:]
changed=changed.replace('        result.reason=immediateCapture?0:', '''        if(o.waveComplete) result.ready=immediateCapture||WaveCanSustain(wave,hp,healing,Setting("AIAssaultDamageHorizon",4),result.healingComplete);
        else result.failedMask|=ASSAULT_UNKNOWN; // Memory/work uncertainty retains original policy.
        CopyWave(result,wave);if(!o.waveComplete)result.failedMask|=ASSAULT_UNKNOWN;
        result.reason=immediateCapture?0:''',1)
# Keep continuation under original policy only when the optional cohort could
# not be represented. A sufficient coherent wave needs no desired-count gate.
changed=changed.replace('        if(previousPhase==1 && !result.ready && roles && damageEnough &&','        if(!o.waveComplete && previousPhase==1 && !result.ready && roles && damageEnough &&')
oldlog='captureEta=%d gatherAge=%d pathQueries=%d firstArrival=%d lastArrival=%d; ready is a route-and-damage forecast, not an executed attack'
changed=changed.replace(oldlog,'captureEta=%d gatherAge=%d pathQueries=%d firstArrival=%d lastArrival=%d waveUnits=%d waveSiege=%d waveCapturers=%d waveStrength=%d waveDamage=%d waveSustain=%d waveFirstETA=%d waveLastETA=%d healingComplete=%d failedMask=%u; readiness forecast only')
changed=changed.replace('firstArrival==INT_MAX?-1:firstArrival,lastArrival);','firstArrival==INT_MAX?-1:firstArrival,lastArrival,result.waveUnits,result.waveSiege,result.waveCapturers,result.waveStrength,result.waveDamage,result.waveSustain,result.waveFirstETA,result.waveLastETA,result.healingComplete,result.failedMask);')
changed=changed.replace('        result.phase=result.ready?1:0;', '        if(result.ready)result.reason=0;\n        else if(o.waveComplete)result.reason=(wave.failed&ASSAULT_CAPTURE)?1:(wave.failed&ASSAULT_SIEGE)?2:(wave.failed&ASSAULT_DAMAGE)?3:(wave.failed&ASSAULT_COHESION)?6:4;\n        if(!result.ready&&(o.wavePathUnknown||!o.captureKnown))result.failedMask|=ASSAULT_UNKNOWN;\n        result.phase=result.ready?1:0;')
once(cpp,body,changed)
openingTypes=(ROOT/'work/first-wave-opening-types.cpp').read_text(encoding='utf-8-sig')
once(cpp,'    std::map<ObjectiveKey,Objective> objectives;',openingTypes+'\n    std::map<ObjectiveKey,Objective> objectives;')
opening=(ROOT/'work/first-wave-opening.cpp').read_text(encoding='utf-8-sig')
originalOpening=fun(new[cpp],'    bool OpeningReady(')
legacyOpening=originalOpening.replace('    bool OpeningReady(', '    static bool LegacyOpeningReady(',1)
once(cpp,originalOpening,legacyOpening+'\n'+opening.strip())
once(cpp,'{ objectives.clear(); commitments.clear();','{ ResetOpeningReadiness(); objectives.clear(); commitments.clear();')
declare=fun(new[cpp],'    bool ReadyToDeclare(')
once(cpp,declare,declare.replace('        bool ready=false;','        if(player.IsAtWarWith(enemy))return true; // Existing forced/defensive war has no voluntary-opening gate.\n        bool ready=false;',1))
core=(ROOT/'work/first-wave-core.cpp').read_text(encoding='utf-8-sig');once(cpp,'    bool OpeningReady(',core+'\n    bool OpeningReady(')
body=fun(new[ai],'    bool ReadyWithAvailableUnits(')
needle='        int present=0,required=0,missing=0,strength=0,support=0; bool capture=false;'
changed=body.replace(needle,'''        bool firstWaveReady=false;
        if(CvStackingOffensiveAI::IsCityAttack(operation)&&Setting("AIAssaultCoordinationEnabled",1)!=0&&
            CvStackingOffensiveAI::TryReadyCoreForArmy(operation,army,firstWaveReady))return firstWaveReady;
'''+needle)
once(ai,body,changed)
for n,s in new.items():
 restored=s
 for a,b in reversed(changes[n]):assert restored.count(b)==1;restored=restored.replace(b,a,1)
 assert restored==files[n],n
 (OUT/n).write_text(s,encoding='utf-8')
 (OUT/('control-'+n)).write_text(files[n],encoding='utf-8')
(OUT/'first-wave.patch').write_text(''.join(''.join(difflib.unified_diff(files[n].splitlines(True),new[n].splitlines(True),fromfile='a/CvGameCoreDLL_Expansion2/'+n,tofile='b/CvGameCoreDLL_Expansion2/'+n)) for n in files),encoding='utf-8')
proof=dict(control=BASE,whole_reverse_exact=True,production_untouched=True,original_hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in files.items()},candidate_hashes={n:hashlib.sha256(s.encode()).hexdigest() for n,s in new.items()},new_settings=[['AIAssaultEssentialSiegeUnits',2,0,32],['AIAssaultFirstWaveMaximumTurns',1,0,4],['AIAssaultWaveMaximumRecords',64,4,256],['AIAssaultIncompleteDamagePercent',125,100,300]],dependency='CvCity::GetAssaultHealingForecast(observer,expectedCityDamage,bool*) from search lane; Opening/own-army cached cohort, ResetOpeningReadiness seam; no added assault path queries, prewar retains original operation-route scan.')
(OUT/'proof.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps(proof))
