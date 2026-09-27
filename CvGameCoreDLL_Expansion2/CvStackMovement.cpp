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
    bool HasVisibleEnemy(CvPlot* pPlot, CvUnit* pUnit)
    {
        return pPlot->isVisible(pUnit->getTeam()) &&
            (pPlot->isEnemyCity(*pUnit) || pPlot->isVisibleEnemyUnit(pUnit));
    }

    const char* CheckPath(CvUnit* pUnit, CvPlot* pDestination, CvStackMovement::Member& member)
    {
        if (pUnit->isDelayedDeath() || pUnit->isInCombat() || pUnit->IsBusy())
            return "Busy";
        if (pUnit->isCargo())
            return "Cargo";
        if (pUnit->getDomainType() == DOMAIN_AIR)
            return "Aircraft";
        if (!pUnit->canMove())
            return "NoMoves";
        if (pUnit->plot() == pDestination)
            return "AlreadyHere";
        if (HasVisibleEnemy(pDestination, pUnit))
            return "Enemy";
        if (!pUnit->canMoveInto(*pDestination, CvUnit::MOVEFLAG_DESTINATION | CvUnit::MOVEFLAG_IGNORE_STACKING_SELF))
            return "TerrainOrBorders";
        int turns = 0;
        if (!pUnit->GeneratePath(pDestination, MOVE_FLAGS | CvUnit::MOVEFLAG_IGNORE_STACKING_SELF, INT_MAX, &turns))
            return "NoPath";
        if (pUnit->GetPathEndFirstTurnPlot() != pDestination)
            return "LaterTurn";
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
        member.movesLeft = pUnit->GetMovementPointsAtCachedTarget();
        return "Ready";
    }
}

CvStackMovement::Plan CvStackMovement::Preview(CvUnit* pSelected, CvPlot* pSource, CvPlot* pDestination, const std::vector<int>& ids)
{
    Plan result;
    if (!pSelected || !pSource || !pDestination || !CvStacking::IsEnabled())
        return result;
    const PlayerTypes owner = pSelected->getOwner();
    // Snapshot IDs are stable, with the selected member first, then ascending ID.
    std::vector<int> ordered(ids);
    std::sort(ordered.begin(), ordered.end());
    ordered.erase(std::unique(ordered.begin(), ordered.end()), ordered.end());
    std::vector<int>::iterator selected = std::find(ordered.begin(), ordered.end(), pSelected->GetID());
    if (selected != ordered.end())
    {
        ordered.erase(selected);
        ordered.insert(ordered.begin(), pSelected->GetID());
    }
    std::map<DomainTypes, int> reserved, movingProtectors, stayingProtectors, movingVulnerable;
    for (size_t i = 0; i < ordered.size(); ++i)
    {
        Member member(ordered[i]);
        CvUnit* pUnit = GET_PLAYER(owner).getUnit(ordered[i]);
        if (pUnit && pUnit->plot() == pSource)
        {
            member.protector = pUnit->IsCombatUnit() && !pUnit->IsCanAttackRanged() && !pUnit->isCargo();
            member.vulnerable = pUnit->IsCanAttackRanged() && pUnit->getDomainType() != DOMAIN_AIR;
            member.reason = CheckPath(pUnit, pDestination, member);
            if (strcmp(member.reason, "Ready") == 0)
            {
                const DomainTypes domain = pUnit->getDomainType();
                // Civilians/support retain their ordinary rules; only normal combat units use slots.
                const bool usesCombatSlot = pUnit->IsCombatUnit() && !pUnit->IsStackingUnit();
                const int occupied = pUnit->CountStackingUnitsAtPlot(pDestination);
                const int capacity = pUnit->GetStackingLimit(pDestination);
                if (usesCombatSlot && !pUnit->CanStackUnitAtPlot(pDestination))
                    member.reason = occupied >= capacity ? "Capacity" : "ForeignStack";
                else if (usesCombatSlot && occupied + reserved[domain] >= capacity)
                    member.reason = "Capacity";
                else
                {
                    member.canMove = true;
                    if (pUnit->IsCombatUnit() && !pUnit->IsStackingUnit())
                        ++reserved[domain];
                }
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

CvStackMovement::Plan CvStackMovement::Execute(CvUnit* pSelected, CvPlot* pSource, CvPlot* pDestination, const std::vector<int>& ids)
{
    // No local PushMission calls: the engine receives the normal synchronized missions.
    Plan result = Preview(pSelected, pSource, pDestination, ids);
    if (!pSelected || pSelected->getOwner() != GC.getGame().getActivePlayer() ||
        !GET_PLAYER(pSelected->getOwner()).isTurnActive())
        return result;
    for (size_t i = 0; i < result.members.size(); ++i)
    {
        Member& member = result.members[i];
        if (!member.canMove)
            continue;
        CvUnit* pUnit = GET_PLAYER(pSelected->getOwner()).getUnit(member.id);
        if (!pUnit || pUnit->plot() != pSource || !pUnit->canMove())
            continue;
        gDLL->sendPushMission(member.id, CvTypes::getMISSION_MOVE_TO(),
            pDestination->getX(), pDestination->getY(), MOVE_FLAGS, false);
        member.sent = true;
    }
    return result;
}
