#pragma once
#include "CvEnums.h"

class CvUnit;
class CvCity;
class CvPlot;
class CvArmyAI;
class CvAIOperation;

// AI policy and bounded, reconstructible planning state. No serialized fields.
namespace CvStackingAI
{
    struct CityDefense
    {
        int immediate, nearby, enemyStrength, seaStrength, collateral, cavalry;
        int landMinimum, landMaximum, landStrength, seaMaximum;
        int rangedMinimum, meleeMaximum;
        CityDefense() : immediate(0), nearby(0), enemyStrength(0), seaStrength(0), collateral(0), cavalry(0),
            landMinimum(0), landMaximum(0), landStrength(0), seaMaximum(0), rangedMinimum(0), meleeMaximum(0) {}
    };
    bool Enabled(PlayerTypes player);
    void Reset();
    CityDefense AssessCity(const CvCity* city);
    int UnitStrength(const CvUnit* unit);
    bool RetainCityUnit(const CvUnit* unit);
    bool NeedsCityDefender(const CvCity* city);
    bool UsefulGarrison(const CvUnit* candidate, const CvCity* city);
    bool WantsRangedDefender(const CvCity* city);
    int RangedDefenseProductionBonus(const CvCity* city, UnitAITypes role, int range);
    bool TryReinforceRearUnit(CvUnit* unit);
    bool CanStartAnotherOperation(PlayerTypes player, DomainTypes domain);
    bool RecruitmentBlocked(const CvUnit* unit, const CvPlot* target);
    void DelayRecruitment(const CvUnit* unit, const CvPlot* target);
    bool ArmyUnitStalled(CvUnit* unit, CvArmyAI* army, CvPlot* checkpoint, int eta);
    bool ReadyWithAvailableUnits(CvAIOperation* operation, CvArmyAI* army);
    bool AssemblyStalled(CvAIOperation* operation, CvArmyAI* army);
}
