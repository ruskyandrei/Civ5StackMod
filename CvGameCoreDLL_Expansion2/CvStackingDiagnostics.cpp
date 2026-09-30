#include "CvGameCoreDLLPCH.h"
#include "CvStackingDiagnostics.h"
#include "CvStackingRules.h"
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
        {"DiagnosticsImmediateFlush",0,0}, {"DiagnosticsBufferKB",64,64}, {"DiagnosticsFlushEveryRows",256,256}, {"DiagnosticsFlushIntervalMilliseconds",1000,1000}, {"DiagnosticsCategoryMask",63,63}, {"DiagnosticsVerboseStartTurn",-1,-1}, {"DiagnosticsVerboseEndTurn",-1,-1}, {"DiagnosticsCombatSummary",1,1}, {"DiagnosticsPerformanceInterval",1,1}
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
        if(!strcmp(category,"DIAGNOSTIC_COST") || !strcmp(category,"PLAN_PERF")) return 16;
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
        closeFile(); level = -1; rowTurn = -1; memoryTurn = -1; rows = 0;
        initialized = false; failed = false; suppressed = false; optionsLoaded = false;
        prefix[0] = 0; directory[0] = 0; configHash = 0;
        costs=Costs(); pendingWrites=0; lastFlush=0;
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
        getLevelUnlocked();
        if (output) writeLine(GC.getGame().getGameTurn(), -1, "LEVEL", value == 0 ? "off" : value == 1 ? "summary" : "verbose");
        if (!value) { closeFile(); strcpy_s(status, sizeof(status), "Off"); }
        level = value; failed = false;
        for (int i = 0; i < MAX_PLAYERS; ++i) { playerTurn[i]=playerAfterTurn[i]=passTurn[i]=-1; }
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
