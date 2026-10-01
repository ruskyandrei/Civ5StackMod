#pragma once
#include "CvEnums.h"
#include <vector>
class CvUnit;
class CvCity;
class CvPlot;
class CvArmyAI;
class CvAIOperation;

// Reconstructible objective/route histories, reset with the existing game cache.
// No fields are added to serialized game objects.
namespace CvStackingOffensiveAI
{
    struct AssaultPlan
    {
        int phase, staging, readyUnits, siege, ranged, capturers, inbound;
        int desiredUnits, desiredSiege, cityDamage, enemyStrength, captureUnit, captureOwner, reason;
        int waveUnits,waveSiege,waveCapturers,waveStrength,waveDamage,waveSustain,waveFirstETA,waveLastETA;unsigned failedMask;
        bool ready, routeKnown,healingComplete;
        AssaultPlan():phase(0),staging(-1),readyUnits(0),siege(0),ranged(0),capturers(0),inbound(0),
            desiredUnits(0),desiredSiege(0),cityDamage(0),enemyStrength(0),captureUnit(-1),captureOwner(-1),reason(0),waveUnits(0),waveSiege(0),waveCapturers(0),waveStrength(0),waveDamage(0),waveSustain(0),waveFirstETA(-1),waveLastETA(-1),failedMask(0),ready(false),routeKnown(false),healingComplete(false){}
    };
    struct Demand
    {
        int staging, target, operation, strength, priority;
        Demand(int s,int t,int o,int n,int p):staging(s),target(t),operation(o),strength(n),priority(p){}
    };
    struct TacticalForce
    {
        int target, domain; std::vector<int> units;
        TacticalForce(int t,int d):target(t),domain(d){}
    };
    bool Enabled(PlayerTypes owner);
    bool IsCityAttack(const CvAIOperation* operation);
    CvPlot* CityTarget(const CvAIOperation* operation);
    void Handoff(CvAIOperation* operation);
    void Reset();
    void Shutdown();
    void ObserveOperation(CvAIOperation* operation);
    void ObserveSiege(PlayerTypes owner, CvCity* city);
    void AddDemands(CvUnit* unit, std::vector<Demand>& result);
    bool HasCommitment(const CvUnit* unit, const CvPlot* target = NULL);
    void RecordTransfer(CvUnit* unit, int target, int operation, int eta);
    bool JoinArrived(CvUnit* unit);
    bool HoldReserve(CvUnit* unit);
    void CancelCommitment(const CvUnit* unit);
    bool RouteBlocked(PlayerTypes owner, CvPlot* target, bool naval);
    void OperationAborted(CvAIOperation* operation, int reason);
    CvPlot* RepairRoute(const CvAIOperation* operation, CvArmyAI* army, CvPlot* from, CvPlot* waypoint);
    bool TryReadyCoreForArmy(CvAIOperation* operation,CvArmyAI* army,bool& ready);
    void ResetOpeningReadiness();
    bool OpeningReady(CvAIOperation* operation, CvArmyAI* army);
    bool ReadyToDeclare(PlayerTypes owner, PlayerTypes enemy);
    bool HoldForContact(CvAIOperation* operation, CvArmyAI* army, CvPlot* next);
    bool MovingStalled(CvAIOperation* operation, CvArmyAI* army, bool contact);
    bool CanCapture(const CvUnit* unit, const CvPlot* city);
    bool ContinueSiege(PlayerTypes owner, CvCity* city);
    bool ConsumeAdditionalTacticalBatch(PlayerTypes owner);
    bool IsSiegeUnit(const CvUnit* unit);
    int DesiredAssaultUnits(PlayerTypes owner, const CvCity* city, DomainTypes domain);
    int DesiredSiegeUnits(PlayerTypes owner, const CvCity* city, DomainTypes domain);
    AssaultPlan AssessAssault(PlayerTypes owner, CvCity* city, DomainTypes domain);
    CvPlot* GetStagingPlot(const CvUnit* unit, const CvPlot* cityTarget);
    bool HoldForAssembly(const CvUnit* unit, const CvPlot* tacticalTarget);
    void ReviewObjectives(PlayerTypes owner);
    CvUnit* GetReservedCapturer(PlayerTypes owner, CvCity* city);
    CvPlot* GetCaptureApproachNow(CvUnit* unit, CvCity* city);
    bool IsAssemblyHeld(const CvUnit* unit);
    void ReleaseAssemblyHold(CvUnit* unit);
    // executing: a planned shot being carried out; a stationary shot is not
    // re-vetoed by danger after other planned units have left its stack.
    bool AllowCityAttack(const CvUnit* unit, CvCity* city, const CvPlot* firing, bool capture, bool executing=false);
    enum ProductionRole { PRODUCTION_CAPTURE=1, PRODUCTION_SIEGE=2, PRODUCTION_RANGED=4 };
    enum ProductionReason { PRODUCTION_NONE=0, PRODUCTION_ROLE=1, PRODUCTION_QUEUE_LIMIT=2,
        PRODUCTION_FORCE_LIMIT=3, PRODUCTION_SUPPLY=4, PRODUCTION_AFFORDABILITY=5,
        PRODUCTION_DOMAIN_QUOTA=6, PRODUCTION_HOME_DEFENSE=7, PRODUCTION_NO_OBJECTIVE=8 };
    struct ProductionBudget
    {
        int turn, supplyAvailable, affordableAvailable, queuedSupply, queuedLand, queuedSea;
        unsigned long generation;
        bool ready;
        ProductionBudget():turn(-1),supplyAvailable(0),affordableAvailable(0),queuedSupply(0),queuedLand(0),queuedSea(0),generation(0),ready(false){}
    };
    struct ProductionIntent
    {
        int target, domain, roles, bonus, reason, units, queued, missingSiege, missingRanged, missingCapture, quotaUnits;
        bool missingRole, quotaEligible;
        ProductionIntent():target(-1),domain(NO_DOMAIN),roles(0),bonus(0),reason(PRODUCTION_NO_OBJECTIVE),
            units(0),queued(0),missingSiege(0),missingRanged(0),missingCapture(0),quotaUnits(0),missingRole(false),quotaEligible(false){}
    };
    // Demand/budget evidence does not replace native canTrain/purchase/resource checks.
    bool GetProductionBudget(PlayerTypes owner,ProductionBudget& result);
    bool GetProductionIntent(const CvCity* city,UnitTypes unit,ProductionIntent& result,bool replaceQueue=true);
    void ProductionQueueChanged(const CvCity* city);
    void ResetProductionPolicy();
    void ProductionCitiesChanged(PlayerTypes owner);
    void InvalidateProductionStaff(PlayerTypes owner,int target,DomainTypes domain);
    void InvalidateProductionOwner(PlayerTypes owner);
    void ProductionEconomyChanged(PlayerTypes owner);
    void RecordProductionRejection(const CvCity* city,UnitTypes unit,const ProductionIntent& intent,int reason);

    int ProductionBonus(const CvCity* city, UnitTypes unit);
    void RecordProduction(CvCity* city, UnitTypes unit);
    void UnitProduced(CvCity* city, CvUnit* unit);
    void TacticalForces(PlayerTypes owner, std::vector<TacticalForce>& result);
    bool IsCombatHistoryCurrent(unsigned long generation);
    bool GetCombatObjective(const CvUnit* unit,int& target,DomainTypes& domain,unsigned long& generation);
    void RecordCombatContribution(PlayerTypes owner,int unit,int target,DomainTypes domain,
        int combatPlot,int defenderOwner,int fieldDamage,int cityDamage,bool captured);
    void RecordStageRouteProgress(CvUnit* unit,int target,int stage,int destination,int from,int expectedEnd);
    bool StageUnit(CvUnit* unit, const CvPlot* cityTarget);
    bool TryStationaryCityFire(CvUnit* unit, const CvPlot* cityTarget);
    // After the tactical and homeland AI: idle ranged units with an unused
    // attack fire at an enemy unit or city from where they stand.
    int FireRemainingRangedShots(PlayerTypes owner);
    bool PrioritizeExisting(PlayerTypes owner, CvPlot* target, bool naval);
}
