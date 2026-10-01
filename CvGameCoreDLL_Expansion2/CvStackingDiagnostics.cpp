#include "CvGameCoreDLLPCH.h"
#include "CvStackingDiagnostics.h"
#include "CvStackingRules.h"
#include "CvStackingStrengthCache.h" // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY
#include "CvDangerPlots.h" // PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY
#include "CvPlayerAI.h"
#include "CvTeam.h"
#include "CvUnit.h"
#include "CvCity.h"
#include "CvPlot.h"
#include "CvMap.h"
#include "CvArmyAI.h"
#include "CvAIOperation.h"
#include "CvGameCoreStructs.h"
#include "../commit_id.inc"
#include <cstdio>
#include <cstdarg>
#include <share.h>
#include <string>
#include "LintFree.h"

namespace
{
    struct Sync { CRITICAL_SECTION value; Sync() { InitializeCriticalSection(&value); } ~Sync() { DeleteCriticalSection(&value); } } sync;
    struct Lock { Lock() { EnterCriticalSection(&sync.value); } ~Lock() { LeaveCriticalSection(&sync.value); } };
    struct Option { const char* name; int fallback, value; } options[] = {
        {"DiagnosticsLevel",0,0}, {"DiagnosticsSummaryInterval",1,1}, {"DiagnosticsDetailInterval",10,10},
        {"DiagnosticsMemoryInterval",10,10}, {"DiagnosticsPlayer",-1,-1}, {"DiagnosticsMaxFileKB",4096,4096},
        {"DiagnosticsMaxFiles",8,8}, {"DiagnosticsMaxRowsPerTurn",4096,4096}, {"DiagnosticsHistogramMaxStack",32,32},
        {"DiagnosticsImmediateFlush",0,0}, {"DiagnosticsBufferKB",64,64}, {"DiagnosticsFlushEveryRows",256,256}, {"DiagnosticsFlushIntervalMilliseconds",1000,1000}, {"DiagnosticsCategoryMask",63,63}, {"DiagnosticsVerboseStartTurn",-1,-1}, {"DiagnosticsVerboseEndTurn",-1,-1}, {"DiagnosticsCombatSummary",1,1}, {"DiagnosticsPerformanceInterval",1,1}, {"DiagnosticsTacticalSampling",0,0}
    };
    struct Costs
    {
        unsigned __int64 recorded, dropped, bytes;
        unsigned int flushes;
        DWORD formatMs, writeMs, flushMs;
        Costs():recorded(0),dropped(0),bytes(0),flushes(0),formatMs(0),writeMs(0),flushMs(0){}
    } costs, passCosts[MAX_PLAYERS];
    DWORD passStarted[MAX_PLAYERS] = {0};
    int passTurn[MAX_PLAYERS];
    char fileBuffer[256*1024]; // Fixed maximum; configured active buffer is 4-256 KiB.
    unsigned int pendingWrites=0;
    DWORD lastFlush=0;
    bool optionsLoaded = false;
    int level = -1, rowTurn = -1, rows = 0, memoryTurn = -1;
    int playerTurn[MAX_PLAYERS];
    int playerAfterTurn[MAX_PLAYERS];
    bool initialized = false, suppressed = false, failed = false;
    FILE* output = NULL;
    unsigned int sequence = 0, runCounter = 0, combatCounter = 0;
    unsigned long phaseGeneration = 0;
    // BEGIN PLAN_SAMPLE_DIAGNOSTIC_ONLY
    const unsigned long PLAN_SAMPLE_STRIDE = 4096;
    // Sparse expensive parents need denser samples; dense leaf/key/math probes
    // retain their existing cadence. These values only affect diagnostics.
    const unsigned long PLAN_SAMPLE_STRIDES[CvStackingDiagnostics::PLAN_SAMPLE_PARTS] =
        {4096,4096,4096,4096,4096,256,256,4096,64,4096,4096,4096,4096};
    int tacticalSamplingOverride = -1;
    struct PlanSampleCounter
    {
        unsigned __int64 calls, selected, samples, ticks, maximum;
    };
    struct PlanSampleState
    {
        bool enabled;
        unsigned int depth;
        unsigned long serial, generation, thread, phase;
        PlayerTypes actor;
        int turn, target;
        long epoch;
        unsigned __int64 frequency, clockReads, clockFailures;
        PlanSampleCounter counter[CvStackingDiagnostics::PLAN_SAMPLE_PARTS];
    };
    // POD TLS is also used by GetStatus. A UI/foreign thread cannot read or
    // update an owning search's counters, and nested searches are suppressed.
    static __declspec(thread) PlanSampleState planSamples = {};
    static __declspec(thread) unsigned long planSampleSerial = 0;
    __declspec(align(4)) volatile LONG planSampleEpoch = 0;
    long ReadPlanSampleEpoch() { return InterlockedCompareExchange(&planSampleEpoch,0,0); }
    void InvalidatePlanSampleEpoch() { InterlockedIncrement(&planSampleEpoch); }
    // END PLAN_SAMPLE_DIAGNOSTIC_ONLY
    // BEGIN PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY
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
    struct EntryCosts
    {
        int turn;
        unsigned long thread, generation;
        unsigned int calls, busyReturns, cpuMeasured;
        unsigned __int64 hookMs, guardMs, hookCPU100ns, guardCPU100ns;
        unsigned long maxHookMs, maxGuardMs;
        EntryCosts():turn(-1),thread(0),generation(0),calls(0),busyReturns(0),cpuMeasured(0),
            hookMs(0),guardMs(0),hookCPU100ns(0),guardCPU100ns(0),maxHookMs(0),maxGuardMs(0){}
    } entryCosts[MAX_PLAYERS];
    enum { GAP_ACTIVATION=4, GAP_HEAD=5, GAP_PARTS=6 };
    struct GapCost
    {
        bool open, cpuAvailable;
        unsigned long started;
        unsigned __int64 cpuStarted, milliseconds, cpu100ns;
        unsigned int calls, cpuMeasured;
        GapCost():open(false),cpuAvailable(false),started(0),cpuStarted(0),milliseconds(0),cpu100ns(0),calls(0),cpuMeasured(0){}
    };
    struct PendingUpdateGap
    {
        bool active, cpuAvailable, lastExit, lastExitCPUAvailable, clippedWrapperStart;
        PlayerTypes actor;
        int turn;
        unsigned long started, thread, generation, serial, lastExitTick, maximumDispatchMs;
        unsigned __int64 cpuStarted, lastExitCPU, dispatchMs, dispatchCPU100ns;
        unsigned int dispatchCalls, dispatchCPUMeasured, nestedScopes;
        unsigned int coreLockAttempts, coreLockCompleted, coreLockCPUMeasured;
        unsigned long maximumCoreLockMs;
        unsigned __int64 coreLockMs, coreLockCPU100ns;
        GapCost part[GAP_PARTS];
        PendingUpdateGap():active(false),cpuAvailable(false),lastExit(false),lastExitCPUAvailable(false),clippedWrapperStart(false),
            actor(NO_PLAYER),turn(-1),started(0),thread(0),generation(0),serial(0),lastExitTick(0),maximumDispatchMs(0),
            cpuStarted(0),lastExitCPU(0),dispatchMs(0),dispatchCPU100ns(0),dispatchCalls(0),dispatchCPUMeasured(0),nestedScopes(0),
            coreLockAttempts(0),coreLockCompleted(0),coreLockCPUMeasured(0),maximumCoreLockMs(0),coreLockMs(0),coreLockCPU100ns(0){}
    } updateGap;
    unsigned int updateDepth[4]={0,0,0,0};
    unsigned long updateThread=0, updateSerial=0;
    bool updateHeadOpen=false;
    unsigned int configHash = 0;
    unsigned long bytesWritten = 0;
    wchar_t directory[MAX_PATH] = L"";
    char prefix[96] = "", status[1024] = "Off";

    int setting(const char* name, int fallback)
    {
        if (!optionsLoaded) { optionsLoaded = true; for (size_t i=0;i<sizeof(options)/sizeof(options[0]);++i) options[i].value=CvStacking::GetInt(options[i].name,options[i].fallback); }
        for (size_t i=0;i<sizeof(options)/sizeof(options[0]);++i) if (!strcmp(name,options[i].name)) return options[i].value;
        return fallback;
    }
    bool threadCPU100ns(unsigned __int64& value)
    {
        FILETIME created,exited,kernel,user;
        if(!GetThreadTimes(GetCurrentThread(),&created,&exited,&kernel,&user)) return false;
        value=((unsigned __int64)kernel.dwHighDateTime<<32)|kernel.dwLowDateTime;
        value+=((unsigned __int64)user.dwHighDateTime<<32)|user.dwLowDateTime;
        return true;
    }
    void dropEntryCosts(PlayerTypes player,int turn,unsigned long thread,unsigned long generation)
    {
        if(player<0 || player>=MAX_PLAYERS) return;
        EntryCosts& entry=entryCosts[player];
        if(entry.turn==turn && entry.thread==thread && entry.generation==generation) entry=EntryCosts();
    }
    void closeFile()
    {
        if(output)
        {
            FILE* closing=output; output=NULL;
            const DWORD start=GetTickCount();
            const int result=fflush(closing); ++costs.flushes;
            costs.flushMs+=GetTickCount()-start;
            fclose(closing);
            if(result) { failed=true; strcpy_s(status,sizeof(status),"Logging unavailable: flush failed"); }
        }
        pendingWrites=0;
    }
    void fail(const char* message)
    {
        closeFile(); failed = true;
        _snprintf_s(status, sizeof(status), _TRUNCATE, "Logging unavailable: %s", message);
    }
    bool flushOutput(bool force)
    {
        if(!output || !pendingWrites) return true;
        const DWORD now=GetTickCount();
        const int interval=setting("DiagnosticsFlushIntervalMilliseconds",1000);
        if(!force && pendingWrites<(unsigned int)setting("DiagnosticsFlushEveryRows",256) &&
            (!interval || now-lastFlush<(DWORD)interval)) return true;
        const int result=fflush(output); ++costs.flushes;
        costs.flushMs+=GetTickCount()-now;
        pendingWrites=0; lastFlush=now;
        if(result) { fail("flush failed"); return false; }
        return true;
    }
    int categoryBit(const char* category)
    {
        if(!strcmp(category,"SUMMARY") || !strcmp(category,"HISTOGRAM") || !strcmp(category,"UNIT") ||
            !strcmp(category,"CITY") || !strncmp(category,"SAMPLE_",7) || !strncmp(category,"DECISION_",9) || !strcmp(category,"UNIT_DECISION")) return 1;
        if(!strncmp(category,"COMBAT_",7) || !strcmp(category,"CITY_CAPTURE")) return 8;
        if(!strcmp(category,"MEMORY")) return 32;
        if(!strcmp(category,"DIAGNOSTIC_COST") || !strcmp(category,"PLAN_PERF") || !strcmp(category,"TURN_PHASE") || !strcmp(category,"TURN_UPDATE_GAP") || !strcmp(category,"PATH_SAMPLE") || !strcmp(category,"PLAN_SAMPLE") || !strcmp(category,"PLAN_PACKET_PROBE")) return 16; // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
        if(!strncmp(category,"PLAN",4) || !strncmp(category,"RECRUIT",7) || !strcmp(category,"LONG_PLAN") || !strcmp(category,"ATTACK_GATE")) return 4;
        return 2;
    }
    int getLevelUnlocked()
    {
        if(!initialized)
        {
            for(int i=0;i<MAX_PLAYERS;++i) { playerTurn[i]=playerAfterTurn[i]=passTurn[i]=-1; passStarted[i]=0; }
            initialized=true;
        }
        if(level<0) level=setting("DiagnosticsLevel",0);
        return level;
    }
    bool enabledUnlocked(int required,PlayerTypes player)
    {
        if(getLevelUnlocked()<required || failed) return false;
        const int filter=setting("DiagnosticsPlayer",-1);
        if(player!=NO_PLAYER && filter>=0 && player!=filter) return false;
        if(required>=2)
        {
            const int turn=GC.getGame().getGameTurn(),first=setting("DiagnosticsVerboseStartTurn",-1),last=setting("DiagnosticsVerboseEndTurn",-1);
            if((first>=0 && turn<first) || (last>=0 && turn>last)) return false;
        }
        return true;
    }
    bool categoryEnabledUnlocked(int required,PlayerTypes player,const char* category)
    {
        if(!enabledUnlocked(required,player)) return false;
        // Safety anomalies remain available regardless of the selected evidence family.
        if(!strcmp(category,"LONG_PLAN") || !strncmp(category,"ANOMALY",7)) return true;
        return (setting("DiagnosticsCategoryMask",63)&categoryBit(category))!=0;
    }
    bool updateTimingEnabled(PlayerTypes player)
    {
        if(!categoryEnabledUnlocked(1,player,"TURN_UPDATE_GAP")) return false;
        const int interval=setting("DiagnosticsPerformanceInterval",1);
        return interval>0 && GC.getGame().getGameTurn()%interval==0;
    }
    void clearUpdateGapState()
    {
        updateGap=PendingUpdateGap();updateThread=0;updateHeadOpen=false;
        for(int i=0;i<4;++i) updateDepth[i]=0;
    }
    bool validUpdateGap()
    {
        if(!updateGap.active) return false;
        if(updateGap.generation!=phaseGeneration || updateGap.turn!=GC.getGame().getGameTurn() ||
            !updateTimingEnabled(updateGap.actor))
        { updateGap=PendingUpdateGap();return false; }
        // Another thread must neither time nor consume this pending activation.
        return updateGap.thread==GetCurrentThreadId();
    }
    void updateGapSample(unsigned long& tick,unsigned __int64& cpu,bool& available)
    {
        tick=GetTickCount();cpu=0;
        available=updateGap.cpuAvailable && threadCPU100ns(cpu) && cpu>=updateGap.cpuStarted;
        if(!available) updateGap.cpuAvailable=false;
    }
    void startGapPart(int part,unsigned long tick,unsigned __int64 cpu,bool available)
    {
        GapCost& cost=updateGap.part[part];
        if(cost.open) return;
        cost.open=true;cost.started=tick;cost.cpuStarted=cpu;cost.cpuAvailable=available;++cost.calls;
    }
    void finishGapPart(int part,unsigned long tick,unsigned __int64 cpu,bool available)
    {
        GapCost& cost=updateGap.part[part];
        if(!cost.open) return;
        cost.open=false;cost.milliseconds+=tick-cost.started;
        if(cost.cpuAvailable && available && cpu>=cost.cpuStarted)
        { ++cost.cpuMeasured;cost.cpu100ns+=cpu-cost.cpuStarted; }
    }
    void finishUpdateGapAtEntry(PlayerTypes player)
    {
        if(updateGap.active && updateGap.actor==player && updateGap.thread!=GetCurrentThreadId())
        { updateGap=PendingUpdateGap();return; }
        if(!validUpdateGap() || updateGap.actor!=player) return;
        unsigned long ended=0;unsigned __int64 cpuEnded=0;bool available=false;
        updateGapSample(ended,cpuEnded,available);
        for(int i=0;i<GAP_PARTS;++i) finishGapPart(i,ended,cpuEnded,available);
        const PendingUpdateGap gap=updateGap;
        updateGap=PendingUpdateGap(); // Entry/reentrant/busy calls consume once, before search.
        CvStackingDiagnostics::Record(1,gap.actor,"TURN_UPDATE_GAP",
            "startTick=%lu endTick=%lu elapsedMs=%lu thread=%lu cpuAvailable=%d cpuStart100ns=%I64u cpuEnd100ns=%I64u cpu100ns=%I64u semantics=activation_to_first_unit_entry totals=inclusive_overlapping_not_phase_bounds "
            "wrapperCalls=%u wrapperMs=%I64u wrapperCPU100ns=%I64u wrapperCPUMeasured=%u wrapperClippedStart=%d "
            "gameCalls=%u gameMs=%I64u gameCPU100ns=%I64u gameCPUMeasured=%u "
            "activationTailCalls=%u activationTailMs=%I64u activationTailCPU100ns=%I64u activationTailCPUMeasured=%u "
            "beginHookCalls=%u beginHookMs=%I64u beginHookCPU100ns=%I64u beginHookCPUMeasured=%u "
            "endHookCalls=%u endHookMs=%I64u endHookCPU100ns=%I64u endHookCPUMeasured=%u "
            "preMovesHeadCalls=%u preMovesHeadMs=%I64u preMovesHeadCPU100ns=%I64u preMovesHeadCPUMeasured=%u "
            "dispatchCalls=%u dispatchMs=%I64u dispatchCPU100ns=%I64u dispatchCPUMeasured=%u maximumDispatchMs=%lu nestedScopes=%u "
            "coreLockAttempts=%u coreLockCompleted=%u coreLockMs=%I64u coreLockCPU100ns=%I64u coreLockCPUMeasured=%u maximumCoreLockMs=%lu; wrapper and game totals include their child hooks/tails; dispatch is between measured wrapper calls, not proof of a particular engine wait; coreLock is a completed constructor acquisition envelope including diagnostic overhead and can overlap dispatch/body totals",
            gap.started,ended,ended-gap.started,gap.thread,available?1:0,available?gap.cpuStarted:0,available?cpuEnded:0,available?cpuEnded-gap.cpuStarted:0,
            gap.part[0].calls,gap.part[0].milliseconds,gap.part[0].cpu100ns,gap.part[0].cpuMeasured,gap.clippedWrapperStart?1:0,
            gap.part[1].calls,gap.part[1].milliseconds,gap.part[1].cpu100ns,gap.part[1].cpuMeasured,
            gap.part[GAP_ACTIVATION].calls,gap.part[GAP_ACTIVATION].milliseconds,gap.part[GAP_ACTIVATION].cpu100ns,gap.part[GAP_ACTIVATION].cpuMeasured,
            gap.part[2].calls,gap.part[2].milliseconds,gap.part[2].cpu100ns,gap.part[2].cpuMeasured,
            gap.part[3].calls,gap.part[3].milliseconds,gap.part[3].cpu100ns,gap.part[3].cpuMeasured,
            gap.part[GAP_HEAD].calls,gap.part[GAP_HEAD].milliseconds,gap.part[GAP_HEAD].cpu100ns,gap.part[GAP_HEAD].cpuMeasured,
            gap.dispatchCalls,gap.dispatchMs,gap.dispatchCPU100ns,gap.dispatchCPUMeasured,gap.maximumDispatchMs,gap.nestedScopes,
            gap.coreLockAttempts,gap.coreLockCompleted,gap.coreLockMs,gap.coreLockCPU100ns,gap.coreLockCPUMeasured,gap.maximumCoreLockMs);
    }
    bool openSegment()
    {
        closeFile();
        if(failed) return false;
        wchar_t path[MAX_PATH];
        const unsigned int slot = sequence % setting("DiagnosticsMaxFiles", 8);
        if (_snwprintf_s(path, MAX_PATH, _TRUNCATE, L"%s%S-%02u.log", directory, prefix, slot) < 0)
        { fail("log filename is too long"); return false; }
        output = _wfsopen(path, L"wb", _SH_DENYWR);
        if (!output) { fail("cannot open log file"); return false; }
        const bool immediate=setting("DiagnosticsImmediateFlush",0)!=0;
        const size_t bufferBytes=(size_t)max(4,min(256,setting("DiagnosticsBufferKB",64)))*1024;
        if(setvbuf(output,immediate?NULL:fileBuffer,immediate?_IONBF:_IOFBF,immediate?0:bufferBytes))
        { fail("cannot configure bounded file buffer"); return false; }
        pendingWrites=0; lastFlush=GetTickCount();
        bytesWritten = 0;
        char narrow[768];
        if (!WideCharToMultiByte(CP_UTF8, 0, path, -1, narrow, sizeof(narrow), NULL, NULL))
            strcpy_s(narrow, sizeof(narrow), prefix);
        _snprintf_s(status, sizeof(status), _TRUNCATE, "%s (segment %u; rolling %d files)", narrow, sequence, setting("DiagnosticsMaxFiles", 8));
        const int written = fprintf(output, "STACKDIAG|SESSION|schema=1 run=%s segment=%u build=%s level=%d configFNV=%08X\n", prefix, sequence, CURRENT_GAMECORE_VERSION, level, configHash);
        if (written < 0) { fail("write failed"); return false; }
        bytesWritten += written; costs.bytes+=written; ++pendingWrites;
        return true;
    }
    bool ensureFile()
    {
        if (failed) return false;
        if (output) return true;
        if (prefix[0] && directory[0]) { ++sequence; return openSegment(); }
        // Obtain the engine-selected Logs directory; do not assume Documents is local.
        FILogFile* locator = LOGFILEMGR.GetLog("StackingDiagnostics-path.log", FILogFile::kDontTimeStamp);
        if (!locator || !locator->GetFileName()) { fail("engine Logs path is unavailable"); return false; }
        wchar_t path[MAX_PATH];
        const DWORD length = GetFullPathNameW(locator->GetFileName(), MAX_PATH, path, NULL);
        if (!length || length >= MAX_PATH) { fail("invalid Logs path"); return false; }
        wchar_t* slash = wcsrchr(path, L'\\');
        if (!slash) { fail("invalid Logs directory"); return false; }
        slash[1] = 0; wcscpy_s(directory, MAX_PATH, path);
        SYSTEMTIME now; GetSystemTime(&now); ++runCounter; sequence = 0;
        _snprintf_s(prefix, sizeof(prefix), _TRUNCATE, "Stacking-%04u%02u%02uT%02u%02u%02u-%03u-p%lu-r%u",
            now.wYear, now.wMonth, now.wDay, now.wHour, now.wMinute, now.wSecond, now.wMilliseconds, GetCurrentProcessId(), runCounter);
        return openSegment();
    }
    void writeLine(int turn, int player, const char* category, const char* message)
    {
        if (!ensureFile()) return;
        const unsigned long limit = (unsigned long)setting("DiagnosticsMaxFileKB", 4096) * 1024;
        if (bytesWritten + strlen(message) + 160 > limit) { ++sequence; if (!openSegment()) return; }
        const DWORD start=GetTickCount();
        int written = fprintf(output, "STACKDIAG|%lu|turn=%d|player=%d|%s|%s\n", start, turn, player, category, message);
        costs.writeMs+=GetTickCount()-start;
        if(written<0) { fail("write failed"); return; }
        bytesWritten+=written; costs.bytes+=written; ++pendingWrites;
        flushOutput(setting("DiagnosticsImmediateFlush",0)!=0 || !strcmp(category,"LONG_PLAN") || !strncmp(category,"ANOMALY",7));
    }
    void configHeader()
    {
        Database::Connection* db = GC.GetGameDatabase();
        if (!db) return;
        const char* queries[] = {
            "SELECT 'setting:'||Name AS K, CAST(Value AS TEXT) AS V FROM Stacking_Settings ORDER BY Name",
            "SELECT 'tech:'||TechType AS K, CAST(CapacityBonus AS TEXT) AS V FROM Stacking_Technologies ORDER BY TechType",
            "SELECT 'combat:'||UnitCombatType||':'||Role AS K, CAST(Value AS TEXT) AS V FROM Stacking_UnitCombatRoles ORDER BY UnitCombatType,Role",
            "SELECT 'class:'||UnitClassType||':'||Role AS K, CAST(Value AS TEXT) AS V FROM Stacking_UnitClassRoles ORDER BY UnitClassType,Role",
            "SELECT 'unit:'||UnitType||':'||Role AS K, CAST(Value AS TEXT) AS V FROM Stacking_UnitRoles ORDER BY UnitType,Role",
            "SELECT 'promotion:'||PromotionType||':'||Role AS K, CAST(Value AS TEXT) AS V FROM Stacking_PromotionRoles ORDER BY PromotionType,Role",
            "SELECT 'buildingclass:'||BuildingClassType AS K, CAST(ProtectionPercent AS TEXT) AS V FROM Stacking_BuildingClassProtection ORDER BY BuildingClassType",
            "SELECT 'building:'||BuildingType AS K, CAST(ProtectionPercent AS TEXT) AS V FROM Stacking_BuildingProtection ORDER BY BuildingType",
            "SELECT 'domain:'||DomainType AS K, CAST(Enabled AS TEXT) AS V FROM Stacking_CollateralDomains ORDER BY DomainType"
        };
        unsigned int hash = 2166136261U;
        for (size_t i = 0; i < sizeof(queries)/sizeof(queries[0]); ++i)
        {
            Database::Results data;
            if (!db->Execute(data, queries[i])) continue;
            while (data.Step())
            {
                const char* key = data.GetText("K"); const char* value = data.GetText("V");
                if (!key || !value) continue;
                std::string row = std::string(key) + "=" + value;
                for (size_t j = 0; j < row.size(); ++j) { hash ^= (unsigned char)row[j]; hash *= 16777619U; }
                hash ^= '\n'; hash *= 16777619U;
                writeLine(GC.getGame().getGameTurn(), -1, "CONFIG_RAW", row.c_str());
            }
        }
        configHash = hash;
        char message[384];
        _snprintf_s(message, sizeof(message), _TRUNCATE, "fnv1a=%08X map=%dx%d effectiveLevel=%d summaryEvery=%d detailEvery=%d playerFilter=%d; raw XML rows above, DLL validation/clamping still applies",
            hash, GC.getMap().getGridWidth(), GC.getMap().getGridHeight(), level,
            setting("DiagnosticsSummaryInterval", 1), setting("DiagnosticsDetailInterval", 10), setting("DiagnosticsPlayer", -1));
        writeLine(GC.getGame().getGameTurn(), -1, "CONFIG", message);
        flushOutput(true);
    }
    void memorySample(int turn)
    {
        const int interval = setting("DiagnosticsMemoryInterval", 10);
        if (!interval || turn % interval || memoryTurn == turn || !categoryEnabledUnlocked(1,NO_PLAYER,"MEMORY")) return;
        memoryTurn = turn;
        SYSTEM_INFO sys; GetSystemInfo(&sys);
        SIZE_T address = (SIZE_T)sys.lpMinimumApplicationAddress, largest = 0;
        unsigned __int64 committed = 0, reserved = 0, freeBytes = 0;
        while (address < (SIZE_T)sys.lpMaximumApplicationAddress)
        {
            MEMORY_BASIC_INFORMATION info;
            if (!VirtualQuery((LPCVOID)address, &info, sizeof(info))) break;
            if (info.State == MEM_COMMIT) committed += info.RegionSize;
            else if (info.State == MEM_RESERVE) reserved += info.RegionSize;
            else if (info.State == MEM_FREE) { freeBytes += info.RegionSize; largest = max(largest, info.RegionSize); }
            SIZE_T next = (SIZE_T)info.BaseAddress + info.RegionSize;
            if (next <= address) break;
            address = next;
        }
        CvStackingDiagnostics::Record(1, NO_PLAYER, "MEMORY", "committedKB=%I64u reservedKB=%I64u freeKB=%I64u largestFreeKB=%Iu", committed/1024, reserved/1024, freeBytes/1024, largest/1024);
    }
}

namespace CvStackingDiagnostics
{
    void Reset()
    {
        Lock lock;
        ++phaseGeneration;
        InvalidatePlanSampleEpoch(); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
        tacticalSamplingOverride=-1; // PLAN_SAMPLE_DIAGNOSTIC_ONLY
        clearUpdateGapState();
        closeFile(); level = -1; rowTurn = -1; memoryTurn = -1; rows = 0;
        initialized = false; failed = false; suppressed = false; optionsLoaded = false;
        prefix[0] = 0; directory[0] = 0; configHash = 0;
        costs=Costs(); pendingWrites=0; lastFlush=0;
        for(int i=0;i<MAX_PLAYERS;++i) entryCosts[i]=EntryCosts();
        strcpy_s(status, sizeof(status), "Off (XML default applies on next use)");
    }
    int GetLevel()
    {
        Lock lock;
        return getLevelUnlocked();
    }
    bool Enabled(int required, PlayerTypes player)
    {
        Lock lock;
        return enabledUnlocked(required,player);
    }
    bool EnabledCategory(int required,PlayerTypes player,const char* category)
    { Lock lock; return categoryEnabledUnlocked(required,player,category); }
    void Flush()
    { Lock lock; flushOutput(true); }
    const char* GetStatus()
    {
        Lock lock;
        static __declspec(thread) char copy[1024];
        getLevelUnlocked();
        strcpy_s(copy, sizeof(copy), level > 0 && !output && !failed ? "Enabled; waiting for the next unit-AI update" : status);
        return copy;
    }
    void SetLevel(int value)
    {
        Lock lock;
        if (value < 0 || value > 2) return;
        ++phaseGeneration;
        InvalidatePlanSampleEpoch(); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
        clearUpdateGapState();
        getLevelUnlocked();
        if (output) writeLine(GC.getGame().getGameTurn(), -1, "LEVEL", value == 0 ? "off" : value == 1 ? "summary" : "verbose");
        if (!value) { closeFile(); strcpy_s(status, sizeof(status), "Off"); }
        level = value; failed = false;
        for (int i = 0; i < MAX_PLAYERS; ++i) { playerTurn[i]=playerAfterTurn[i]=passTurn[i]=-1; entryCosts[i]=EntryCosts(); }
        if (value && ensureFile()) configHeader();
    }
    void Record(int required, PlayerTypes player, const char* category, const char* format, ...)
    {
        Lock lock;
        if (!categoryEnabledUnlocked(required, player, category)) return;
        const int turn = GC.getGame().getGameTurn();
        if (rowTurn != turn) { rowTurn = turn; rows = 0; suppressed = false; }
        if (rows >= setting("DiagnosticsMaxRowsPerTurn", 4096))
        {
            ++costs.dropped;
            if (!suppressed) { suppressed = true; writeLine(turn, -1, "TRUNCATED", "per-turn diagnostic row budget reached; see DIAGNOSTIC_COST for dropped counts"); flushOutput(true); }
            return;
        }
        ++rows; ++costs.recorded;
        const DWORD formatStart=GetTickCount();
        char text[3072]; va_list args; va_start(args, format);
        const int result = _vsnprintf_s(text, sizeof(text), _TRUNCATE, format, args); va_end(args);
        for (char* p = text; *p; ++p) if (*p == '\n' || *p == '\r') *p = ' ';
        if (result < 0) strcpy_s(text + sizeof(text) - 24, 24, " [message truncated]");
        costs.formatMs+=GetTickCount()-formatStart;
        const bool opening = output == NULL;
        if (!ensureFile()) return;
        if (opening) configHeader();
        writeLine(turn, player, category, text);
    }
    TurnPhaseScope::TurnPhaseScope(PlayerTypes player,const char* phase):
        active(false),cpuAvailable(false),actor(player),name(phase),turn(-1),started(0),thread(0),generation(0),cpuStarted(0)
    {
        Lock lock;
        if(!phase || !categoryEnabledUnlocked(1,player,"TURN_PHASE")) return;
        const int interval=setting("DiagnosticsPerformanceInterval",1);
        if(interval<=0) return;
        turn=GC.getGame().getGameTurn();
        if(turn%interval) return;
        generation=phaseGeneration;
        thread=GetCurrentThreadId();
        started=GetTickCount();
        cpuAvailable=threadCPU100ns(cpuStarted);
        active=true;
    }
    TurnPhaseScope::~TurnPhaseScope()
    { Finish(); }
    void TurnPhaseScope::Finish()
    {
        if(!active) return;
        active=false; // Explicit Finish followed by destruction records once.
        Lock lock;
        if(generation!=phaseGeneration || turn!=GC.getGame().getGameTurn() || thread!=GetCurrentThreadId() ||
            !categoryEnabledUnlocked(1,actor,"TURN_PHASE")) return;
        const unsigned long ended=GetTickCount();
        unsigned __int64 cpuEnded=0;
        cpuAvailable=cpuAvailable && threadCPU100ns(cpuEnded) && cpuEnded>=cpuStarted;
        Record(1,actor,"TURN_PHASE","phase=%s startTick=%lu endTick=%lu elapsedMs=%lu thread=%lu cpuAvailable=%d cpuStart100ns=%I64u cpuEnd100ns=%I64u cpu100ns=%I64u semantics=inclusive cpuSemantics=inclusive_same_thread; nested TURN_PHASE and PLAN intervals overlap; do not sum all phase wall or CPU durations as a round",name,started,ended,ended-started,thread,cpuAvailable?1:0,cpuAvailable?cpuStarted:0,cpuAvailable?cpuEnded:0,cpuAvailable?cpuEnded-cpuStarted:0);
    }
    // BEGIN PLAN_SAMPLE_DIAGNOSTIC_ONLY
    void SetTacticalSamplingEnabled(bool enabled)
    {
        Lock lock;
        tacticalSamplingOverride=enabled?1:0;
        InvalidatePlanSampleEpoch();
    }
    bool GetTacticalSamplingEnabled()
    {
        Lock lock;
        return tacticalSamplingOverride>=0 ? tacticalSamplingOverride!=0 : setting("DiagnosticsTacticalSampling",0)!=0;
    }
    // BEGIN PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
    bool TryGetPlanSamplingContext(unsigned long& serial,long& epoch)
    {
        // TLS/epoch reads only; no settings, lock, clock or thread-ID syscall.
        if(!planSamples.enabled||planSamples.depth!=1||planSamples.epoch!=ReadPlanSampleEpoch())return false;
        serial=planSamples.serial;epoch=planSamples.epoch;return true;
    }
    // END PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
    PlanSampleSession::PlanSampleSession(PlayerTypes player,int targetPlotIndex):entered(true),outer(false),serial(0),threadState(&planSamples)
    {
        if(planSamples.depth++)
        {
            serial=planSamples.serial;
            return;
        }
        outer=true;
        serial=++planSampleSerial;
        if(!serial) serial=++planSampleSerial;
        planSamples.serial=serial;
        planSamples.enabled=false;
        Lock lock;
        if(!(tacticalSamplingOverride>=0 ? tacticalSamplingOverride!=0 : setting("DiagnosticsTacticalSampling",0)!=0)) return;
        if(!categoryEnabledUnlocked(1,player,"PLAN_SAMPLE")) return;
        const int interval=setting("DiagnosticsPerformanceInterval",1);
        if(interval<=0 || GC.getGame().getGameTurn()%interval || !gDLL->HasGameCoreLock()) return;
        LARGE_INTEGER frequency;
        if(!QueryPerformanceFrequency(&frequency) || frequency.QuadPart<=0) return;
        memset(planSamples.counter,0,sizeof(planSamples.counter));
        planSamples.generation=phaseGeneration;
        planSamples.thread=GetCurrentThreadId();
        planSamples.actor=player;
        planSamples.turn=GC.getGame().getGameTurn();
        planSamples.target=targetPlotIndex;
        planSamples.epoch=ReadPlanSampleEpoch();
        // Rotate repeated targets by the outer TLS serial, without gameplay RNG.
        planSamples.phase=((unsigned long)targetPlotIndex*1664525UL+serial*2246822519UL+1013904223UL)&(PLAN_SAMPLE_STRIDE-1);
        planSamples.frequency=(unsigned __int64)frequency.QuadPart;
        planSamples.clockReads=planSamples.clockFailures=0;
        planSamples.enabled=true;
    }
    PlanSampleSession::~PlanSampleSession()
    {
        if(!entered || threadState!=&planSamples || planSamples.serial!=serial || !planSamples.depth) return;
        if(--planSamples.depth || !outer) return;
        const bool enabled=planSamples.enabled;
        planSamples.enabled=false;
        if(!enabled) return;
        Lock lock;
        if(planSamples.epoch!=ReadPlanSampleEpoch() || planSamples.generation!=phaseGeneration ||
            planSamples.thread!=GetCurrentThreadId() || planSamples.turn!=GC.getGame().getGameTurn() ||
            !categoryEnabledUnlocked(1,planSamples.actor,"PLAN_SAMPLE")) return;
        // One bounded row per outer search, including early returns/unwinding.
        // Lists share the fixed part ordering below; durations overlap.
        char calls[384]="",selected[384]="",samples[384]="",ticks[384]="",maximum[384]="",strides[96]="",phases[96]="";
        size_t a=0,b=0,c=0,d=0,e=0,f=0,g=0;
        for(int i=0;i<PLAN_SAMPLE_PARTS;++i)
        {
            const PlanSampleCounter& part=planSamples.counter[i];
            const unsigned long stride=PLAN_SAMPLE_STRIDES[i];
            const unsigned long phase=(planSamples.phase+(unsigned long)i*97UL)&(stride-1);
            f+=sprintf_s(strides+f,sizeof(strides)-f,"%s%lu",i?",":"",stride);
            g+=sprintf_s(phases+g,sizeof(phases)-g,"%s%lu",i?",":"",phase);
            a+=sprintf_s(calls+a,sizeof(calls)-a,"%s%I64u",i?",":"",part.calls);
            b+=sprintf_s(selected+b,sizeof(selected)-b,"%s%I64u",i?",":"",part.selected);
            c+=sprintf_s(samples+c,sizeof(samples)-c,"%s%I64u",i?",":"",part.samples);
            d+=sprintf_s(ticks+d,sizeof(ticks)-d,"%s%I64u",i?",":"",part.ticks);
            e+=sprintf_s(maximum+e,sizeof(maximum)-e,"%s%I64u",i?",":"",part.maximum);
        }
        Record(1,planSamples.actor,"PLAN_SAMPLE","targetPlot=%d serial=%lu thread=%lu stride=%lu phase=%lu cadenceVersion=2 strides=%s phases=%s qpcFrequency=%I64u qpcFrequencyCalls=1 qpcReads=%I64u clockFailures=%I64u parts=combatMove,turnEnd,stackScore,unitDanger,dangerKey,dangerLeaf,preferred,moveUpdate,nextAssignments,citySimulation,unitSimulation,damageMath,randomDamageMath calls=%s selected=%s samples=%s ticks=%s maxTicks=%s semantics=inclusive_same_thread_wall_samples overlap=parent_child_not_additive lifecycle=outer_return_or_unwind; raw ticks require frequency conversion; stride estimates are approximate and systematic samples can alias work; dangerKey includes lookup, dangerLeaf is scalar-miss/outcome-resolution excluding admission; no native CPU-share claim",
            planSamples.target,serial,planSamples.thread,PLAN_SAMPLE_STRIDE,planSamples.phase,strides,phases,planSamples.frequency,
            planSamples.clockReads,planSamples.clockFailures,calls,selected,samples,ticks,maximum);
    }
    PlanSampleScope::PlanSampleScope(PlanSamplePart value,bool eligible):sampled(false),part(value),serial(0),epoch(0),started(0),threadState(NULL)
    {
        if(!eligible || !planSamples.enabled || planSamples.depth!=1 || value<0 || value>=PLAN_SAMPLE_PARTS) return;
        PlanSampleCounter& count=planSamples.counter[value];
        ++count.calls;
        const unsigned long stride=PLAN_SAMPLE_STRIDES[value];
        const unsigned long phase=(planSamples.phase+(unsigned long)value*97UL)&(stride-1);
        if((count.calls+phase)&(stride-1)) return;
        if(planSamples.epoch!=ReadPlanSampleEpoch()) { planSamples.enabled=false; return; }
        ++count.selected;
        LARGE_INTEGER now;
        ++planSamples.clockReads;
        if(!QueryPerformanceCounter(&now) || now.QuadPart<0) { ++planSamples.clockFailures; return; }
        serial=planSamples.serial;
        epoch=planSamples.epoch;
        started=(unsigned __int64)now.QuadPart;
        threadState=&planSamples;
        sampled=true;
    }
    void PlanSampleScope::FinishSampled()
    {
        if(!sampled || threadState!=&planSamples) return;
        sampled=false;
        if(!planSamples.enabled || planSamples.depth!=1 || planSamples.serial!=serial ||
            planSamples.epoch!=epoch || epoch!=ReadPlanSampleEpoch()) return;
        LARGE_INTEGER now;
        ++planSamples.clockReads;
        if(!QueryPerformanceCounter(&now) || now.QuadPart<0 || (unsigned __int64)now.QuadPart<started)
        { ++planSamples.clockFailures; return; }
        PlanSampleCounter& count=planSamples.counter[part];
        const unsigned __int64 duration=(unsigned __int64)now.QuadPart-started;
        ++count.samples;
        count.ticks+=duration;
        if(duration>count.maximum) count.maximum=duration;
    }
    // END PLAN_SAMPLE_DIAGNOSTIC_ONLY
    // BEGIN PATH_QUERY_PROFILE_DIAGNOSTIC_ONLY
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
    UpdateBoundaryScope::UpdateBoundaryScope(UpdateBoundaryPart value):active(false),part(value),thread(0),generation(0)
    {
        Lock lock;
        if(value<UPDATE_WRAPPER || value>UPDATE_END_HOOK || !updateTimingEnabled(NO_PLAYER)) return;
        thread=GetCurrentThreadId();generation=phaseGeneration;
        bool any=false;for(int i=0;i<4;++i) any=any || updateDepth[i]!=0;
        if(any && updateThread!=thread) return;
        updateThread=thread;
        const bool outer=updateDepth[part]++==0;
        active=true;
        if(part==UPDATE_GAME && outer) updateHeadOpen=true;
        if(!validUpdateGap()) return;
        if(!outer) { ++updateGap.nestedScopes;return; }
        unsigned long tick=0;unsigned __int64 cpu=0;bool available=false;
        updateGapSample(tick,cpu,available);
        if(part==UPDATE_WRAPPER && updateGap.lastExit)
        {
            const unsigned long elapsed=tick-updateGap.lastExitTick;
            ++updateGap.dispatchCalls;updateGap.dispatchMs+=elapsed;
            updateGap.maximumDispatchMs=max(updateGap.maximumDispatchMs,elapsed);
            if(available && updateGap.lastExitCPUAvailable && cpu>=updateGap.lastExitCPU)
            { ++updateGap.dispatchCPUMeasured;updateGap.dispatchCPU100ns+=cpu-updateGap.lastExitCPU; }
            updateGap.lastExit=false;
        }
        startGapPart(part,tick,cpu,available);
        if(part==UPDATE_GAME) startGapPart(GAP_HEAD,tick,cpu,available);
    }
    UpdateBoundaryScope::~UpdateBoundaryScope()
    {
        if(!active) return;
        Lock lock;
        if(generation!=phaseGeneration || thread!=GetCurrentThreadId() || updateThread!=thread || updateDepth[part]==0) return;
        const bool outer=--updateDepth[part]==0;
        if(!outer) return;
        if(part==UPDATE_GAME) updateHeadOpen=false;
        if(!validUpdateGap()) return;
        unsigned long tick=0;unsigned __int64 cpu=0;bool available=false;
        updateGapSample(tick,cpu,available);
        finishGapPart(part,tick,cpu,available);
        if(part==UPDATE_GAME) finishGapPart(GAP_HEAD,tick,cpu,available);
        if(part==UPDATE_WRAPPER)
        { updateGap.lastExit=true;updateGap.lastExitTick=tick;updateGap.lastExitCPU=cpu;updateGap.lastExitCPUAvailable=available; }
    }
    void BeforeUpdateMoves()
    {
        Lock lock;
        if(updateDepth[UPDATE_GAME]!=1 || updateThread!=GetCurrentThreadId()) return;
        updateHeadOpen=false;
        if(!validUpdateGap() || !updateGap.part[GAP_HEAD].open) return;
        unsigned long tick=0;unsigned __int64 cpu=0;bool available=false;
        updateGapSample(tick,cpu,available);finishGapPart(GAP_HEAD,tick,cpu,available);
    }
    CoreLockAcquireScope::CoreLockAcquireScope():active(false),cpuAvailable(false),serial(0),thread(0),generation(0),started(0),cpuStarted(0)
    {
        // No GC, category, setting, database or engine calls before acquisition.
        // The pending marker already established the diagnostic sampling policy.
        Lock lock;
        if(!updateGap.active || failed || updateGap.generation!=phaseGeneration) return;
        thread=GetCurrentThreadId();
        if(updateGap.thread!=thread) return;
        serial=updateGap.serial;generation=phaseGeneration;
        ++updateGap.coreLockAttempts;
        started=GetTickCount();cpuAvailable=updateGap.cpuAvailable && threadCPU100ns(cpuStarted);
        active=true;
        // This diagnostic lock is released before the caller acquires GameCore.
    }
    void CoreLockAcquireScope::Complete()
    {
        if(!active) return;
        active=false;
        Lock lock;
        if(generation!=phaseGeneration || serial!=updateGap.serial || thread!=GetCurrentThreadId() || !validUpdateGap()) return;
        // Called only after the unchanged engine acquisition returned successfully.
        const unsigned long ended=GetTickCount(),elapsed=ended-started;
        unsigned __int64 cpuEnded=0;
        const bool available=cpuAvailable && threadCPU100ns(cpuEnded) && cpuEnded>=cpuStarted;
        ++updateGap.coreLockCompleted;updateGap.coreLockMs+=elapsed;
        updateGap.maximumCoreLockMs=max(updateGap.maximumCoreLockMs,elapsed);
        if(available) { ++updateGap.coreLockCPUMeasured;updateGap.coreLockCPU100ns+=cpuEnded-cpuStarted; }
    }
    ActivationTailScope::ActivationTailScope():active(false),serial(0),thread(0),generation(0){}
    void ActivationTailScope::Start(PlayerTypes player,bool eligible)
    {
        if(active || !eligible || player<0 || player>=MAX_PLAYERS) return;
        Lock lock;
        if(!updateTimingEnabled(player)) return;
        updateGap=PendingUpdateGap();updateGap.active=true;updateGap.actor=player;
        updateGap.turn=GC.getGame().getGameTurn();updateGap.generation=generation=phaseGeneration;
        updateGap.thread=thread=GetCurrentThreadId();
        updateGap.serial=serial=++updateSerial;
        updateGap.started=GetTickCount();updateGap.cpuAvailable=threadCPU100ns(updateGap.cpuStarted);
        startGapPart(GAP_ACTIVATION,updateGap.started,updateGap.cpuStarted,updateGap.cpuAvailable);
        if(updateThread==thread)
        {
            for(int i=0;i<4;++i) if(updateDepth[i]) startGapPart(i,updateGap.started,updateGap.cpuStarted,updateGap.cpuAvailable);
            if(updateDepth[UPDATE_GAME] && updateHeadOpen) startGapPart(GAP_HEAD,updateGap.started,updateGap.cpuStarted,updateGap.cpuAvailable);
            updateGap.clippedWrapperStart=updateDepth[UPDATE_WRAPPER]!=0;
        }
        active=true;
    }
    ActivationTailScope::~ActivationTailScope()
    {
        if(!active) return;
        Lock lock;
        if(generation!=phaseGeneration || thread!=GetCurrentThreadId() || updateGap.serial!=serial || !validUpdateGap()) return;
        unsigned long tick=0;unsigned __int64 cpu=0;bool available=false;
        updateGapSample(tick,cpu,available);finishGapPart(GAP_ACTIVATION,tick,cpu,available);
    }
    UnitAIEntryScope::UnitAIEntryScope(PlayerTypes player):active(false),hookDone(false),cpuAvailable(false),actor(player),
        turn(-1),started(0),hookEnded(0),thread(0),generation(0),cpuStarted(0),cpuHookEnded(0)
    {
        Lock lock;
        if(player<0 || player>=MAX_PLAYERS || !categoryEnabledUnlocked(1,player,"TURN_PHASE")) return;
        const int interval=setting("DiagnosticsPerformanceInterval",1);
        if(interval<=0) return;
        turn=GC.getGame().getGameTurn();
        if(turn%interval) return;
        finishUpdateGapAtEntry(player);
        generation=phaseGeneration;thread=GetCurrentThreadId();started=GetTickCount();
        cpuAvailable=threadCPU100ns(cpuStarted);active=true;
    }
    UnitAIEntryScope::~UnitAIEntryScope()
    {
        if(!active) return;
        // An exception/unfinished entry must not leave earlier busy polls to
        // be reported as part of an apparently complete processing window.
        Lock lock;dropEntryCosts(actor,turn,thread,generation);
    }
    void UnitAIEntryScope::HookFinished()
    {
        if(!active || hookDone) return;
        Lock lock;
        if(generation!=phaseGeneration || turn!=GC.getGame().getGameTurn() || thread!=GetCurrentThreadId() ||
            !categoryEnabledUnlocked(1,actor,"TURN_PHASE"))
        { dropEntryCosts(actor,turn,thread,generation);active=false;return; }
        hookEnded=GetTickCount();cpuAvailable=cpuAvailable && threadCPU100ns(cpuHookEnded) && cpuHookEnded>=cpuStarted;
        hookDone=true;
    }
    void UnitAIEntryScope::Finish(bool busy)
    {
        if(!active) return;
        active=false;
        Lock lock;
        if(!hookDone || generation!=phaseGeneration || turn!=GC.getGame().getGameTurn() || thread!=GetCurrentThreadId() ||
            !categoryEnabledUnlocked(1,actor,"TURN_PHASE"))
        { dropEntryCosts(actor,turn,thread,generation);return; }
        const unsigned long ended=GetTickCount();
        unsigned __int64 cpuEnded=0;
        cpuAvailable=cpuAvailable && threadCPU100ns(cpuEnded) && cpuEnded>=cpuHookEnded;
        EntryCosts& entry=entryCosts[actor];
        if(entry.turn!=turn || entry.thread!=thread || entry.generation!=generation) entry=EntryCosts();
        entry.turn=turn;entry.thread=thread;entry.generation=generation;
        const unsigned long hookMs=hookEnded-started,guardMs=ended-hookEnded;
        ++entry.calls;entry.busyReturns+=busy?1:0;entry.hookMs+=hookMs;entry.guardMs+=guardMs;
        entry.maxHookMs=max(entry.maxHookMs,hookMs);entry.maxGuardMs=max(entry.maxGuardMs,guardMs);
        if(cpuAvailable)
        { ++entry.cpuMeasured;entry.hookCPU100ns+=cpuHookEnded-cpuStarted;entry.guardCPU100ns+=cpuEnded-cpuHookEnded; }
        if(busy) return;
        Record(1,actor,"TURN_PHASE","phase=unit_ai_entry startTick=%lu endTick=%lu elapsedMs=%lu thread=%lu cpuAvailable=%d cpuStart100ns=%I64u cpuEnd100ns=%I64u cpu100ns=%I64u semantics=inclusive cpuSemantics=inclusive_same_thread entryCalls=%u busyReturns=%u aggregateHookMs=%I64u aggregateGuardMs=%I64u maxHookMs=%lu maxGuardMs=%lu aggregateCPUAvailable=%d aggregateCPUMeasuredCalls=%u aggregateHookCPU100ns=%I64u aggregateGuardCPU100ns=%I64u; bounds cover last contiguous entry only; aggregates sum completed entry spans since last real pass and may overlap nested calls; do not union aggregate totals as phase bounds",
            started,ended,ended-started,thread,cpuAvailable?1:0,cpuAvailable?cpuStarted:0,cpuAvailable?cpuEnded:0,cpuAvailable?cpuEnded-cpuStarted:0,entry.calls,entry.busyReturns,
            entry.hookMs,entry.guardMs,entry.maxHookMs,entry.maxGuardMs,entry.cpuMeasured==entry.calls?1:0,entry.cpuMeasured,entry.hookCPU100ns,entry.guardCPU100ns);
        entry=EntryCosts();
    }
    void OnPlayerTurn(CvPlayer& player)
    {
        Lock lock;
        const PlayerTypes owner = player.GetID();
        if (!enabledUnlocked(1, owner)) return;
        const int turn = GC.getGame().getGameTurn();
        if (playerTurn[owner] == turn) return;
        playerTurn[owner] = turn;
        flushOutput(true);
        memorySample(turn);
        const int interval = setting("DiagnosticsSummaryInterval", 1);
        if(turn%interval || !categoryEnabledUnlocked(1,owner,"SUMMARY"))
        { passTurn[owner]=turn; passStarted[owner]=GetTickCount(); passCosts[owner]=costs; return; }
        const DWORD start = GetTickCount();
        Record(1, owner, "SAMPLE_BEGIN", "phase=before_unit_AI");
        int units = 0, combat = 0, ranged = 0, wounded = 0, illegal = 0, hp = 0, cities = 0;
        // Fixed diagnostic workspace: no allocation proportional to the world or turn count.
        int histogram[2][257] = {{0}};
        const int histogramLimit = setting("DiagnosticsHistogramMaxStack",32);
        int stacked = 0, maximum = 0, unprotected = 0, over = 0;
        const int detailInterval = setting("DiagnosticsDetailInterval", 10);
        const bool detail = Enabled(2, owner) && detailInterval && turn % detailInterval == 0;
        int loop = 0;
        for (CvUnit* unit = player.firstUnit(&loop); unit; unit = player.nextUnit(&loop))
        {
            if (unit->isDelayedDeath()) continue;
            ++units; hp += unit->GetCurrHitPoints(); wounded += unit->getDamage() > 0;
            CvPlot* plot = unit->plot();
            const bool counted = plot && unit->IsCombatUnit() && !unit->IsStackingUnit() && !unit->isCargo() && unit->getDomainType() != DOMAIN_AIR;
            int cap = plot && (counted || detail) ? unit->GetStackingLimit(plot) : -1, legal = -1;
            if (counted)
            {
                ++combat; ranged += unit->IsCanAttackRanged(); legal = unit->CanStackUnitAtPlot(plot) ? 1 : 0; illegal += legal == 0;
                int groupCount=0, groupRanged=0, groupMelee=0, firstID=unit->GetID(), groupCap=cap;
                for (int j=0;j<plot->getNumUnits();++j)
                {
                    const CvUnit* member=plot->getUnitByIndex(j);
                    if (!member || member->getOwner()!=owner || member->getDomainType()!=unit->getDomainType() || !member->IsCombatUnit() || member->IsStackingUnit() || member->isCargo() || member->isDelayedDeath()) continue;
                    firstID=min(firstID,member->GetID());
                }
                if (unit->GetID()==firstID)
                {
                    for(int j=0;j<plot->getNumUnits();++j)
                    {
                        const CvUnit* member=plot->getUnitByIndex(j);
                        if(!member || member->getOwner()!=owner || member->getDomainType()!=unit->getDomainType() || !member->IsCombatUnit() || member->IsStackingUnit() || member->isCargo() || member->isDelayedDeath()) continue;
                        ++groupCount; groupCap=min(groupCap,member->GetStackingLimit(plot));
                        if(!member->isEmbarked()) { if(member->IsCanAttackRanged()) ++groupRanged; else ++groupMelee; }
                    }
                    stacked+=groupCount>=2; maximum=max(maximum,groupCount); over+=groupCount>groupCap;
                    if (!groupMelee) unprotected+=groupRanged;
                    ++histogram[unit->getDomainType()==DOMAIN_SEA?1:0][min(groupCount,histogramLimit)];
                }
            }
            if (detail || legal == 0)
                Record(1, owner, detail ? "UNIT" : "ANOMALY_UNIT", "id=%d type=%d x=%d y=%d domain=%d hp=%d maxHP=%d moves=%d cap=%d legal=%d counted=%d ranged=%d antiCav=%d flank=%d collateral=%d cargo=%d embarked=%d army=%d",
                    unit->GetID(), unit->getUnitType(), unit->getX(), unit->getY(), unit->getDomainType(), unit->GetCurrHitPoints(), unit->GetMaxHitPoints(), unit->getMoves(), cap, legal, counted,
                    unit->IsCanAttackRanged(), CvStacking::IsAntiCavalry(unit), CvStacking::CanFlank(unit), CvStacking::GetCollateralTargetLimit(unit), unit->isCargo(), unit->isEmbarked(), unit->getArmyID());
        }
        for (CvCity* city = player.firstCity(&loop); city; city = player.nextCity(&loop))
        {
            ++cities;
            if (detail) { const CvUnit* garrison = city->GetGarrisonedUnit(); Record(2, owner, "CITY", "id=%d x=%d y=%d damage=%d maxHP=%d population=%d garrison=%d protection=%d", city->GetID(), city->getX(), city->getY(), city->getDamage(), city->GetMaxHitPoints(), city->getPopulation(), garrison ? garrison->GetID() : -1, CvStacking::GetCityProtection(city)); }
        }
        Record(1, owner, "SUMMARY", "units=%d countedCombat=%d ranged=%d hp=%d wounded=%d cities=%d stackTiles=%d maxStack=%d illegal=%d overCap=%d rangedWithoutMelee=%d; composition is not a danger prediction", units, combat, ranged, hp, wounded, cities, stacked, maximum, illegal, over, unprotected);
        for (int domain=0;domain<2;++domain) for (int size=1;size<=histogramLimit;++size) if (histogram[domain][size])
            Record(1, owner, "HISTOGRAM", "domain=%d size=%d overflowBucket=%d plots=%d", domain?DOMAIN_SEA:DOMAIN_LAND, size, size==histogramLimit, histogram[domain][size]);
        Record(1, owner, "SAMPLE_END", "elapsedMs=%lu", GetTickCount() - start);
        flushOutput(true);
        passTurn[owner]=turn; passStarted[owner]=GetTickCount(); passCosts[owner]=costs;
    }

    void AfterPlayerUnitAI(CvPlayer& player)
    {
        Lock lock;
        const PlayerTypes owner=player.GetID();
        if (!enabledUnlocked(1,owner)) return;
        const int turn=GC.getGame().getGameTurn();
        if (playerAfterTurn[owner]==turn) return;
        playerAfterTurn[owner]=turn;
        const DWORD finished=GetTickCount(); const Costs passEnd=costs;
        const bool sampledTurn=turn%setting("DiagnosticsSummaryInterval",1)==0;
        const bool sample=sampledTurn && categoryEnabledUnlocked(1,owner,"SUMMARY");
        const int interval=setting("DiagnosticsDetailInterval",10);
        const bool detail=Enabled(2,owner) && interval && turn%interval==0;
        int loop=0,combat=0,inCities=0,inArmies=0,idle=0;
        for (CvUnit* unit=sample?player.firstUnit(&loop):NULL;unit;unit=player.nextUnit(&loop))
        {
            if (unit->isDelayedDeath() || !unit->IsCombatUnit()) continue;
            ++combat; inCities+=unit->plot() && unit->plot()->isCity(); inArmies+=unit->getArmyID()!=-1;
            const bool unassigned=unit->getArmyID()==-1 && !unit->IsHurt() && unit->getTacticalMove()==AI_TACTICAL_MOVE_NONE &&
                (unit->getHomelandMove()==AI_HOMELAND_MOVE_NONE || unit->getHomelandMove()==AI_HOMELAND_MOVE_UNASSIGNED);
            idle+=unassigned;
            if (detail) Record(2,owner,"UNIT_DECISION","unit=%d plot=%d hp=%d moves=%d processed=%d army=%d garrison=%d tactical=%d homeland=%d unassigned=%d",unit->GetID(),unit->plot()?unit->plot()->GetPlotIndex():-1,unit->GetCurrHitPoints(),unit->getMoves(),unit->TurnProcessed(),unit->getArmyID(),unit->IsGarrisoned(),unit->getTacticalMove(),unit->getHomelandMove(),unassigned);
        }
        if(sample) Record(1,owner,"DECISION_SUMMARY","phase=after_first_unit_AI_pass combat=%d inCities=%d inArmies=%d healthyUnassigned=%d; counts can overlap and unfinished animations may cause later passes",combat,inCities,inArmies,idle);
        if(sampledTurn && categoryEnabledUnlocked(1,owner,"OPERATION_STATUS"))
            for(size_t i=0;i<player.getNumAIOperations();++i)
            {
                CvAIOperation* op=player.getAIOperationByIndex(i);
                if(!op) continue;
                CvArmyAI* army=op->GetArmy(0); CvPlot* target=op->GetTargetPlot(); CvPlot* muster=op->GetMusterPlot();
                Record(1,owner,"OPERATION_STATUS","operation=%d type=%d state=%d enemy=%d target=%d muster=%d army=%d filled=%d slots=%d neededBuild=%d training=%d age=%d",
                    op->GetID(),op->GetOperationType(),op->GetOperationState(),op->GetEnemy(),target?target->GetPlotIndex():-1,muster?muster->GetPlotIndex():-1,
                    army?army->GetID():-1,army?(int)army->GetNumSlotsFilled():0,army?(int)army->GetNumFormationEntries():0,
                    (int)op->GetNumUnitsNeededToBeBuilt(),(int)op->GetNumUnitsCommittedToBeBuilt(),turn-op->GetTurnStarted());
            }
        const int perfInterval=setting("DiagnosticsPerformanceInterval",1);
        if(perfInterval && turn%perfInterval==0 && passTurn[owner]==turn && categoryEnabledUnlocked(1,owner,"DIAGNOSTIC_COST"))
        {
            const Costs& before=passCosts[owner]; char message[512];
            _snprintf_s(message,sizeof(message),_TRUNCATE,"phase=first_unit_AI_pass elapsedMs=%lu recorded=%I64u dropped=%I64u bytes=%I64u flushes=%u formatMs=%lu writeMs=%lu flushMs=%lu; logger counters exclude snapshots and this row; tick timing is coarse",
                finished-passStarted[owner],passEnd.recorded-before.recorded,passEnd.dropped-before.dropped,passEnd.bytes-before.bytes,passEnd.flushes-before.flushes,
                passEnd.formatMs-before.formatMs,passEnd.writeMs-before.writeMs,passEnd.flushMs-before.flushMs);
            writeLine(turn,owner,"DIAGNOSTIC_COST",message);
        }
        flushOutput(true);
    }
    void CombatScope::AddUnit(int owner, int id, const char* role, int rolledDamage)
    {
        if (owner < 0 || owner >= MAX_PLAYERS || id < 0 || count >= 35) return;
        CvUnit* unit = GET_PLAYER((PlayerTypes)owner).getUnit(id);
        if (!unit) return;
        if(detailed) Record(2, actor, "COMBAT_MEMBER", "combat=%u role=%s owner=%d id=%d hpBefore=%d maxHP=%d damageKind=%s rolledDamage=%d x=%d y=%d", serial, role, owner, id, unit->GetCurrHitPoints(), unit->GetMaxHitPoints(), !strcmp(role,"secondary_or_garrison") ? "received" : "inflicted", rolledDamage, unit->getX(), unit->getY());
        for (int i = 0; i < count; ++i) if (owners[i] == owner && ids[i] == id) return;
        owners[count] = owner; ids[count] = id; health[count] = unit->GetCurrHitPoints(); ++count;
    }
    CombatScope::CombatScope(const CvCombatInfo& info, unsigned int eventID) : active(false), detailed(false), compact(false),
        attackingOwner(-1), cityOwnerBefore(-1), cityIDBefore(-1), cityHPBefore(-1), cityProtectionBefore(0),
        attackingUnitID(-1), attackingCityID(-1), defendingOwner(-1), defendingUnitID(-1), defendingCityID(-1),
        primaryDamage(0), retaliationDamage(0), bystanderCount(0), bystanderDamage(0), ranged(false), bombing(false),
        serial(0), actor(NO_PLAYER), plotIndex(-1), count(0)
    {
        Lock lock;
        if(getLevelUnlocked()<1) return;
        const CvUnit* attacker = info.getUnit(BATTLE_UNIT_ATTACKER);
        const CvCity* attackingCity = info.getCity(BATTLE_UNIT_ATTACKER);
        const CvUnit* defendingUnit = info.getUnit(BATTLE_UNIT_DEFENDER);
        const CvCity* defendingCity = info.getCity(BATTLE_UNIT_DEFENDER);
        attackingUnitID=attacker?attacker->GetID():-1;
        attackingCityID=attackingCity?attackingCity->GetID():-1;
        defendingOwner=defendingUnit?defendingUnit->getOwner():defendingCity?defendingCity->getOwner():-1;
        defendingUnitID=defendingUnit?defendingUnit->GetID():-1;
        defendingCityID=defendingCity?defendingCity->GetID():-1;
        actor = attacker ? attacker->getOwner() : attackingCity ? attackingCity->getOwner() : NO_PLAYER;
        attackingOwner=actor;
        const int filter=setting("DiagnosticsPlayer",-1);
        if(filter>=0 && actor!=filter)
        {
            bool involved=false;
            for(int i=0;i<BATTLE_UNIT_COUNT;++i)
            {
                const CvUnit* unit=info.getUnit((BattleUnitTypes)i); const CvCity* city=info.getCity((BattleUnitTypes)i);
                involved|=(unit && unit->getOwner()==filter) || (city && city->getOwner()==filter);
            }
            for(int i=0;i<info.getDamageMemberCount() && !involved;++i) involved=info.getDamageMembers()[i].GetPlayer()==filter;
            if(!involved) return;
            actor=(PlayerTypes)filter; // Include incoming attacks involving the filtered player.
        }
        detailed=categoryEnabledUnlocked(2,actor,"COMBAT_BEGIN");
        compact=setting("DiagnosticsCombatSummary",1)!=0 && categoryEnabledUnlocked(1,actor,"COMBAT_SUMMARY");
        if(!detailed && !compact) return;
        active=true; serial=++combatCounter;
        primaryDamage=info.getDamageInflicted(BATTLE_UNIT_ATTACKER); retaliationDamage=info.getDamageInflicted(BATTLE_UNIT_DEFENDER);
        ranged=info.getAttackIsRanged(); bombing=info.getAttackIsBombingMission();
        const CvPlot* plot = info.getPlot(); plotIndex = plot ? plot->GetPlotIndex() : -1;
        if(detailed) Record(2, actor, "COMBAT_BEGIN", "combat=%u parent=%u x=%d y=%d ranged=%d bombing=%d primaryDamage=%d retaliation=%d members=%d advance=%d", serial, eventID, plot ? plot->getX() : -1, plot ? plot->getY() : -1, info.getAttackIsRanged(), info.getAttackIsBombingMission(), info.getDamageInflicted(BATTLE_UNIT_ATTACKER), info.getDamageInflicted(BATTLE_UNIT_DEFENDER), info.getDamageMemberCount(), info.getAttackerAdvances());
        for (int i = 0; i < BATTLE_UNIT_COUNT; ++i)
        {
            const CvUnit* unit = info.getUnit((BattleUnitTypes)i);
            if (unit) AddUnit(unit->getOwner(), unit->GetID(), i == BATTLE_UNIT_ATTACKER ? "attacker" : i == BATTLE_UNIT_DEFENDER ? "defender" : "interceptor", info.getDamageInflicted((BattleUnitTypes)i));
        }
        for (int i = 0; i < info.getDamageMemberCount(); ++i)
        {
            const CvCombatMemberEntry& member = info.getDamageMembers()[i];
            if(member.IsUnit())
            { ++bystanderCount; bystanderDamage+=member.GetDamage(); AddUnit(member.GetPlayer(),member.GetID(),"secondary_or_garrison",member.GetDamage()); }
        }
        if(plot && plot->isCity())
        {
            const CvCity* city=plot->getPlotCity();
            cityOwnerBefore=city->getOwner(); cityIDBefore=city->GetID(); cityHPBefore=city->GetMaxHitPoints()-city->getDamage(); cityProtectionBefore=CvStacking::GetCityProtection(city);
            if(detailed) Record(2,actor,"COMBAT_CITY_BEFORE","combat=%u owner=%d id=%d damage=%d maxHP=%d protection=%d",serial,cityOwnerBefore,cityIDBefore,city->getDamage(),city->GetMaxHitPoints(),cityProtectionBefore);
        }
        if(detailed) flushOutput(true); // Preserve the detailed pre-resolution bracket for crash investigations.
    }
    CombatScope::~CombatScope()
    {
        Lock lock;
        if (!active) return;
        int missing=0; long long healthLost=0;
        // Resolve combat may delete/capture units: look up saved identities, never reuse raw pointers.
        for (int i = 0; i < count; ++i)
        {
            const CvUnit* unit = GET_PLAYER((PlayerTypes)owners[i]).getUnit(ids[i]);
            if(unit) healthLost+=max(0,health[i]-unit->GetCurrHitPoints()); else ++missing;
            if(detailed) Record(2, actor, "COMBAT_AFTER", "combat=%u owner=%d id=%d present=%d delayedDeath=%d hpBefore=%d hpAfter=%d x=%d y=%d", serial, owners[i], ids[i], unit != NULL, unit ? unit->isDelayedDeath() : 0, health[i], unit ? unit->GetCurrHitPoints() : 0, unit ? unit->getX() : -1, unit ? unit->getY() : -1);
        }
        CvPlot* plot = plotIndex >= 0 ? GC.getMap().plotByIndexUnchecked(plotIndex) : NULL;
        int cityOwnerAfter=-1,cityHPAfter=-1;
        if(plot && plot->isCity())
        {
            const CvCity* city=plot->getPlotCity(); const CvUnit* garrison=city->GetGarrisonedUnit();
            cityOwnerAfter=city->getOwner(); cityHPAfter=city->GetMaxHitPoints()-city->getDamage();
            if(detailed) Record(2,actor,"COMBAT_CITY_AFTER","combat=%u owner=%d id=%d damage=%d garrison=%d",serial,cityOwnerAfter,city->GetID(),city->getDamage(),garrison?garrison->GetID():-1);
            if(cityOwnerBefore>=0 && cityOwnerAfter!=cityOwnerBefore)
                Record(1,actor,"CITY_CAPTURE","combat=%u plot=%d oldOwner=%d newOwner=%d oldCity=%d newCity=%d",serial,plotIndex,cityOwnerBefore,cityOwnerAfter,cityIDBefore,city->GetID());
        }
        if(compact) Record(1,actor,"COMBAT_SUMMARY","combat=%u plot=%d attackerOwner=%d attackerUnit=%d attackerCity=%d defenderOwner=%d defenderUnit=%d defenderCity=%d ranged=%d bombing=%d rolledPrimary=%d rolledRetaliation=%d bystanders=%d bystanderRolledDamage=%I64d hpLostPresent=%I64d missingUnits=%d cityBeforeOwner=%d cityAfterOwner=%d cityHPBefore=%d cityHPAfter=%d protectionBefore=%d; bystanders include ordinary garrison absorption; missing is not a death claim",
            serial,plotIndex,attackingOwner,attackingUnitID,attackingCityID,defendingOwner,defendingUnitID,defendingCityID,ranged,bombing,primaryDamage,retaliationDamage,bystanderCount,bystanderDamage,healthLost,missing,cityOwnerBefore,cityOwnerAfter,cityHPBefore,cityHPAfter,cityProtectionBefore);
        if(detailed) Record(2,actor,"COMBAT_END","combat=%u",serial);
        flushOutput(true);
    }
}
