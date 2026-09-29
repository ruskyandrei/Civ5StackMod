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
