#include "CvGameCoreDLLPCH.h"
#include "CvStackMovement.h"
#include "CvStackingRules.h"
#include "CvUnit.h"
#include "CvPlot.h"
#include "CvPlayerAI.h"
#include "CvGameCoreUtils.h"
#include "CvGlobals.h"
#include "CvGame.h"
#include "CvTeam.h"
#include "CvTypes.h"
#include "CvAStarNode.h"
#include <algorithm>
#include <map>
#include <set>
#include "LintFree.h"

namespace
{
    // Deliberately omit ATTACK, KEEP_LINK, IGNORE_STACKING and approximate targets.
    const int MOVE_FLAGS = CvUnit::MOVEFLAG_ABORT_IF_NEW_ENEMY_REVEALED | CvUnit::MOVEFLAG_STACK_SAFE;
    // STACK_SAFE missions expire at turn end, so later arrivals get an ordinary multi-turn move
    // that still stops when new enemies come into view.
    const int QUEUED_MOVE_FLAGS = CvUnit::MOVEFLAG_ABORT_IF_NEW_ENEMY_REVEALED;
    bool HasVisibleEnemy(CvPlot* pPlot, CvUnit* pUnit)
    {
        return pPlot->isVisible(pUnit->getTeam()) &&
            (pPlot->isEnemyCity(*pUnit) || pPlot->isVisibleEnemyUnit(pUnit));
    }

    // Reasons that apply regardless of destination; NULL when the unit may take a move order.
    const char* CheckMover(CvUnit* pUnit, bool bQueueLater)
    {
        if (pUnit->isDelayedDeath() || pUnit->isInCombat() || pUnit->IsBusy())
            return "Busy";
        if (pUnit->isCargo())
            return "Cargo";
        if (pUnit->getDomainType() == DOMAIN_AIR)
            return "Aircraft";
        if (!bQueueLater && !pUnit->canMove())
            return "NoMoves";
        return NULL;
    }

    bool CanEndAt(CvUnit* pUnit, CvPlot* pDestination)
    {
        return pUnit->canMoveInto(*pDestination, CvUnit::MOVEFLAG_DESTINATION | CvUnit::MOVEFLAG_IGNORE_STACKING_SELF);
    }

    const char* CheckPath(CvUnit* pUnit, CvPlot* pDestination, CvStackMovement::Member& member, bool bQueueLater)
    {
        if (const char* reason = CheckMover(pUnit, bQueueLater))
            return reason;
        if (pUnit->plot() == pDestination)
            return "AlreadyHere";
        if (HasVisibleEnemy(pDestination, pUnit))
            return "Enemy";
        if (!CanEndAt(pUnit, pDestination))
            return "TerrainOrBorders";
        int turns = 0;
        if (!pUnit->GeneratePath(pDestination, MOVE_FLAGS | CvUnit::MOVEFLAG_IGNORE_STACKING_SELF, INT_MAX, &turns))
            return "NoPath";
        member.turns = turns;
        const bool bArrivesNow = pUnit->canMove() && pUnit->GetPathEndFirstTurnPlot() == pDestination;
        if (!bArrivesNow && !bQueueLater)
            return "LaterTurn";
        // Later arrivals are ordered with the queued flags, so check that route instead.
        if (!bArrivesNow)
        {
            if (!pUnit->GeneratePath(pDestination, QUEUED_MOVE_FLAGS | CvUnit::MOVEFLAG_IGNORE_STACKING_SELF, INT_MAX, &turns))
                return "NoPath";
            member.turns = turns;
        }
        const CvPathNodeArray& path = pUnit->GetLastPath();
        for (size_t i = 0; i < path.size(); ++i)
        {
            CvPlot* pStep = path.GetPlotByIndex((int)i);
            if (!pStep)
                return "NoPath";
            if (HasVisibleEnemy(pStep, pUnit))
                return "Enemy";
            if (!pStep->isVisible(pUnit->getTeam()))
                member.uncertain = true;
        }
        if (!bArrivesNow)
            return "Queued";
        member.movesLeft = pUnit->GetMovementPointsAtCachedTarget();
        return "Ready";
    }

    // Civilians/support retain their ordinary rules; only normal combat units use slots.
    // Returns the blocking reason, or NULL after reserving the slot.
    const char* ReserveSlot(CvUnit* pUnit, CvPlot* pDestination, std::map<DomainTypes, int>& reserved)
    {
        if (!pUnit->IsCombatUnit() || pUnit->IsStackingUnit())
            return NULL;
        const DomainTypes domain = pUnit->getDomainType();
        const int occupied = pUnit->CountStackingUnitsAtPlot(pDestination);
        const int capacity = pUnit->GetStackingLimit(pDestination);
        if (!pUnit->CanStackUnitAtPlot(pDestination))
            return occupied >= capacity ? "Capacity" : "ForeignStack";
        if (occupied + reserved[domain] >= capacity)
            return "Capacity";
        ++reserved[domain];
        return NULL;
    }

    // Snapshot IDs are stable, with the selected member first, then ascending ID.
    std::vector<int> OrderMembers(CvUnit* pSelected, const std::vector<int>& ids)
    {
        std::vector<int> ordered(ids);
        std::sort(ordered.begin(), ordered.end());
        ordered.erase(std::unique(ordered.begin(), ordered.end()), ordered.end());
        std::vector<int>::iterator selected = std::find(ordered.begin(), ordered.end(), pSelected->GetID());
        if (selected != ordered.end())
        {
            ordered.erase(selected);
            ordered.insert(ordered.begin(), pSelected->GetID());
        }
        return ordered;
    }
}

CvStackMovement::Plan CvStackMovement::Preview(CvUnit* pSelected, CvPlot* pSource, CvPlot* pDestination, const std::vector<int>& ids, bool bQueueLater)
{
    Plan result;
    if (!pSelected || !pSource || !pDestination || !CvStacking::IsEnabled())
        return result;
    const PlayerTypes owner = pSelected->getOwner();
    const std::vector<int> ordered = OrderMembers(pSelected, ids);
    std::map<DomainTypes, int> reserved, movingProtectors, stayingProtectors, movingVulnerable;
    for (size_t i = 0; i < ordered.size(); ++i)
    {
        Member member(ordered[i]);
        CvUnit* pUnit = GET_PLAYER(owner).getUnit(ordered[i]);
        if (pUnit && pUnit->plot() == pSource)
        {
            member.protector = pUnit->IsCombatUnit() && !pUnit->IsCanAttackRanged() && !pUnit->isCargo();
            member.vulnerable = pUnit->IsCanAttackRanged() && pUnit->getDomainType() != DOMAIN_AIR;
            member.reason = CheckPath(pUnit, pDestination, member, bQueueLater);
            if (strcmp(member.reason, "Ready") == 0 || strcmp(member.reason, "Queued") == 0)
            {
                // Later arrivals hold their slot too: they will occupy it when they arrive.
                if (const char* blocked = ReserveSlot(pUnit, pDestination, reserved))
                    member.reason = blocked;
                else
                    member.canMove = true;
            }
            if (member.protector)
            {
                if (member.canMove) ++movingProtectors[pUnit->getDomainType()];
                else ++stayingProtectors[pUnit->getDomainType()];
            }
            if (member.canMove && member.vulnerable)
                ++movingVulnerable[pUnit->getDomainType()];
        }
        else if (pUnit)
            member.reason = "LeftSource";
        result.members.push_back(member);
        if (member.canMove) ++result.moving;
        else ++result.staying;
    }
    for (std::map<DomainTypes, int>::const_iterator it = movingVulnerable.begin(); it != movingVulnerable.end(); ++it)
        if (it->second > 0 && stayingProtectors[it->first] > 0 && movingProtectors[it->first] == 0)
            result.protectorStays = true;
    return result;
}

CvStackMovement::Plan CvStackMovement::Execute(CvUnit* pSelected, CvPlot* pSource, CvPlot* pDestination, const std::vector<int>& ids, bool bQueueLater)
{
    // No local PushMission calls: the engine receives the normal synchronized missions.
    Plan result = Preview(pSelected, pSource, pDestination, ids, bQueueLater);
    if (!pSelected || pSelected->getOwner() != GC.getGame().getActivePlayer() ||
        !GET_PLAYER(pSelected->getOwner()).isTurnActive())
        return result;
    for (size_t i = 0; i < result.members.size(); ++i)
    {
        Member& member = result.members[i];
        if (!member.canMove)
            continue;
        CvUnit* pUnit = GET_PLAYER(pSelected->getOwner()).getUnit(member.id);
        const bool bQueued = strcmp(member.reason, "Queued") == 0;
        if (!pUnit || pUnit->plot() != pSource || (!bQueued && !pUnit->canMove()))
            continue;
        gDLL->sendPushMission(member.id, CvTypes::getMISSION_MOVE_TO(),
            pDestination->getX(), pDestination->getY(), bQueued ? QUEUED_MOVE_FLAGS : MOVE_FLAGS, false);
        member.sent = true;
    }
    return result;
}

CvStackMovement::Reach CvStackMovement::GetReach(CvUnit* pSelected, CvPlot* pSource, const std::vector<int>& ids)
{
    Reach result;
    if (!pSelected || !pSource || !CvStacking::IsEnabled())
        return result;
    const PlayerTypes owner = pSelected->getOwner();
    const std::vector<int> ordered = OrderMembers(pSelected, ids);
    std::vector<CvUnit*> movers;
    std::vector<ReachablePlots> reach;
    std::set<int> candidates;
    for (size_t i = 0; i < ordered.size(); ++i)
    {
        CvUnit* pUnit = GET_PLAYER(owner).getUnit(ordered[i]);
        if (!pUnit || pUnit->plot() != pSource)
            continue;
        ++result.members;
        if (CheckMover(pUnit, false))
            continue;
        ++result.eligible;
        movers.push_back(pUnit);
        reach.push_back(TacticalAIHelpers::GetAllPlotsInReachThisTurn(pUnit, pSource, MOVE_FLAGS | CvUnit::MOVEFLAG_IGNORE_STACKING_SELF));
        for (ReachablePlots::const_iterator it = reach.back().begin(); it != reach.back().end(); ++it)
            candidates.insert(it->iPlotIndex);
    }
    candidates.erase(pSource->GetPlotIndex());
    // Same destination checks and capacity order as Preview, without a path per unit and plot.
    for (std::set<int>::const_iterator it = candidates.begin(); it != candidates.end(); ++it)
    {
        CvPlot* pPlot = GC.getMap().plotByIndex(*it);
        if (!pPlot)
            continue;
        std::map<DomainTypes, int> reserved;
        int arriving = 0;
        for (size_t i = 0; i < movers.size(); ++i)
        {
            CvUnit* pUnit = movers[i];
            if (reach[i].find(*it) == reach[i].end() || HasVisibleEnemy(pPlot, pUnit) || !CanEndAt(pUnit, pPlot))
                continue;
            if (!ReserveSlot(pUnit, pPlot, reserved))
                ++arriving;
        }
        if (arriving > 0)
            result.plots.push_back(ReachPlot(*it, arriving));
    }
    return result;
}
