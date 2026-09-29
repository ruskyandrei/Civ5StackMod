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
    struct Demand
    {
        int staging, target, operation, strength, priority;
        Demand(int s,int t,int o,int n,int p):staging(s),target(t),operation(o),strength(n),priority(p){}
    };
    bool Enabled(PlayerTypes owner);
    bool IsCityAttack(const CvAIOperation* operation);
    CvPlot* CityTarget(const CvAIOperation* operation);
    void Handoff(CvAIOperation* operation);
    void Reset();
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
    bool OpeningReady(CvAIOperation* operation, CvArmyAI* army);
    bool ReadyToDeclare(PlayerTypes owner, PlayerTypes enemy);
    bool HoldForContact(CvAIOperation* operation, CvArmyAI* army, CvPlot* next);
    bool MovingStalled(CvAIOperation* operation, CvArmyAI* army, bool contact);
    bool CanCapture(const CvUnit* unit, const CvPlot* city);
    bool ContinueSiege(PlayerTypes owner, CvCity* city);
    bool PrioritizeExisting(PlayerTypes owner, CvPlot* target, bool naval);
}
