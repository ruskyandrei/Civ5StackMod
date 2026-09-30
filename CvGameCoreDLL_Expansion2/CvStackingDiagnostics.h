#pragma once
#ifndef CV_STACKING_DIAGNOSTICS_H
#define CV_STACKING_DIAGNOSTICS_H
#include "CvEnums.h"
class CvPlayer;
class CvCombatInfo;
namespace CvStackingDiagnostics
{
    // Diagnostic state is session-local, never serialized or used by gameplay.
    void Reset();
    void SetLevel(int level);
    int GetLevel();
    const char* GetStatus();
    bool Enabled(int level, PlayerTypes player = NO_PLAYER);
    bool EnabledCategory(int level, PlayerTypes player, const char* category);
    void Flush();
    void Record(int level, PlayerTypes player, const char* category, const char* format, ...);
    void OnPlayerTurn(CvPlayer& player);
    void AfterPlayerUnitAI(CvPlayer& player);
    // Top-level wall-clock phases only. Inclusive intervals can overlap nested
    // phases and PLAN; use their tick bounds, never sum all rows as a round.
    // Call Finish at a boundary, or let destruction finish on an early return.
    class TurnPhaseScope
    {
    public:
        TurnPhaseScope(PlayerTypes player, const char* phase);
        ~TurnPhaseScope();
        void Finish();
    private:
        TurnPhaseScope(const TurnPhaseScope&);
        TurnPhaseScope& operator=(const TurnPhaseScope&);
        bool active;
        bool cpuAvailable;
        PlayerTypes actor;
        const char* name;
        int turn;
        unsigned long started, thread, generation;
        unsigned __int64 cpuStarted;
    };
    // The last contiguous entry interval is a TURN_PHASE. Earlier busy polls
    // are aggregate counters only, never extra phase rows or a spanning timer.
    class UnitAIEntryScope
    {
    public:
        explicit UnitAIEntryScope(PlayerTypes player);
        ~UnitAIEntryScope();
        void HookFinished();
        void Finish(bool busy);
    private:
        UnitAIEntryScope(const UnitAIEntryScope&);
        UnitAIEntryScope& operator=(const UnitAIEntryScope&);
        bool active, hookDone, cpuAvailable;
        PlayerTypes actor;
        int turn;
        unsigned long started, hookEnded, thread, generation;
        unsigned __int64 cpuStarted, cpuHookEnded;
    };
    // One pending AI activation, ending at its first unit-AI entry. These
    // boundaries aggregate silently; the spanning summary is not TURN_PHASE.
    enum UpdateBoundaryPart { UPDATE_WRAPPER, UPDATE_GAME, UPDATE_BEGIN_HOOK, UPDATE_END_HOOK };
    class UpdateBoundaryScope
    {
    public:
        explicit UpdateBoundaryScope(UpdateBoundaryPart part);
        ~UpdateBoundaryScope();
    private:
        UpdateBoundaryScope(const UpdateBoundaryScope&);
        UpdateBoundaryScope& operator=(const UpdateBoundaryScope&);
        bool active;
        UpdateBoundaryPart part;
        unsigned long thread, generation;
    };
    void BeforeUpdateMoves();
    class ActivationTailScope
    {
    public:
        ActivationTailScope();
        ~ActivationTailScope();
        void Start(PlayerTypes player, bool eligible);
    private:
        ActivationTailScope(const ActivationTailScope&);
        ActivationTailScope& operator=(const ActivationTailScope&);
        bool active;
        unsigned long serial, thread, generation;
    };
    class CombatScope
    {
    public:
        CombatScope(const CvCombatInfo& info, unsigned int eventID);
        ~CombatScope();
    private:
        CombatScope(const CombatScope&);
        CombatScope& operator=(const CombatScope&);
        void AddUnit(int owner, int id, const char* role, int rolledDamage);
        bool active, detailed, compact;
        int attackingOwner, cityOwnerBefore, cityIDBefore, cityHPBefore, cityProtectionBefore;
        int attackingUnitID, attackingCityID, defendingOwner, defendingUnitID, defendingCityID;
        int primaryDamage, retaliationDamage, bystanderCount;
        long long bystanderDamage;
        bool ranged, bombing;
        unsigned int serial;
        PlayerTypes actor;
        int plotIndex, count;
        int owners[35], ids[35], health[35];
    };
}
#endif
