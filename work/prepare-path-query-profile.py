"""Stage default-off path query diagnostics; no result reuse/production edits."""
from pathlib import Path
import difflib,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];CONTROL='e0d85052b';OUT=ROOT/'work/path-query-profile-staged';OUT.mkdir(exist_ok=True)
names=['CvStackingDiagnostics.h','CvStackingDiagnostics.cpp','CvAStar.cpp']
old={n:subprocess.check_output(['git','show',CONTROL+':CvGameCoreDLL_Expansion2/'+n],cwd=ROOT).decode('utf-8-sig') for n in names};new=dict(old)
header=r'''    // BEGIN PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY
    enum PathProfilePart { PATH_RAW_DANGER, PATH_CLEAR_TERRAIN, PATH_PROFILE_PARTS };
    class PathProfileSession
    {
    public:
        PathProfileSession(PlayerTypes player,int unit,int pathType,int generation,int flags,int startX,int startY,int goalX,int goalY,bool verify);
        ~PathProfileSession();
    private:
        PathProfileSession(const PathProfileSession&);
        PathProfileSession& operator=(const PathProfileSession&);
        bool outer;
        unsigned long serial;
        const void* threadState;
    };
    class PathProfileScope
    {
    public:
        PathProfileScope(PathProfilePart part,const CvUnit* unit=NULL,const CvPlot* plot=NULL);
        ~PathProfileScope() { Finish(); }
        void Finish() { if(sampled) FinishSampled(); }
    private:
        PathProfileScope(const PathProfileScope&);
        PathProfileScope& operator=(const PathProfileScope&);
        void FinishSampled();
        bool sampled;
        PathProfilePart part;
        unsigned long serial;
        long epoch;
        unsigned __int64 started;
        const void* threadState;
    };
    void CountPathNodeCache(bool hit);
    // END PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY
'''
globals=r'''    // BEGIN PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY
    enum { PATH_QUERY_STRIDE=8, PATH_CALL_STRIDE=16, PATH_REPEAT_SLOTS=128, PATH_REPEAT_PROBES=16 };
    struct PathRepeatSlot { bool used; int plot,hp,maxHP;long scene; };
    struct PathProfileState
    {
        bool enabled,verify,queryClock;
        unsigned depth;
        unsigned long serial,thread,generation,nodeGeneration,flags,phase,queryPhase,startedTick;
        PlayerTypes actor;
        int turn,unit,pathType,startX,startY,goalX,goalY,eventFlags;
        long epoch,scene;
        unsigned __int64 frequency,started,clockReads,clockFailures,nested,cacheHits,cacheBuilds;
        unsigned __int64 tracked,untracked,repeats,samePhysicalRepeats,dirty,actorMismatch;
        PlanSampleCounter counter[CvStackingDiagnostics::PATH_PROFILE_PARTS];
        PathRepeatSlot seen[PATH_REPEAT_SLOTS];
    };
    static __declspec(thread) PathProfileState pathProfile={};
    static __declspec(thread) unsigned long pathProfileSerial=0;
    static __declspec(thread) long pathProfileDisabledEpoch=-1;
    // END PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY
'''
methods=r'''    // BEGIN PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY
    PathProfileSession::PathProfileSession(PlayerTypes player,int unit,int pathType,int generation,int flags,int startX,int startY,int goalX,int goalY,bool verify):outer(false),serial(0),threadState(&pathProfile)
    {
        if(pathProfile.depth++) { serial=pathProfile.serial;if(pathProfile.enabled)++pathProfile.nested;return; }
        outer=true;serial=++pathProfileSerial;if(!serial)serial=++pathProfileSerial;
        pathProfile.serial=serial;pathProfile.enabled=false;
        // Only a sampling-off observation made under Lock is mirrored. Toggle,
        // level and load/reset already bump the shared atomic sampling epoch.
        if(pathProfileDisabledEpoch==ReadPlanSampleEpoch())return;
        Lock lock;
        if(!(tacticalSamplingOverride>=0?tacticalSamplingOverride!=0:setting("DiagnosticsTacticalSampling",0)!=0))
        { pathProfileDisabledEpoch=ReadPlanSampleEpoch();return; }
        if(!categoryEnabledUnlocked(1,player,"PATH_SAMPLE"))return;
        const int interval=setting("DiagnosticsPerformanceInterval",1);
        if(interval<=0 || GC.getGame().getGameTurn()%interval || !gDLL->HasGameCoreLock())return;
        const unsigned long phase=((unsigned long)unit*1664525UL+(unsigned long)player*97UL+(unsigned long)pathType*13UL)&(PATH_QUERY_STRIDE-1);
        if((serial+phase)&(PATH_QUERY_STRIDE-1))return;
        LARGE_INTEGER frequency,now;
        if(!QueryPerformanceFrequency(&frequency)||frequency.QuadPart<=0)return;
        memset(pathProfile.counter,0,sizeof(pathProfile.counter));memset(pathProfile.seen,0,sizeof(pathProfile.seen));
        pathProfile.frequency=(unsigned __int64)frequency.QuadPart;
        pathProfile.clockReads=1;pathProfile.clockFailures=0;
        pathProfile.queryClock=QueryPerformanceCounter(&now)!=0&&now.QuadPart>=0;
        pathProfile.started=pathProfile.queryClock?(unsigned __int64)now.QuadPart:0;
        if(!pathProfile.queryClock)++pathProfile.clockFailures;
        pathProfile.startedTick=GetTickCount();pathProfile.generation=phaseGeneration;
        pathProfile.thread=GetCurrentThreadId();pathProfile.actor=player;pathProfile.unit=unit;pathProfile.pathType=pathType;
        pathProfile.turn=GC.getGame().getGameTurn();pathProfile.nodeGeneration=generation;pathProfile.flags=flags;
        pathProfile.startX=startX;pathProfile.startY=startY;pathProfile.goalX=goalX;pathProfile.goalY=goalY;pathProfile.verify=verify;
        pathProfile.epoch=ReadPlanSampleEpoch();pathProfile.scene=CvStackingStrengthCache::SceneEpoch();
        pathProfile.eventFlags=(MOD_EVENTS_CAN_MOVE_INTO?1:0)|(MOD_EVENTS_AIRLIFT?2:0)|(MOD_EVENTS_SEALIFT?4:0)|
            (MOD_EVENTS_UNIT_RANGEATTACK?8:0)|(MOD_EVENTS_CITY_BOMBARD?16:0)|(MOD_EVENTS_REBASE?32:0);
        pathProfile.queryPhase=phase;pathProfile.phase=(serial*2246822519UL+(unsigned long)unit*1664525UL)&(PATH_CALL_STRIDE-1);
        pathProfile.nested=pathProfile.cacheHits=pathProfile.cacheBuilds=0;
        pathProfile.tracked=pathProfile.untracked=pathProfile.repeats=pathProfile.samePhysicalRepeats=pathProfile.dirty=pathProfile.actorMismatch=0;
        pathProfile.enabled=true;
    }
    PathProfileSession::~PathProfileSession()
    {
        if(threadState!=&pathProfile||serial!=pathProfile.serial||!pathProfile.depth)return;
        if(--pathProfile.depth||!outer)return;
        const bool enabled=pathProfile.enabled;pathProfile.enabled=false;if(!enabled)return;
        Lock lock;
        if(pathProfile.epoch!=ReadPlanSampleEpoch()||pathProfile.generation!=phaseGeneration||
            pathProfile.thread!=GetCurrentThreadId()||pathProfile.turn!=GC.getGame().getGameTurn()||
            !categoryEnabledUnlocked(1,pathProfile.actor,"PATH_SAMPLE"))return;
        LARGE_INTEGER now;unsigned __int64 queryTicks=0;bool queryAvailable=false;
        if(pathProfile.queryClock)
        {
            ++pathProfile.clockReads;queryAvailable=QueryPerformanceCounter(&now)&&now.QuadPart>=0&&
                (unsigned __int64)now.QuadPart>=pathProfile.started;
            if(queryAvailable)queryTicks=(unsigned __int64)now.QuadPart-pathProfile.started;else ++pathProfile.clockFailures;
        }
        const PlanSampleCounter& danger=pathProfile.counter[PATH_RAW_DANGER];const PlanSampleCounter& terrain=pathProfile.counter[PATH_CLEAR_TERRAIN];
        Record(1,pathProfile.actor,"PATH_SAMPLE",
            "unit=%d pathType=%d origin=%s serial=%lu thread=%lu nodeGeneration=%lu flags=%lu startX=%d startY=%d goalX=%d goalY=%d queryStride=%u queryPhase=%lu callStride=%u callPhase=%lu startTick=%lu endTick=%lu sourceEpochStart=%ld sourceEpochEnd=%ld eventFlags=%d trackingSlots=128 trackingProbeLimit=16 repeatCoverage=observed_lower_bound_if_untracked_nonzero qpcFrequency=%I64u qpcReads=%I64u clockFailures=%I64u queryAvailable=%d queryTicks=%I64u nestedQueries=%I64u nodeCacheHits=%I64u nodeCacheBuilds=%I64u rawDangerCalls=%I64u trackedDangerCalls=%I64u untrackedDangerCalls=%I64u repeatedPlotCalls=%I64u sameSceneHPRepeats=%I64u dirtyDangerCalls=%I64u actorMismatches=%I64u dangerSelected=%I64u dangerSamples=%I64u dangerTicks=%I64u dangerMaxTicks=%I64u terrainCalls=%I64u terrainSelected=%I64u terrainSamples=%I64u terrainTicks=%I64u terrainMaxTicks=%I64u semantics=inclusive_same_thread_wall_samples repeatSemantics=bounded_plot_scene_actor_HP_opportunities_not_validated_cache_hits overlap=nested_queries_and_PLAN_not_additive; subset of systematic sampled queries; no raw-result reuse; missing samples unknown; callback masks do not exclude legacy loading listeners",
            pathProfile.unit,pathProfile.pathType,pathProfile.verify?"verify":"search",serial,pathProfile.thread,pathProfile.nodeGeneration,pathProfile.flags,pathProfile.startX,pathProfile.startY,pathProfile.goalX,pathProfile.goalY,
            PATH_QUERY_STRIDE,pathProfile.queryPhase,PATH_CALL_STRIDE,pathProfile.phase,pathProfile.startedTick,GetTickCount(),pathProfile.scene,CvStackingStrengthCache::SceneEpoch(),pathProfile.eventFlags,
            pathProfile.frequency,pathProfile.clockReads,pathProfile.clockFailures,queryAvailable?1:0,queryTicks,pathProfile.nested,pathProfile.cacheHits,pathProfile.cacheBuilds,
            danger.calls,pathProfile.tracked,pathProfile.untracked,pathProfile.repeats,pathProfile.samePhysicalRepeats,pathProfile.dirty,pathProfile.actorMismatch,
            danger.selected,danger.samples,danger.ticks,danger.maximum,terrain.calls,terrain.selected,terrain.samples,terrain.ticks,terrain.maximum);
    }
    void CountPathNodeCache(bool hit)
    {
        if(!pathProfile.enabled||pathProfile.depth!=1)return;
        if(hit)++pathProfile.cacheHits;else ++pathProfile.cacheBuilds;
    }
    PathProfileScope::PathProfileScope(PathProfilePart value,const CvUnit* unit,const CvPlot* plot):sampled(false),part(value),serial(0),epoch(0),started(0),threadState(NULL)
    {
        if(!pathProfile.enabled||pathProfile.depth!=1||value<0||value>=PATH_PROFILE_PARTS)return;
        if(pathProfile.epoch!=ReadPlanSampleEpoch()) { pathProfile.enabled=false;return; }
        PlanSampleCounter& count=pathProfile.counter[value];++count.calls;
        if(value==PATH_RAW_DANGER&&unit&&plot)
        {
            const PlayerTypes owner=unit->getOwner();
            if(owner!=pathProfile.actor||unit->GetID()!=pathProfile.unit)++pathProfile.actorMismatch;
            else
            {
                const bool dirty=GET_PLAYER(owner).GetDangerPlots()->IsDirty();if(dirty)++pathProfile.dirty;
                const int target=plot->GetPlotIndex(),hp=unit->GetCurrHitPoints(),maxHP=unit->GetMaxHitPoints();
                const long scene=CvStackingStrengthCache::SceneEpoch();
                unsigned slot=((unsigned)target*2654435761UL)&(PATH_REPEAT_SLOTS-1),probe=0;
                for(;probe<PATH_REPEAT_PROBES;++probe,slot=(slot+1)&(PATH_REPEAT_SLOTS-1))
                {
                    PathRepeatSlot& seen=pathProfile.seen[slot];
                    if(seen.used&&seen.plot!=target)continue;
                    ++pathProfile.tracked;
                    if(seen.used) { ++pathProfile.repeats;if(!dirty&&seen.scene==scene&&seen.hp==hp&&seen.maxHP==maxHP)++pathProfile.samePhysicalRepeats; }
                    seen.used=true;seen.plot=target;seen.scene=scene;seen.hp=hp;seen.maxHP=maxHP;break;
                }
                if(probe==PATH_REPEAT_PROBES)++pathProfile.untracked;
            }
        }
        else if(value==PATH_RAW_DANGER)++pathProfile.untracked;
        const unsigned long phase=(pathProfile.phase+(unsigned long)value*7UL)&(PATH_CALL_STRIDE-1);
        if((count.calls+phase)&(PATH_CALL_STRIDE-1))return;
        if(pathProfile.epoch!=ReadPlanSampleEpoch()) { pathProfile.enabled=false;return; }
        ++count.selected;LARGE_INTEGER now;++pathProfile.clockReads;
        if(!QueryPerformanceCounter(&now)||now.QuadPart<0) { ++pathProfile.clockFailures;return; }
        serial=pathProfile.serial;epoch=pathProfile.epoch;started=(unsigned __int64)now.QuadPart;threadState=&pathProfile;sampled=true;
    }
    void PathProfileScope::FinishSampled()
    {
        if(!sampled||threadState!=&pathProfile)return;sampled=false;
        if(!pathProfile.enabled||pathProfile.depth!=1||pathProfile.serial!=serial||pathProfile.epoch!=epoch||epoch!=ReadPlanSampleEpoch())return;
        LARGE_INTEGER now;++pathProfile.clockReads;
        if(!QueryPerformanceCounter(&now)||now.QuadPart<0||(unsigned __int64)now.QuadPart<started) { ++pathProfile.clockFailures;return; }
        PlanSampleCounter& count=pathProfile.counter[part];const unsigned __int64 duration=(unsigned __int64)now.QuadPart-started;
        ++count.samples;count.ticks+=duration;if(duration>count.maximum)count.maximum=duration;
    }
    // END PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY
'''
new[names[0]]=new[names[0]].replace('class CvCombatInfo;','class CvCombatInfo;\nclass CvUnit;\nclass CvPlot;',1).replace('    // The last contiguous entry interval',header+'    // The last contiguous entry interval',1)
new[names[1]]=new[names[1]].replace('#include "CvStackingRules.h"','#include "CvStackingRules.h"\n#include "CvStackingStrengthCache.h" // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY\n#include "CvDangerPlots.h" // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY',1)
new[names[1]]=new[names[1]].replace('    struct EntryCosts',globals+'    struct EntryCosts',1).replace('    UpdateBoundaryScope::UpdateBoundaryScope(',methods+'    UpdateBoundaryScope::UpdateBoundaryScope(',1).replace(' || !strcmp(category,"PLAN_SAMPLE")',' || !strcmp(category,"PATH_SAMPLE") || !strcmp(category,"PLAN_SAMPLE")',1)
cpp=new[names[2]].replace('#include "CvAStar.h"','#include "CvAStar.h"\n#include "CvStackingDiagnostics.h" // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY',1)
cpp=cpp.replace('\tSanitizeFlags();\n\tReset();','\tSanitizeFlags();\n\tReset();\n\tCvStackingDiagnostics::PathProfileSession pathProfileSession(m_sData.ePlayer,m_sData.iUnitID,m_sData.ePath,m_iCurrentGenerationID,m_sData.iFlags,iXstart,iYstart,iXdest,iYdest,false); // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY',1)
cpp=cpp.replace('\tif (kToNodeCacheData.iGenerationID==finder->GetCurrentGenerationID())\n\t\treturn;','\tif (kToNodeCacheData.iGenerationID==finder->GetCurrentGenerationID())\n\t{\n\t\tCvStackingDiagnostics::CountPathNodeCache(true); // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY\n\t\treturn;\n\t}\n\tCvStackingDiagnostics::CountPathNodeCache(false); // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY',1)
cpp=cpp.replace('\t\tint iPlotDanger = pUnit->GetDanger(pToPlot);','\t\tCvStackingDiagnostics::PathProfileScope dangerProfile(CvStackingDiagnostics::PATH_RAW_DANGER,pUnit,pToPlot); // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY\n\t\tint iPlotDanger = pUnit->GetDanger(pToPlot);\n\t\tdangerProfile.Finish(); // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY',1)
cpp=cpp.replace('bool canEnterTerritoryAndTerrain(const CvUnit* pUnit, const CvPlot* pPlot, int iMoveFlags)\n{','bool canEnterTerritoryAndTerrain(const CvUnit* pUnit, const CvPlot* pPlot, int iMoveFlags)\n{\n\tCvStackingDiagnostics::PathProfileScope terrainProfile(CvStackingDiagnostics::PATH_CLEAR_TERRAIN); // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY',1)
cpp=cpp.replace('\tm_sData = path.sConfig;\n\tif (udInitializeFunc)','\tm_sData = path.sConfig;\n\tCvStackingDiagnostics::PathProfileSession pathProfileSession(m_sData.ePlayer,m_sData.iUnitID,m_sData.ePath,m_iCurrentGenerationID,m_sData.iFlags,path.vPlots.front().x,path.vPlots.front().y,path.vPlots.back().x,path.vPlots.back().y,true); // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY\n\tif (udInitializeFunc)',1)
new[names[2]]=cpp
patch=[];proof={}
for n in names:
 assert new[n]!=old[n];(OUT/n).write_text(new[n],encoding='utf-8',newline='')
 patch+=difflib.unified_diff(old[n].splitlines(True),new[n].splitlines(True),fromfile='a/CvGameCoreDLL_Expansion2/'+n,tofile='b/CvGameCoreDLL_Expansion2/'+n)
 proof[n]=dict(control_sha256=hashlib.sha256(old[n].encode()).hexdigest(),stage_sha256=hashlib.sha256(new[n].encode()).hexdigest())
for name in ('profile-turn-phases.py','profile-phase-cpu.py'):
 path=ROOT/'work'/name;before=path.read_text(encoding='utf-8-sig');after=before
 if name=='profile-turn-phases.py':after=after.replace('"PLAN_PACKET_PROBE")','"PLAN_PACKET_PROBE", "PATH_SAMPLE")',1)
 after=after.replace('excluding TURN_PHASE/TURN_UPDATE_GAP/PLAN_PACKET_PROBE','excluding TURN_PHASE/TURN_UPDATE_GAP/PLAN_PACKET_PROBE/PATH_SAMPLE').replace('excluding TURN_PHASE/TURN_UPDATE_GAP from','excluding TURN_PHASE/TURN_UPDATE_GAP/PLAN_PACKET_PROBE/PATH_SAMPLE from')
 (OUT/name).write_text(after,encoding='utf-8',newline='');assert before!=after
 patch+=difflib.unified_diff(before.splitlines(True),after.splitlines(True),fromfile='a/work/'+name,tofile='b/work/'+name)
 proof['work/'+name]=dict(control_sha256=hashlib.sha256(before.encode()).hexdigest(),stage_sha256=hashlib.sha256(after.encode()).hexdigest(),change='legacy_anchor_category_and_wording_only')
(OUT/'path-profile.patch').write_text(''.join(patch),encoding='utf-8',newline='')
(OUT/'proof.json').write_text(json.dumps(dict(control=CONTROL,files=proof,production_applied=False,result_reuse=False,query_stride=8,call_stride=16,bounded_repeat_slots=128),indent=2)+'\n',encoding='utf-8')
print('Prepared work-only path query profile; no production edits/build.')
