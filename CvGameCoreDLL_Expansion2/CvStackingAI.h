#pragma once
#include "CvEnums.h"

class CvUnit;
class CvCity;
class CvPlot;
class CvArmyAI;
class CvAIOperation;
class CvPlayer;

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
    // Melee/ranged mix and medic cover of the stack one unit would be part of.
    // Score() adds the unit itself; Add() ignores members that do not count.
    struct StackMix
    {
        int melee, ranged, others, otherHeal, healable;
        StackMix() : melee(0), ranged(0), others(0), otherHeal(0), healable(0) {}
        void Add(const CvUnit* unit, const CvUnit* member, int memberDamage);
        int Score(const CvUnit* unit, int selfDamage) const;
    };
    int CompositionScore(const CvUnit* unit, const CvPlot* plot);
    int MedicPromotionPercent(const CvUnit* unit);
    // Siege tile preference near an enemy city: defensive terrain is worth more,
    // and a melee tile next to the city that would attack it across a river less.
    int SiegeTileScore(const CvUnit* unit, const CvPlot* plot, const CvPlot* cityPlot);
    // Conquest: puppet a city whose annexation would drop approval below the
    // happiness line; keep developed conquered cities from being razed unless
    // revolt is imminent; stop razing once approval recovers.
    bool ConquestWouldMakeUnhappy(CvPlayer& player, const CvCity* city);
    bool KeepFromRazing(CvPlayer& player, CvCity* city);
    void UnrazeRecoveredCities(CvPlayer& player);
    // Buys a land unit of this role in the city with gold, within the AI's budget.
    bool BuyCityUnit(CvCity* city, UnitAITypes role);
    void CityDefensePurchases(CvPlayer& player);
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
