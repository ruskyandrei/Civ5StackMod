/*	-------------------------------------------------------------------------------------------------------
	© 1991-2012 Take-Two Interactive Software and its subsidiaries.  Developed by Firaxis Games.  
	Sid Meier's Civilization V, Civ, Civilization, 2K Games, Firaxis Games, Take-Two Interactive Software 
	and their respective logos are all trademarks of Take-Two interactive Software, Inc.  
	All other marks and trademarks are the property of their respective owners.  
	All rights reserved. 
	------------------------------------------------------------------------------------------------------- */
#include "CvGameCoreDLLPCH.h"
#include "CvStackingAI.h"
#include "CvStackingOffensiveAI.h"
#include "CvStackingRules.h"
#include "CvStackingStrengthCache.h"
#include "CvDangerPlots.h"
#include "CvUnitCombat.h"
#include "CvTacticalAI.h"
#include "CvTacticalAnalysisMap.h"
#include "CvGameCoreUtils.h"
#include "CvAStar.h"
#include "CvEconomicAI.h"
#include "CvEnumSerialization.h"
#include "CvGrandStrategyAI.h"
#include "cvStopWatch.h"
#include "CvMilitaryAI.h"
#include "CvTypes.h"
#include "CvDiplomacyAI.h"
#include "CvBarbarians.h"
#include "CvUnitMovement.h"
#include "CvStackingDiagnostics.h"

#include <iomanip>
#include <sstream>
#include <cmath>
#include <deque>
#include <new>
#include <cstring>
#include "LintFree.h"

//for easier debugging
#ifdef VPDEBUG
#define TACTDEBUG 1
#endif

int gCurrentUnitToTrack = 0;
const unsigned char TACTICAL_COMBAT_MAX_TARGET_DISTANCE = 4; //not larger than 4, not smaller than 3
const int TACTICAL_COMBAT_CITADEL_BONUS = 67; //larger than 60 to override firstline/secondline difference
const short TACTICAL_COMBAT_IMPOSSIBLE_SCORE = (short) -1000;
const int TACTSIM_UNIQUENESS_CHECK_GENERATIONS = 3; //higher means check more siblings for permutations
const int TACTSIM_BREADTH_FIRST_GENERATIONS = 3; //switch to depth-first later
const int TACTSIM_MAX_UNITS = 13; //we have limited storage and time ...

//global memory for tactical simulation
CvTactPosStorage gTactPosStorage(6000);
CvSupportPosStorage gSupportPosStorage(60);
CvTactAssignmentStorage gAssignmentStorage(2000);
TCachedMovePlots gReachablePlotsLookup;
TCachedRangeAttackPlots gRangeAttackPlotsLookup;
TCachedDistanceToTargetPlots gDistanceToTargetPlots;
CvPlot* gTargetPlot;
vector<int> gLandEnemies, gSeaEnemies, gCities, gNewlyVisiblePlots;
vector<pair<int, int>> gCitadels;
vector<OptionWithScore<STacticalAssignment*>> gPossibleMoves, gPossibleRangedAttacks, gOverAllChoices;
vector<SComboMove> gMovesToAdd;
map<int, int> gBadUnitsCount;
SUnitIDValueContainer gEnemyDamageDealt;
TUnitFlagLookup gSafePlotCount;
int gDefaultUnitLossThreshold;
int gMedianUnitXP;
int gMinHpForTactsim;
PlayerTypes eLastTactSimPlayer = NO_PLAYER;

//just some statistics
unsigned long gMovePlotsCacheHit = 0, gMovePlotsCacheMiss = 0;
unsigned long gAttackPlotsCacheHit = 0, gAttackPlotsCacheMiss = 0;
unsigned long gAttackCacheHit = 0, gAttackCacheMiss = 0;
unsigned long gDangerCacheHit = 0, gDangerCacheMiss = 0;
unsigned long giEquivalentPos = 0, giDifferentPos = 0;
unsigned long giValidEndPos = 0, giInvalidEndPos = 0;
int gCheckedPositions = 0;

void CheckDebugTrigger(int iUnitID)
{
	if (iUnitID == gCurrentUnitToTrack)
	{
		//put a breakpoint here if required
		OutputDebugString("match\n");
	}
}

//=====================================
// CvTacticalTarget
//=====================================

/// This target make sense for this domain of unit/zone?
bool CvTacticalTarget::IsTargetValidInThisDomain(DomainTypes eDomain) const
{
	switch(GetTargetType())
	{
	case AI_TACTICAL_TARGET_NONE:
		return false;

	case AI_TACTICAL_TARGET_DEFENSIVE_BASTION:
	case AI_TACTICAL_TARGET_BARBARIAN_CAMP:
	case AI_TACTICAL_TARGET_IMPROVEMENT:
	case AI_TACTICAL_TARGET_IMPROVEMENT_TO_DEFEND:
	case AI_TACTICAL_TARGET_TRADE_UNIT_LAND:
	case AI_TACTICAL_TARGET_ENEMY_CITADEL:
	case AI_TACTICAL_TARGET_IMPROVEMENT_RESOURCE:
	case AI_TACTICAL_TARGET_GOODY:
		return eDomain == DOMAIN_LAND;

	case AI_TACTICAL_TARGET_BLOCKADE_POINT:
	case AI_TACTICAL_TARGET_TRADE_UNIT_SEA:
		return eDomain == DOMAIN_SEA;

	case AI_TACTICAL_TARGET_ENEMY_CITY:
	case AI_TACTICAL_TARGET_FRIENDLY_CITY:
	case AI_TACTICAL_TARGET_LOW_PRIORITY_CIVILIAN:
	case AI_TACTICAL_TARGET_HIGH_PRIORITY_CIVILIAN:
	case AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT:
		return true;
	}

	return false;
}

template<typename FocusArea, typename Visitor>
void CvFocusArea::Serialize(FocusArea& focusArea, Visitor& visitor)
{
	visitor(focusArea.m_iX);
	visitor(focusArea.m_iY);
	visitor(focusArea.m_iRadius);
	visitor(focusArea.m_iLastTurn);
}

FDataStream& operator<<(FDataStream& saveTo, const CvFocusArea& readFrom)
{
	CvStreamSaveVisitor serialVisitor(saveTo);
	CvFocusArea::Serialize(readFrom, serialVisitor);
	return saveTo;
}

FDataStream& operator>>(FDataStream& loadFrom, CvFocusArea& writeTo)
{
	CvStreamLoadVisitor serialVisitor(loadFrom);
	CvFocusArea::Serialize(writeTo, serialVisitor);
	return loadFrom;
}

//=====================================
// CvTacticalAI
//=====================================

/// Constructor
CvTacticalAI::CvTacticalAI(void)
{
}

/// Destructor
CvTacticalAI::~CvTacticalAI(void)
{
	Uninit();
}

/// Initialize
void CvTacticalAI::Init(CvPlayer* pPlayer)
{
	// Store off the pointer to the objects we need elsewhere in the game engine
	m_pPlayer = pPlayer;

	m_tacticalMap.Reset(m_pPlayer ? m_pPlayer->GetID() : NO_PLAYER);

	// Initialize AI constants from XML
	m_iRecruitRange = /*8*/ GD_INT_GET(AI_TACTICAL_RECRUIT_RANGE);
	m_iLandBarbarianRange = max(1, GC.getGame().getHandicapInfo().getBarbarianLandTargetRange());
	m_iSeaBarbarianRange = max(1, GC.getGame().getHandicapInfo().getBarbarianSeaTargetRange());
}

/// Deallocate memory created in initialize
void CvTacticalAI::Uninit()
{
}

///
template<typename TacticalAI, typename Visitor>
void CvTacticalAI::Serialize(TacticalAI& tacticalAI, Visitor& visitor)
{
	visitor(tacticalAI.m_focusAreas);
	visitor(tacticalAI.m_tacticalMap);
}

/// Serialization read
void CvTacticalAI::Read(FDataStream& kStream)
{
	CvStreamLoadVisitor serialVisitor(kStream);
	Serialize(*this, serialVisitor);
}

/// Serialization write
void CvTacticalAI::Write(FDataStream& kStream) const
{
	CvStreamSaveVisitor serialVisitor(kStream);
	Serialize(*this, serialVisitor);
}

FDataStream& operator>>(FDataStream& stream, CvTacticalAI& tacticalAI)
{
	tacticalAI.Read(stream);
	return stream;
}
FDataStream& operator<<(FDataStream& stream, const CvTacticalAI& tacticalAI)
{
	tacticalAI.Write(stream);
	return stream;
}

/// Mark all the units that will be under tactical AI control this turn
void CvTacticalAI::RecruitUnits()
{
	int iLoop = 0;
	m_CurrentTurnUnits.clear();

	// Loop through our units
	for(CvUnit* pLoopUnit = m_pPlayer->firstUnit(&iLoop); pLoopUnit; pLoopUnit = m_pPlayer->nextUnit(&iLoop))
	{
		// debugging hook
		if (gCurrentUnitToTrack == pLoopUnit->GetID())
			pLoopUnit->DumpDangerInNeighborhood();

		// we reset this every turn in order to spot units falling through the cracks
		// todo: ideally we have some persistency and prefer to assign the same tasks across turns ...
		pLoopUnit->setTacticalMove(AI_TACTICAL_MOVE_NONE);
		pLoopUnit->setHomelandMove(AI_HOMELAND_MOVE_NONE);

		// Never want immobile/dead units, explorers, ones that have already moved or automated human units
		if(!pLoopUnit->canUseForTacticalAI())
			continue;

		// reset mission AI so we don't see stale information (debugging only)
		pLoopUnit->SetMissionAI(NO_MISSIONAI,NULL,NULL);

		// we want all combat ready air units, except nukes (those go through operational AI)
		if (pLoopUnit->getDomainType() == DOMAIN_AIR)
		{
			//rebasing is done in homeland AI
			if (!ShouldRebase(pLoopUnit))
				m_CurrentTurnUnits.push_back(pLoopUnit->GetID());
		}
		// Now down to land and sea units
		else
		{
			if (pLoopUnit->getArmyID() != -1)
				//army units will be moved as part of the army moves
				pLoopUnit->setTacticalMove(AI_TACTICAL_OPERATION);
			else
				m_CurrentTurnUnits.push_back(pLoopUnit->GetID());
		}
	}

#if defined(MOD_CORE_DEBUGGING)
	if (MOD_CORE_DEBUGGING)
	{
		for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); ++it)
		{
			CvUnit* pUnit = m_pPlayer->getUnit(*it);
			if (!pUnit)
				continue;
			CvString msg = CvString::format("using %s %d at %d,%d for tactical ai. power is %d\n", pUnit->getName().c_str(), pUnit->GetID(), pUnit->getX(), pUnit->getY(), pUnit->GetPower() );
			LogTacticalMessage( msg );
		}
	}
#endif
}

/// Update the AI for units
void CvTacticalAI::Update()
{
	CvStackingDiagnostics::TurnPhaseScope phase(m_pPlayer->GetID(),"tactical_ai");
	UpdateVisibility();
	CvStackingDiagnostics::TurnPhaseScope targetPhase(m_pPlayer->GetID(),"tactical_targets");
	DropOldFocusAreas();
	FindTacticalTargets();
	targetPhase.Finish();

	//do this after updating the target list!
	{
		CvStackingDiagnostics::TurnPhaseScope recruitPhase(m_pPlayer->GetID(),"tactical_recruit");
		RecruitUnits();
	}
	// Current legal captures and protected batteries act before healing,
	// operational assembly or a withdrawing zone consumes their orders.
	{
		CvStackingDiagnostics::TurnPhaseScope opportunityPhase(m_pPlayer->GetID(),"immediate_city_opportunities");
		PlotImmediateCityOpportunities();
	}

	// Loop through each dominance zone assigning moves
	ProcessDominanceZones();
}

/// Clear up memory usage
void CvTacticalAI::CleanUp()
{
	m_AllTargets.clear();
	m_ZoneTargets.clear();
}

/// Add a temporary focus of attention around a short-term target
void CvTacticalAI::AddFocusArea(CvPlot* pPlot, int iRadius, int iDuration)
{
	if (!pPlot)
		return;

	CvFocusArea zone;
	zone.m_iX = pPlot->getX();
	zone.m_iY = pPlot->getY();
	zone.m_iRadius = iRadius;
	zone.m_iLastTurn = GC.getGame().getGameTurn() + iDuration;

	m_focusAreas.push_back(zone);
}

/// Remove a temporary focus of attention we no longer need to track
void CvTacticalAI::DeleteFocusArea(CvPlot* pPlot)
{
	std::vector<CvFocusArea> zonesCopy(m_focusAreas);
	m_focusAreas.clear();

	// Copy back to original vector any whose coords don't match
	for(unsigned int iI = 0; iI < zonesCopy.size(); iI++)
		if(zonesCopy[iI].m_iX != pPlot->getX() || zonesCopy[iI].m_iY != pPlot->getY())
			m_focusAreas.push_back(zonesCopy[iI]);
}

/// Remove focus zones that have expired
void CvTacticalAI::DropOldFocusAreas()
{
	std::vector<CvFocusArea> zonesCopy(m_focusAreas);
	m_focusAreas.clear();

	// Copy back to original vector any that haven't expired
	for(unsigned int iI = 0; iI < zonesCopy.size(); iI++)
		if(zonesCopy[iI].m_iLastTurn >= GC.getGame().getGameTurn())
			m_focusAreas.push_back(zonesCopy[iI]);
}

/// Is this a city that an operation just deployed in front of?
bool CvTacticalAI::IsInFocusArea(const CvPlot* pPlot) const
{
	for(unsigned int iI = 0; iI < m_focusAreas.size(); iI++)
		if(plotDistance(pPlot->getX(),pPlot->getY(),m_focusAreas[iI].m_iX,m_focusAreas[iI].m_iY)<=m_focusAreas[iI].m_iRadius)
			return true;

	return false;
}

/// Setup knowledge of other players' seen plots
void CvTacticalAI::UpdateVisibility()
{
	CvStackingDiagnostics::TurnPhaseScope phase(m_pPlayer->GetID(),"tactical_visibility");
	const TeamTypes eTeam = m_pPlayer->getTeam();

	CvPlot* pLoopPlot;

	for (int iI = 0; iI < GC.getMap().numPlots(); iI++)
	{
		pLoopPlot = GC.getMap().plotByIndexUnchecked(iI);
		pLoopPlot->ResetKnownVisibility();
	}

	for (int iI = 0; iI < GC.getMap().numPlots(); iI++)
	{
		pLoopPlot = GC.getMap().plotByIndexUnchecked(iI);

		if (!pLoopPlot->isRevealed(eTeam))
			continue;

		UpdateVisibilityFromBorders(pLoopPlot);

		if (!pLoopPlot->isVisible(eTeam))
			continue;

		UpdateVisibilityFromUnits(pLoopPlot);
	}
}

/// Check if there are any units owned by other players in this tile and what they can see
void CvTacticalAI::UpdateVisibilityFromUnits(CvPlot* pPlot)
{
	if (!pPlot)
		return;

	const TeamTypes ePlayerTeam = m_pPlayer->getTeam();

	if (pPlot->getNumUnits() > 0)
	{
		CvUnit* pLoopUnit;
		TeamTypes eLoopUnitTeam;

		for (int iI = 0; iI < pPlot->getNumUnits(); iI++)
		{
			pLoopUnit = pPlot->getUnitByIndex(iI);
			if(pLoopUnit == NULL)
			{
				if(GC.getGame().isNetworkMultiPlayer())
				{
					CvString msg; CvString::format(msg, "*** PLOT UNIT DESYNC *** UpdateVisibilityFromUnits: NULL unit at index %d on plot (%d,%d). Plot reports %d units.",
						iI, pPlot->getX(), pPlot->getY(), pPlot->getNumUnits());
					gGlobals.getDLLIFace()->sendChat(msg, CHATTARGET_ALL, NO_PLAYER);
				}
				continue;
			}
			PRECONDITION(pLoopUnit, "UpdateVisibilityFromUnits: Unit not found on plot, desync between plot unit list and actual unit positions");
			eLoopUnitTeam = pLoopUnit->getTeam();

			if (eLoopUnitTeam != ePlayerTeam && !pLoopUnit->isInvisible(ePlayerTeam, false))
			{
				pPlot->ChangeKnownAdjacentSight(eLoopUnitTeam, NO_TEAM, pLoopUnit->visibilityRange(), pLoopUnit->getFacingDirection(true));
			}
		}
	}

	if (pPlot->IsTradeUnitRoute())
	{
		PlotIndexContainer aiTradeUnitsAtPlot = m_pPlayer->GetTrade()->GetOpposingTradeUnitsAtPlot(pPlot, false);
		for (PlotIndexContainer::const_iterator it = aiTradeUnitsAtPlot.begin(); it != aiTradeUnitsAtPlot.end(); ++it)
		{
			PlayerTypes eTradeUnitOwner = GC.getGame().GetGameTrade()->GetOwnerFromID(*it);

			if (eTradeUnitOwner != NO_PLAYER && GET_PLAYER(eTradeUnitOwner).getTeam() != ePlayerTeam)
				pPlot->IncreaseKnownVisibilityCount(GET_PLAYER(eTradeUnitOwner).getTeam(), NO_TEAM);
		}
	}
}

void CvTacticalAI::UpdateVisibilityFromBorders(CvPlot* pPlot)
{
	const TeamTypes ePlayerTeam = m_pPlayer->getTeam();
	const TeamTypes ePlotTeam = pPlot->getTeam();
	const PlayerTypes eMinorCivAlly = ePlotTeam != NO_TEAM ? (GET_TEAM(ePlotTeam).isMinorCiv() ? GET_PLAYER(pPlot->getOwner()).GetMinorCivAI()->GetAlly() : NO_PLAYER) : NO_PLAYER;
	TeamTypes eMinorCivAllyTeam = eMinorCivAlly != NO_PLAYER ? GET_PLAYER(eMinorCivAlly).getTeam() : NO_TEAM;

	if (eMinorCivAllyTeam == ePlayerTeam)
		eMinorCivAllyTeam = NO_TEAM;

	if (ePlotTeam != NO_TEAM && ePlotTeam != ePlayerTeam)
	{
		pPlot->ChangeKnownAdjacentSight(ePlotTeam, eMinorCivAllyTeam, GD_INT_GET(PLOT_VISIBILITY_RANGE), NO_DIRECTION);
	}
}

// PRIVATE METHODS

/// Make lists of everything we might want to target with the tactical AI this turn
void CvTacticalAI::FindTacticalTargets()
{
	CvPlayerTrade* pPlayerTrade = m_pPlayer->GetTrade();

	bool bNoBarbsAllowedYet = GC.getGame().getGameTurn() < GC.getGame().GetBarbarianReleaseTurn();
	vector<PlayerTypes> vUnfriendlyMajors = m_pPlayer->GetUnfriendlyMajors();

	// Look at every tile on map
	for (int iI = 0; iI < GC.getMap().numPlots(); iI++)
	{
		CvPlot* pLoopPlot = GC.getMap().plotByIndexUnchecked(iI);
		bool bValidPlot = pLoopPlot->isRevealed(m_pPlayer->getTeam());

		// Make sure I am not a barbarian who can not move into owned territory this early in the game
		if (m_pPlayer->isBarbarian() && bNoBarbsAllowedYet && pLoopPlot->isOwned())
			continue;

		if (bValidPlot)
		{
			//camps are typically revealed but not visible; also the camp might since have been cleared but we don't know yet - so check if it is owned now
			bool bSuspectedBarbCamp = pLoopPlot->getRevealedImprovementType(m_pPlayer->getTeam()) == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT) && !pLoopPlot->isOwned();

			CvTacticalTarget newTarget;
			newTarget.SetTargetX(pLoopPlot->getX());
			newTarget.SetTargetY(pLoopPlot->getY());
			newTarget.SetDominanceZone(GetTacticalAnalysisMap()->GetDominanceZoneID(iI));

			// Have a ...
			// ... friendly city?
			CvCity* pCity = pLoopPlot->getPlotCity();
			if (pCity != NULL)
			{
				if (m_pPlayer->GetID() == pCity->getOwner())
				{
					CvTacticalDominanceZone* pLandZone = GetTacticalAnalysisMap()->GetZoneByCity(pCity, false);
					CvTacticalDominanceZone* pWaterZone = GetTacticalAnalysisMap()->GetZoneByCity(pCity, true);
					int iBorderScore = (pLandZone ? pLandZone->GetBorderScore(DOMAIN_LAND) : 0) + (pWaterZone ? pWaterZone->GetBorderScore(DOMAIN_SEA) : 0);
					if (iBorderScore > 0)
					{
						newTarget.SetTargetType(AI_TACTICAL_TARGET_FRIENDLY_CITY);
						newTarget.SetAuxIntData(iBorderScore);
						m_AllTargets.push_back(newTarget);
					}
				}

				// ... enemy city
				else if (atWar(m_pPlayer->getTeam(), pCity->getTeam()))
				{
					newTarget.SetTargetType(AI_TACTICAL_TARGET_ENEMY_CITY);
					//barbarians don't care about cities much compared to normal players
					newTarget.SetAuxIntData( m_pPlayer->isBarbarian() ? 20 : 100);
					m_AllTargets.push_back(newTarget);
				}
			}
			else
			{
				// ... enemy combat unit? we allow visible ones and some we remember from the previous turn
				CvUnit* pUnit = pLoopPlot->getBestDefender(NO_PLAYER, m_pPlayer->GetID(), NULL, true, true);
				bool bCanSeeUnit = pUnit && pLoopPlot->isVisible(m_pPlayer->getTeam()) && !pUnit->isInvisible(m_pPlayer->getTeam(), false);
				bool bRememberUnit = pUnit && m_pPlayer->IsVanishedUnit(pUnit->GetIDInfo());
				if (bCanSeeUnit || bRememberUnit)
				{
					//minors ignore barbarians until they are close to their borders
					if (!m_pPlayer->isMinorCiv() || !pUnit->isBarbarian() || pUnit->plot()->isAdjacentTeam(m_pPlayer->getTeam()))
					{
						newTarget.SetTargetType(AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT);
						newTarget.SetUnitPtr(pUnit);
						newTarget.SetAuxIntData(50);
						m_AllTargets.push_back(newTarget);
					}
				}
				// ... unprotected enemy civilian?
				else if (pLoopPlot->isEnemyUnit(m_pPlayer->GetID(),false,true) && !pLoopPlot->isNeutralUnit(m_pPlayer->GetID(),true,true))
				{
					for (int iUnitLoop = 0; iUnitLoop < pLoopPlot->getNumUnits(); iUnitLoop++)
					{
						CvUnit* pUnit = pLoopPlot->getUnitByIndex(iUnitLoop);

						//barbarians do not attack civilians before the first city was founded.
						if (!m_pPlayer->isBarbarian() || GET_PLAYER(pUnit->getOwner()).GetNumCitiesFounded() > 0)
						{
							newTarget.SetTargetType(IsHighPriorityCivilianTarget(&newTarget) ? AI_TACTICAL_TARGET_HIGH_PRIORITY_CIVILIAN : AI_TACTICAL_TARGET_LOW_PRIORITY_CIVILIAN);
							newTarget.SetUnitPtr(pUnit);
							newTarget.SetAuxIntData(25);
							m_AllTargets.push_back(newTarget);
						}
					}
				}

				// ... barbarian camp? doesn't matter if it has a unit inside
				// note that minors ignore barb camps, cannot clear them anyway
				if (bSuspectedBarbCamp && (m_pPlayer->isMajorCiv() || m_pPlayer->isBarbarian()))
				{
					int iBaseScore = pLoopPlot->isVisible(m_pPlayer->getTeam()) ? 100 : 50;
					newTarget.SetTargetType(AI_TACTICAL_TARGET_BARBARIAN_CAMP);
					newTarget.SetAuxIntData(iBaseScore - m_pPlayer->GetCityDistancePathLength(pLoopPlot));
					m_AllTargets.push_back(newTarget);
				}

				// ... unpopped goody hut? (ancient ruins)
				if(!m_pPlayer->isMinorCiv() && pLoopPlot->isRevealedGoody(m_pPlayer->getTeam()))
				{
					int iBaseScore = pLoopPlot->isVisible(m_pPlayer->getTeam()) ? 100 : 50;
					newTarget.SetTargetType(AI_TACTICAL_TARGET_GOODY);
					newTarget.SetAuxIntData(iBaseScore - m_pPlayer->GetCityDistancePathLength(pLoopPlot));
					m_AllTargets.push_back(newTarget);
				}

				// Or citadels (for pillaging!)
				if (atWar(m_pPlayer->getTeam(), pLoopPlot->getTeam()) &&
					pLoopPlot->getRevealedImprovementType(m_pPlayer->getTeam()) != NO_IMPROVEMENT &&
					GC.getImprovementInfo(pLoopPlot->getRevealedImprovementType(m_pPlayer->getTeam()))->GetNearbyEnemyDamage() > /*10 in CP, 5 in VP*/ GD_INT_GET(ENEMY_HEAL_RATE) &&
					!pLoopPlot->IsImprovementPillaged())
				{
					newTarget.SetTargetType(AI_TACTICAL_TARGET_ENEMY_CITADEL);
					newTarget.SetAuxIntData(80);
					m_AllTargets.push_back(newTarget);
				}

				// ... enemy improvement?
				if (atWar(m_pPlayer->getTeam(), pLoopPlot->getTeam()) &&
					pLoopPlot->getRevealedImprovementType(m_pPlayer->getTeam()) != NO_IMPROVEMENT &&
					!pLoopPlot->IsImprovementPillaged())
				{
					ResourceTypes eResource = pLoopPlot->getResourceType(m_pPlayer->getTeam());
					int iExtraScore = 0;
					//does this make a difference in the end?
					if (m_pPlayer->isBarbarian() || m_pPlayer->GetPlayerTraits()->IsWarmonger())
						iExtraScore = 20;

					ResourceUsageTypes eResourceUsage = (eResource != NO_RESOURCE) ? GC.getResourceInfo(eResource)->getResourceUsage() : RESOURCEUSAGE_BONUS;
					if (eResourceUsage == RESOURCEUSAGE_STRATEGIC)
					{
						newTarget.SetTargetType(AI_TACTICAL_TARGET_IMPROVEMENT_RESOURCE);
						newTarget.SetAuxIntData(80+iExtraScore);
					}
					else if (eResourceUsage == RESOURCEUSAGE_LUXURY)
					{
						newTarget.SetTargetType(AI_TACTICAL_TARGET_IMPROVEMENT_RESOURCE);
						newTarget.SetAuxIntData(40+iExtraScore);
					}
					else
					{
						newTarget.SetTargetType(AI_TACTICAL_TARGET_IMPROVEMENT);
						newTarget.SetAuxIntData(5+iExtraScore);
					}

					m_AllTargets.push_back(newTarget);
				}

				// ... enemy trade route? (city connection - not caravan)
				// checking for city connection is not enough, some people (iroquois) don't need roads, so there isn't anything to pillage 
				if (atWar(m_pPlayer->getTeam(), pLoopPlot->getTeam()) &&
					pLoopPlot->getRevealedRouteType(m_pPlayer->getTeam()) != NO_ROUTE && 
					!pLoopPlot->IsRoutePillaged() && pLoopPlot->IsCityConnection() &&
					!GetTacticalAnalysisMap()->IsInEnemyDominatedZone(pLoopPlot))
				{
					newTarget.SetTargetType(AI_TACTICAL_TARGET_IMPROVEMENT);
					newTarget.SetAuxIntData(10);
					m_AllTargets.push_back(newTarget);
				}

				// ... enemy trade unit
				if (pLoopPlot->isVisible(m_pPlayer->getTeam()) && pPlayerTrade->ContainsEnemyTradeUnit(pLoopPlot))
				{
					newTarget.SetTargetType( pLoopPlot->isWater() ? AI_TACTICAL_TARGET_TRADE_UNIT_SEA : AI_TACTICAL_TARGET_TRADE_UNIT_LAND);
					newTarget.SetAuxIntData(35);
					m_AllTargets.push_back(newTarget);
				}

				// ... defensive bastion?
				if (m_pPlayer->GetID() == pLoopPlot->getOwner() && pLoopPlot->getDomain()==DOMAIN_LAND &&
					(pLoopPlot->defenseModifier(m_pPlayer->getTeam(), false, false) >= 30 || pLoopPlot->IsChokePoint()) &&
					(!vUnfriendlyMajors.empty() && pLoopPlot->IsBorderLand(m_pPlayer->GetID(), vUnfriendlyMajors))
					)
				{
					newTarget.SetTargetType(AI_TACTICAL_TARGET_DEFENSIVE_BASTION);
					int iValue = pLoopPlot->defenseModifier(m_pPlayer->getTeam(), false, false);
					if (pLoopPlot->IsChokePoint())
						iValue *= 3;

					newTarget.SetAuxIntData(iValue);
					m_AllTargets.push_back(newTarget);
				}

				// ... friendly strategic resource improvement?
				if (m_pPlayer->GetID() == pLoopPlot->getOwner() &&
					pLoopPlot->getResourceType() != NO_RESOURCE && 
					pLoopPlot->getImprovementType() != NO_IMPROVEMENT && !pLoopPlot->IsImprovementPillaged())
				{
					if (pLoopPlot->getOwningCity() != NULL && !vUnfriendlyMajors.empty() && pLoopPlot->getOwningCity()->isBorderCity(vUnfriendlyMajors))
					{
						CvResourceInfo* pkResourceInfo = GC.getResourceInfo(pLoopPlot->getResourceType());
						if (pkResourceInfo && pkResourceInfo->getResourceUsage() == RESOURCEUSAGE_STRATEGIC)
						{
							newTarget.SetTargetType(AI_TACTICAL_TARGET_IMPROVEMENT_TO_DEFEND);
							newTarget.SetAuxIntData(1);
							m_AllTargets.push_back(newTarget);
						}
					}
				}

				//Enemy water plots?
				if (pLoopPlot->isRevealed(m_pPlayer->getTeam()) && pLoopPlot->isWater() && atWar(m_pPlayer->getTeam(), pLoopPlot->getTeam()))
				{
					CvCity* pOwningCity = pLoopPlot->getOwningCity();
					if (pOwningCity != NULL && pLoopPlot->isValidMovePlot(m_pPlayer->GetID(),true))
					{
						int iDistance = GET_PLAYER(pOwningCity->getOwner()).GetCityDistanceInPlots(pLoopPlot);
						//we want to stay for a while, so stay out of danger as far as possible
						if (iDistance < 4 && m_pPlayer->GetPossibleAttackers(*pLoopPlot,NO_TEAM).empty())
						{
							//try to stay away from land
							int iWeight = pLoopPlot->GetSeaBlockadeScore(m_pPlayer->GetID());

							//prefer close targets
							iWeight = max(1, iWeight - m_pPlayer->GetCityDistancePathLength(pLoopPlot));

							//try to support the troops
							if (pOwningCity->getDamage() > 0 || pOwningCity->isUnderSiege())
								iWeight *= 2;

							if (iWeight > 0)
							{
								newTarget.SetTargetType(AI_TACTICAL_TARGET_BLOCKADE_POINT);
								newTarget.SetAuxIntData(iWeight);
								m_NavalBlockadePoints.push_back(newTarget);
							}
						}
					}
				}
			}
		}
	}

	// POST-PROCESSING ON TARGETS

	// make sure high prio units have the higher scores
	UpdateTargetScores();

	//Let's clean up our naval target list.
	PrioritizeNavalTargetsAndAddToMainList();

	// since the combat simulation considers a whole area, we don't need to attack for individual units
	SortTargetListAndDropUselessTargets();

	if (GC.getLogging() && GC.getAILogging())
		DumpTacticalTargets();
}

/// Don't allow adjacent tiles to both be sentry points
void CvTacticalAI::PrioritizeNavalTargetsAndAddToMainList()
{
	// First, sort the sentry points by priority
	std::stable_sort(m_NavalBlockadePoints.begin(), m_NavalBlockadePoints.end());
	CvTacticalTarget newTarget;
	// Loop through all points in copy
	for (unsigned int iI = 0; iI < m_NavalBlockadePoints.size(); iI++)
	{
		// Is the target of an appropriate type?
		CvPlot* pPlot = GC.getMap().plot(m_NavalBlockadePoints[iI].GetTargetX(), m_NavalBlockadePoints[iI].GetTargetY());
		if (pPlot != NULL)
		{
			//Only keep top 10 targets.
			if (pPlot->getImprovementType() != NO_IMPROVEMENT || iI < 10)
			{
				newTarget.SetTargetType(AI_TACTICAL_TARGET_BLOCKADE_POINT);
				newTarget.SetTargetX(pPlot->getX());
				newTarget.SetTargetY(pPlot->getY());
				newTarget.SetDominanceZone(GetTacticalAnalysisMap()->GetDominanceZoneID(pPlot->GetPlotIndex()));
				newTarget.SetAuxIntData(m_NavalBlockadePoints[iI].GetAuxIntData());
				m_AllTargets.push_back(newTarget);
			}
		}
	}
	m_NavalBlockadePoints.clear();
}

void CvTacticalAI::ProcessDominanceZones()
{
	CvStackingDiagnostics::TurnPhaseScope phase(m_pPlayer->GetID(),"tactical_dominance");
	// Barbarian processing is straightforward -- just one big list of priorites and everything is considered at once
	if(m_pPlayer->isBarbarian())
	{
		ExtractTargetsForZone(NULL);
		AssignBarbarianMoves();
	}
	else
	{
		//high prio goes first
		AssignGlobalHighPrioMoves();

		//then confront the enemy in each tactical zone
		CvStackingDiagnostics::TurnPhaseScope zonePhase(m_pPlayer->GetID(),"tactical_zone_attacks");
		for(int iI = 0; iI < GetTacticalAnalysisMap()->GetNumZones(); iI++)
		{
			CvTacticalDominanceZone* pZone = GetTacticalAnalysisMap()->GetZoneByIndex(iI);

			PlotEmergencyPurchases(pZone);

			int iTargets = ExtractTargetsForZone(pZone);
			if (iTargets==0)
				continue;

			if (GC.getLogging() && GC.getAILogging())
			{
				CvString strLogString;
				CvCity* pZoneCity = pZone->GetZoneCity();
				strLogString.Format("Zone %d, %s, city of %s, posture %s, %d targets",  
					pZone ? pZone->GetZoneID() : -1, pZone->IsWater() ? "water" : "land",
					pZoneCity ? pZoneCity->getNameNoSpace().c_str() : "none", 
					postureNames[pZone->GetPosture()], iTargets);
				LogTacticalMessage(strLogString);
			}

			switch (pZone->GetPosture())
			{
			case TACTICAL_POSTURE_NONE:
				break; //no posture assigned so do nothing; TODO: Maybe this should be unreachable?
			case TACTICAL_POSTURE_WITHDRAW: //give up
				PlotWithdrawMoves(pZone);
				break;
			case TACTICAL_POSTURE_HEDGEHOG: //defend
				PlotHedgehogMoves(pZone);
				break;
			case TACTICAL_POSTURE_ATTRITION: //low risk attacks on units
				PlotAttritionAttacks(pZone);
				break;
			case TACTICAL_POSTURE_EXPLOIT_FLANKS: //try to kill enemy units
				PlotExploitFlanksMoves(pZone);
				break;
			case TACTICAL_POSTURE_STEAMROLL: //attack everything including cities
				PlotSteamrollMoves(pZone);
				break;
			case TACTICAL_POSTURE_SURGICAL_CITY_STRIKE: //go for the city first
				PlotSurgicalCityStrikeMoves(pZone);
				break;
			case TACTICAL_POSTURE_COUNTERATTACK: //concentrated fire on enemy units
				PlotCounterattackMoves(pZone);
				break;
			}
		}

		zonePhase.Finish();
		//second pass: bring in reinforcements
		CvStackingDiagnostics::TurnPhaseScope reinforcePhase(m_pPlayer->GetID(),"tactical_reinforcements");
		for (int iI = 0; iI < GetTacticalAnalysisMap()->GetNumZones(); iI++)
			PlotReinforcementMoves(GetTacticalAnalysisMap()->GetZoneByIndex(iI));
		reinforcePhase.Finish();

		//now mid prio moves like capturing barb camps, pillaging
		AssignGlobalMidPrioMoves();

		//finally arrange our remaining idle units for defense
		AssignGlobalLowPrioMoves();
	}

	//failsafe
	ReviewUnassignedUnits();
}

/// Choose which tactics to run and assign units to it
void CvTacticalAI::AssignGlobalHighPrioMoves()
{
	CvStackingDiagnostics::TurnPhaseScope phase(m_pPlayer->GetID(),"tactical_high_priority");
	ExtractTargetsForZone(NULL);

	//make some space near the frontline
	PlotHealMoves(true);
	//move armies first
	PlotOperationalArmyMoves();

	//garrisons sometimes make a sortie so we have to get them back
	PlotGarrisonMoves(2);
}

/// Choose which tactics to run and assign units to it
void CvTacticalAI::AssignGlobalMidPrioMoves()
{
	CvStackingDiagnostics::TurnPhaseScope phase(m_pPlayer->GetID(),"tactical_mid_priority");
	ExtractTargetsForZone(NULL);

	//air sweeps / attacks are already done during zone attacks, this is just for the remaining units
	PlotAirPatrolMoves();

	//score some goodies
	PlotGrabGoodyMoves();
	PlotCivilianAttackMoves();

	//make sure our frontline fortresses are occupied
	PlotBastionMoves(2);

	//now all attacks are done, try to move any unprocessed units out of harm's way
	PlotMovesToSafety(true);

	//try again now that other blocking units might have moved
	PlotHealMoves(false);

	//harass the enemy (plundering also happens during combat sim ...)
	PlotPillageMoves(AI_TACTICAL_TARGET_ENEMY_CITADEL, true);
	PlotPlunderTradeUnitMoves(DOMAIN_LAND);
	PlotPlunderTradeUnitMoves(DOMAIN_SEA);
	PlotPillageMoves(AI_TACTICAL_TARGET_IMPROVEMENT_RESOURCE, true);
	PlotPillageMoves(AI_TACTICAL_TARGET_IMPROVEMENT, true);
	PlotPillageMoves(AI_TACTICAL_TARGET_ENEMY_CITADEL, false);
	PlotPillageMoves(AI_TACTICAL_TARGET_IMPROVEMENT_RESOURCE, false);
	PlotPillageMoves(AI_TACTICAL_TARGET_IMPROVEMENT, false);
	PlotBlockadeMoves();
}

/// Choose which tactics to run and assign units to it
void CvTacticalAI::AssignGlobalLowPrioMoves()
{
	CvStackingDiagnostics::TurnPhaseScope phase(m_pPlayer->GetID(),"tactical_low_priority");
	ExtractTargetsForZone(NULL);

	//defense preparation for next turn
	PlotGuardImprovementMoves(2);

	//do this last after the units in need have already moved
	PlotNavalEscortMoves();

	//civilians move out of harms way last, when all potential defenders are set in place
	PlotMovesToSafety(false);
}

/// Choose which tactics to run and assign units to it (barbarian version)
void CvTacticalAI::AssignBarbarianMoves()
{
	//even barbarians like their camps
	PlotBarbarianCampDefense();

	//barbarians don't have tactical zones, they just attack everything that moves
	PlotBarbarianAttacks();
	PlotCivilianAttackMoves();

	//barbarians like to plunder as well
	PlotPillageMoves(AI_TACTICAL_TARGET_IMPROVEMENT_RESOURCE, true);
	PlotPillageMoves(AI_TACTICAL_TARGET_IMPROVEMENT, true);
	PlotPlunderTradeUnitMoves(DOMAIN_LAND);
	PlotPlunderTradeUnitMoves(DOMAIN_SEA);

	//normal roaming to find targets
	PlotBarbarianRoaming();

	//safety comes last for the barbarians ...
	PlotMovesToSafety(true /*bCombatUnits*/);
	PlotMovesToSafety(false /*bCombatUnits*/);
}

/// Assign a group of units to take down each city we can capture
bool CvTacticalAI::TryCityCaptureWithUnit(CvUnit* unit,CvPlot* target)
{
	if(!unit || unit->getOwner()!=m_pPlayer->GetID() || !target || !target->isCity() || target->getOwner()==NO_PLAYER ||
		!target->isVisible(m_pPlayer->getTeam()) || !m_pPlayer->IsAtWarWith(target->getOwner())) return false;
	CvCity* city=target->getPlotCity();
	CvPlot* approach=CvStackingOffensiveAI::GetCaptureApproachNow(unit,city);
	if(!approach) return false;
	int retaliation=0,garrison=0;
	const int damage=TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(city,unit,approach,retaliation,garrison);
	const int remaining=max(0,city->GetMaxHitPoints()-city->getDamage());
	if(damage<remaining || retaliation>=unit->GetCurrHitPoints()) return false;
	CvStackingOffensiveAI::ReleaseAssemblyHold(unit);
	CvStackingDiagnostics::Record(1,m_pPlayer->GetID(),"CAPTURE_ORDER","target=%d unit=%d from=%d approach=%d hp=%d damage=%d retaliation=%d",target->GetPlotIndex(),unit->GetID(),unit->plot()->GetPlotIndex(),approach->GetPlotIndex(),remaining,damage,retaliation);
	const int unitID=unit->GetID();
	const int turns=ExecuteMoveToPlot(unit,target,false,CvUnit::MOVEFLAG_ATTACK|CvUnit::MOVEFLAG_DESTINATION|CvUnit::MOVEFLAG_SAFE_EMBARK_ONLY);
	// A route estimate or a blocker workaround does not establish that the city
	// changed hands. The mission can delete its unit; inspect the stable plot.
	const bool captured=target->getOwner()==m_pPlayer->GetID();
	CvStackingDiagnostics::Record(1,m_pPlayer->GetID(),"CAPTURE_RESULT","target=%d unit=%d captured=%d turnsRemaining=%d ownerAfter=%d",target->GetPlotIndex(),unitID,captured,turns,target->getOwner());
	if(captured) UnitProcessed(unitID);
	return captured;
}

bool CvTacticalAI::TryReservedCityCapture(CvPlot* target)
{
	if(!CvStackingOffensiveAI::Enabled(m_pPlayer->GetID()) || !target || !target->isCity() || target->getOwner()==NO_PLAYER ||
		!target->isVisible(m_pPlayer->getTeam()) || !m_pPlayer->IsAtWarWith(target->getOwner())) return false;
	CvUnit* reserved=CvStackingOffensiveAI::GetReservedCapturer(m_pPlayer->GetID(),target->getPlotCity());
	const int reservedID=reserved?reserved->GetID():-1;
	if(TryCityCaptureWithUnit(reserved,target)) return true;
	// An objective limit, stale reservation or spent capturer must not hide a
	// surviving adjacent alternative. This scan adds no prospective path work.
	vector<int> adjacent;
	const size_t limit=(size_t)max(0,CvStacking::GetInt("AIOffensiveSupportMaximumUnits",32));
	for(int i=1;i<RING1_PLOTS && adjacent.size()<limit;++i)
	{
		CvPlot* plot=iterateRingPlots(target,i);
		if(!plot) continue;
		for(int j=0;j<plot->getNumUnits() && adjacent.size()<limit;++j)
		{
			CvUnit* unit=plot->getUnitByIndex(j);
			if(unit && unit->getOwner()==m_pPlayer->GetID() && unit->GetID()!=reservedID && !unit->isDelayedDeath() &&
				unit->isNativeDomain(plot) && CvStackingOffensiveAI::CanCapture(unit,target) &&
				unit->canMove() && !unit->isOutOfAttacks() && (unit->canUseNow() || CvStackingOffensiveAI::IsAssemblyHeld(unit)))
				adjacent.push_back(unit->GetID());
		}
	}
	for(size_t i=0;i<adjacent.size();++i)
	{
		CvUnit* unit=m_pPlayer->getUnit(adjacent[i]);
		if(!unit || unit->isDelayedDeath() || CvStackingAI::RetainCityUnit(unit) || unit->IsCoveringFriendlyCivilian() ||
			!unit->isNativeDomain(unit->plot()) || !CvStackingOffensiveAI::CanCapture(unit,target) ||
			(!unit->canUseNow() && !CvStackingOffensiveAI::IsAssemblyHeld(unit)) ||
			(CvStackingOffensiveAI::HasCommitment(unit) && !CvStackingOffensiveAI::HasCommitment(unit,target))) continue;
		if(TryCityCaptureWithUnit(unit,target)) return true;
	}
	return false;
}

void CvTacticalAI::PlotImmediateCityOpportunities()
{
	if(!CvStackingOffensiveAI::Enabled(m_pPlayer->GetID())) return;
	ClearCurrentMoveUnits(AI_TACTICAL_SURGICAL_STRIKE);
	vector<int> units,cityPlots;
	int loop=0;
	for(CvUnit* unit=m_pPlayer->firstUnit(&loop);unit;unit=m_pPlayer->nextUnit(&loop)) units.push_back(unit->GetID());
	const size_t cityLimit=(size_t)max(0,CvStacking::GetInt("AIOffensiveSupportMaximumObjectives",8));
	const int shotLimit=max(0,CvStacking::GetInt("AIOffensiveSupportMaximumUnits",32));
	const int weakPercent=CvStacking::GetInt("AIAssaultOpportunityHPPercent",30);
	for(size_t i=0;i<m_AllTargets.size() && cityPlots.size()<cityLimit;++i)
	{
		if(m_AllTargets[i].GetTargetType()!=AI_TACTICAL_TARGET_ENEMY_CITY) continue;
		CvPlot* plot=GC.getMap().plot(m_AllTargets[i].GetTargetX(),m_AllTargets[i].GetTargetY());
		if(!plot || !plot->isCity() || !plot->isVisible(m_pPlayer->getTeam()) || !m_pPlayer->IsAtWarWith(plot->getOwner())) continue;
		if(std::find(cityPlots.begin(),cityPlots.end(),plot->GetPlotIndex())!=cityPlots.end()) continue;
		CvCity* city=plot->getPlotCity();
		const bool weak=(city->GetMaxHitPoints()-city->getDamage())*100<=city->GetMaxHitPoints()*weakPercent;
		bool currentOpportunity=false;
		for(size_t j=0;j<units.size() && !currentOpportunity;++j)
		{
			CvUnit* unit=m_pPlayer->getUnit(units[j]);
			if(!unit || unit->isDelayedDeath() || !unit->canUseNow() || unit->TurnProcessed() || unit->isOutOfAttacks() ||
				CvStackingAI::RetainCityUnit(unit) ||
				(CvStackingOffensiveAI::HasCommitment(unit) && !CvStackingOffensiveAI::HasCommitment(unit,plot))) continue;
			currentOpportunity=(weak && plotDistance(*unit->plot(),*plot)<=1 && CvStackingOffensiveAI::CanCapture(unit,plot)) ||
				(!unit->shouldHeal(false) && CvStackingOffensiveAI::IsSiegeUnit(unit) && plotDistance(*unit->plot(),*plot)<=unit->GetRange() &&
				 unit->canRangeStrikeAt(plot->getX(),plot->getY()));
		}
		if(!currentOpportunity) continue;
		cityPlots.push_back(plot->GetPlotIndex());
		if(weak)
		{
			if(TryReservedCityCapture(plot))
			{
				CvStackingDiagnostics::Record(1,m_pPlayer->GetID(),"IMMEDIATE_CITY","target=%d action=capture_before_fire",plot->GetPlotIndex());
				DeleteFocusArea(plot);
			}
		}
	}
	int shots=0;
	for(size_t i=0;i<units.size() && shots<shotLimit;++i)
	{
		CvUnit* unit=m_pPlayer->getUnit(units[i]);
		if(!unit || unit->isDelayedDeath() || unit->TurnProcessed() || !unit->canUseNow() || unit->isOutOfAttacks() ||
			unit->shouldHeal(false) || !CvStackingOffensiveAI::IsSiegeUnit(unit)) continue;
		for(size_t j=0;j<cityPlots.size();++j)
		{
			CvPlot* plot=GC.getMap().plotByIndexUnchecked(cityPlots[j]);
			if(!plot || !plot->isCity() || !m_pPlayer->IsAtWarWith(plot->getOwner())) continue;
			if(CvStackingOffensiveAI::TryStationaryCityFire(unit,plot))
			{
				++shots;
				unit=m_pPlayer->getUnit(units[i]);
				CvStackingDiagnostics::Record(1,m_pPlayer->GetID(),"IMMEDIATE_CITY","target=%d unit=%d action=stationary_range_order after=%d",plot->GetPlotIndex(),units[i],unit&&!unit->isDelayedDeath()?unit->plot()->GetPlotIndex():-1);
				if(unit && !unit->isDelayedDeath() && !unit->canUseNow()) UnitProcessed(units[i]);
				break; // A unit uses only its highest-priority eligible city.
			}
		}
	}
	for(size_t i=0;i<cityPlots.size();++i)
	{
		CvPlot* plot=GC.getMap().plotByIndexUnchecked(cityPlots[i]);
		if(!plot || !plot->isCity() || !m_pPlayer->IsAtWarWith(plot->getOwner())) continue;
		CvCity* city=plot->getPlotCity();
		if((city->GetMaxHitPoints()-city->getDamage())*100<=city->GetMaxHitPoints()*weakPercent)
		{
			if(TryReservedCityCapture(plot))
			{
				CvStackingDiagnostics::Record(1,m_pPlayer->GetID(),"IMMEDIATE_CITY","target=%d action=capture_after_fire",plot->GetPlotIndex());
				DeleteFocusArea(plot);
			}
		}
	}
}

void CvTacticalAI::ExecuteCaptureCityMoves()
{
	// See how many moves of this type we can execute
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_ENEMY_CITY, AL_HIGH); pTarget!=NULL; pTarget = GetNextZoneTarget(AL_HIGH))
	{
		//mark the target whether the attack happened or not - we won't have a better chance this turn
		pTarget->SetLastAggLevel(AL_HIGH);

		// See what units we have who can reach target this turn
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
		if(pPlot != NULL && pPlot->isCity())
		{
			m_CurrentMoveCities.clear();
			CvCity* pCity = pPlot->getPlotCity();

			// Safe preparatory fire may have opened a capture while the shared
			// gathering forecast is still cached. Actual legality wins over it.
			if(TryReservedCityCapture(pPlot))
			{ if(pPlot->getOwner()==m_pPlayer->GetID()) DeleteFocusArea(pPlot);continue; }
			if(!CvStackingOffensiveAI::ContinueSiege(m_pPlayer->GetID(),pCity)) continue;

			//first try the land zone
			CvTacticalDominanceZone* pZone = GetTacticalAnalysisMap()->GetZoneByCity(pCity, false);

			//does it look good there?
			if (!pZone || (pZone->GetOverallDominanceFlag() == TACTICAL_DOMINANCE_ENEMY && !pCity->isInDangerOfFalling()))
			{
				//try again with the water zone
				pZone = GetTacticalAnalysisMap()->GetZoneByCity(pCity, true);

				if (!pZone || (pZone->GetOverallDominanceFlag() == TACTICAL_DOMINANCE_ENEMY && !pCity->isInDangerOfFalling()))
				{
					// Zone dominance counts every unit in a wide zone. The local
					// assault forecast may still find a force near this city that
					// can hold the field: an assessed ready wave, or bombardment.
					bool bLocalForce = false;
					if (CvStackingOffensiveAI::Enabled(m_pPlayer->GetID()) && CvStacking::GetInt("AIAssaultDominanceOverride",1) != 0)
					{
						const CvStackingOffensiveAI::AssaultPlan land=CvStackingOffensiveAI::AssessAssault(m_pPlayer->GetID(),pCity,DOMAIN_LAND);
						const CvStackingOffensiveAI::AssaultPlan sea=CvStackingOffensiveAI::AssessAssault(m_pPlayer->GetID(),pCity,DOMAIN_SEA);
						bLocalForce = land.bombard || sea.bombard || (land.ready && land.waveUnits>0) || (sea.ready && sea.waveUnits>0);
					}
					if (!bLocalForce)
					{
						if (GC.getLogging() && GC.getAILogging())
						{
							CvString strLogString;
							strLogString.Format("Zone %d, City of %s, is in enemy dominated zone - won't try to capture, X: %d, Y: %d, ",
								pZone ? pZone->GetZoneID() : -1, pCity->getNameNoSpace().c_str(), pCity->getX(), pCity->getY());
							LogTacticalMessage(strLogString);
						}

						CvStackingDiagnostics::Record(1, m_pPlayer->GetID(), "CITY_GATE", "target=%d:%d reason=enemy_dominance", pPlot->getX(), pPlot->getY());
						continue;
					}
					CvStackingDiagnostics::Record(1, m_pPlayer->GetID(), "CITY_GATE", "target=%d:%d reason=dominance_override", pPlot->getX(), pPlot->getY());
				}
			}

			// Always recruit both naval and land based forces if available!
			if(FindUnitsWithinStrikingDistance(pPlot))
			{
				if(CvStackingOffensiveAI::Enabled(m_pPlayer->GetID()))
				{
					const CvStackingOffensiveAI::AssaultPlan land=CvStackingOffensiveAI::AssessAssault(m_pPlayer->GetID(),pCity,DOMAIN_LAND);
					const CvStackingOffensiveAI::AssaultPlan sea=CvStackingOffensiveAI::AssessAssault(m_pPlayer->GetID(),pCity,DOMAIN_SEA);
					if(!land.ready && !sea.ready)
					{
						vector<CvUnit*> gathering;
						for(size_t i=0;i<m_CurrentMoveUnits.size();++i)
						{ CvUnit* unit=m_pPlayer->getUnit(m_CurrentMoveUnits[i].GetID()); if(unit) gathering.push_back(unit); }
						PositionUnitsAroundTarget(gathering,pPlot);
						// Safe fire during staging may open a capture while this
						// turn's assembly forecast still says the wave is incomplete.
						if(TryReservedCityCapture(pPlot) && pPlot->getOwner()==m_pPlayer->GetID())
							DeleteFocusArea(pPlot);
						continue;
					}
				}
				int iRequiredDamage = pCity->GetMaxHitPoints() - pCity->getDamage();
				int iExpectedDamagePerTurn = ComputeTotalExpectedDamage(*pTarget);

				if (iExpectedDamagePerTurn < iRequiredDamage)
				{
					//actual siege will typically be longer because not all units actually attack the city each turn
					int iMaxSiegeTurns = CvStackingOffensiveAI::Enabled(m_pPlayer->GetID()) ? CvStacking::GetInt("AIAssaultDamageHorizon",4) : 13;

					int iCityHealRate = 0;
					if (CvStackingOffensiveAI::Enabled(m_pPlayer->GetID()))
						iCityHealRate = pCity->GetAssaultHealingForecast(m_pPlayer->GetID(), iExpectedDamagePerTurn);
					else if (!pCity->IsBlockadedWaterAndLand())
					{
						iCityHealRate = /*20 in CP, 8 in VP*/ GD_INT_GET(CITY_HIT_POINTS_HEALED_PER_TURN);
						if (MOD_BALANCE_VP)
							iCityHealRate += pCity->getPopulation();
					}

					//assume the city heals each turn ...
					if ((iExpectedDamagePerTurn - iCityHealRate) * iMaxSiegeTurns < iRequiredDamage)
					{
						if (GC.getLogging() && GC.getAILogging() && pZone)
						{
							CvString strLogString;
							strLogString.Format("Zone %d, too early for attacking %s, required damage %d, expected max damage per turn %d",
								pZone ? pZone->GetZoneID() : -1, pCity->getNameNoSpace().c_str(), iRequiredDamage, iExpectedDamagePerTurn);
							LogTacticalMessage(strLogString);
						}

						CvStackingDiagnostics::Record(1, m_pPlayer->GetID(), "CITY_GATE", "target=%d:%d reason=insufficient_damage required=%d expected=%d heal=%d candidates=%u",
							pPlot->getX(), pPlot->getY(), iRequiredDamage, iExpectedDamagePerTurn, iCityHealRate, (unsigned int)m_CurrentMoveUnits.size());
						continue;
					}
				}

				//see whether we have melee units for capturing
				int iMeleeCount = 0;
				for (unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
				{
					CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
					if (!pUnit || !pUnit->canMove())
						continue;

					// Are we a melee unit
					if (CvStackingOffensiveAI::Enabled(m_pPlayer->GetID()) ? (CvStackingOffensiveAI::CanCapture(pUnit,pPlot) && pUnit->canMoveInto(*pPlot,CvUnit::MOVEFLAG_ATTACK|CvUnit::MOVEFLAG_DESTINATION)) : !pUnit->IsCanAttackRanged())
						iMeleeCount++;
				}

				if (iMeleeCount == 0 && iRequiredDamage <= 1)
				{
					if (GC.getLogging() && GC.getAILogging())
					{
						CvString strLogString;
						strLogString.Format("Zone %d, no melee units to capture %s", pZone ? pZone->GetZoneID() : -1, pCity->getNameNoSpace().c_str());
						LogTacticalMessage(strLogString);
					}

					CvStackingDiagnostics::Record(1, m_pPlayer->GetID(), "CITY_GATE", "target=%d:%d reason=no_melee required=%d candidates=%u", pPlot->getX(), pPlot->getY(), iRequiredDamage, (unsigned int)m_CurrentMoveUnits.size());
					continue;
				}

				if (GC.getLogging() && GC.getAILogging())
				{
					CvString strLogString;
					strLogString.Format("Zone %d, attempting capture of %s, required damage %d, expected max damage per turn %d",
						pZone ? pZone->GetZoneID() : -1, pCity->getNameNoSpace().c_str(), iRequiredDamage, iExpectedDamagePerTurn);
					LogTacticalMessage(strLogString);
				}

				//finally do the attack. be a bit more careful if we have few melee units
				CvStackingDiagnostics::Record(1, m_pPlayer->GetID(), "CITY_GATE", "target=%d:%d reason=attempt required=%d expected=%d candidates=%u melee=%d",
					pPlot->getX(), pPlot->getY(), iRequiredDamage, iExpectedDamagePerTurn, (unsigned int)m_CurrentMoveUnits.size(), iMeleeCount);
				ExecuteAttackWithUnits(pPlot, iMeleeCount>2 ? AL_HIGH : AL_MEDIUM);
				// Ranged softening may have opened a capture after the search chose
				// its actions. Recheck the reserved unit on the actual changed board.
				TryReservedCityCapture(pPlot);

				// Did it work?  If so, don't need a temporary dominance zone if had one here
				if (pPlot->getOwner() == m_pPlayer->GetID())
					DeleteFocusArea(pPlot);

				//do we have embarked units we need to put ashore
				if (FindEmbarkedUnitsAroundTarget(pPlot, 4))
					ExecuteLandingOperation(pPlot);
			}
			else
				CvStackingDiagnostics::Record(1, m_pPlayer->GetID(), "CITY_GATE", "target=%d:%d reason=no_eligible_units", pPlot->getX(), pPlot->getY());
		}
	}
}

/// Assign a unit to capture an undefended barbarian camp
void CvTacticalAI::PlotGrabGoodyMoves()
{
	ClearCurrentMoveUnits(AI_TACTICAL_GOODY);

	//allow a fairly big range so we can clear islands as well unless we're at war and need the units otherwise
	//note the barbarians are excluded from that check
	int iRange = m_pPlayer->IsAtWarAnyMajor() ? 6 : 11;

	//ruins first
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_GOODY); pTarget!=NULL; pTarget = GetNextZoneTarget())
	{
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
		CvUnit* pUnit =	FindUnitForThisMove(AI_TACTICAL_GOODY,pPlot,iRange);
		if (pUnit)
		{
			ExecuteMoveToPlot(pUnit, pPlot, false);

			if (pUnit->canMove())
				//can use this unit for other stuff, reset the tactmove to avoid spamming the log
				pUnit->setTacticalMove(AI_TACTICAL_MOVE_NONE);
			else
				UnitProcessed(pUnit->GetID());

			if(GC.getLogging() && GC.getAILogging())
			{
				CvString strLogString;
				strLogString.Format("Moving %s %d to grab a goody, X: %d, Y: %d", pUnit->getName().c_str(), pUnit->GetID(), pTarget->GetTargetX(), pTarget->GetTargetY());
				LogTacticalMessage(strLogString);
			}
		}
	}

	//then barb camps, occupied or not
	ClearCurrentMoveUnits(AI_TACTICAL_BARBARIAN_CAMP);
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_BARBARIAN_CAMP); pTarget!=NULL; pTarget = GetNextZoneTarget())
	{
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
		if (FindUnitsForHarassing(pPlot,iRange,-1,-1,DOMAIN_LAND,false,true,3))
		{
			ExecuteBarbarianCampMove(pPlot);
			if( GC.getLogging() && GC.getAILogging() )
			{
				CvString strLogString;
				strLogString.Format("Trying to remove barbarian camp, X: %d, Y: %d", pPlot->getX(), pPlot->getY());
				LogTacticalMessage(strLogString);
			}
		}
	}
}

void CvTacticalAI::ExecuteBarbarianTheft()
{
	vector<CvUnit*> vUsedUnits;
	for (std::list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); ++it)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(*it);
		CvCity* pCity = pUnit->plot()->GetAdjacentCity();
		if (pCity)
		{
			if (CvBarbarians::DoTakeOverCityState(pCity) || CvBarbarians::DoStealFromCity(pUnit, pCity))
				vUsedUnits.push_back(pUnit);
		}
	}
	//have to do this in two steps to keep our iterator happy
	for (size_t i=0; i<vUsedUnits.size(); i++)
	{
		vUsedUnits[i]->finishMoves();
		UnitProcessed(vUsedUnits[i]->GetID());
	}
}

/// Moved endangered units to safe hexes
void CvTacticalAI::PlotMovesToSafety(bool bCombatUnits)
{
	ClearCurrentMoveUnits(AI_TACTICAL_SAFETY);

	// Loop through all recruited units
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(*it);
		if(pUnit && pUnit->canUseForTacticalAI())
		{
			// try to flee or hide
			int iDangerLevel = pUnit->GetDanger();
			if(iDangerLevel > 0 || pUnit->plot()->IsKnownVisibleToEnemy(m_pPlayer->GetID()))
			{
				bool bAddUnit = false;
				if(bCombatUnits)
				{
					if (!pUnit->IsCombatUnit() || (pUnit->IsGarrisoned() && pUnit->getDomainType() != DOMAIN_SEA) || pUnit->getArmyID() != -1)
						continue;

					//if danger is high or we took a lot of damage last turn
					//counterintuitively, barbarians always flee, because if we get here it means we did not attack this turn!
					if(iDangerLevel>pUnit->GetMaxHitPoints() || pUnit->isProjectedToDieNextTurn() || pUnit->isBarbarian())
					{
						bAddUnit = true;
					}
				}
				else
				{
					// Civilian (or embarked) units always flee from danger
					if(!pUnit->IsCanDefend())
					{
						bAddUnit = true;
					}
				}

				if (bAddUnit)
				{
					m_CurrentMoveUnits.push_back(CvTacticalUnit(pUnit->GetID()));
					//we will later sort by "attack strength" so fake it
					//ranged/slow units should retreat first, ie have a high strength
					int iFakeStrength = (pUnit->IsCanAttackRanged() ? 30 : 20) - pUnit->baseMoves(false);
					m_CurrentMoveUnits.back().SetAttackStrength(iFakeStrength);
					m_CurrentMoveUnits.back().SetHealthPercent(1,1);
				}
			}
		}
	}

	//melee units should retreat last
	std::stable_sort(m_CurrentMoveUnits.begin(), m_CurrentMoveUnits.end());

	for(unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
		ExecuteMovesToSafestPlot(pUnit);
	}
}

/// Move barbarians across the map
void CvTacticalAI::PlotBarbarianRoaming()
{
	if (!m_pPlayer->isBarbarian())
		return;

	ClearCurrentMoveUnits(AI_TACTICAL_BARBARIAN_ROAM);

	// Loop through all recruited units
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(*it);
		if (pUnit && pUnit->canUseForTacticalAI())
			m_CurrentMoveUnits.push_back(CvTacticalUnit(pUnit->GetID()));
	}

	if(m_CurrentMoveUnits.size() > 0)
		ExecuteBarbarianRoaming();
}

//attack military units and civilians without regard for tactical zones
void CvTacticalAI::PlotBarbarianAttacks()
{
	//the Execute* functions are generic, need to set the current tactical move before calling them
	ClearCurrentMoveUnits(AI_TACTICAL_BARBARIAN_HUNT);
	ExecuteBarbarianTheft();
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT, AL_BRAVEHEART); pTarget != NULL; pTarget = GetNextZoneTarget(AL_BRAVEHEART))
		ExecuteDestroyEnemyUnits(*pTarget, AL_BRAVEHEART);
	ExecuteCaptureCityMoves();
}

/// Plunder trade routes
void CvTacticalAI::PlotPlunderTradeUnitMoves(DomainTypes eDomain)
{
	ClearCurrentMoveUnits(AI_TACTICAL_PLUNDER);

	AITacticalTargetType eTargetType = (eDomain == DOMAIN_LAND) ? AI_TACTICAL_TARGET_TRADE_UNIT_LAND : AI_TACTICAL_TARGET_TRADE_UNIT_SEA;

	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(eTargetType); pTarget!=NULL; pTarget = GetNextZoneTarget())
	{
		// See what units we have who can reach target this turn
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());

		if (FindUnitsForHarassing(pPlot,0,GD_INT_GET(MAX_HIT_POINTS)/2,-1,eDomain,true,false,5,true))
		{
			// Queue best one up to capture it
			ExecutePlunderTradeUnit(pPlot);

			if(GC.getLogging() && GC.getAILogging())
			{
				CvString strLogString;
				strLogString.Format("Plundering trade unit, X: %d, Y: %d", pTarget->GetTargetX(), pTarget->GetTargetY());
				LogTacticalMessage(strLogString);
			}
		}
	}
}

/// Process units that we recruited out of operational moves.
void CvTacticalAI::PlotOperationalArmyMoves()
{
	CvStackingDiagnostics::TurnPhaseScope phase(m_pPlayer->GetID(),"tactical_operations");
	//just so that UnitProcessed() sets the right flags
	ClearCurrentMoveUnits(AI_TACTICAL_OPERATION);

	// move all units in operations
	std::vector<int> opsToKill;
	for (size_t i=0; i<m_pPlayer->getNumAIOperations(); i++)
	{
		CvAIOperation* pOp = m_pPlayer->getAIOperationByIndex(i);
		if (!pOp->DoTurn())
			opsToKill.push_back(pOp->GetID());
	}

	//clean up - have to do this in two steps so the iterator does not get invalidated
	for (size_t i=0; i<opsToKill.size(); i++)
		m_pPlayer->getAIOperation(opsToKill[i])->Kill();
	PlotStackingOffensiveMoves();
}

void CvTacticalAI::PlotStackingOffensiveMoves()
{
	CvStackingDiagnostics::TurnPhaseScope phase(m_pPlayer->GetID(),"stacking_offensive_moves");
	vector<CvStackingOffensiveAI::TacticalForce> forces;
	CvStackingOffensiveAI::TacticalForces(m_pPlayer->GetID(),forces);
	for(size_t i=0;i<forces.size();++i)
	{
		CvPlot* target=GC.getMap().plotByIndexUnchecked(forces[i].target);
		if(!target || !target->isCity() || !m_pPlayer->IsAtWarWith(target->getOwner())) continue;
		vector<CvUnit*> units;
		for(size_t j=0;j<forces[i].units.size();++j)
		{ CvUnit* unit=m_pPlayer->getUnit(forces[i].units[j]);if(unit && unit->canUseNow()) units.push_back(unit); }
		if(!units.empty()) PositionUnitsAroundTarget(units,target);
	}
}

/// Assigns units to pillage enemy improvements
void CvTacticalAI::PlotPillageMoves(AITacticalTargetType eTarget, bool bImmediate)
{
	ClearCurrentMoveUnits(AI_TACTICAL_PILLAGE);

	int iBaseDamage = /*25*/ GD_INT_GET(PILLAGE_HEAL_AMOUNT);
	CvString szTargetName = "";
	if(GC.getLogging() && GC.getAILogging())
	{
		if (eTarget == AI_TACTICAL_TARGET_ENEMY_CITADEL)
		{
			szTargetName = "Citadel";
			iBaseDamage = 0; //also undamaged units may pillage this
		}
		else if (eTarget == AI_TACTICAL_TARGET_IMPROVEMENT_RESOURCE)
		{
			szTargetName = "Improved Resource";
			iBaseDamage = 0; //also undamaged units may pillage this
		}
		else if (eTarget == AI_TACTICAL_TARGET_IMPROVEMENT)
		{
			szTargetName = "Improvement";
		}
	}

	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(eTarget); pTarget != NULL; pTarget = GetNextZoneTarget())
	{
		// See what units we have who can reach target this turn
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());

		int iMinDamage = iBaseDamage;
		CvTacticalDominanceZone* pZone = GetTacticalAnalysisMap()->GetZoneByPlot(pPlot);
		if (pZone)
		{
			//do not move in to pillage when we are fleeing from the zone (but we may pillage while withdrawing)
			if (pZone->GetPosture() == TACTICAL_POSTURE_WITHDRAW)
				continue;

			if (pZone->IsWater())
				iMinDamage = 0;
			else if (pZone->GetOverallDominanceFlag() == TACTICAL_DOMINANCE_ENEMY)
				iMinDamage /= 2;
		}

		// Don't do it if an enemy unit became visible in the meantime
		if (pPlot->getVisibleEnemyDefender(m_pPlayer->GetID()) != NULL)
			continue;

		if (bImmediate)
		{
			// try paratroopers first, not because they are more effective, just because it looks cooler...
			if (eTarget != AI_TACTICAL_TARGET_IMPROVEMENT && FindParatroopersWithinStrikingDistance(pPlot,true))
			{
				// Queue best one up to capture it
				ExecuteParadropPillage(pPlot);

				if (GC.getLogging() && GC.getAILogging())
				{
					CvString strLogString;
					strLogString.Format("Paratrooping in to pillage %s, X: %d, Y: %d", szTargetName.GetCString(), pTarget->GetTargetX(), pTarget->GetTargetY());
					LogTacticalMessage(strLogString);
				}

			}
			else if (FindUnitsForHarassing(pPlot, 0, GD_INT_GET(MAX_HIT_POINTS) / 3, GD_INT_GET(MAX_HIT_POINTS) - iMinDamage, DOMAIN_LAND, true, false, 1))
			{
				if (ExecutePillage(pPlot))
				{
					if (GC.getLogging() && GC.getAILogging())
					{
						CvString strLogString;
						strLogString.Format("Pillaging %s, X: %d, Y: %d", szTargetName.GetCString(), pTarget->GetTargetX(), pTarget->GetTargetY());
						LogTacticalMessage(strLogString);
					}
				}
			}
		}
		else if (FindUnitsForHarassing(pPlot, 2, GD_INT_GET(MAX_HIT_POINTS) / 2, GD_INT_GET(MAX_HIT_POINTS) - iMinDamage, DOMAIN_LAND, false, false, 1))
		{
			//be careful when sending out single units ...
			CvTacticalDominanceZone* pZone = GetTacticalAnalysisMap()->GetZoneByPlot(pPlot);
			if (!pZone || pZone->GetOverallDominanceFlag() == TACTICAL_DOMINANCE_ENEMY)
				continue;

			CvUnit* pUnit = (m_CurrentMoveUnits.size() > 0) ? m_pPlayer->getUnit(m_CurrentMoveUnits.begin()->GetID()) : 0;
			if (pUnit && pUnit->canMoveInto(*pPlot, CvUnit::MOVEFLAG_DESTINATION))
			{
				ExecuteMoveToPlot(pUnit, pPlot, true, CvUnit::MOVEFLAG_NO_EMBARK | CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER);

				if (GC.getLogging() && GC.getAILogging())
				{
					CvString strLogString;
					strLogString.Format("Moving toward %s for pillage, X: %d, Y: %d", szTargetName.GetCString(), pTarget->GetTargetX(), pTarget->GetTargetY());
					LogTacticalMessage(strLogString);
				}

				UnitProcessed(pUnit->GetID());
			}
		}
	}
}

/// Move barbarian ships to disrupt usage of water improvements
void CvTacticalAI::PlotBlockadeMoves()
{
	ClearCurrentMoveUnits(AI_TACTICAL_BLOCKADE);

	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_BLOCKADE_POINT); pTarget!=NULL; pTarget = GetNextZoneTarget())
	{
		// See what units we have who can reach target this turn
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
		if (FindUnitsForHarassing(pPlot, 4, GD_INT_GET(MAX_HIT_POINTS)/2, -1, DOMAIN_SEA, false, false, 1))
		{
			// Queue best one up to capture it
			ExecuteNavalBlockadeMove(pPlot);

			if(GC.getLogging() && GC.getAILogging())
			{
				CvString strLogString;
				strLogString.Format("Moving into enemy territory for a naval blockade with move to, X: %d, Y: %d", pTarget->GetTargetX(), pTarget->GetTargetY());
				LogTacticalMessage(strLogString);
			}
		}
	}
}

void CvTacticalAI::PlotCivilianAttackMoves()
{
	ClearCurrentMoveUnits(AI_TACTICAL_CAPTURE);
	ExecuteCivilianAttackMoves(AI_TACTICAL_TARGET_HIGH_PRIORITY_CIVILIAN);
	ExecuteCivilianAttackMoves(AI_TACTICAL_TARGET_LOW_PRIORITY_CIVILIAN);
}

/// Assigns units to capture undefended civilians
void CvTacticalAI::ExecuteCivilianAttackMoves(AITacticalTargetType eTargetType)
{
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(eTargetType); pTarget!=NULL; pTarget = GetNextZoneTarget())
	{
		// See what units we have who can reach target this turn
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
		if(FindUnitsForHarassing(pPlot,1,GD_INT_GET(MAX_HIT_POINTS)/2,-1,DOMAIN_LAND,false,false,1))
		{
			for (size_t i = 0; i < m_CurrentMoveUnits.size(); i++)
			{
				CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[i].GetID());
				if (!pUnit || !pUnit->canMoveInto(*pPlot, CvUnit::MOVEFLAG_ATTACK))
					continue;
				//don't allow humans to use civilians as bait to lure units out of camps
				if (pUnit->GetDanger() == 0 || pUnit->plot()->getImprovementType()!=(ImprovementTypes)GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT))
				{
					pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pPlot->getX(), pPlot->getY(), CvUnit::MOVEFLAG_NO_EMBARK);

					// Delete this unit from those we have to move
					if (!pUnit->canMove())
						UnitProcessed(m_CurrentMoveUnits[i].GetID());

					if (GC.getLogging() && GC.getAILogging())
					{
						CvString strLogString;
						switch (eTargetType)
						{
						case AI_TACTICAL_TARGET_HIGH_PRIORITY_CIVILIAN:
							strLogString.Format("Attacking high priority civilian, X: %d, Y: %d", pTarget->GetTargetX(),
								pTarget->GetTargetY());
							break;
						case AI_TACTICAL_TARGET_LOW_PRIORITY_CIVILIAN:
							strLogString.Format("Attacking low priority civilian, X: %d, Y: %d", pTarget->GetTargetX(),
								pTarget->GetTargetY());
							break;
						default:
							UNREACHABLE(); // Unsupported `eTargetType`.
						}
						LogTacticalMessage(strLogString);
					}

					break;
				}
			}
		}
	}
}

/// Assigns units to heal
void CvTacticalAI::PlotHealMoves(bool bFirstPass)
{
	ClearCurrentMoveUnits(AI_TACTICAL_HEAL);

	// Loop through all recruited units
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(*it);
		if (!pUnit || !pUnit->canUseForTacticalAI())
			continue;

		if (pUnit->shouldHeal(bFirstPass))
			m_CurrentMoveUnits.push_back(CvTacticalUnit(pUnit->GetID()));
	}

	if(m_CurrentMoveUnits.size() > 0)
		ExecuteHeals(bFirstPass);
}

/// Assigns a barbarian to go protect an undefended camp
void CvTacticalAI::PlotBarbarianCampDefense()
{
	ClearCurrentMoveUnits(AI_TACTICAL_BARBARIAN_CAMP);

	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_BARBARIAN_CAMP); pTarget!=NULL; pTarget = GetNextZoneTarget())
	{
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());

		//for the barbarian player AI_TACTICAL_TARGET_BARBARIAN_CAMP does not automatically mean the camp is empty of _barbarian_ defenders (check is only for enemy units)
		CvUnit* currentDefender = pPlot->getBestDefender(BARBARIAN_PLAYER);
		if (currentDefender)
		{
			if (currentDefender->CanUpgradeRightNow(true) && !currentDefender->IsHurt())
			{
				CvUnit* pNewUnit = currentDefender->DoUpgrade(true);
				if (pNewUnit)
					UnitProcessed(pNewUnit->GetID());
			}
			else if (currentDefender->IsCanAttackRanged())
			{
				//don't leave camp
				TacticalAIHelpers::PerformRangedOpportunityAttack(currentDefender);
				currentDefender->PushMission(CvTypes::getMISSION_SKIP());
			}
			else
			{
				//capture unprotected civilians if we can return to camp in the same turn
				CvPlot** neighbors = GC.getMap().getNeighborsShuffled(pPlot);
				for (int i = 0; i < NUM_DIRECTION_TYPES; i++)
				{
					CvPlot* pNeighbor = neighbors[i];
					if (!pNeighbor)
						continue;

					if (!pNeighbor->isEnemyUnit(m_pPlayer->GetID(), true, true, true, true) &&
						pNeighbor->isEnemyUnit(m_pPlayer->GetID(), false, true, true, true) &&
						currentDefender->TurnsToReachTarget(pPlot,0,1)==0)
					{
						currentDefender->PushMission(CvTypes::getMISSION_MOVE_TO(), pNeighbor->getX(), pNeighbor->getY());
						currentDefender->PushMission(CvTypes::getMISSION_MOVE_TO(), pPlot->getX(), pPlot->getY());
						break;
					}
				}

				//melee may attack but never leave camp (because they won't return then)
				TacticalAIHelpers::PerformOpportunityAttack(currentDefender,false);
				currentDefender->PushMission(CvTypes::getMISSION_SKIP());
			}

			UnitProcessed(currentDefender->GetID());
		}
		else if (FindUnitsForHarassing(pPlot,5,-1,-1,DOMAIN_LAND,false,false,1))
		{
			CvUnit* pUnit = (m_CurrentMoveUnits.size() > 0) ? m_pPlayer->getUnit(m_CurrentMoveUnits.begin()->GetID()) : 0;
			ExecuteMoveToPlot(pUnit,pPlot);
			if (GC.getLogging() && GC.getAILogging())
			{
				CvString strLogString;
				strLogString.Format("Moving to protect camp, X: %d, Y: %d", pTarget->GetTargetX(), pTarget->GetTargetY());
				LogTacticalMessage(strLogString);
			}
		}
	}
}

/// Make a defensive move to garrison a city
void CvTacticalAI::PlotGarrisonMoves(int iNumTurnsAway)
{
	ClearCurrentMoveUnits(AI_TACTICAL_GARRISON);

	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_FRIENDLY_CITY); pTarget!=NULL; pTarget = GetNextZoneTarget())
	{
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
		CvCity* pCity = pPlot->getPlotCity();
		if(!pCity)
			continue;

		// it's possible that the city did not perform a ranged attack this turn yet although enemies are present
		// this depends on the tactical posture ... so let's try again here as a safety net
		CvUnit* pEnemyPlot = pCity->getBestRangedStrikeTarget();
		if (pEnemyPlot)
			pCity->rangeStrike(pEnemyPlot->getX(), pEnemyPlot->getY());

		if (CvStackingAI::Enabled(m_pPlayer->GetID()))
		{
			// A city may hold several units but only its assessed defenders are reserved.
			// Do not upgrade/move units while iterating its mutable unit list.
			vector<int> retained;
			for (int i = 0; i < pPlot->getNumUnits(); ++i)
			{
				CvUnit* defender = pPlot->getUnitByIndex(i);
				if (!defender || defender->getOwner()!=m_pPlayer->GetID() || defender->getArmyID()!=-1 || defender->TurnProcessed()) continue;
				if (CvStackingAI::RetainCityUnit(defender)) retained.push_back(defender->GetID());
			}
			CvUnit* candidate = FindUnitForThisMove(AI_TACTICAL_GARRISON, pPlot, iNumTurnsAway);
			if (candidate)
			{
				const int candidateID = candidate->GetID();
				const int from = candidate->plot()->GetPlotIndex();
				const int turns = ExecuteMoveToPlot(candidate,pPlot,false);
				// A move may process/upgrade the unit even with bSetProcessed=false.
				CvUnit* moved = m_pPlayer->getUnit(candidateID);
				const int after = moved && moved->plot() ? moved->plot()->GetPlotIndex() : -1;
				CvStackingDiagnostics::Record(1,m_pPlayer->GetID(),"GARRISON_ASSIGN","city=%d unit=%d from=%d after=%d result=%d present=%d",pCity->GetID(),candidateID,from,after,turns,moved!=NULL);
				if (moved && !moved->isDelayedDeath() && !moved->TurnProcessed() && turns!=INT_MAX && after!=from) UnitProcessed(candidateID);
			}
			// Re-evaluate after arrival: release an old defender when the new one is adequate.
			for (size_t i=0;i<retained.size();++i)
			{
				CvUnit* defender=m_pPlayer->getUnit(retained[i]);
				if (!defender || !CvStackingAI::RetainCityUnit(defender)) continue;
				TacticalAIHelpers::PerformOpportunityAttack(defender,false);
				defender=m_pPlayer->getUnit(retained[i]);
				if (!defender || defender->isDelayedDeath()) continue;
				defender->PushMission(CvTypes::getMISSION_SKIP());
				CvStackingDiagnostics::Record(1,m_pPlayer->GetID(),"CITY_RETAIN","city=%d plot=%d unit=%d domain=%d role=%d ranged=%d siege=%d garrison=%d hp=%d reason=defense_requirement",
					pCity->GetID(),pPlot->GetPlotIndex(),defender->GetID(),defender->getDomainType(),defender->AI_getUnitAIType(),
					defender->IsCanAttackRanged(),CvStackingOffensiveAI::IsSiegeUnit(defender),defender->IsGarrisoned(),defender->GetCurrHitPoints());
				UnitProcessed(defender->GetID()); // may upgrade/delete the old unit; no dereference afterward
			}
			continue;
		}

		// ignore core cities here (handled by homeland ai)
		if (!pCity->isBorderCity() && !pCity->GetCityCitizens()->AnyPlotBlockaded() && !m_pPlayer->GetMilitaryAI()->IsExposedToEnemy(pCity,NO_PLAYER))
			continue;

		for (int iI = 0; iI < pPlot->getNumUnits(); iI++)
		{
			CvUnit* pUnit = pPlot->getUnitByIndex(iI);
			// Naval units in cities shouldn't stay idle
			if (pUnit->getDomainType() == DOMAIN_SEA)
			{
				if (pUnit->getOwner() != m_pPlayer->GetID())
					continue;

				m_CurrentMoveUnits.push_back(CvTacticalUnit(pUnit->GetID()));
			}
		}

		//note that garrisons do not need to be "recruited" into tactical AI
		CvUnit* pGarrison = pCity->GetGarrisonedUnit();

		// Allow valid land or naval garrisons, but don't use recon units as garrisons
		if (pGarrison && (!pGarrison->CanGarrison() || pGarrison->getUnitInfo().GetDefaultUnitAIType() == UNITAI_EXPLORE))
			pGarrison = NULL;

		if (pGarrison)
		{
			if (pGarrison->CanUpgradeRightNow(false) && !pGarrison->IsHurt())
			{
				// Don't upgrade if we will go over supply
				if (m_pPlayer->GetNumUnitsToSupply() < m_pPlayer->GetNumUnitsSupplied() || !pGarrison->isNoSupply())
				{
					CvUnit* pNewUnit = pGarrison->DoUpgrade();
					if (pNewUnit)
						UnitProcessed(pNewUnit->GetID());
				}
			}

			//sometimes we have an accidental garrison ...
			if (pGarrison->AI_getUnitAIType() == UNITAI_EXPLORE || pGarrison->isDelayedDeath() || pGarrison->TurnProcessed() || pGarrison->getArmyID()!=-1)
				continue;

			//first check how many enemies are around
			int iEnemyCount = 0;
			for (int i = RING0_PLOTS; i < RING3_PLOTS; i++)
			{
				CvPlot* pNeighbor = iterateRingPlots(pPlot, i);
				if (pNeighbor && pNeighbor->isEnemyUnit(m_pPlayer->GetID(), true, true))
				{
					if (i < RING1_PLOTS)
						iEnemyCount++;
					else
					{
						CvUnit* pEnemy = pNeighbor->getBestDefender(NO_PLAYER, m_pPlayer->GetID(), NULL, true);
						ASSERT(pEnemy, "isEnemyUnit is true, but getBestDefender didn't return a unit");
						if (!pEnemy)
							continue;
						ReachablePlots reachablePlots = pEnemy->GetAllPlotsInReachThisTurn(true, true, true, pEnemy->maxMoves());

						if (reachablePlots.find(pPlot->GetPlotIndex()) != reachablePlots.end())
							iEnemyCount++;
					}
				}
			}

			//note: ranged garrisons are also used in ExecuteDestroyUnit etc if they can hit a target without moving
			//here we have more advanced logic and allow some movement if it's safe (and it's not our last stand)
			TacticalAIHelpers::PerformOpportunityAttack(pGarrison, iEnemyCount < 2 && m_pPlayer->getNumCities() > 1 );

			//no need to call SetProcessed() because the unit was never in currentTurnUnits
			//do not call finishMoves() else the garrison will not heal!
			pGarrison->PushMission(CvTypes::getMISSION_SKIP());
			pGarrison->SetTurnProcessed(true);

			//don't try to find a better garrison while under siege
			if (pCity->isUnderSiege())
				continue;
		}

		//prefer ranged land units as garrisons ...
		bool bWantGarrison = (pGarrison == NULL || !pGarrison->isNativeDomain(pPlot) || !pGarrison->IsCanAttackRanged() || pGarrison->GetRange() < 2);
		if ( bWantGarrison && pCity->NeedsGarrison() )
		{
			// Grab units that make sense for this move type
			CvUnit* pUnit = FindUnitForThisMove(AI_TACTICAL_GARRISON, pPlot, iNumTurnsAway);
			if (pUnit)
			{
				//move out old garrison if necessary
				if (pGarrison && pUnit->CanSafelyReachInXTurns(pPlot, 0))
				{
					CvPlot* pFreePlot = pCity->GetPlotForNewUnit(pGarrison->getUnitType(), false);
					if (pFreePlot)
						//do not set it processed, it should be considered for other tactical moves later
						ExecuteMoveToPlot(pGarrison, pFreePlot, false);
				}

				//if the old garrison did not move out this will fail (possibly also for other reasons)
				int iTurnsLeft = ExecuteMoveToPlot(pUnit, pPlot);

				//if everything went according to plan ...
				if (iTurnsLeft != INT_MAX)
				{
					if (GC.getLogging() && GC.getAILogging())
					{
						CvString strLogString;
						strLogString.Format("Unit %d, moving to garrison, X: %d, Y: %d, Priority: %d, Turns Away: %d", 
							pUnit->GetID(), pTarget->GetTargetX(), pTarget->GetTargetY(), pTarget->GetAuxIntData(), iTurnsLeft);
						LogTacticalMessage(strLogString);
					}

					//just in case we're doing this with enemy arounds and have movement left
					TacticalAIHelpers::PerformOpportunityAttack(pUnit);

					//the new garrison came from the tactical AI current turn units, so need to mark it
					UnitProcessed(pUnit->GetID());
				}
			}
		}
	}

	for (size_t iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
		if (!pUnit)
			continue;

		bool bUpgraded = false;
		if (pUnit->CanUpgradeRightNow(false) && !pUnit->IsHurt())
		{
			// Don't upgrade if we will go over supply
			if (m_pPlayer->GetNumUnitsToSupply() < m_pPlayer->GetNumUnitsSupplied() || !pUnit->isNoSupply())
			{
				CvUnit* pNewUnit = pUnit->DoUpgrade();
				if (pNewUnit)
				{
					bUpgraded = true;
					UnitProcessed(pNewUnit->GetID());
				}
			}
		}

		if (!bUpgraded)
			TacticalAIHelpers::PerformOpportunityAttack(pUnit, true);
	}
}

/// Establish a defensive bastion adjacent to a city
void CvTacticalAI::PlotBastionMoves(int iNumTurnsAway)
{
	ClearCurrentMoveUnits(AI_TACTICAL_GUARD);

	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_DEFENSIVE_BASTION); pTarget!=NULL; pTarget = GetNextZoneTarget())
	{
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
		if (!TacticalAIHelpers::IsCloseToContestedBorder(m_pPlayer,pPlot))
			continue;

		// Grab units that make sense for this move type
		CvUnit* pUnit = FindUnitForThisMove(AI_TACTICAL_GUARD, pPlot, iNumTurnsAway);

		//move may fail if the plot is already occupied (can happen if another unit moved there during this turn)
		if (pUnit && ExecuteMoveToPlot(pUnit, pPlot, true, CvUnit::MOVEFLAG_SAFE_EMBARK_ONLY)==0)
		{
			if (pUnit->CanUpgradeRightNow(false) && !pUnit->IsHurt())
			{
				// Don't upgrade if we will go over supply
				if (m_pPlayer->GetNumUnitsToSupply() < m_pPlayer->GetNumUnitsSupplied() || !pUnit->isNoSupply())
				{
					CvUnit* pNewUnit = pUnit->DoUpgrade();
					if (pNewUnit)
						UnitProcessed(pNewUnit->GetID());
				}
			}
			if (GC.getLogging() && GC.getAILogging())
			{
				CvString strLogString;
				strLogString.Format("Bastion, X: %d, Y: %d, Priority: %d, Turns Away: %d", pTarget->GetTargetX(), pTarget->GetTargetY(), pTarget->GetAuxIntData(), iNumTurnsAway);
				LogTacticalMessage(strLogString);
			}
		}
	}
}

/// Make a defensive move to guard an improvement
void CvTacticalAI::PlotGuardImprovementMoves(int iNumTurnsAway)
{
	ClearCurrentMoveUnits(AI_TACTICAL_GUARD);

	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_IMPROVEMENT_TO_DEFEND); pTarget!=NULL; pTarget = GetNextZoneTarget())
	{
		// Grab units that make sense for this move type
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
		CvUnit* pUnit = FindUnitForThisMove(AI_TACTICAL_GUARD, pPlot, iNumTurnsAway);

		//move may fail if the plot is already occupied (can happen if another unit moved there during this turn)
		if (pUnit && ExecuteMoveToPlot(pUnit, pPlot, true, CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER)==0)
		{
			if (pUnit->CanUpgradeRightNow(false) && !pUnit->IsHurt())
			{
				// Don't upgrade if we will go over supply
				if (m_pPlayer->GetNumUnitsToSupply() < m_pPlayer->GetNumUnitsSupplied() || !pUnit->isNoSupply())
				{
					CvUnit* pNewUnit = pUnit->DoUpgrade();
					if (pNewUnit)
						UnitProcessed(pNewUnit->GetID());
				}
			}
			if(GC.getLogging() && GC.getAILogging())
			{
				CvString strLogString;
				strLogString.Format("Guard Improvement, X: %d, Y: %d, Turns Away: %d", pTarget->GetTargetX(), pTarget->GetTargetY(), iNumTurnsAway);
				LogTacticalMessage(strLogString);
			}
		}
	}
}

/// Set fighters to intercept
void CvTacticalAI::PlotAirPatrolMoves()
{
	ClearCurrentMoveUnits(AI_TACTICAL_AIRPATROL);
	std::vector<CvPlot*> checkedPlotList;

	// Loop through all recruited units
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(*it);
		if (pUnit && pUnit->getDomainType()==DOMAIN_AIR && pUnit->canUseForTacticalAI())
		{
			// Am I eligible to intercept? We only commandeered units which won't be rebased
			if(pUnit->canAirPatrol(NULL))
			{
				CvPlot* pUnitPlot = pUnit->plot();
				int iNumNearbyBombers = m_pPlayer->GetMilitaryAI()->GetNumEnemyAirUnitsInRange(pUnitPlot, pUnit->GetRange(), false/*bCountFighters*/, true/*bCountBombers*/);
				int iNumNearbyFighters = m_pPlayer->GetMilitaryAI()->GetNumEnemyAirUnitsInRange(pUnitPlot, pUnit->GetRange(), true/*bCountFighters*/, false/*bCountBombers*/);
				int iNumPlotNumAlreadySet = std::count(checkedPlotList.begin(), checkedPlotList.end(), pUnitPlot);

				// To at least intercept once if only one bomber found.
				if (iNumNearbyBombers == 1)
					iNumNearbyBombers++;

				// TODO: we should not just use any interceptor but the best one (depending on promotions etc)
				int maxInterceptorsWanted = (iNumNearbyBombers / 2) + (iNumNearbyFighters / 4);
				if (iNumPlotNumAlreadySet < maxInterceptorsWanted)
				{
					checkedPlotList.push_back(pUnitPlot);
					m_CurrentMoveUnits.push_back(CvTacticalUnit(pUnit->GetID()));
				}
			}
		}
	}

	if(m_CurrentMoveUnits.size() > 0)
	{
		ExecuteAirPatrolMoves();
	}
}

/// Spend money to buy defenses
void CvTacticalAI::PlotEmergencyPurchases(CvTacticalDominanceZone* pZone)
{
	if(!pZone || pZone->IsWater())
		return;

	CvCity* pCity = pZone->GetZoneCity();
	if (!pCity || pCity->getOwner() != m_pPlayer->GetID())
		return;

	// Don't waste money if there's no hope
	if (pCity->isInDangerOfFalling())
		return;

	// Sometimes buying a unit is useless
	bool bWantUnits = true;
	if (MOD_BALANCE_PURCHASED_UNIT_DAMAGE && pCity->getDamage() * 2 > pCity->GetMaxHitPoints())
		bWantUnits = false;

	// If we need additional units - ignore the supply limit here, we're probably losing units anyway
	if (pZone->GetOverallDominanceFlag()>TACTICAL_DOMINANCE_FRIENDLY || pCity->isUnderSiege())
	{
		if (!MOD_BALANCE_BUILDING_INVESTMENTS)
			m_pPlayer->GetMilitaryAI()->BuyEmergencyBuilding(pCity);

		if (!MOD_BALANCE_UNIT_INVESTMENTS)
		{
			//only buy ranged if there's no garrison
			//otherwise it will be placed outside of the city and most probably die instantly
			if (!pCity->HasGarrison())
				m_pPlayer->GetMilitaryAI()->BuyEmergencyUnit(UNITAI_RANGED, pCity);
			else if (bWantUnits)
			{
				//in water zones buy naval melee
				if (pZone->IsWater() && pCity->isCoastal())
					m_pPlayer->GetMilitaryAI()->BuyEmergencyUnit(UNITAI_ATTACK_SEA, pCity);
				else
					//otherwise buy defensive land units
					if (!MOD_AI_UNIT_PRODUCTION)
						m_pPlayer->GetMilitaryAI()->BuyEmergencyUnit(GC.getGame().randRangeExclusive(0, 5, CvSeeder(pCity->plot()->GetPseudoRandomSeed())) < 2 ? UNITAI_COUNTER : UNITAI_DEFENSE, pCity);
					else //AI Unit Production : Counter is AA only now
						m_pPlayer->GetMilitaryAI()->BuyEmergencyUnit(UNITAI_DEFENSE, pCity);
			}
		}
	}
}

/// Move naval units over top of unprotected embarked units
void CvTacticalAI::PlotNavalEscortMoves()
{
	ClearCurrentMoveUnits(AI_TACTICAL_ESCORT);

	std::vector<CvUnit*> vTargetUnits;
	int iLoop = 0;
	for(CvUnit* pLoopUnit = m_pPlayer->firstUnit(&iLoop); pLoopUnit != NULL; pLoopUnit = m_pPlayer->nextUnit(&iLoop))
	{
		if (pLoopUnit->isEmbarked())
			vTargetUnits.push_back(pLoopUnit);
	}

	// Loop through all recruited units
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(*it);
		if (pUnit && pUnit->canUseForTacticalAI() && !pUnit->shouldHeal(false))
		{
			// Am I a naval combat unit?
			if(pUnit->getDomainType() == DOMAIN_SEA && pUnit->IsCanAttack())
			{
				//any embarked unit close by?
				int iMaxDist = pUnit->getMoves();
				for (size_t i=0; i<vTargetUnits.size(); i++)
				{
					if (plotDistance(*pUnit->plot(),*vTargetUnits[i]->plot())<=iMaxDist)
					{
						m_CurrentMoveUnits.push_back(CvTacticalUnit(pUnit->GetID()));
						break;
					}
				}
			}
		}
	}

	if(m_CurrentMoveUnits.size() > 0)
	{
		ExecuteEscortEmbarkedMoves(vTargetUnits);
	}
}

// PLOT MOVES FOR ZONE TACTICAL POSTURES

/// Win an attrition campaign with bombardments
void CvTacticalAI::PlotAttritionAttacks(CvTacticalDominanceZone* pZone)
{
	(void)pZone; //unused but can be inspected
	ClearCurrentMoveUnits(AI_TACTICAL_ATTRITION);

	//todo: the targets are sorted in a very rough "how bad can they hit us" order
	//but we should probably sort them in a "how bad can we hit them" order
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT, AL_LOW); pTarget!=NULL; pTarget = GetNextZoneTarget(AL_LOW))
		ExecuteDestroyEnemyUnits(*pTarget,AL_LOW);

	//don't expose our units for city attacks here; if we are likely to succeed we don't call PlotAttritionAttacks
}

/// Defeat enemy units by using our advantage in numbers
void CvTacticalAI::PlotExploitFlanksMoves(CvTacticalDominanceZone* pZone)
{
	(void)pZone; //unused but can be inspected
	ClearCurrentMoveUnits(AI_TACTICAL_FLANKATTACK);

	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT, AL_MEDIUM); pTarget!=NULL; pTarget = GetNextZoneTarget(AL_MEDIUM))
		ExecuteDestroyEnemyUnits(*pTarget, AL_MEDIUM);

	//just in case there is a city ... it can happen that the city is wide open and the defenders are on another island
	ExecuteCaptureCityMoves();
}

/// We have more overall strength than enemy, defeat his army first
void CvTacticalAI::PlotSteamrollMoves(CvTacticalDominanceZone* pZone)
{
	(void)pZone; //unused but can be inspected
	ClearCurrentMoveUnits(AI_TACTICAL_STEAMROLL);

	// See if there are any kill attacks we can make.
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT, AL_HIGH); pTarget != NULL; pTarget = GetNextZoneTarget(AL_HIGH))
		ExecuteDestroyEnemyUnits(*pTarget, AL_HIGH);

	// Now go after the city
	ExecuteCaptureCityMoves();
}

/// We should be strong enough to take out the city before the enemy can whittle us down with ranged attacks
void CvTacticalAI::PlotSurgicalCityStrikeMoves(CvTacticalDominanceZone* pZone)
{
	(void)pZone; //unused but can be inspected
	ClearCurrentMoveUnits(AI_TACTICAL_SURGICAL_STRIKE);

	// Attack the city first
	ExecuteCaptureCityMoves();

	// Take any other really good attacks we've set up
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT, AL_MEDIUM); pTarget != NULL; pTarget = GetNextZoneTarget(AL_MEDIUM))
		ExecuteDestroyEnemyUnits(*pTarget, AL_MEDIUM);
}

/// Build a defensive shell around this city
void CvTacticalAI::PlotHedgehogMoves(CvTacticalDominanceZone* pZone)
{
	ClearCurrentMoveUnits(AI_TACTICAL_HEDGEHOG);

	// Be careful with our units, we don't have so many
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT, AL_LOW); pTarget != NULL; pTarget = GetNextZoneTarget(AL_LOW))
		ExecuteDestroyEnemyUnits(*pTarget, AL_LOW);

	// exception : early reinforcement before attacks in other zones are considered
	PlotReinforcementMoves(pZone);
}

/// Try to push back the invader
void CvTacticalAI::PlotCounterattackMoves(CvTacticalDominanceZone* pZone)
{
	(void)pZone; //unused but can be inspected
	ClearCurrentMoveUnits(AI_TACTICAL_COUNTERATTACK);

	// Attack priority unit targets
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT, AL_MEDIUM); pTarget != NULL; pTarget = GetNextZoneTarget(AL_MEDIUM))
		ExecuteDestroyEnemyUnits(*pTarget, AL_MEDIUM);

}

/// Withdraw out of current dominance zone
void CvTacticalAI::PlotWithdrawMoves(CvTacticalDominanceZone* pZone)
{
	if (!pZone)
		return;

	ClearCurrentMoveUnits(AI_TACTICAL_WITHDRAW);

	// Loop through all recruited units
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(*it);
		if (pUnit && pUnit->canUseForTacticalAI())
		{
			// Recent, healthy deployments need to attack!
			if (pUnit->IsRecentlyDeployedFromOperation() && (pUnit->GetCurrHitPoints() > pUnit->GetMaxHitPoints()/2))
				continue;

			// Am I in the current dominance zone?
			// Units in other dominance zones need to fend for themselves, depending on their own posture
			CvTacticalDominanceZone* pUnitZone = GetTacticalAnalysisMap()->GetZoneByPlot(pUnit->plot());
			if (pUnitZone != pZone)
				continue;

			// However, zones might overlap borders, so double check that we don't give up our border forts
			if (pZone->GetTerritoryType() != TACTICAL_TERRITORY_FRIENDLY)
			{
				if (TacticalAIHelpers::IsPlayerCitadel(pUnit->plot(), pUnit->getOwner()) && pUnit->getDomainType() == DOMAIN_LAND)
					continue;

				if (pUnit->plot()->IsFriendlyTerritory(pUnit->getOwner()) && !pUnit->plot()->IsAdjacentOwnedByEnemy(pUnit->getTeam()))
					continue;
			}

			m_CurrentMoveUnits.push_back(CvTacticalUnit(pUnit->GetID()));
			//we will later sort by "attack strength" so fake it
			//ranged/slow units should retreat first, ie have a high strength
			int iFakeStrength = (pUnit->IsCanAttackRanged() ? 30 : 20) - pUnit->baseMoves(false);
			m_CurrentMoveUnits.back().SetAttackStrength(iFakeStrength);
			m_CurrentMoveUnits.back().SetHealthPercent(1, 1);
		}
	}

	if(m_CurrentMoveUnits.size() > 0)
	{
		//melee units should retreat last
		std::stable_sort(m_CurrentMoveUnits.begin(), m_CurrentMoveUnits.end());
		ExecuteWithdrawMoves();
	}
}

/// Close units in on primary target of this dominance zone
void CvTacticalAI::PlotReinforcementMoves(CvTacticalDominanceZone* pTargetZone)
{
	ClearCurrentMoveUnits(AI_TACTICAL_REINFORCE);

	//sometimes there is nothing to do ...
	if (!pTargetZone || pTargetZone->GetPosture() == TACTICAL_POSTURE_WITHDRAW)
		return;

	//don't try to reinforce wilderness zones
	CvCity* pZoneCity = pTargetZone->GetZoneCity();
	if (!pZoneCity)
		return;
	
	//don't try to reinforce neutral zones if there are no enemies
	if (pZoneCity->getTeam() != m_pPlayer->getTeam() && pTargetZone->GetTotalEnemyUnitCount()==0)
		return;

	//sometimes we do not need further reinforcement - should we check whether we still need siege units specifically?
	bool bNeedMeleeOnly = false;
	bool bNeedSiegeOnly = false;
	if (pTargetZone->GetOverallDominanceFlag() == TACTICAL_DOMINANCE_FRIENDLY && pTargetZone->GetRangedDominanceFlag(100) == TACTICAL_DOMINANCE_FRIENDLY)
	{
		if (pTargetZone->GetFriendlyMeleeStrength() == 0) //get in melee units to capture a city!
			bNeedMeleeOnly = true;
		else if (CvStackingAI::Enabled(m_pPlayer->GetID()) && !pTargetZone->IsWater() && m_pPlayer->IsAtWarWith(pZoneCity->getOwner()))
		{
			int siege = 0, loop = 0;
			for (CvUnit* unit=m_pPlayer->firstUnit(&loop);unit;unit=m_pPlayer->nextUnit(&loop))
				if (!unit->isDelayedDeath() && !unit->isEmbarked() && unit->AI_getUnitAIType()==UNITAI_CITY_BOMBARD &&
					plotDistance(*unit->plot(),*pZoneCity->plot())<=TACTICAL_COMBAT_MAX_TARGET_DISTANCE) ++siege;
			bNeedSiegeOnly = siege<CvStacking::GetInt("AICityAssaultMinimumSiege",1);
			if (!bNeedSiegeOnly) return;
			CvStackingDiagnostics::Record(1,m_pPlayer->GetID(),"SIEGE_REINFORCE","city=%d siege=%d reason=missing_bombard_role",pZoneCity->GetID(),siege);
		}
		else return;
	}

	//sometimes it's pointless, too far out
	if (!pTargetZone->HasNeighborZone(m_pPlayer->GetID()) && pTargetZone->GetOverallDominanceFlag() == TACTICAL_DOMINANCE_ENEMY)
		return;

	// we want units which are somewhat close (so we don't deplete other combat zones) 
	// do not set a player - that way we can traverse unrevealed plots and foreign territory
	SPathFinderUserData data(NO_PLAYER, PT_ARMY_MIXED, NO_PLAYER, GetRecruitRange());
	CvPlot* pTargetPlot = pZoneCity->plot();

	ReachablePlots relevantPlots = GC.GetStepFinder().GetPlotsInReach(pTargetPlot, data);

	int iMoveUnitsAlreadyInZone = 0;
	for (ReachablePlots::const_iterator it = relevantPlots.begin(); it != relevantPlots.end(); ++it)
	{
		CvPlot* pPlot = GC.getMap().plotByIndexUnchecked( it->iPlotIndex );
		for (int i = 0; i < pPlot->getNumUnits(); i++)
		{
			CvUnit* pUnit = pPlot->getUnitByIndex(i);
			if (pUnit->getOwner()==m_pPlayer->GetID() && pUnit->canUseForTacticalAI())
			{
				if (CvStackingAI::Enabled(m_pPlayer->GetID()) && CvStackingAI::RetainCityUnit(pUnit)) continue;
				if (bNeedSiegeOnly && pUnit->AI_getUnitAIType()!=UNITAI_CITY_BOMBARD) continue;
				CvTacticalDominanceZone* pUnitZone = GetTacticalAnalysisMap()->GetZoneByPlot(pUnit->plot());
				if (pUnitZone && pUnitZone != pTargetZone)
				{
					//we should not pull units from zones which need them
					if (pUnitZone->GetOverallDominanceFlag() != TACTICAL_DOMINANCE_FRIENDLY && pUnitZone->GetPosture() != TACTICAL_POSTURE_WITHDRAW)
						if (!pPlot->isCity() || pPlot->getPlotCity()->isInDangerOfFalling() || pUnit->getDomainType() == DOMAIN_SEA)
							if (!pUnit->isEmbarked()) //cannot fight if embarked, so we can take it!
								continue;
				}

				// Skip ranged if we only need melee
				if (bNeedMeleeOnly && pUnit->IsCanAttackRanged())
					continue;

				// Carriers have special moves
				if (pUnit->AI_getUnitAIType() == UNITAI_CARRIER_SEA)
					continue;

				// Do not move siege units into enemy dominated zones ... wait until we have some cover!
				if (pUnit->AI_getUnitAIType() == UNITAI_CITY_BOMBARD && pTargetZone->GetOverallDominanceFlag() == TACTICAL_DOMINANCE_ENEMY)
					continue;

				//don't send generals / admirals across the map in an uncontrolled and potentially unescorted manner
				//it's enough if we recruit them for armies or combat sim
				if (pUnit->IsGreatGeneral() || pUnit->IsGreatAdmiral() || (pUnit->IsSapper() && pUnit->IsCivilianUnit()))
					continue;

				//conversely, don't leave generals out in the cold
				if (pUnit->IsCoveringFriendlyCivilian())
				{
					//a bit weird to just push a mission and not make an explicit plot/execute pair for this but should be ok
					pUnit->PushMission(CvTypes::getMISSION_SKIP());
					UnitProcessed(pUnit->GetID());
					continue;
				}

				// Proper domain of unit?
				// Note that coastal cities have two zones, so we will call this method twice
				if ((pTargetZone->IsWater() && pUnit->getDomainType() == DOMAIN_SEA) ||
					(!pTargetZone->IsWater() && pUnit->getDomainType() == DOMAIN_LAND))
				{
					// don't use near-dead units to attack ... misuse the flag here to be more careful when attacking
					if (pUnit->shouldHeal(pTargetZone->GetTerritoryType() == TACTICAL_TERRITORY_FRIENDLY))
						continue;

					//don't run away if there's other work to do (will eventually be handled by ExecuteAttackWithUnits)
					bool bHaveFarTarget = false;
					vector<pair<CvPlot*,bool>> altTargets = TacticalAIHelpers::GetTargetsInRange(pUnit, false, false);
					for (size_t j = 0; j < altTargets.size(); j++)
						bHaveFarTarget |= (plotDistance(*altTargets[j].first, *pTargetPlot) > TACTICAL_COMBAT_MAX_TARGET_DISTANCE);

					if (bHaveFarTarget)
						continue;

					CvTacticalUnit unit(pUnit->GetID());
					unit.SetMovesToTarget(it->iPathLength);
					m_CurrentMoveUnits.push_back(unit);

					if (m_pPlayer->GetTacticalAI()->GetTacticalAnalysisMap()->GetZoneByPlot(pUnit->plot()) == pTargetZone)
						iMoveUnitsAlreadyInZone++;
				}
			}
		}
	}

	//if we only have a single unit to work with in total, this is a case for pillage moves or the like
	if (pTargetZone->GetTotalFriendlyUnitCount() + m_CurrentMoveUnits.size() - iMoveUnitsAlreadyInZone < 2)
		return;

	if (m_CurrentMoveUnits.size() > 0)
	{
		vector<CvUnit*> vUnits;
		for (size_t i = 0; i < m_CurrentMoveUnits.size(); i++)
		{
			CvUnit* pUnit = m_pPlayer->getUnit( m_CurrentMoveUnits[i].GetID() );
			if (pUnit->canUseNow())
				vUnits.push_back(pUnit);
		}

		PositionUnitsAroundTarget(vUnits,pTargetPlot);
	}
}

/// Log that we couldn't find assignments for some units
void CvTacticalAI::ReviewUnassignedUnits()
{
	// Loop through all remaining units.
	// Do not call UnitProcessed() from here as it may invalidate our iterator
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(*it);
		if (pUnit && pUnit->canUseForTacticalAI())
		{
			//don't overwrite army moves ... everything else is fair game
			if (pUnit->getArmyID()==-1)
				pUnit->setTacticalMove(AI_TACTICAL_UNASSIGNED);

			//there shouldn't be any danger but just in case
			CvPlot* pSafePlot = pUnit->GetDanger() > pUnit->ActualHealRate(pUnit->plot()) ? TacticalAIHelpers::FindSafestPlotInReach(pUnit, true).first : NULL;
			if (pSafePlot)
			{
				pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pSafePlot->getX(), pSafePlot->getY());

				if (pUnit->CanUpgradeRightNow(false) && !pUnit->IsHurt())
				{
					// Don't upgrade if we will go over supply
					if (m_pPlayer->GetNumUnitsToSupply() < m_pPlayer->GetNumUnitsSupplied() || !pUnit->isNoSupply())
					{
						CvUnit* pNewUnit = pUnit->DoUpgrade();
						if (pNewUnit)
						{
							pNewUnit->SetTurnProcessed(true);
						}
					}
				}

				if (!pUnit->canMove())
					pUnit->SetTurnProcessed(true);
			}

			//do not skip the turn, finish moves, set the turn processed flag for units which we didn't move
			//homeland AI will take care of them!
		}
	}

	//fallback - if a city can bombard a unit but the corresponding target was suppressed, we do the attack here
	int iLoop;
	for (CvCity* pLoopCity = m_pPlayer->firstCity(&iLoop); pLoopCity != NULL; pLoopCity = m_pPlayer->nextCity(&iLoop))
	{
		CvUnit* pTarget = pLoopCity->getBestRangedStrikeTarget();
		if (pTarget)
			pLoopCity->doTask(TASK_RANGED_ATTACK, pTarget->getX(), pTarget->getY(), false);
	}
}

// OPERATIONAL AI SUPPORT FUNCTIONS

CvUnit* SwitchEscort(CvUnit* pCivilian, CvPlot* pNewEscortPlot, CvUnit* pEscort, CvArmyAI* pThisArmy)
{
	CvUnit* pPlotDefender = pNewEscortPlot->getBestDefender(pCivilian->getOwner());

	//Maybe we just make this guy our new escort, eh?
	if(pPlotDefender && pPlotDefender->getArmyID() == -1 && pPlotDefender->getDomainType() == pCivilian->getDomainType() && pPlotDefender->AI_getUnitAIType() != UNITAI_CITY_BOMBARD)
	{
		int iSlot = pThisArmy->RemoveUnit(pEscort->GetID(),true);
		if (iSlot>=0)
		{
			pThisArmy->AddUnit(pPlotDefender->GetID(), iSlot, pThisArmy->GetSlotInfo(iSlot).m_requiredSlot);
			if (GC.getLogging() && GC.getAILogging())
			{
				CvString strLogString;
				strLogString.Format("SingleHexOperationMoves: Switched escort to get things going.");
				GET_PLAYER(pCivilian->getOwner()).GetTacticalAI()->LogTacticalMessage(strLogString);
			}

			return pPlotDefender;
		}
		else
			CUSTOMLOG("SwitchEscort: Failed to remove unit from army!");
	}

	return NULL;
}

/// Move a single stack (civilian plus escort) to its destination
void CvTacticalAI::PlotArmyMovesEscort(CvArmyAI* pThisArmy)
{
	if (!pThisArmy)
		return;

	CvAIOperation* pOperation = GET_PLAYER(pThisArmy->GetOwner()).getAIOperation(pThisArmy->GetOperationID());
	if (!pOperation)
		return;

	//the unit to be escorted is always the first one
	CvUnit* pCivilian = pThisArmy->GetFirstUnit();
	//the second unit would be the first escort
	CvUnit* pEscort = pThisArmy->GetNextUnit(pCivilian);
	//additional escorts
	std::vector<CvUnit*> vExtraEscorts;
	CvUnit* pExtraEscort = pThisArmy->GetNextUnit(pEscort);
	while (pExtraEscort)
	{
		vExtraEscorts.push_back(pExtraEscort);
		pExtraEscort = pThisArmy->GetNextUnit(pExtraEscort); 
	}

	// No civilian? that's a problem
	if(!pCivilian || !pCivilian->IsCivilianUnit())
	{
		return;
	}

	// ESCORT AND CIVILIAN MEETING UP
	if(pThisArmy->GetArmyAIState() == ARMYAISTATE_WAITING_FOR_UNITS_TO_REINFORCE || 
		pThisArmy->GetArmyAIState() == ARMYAISTATE_WAITING_FOR_UNITS_TO_CATCH_UP)
	{
		// Check to make sure escort can get to civilian
		if(pOperation->GetMusterPlot() != NULL)
		{
			//check if the civilian is in danger
			if ( pCivilian->GetDanger() > 0 )
			{
				//try to move to safety
				CvPlot* pBetterPlot = TacticalAIHelpers::FindSafestPlotInReach(pCivilian,true).first;
				if (pBetterPlot)
				{
					ExecuteMoveToPlot(pCivilian,pBetterPlot);
					return;
				}
			}

			//civilian and escort have not yet met up
			if(pEscort)
			{
				//civilian is already there
				if(pCivilian->plot() == pOperation->GetMusterPlot())
				{
					//another military unit is blocking our escort ... find another muster plot
					if(pCivilian->plot()->GetNumCombatUnits() > 0)
					{
						CvUnit* pNewEscort = SwitchEscort(pCivilian,pCivilian->plot(),pEscort,pThisArmy);
						if (pNewEscort)
							pOperation->CheckTransitionToNextStage();
						else //did not switch
						{
							//Let's have them move forward, see if that clears things up.
							ExecuteMoveToPlot(pCivilian, pOperation->GetTargetPlot(),true,CvUnit::MOVEFLAG_APPROX_TARGET_RING1|CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER);
							ExecuteMoveToPlot(pEscort, pOperation->GetTargetPlot(),true,CvUnit::MOVEFLAG_APPROX_TARGET_RING1);

							//try again next turn
							pOperation->SetMusterPlot(pCivilian->plot());

							if(GC.getLogging() && GC.getAILogging())
							{
								CvString strLogString;
								strLogString.Format("SingleHexOperationMoves: Forced movement to get things going.");
								LogTacticalMessage(strLogString);
							}
						}
					}
					else
					{
						//move escort towards civilian
						if (ExecuteMoveToPlot(pEscort, pCivilian->plot())>0)
						{
							//d'oh. escort cannot reach us
							CvUnit* pNewEscort = SwitchEscort(pCivilian,pCivilian->plot(),pEscort,pThisArmy);

							if (pEscort==pNewEscort)
								pOperation->SetToAbort(AI_ABORT_LOST_PATH);

							return;	
						}

						UnitProcessed(pCivilian->GetID());
					}
				}
				else
				{
					//both must move
					CvPlot* pMuster = pOperation->GetMusterPlot();
					ExecuteMoveToPlot(pCivilian, pMuster);
					ExecuteMoveToPlot(pEscort, pOperation->GetMusterPlot(),true,pEscort->canMoveInto(*pMuster)?0:CvUnit::MOVEFLAG_APPROX_TARGET_RING1);
				}

				if(pOperation->GetOperationState()!=AI_OPERATION_STATE_ABORTED && GC.getLogging() && GC.getAILogging())
				{
					CvString strTemp;
					CvString strLogString;
					strTemp = GC.getUnitInfo(pEscort->getUnitType())->GetDescription();
					strLogString.Format("Moving escorting %s to civilian for operation, Civilian X: %d, Civilian Y: %d, X: %d, Y: %d", strTemp.GetCString(), pCivilian->plot()->getX(), pCivilian->plot()->getY(), pEscort->getX(), pEscort->getY());
					LogTacticalMessage(strLogString);
				}
			}
			else
			{
				//no escort
				if (pCivilian->plot() == pOperation->GetMusterPlot())
					pOperation->CheckTransitionToNextStage();
				else if (pCivilian->GetDanger(pOperation->GetMusterPlot())<INT_MAX)
					//continue moving. if this should fail, we just freeze and wait for better times
					ExecuteMoveToPlot(pCivilian,pOperation->GetMusterPlot());
			}
		}
	}

	// MOVING TO TARGET ... or really close
	if(pThisArmy->GetArmyAIState() == ARMYAISTATE_MOVING_TO_DESTINATION ||
		pThisArmy->GetArmyAIState() == ARMYAISTATE_AT_DESTINATION)
	{
		if (pOperation->CheckTransitionToNextStage() && pOperation->GetOperationState() == AI_OPERATION_STATE_SUCCESSFUL_FINISH)
			return;

		int iMoveFlags = CvUnit::MOVEFLAG_NO_ENEMY_TERRITORY;
		//if necessary and possible, avoid plots where our escort cannot follow
		if (pEscort)
		{
			if (!pOperation->GetTargetPlot()->isNeutralUnit(pEscort->getOwner(), true, true))
				iMoveFlags |= CvUnit::MOVEFLAG_DONT_STACK_WITH_NEUTRAL;
		}
		else
		{
			iMoveFlags |= CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER;
		}
	
		// the escort leads the way
		bool bPathFound = false;
		bool bContinueOperation = true;
		CvString strLogString;
		if(pEscort)
		{
			//the target plot may be a city, so we need to check if the escort can actually go there
			//but the civilian uses the same flags so dump the escort when we're already there
			CvPlot* pTargetPlot = pOperation->GetTargetPlot();
			if (!pEscort->canMoveInto(*pTargetPlot) && !pEscort->plot()->isAdjacent(pTargetPlot))
				iMoveFlags |= CvUnit::MOVEFLAG_APPROX_TARGET_RING1;

			bool bHavePathEscort = pEscort->GeneratePath(pOperation->GetTargetPlot(), iMoveFlags);
			if(bHavePathEscort)
			{
				CvPlot* pCommonPlot = pEscort->GetPathEndFirstTurnPlot();
				//need to check if civilian can enter because of unrevealed tiles in path
				if(pCommonPlot != NULL && pCivilian->canMoveInto(*pCommonPlot,CvUnit::MOVEFLAG_DESTINATION))
				{
					int iTurns = INT_MAX;
					bool bHavePathCivilian = pCivilian->GeneratePath(pCommonPlot, iMoveFlags, 5, &iTurns);
					if (bHavePathCivilian)
					{
						bPathFound = true;

						if (iTurns > 0)
							//escort seems to be faster than the civilian, slow down
							pCommonPlot = pCivilian->GetPathEndFirstTurnPlot();

						//we know they can stack
						ExecuteMoveToPlot(pEscort, pCommonPlot);
						ExecuteMoveToPlot(pCivilian, pCommonPlot);

						if (GC.getLogging() && GC.getAILogging())
						{
							strLogString.Format("%s now at (%d,%d). Moving towards (%d,%d) with escort %s. escort leading.",
								pCivilian->getName().c_str(), pCivilian->getX(), pCivilian->getY(),
								pOperation->GetTargetPlot()->getX(), pOperation->GetTargetPlot()->getY(), pEscort->getName().c_str());
						}
					}
				}
			}
			else
			{
				//civilian leads the way since escort seems to be blocked
				//but maybe we can at least find a way for this turn
				bool bHavePathCivilian = pCivilian->GeneratePath(pOperation->GetTargetPlot(), iMoveFlags);
				if(bHavePathCivilian)
				{
					CvPlot* pCommonPlot = pCivilian->GetPathEndFirstTurnPlot();
					if(pCommonPlot != NULL)
					{
						int iTurns = INT_MAX;
						if (!pEscort->canMoveInto(*pCommonPlot))
							iMoveFlags |= CvUnit::MOVEFLAG_APPROX_TARGET_RING1;

						bool bHavePathEscort = pEscort->GeneratePath(pCommonPlot, iMoveFlags, 5, &iTurns);
						if (bHavePathEscort)
						{
							bPathFound = true;

							if (iTurns > 0)
								//civilian seems to be faster than the escort, slow down
								pCommonPlot = pEscort->GetPathEndFirstTurnPlot();

							//we know they can stack
							ExecuteMoveToPlot(pEscort, pCommonPlot);
							ExecuteMoveToPlot(pCivilian, pCommonPlot);
						}
						else
						{
							//our escort can't move into the next path plot. maybe it's blocked by a friendly unit?
							CvUnit* pNewEscort = SwitchEscort(pCivilian,pCommonPlot,pEscort,pThisArmy);
							if (pNewEscort)
							{
								ExecuteMoveToPlot(pCivilian, pCommonPlot);
								pNewEscort->PushMission(CvTypes::getMISSION_SKIP());
								UnitProcessed(pNewEscort->GetID());
							}
						}
					}
				}
			}
			
			if(!bPathFound)
			{
				//we have a problem, apparently civilian and escort must split up
				//use a special flag here to make sure we're not stuck in a dead end with limited sight (can happen with embarked units)
				if (ExecuteMoveToPlot(pCivilian, pOperation->GetTargetPlot(), false, (iMoveFlags | CvUnit::MOVEFLAG_CONTINUE_TO_CLOSEST_PLOT))==INT_MAX)
				{
					pOperation->SetToAbort(AI_ABORT_LOST_PATH);
					strLogString.Format("%s stuck at (%d,%d), cannot find safe path to target. aborting.", 
						pCivilian->getName().c_str(), pCivilian->getX(), pCivilian->getY() );
					bContinueOperation = false;
				}
				//try to stay close
				else if (ExecuteMoveToPlot(pEscort, pCivilian->plot(), false)==INT_MAX)
				{
					MoveToEmptySpaceNearTarget(pEscort, pCivilian->plot(), pCivilian->plot()->getDomain(), 12);
					strLogString.Format("%s at (%d,%d) separated from escort %s at (%d,%d)",
						pCivilian->getName().c_str(), pCivilian->getX(), pCivilian->getY(),
						pEscort->getName().c_str(), pEscort->getX(), pEscort->getY());
				}
				else
				{
					strLogString.Format("%s at (%d,%d) had an issue moving to its target but it was resolved",
						pCivilian->getName().c_str(), pCivilian->getX(), pCivilian->getY());
				}
			}
		}
		else //no escort
		{
			bool bHavePathCivilian = pCivilian->GeneratePath(pOperation->GetTargetPlot(), iMoveFlags);
			if(bHavePathCivilian)
			{
				CvPlot* pTurnTarget = pCivilian->GetPathEndFirstTurnPlot();
				if(pTurnTarget != NULL)
				{
					if (pCivilian->GetDanger(pTurnTarget) == INT_MAX)
					{
						CvPlot* pAlternativeTarget = TacticalAIHelpers::FindSafestPlotInReach(pCivilian, true, true).first;
						if (pAlternativeTarget)
							pTurnTarget = pAlternativeTarget;
					}
					else
					{
						//maybe we can find ourselves an escort!
						CvUnit* pDefender = pTurnTarget->getBestDefender(m_pPlayer->GetID());
						if (pDefender && pDefender->getArmyID() == -1 && pDefender->getDomainType() == pCivilian->getDomainType())
						{
							pThisArmy->AddUnit(pDefender->GetID(), 1, pThisArmy->GetSlotInfo(1).m_requiredSlot);
							if (GC.getLogging() && GC.getAILogging())
							{
								CvString strLogString;
								strLogString.Format("SingleHexOperationMoves: Grabbed an escort along the way.");
							}
							pDefender->SetTurnProcessed(true);
						}
					}

					ExecuteMoveToPlot(pCivilian, pTurnTarget);
					if(GC.getLogging() && GC.getAILogging())
					{
						strLogString.Format("%s now at (%d,%d). Moving normally towards (%d,%d) without escort.",  pCivilian->getName().c_str(), pCivilian->getX(), pCivilian->getY(), pOperation->GetTargetPlot()->getX(), pOperation->GetTargetPlot()->getY() );
					}
				}
			}
			else
			{
				if (MoveToEmptySpaceNearTarget(pCivilian, pOperation->GetTargetPlot(), DOMAIN_LAND, INT_MAX, true))
				{
					if(GC.getLogging() && GC.getAILogging())
						strLogString.Format("%s now at (%d,%d). Moving to empty space near target (%d,%d) without escort.",  pCivilian->getName().c_str(), pCivilian->getX(), pCivilian->getY(), pOperation->GetTargetPlot()->getX(), pOperation->GetTargetPlot()->getY() );
				}
				else
				{
					pOperation->SetToAbort(AI_ABORT_LOST_PATH);
					if(GC.getLogging() && GC.getAILogging())
						strLogString.Format("%s at (%d,%d). Aborted operation. No path to target for civilian.",  pCivilian->getName().c_str(), pCivilian->getX(), pCivilian->getY() );
				}
			}
		}

		// now we're done, if the operation was cancelled, let the units be handled by Homeland AI
		if (bContinueOperation)
		{
			UnitProcessed(pCivilian->GetID());
			if (pEscort)
				UnitProcessed(pEscort->GetID());
		}

		// logging
		if(GC.getLogging() && GC.getAILogging())
		{
			LogTacticalMessage(strLogString);
		}
	}

	//move any additional escorts near the civilian
	for (size_t i=0; i<vExtraEscorts.size(); i++)
	{
		CvUnit* pUnit = vExtraEscorts[i];
		MoveToEmptySpaceNearTarget( pUnit, pCivilian->plot(), NO_DOMAIN, 23 );
		if(GC.getLogging() && GC.getAILogging())
		{
			CvString strTemp;
			CvString strLogString;
			strTemp = GC.getUnitInfo(pUnit->getUnitType())->GetDescription();
			strLogString.Format("Moving additional escorting %s to civilian for operation, Civilian X: %d, Civilian Y: %d, X: %d, Y: %d", strTemp.GetCString(), pCivilian->plot()->getX(), pCivilian->plot()->getY(), pUnit->getX(), pUnit->getY());
			LogTacticalMessage(strLogString);
		}
		UnitProcessed(pUnit->GetID());
	}
}

/// Move a large army to its destination against an enemy target
void CvTacticalAI::PlotArmyMovesCombat(CvArmyAI* pThisArmy)
{
	if (!pThisArmy)
		return;

	CvAIOperation* pOperation = GET_PLAYER(pThisArmy->GetOwner()).getAIOperation(pThisArmy->GetOperationID());
	if (!pOperation || pOperation->GetMusterPlot() == NULL)
		return;

	//where do we want to go
	CvPlot* pThisTurnTarget = pOperation->ComputeTargetPlotForThisTurn(pThisArmy);
	if (pThisTurnTarget == NULL)
	{
		pOperation->SetToAbort(AI_ABORT_LOST_PATH);
		return;
	}

    const bool contact=CheckForEnemiesNearArmy(pThisArmy);
    if(CvStackingOffensiveAI::MovingStalled(pOperation,pThisArmy,contact))
    { pOperation->SetToAbort(AI_ABORT_TIMED_OUT); return; }
    // Engaged units have already received tactical orders. Let an unexposed core keep advancing.
    if (contact && CvStackingOffensiveAI::HoldForContact(pOperation,pThisArmy,pThisTurnTarget))
	{
		//try to keep our units together, do not move on while there are enemies around, it's too dangerous
		pThisTurnTarget = pThisArmy->GetCenterOfMass(true);
		pOperation->LogOperationSpecialMessage("Contact with enemy!");
	}

	// RECRUITING
	if(pThisArmy->GetArmyAIState() == ARMYAISTATE_WAITING_FOR_UNITS_TO_REINFORCE || 
		pThisArmy->GetArmyAIState() == ARMYAISTATE_WAITING_FOR_UNITS_TO_CATCH_UP)
	{
		// This is where we try to gather. Don't use the center of mass here, it may drift anywhere 
		ExecuteGatherMoves(pThisArmy,pThisTurnTarget);
	}

	// MOVING TO TARGET
	else if(pThisArmy->GetArmyAIState() == ARMYAISTATE_MOVING_TO_DESTINATION)
	{
		//if this operation has a specific target player
		if (pOperation->GetEnemy() != NO_PLAYER)
		{
			//getting too close to another enemy?
			if (GC.getGame().GetClosestCityDistanceInPlots(pThisTurnTarget) < 3)
			{
				PlayerTypes eCityOwner = GC.getGame().GetClosestCityOwnerByPlots(pThisTurnTarget);
				if (eCityOwner != pOperation->GetEnemy() && m_pPlayer->IsAtWarWith(eCityOwner))
					pOperation->SetToAbort(AI_ABORT_TOO_DANGEROUS);
			}
		}

		//try to arrange the units somewhat closer to the target
		ExecuteGatherMoves(pThisArmy,pThisTurnTarget);
	}
}

//workaround to make units from disbanded armies accessible to tactical AI in the same turn
void CvTacticalAI::AddCurrentTurnUnit(CvUnit * pUnit)
{
	if (pUnit && pUnit->canMove())
		m_CurrentTurnUnits.push_back( pUnit->GetID() );
}

//make sure our units come in a defined order (important for reproducability, don't want to sort pointers!)
struct PrSortByUnitId
{
	bool operator()(const CvUnit* lhs, const CvUnit* rhs) const { return lhs->GetID() < rhs->GetID(); }
};

// Disabling preferences must not disable occupancy or combat prediction.
static bool StackPreferencesEnabled()
{
 return CvStacking::IsEnabled() && CvStacking::GetIntByKey(CvStacking::HOT_AIEnabled, 1) != 0;
}

static bool CanApproachInProtectedStack(const CvUnit* unit, const CvPlot* destination, int destinationDanger);

static int StackCollateralWeight()
{
 return StackPreferencesEnabled() ? CvStacking::GetIntByKey(CvStacking::HOT_AIStackCollateralWeight, 100) : 100;
}

static int StackCollateralValue(const CvUnit* attacker, const CvPlot* plot, const CvUnit* primary, int primaryHit, int garrisonHit = 0)
{
 if (!CvStacking::IsEnabled())
  return 0;
 vector<const CvUnit*> candidates;
 for (int i = 0; i < plot->getNumUnits(); ++i)
  candidates.push_back(plot->getUnitByIndex(i));
 const CvCity* city = plot->getPlotCity();
 const vector<pair<const CvUnit*, int> > collateral = CvUnitCombat::GetStackCollateralDamage(attacker, plot, primary, primaryHit,
  candidates, SUnitIDValueContainer(), city ? city->GetGarrisonedUnit() : NULL, garrisonHit);
 int value = 0;
 for (size_t i = 0; i < collateral.size(); ++i)
  value += collateral[i].second;
 return value * StackCollateralWeight() / 100;
}

/// Queues up attacks on enemy units on or adjacent to army's desired center
bool CvTacticalAI::CheckForEnemiesNearArmy(CvArmyAI* pArmy)
{
	if (!pArmy)
		return false;

	set<CvUnit*, PrSortByUnitId> ourUnitsInitial;
	CvUnit* pUnit = pArmy->GetFirstUnit();
	while (pUnit)
	{
		if (!pUnit->canUseNow() || pUnit->GetCurrHitPoints()<pUnit->GetMaxHitPoints() / 2)
		{
			pUnit = pArmy->GetNextUnit(pUnit);
			continue;
		}

		//can we attack somebody?
		vector<pair<CvPlot*, bool>> targets = TacticalAIHelpers::GetTargetsInRange(pUnit);
		//who can attack us?
		vector<CvUnit*> vEnemyAttackers = m_pPlayer->GetPossibleAttackers(*pUnit->plot(), m_pPlayer->getTeam());

		if (targets.empty() && vEnemyAttackers.empty() && !pUnit->IsCivilianUnit())
		{
			pUnit = pArmy->GetNextUnit(pUnit);
			continue;
		}

		//this unit can be attacked, remember it
		ourUnitsInitial.insert(pUnit);

		for (size_t i = 0; i < vEnemyAttackers.size(); i++)
		{
			//now here's the trick, also include our non-army units which happen to be around
			vector<CvUnit*> vOurAttackersAndAllies = GET_PLAYER(vEnemyAttackers[i]->getOwner()).GetPossibleAttackers(*vEnemyAttackers[i]->plot(), vEnemyAttackers[i]->getTeam());
			for (size_t j = 0; j < vOurAttackersAndAllies.size(); j++)
				if (vOurAttackersAndAllies[j]->getOwner()==m_pPlayer->GetID())
					ourUnitsInitial.insert(vOurAttackersAndAllies[j]);
		}

		pUnit = pArmy->GetNextUnit(pUnit);
	}

	if (ourUnitsInitial.empty())
		return false;

	//now that we have a set of units find the center of mass
	int x = 0;
	int y = 0;
	set<CvPlot*, PrSortByPlotIndex> allEnemyPlots;
	for (set<CvUnit*, PrSortByUnitId>::const_iterator it = ourUnitsInitial.begin(); it != ourUnitsInitial.end(); ++it)
	{
		x += (*it)->getX();
		y += (*it)->getY();

		vector<CvUnit*> vEnemyAttackers = m_pPlayer->GetPossibleAttackers(*(*it)->plot(), m_pPlayer->getTeam());
		for (size_t i = 0; i < vEnemyAttackers.size(); i++)
			allEnemyPlots.insert(vEnemyAttackers[i]->plot());
	}
	x = (x * 100) / ourUnitsInitial.size();
	y = (y * 100) / ourUnitsInitial.size();

	//now find the closest enemy plot to our center of mass
	CvPlot* pCoM = GC.getMap().plot((x + 50) / 100, (y + 50) / 100);
	CvPlot* pClosestEnemyPlot = NULL;
	int iMinDist = INT_MAX;
	for (set<CvPlot*, PrSortByPlotIndex>::const_iterator it = allEnemyPlots.begin(); it != allEnemyPlots.end(); ++it)
	{
		int iDist = plotDistance(*pCoM, *(*it));
		if (iDist < iMinDist)
		{
			pClosestEnemyPlot = *it;
			iMinDist = iDist;
		}
	}

	if (pClosestEnemyPlot == NULL)
		return false;

	//ignore units which are VERY far out; combat sim will ignore the "worst" units if necessary
	vector<CvUnit*> ourUnitsFinal;
	for (set<CvUnit*, PrSortByUnitId>::const_iterator it = ourUnitsInitial.begin(); it != ourUnitsInitial.end(); ++it)
	{
		if (plotDistance(*pCoM, *(*it)->plot()) < 7)
			ourUnitsFinal.push_back(*it);
	}

	if (GC.getLogging() && GC.getAILogging())
	{
		CvString strMsg;
		strMsg.Format("Performing opportunity attack with army %d and friends", pArmy->GetID());
		LogTacticalMessage(strMsg);
	}

	//we probably didn't see all enemy units, so doublecheck ... don't get drawn into the wrong fight
	CvCity* pClosestCity = GC.getGame().GetClosestCityByPlots(pClosestEnemyPlot, NO_PLAYER);
	CvTacticalDominanceZone* pZone = m_pPlayer->GetTacticalAI()->GetTacticalAnalysisMap()->GetZoneByCity(pClosestCity,pArmy->GetType()!=ARMY_TYPE_LAND);
	if (pZone && pZone->GetZoneCity() && pZone->GetTerritoryType()==TACTICAL_TERRITORY_ENEMY && pZone->GetOverallDominanceFlag() == TACTICAL_DOMINANCE_ENEMY)
		return false;

	return TacticalAIHelpers::FindAndExecuteBestUnitAssignments(m_pPlayer->GetID(), ourUnitsFinal, pClosestEnemyPlot, AL_MEDIUM);
}

void CvTacticalAI::ExecuteGatherMoves(CvArmyAI * pArmy, CvPlot * pTurnTarget)
{
	if (!pArmy || !pTurnTarget)
		return;

	vector<CvUnit*> vUnits;
	CvUnit* pUnit = pArmy->GetFirstUnit();
	while (pUnit)
	{
		if (pUnit->canUseNow()) //ignore units used during CheckForEnemiesNearArmy
			vUnits.push_back(pUnit);

		pUnit = pArmy->GetNextUnit(pUnit);
	}

	if (GC.getLogging() && GC.getAILogging())
	{
		CvString strMsg;
		strMsg.Format("Gathering army %d", pArmy->GetID());
		for (size_t i = 0; i < pArmy->GetNumFormationEntries(); i++)
		{
			CvArmyFormationSlot* slot = pArmy->GetSlotStatus(i);
			strMsg += CvString::format("; unit %d", slot->GetUnitID());
		}
		LogTacticalMessage(strMsg);
	}

	//we used to pass the army's target plot as a fallback target
	//but for sneak attacks the target plot may be unreachable
	//so we just go step by step
	PositionUnitsAroundTarget(vUnits, pTurnTarget);
}

// ROUTINES TO PROCESS AND SORT TARGETS

void CvTacticalAI::DumpTacticalTargets()
{
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT); pTarget!=NULL; pTarget = GetNextZoneTarget())
	{
		CvUnit* pUnit = pTarget->GetUnitPtr();
		CvString strMsg;
		strMsg.Format("Enemy %s, id %d at (%d,%d), score %d, damage %d", 
			pUnit->getName().c_str(), pUnit->GetID(), pTarget->GetTargetX(), pTarget->GetTargetY(),
			pTarget->GetAuxIntData(), pUnit->getDamage());
		LogTacticalMessage(strMsg);
	}
}

// adjust the score so that we can sort the targets
// keep in mind that the tactical combat sim will also take into account other enemies around the target
// and try to do as much damage as possible. so we only need a rough scoring here.
void CvTacticalAI::UpdateTargetScores()
{
	for(vector<CvTacticalTarget>::iterator it = m_AllTargets.begin(); it != m_AllTargets.end(); ++it)
	{
		CvPlot* pPlot = GC.getMap().plot(it->GetTargetX(), it->GetTargetY());
		if(it->GetTargetType() == AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT)
		{
			//try to attack target close to our units first
			vector<CvUnit*> myUnits = pPlot->GetAdjacentFriendlyCombatUnits(m_pPlayer->getTeam(), 3, pPlot->getDomain());
			it->SetAuxIntData(it->GetAuxIntData() + myUnits.size());

			//try to attack targets close to our cities first
			int iDist = m_pPlayer->GetCityDistanceInPlots(pPlot);
			if (iDist != INT_MAX)
			{
				int iDistScore = max(0, 5 - iDist);
				it->SetAuxIntData(it->GetAuxIntData() + iDistScore);
			}
		}
	}
}

void CvTacticalAI::SortTargetListAndDropUselessTargets()
{
	// Important: Sort all targets by aux data (if used for that target type)
	std::stable_sort(m_AllTargets.begin(), m_AllTargets.end());

	vector<CvTacticalTarget> reducedTargetList;

	//now in the sorted list we can suppress adjacent non-maximum targets
	int iSuppressionRange = 2;
	for (vector<CvTacticalTarget>::const_iterator it = m_AllTargets.begin(); it != m_AllTargets.end(); ++it)
	{
		bool bBetterTargetAdjacent = false;

		//do this only for enemy units in the same domain
		if (it->GetTargetType() == AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT )
		{
			for (vector<CvTacticalTarget>::const_iterator it2 = reducedTargetList.begin(); it2 != reducedTargetList.end(); ++it2)
			{
				//land zones have id > 0, water zones id < 0. opposite signs means domain mismatch
				//check signs without multiplication to avoid overflow with large zone IDs
				int iZone1 = it->GetDominanceZone();
				int iZone2 = it2->GetDominanceZone();
				if ((iZone1 > 0 && iZone2 < 0) || (iZone1 < 0 && iZone2 > 0))
					continue;

				//if close to one of our cities, make sure we're not dropping it
				CvPlot* pPlot = GC.getMap().plot(it->GetTargetX(), it->GetTargetY());
				if (m_pPlayer->GetCityDistanceInPlots(pPlot) < 4)
					continue;

				if (it2->GetTargetType() == AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT)
				{
					if (it2->GetAuxIntData() >= it->GetAuxIntData() && plotDistance(it2->GetTargetX(), it2->GetTargetY(), it->GetTargetX(), it->GetTargetY()) <= iSuppressionRange)
					{
						bBetterTargetAdjacent = true;
						break;
					}
				}
			}
		}

		if (!bBetterTargetAdjacent)
			reducedTargetList.push_back(*it);
	}

	m_AllTargets = reducedTargetList;
}

void CvTacticalAI::ClearCurrentMoveUnits(AITacticalMove eNewMove)
{
	m_CurrentAirSweepUnits.clear();
	m_CurrentMoveCities.clear();
	m_CurrentMoveUnits.clear();
	m_CurrentMoveUnits.setCurrentTacticalMove(eNewMove);
}

/// Sift through the target list and find just those that apply to the dominance zone we are currently looking at
int CvTacticalAI::ExtractTargetsForZone(CvTacticalDominanceZone* pZone /* Pass in NULL for all zones */)
{
	int iMaxRadius = GetTacticalAnalysisMap()->GetMaxZoneRadius();

	m_ZoneTargets.clear();
	for(vector<CvTacticalTarget>::iterator it = m_AllTargets.begin(); it != m_AllTargets.end(); ++it)
	{
		//domain check
		if (pZone)
		{
			DomainTypes eDomain = pZone->IsWater() ? DOMAIN_SEA : DOMAIN_LAND;
			if (!it->IsTargetValidInThisDomain(eDomain))
				continue;
		}

		//zone match
		if(pZone == NULL || it->GetDominanceZone() == pZone->GetZoneID())
		{
			m_ZoneTargets.push_back(&(*it));
			continue;
		}

		//zone boundaries are arbitrary sometimes so include neighboring tiles as well for smaller zones
		if (pZone && plotDistance(pZone->GetCenterX(), pZone->GetCenterY(), it->GetTargetX(), it->GetTargetY()) <= iMaxRadius)
		{
			m_ZoneTargets.push_back(&(*it));
		}
	}

	return (int)m_ZoneTargets.size();
}

/// Find the first target of a requested type in current dominance zone (call after ExtractTargetsForZone())
CvTacticalTarget* CvTacticalAI::GetFirstZoneTarget(AITacticalTargetType eType, eAggressionLevel threshold)
{
	m_eCurrentTargetType = eType;
	m_iCurrentTargetIndex = 0;

	while(m_iCurrentTargetIndex < (int)m_ZoneTargets.size())
	{
		//doesn't make sense to attack multiple times without raising the agg level
		if (m_ZoneTargets[m_iCurrentTargetIndex]->GetLastAggLevel() < threshold)
		{
			if (m_eCurrentTargetType == AI_TACTICAL_TARGET_NONE || m_ZoneTargets[m_iCurrentTargetIndex]->GetTargetType() == m_eCurrentTargetType)
			{
				return m_ZoneTargets[m_iCurrentTargetIndex];
			}
		}
		m_iCurrentTargetIndex++;
	}

	return NULL;
}

/// Find the next target of a requested type in current dominance zone (call after GetFirstZoneTarget())
CvTacticalTarget* CvTacticalAI::GetNextZoneTarget(eAggressionLevel threshold)
{
	m_iCurrentTargetIndex++;

	while(m_iCurrentTargetIndex < (int)m_ZoneTargets.size())
	{
		//doesn't make sense to attack multiple times without raising the agg level
		if (m_ZoneTargets[m_iCurrentTargetIndex]->GetLastAggLevel() < threshold)
		{
			if (m_eCurrentTargetType == AI_TACTICAL_TARGET_NONE || m_ZoneTargets[m_iCurrentTargetIndex]->GetTargetType() == m_eCurrentTargetType)
			{
				return m_ZoneTargets[m_iCurrentTargetIndex];
			}
		}
		m_iCurrentTargetIndex++;
	}

	return NULL;
}

// ROUTINES TO EXECUTE A MISSION

/// Capture the gold from a barbarian camp
void CvTacticalAI::ExecuteBarbarianCampMove(CvPlot* pTargetPlot)
{
	//ignore visibility here so the AI doesn't go naively after revealed but invisible camps
	//and then a unit is stuck there without being able to attack
	if (pTargetPlot->isEnemyUnit(m_pPlayer->GetID(), true, false))
	{
		int nGoodAttackers = 0;
		vector<CvUnit*> vUnits;
		for (size_t i = 0; i < m_CurrentMoveUnits.size(); i++)
		{
			CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[i].GetID());
			if (!pUnit)
				continue;

			//need at least one good attacker
			if (TacticalAIHelpers::IsAttackNetPositive(pUnit, pTargetPlot, 0))
				nGoodAttackers++;

			vUnits.push_back(pUnit);

			//don't use too many units
			if (nGoodAttackers > 2)
				break;
		}

		//just get into position, we will attack next turn when in place
		if (nGoodAttackers>1)
			PositionUnitsAroundTarget(vUnits, pTargetPlot);
	}
	else
	{
		for (size_t i = 0; i < m_CurrentMoveUnits.size(); i++)
		{
			CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[i].GetID());
			if (!pUnit)
				continue;

			//try to get into position
			//some of the camps the player has revealed may since have been cleared ... but we need to check
			//if the camp has been cleared there might be a neutral unit in the plot and our pathfinding could fail without the approximate flag!
			ExecuteMoveToPlot(pUnit, pTargetPlot, false, CvUnit::MOVEFLAG_APPROX_TARGET_RING1|CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER);

			if (pUnit->canMove())
			{
				//capture the camp if it still exists - if there is an enemy then we'll attack later
				if (pTargetPlot->GetNumCombatUnits()==0)
					ExecuteMoveToPlot(pUnit, pTargetPlot, false);

				//can use this unit for other moves, reset the tactmove to avoid spamming the log
				pUnit->setTacticalMove(AI_TACTICAL_MOVE_NONE);
			}
			else
				UnitProcessed(pUnit->GetID());

			if (pUnit->plot() == pTargetPlot)
				break;
		}
	}
}

/// Pillage an undefended improvement
bool CvTacticalAI::ExecutePillage(CvPlot* pTargetPlot)
{
	for (size_t i = 0; i < m_CurrentMoveUnits.size(); i++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[i].GetID());
		if (pUnit && pUnit->canMoveInto(*pTargetPlot, CvUnit::MOVEFLAG_DESTINATION))
		{
			if (pUnit->shouldPillage(pTargetPlot))
			{
				ExecuteMoveToPlot(pUnit, pTargetPlot, false, CvUnit::MOVEFLAG_ABORT_IF_NEW_ENEMY_REVEALED);

				//now that the neighbor plots are revealed, maybe it's better to retreat?
				CvPlot* pSafePlot = NULL;
				if (TacticalAIHelpers::GetOtherPlayerImprovementDamage(pUnit->plot(), m_pPlayer->GetID(), true) == 0)
				{
					if (!pUnit->shouldPillage(pUnit->plot()))
						pSafePlot = TacticalAIHelpers::FindSafestPlotInReach(pUnit, true).first;
				}

				if (pSafePlot)
				{
					//better go somewhere else
					pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pSafePlot->getX(), pSafePlot->getY());
					if (!pUnit->canMove())
						UnitProcessed(pUnit->GetID());
					//no use trying this target again
					return false;
				}
				else
				{
					//proceed
					pUnit->PushMission(CvTypes::getMISSION_PILLAGE());
					if (!pUnit->canMove())
						UnitProcessed(pUnit->GetID());
					//done
					return true;
				}
			}
		}
	}

	return false;
}

/// Pillage an undefended improvement
void CvTacticalAI::ExecutePlunderTradeUnit(CvPlot* pTargetPlot)
{
	// Move first one to target
	CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[0].GetID());
	if(pUnit)
	{
		if(pUnit->canMoveInto(*pTargetPlot, CvUnit::MOVEFLAG_DESTINATION ))
		{
			pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pTargetPlot->getX(), pTargetPlot->getY());
			if (pUnit->at(pTargetPlot->getX(), pTargetPlot->getY()))
			{
				pUnit->PushMission(CvTypes::getMISSION_PLUNDER_TRADE_ROUTE());
				//only end the turn if we can't move anymore
				if (!pUnit->canMove())
					UnitProcessed(pUnit->GetID());
			}
		}
		else if (MoveToEmptySpaceNearTarget(pUnit, pTargetPlot, NO_DOMAIN, 23))
		{
			TacticalAIHelpers::PerformRangedOpportunityAttack(pUnit);
			//don't run away
			UnitProcessed(pUnit->GetID());
		}

	}
}

/// Paradrop in to pillage an undefended improvement
void CvTacticalAI::ExecuteParadropPillage(CvPlot* pTargetPlot)
{
	// Move first one to target
	CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[0].GetID());
	if(pUnit)
	{
		pUnit->PushMission(CvTypes::getMISSION_PARADROP(), pTargetPlot->getX(), pTargetPlot->getY());
		pUnit->PushMission(CvTypes::getMISSION_PILLAGE());

		// Delete this unit from those we have to move
		if (!pUnit->canMove())
			UnitProcessed(pUnit->GetID());
	}
}

void CvTacticalAI::ExecuteAirAttack(CvPlot* pTargetPlot)
{
	if (!pTargetPlot)
		return;

	// Do air attacks, ignore all other units
	for(unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());

		if (pUnit && pUnit->getDomainType()==DOMAIN_AIR) //this includes planes and missiles. no nukes.
		{
			int iCount = 0; //failsafe
			while (pUnit->canMove() && pUnit->GetCurrHitPoints() > 30 && iCount < pUnit->getNumAttacks())
			{
				CvPlot* pBestTarget = FindAirTargetNearTarget(pUnit, pTargetPlot);
				if (pBestTarget != NULL)
				{
					//it's a ranged attack but it uses the move mission ... air units are strange
					pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pBestTarget->getX(), pBestTarget->getY());

					if (GC.getLogging() && GC.getAILogging())
					{
						CvString strMsg;
						strMsg.Format("%s ATTACK: %s %d attacks target X: %d, Y: %d", pUnit->isSuicide() ? "MISSILE":"AIR" , pUnit->getName().c_str(), pUnit->GetID(), pBestTarget->getX(), pBestTarget->getY());
						LogTacticalMessage(strMsg);
					}
				}
				iCount++;
			}

			if (pUnit->getNumAttacks() - pUnit->getNumAttacksMadeThisTurn() == 0)
				UnitProcessed(m_CurrentMoveUnits[iI].GetID());
		}
	}
}

/// Queues up attacks on enemy units on or adjacent to army's desired center
CvPlot* CvTacticalAI::FindAirTargetNearTarget(CvUnit* pUnit, CvPlot* pApproximateTargetPlot)
{
	int iRange = pUnit->GetRange();
	int iBestValue = -INT_MAX;
	CvPlot* pBestPlot = NULL;

	// Loop through all appropriate targets to see if any is of concern
	for (unsigned int iI = 0; iI < m_AllTargets.size(); iI++)
	{
		// Is the target of an appropriate type?
		if (m_AllTargets[iI].GetTargetType() == AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT ||
			m_AllTargets[iI].GetTargetType() == AI_TACTICAL_TARGET_ENEMY_CITY)
		{
			//make sure it is close to our actual target plot
			if (pApproximateTargetPlot)
			{
				int iTargetDistance = plotDistance(m_AllTargets[iI].GetTargetX(), m_AllTargets[iI].GetTargetY(), pApproximateTargetPlot->getX(), pApproximateTargetPlot->getY());
				if (iTargetDistance > 3)
					continue;
			}

			int iDistance = plotDistance(m_AllTargets[iI].GetTargetX(), m_AllTargets[iI].GetTargetY(), pUnit->getX(), pUnit->getY());
			if (iDistance <= iRange)
			{
				CvPlot* pTestPlot = GC.getMap().plot(m_AllTargets[iI].GetTargetX(), m_AllTargets[iI].GetTargetY());
				if (pTestPlot == NULL)
					continue;

				//don't beat a dead horse
				CvCity *pCity = pTestPlot->getPlotCity();
				if (pCity && pCity->getDamage() > pCity->GetMaxHitPoints() - 10 && CvStacking::GetCollateralTargetLimit(pUnit) == 0)
					continue;

				CvUnit* pDefender = pUnit->rangeStrikeTarget(*pTestPlot, true);
				if (!pDefender && !pCity)
					continue;

				int iValue = 0;
				int iUnusedReferenceVariable = 0;
				if (pUnit->AI_getUnitAIType() == UNITAI_MISSILE_AIR)
				{
					if (pDefender)
					{
						//ignore the city when attacking!
						iValue += pUnit->GetAirCombatDamage(pDefender, NULL, 0, iUnusedReferenceVariable, false);
						//bonus for a kill
						if (pDefender->GetCurrHitPoints() <= iValue)
							iValue += 21;
						//bonus for hitting units in cities, can only do that with missiles
						if (pDefender->plot()->isCity())
							iValue += 6;
					}
					else
					{
						// air missiles don't do damage to ungarrisoned cities
						continue;
					}
				}
    else
    {
     const CvUnit* garrison = pCity ? pCity->GetGarrisonedUnit() : NULL;
     int garrisonHit = 0;
     int hit = pUnit->GetAirCombatDamage(pCity ? NULL : pDefender, pCity,
      garrison ? garrison->GetMaxHitPoints() : 0, garrisonHit, false);
     int collateral = StackCollateralValue(pUnit, pTestPlot, pCity ? NULL : pDefender, hit, garrisonHit);
     int damageValue = hit;
     if (pCity)
     {
      damageValue = min(hit, max(0, pCity->GetMaxHitPoints() - pCity->getDamage() - 1));
      damageValue += garrison ? min(garrisonHit, garrison->GetCurrHitPoints()) : 0;
      if (pApproximateTargetPlot && !pApproximateTargetPlot->isCity())
       damageValue = garrison ? min(garrisonHit, garrison->GetCurrHitPoints()) : 0;
     }
     else
      damageValue = min(hit, pDefender->GetCurrHitPoints());
     int strikeChance = 100;
     int interceptionRisk = 0;
     const CvUnit* interceptor = pTestPlot->GetBestInterceptor(pUnit->getOwner(), pUnit, false, true);
     if (interceptor)
     {
      const int interceptionHit = interceptor->GetInterceptionDamage(pUnit, false, pTestPlot);
      if (interceptionHit > 0)
      {
       int chance = interceptor->interceptionProbability() * (100 - pUnit->evasionProbability()) / 100;
       strikeChance = 100 - min(100, max(0, chance));
       interceptionRisk = interceptionHit * (100 - strikeChance) / 100;
      }
     }
     const int retaliation = pCity ? pCity->GetAirStrikeDefenseDamage(pUnit, false) : pDefender->GetAirStrikeDefenseDamage(pUnit, false);
     iValue += (damageValue + collateral - retaliation) * strikeChance / 100 - interceptionRisk - iDistance * 3;
     if (interceptionRisk + retaliation * strikeChance / 100 >= pUnit->GetCurrHitPoints())
      continue;
    }

				if (iValue > iBestValue)
				{
					iBestValue = iValue;
					pBestPlot = pTestPlot;
				}
			}			
		}
	}

	return pBestPlot;
}

void CvTacticalAI::ExecuteAirSweep(CvPlot* pTargetPlot)
{
	//maybe there are no interceptors and we just had the fighter for air recon ...
	if (!pTargetPlot || pTargetPlot->GetInterceptorCount(m_pPlayer->GetID(), NULL, false, true) == 0)
		return;

	// Start by sending possible air sweeps
	for (unsigned int iI = 0; iI < m_CurrentAirSweepUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentAirSweepUnits[iI].GetID());

		if (pUnit && pUnit->canMove())
		{
			if (pUnit->canAirSweep())
			{
				pUnit->PushMission(CvTypes::getMISSION_AIR_SWEEP(), pTargetPlot->getX(), pTargetPlot->getY());
				if (pUnit->isOutOfAttacks())
					UnitProcessed(m_CurrentAirSweepUnits[iI].GetID());
			}

			if (GC.getLogging() && GC.getAILogging())
			{
				CvString strMsg;
				strMsg.Format("Starting air sweep with %s %d before attack on X: %d, Y: %d", pUnit->getName().c_str(), pUnit->GetID(), pTargetPlot->getX(), pTargetPlot->getY());
				LogTacticalMessage(strMsg);
			}
		}
	}
}

bool CvTacticalAI::ExecuteSpotterMove(const vector<CvUnit*>& vUnits, CvPlot* pTargetPlot)
{
	if (pTargetPlot->isVisible(m_pPlayer->getTeam()))
		return true; //nothing to do

	//else find a suitable unit
	vector<CvUnit*> vCandidates;
	for (size_t i = 0; i < vUnits.size(); i++)
	{
		CvUnit* pUnit = vUnits[i];

		// we want fast units or tanks
		// (unitai defense includes ranged units ... don't use it here)
		switch (pUnit->AI_getUnitAIType())
		{
		case UNITAI_FAST_ATTACK:
		case UNITAI_SKIRMISHER:
		case UNITAI_ATTACK_SEA:
		case UNITAI_SUBMARINE:
		case UNITAI_ATTACK:
		case UNITAI_COUNTER:
			vCandidates.push_back(pUnit);
			break;
		default:
			break; // Not a candidate.
		}
	}

	vector<OptionWithScore<pair<CvUnit*, CvPlot*>>> vOptions;

	for (size_t i = 0; i < vCandidates.size(); i++)
	{
		CvUnit* pUnit = vCandidates[i];
		int iFlags = CvUnit::MOVEFLAG_NO_EMBARK;

		//move into ring 2 unless we are already there and still can't see the target
		iFlags |= plotDistance(*pTargetPlot, *pUnit->plot()) > 2 ? CvUnit::MOVEFLAG_APPROX_TARGET_RING2 : CvUnit::MOVEFLAG_APPROX_TARGET_RING1;

		if (pUnit->GeneratePath(pTargetPlot, iFlags, 2))
		{
			//try to see if we have a plot we can reach this turn and see the target
			const CvPathNodeArray& path = pUnit->GetLastPath();
			for (size_t i = 0; i < path.size(); i++)
			{
				if (path[i].m_iMoves==0) //want some movement left to retreat if required
					break;

				CvPlot* pPathPlot = GC.getMap().plotUnchecked(path[i].m_iX, path[i].m_iY);
				if (pPathPlot->canSeePlot(pTargetPlot, pUnit->getTeam(), pUnit->visibilityRange(), NO_DIRECTION))
				{
					//or should we use danger as the sorting criterion?
					vOptions.push_back(OptionWithScore<pair<CvUnit*, CvPlot*>>(make_pair(pUnit,pPathPlot),path[i].m_iMoves));
				}
			}
		}
	}

	if (!vOptions.empty())
	{
		std::stable_sort(vOptions.begin(), vOptions.end());
		ExecuteMoveToPlot(vOptions.front().option.first, vOptions.front().option.second, false, CvUnit::MOVEFLAG_NO_EMBARK);
		return true;
	}

	//last resort. use an air sweep to an adjacent plot for recon
	CvPlot** aPlotsToCheck = GC.getMap().getNeighborsUnchecked(pTargetPlot);
	for (unsigned int iI = 0; iI < m_CurrentAirSweepUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentAirSweepUnits[iI].GetID());
		for (int iI = 0; iI < NUM_DIRECTION_TYPES; iI++)
		{
			CvPlot* pAdjacentPlot = aPlotsToCheck[iI];
			if (pAdjacentPlot != NULL && pAdjacentPlot->isVisible(m_pPlayer->getTeam()))
			{
				if (pUnit && pUnit->canAirSweepAt(pAdjacentPlot->getX(), pAdjacentPlot->getY()))
				{
					pUnit->PushMission(CvTypes::getMISSION_AIR_SWEEP(), pAdjacentPlot->getX(), pAdjacentPlot->getY());
					CUSTOMLOG("using air sweep for recon!")
					if (pUnit->isOutOfAttacks())
						UnitProcessed(m_CurrentAirSweepUnits[iI].GetID());
					return true;
				}
			}
		}
	}

	return false;
}

bool CvTacticalAI::ExecuteAttackWithCities(CvUnit* pDefender)
{
	// Start by applying damage from city bombards
	for (unsigned int iI = 0; iI < m_CurrentMoveCities.size(); iI++)
	{
		CvCity* pCity = m_pPlayer->getCity(m_CurrentMoveCities[iI].GetID());
		if (!pCity)
			continue;

		if (pCity->canRangeStrikeAt(pDefender->getX(), pDefender->getY()) && !pCity->isMadeAttack())
		{
			pCity->doTask(TASK_RANGED_ATTACK, pDefender->getX(), pDefender->getY(), false);
			if (pDefender->GetCurrHitPoints() < 1)
				return true;
		}
	}

	//not killed
	return false;
}

//evaluate many possible unit assignments around the target plot and choose the best one
//will not necessarily attack only the target plot when other targets are present!
bool CvTacticalAI::ExecuteAttackWithUnits(CvPlot* pTargetPlot, eAggressionLevel eAggLvl)
{
	vector<CvUnit*> vUnits;
	for (size_t i=0; i<m_CurrentMoveUnits.size(); i++)
		if (m_CurrentMoveUnits[i].GetAttackStrength()>=0) //sometimes we mark units as unnecessary
			vUnits.push_back( m_pPlayer->getUnit( m_CurrentMoveUnits[i].GetID() ) );

	//try to improve visibility
	if (!ExecuteSpotterMove(vUnits,pTargetPlot))
	{
		CvStackingDiagnostics::Record(1, m_pPlayer->GetID(), "ATTACK_GATE", "target=%d:%d reason=not_visible candidates=%u", pTargetPlot->getX(), pTargetPlot->getY(), (unsigned int)vUnits.size());
		return false;
	}

	//first handle air units (including missiles)
	ExecuteAirSweep(pTargetPlot);
	ExecuteAirAttack(pTargetPlot);

	//did the air attack already kill the enemy?
	if (pTargetPlot->getBestDefender(NO_PLAYER, m_pPlayer->GetID(), NULL, true, true) == NULL && !pTargetPlot->isCity())
		return true;

#if defined(MOD_CORE_DEBUGGING)
	if (MOD_CORE_DEBUGGING)
		LogTacticalMessage(CvString::format("trying attack on %d:%d, agg level %d", pTargetPlot->getX(), pTargetPlot->getY(), eAggLvl));
#endif

	return TacticalAIHelpers::FindAndExecuteBestUnitAssignments(m_pPlayer->GetID(), vUnits, pTargetPlot, eAggLvl);
}

// Each domain has its own roles, routes and readiness. A gathering army must
// not hold a ready fleet, or inherit readiness from whichever unit sorts first.
// A bombarding force advances with its escorts; melee city attacks still wait
// for readiness (CvStackingOffensiveAI::AllowCityAttack).
bool CvTacticalAI::StageGatheringCityAssault(vector<int>& unitIDs, CvPlot* pTarget)
{
	if(!pTarget || !pTarget->isCity() || !m_pPlayer->IsAtWarWith(pTarget->getOwner())) return false;
	std::map<int,bool> readiness;
	vector<int> active;
	bool gathering=false;
	for(size_t i=0;i<unitIDs.size();++i)
	{
		CvUnit* unit=m_pPlayer->getUnit(unitIDs[i]);
		if(!unit || unit->isDelayedDeath() || unit->getOwner()!=m_pPlayer->GetID()) continue;
		if(unit->IsCombatUnit() && unit->getDomainType()!=DOMAIN_AIR)
		{
			const int domain=unit->getDomainType();
			std::map<int,bool>::iterator ready=readiness.find(domain);
			if(ready==readiness.end())
			{
				const CvStackingOffensiveAI::AssaultPlan plan=CvStackingOffensiveAI::AssessAssault(
					m_pPlayer->GetID(),pTarget->getPlotCity(),unit->getDomainType());
				ready=readiness.insert(std::make_pair(domain,plan.ready||plan.bombard)).first;
			}
			if(!ready->second)
			{
				gathering=true;
				if(unit->canUseNow() && !CvStackingOffensiveAI::StageUnit(unit,pTarget))
				{
					unit=m_pPlayer->getUnit(unitIDs[i]);
					if(unit && !unit->isDelayedDeath() && unit->GetDanger()>0) ExecuteMovesToSafestPlot(unit);
				}
				// Failed safe staging does not authorize a generic ring-two
				// approach into the same city's defensive fire.
				continue;
			}
		}
		active.push_back(unitIDs[i]);
	}
	unitIDs.swap(active);
	return gathering;
}

//target can be friendly, neutral or hostile
bool CvTacticalAI::PositionUnitsAroundTarget(const vector<CvUnit*>& vInputUnits, CvPlot* pTarget)
{
	if(!pTarget) return false;
	vector<int> unitIDs;vector<CvUnit*> vUnits;
	for(size_t i=0;i<vInputUnits.size();++i)
		if(vInputUnits[i] && vInputUnits[i]->getOwner()==m_pPlayer->GetID())
		{ unitIDs.push_back(vInputUnits[i]->GetID());vUnits.push_back(vInputUnits[i]); }
	const bool gathering=StageGatheringCityAssault(unitIDs,pTarget);
	vUnits.clear();
	for(size_t i=0;i<unitIDs.size();++i)
	{ CvUnit* unit=m_pPlayer->getUnit(unitIDs[i]);if(unit && !unit->isDelayedDeath()) vUnits.push_back(unit); }
	if(vUnits.empty()) return gathering;
	//try to improve visibility. however, if the target is too far away this may fail ... in that case we chance it
	ExecuteSpotterMove(vUnits, pTarget);
	vUnits.clear();
	for(size_t i=0;i<unitIDs.size();++i)
	{ CvUnit* unit=m_pPlayer->getUnit(unitIDs[i]);if(unit && !unit->isDelayedDeath()) vUnits.push_back(unit); }

	if (MOD_CORE_DEBUGGING)
		LogTacticalMessage(CvString::format("seeking defensive positioning around %d:%d", pTarget->getX(), pTarget->getY()));

	//first round: in case there are enemies around, do a combat simulation
	vector<CvUnit*> vSimUnits = vUnits; //make a copy we can modify!
	bool bTactSimSuccess = TacticalAIHelpers::FindAndExecuteBestUnitAssignments(m_pPlayer->GetID(), vSimUnits, pTarget, AL_LOW);
	// The simulation executes combat and can destroy or upgrade participants.
	vUnits.clear();
	for(size_t i=0;i<unitIDs.size();++i)
	{ CvUnit* unit=m_pPlayer->getUnit(unitIDs[i]);if(unit && !unit->isDelayedDeath()) vUnits.push_back(unit); }

	//sometimes tactsim cannot use all units, eg if they are too far out
	vector<CvUnit*> farout;
	bool bHaveNavalEscort = false;
	for (vector<CvUnit*>::const_iterator it = vUnits.begin(); it != vUnits.end(); ++it)
	{
		CvUnit* pUnit = *it;

		//also include units we already moved ...
		if (pUnit->IsCombatUnit() && pUnit->getDomainType() == DOMAIN_SEA)
			bHaveNavalEscort = true;

		if (pUnit->TurnProcessed())
			continue;
		
		// This plot distance function call is valid since the update function was called in FindAndExecuteBestUnitAssignments
		if (bTactSimSuccess && TacticalAIHelpers::GetPlotDistanceToTarget(pUnit->plot()->GetPlotIndex(), pUnit->getDomainType()) <= TACTICAL_COMBAT_MAX_TARGET_DISTANCE)
			continue; //do not end the turn ... we may want to shuffle them around later

		farout.push_back(pUnit);
	}

	//we want to move the civilians last so they have a better chance of getting cover
	struct PrSortCombatFirst
	{
		bool operator()(const CvUnit* lhs, const CvUnit* rhs) const 
			{ return (lhs->IsCivilianUnit() ? 2 : lhs->AI_getUnitAIType()==UNITAI_CITY_BOMBARD ? 1 : 0) < (rhs->IsCivilianUnit() ? 2 : rhs->AI_getUnitAIType() == UNITAI_CITY_BOMBARD ? 1 : 0); }
	};
	std::stable_sort(farout.begin(), farout.end(), PrSortCombatFirst());
	vector<int> faroutIDs;
	for(size_t i=0;i<farout.size();++i) faroutIDs.push_back(farout[i]->GetID());

	//second round: move in as long as there is no danger and we're still far away
	for (vector<int>::const_iterator it = faroutIDs.begin(); it != faroutIDs.end(); ++it)
	{
		//lots of flags ...
		CvUnit* pUnit = m_pPlayer->getUnit(*it);
		if(!pUnit || pUnit->isDelayedDeath() || pUnit->TurnProcessed()) continue;
		int	iFlags = CvUnit::MOVEFLAG_NO_STOPNODES | CvUnit::MOVEFLAG_APPROX_TARGET_RING2;
		if (pUnit->isNativeDomain(pTarget)) //don't embark if we don't have to
			iFlags |= CvUnit::MOVEFLAG_APPROX_TARGET_NATIVE_DOMAIN;
		if (pUnit->IsCivilianUnit())
			iFlags |= (CvUnit::MOVEFLAG_DONT_STACK_WITH_NEUTRAL | CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER);
		if (!bHaveNavalEscort && pUnit->getDomainType()==DOMAIN_LAND)
			iFlags |= CvUnit::MOVEFLAG_NO_EMBARK;

		// Try to approach the target; approximate paths may already be in range.
		if (!pUnit->GeneratePath(pTarget, iFlags, GetRecruitRange()))
			continue;
		// An approximate path can succeed with no nodes when already in range.
		// Keep the checked endpoint stable across danger/protection queries.
		CvPlot* pApproachEndPlot = pUnit->GetPathEndFirstTurnPlot();
		if (!pApproachEndPlot)
			continue;

		//we are not here to fight or flee, let other moves take over
		int iDanger = pUnit->GetDanger(pApproachEndPlot);
		int iDangerLimit = (pUnit->IsCanAttack() && pUnit->AI_getUnitAIType()!=UNITAI_CITY_BOMBARD) ? pUnit->GetCurrHitPoints() / 2 : 0;
		//generals and siege should not even be in fog danger
		const bool bProtectedApproach = iDanger > iDangerLimit && pUnit->AI_getUnitAIType() == UNITAI_CITY_BOMBARD &&
			CanApproachInProtectedStack(pUnit, pApproachEndPlot, iDanger);
		if (pUnit->AI_getUnitAIType() == UNITAI_CITY_BOMBARD && iDanger > iDangerLimit)
			CvStackingDiagnostics::Record(1, pUnit->getOwner(), "SIEGE_APPROACH", "unit=%d from=%d destination=%d danger=%d limit=%d protectedAccepted=%d",
				pUnit->GetID(), pUnit->plot()->GetPlotIndex(), pApproachEndPlot->GetPlotIndex(), iDanger, iDangerLimit, bProtectedApproach ? 1 : 0);
		if (iDanger > iDangerLimit && !bProtectedApproach)
			continue;

		//embark only when it's safe
		CvTacticalDominanceZone* pZone = GetTacticalAnalysisMap()->GetZoneByPlot(pApproachEndPlot);
		if (pZone && pZone->GetOverallDominanceFlag() != TACTICAL_DOMINANCE_FRIENDLY && !pUnit->isEmbarked())
			iFlags |= CvUnit::MOVEFLAG_NO_EMBARK;

		ExecuteMoveToPlot(pUnit, pTarget, true, iFlags);
	}

	//third round: if the unit is in an army (no tactical moves) and did not move yet, move it to safety now
	for (vector<int>::const_iterator it = unitIDs.begin(); it != unitIDs.end(); ++it)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(*it);
		if(!pUnit || pUnit->isDelayedDeath()) continue;
		//don't move in further if we're already close
		if (pUnit->TurnProcessed() || pUnit->getArmyID() == -1)
			continue;

		//only flee if we're in danger, and not too far ideally
		if (pUnit->GetDanger() > pUnit->ActualHealRate(pUnit->plot()) || (!pUnit->IsCombatUnit() && pUnit->plot()->getNumDefenders(pUnit->getOwner()) == 0))
		{
			//units are not typically hurt but this is convenient function to move out of danger
			//MoveToSafestPlot() may cause units to run too far
			CvPlot* pPlot = TacticalAIHelpers::FindClosestSafePlotForHealing(pUnit, false).first;
			//second chance for emergencies
			if (!pPlot)
				pPlot = TacticalAIHelpers::FindSafestPlotInReach(pUnit, false, false).first;
			if (pPlot)
				pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pPlot->getX(), pPlot->getY(), 0, false, false, MISSIONAI_TACTMOVE);
		}

		pUnit=m_pPlayer->getUnit(*it);
		if(!pUnit || pUnit->isDelayedDeath()) continue;
		if (pUnit->canMove())
			pUnit->PushMission(CvTypes::getMISSION_SKIP());
		pUnit=m_pPlayer->getUnit(*it);
		if(pUnit && !pUnit->isDelayedDeath()) pUnit->SetTurnProcessed(true);
	}

	return bTactSimSuccess || gathering;
}

void CvTacticalAI::ExecuteLandingOperation(CvPlot* pTargetPlot)
{
	if (!pTargetPlot)
		return;

	struct SAssignment
	{
		SAssignment( CvUnit* unit, CvPlot* plot, int score, bool isAttack ) : pUnit(unit), pPlot(plot), iScore(score), bAttack(isAttack) {}
		CvUnit* pUnit;
		CvPlot* pPlot;
		int iScore;
		bool bAttack;
		bool operator<(const SAssignment& rhs) const { return iScore>rhs.iScore; }
	};

	struct PrPlotMatch
	{
		PrPlotMatch(CvPlot* refPlot) : pRefPlot(refPlot) {}
		CvPlot* pRefPlot;
		bool operator()(const SAssignment& other) { return pRefPlot==other.pPlot; } 
	};

	struct PrUnitMatch
	{
		PrUnitMatch(CvUnit* refUnit) : pRefUnit(refUnit) {}
		CvUnit* pRefUnit;
		bool operator()(const SAssignment& other) { return pRefUnit==other.pUnit; } 
	};

	vector<SAssignment> choices;
	for (size_t i=0; i<m_CurrentMoveUnits.size(); i++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[i].GetID());
		if (!pUnit)
			continue;

		//first check our immediate neighborhood (ie the tiles we can reach within one turn)
		ReachablePlots eligiblePlots = pUnit->GetAllPlotsInReachThisTurn(true, true, false);
		for (ReachablePlots::const_iterator tile=eligiblePlots.begin(); tile!=eligiblePlots.end(); ++tile)
		{
			CvPlot* pEvalPlot = GC.getMap().plotByIndexUnchecked(tile->iPlotIndex);
			ASSERT(pEvalPlot != NULL, "plotByIndexUnchecked returned null - invalid plot index");
			if (!pEvalPlot->isCoastalLand())
				continue;
			
			int iBonus = plotDistance(*pEvalPlot,*pTargetPlot) * (-10);
			if (pUnit->IsCanAttackRanged())
			{
				if (pEvalPlot->getArea()!=pTargetPlot->getArea() && plotDistance(*pEvalPlot,*pTargetPlot)>pUnit->GetRange())
					continue;

				if (pEvalPlot->isHills())
					iBonus += 20;
			}
			else
			{
				if (pEvalPlot->getArea()!=pTargetPlot->getArea())
					continue;
			}

			bool bAttack = pEvalPlot->isEnemyCity(*pUnit);
			CvUnit* pDefender = pEvalPlot->getBestDefender(NO_PLAYER);
			if (pDefender)
			{
				if ( m_pPlayer->IsAtWarWith(pDefender->getOwner()) )
					bAttack = true;
				else if (!CvStacking::IsEnabled() || !pUnit->canMoveInto(*pEvalPlot, CvUnit::MOVEFLAG_DESTINATION))
					continue; //neutral restrictions and full stacks still apply
			}

			if (bAttack && pUnit->IsCanAttackWithMove())
			{
				//check if attack makes sense
				if (TacticalAIHelpers::IsAttackNetPositive(pUnit,pEvalPlot,0))
				{
					choices.push_back( SAssignment(pUnit,pEvalPlot,pUnit->GetMaxHitPoints()+1,true) );
				}
			}
			else if (!bAttack)
			{
				//check danger
				int iScore = pUnit->GetMaxHitPoints() - pUnit->GetDanger(pEvalPlot) + iBonus;
				if (iScore>0)
					choices.push_back( SAssignment(pUnit,pEvalPlot,iScore,false) );
			}
		}
	}

	//prefer non-isolated plots
	for (vector<SAssignment>::iterator it=choices.begin(); it!=choices.end(); ++it)
	{
		for (vector<SAssignment>::iterator it2=choices.begin(); it2!=choices.end(); ++it2)
		{
			if (it2!=it && it2->pPlot->isAdjacent(it->pPlot))
				it2->iScore += 10;
		}

		if (it->pPlot->IsFriendlyUnitAdjacent(m_pPlayer->getTeam(),true))
			it->iScore += 10;
	}

	//ok let's go
	std::stable_sort(choices.begin(),choices.end());
	while (!choices.empty())
	{
		SAssignment next = choices.front();
		choices.erase(choices.begin());
		if (CvStacking::IsEnabled())
		{
			// Earlier landings may consume the last slot or reveal a new defender.
			// Keep alternate destinations for this unit when this candidate fails.
			int flags = CvUnit::MOVEFLAG_DESTINATION | (next.bAttack ? CvUnit::MOVEFLAG_ATTACK : 0);
			if (!next.pUnit->canMoveInto(*next.pPlot, flags) || (next.bAttack && !TacticalAIHelpers::IsAttackNetPositive(next.pUnit, next.pPlot, 0)))
				continue;
		}
		vector<SAssignment>::iterator last;
		if (!CvStacking::IsEnabled())
		{
			last = remove_if(choices.begin(), choices.end(), PrPlotMatch(next.pPlot)); choices.erase(last, choices.end());
		}
		last = remove_if(choices.begin(), choices.end(), PrUnitMatch(next.pUnit)); choices.erase(last, choices.end());
		next.pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), next.pPlot->getX(), next.pPlot->getY());
		if (!next.pUnit->canMove()) //not all units end their turn after disembark - they can still be used for other moves!
			UnitProcessed(next.pUnit->GetID());
	}

	//note that it's possible some units were not moved because of conflicts
}

/// Execute moving units to a better location
void CvTacticalAI::ExecuteRepositionMoves()
{
	//don't be too predictable
	int shuffledIndex[RING4_PLOTS - RING1_PLOTS];
	for (int i = RING1_PLOTS; i < RING4_PLOTS; i++)
		shuffledIndex[i-RING1_PLOTS] = i;

	int iNumPlots = RING4_PLOTS - RING1_PLOTS;
	for (int i = 0; i < iNumPlots - 1; i++)
	{
		int iSwapIndex = GC.getGame().randRangeExclusive(0, iNumPlots - i, CvSeeder(m_CurrentMoveUnits.size()).mix(i));
		std::swap<int>(shuffledIndex[i], shuffledIndex[iSwapIndex]);
	}

	for (unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
		if (!pUnit)
			continue;

		//any cities we can reinforce?
		CvPlot* pTarget = FindNearbyTarget(pUnit, 12, false);
		if (!pTarget)
			continue;

		//already close ...
		if (plotDistance(*pTarget, *pUnit->plot()) < 5 && TacticalAIHelpers::IsGoodPlotForStaging(m_pPlayer, pUnit->plot(), pUnit->getDomainType()))
		{
			pUnit->PushMission(CvTypes::getMISSION_SKIP());
			UnitProcessed(m_CurrentMoveUnits[iI].GetID());
			continue;
		}

		//find a good spot
		for (int i = 0; i<iNumPlots; i++)
		{
			CvPlot* pTestPlot = iterateRingPlots(pTarget, shuffledIndex[i]);
			if (!pTestPlot)
				continue;

			if (pUnit->IsCanAttackRanged())
				if (pTestPlot->IsAdjacentOwnedByTeamOtherThan(m_pPlayer->getTeam()))
					continue;

			//staging is not fighting ...
			if (pUnit->GetDanger(pTestPlot) > pUnit->GetCurrHitPoints()/5)
				continue;

			if (TacticalAIHelpers::IsGoodPlotForStaging(m_pPlayer, pTestPlot, pUnit->getDomainType()))
			{
				if(GC.getLogging() && GC.getAILogging() && m_pPlayer->isMajorCiv())
				{
					CvString strTemp = pUnit->getUnitInfo().GetDescription();
					CvString strLogString;
					strLogString.Format("%s moving to reinforce city at, X: %d, Y: %d, Current X: %d, Current Y: %d", 
						strTemp.GetCString(), pTestPlot->getX(), pTestPlot->getY(), pUnit->getX(), pUnit->getY());
					LogTacticalMessage(strLogString);
				}

				ExecuteMoveToPlot(pUnit, pTestPlot);
				UnitProcessed(m_CurrentMoveUnits[iI].GetID());
				break;
			}
		}
	}
}

/// Moves units to the hex with the lowest danger
void CvTacticalAI::ExecuteMovesToSafestPlot(CvUnit* pUnit)
{
	if (!pUnit)
		return;

	CvPlot* pUnitPlot = pUnit->plot();

	//so easy
	pair<CvPlot*, int> pBestPlotMove = TacticalAIHelpers::FindSafestPlotInReach(pUnit, true, true);
	if (pBestPlotMove.first)
	{
		//check if we need to bump somebody else
		CvUnit* pBumpUnit = pUnit->GetPotentialUnitToPushOut(*pBestPlotMove.first);
		if (pBumpUnit)
		{
			if (pUnit->PushBlockingUnitOutOfPlot(*pBestPlotMove.first))
			{
				UnitProcessed(pUnit->GetID());
				return;
			}
		}

		int iMovesRemaining = pBestPlotMove.second;

		//pillage before retreat, if we have movement points to spare
		if ((pUnit->hasFreePillageMove() || iMovesRemaining > GD_INT_GET(MOVE_DENOMINATOR)) && pUnit->shouldPillage(pUnitPlot))
		{
			pUnit->PushMission(CvTypes::getMISSION_PILLAGE());
			if (!pUnit->hasFreePillageMove())
				iMovesRemaining -= GD_INT_GET(MOVE_DENOMINATOR);
		}

		//typical citadel case
		if (pUnitPlot == pBestPlotMove.first)
		{
			if (pUnit->GetCurrHitPoints() > pUnit->GetMaxHitPoints() * 3 / 5)
				TacticalAIHelpers::PerformRangedOpportunityAttack(pUnit);

			//make sure the unit stays put!
			pUnit->PushMission(CvTypes::getMISSION_SKIP());
		}
		else
		{
			//try to do some damage if we have movement points to spare
			if ((iMovesRemaining > GD_INT_GET(MOVE_DENOMINATOR) || pUnit->IsFreeAttackMoves()) && pUnit->canRangeStrike() && pUnit->canMoveAfterAttacking())
				TacticalAIHelpers::PerformRangedOpportunityAttack(pUnit, false, iMovesRemaining);

			// Move to the lowest danger value found
			pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pBestPlotMove.first->getX(), pBestPlotMove.first->getY(), 0, false, false, MISSIONAI_TACTMOVE);

			//pillage after retreat, if we have movement points to spare
			if (pUnit->shouldPillage(pUnitPlot, false, true) && (pUnit->getMoves() > GD_INT_GET(MOVE_DENOMINATOR) || pUnit->IsFreeAttackMoves() || !pUnit->canRangeStrike()))
				pUnit->PushMission(CvTypes::getMISSION_PILLAGE());

			//see if we can do damage after retreating
			if (pUnit->canMove() && pUnit->canRangeStrike())
				TacticalAIHelpers::PerformRangedOpportunityAttack(pUnit);
		}

		UnitProcessed(pUnit->GetID());
	}
	else if (pUnit->GetDanger() < min(pUnit->GetCurrHitPoints() + pUnit->ActualHealRate(pUnitPlot), pUnit->GetMaxHitPoints()))
	{
		//do nothing and hope for the best
		pUnit->PushMission(CvTypes::getMISSION_SKIP());
		UnitProcessed(pUnit->GetID());
	}
	else //no good plot found
	{
		if(GC.getLogging() && GC.getAILogging())
		{
			CvString strLogString;
			CvString strTemp;
			strTemp = GC.getUnitInfo(pUnit->getUnitType())->GetDescription();
			strLogString.Format("Failed to find destination moving %s to safety from, X: %d, Y: %d", strTemp.GetCString(), pUnit->getX(), pUnit->getY());
			LogTacticalMessage(strLogString);
		}

		//try to go home
		if(pUnitPlot->getOwner() != pUnit->getOwner())
		{
			CvCity* pClosestCity = m_pPlayer->GetClosestCityByPathLength(pUnitPlot);
			if (m_pPlayer->isMinorCiv())
				pClosestCity = m_pPlayer->getCapitalCity();

			CvPlot* pMovePlot = pClosestCity ? pClosestCity->plot() : NULL;
			if(pMovePlot != NULL)
				MoveToEmptySpaceNearTarget(pUnit,pMovePlot,DOMAIN_LAND,42,true);
			else
				pUnit->PushMission(CvTypes::getMISSION_SKIP());

			UnitProcessed(pUnit->GetID());
		}
	}
}

/// Heal chosen units
void CvTacticalAI::ExecuteHeals(bool bFirstPass)
{
	for(unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
		if (!pUnit)
			continue;

		pair<CvPlot*, int> pBetterPlotMove = make_pair(static_cast<CvPlot*>(NULL), 0);

		//need to split from army?
		if (pUnit->getArmyID() != -1)
		{
			CvArmyAI* pArmy = m_pPlayer->getArmyAI(pUnit->getArmyID());
			if (pArmy)
			{
				//Don't do this for civilan operations!
				CvAIOperation* AIOperation = m_pPlayer->getAIOperation(pArmy->GetOperationID());
				if (AIOperation && AIOperation->IsCivilianOperation())
					continue;

				if (pArmy->GetArmyAIState() != ARMYAISTATE_WAITING_FOR_UNITS_TO_REINFORCE)
					pArmy->RemoveUnit(pUnit->GetID(), false);
			}
		}

		//find a suitable spot for healing
		if (pUnit->getDomainType() == DOMAIN_LAND)
		{
			if (pUnit->GetDamageAoEFortified() > 0 && pUnit->canFortify(pUnit->plot()) &&
				pUnit->GetDanger() < pUnit->GetCurrHitPoints() + pUnit->ActualHealRate(pUnit->plot()) &&
				pUnit->plot()->GetNumEnemyUnitsAdjacent(pUnit->getTeam(), pUnit->getDomainType()) > 1)
			{
				//units with area damage if fortified should fortify as much as possible if near enemies
				pUnit->PushMission(CvTypes::getMISSION_FORTIFY());
				UnitProcessed(pUnit->GetID());
				continue;
			}

			//try opportunistic attacks if there is only one nearby unit
			if (pUnit->GetDanger() > 0 && !pUnit->isEmbarked())
			{
				std::vector<CvUnit*> vAttackers = m_pPlayer->GetPossibleAttackers(*pUnit->plot(),m_pPlayer->getTeam());
				if (vAttackers.size() == 1 && TacticalAIHelpers::KillLoneEnemyIfPossible(pUnit, vAttackers[0]))
				{
					if (GC.getLogging() && GC.getAILogging())
					{
						CvString strLogString;
						strLogString.Format("Healing unit %s (%d) counterattacked pursuer at X: %d, Y: %d",
							pUnit->getName().GetCString(), pUnit->GetID(), vAttackers[0]->getX(), vAttackers[0]->getY());
						LogTacticalMessage(strLogString);
					}
				}
			}

			pBetterPlotMove = TacticalAIHelpers::FindClosestSafePlotForHealing(pUnit);
		}
		else if (pUnit->getDomainType()==DOMAIN_SEA)
		{
			if (pUnit->GetDanger()>0 || pUnit->ActualHealRate(pUnit->plot()) == 0)
			{
				std::vector<CvUnit*> vAttackers = m_pPlayer->GetPossibleAttackers(*pUnit->plot(),m_pPlayer->getTeam());
				//try to turn the tables on him
				if (vAttackers.size() == 1 && TacticalAIHelpers::KillLoneEnemyIfPossible(pUnit, vAttackers[0]))
				{
					if (GC.getLogging() && GC.getAILogging())
					{
						CvString strLogString;
						strLogString.Format("Healing unit %s (%d) counterattacked pursuer at X: %d, Y: %d",
							pUnit->getName().GetCString(), pUnit->GetID(), vAttackers[0]->getX(), vAttackers[0]->getY());
						LogTacticalMessage(strLogString);
					}
				}
				else
				{
					//why not pillage some tiles?
					if (pUnit->shouldPillage(pUnit->plot()))
					{
						pUnit->PushMission(CvTypes::getMISSION_PILLAGE());
						if (GC.getLogging() && GC.getAILogging())
						{
							CvString strMsg;
							strMsg.Format("Heal: pillage with %s before move, X: %d, Y: %d", pUnit->getName().GetCString(), pUnit->getX(), pUnit->getY());
							LogTacticalMessage(strMsg);
						}
					}
				}

				pBetterPlotMove = TacticalAIHelpers::FindClosestSafePlotForHealing(pUnit);
			}
		}

		//now finally do something
		if (pBetterPlotMove.first)
		{
			if (pBetterPlotMove.first != pUnit->plot())
			{
				//ranged attack before fleeing for fast units
				if (pUnit->canMoveAfterAttacking() && (pBetterPlotMove.second > GD_INT_GET(MOVE_DENOMINATOR) || pUnit->IsFreeAttackMoves()) && pUnit->canRangeStrike())
					TacticalAIHelpers::PerformRangedOpportunityAttack(pUnit, false, pBetterPlotMove.second);

				CvUnit* pPushUnit = pUnit->GetPotentialUnitToPushOut(*pBetterPlotMove.first);
				if (pPushUnit)
					pUnit->PushBlockingUnitOutOfPlot(*pBetterPlotMove.first);
				else //plot should be free
					ExecuteMoveToPlot(pUnit, pBetterPlotMove.first);
			}
			else
				//this is required to flush the previous mission!
				pUnit->PushMission(CvTypes::getMISSION_SKIP());

			UnitProcessed(pUnit->GetID());
		}
		//no safe plot to heal ...
		else if (!bFirstPass && pUnit->getDomainType() != DOMAIN_AIR && pUnit->GetDanger() > /*10*/ GD_INT_GET(NEUTRAL_HEAL_RATE))
		{
			//why not pillage more tiles?
			if (pUnit->shouldPillage(pUnit->plot()))
			{
				pUnit->PushMission(CvTypes::getMISSION_PILLAGE());
			
				if (GC.getLogging() && GC.getAILogging())
				{
					CvString strMsg;
					strMsg.Format("Heal: pillage with %s after move, X: %d, Y: %d", pUnit->getName().GetCString(), pUnit->getX(), pUnit->getY());
					LogTacticalMessage(strMsg);
				}
			}

			//at least try to flee if we're not needed
			if (!pUnit->IsCoveringFriendlyCivilian())
			{
				pBetterPlotMove = TacticalAIHelpers::FindSafestPlotInReach(pUnit, true);
				if (pBetterPlotMove.first && pBetterPlotMove.first != pUnit->plot())
					ExecuteMoveToPlot(pUnit, pBetterPlotMove.first);
			}

			if (!pUnit->canMove())
				UnitProcessed(pUnit->GetID());
		}
	}
}

/// Move barbarian to faraway targets 
void CvTacticalAI::ExecuteBarbarianRoaming()
{
	for(unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
		if(pUnit && pUnit->isBarbarian()) //combat and captured civilians both
		{
			// LAND MOVES
			if(pUnit->getDomainType() == DOMAIN_LAND)
			{
				CvPlot* pPlot = pUnit->plot();
				if(pPlot && (pPlot->getImprovementType() == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT) || pPlot->isCity()))
				{
					pUnit->PushMission(CvTypes::getMISSION_SKIP());
					UnitProcessed(pUnit->GetID());
					//do it this way to avoid a warning
					pUnit->setTacticalMove(AI_TACTICAL_MOVE_NONE);
					pUnit->setTacticalMove(AI_TACTICAL_BARBARIAN_CAMP);
					continue;
				}

				//where to?
				CvPlot* pBestPlot = FindBestBarbarianLandTarget(pUnit);
				if(!pBestPlot)
					continue;
					
				//civilian to capture?
				bool bTargetIsCombat = pBestPlot->isEnemyUnit(BARBARIAN_PLAYER, true, true);
				bool bTargetIsCivilian = pBestPlot->isEnemyUnit(BARBARIAN_PLAYER, false, true);
				bool bTargetIsImprovement = pBestPlot->getImprovementType() != NO_IMPROVEMENT && !pBestPlot->IsImprovementPillaged();

				//just move in if we can
				if ((bTargetIsCivilian || bTargetIsImprovement) && !bTargetIsCombat)
				{
					pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pBestPlot->getX(), pBestPlot->getY());
					if (pUnit->canMove() && pUnit->at(pBestPlot->getX(), pBestPlot->getY()))
						pUnit->PushMission(CvTypes::getMISSION_PILLAGE());
				}
				//move towards the target but don't hang around there
				//in fact, since we apparently did not attack this turn, we should continue roaming
				else if (bTargetIsCombat && plotDistance(*pBestPlot, *pUnit->plot()) > 1)
				{
					MoveToEmptySpaceNearTarget(pUnit, pBestPlot, DOMAIN_LAND, 12);
				}

				//hit and run, if you can
				if (!pUnit->canMove())
					UnitProcessed(m_CurrentMoveUnits[iI].GetID());
			}
			// NAVAL MOVES
			else
			{
				CvPlot* pBestPlot = FindBestBarbarianSeaTarget(pUnit);
				if(!pBestPlot)
					continue;

				//no naval pillaging, it's just too annoying
				//same logic as above, if we're already at the target we don't end the turn but move to safety
				bool bTargetIsCombat = pBestPlot->isEnemyUnit(BARBARIAN_PLAYER, true, true);
				if (!bTargetIsCombat || plotDistance(*pBestPlot, *pUnit->plot()) > 1)
				{
					if (MoveToEmptySpaceNearTarget(pUnit, pBestPlot, DOMAIN_SEA, 12))
					{
						TacticalAIHelpers::PerformOpportunityAttack(pUnit, true);
						UnitProcessed(m_CurrentMoveUnits[iI].GetID());
					}
				}
			}
		}
	}
}

/// Move unit to a specific tile, return turns remaining
int CvTacticalAI::ExecuteMoveToPlot(CvUnit* pUnit, CvPlot* pTarget, bool bSetProcessed, int iFlags)
{
	int iResult = INT_MAX; //impossible

	if(!pUnit || !pTarget)
		return iResult;
	const int unitID=pUnit->GetID();
	CvPlayer& owner=GET_PLAYER(pUnit->getOwner());

	//for inspection in GUI
	pUnit->SetMissionAI(MISSIONAI_TACTMOVE, pTarget, NULL);

	// Unit already at target plot?
	if(pTarget == pUnit->plot() && pUnit->canEndTurnAtPlot(pTarget))
	{
		iResult = 0;

		TacticalAIHelpers::PerformRangedOpportunityAttack(pUnit);
		pUnit=owner.getUnit(unitID);
		if(!pUnit || pUnit->isDelayedDeath()) return iResult;
		pUnit->PushMission(CvTypes::getMISSION_SKIP());
	}
	else if (pUnit->canMoveInto(*pTarget, CvUnit::MOVEFLAG_DESTINATION|(iFlags&CvUnit::MOVEFLAG_ATTACK)) || (iFlags&CvUnit::MOVEFLAG_APPROX_TARGET_RING1) || (iFlags&CvUnit::MOVEFLAG_APPROX_TARGET_RING2))
	{
		int iTurns = INT_MAX;
		if (pUnit->GeneratePath(pTarget,iFlags,INT_MAX,&iTurns))
		{
			//pillage if it makes sense and we have movement points to spare
			if (!(iFlags&CvUnit::MOVEFLAG_ATTACK) && pUnit->shouldPillage(pUnit->plot(), true, true) && (pUnit->hasFreePillageMove() || pUnit->GetMovementPointsAtCachedTarget()>=GD_INT_GET(MOVE_DENOMINATOR)))
			{
				pUnit->PushMission(CvTypes::getMISSION_PILLAGE());
				pUnit=owner.getUnit(unitID);
				if(!pUnit || pUnit->isDelayedDeath()) return iResult;
				
				if (GC.getLogging() && GC.getAILogging())
				{
					CvString strMsg;
					strMsg.Format("Move To Plot: pillage with %s, X: %d, Y: %d", pUnit->getName().GetCString(), pUnit->getX(), pUnit->getY());
					LogTacticalMessage(strMsg);
				}
			}

			iResult = iTurns - 1;
			pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pTarget->getX(), pTarget->getY(), iFlags, false, false, MISSIONAI_TACTMOVE, pTarget);
			pUnit=owner.getUnit(unitID);
			if(!pUnit || pUnit->isDelayedDeath()) return iResult;

			bool bAlreadyThere = false;
			if (iFlags&CvUnit::MOVEFLAG_APPROX_TARGET_RING2)
				bAlreadyThere = (plotDistance(*pUnit->plot(),*pTarget)<3);
			else if  (iFlags&CvUnit::MOVEFLAG_APPROX_TARGET_RING1)
				bAlreadyThere = (plotDistance(*pUnit->plot(),*pTarget)<2);
			else
				bAlreadyThere = pUnit->at(pTarget->getX(), pTarget->getY());

			//typically because of MOVEFLAG_ABORT_IN_DANGER and newly revealed enemies ...
			if (bSetProcessed && !bAlreadyThere && pUnit->canMove() && pUnit->getArmyID()==-1)
			{
				//try to go to a better place if we're sure the unit will not be moved again this turn
				pTarget = TacticalAIHelpers::FindSafestPlotInReach(pUnit, true).first;
				if (pTarget)
				{
					pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pTarget->getX(), pTarget->getY(), 0 /*no approximate flags*/, false, false, MISSIONAI_TACTMOVE, pTarget);
					pUnit=owner.getUnit(unitID);
					if(!pUnit || pUnit->isDelayedDeath()) return iResult;
				}
			}
		}
		//maybe units are blocking our way? 
		else if (pUnit->GeneratePath(pTarget,iFlags|CvUnit::MOVEFLAG_IGNORE_STACKING_SELF,INT_MAX,&iTurns))
		{
			//already close? try to push the other unit out
			if (iTurns == 0)
			{
				CvUnit* pPushUnit = pUnit->GetPotentialUnitToPushOut(*pTarget);
				if (pPushUnit && pUnit->PushBlockingUnitOutOfPlot(*pTarget))
					iResult = 0;
				pUnit=owner.getUnit(unitID);
				if(!pUnit || pUnit->isDelayedDeath()) return iResult;
			}
			else
			{
				//try to find a good plot in the direction of the target and hope the block clears
				CvPlot* pWorkaround = pUnit->GetLastValidDestinationPlotInCachedPath();
				if (pWorkaround)
				{
					pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pTarget->getX(), pTarget->getY(), iFlags, false, false, MISSIONAI_TACTMOVE, pTarget);
					pUnit=owner.getUnit(unitID);
					if(!pUnit || pUnit->isDelayedDeath()) return iTurns-1;
					if (bSetProcessed || !pUnit->canMove())
						UnitProcessed(unitID);
					iResult = iTurns-1;
					pUnit=owner.getUnit(unitID);
					if(!pUnit || pUnit->isDelayedDeath()) return iResult;
				}
			}
		}

		if(iResult==0 && pUnit->canMove())
			TacticalAIHelpers::PerformRangedOpportunityAttack(pUnit);
	}

	if (bSetProcessed)
		UnitProcessed(unitID);

	return iResult;
}

/// Find an adjacent hex to move a blocking unit to
bool CvTacticalAI::ExecuteMoveOfBlockingUnit(CvUnit* pBlockingUnit, CvPlot* pPreferredDirection)
{
	if(!pBlockingUnit->canMove())
	{
		return false;
	}

	CvPlot* pOldPlot = pBlockingUnit->plot();

	std::vector<SPlotWithScore> vCandidates;

	for(int iI = 0; iI < NUM_DIRECTION_TYPES; iI++)
	{
		CvPlot* pPlot = plotDirection(pBlockingUnit->getX(), pBlockingUnit->getY(), ((DirectionTypes)iI));
		if(pPlot != NULL)
		{
			if (pPreferredDirection)
				vCandidates.push_back( SPlotWithScore(pPlot,plotDistance(pPreferredDirection->getX(),pPreferredDirection->getY(),pPlot->getX(),pPlot->getY())) );
			else
				vCandidates.push_back( SPlotWithScore(pPlot,0) );
		}
	}

	std::stable_sort(vCandidates.begin(),vCandidates.end());

	for (std::vector<SPlotWithScore>::const_iterator it=vCandidates.begin(); it!=vCandidates.end(); ++it)
	{
		CvPlot* pPlot = it->pPlot;

		// Don't embark for one of these moves
		if (!pOldPlot->isWater() && pPlot->isWater() && pBlockingUnit->getDomainType() == DOMAIN_LAND)
		{
			continue;
		}

		// Has to be somewhere we can move and be empty of other units/enemy cities
		if(!pPlot->getVisibleEnemyDefender(m_pPlayer->GetID()) && !pPlot->isEnemyCity(*pBlockingUnit) && pBlockingUnit->GeneratePath(pPlot))
		{
			ExecuteMoveToPlot(pBlockingUnit, pPlot);
			if(GC.getLogging() && GC.getAILogging())
			{
				CvString strTemp;
				CvString strLogString;
				strTemp = pBlockingUnit->getUnitInfo().GetDescription();
				strLogString.Format("Moving blocking %s out of way, Leaving X: %d, Y: %d, Now At X: %d, Y: %d", strTemp.GetCString(), pOldPlot->getX(), pOldPlot->getY(), pBlockingUnit->getX(), pBlockingUnit->getY());
				LogTacticalMessage(strLogString);
			}
			return true;
		}
	}
	return false;
}

/// Move unit to protect a specific tile
void CvTacticalAI::ExecuteNavalBlockadeMove(CvPlot* pTarget)
{
	if (!pTarget)
		return;

	for (unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
		if (pUnit && pUnit->canUseForTacticalAI())
		{
			//see if we can harrass the enemy first
			if (pUnit->shouldPillage(pUnit->plot()))
				pUnit->PushMission(CvTypes::getMISSION_PILLAGE());

			//safety check
			if (pUnit->GetDanger(pTarget) <= pUnit->GetCurrHitPoints())
			{
				//make sure we have a valid path
				if (!pUnit->GeneratePath(pTarget))
					continue;

				if (pUnit->GetDanger(pUnit->GetPathEndFirstTurnPlot()) <= pUnit->GetCurrHitPoints())
				{
					if (GC.getLogging() && GC.getAILogging())
					{
						CvString strMsg;
						strMsg.Format("Naval blockade at %d:%d with %s at %d:%d", pTarget->getX(), pTarget->getY(), pUnit->getName().GetCString(), pUnit->getX(), pUnit->getY());
						LogTacticalMessage(strMsg);
					}

					pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pTarget->getX(), pTarget->getY(), CvUnit::MOVEFLAG_APPROX_TARGET_RING1);

					//see if we can harrass the enemy now
					TacticalAIHelpers::PerformOpportunityAttack(pUnit, true);
					if (pUnit->shouldPillage(pUnit->plot(), false, true))
						pUnit->PushMission(CvTypes::getMISSION_PILLAGE());

					UnitProcessed(pUnit->GetID());

					//one is enough?
					break;
				}
			}
		}
	}
}

/// Set up fighters to intercept enemy air units
void CvTacticalAI::ExecuteAirPatrolMoves()
{
	for(unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
		if(pUnit)
		{
			if(pUnit->canAirPatrol(NULL))
			{
				if(GC.getLogging() && GC.getAILogging())
				{
					CvString strLogString;
					strLogString.Format("Starting air patrol at, X: %d, Y: %d with %s %d", pUnit->getX(), pUnit->getY(), pUnit->getName().c_str(), pUnit->GetID());
					LogTacticalMessage(strLogString);
				}

				pUnit->PushMission(CvTypes::getMISSION_AIRPATROL());
				UnitProcessed(m_CurrentMoveUnits[iI].GetID());
			}
		}
	}
}

/// Set up fighters to air sweep to suppress enemy air units/AA
void CvTacticalAI::ExecuteAirSweepMoves()
{
	for(unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
		if(pUnit)
		{
			if(pUnit->canAirSweep())
			{
				CvPlot *pTarget = m_pPlayer->GetMilitaryAI()->GetBestAirSweepTarget(pUnit);
				if (pTarget)
				{
					pUnit->PushMission(CvTypes::getMISSION_AIR_SWEEP(), pTarget->getX(), pTarget->getY());
					pUnit->finishMoves();
					UnitProcessed(m_CurrentMoveUnits[iI].GetID());
				}
			}
		}
	}
}

/// Bombard enemy units from plots they can't reach (return true if some attack made)
bool CvTacticalAI::ExecuteDestroyEnemyUnits(CvTacticalTarget& kTarget, eAggressionLevel aggLvl)
{
	//mark the target no matter if the attack succeeds
	kTarget.SetLastAggLevel(aggLvl);

	CvPlot* pTargetPlot = GC.getMap().plot(kTarget.GetTargetX(), kTarget.GetTargetY());
	//target may be invisible because we remember it from the previous turn ...
	CvUnit* pDefender = pTargetPlot->getBestDefender(NO_PLAYER, m_pPlayer->GetID(), NULL, true, true);
	if (pDefender && !pDefender->isDelayedDeath())
	{
		// Might be able to hit/kill with a city
		bool bCityCanAttack = FindCitiesWithinStrikingDistance(pTargetPlot);
		if (bCityCanAttack && ExecuteAttackWithCities(pDefender))
			return true;

		// Now the real deal
		if (FindUnitsWithinStrikingDistance(pTargetPlot) && ComputeTotalExpectedDamage(kTarget) > 0)
			return ExecuteAttackWithUnits(pTargetPlot, aggLvl);
	}

	return false;
}

/// Move units out of current dominance zone
void CvTacticalAI::ExecuteWithdrawMoves()
{
	for(unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
		if(!pUnit)
			continue;
		
		// Allow withdraw to neighboring tactical zone which seems safe
		CvTacticalDominanceZone* pZone = GetTacticalAnalysisMap()->GetZoneByPlot(pUnit->plot());
		if (!pZone)
			continue;

		//todo: if we withdraw one unit, make sure we withdraw any neighboring units as well .. don't want to leave anyone behind!
		int iBestScore = 0;
		CvPlot* pTargetPlot = NULL;
		for (std::vector<int>::const_iterator it = pZone->GetNeighboringZones().begin(); it != pZone->GetNeighboringZones().end(); ++it)
		{
			CvTacticalDominanceZone* pNextZone = GetTacticalAnalysisMap()->GetZoneByID(*it);
			if (pNextZone && pNextZone->GetZoneCity() && pNextZone->IsWater() == (pUnit->getDomainType() == DOMAIN_SEA))
			{
				CvPlot* pTestPlot = pNextZone->GetZoneCity()->plot();
				int iScore = pNextZone->getHospitalityScore();
				int iTurns = pUnit->TurnsToReachTarget(pTestPlot, CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER, 12);
				if (iTurns == INT_MAX)
					continue;

				iScore = (iScore * 100) / (iTurns + 1);
				if (iScore > iBestScore)
				{
					pTargetPlot = GC.getMap().plot(pNextZone->GetCenterX(), pNextZone->GetCenterY());
					iBestScore = iScore;
				}
			}
		}

		if (!pTargetPlot)
		{
			//Just go towards nearest city and try to avoid expensive distance map updates for minor players ...
			CvCity* pNearestCity = m_pPlayer->isMinorCiv() ? m_pPlayer->getCapitalCity() : m_pPlayer->GetClosestCityByPathLength(pUnit->plot());

			//Note this might for naval units since pathlength is cross-domain, might give impossible target!
			//But considering we have another fallback below this should be ok
			if (pNearestCity)
				pTargetPlot = pNearestCity->plot();
		}

		if (pTargetPlot && MoveToEmptySpaceNearTarget(pUnit, pTargetPlot, pUnit->getDomainType(), 12, true))
		{
			TacticalAIHelpers::PerformRangedOpportunityAttack(pUnit, false);
			UnitProcessed(m_CurrentMoveUnits[iI].GetID());

			if(GC.getLogging() && GC.getAILogging())
			{
				CvString strLogString;
				strLogString.Format("%s %d withdrew from (%d,%d) towards (%d,%d)", 
					pUnit->getName().GetCString(),pUnit->GetID(),pUnit->getX(),pUnit->getY(),pTargetPlot->getX(),pTargetPlot->getY());
				LogTacticalMessage(strLogString);
			}
		}
		else
		{
			if (pUnit->shouldPillage(pUnit->plot(), true))
				pUnit->PushMission(CvTypes::getMISSION_PILLAGE());

			//now move all units which didn't find a path to a city
			ExecuteMovesToSafestPlot(pUnit);
		}
	}

}

/// Move naval units on top of embarked units in danger
void CvTacticalAI::ExecuteEscortEmbarkedMoves(std::vector<CvUnit*> vTargets)
{
	for(unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pUnit = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());
		if(pUnit)
		{
			CvUnit* pBestTarget = NULL;
			int iHighestDanger = -1;
			int iBestMoveFlag = 0;

			// Loop through all my embarked units that are: alone and within range
			for (size_t i=0; i<vTargets.size(); ++i)
			{
				CvUnit* pTarget = vTargets[i];
				int iMoveFlag = pUnit->CanStackUnitAtPlot(pTarget->plot()) ? CvUnit::MOVEFLAG_IGNORE_DANGER : CvUnit::MOVEFLAG_APPROX_TARGET_RING1;
				
				// Can this unit get to the embarked unit in two moves?
				int iTurns = pUnit->TurnsToReachTarget(pTarget->plot(),iMoveFlag,1);
				if (iTurns <= 1)
				{
					//note: civilian in danger have INT_MAX
					int iDanger = pTarget->GetDanger();
					if (iDanger > iHighestDanger)
					{
						iHighestDanger = iDanger;
						pBestTarget = pTarget;
						iBestMoveFlag = iMoveFlag;
					}
				}
			}

			if (pBestTarget)
			{
				ExecuteMoveToPlot(pUnit, pBestTarget->plot(), true, iBestMoveFlag);

				//If we can shoot while doing this, do it!
				if (TacticalAIHelpers::PerformRangedOpportunityAttack(pUnit))
				{
					if(GC.getLogging() && GC.getAILogging())
					{
						CvString strLogString;
						strLogString.Format("%s escort opportunity range attack, Current X: %d, Current Y: %d", pUnit->getName().GetCString(), pUnit->getX(), pUnit->getY());
						LogTacticalMessage(strLogString);
					}
				}

				if(GC.getLogging() && GC.getAILogging())
				{
					CvString strLogString;
					strLogString.Format("%s escorted embarked unit at, Current X: %d, Current Y: %d", pUnit->getName().GetCString(), pUnit->getX(), pUnit->getY());
					LogTacticalMessage(strLogString);
				}
			}
		}
	}
}

// Get best plot of the array of possible plots, based on plot danger.
CvPlot* CvTacticalAI::GetBestRepositionPlot(CvUnit* pUnit, CvPlot* plotTarget, int iAcceptableDanger)
{
	//safety: barbarians don't leave camp
	if (pUnit->isBarbarian() && pUnit->plot()->getImprovementType() == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT))
		return NULL;

	//don't pull units out of cities for repositioning
	if (CvStackingAI::Enabled(pUnit->getOwner()) ? CvStackingAI::RetainCityUnit(pUnit) : (pUnit->IsGarrisoned() && pUnit->getDomainType() != DOMAIN_SEA && pUnit->plot()->getPlotCity()->NeedsGarrison()))
		return NULL;

	ReachablePlots reachablePlots = pUnit->GetAllPlotsInReachThisTurn(true, true, false);
	if (reachablePlots.empty())
		return NULL;

	CvCity* pTargetCity = plotTarget->getPlotCity();
	CvUnit* pTargetUnit = NULL;
	if (!pTargetCity)
		pTargetUnit = plotTarget->getBestDefender(NO_PLAYER, m_pPlayer->GetID());

	//done with the preparation, now start for real
	std::vector<SPlotWithTwoScoresL2> vStats;
	int iHighestAttack = 0;
	int iLowestDanger = INT_MAX;
	bool bIsRanged = pUnit->IsCanAttackRanged();

	for (ReachablePlots::iterator moveTile=reachablePlots.begin(); moveTile!=reachablePlots.end(); ++moveTile)
	{
		CvPlot* pMoveTile = GC.getMap().plotByIndexUnchecked(moveTile->iPlotIndex);

		//already occupied?
		if (!pUnit->canMoveInto(*pMoveTile,CvUnit::MOVEFLAG_DESTINATION ))
			continue;

		bool bBetterPass = false;
		if (bIsRanged)
		{
			//don't fly too close to the sun ...
			if ( pUnit->GetRange()>1 && plotDistance(*pMoveTile,*plotTarget)<2 )
				bBetterPass = true;
		}

		int iCurrentDanger = pUnit->GetDanger(pMoveTile);

		int iCurrentAttack = 0; //these methods take into account embarkation so we don't have to check for it
		if (bIsRanged && pUnit->canEverRangeStrikeAt(plotTarget->getX(),plotTarget->getY(),pMoveTile,false))
			iCurrentAttack = pUnit->GetMaxRangedCombatStrength(pTargetUnit, pTargetCity, true, pMoveTile, plotTarget);
		else if (!bIsRanged && (pUnit->GetNumEnemyUnitsAdjacent()>0 || pMoveTile->IsFriendlyUnitAdjacent(pUnit->getTeam(),true)) )
			iCurrentAttack = pUnit->GetMaxAttackStrength(pMoveTile, plotTarget, pTargetUnit);

		if (bBetterPass)
			iCurrentAttack /= 2;

		if (iCurrentDanger<=iAcceptableDanger && iCurrentAttack>0)
		{
			vStats.push_back( SPlotWithTwoScoresL2(pMoveTile,iCurrentAttack,iCurrentDanger) );

			iHighestAttack = max( iHighestAttack, iCurrentAttack );
			iLowestDanger = min( iLowestDanger, iCurrentDanger );
		}
	}

	//we want to find the best combination of attack potential and danger
	float fBestScore = 0;
	CvPlot* pBestRepositionPlot = NULL;
	for (std::vector<SPlotWithTwoScoresL2>::const_iterator it=vStats.begin(); it!=vStats.end(); ++it)
	{
		//be conservative: danger counts twice as much as attack strength
		float fScore = it->score1 / float(iHighestAttack) + 2 * float(iLowestDanger) / it->score2;

		if (fScore > fBestScore)
		{
			pBestRepositionPlot = it->pPlot;
			fBestScore = fScore;
		}
	}

	return pBestRepositionPlot;
}

//AMS: Fills m_CurrentAirSweepUnits with all units able to sweep at target plot.
void CvTacticalAI::FindAirUnitsToAirSweep(CvPlot* pTarget)
{
	// Always use one if available in case we need it for recon
	int interceptionsOnPlot = max(1, pTarget->GetInterceptorCount(m_pPlayer->GetID(), NULL, false, true));

	// Loop through all units available to tactical AI this turn
	m_CurrentAirSweepUnits.clear();
	for (list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end() && interceptionsOnPlot > 0; ++it)
	{
		CvUnit* pLoopUnit = m_pPlayer->getUnit(*it);
		if (pLoopUnit && pLoopUnit->canUseForTacticalAI())
		{
			// Is an air unit.
			if (pLoopUnit->getDomainType() == DOMAIN_AIR && pLoopUnit->canMove())
			{
				// Is able to sweep at target
				if (pLoopUnit->canAirSweepAt(pTarget->getX(), pTarget->getY()))
				{
					int iAttackStrength = pLoopUnit->GetMaxRangedCombatStrength(pTarget->GetBestInterceptor(pLoopUnit->getOwner(),pLoopUnit,false,true),NULL,true,NULL,pTarget);
					// Mod to air sweep strength
					iAttackStrength *= (100 + pLoopUnit->GetAirSweepCombatModifier());
					iAttackStrength /= 100;
					CvTacticalUnit unit(pLoopUnit->GetID());
					unit.SetAttackStrength(iAttackStrength);
					unit.SetHealthPercent(pLoopUnit->GetCurrHitPoints(), pLoopUnit->GetMaxHitPoints());
					m_CurrentAirSweepUnits.push_back(unit);

					interceptionsOnPlot--;
				}
			}
		}
	}

	std::stable_sort(m_CurrentAirSweepUnits.begin(), m_CurrentAirSweepUnits.end());
}

CvUnit* CvTacticalAI::FindUnitForThisMove(AITacticalMove eMove, CvPlot* pTarget, int iNumTurnsAway /* = -1 if any distance okay */)
{
	static UnitCombatTypes eReconType = (UnitCombatTypes)GC.getInfoTypeForString("UNITCOMBAT_RECON", true);

	m_CurrentMoveUnits.clear();
	std::vector<OptionWithScore<CvUnit*>> possibleUnits;

	// Loop through all units available to tactical AI this turn
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pLoopUnit = m_pPlayer->getUnit(*it);
		if(pLoopUnit && pLoopUnit->getDomainType() != DOMAIN_AIR && pLoopUnit->IsCombatUnit() && !pLoopUnit->TurnProcessed())
		{
			// Mod option: only recon units can claim ruins
			// Leaving this code here because A) this option can be turned off (is by default in Community Patch Only), and
			// B) even though most explorers aren't available to tactical AI, some secondary explorer units with the Reconnaissance promotion, like Conquistadors, can make use of it
			// Economic AI still places a high value on goody huts for AI explorers, so they'll still be prioritized; see EconomicAIHelpers::ScoreExplorePlot()
			if (MOD_BALANCE_RECON_ONLY_ANCIENT_RUINS && eMove == AI_TACTICAL_GOODY && pTarget->isRevealedGoody(m_pPlayer->getTeam()))
			{
				if (pLoopUnit->getUnitCombatType() != eReconType && !pLoopUnit->IsGainsXPFromScouting())
					continue;
			}

			//note that garrisons are not recruited into m_CurrentTurnUnits in the first place
			if(!pLoopUnit->canMove() || !pLoopUnit->IsCanAttack() || !pLoopUnit->canMoveInto(*pTarget,CvUnit::MOVEFLAG_DESTINATION))
				continue;

			if(pLoopUnit->AI_getUnitAIType() == UNITAI_EXPLORE || pLoopUnit->AI_getUnitAIType() == UNITAI_EXPLORE_SEA || pLoopUnit->getArmyID() != -1)
				continue;

			if (pLoopUnit->IsCoveringFriendlyCivilian())
				continue;

			// Share city retention with operation recruitment and avoid redundant garrison orders.
			if (CvStackingAI::Enabled(m_pPlayer->GetID()) &&
				(CvStackingAI::RetainCityUnit(pLoopUnit) ||
				(eMove==AI_TACTICAL_GARRISON && !CvStackingAI::UsefulGarrison(pLoopUnit,pTarget->getPlotCity()))))
				continue;

			//performance optimization ... careful because zero is a valid turn value
			if(iNumTurnsAway>1 && plotDistance(*pLoopUnit->plot(),*pTarget)>5*iNumTurnsAway)
				continue;

			int iExtraScore = 0;
			if(eMove == AI_TACTICAL_GARRISON)
			{
				// Do not pull units out of important citadels
				CvPlot* pUnitPlot = pLoopUnit->plot();
				if (TacticalAIHelpers::IsPlayerCitadel(pUnitPlot, m_pPlayer->GetID()) && pUnitPlot->IsBorderLand(m_pPlayer->GetID()) && pLoopUnit->getDomainType() == DOMAIN_LAND)
					continue;

				CvCity* pTargetCity = pTarget->getPlotCity();
				if (!pTargetCity)
					continue;

				// Want to put ranged units in cities to give them a ranged attack (but siege units should be used for offense)
				switch (pLoopUnit->AI_getUnitAIType())
				{
				case UNITAI_RANGED:
					if (pLoopUnit->GetRange() > 1)
						iExtraScore += 30 + pTargetCity->getGarrisonRangedAttackModifier();
					break;
				case UNITAI_DEFENSE_AIR:
				case UNITAI_DEFENSE:
					iExtraScore += 20;
					break;
				default:
					//nothing
					break;
				}

				// Don't use recon units as garrisons
				if (pLoopUnit->getUnitInfo().GetDefaultUnitAIType() == UNITAI_EXPLORE)
					iExtraScore -= 50;

				// Score candidate by effective city-strength contribution relative to city strength without garrison.
				int iCityStrengthNoGarrison = pTargetCity->getStrengthValue();

				CvUnit* pCurrentGarrison = pTargetCity->GetGarrisonedUnit();
				if (pCurrentGarrison)
					iCityStrengthNoGarrison -= (max(pCurrentGarrison->GetBaseCombatStrength(), pCurrentGarrison->GetBaseRangedCombatStrength()) * 10000) /
						max(1, pCurrentGarrison->getDomainType() == DOMAIN_LAND ? GD_INT_GET(CITY_STRENGTH_LAND_UNIT_DIVISOR) : GD_INT_GET(CITY_STRENGTH_NAVAL_UNIT_DIVISOR));

				iCityStrengthNoGarrison = max(1, iCityStrengthNoGarrison);

				const int iCandidateRawStrength = max(pLoopUnit->GetBaseCombatStrength(), pLoopUnit->GetBaseRangedCombatStrength());
				const int iCandidateDivisor = (pLoopUnit->getDomainType() == DOMAIN_LAND) ? GD_INT_GET(CITY_STRENGTH_LAND_UNIT_DIVISOR) : GD_INT_GET(CITY_STRENGTH_NAVAL_UNIT_DIVISOR);
				const int iCandidateContributionTimes100 = (iCandidateRawStrength * 10000) / max(1, iCandidateDivisor);

				iExtraScore += (120 * iCandidateContributionTimes100) / iCityStrengthNoGarrison;

				// Naval garrisons cannot attack, so they're much worse
				if (pLoopUnit->getDomainType() == DOMAIN_SEA && MOD_CORE_NO_NAVAL_RANGED_ATTACKS_FROM_CITIES && !pLoopUnit->isNativeDomain(pTarget))
					iExtraScore -= 50;

				// Don't put units with a defense boosted from promotions in cities, these boosts are ignored
				iExtraScore -= pLoopUnit->getDefenseModifier();
			}
			else if (eMove == AI_TACTICAL_GUARD)
			{
				// Heal first, guards might be attacked
				if (pLoopUnit->shouldHeal(false))
					continue;

				// Don't embark!
				if (pLoopUnit->getDomainType() != pTarget->getDomain())
					continue;

				// No siege units as plot defenders
				if (pLoopUnit->AI_getUnitAIType()==UNITAI_CITY_BOMBARD)
					continue;

				// Ranged units are ok only in citadels
				if (!TacticalAIHelpers::IsPlayerCitadel(pTarget, m_pPlayer->GetID()) && pLoopUnit->getDomainType() == DOMAIN_LAND)
				{
					if (pLoopUnit->IsCanAttackRanged())
						continue;
					if (pLoopUnit->getExtraVisibilityRange() > 0)
						iExtraScore += 23;
				}

				//these can do in a pinch
				if (pLoopUnit->noDefensiveBonus() || !pLoopUnit->canFortify(pTarget))
					iExtraScore -= 21;

				// Units with defensive promotions are especially valuable
				if(pLoopUnit->getDefenseModifier() > 0 || pLoopUnit->getExtraRangedDefenseModifier() > 0)
					iExtraScore += 31;
			}
			else if(eMove == AI_TACTICAL_GOODY)
			{
				// Fast movers are top priority
				if (pLoopUnit->getUnitInfo().GetUnitAIType(UNITAI_FAST_ATTACK) || pLoopUnit->getUnitInfo().GetUnitAIType(UNITAI_SKIRMISHER))
					iExtraScore += 31;
			}

			//otherwise collect and sort
			int iTurns = pLoopUnit->TurnsToReachTarget(pTarget, CvUnit::MOVEFLAG_SAFE_EMBARK_ONLY, (iNumTurnsAway == -1 ? MAX_INT : iNumTurnsAway));
			if(iTurns != MAX_INT)
			{
				//tricky to make a good score avoiding ties ...
				int iScore = 1000 + iExtraScore - 20 * iTurns - plotDistance(*pTarget,*pLoopUnit->plot());
				possibleUnits.push_back( OptionWithScore<CvUnit*>(pLoopUnit, iScore));
			}
		}
	}

	if (possibleUnits.empty())
		return NULL;
	else
	{
		std::stable_sort(possibleUnits.begin(), possibleUnits.end());
		CheckDebugTrigger(possibleUnits.front().option->GetID());
		return possibleUnits.front().option;
	}
}

/// Fills m_CurrentMoveUnits with all units within X turns of a target (returns TRUE if 1 or more found)
bool CvTacticalAI::FindUnitsWithinStrikingDistance(CvPlot* pTarget)
{
	m_CurrentMoveUnits.clear();

	bool rtnValue = false;
	bool bIsCityTarget = pTarget->isCity();
	bool bAirUnitsAdded = false;
	CvUnit* pDefender = pTarget->getBestDefender(NO_PLAYER, m_pPlayer->GetID(), NULL, false, true);

	//todo: check if defender can be damaged at all or if an attacker would die?
	// Loop through all units available to tactical AI this turn
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pLoopUnit = m_pPlayer->getUnit(*it);
		if(!pLoopUnit || !pLoopUnit->canUseForTacticalAI())
			continue;

		// Don't pull barbarian units out of camps to attack.
		if(pLoopUnit->isBarbarian() && (pLoopUnit->plot()->getImprovementType() == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT)))
			continue;

		// Some units can't enter cities
		if (pLoopUnit->isNoCapture() && bIsCityTarget)
			continue;

		// Don't bother with pathfinding if we're very far away
		if (plotDistance(*pLoopUnit->plot(), *pTarget) > pLoopUnit->baseMoves(false) * 4 && !pLoopUnit->getUnitInfo().IsCanChangePort())
			continue;

		//if it's a fighter plane, don't use it here, we need it for interceptions / sweeps
		if (pLoopUnit->getUnitInfo().GetDefaultUnitAIType() == UNITAI_DEFENSE_AIR)
			continue;

		if (pLoopUnit->IsCoveringFriendlyCivilian())
			continue;

		//note that garrisoned units are *not* recruited into m_CurrentTurnUnits!
		//also note that units in citadels are recruited, but the combat sim knows about their importance

		bool bCanReach = false;
		if ( pLoopUnit->IsCanAttackRanged() )
		{
			//can attack without moving ... for aircraft and other long-range units
			if (pLoopUnit->canRangeStrikeAt(pTarget->getX(), pTarget->getY()))
				bCanReach = true;
			else if (pLoopUnit->canMove() && pLoopUnit->getDomainType()!=DOMAIN_AIR)
			{
				//note that we also take units which can reach an attack plot but can only attack next turn. that's ok.
				ReachablePlots reachablePlots = TacticalAIHelpers::GetAllPlotsInReachThisTurn(pLoopUnit, pLoopUnit->plot(),
					CvUnit::MOVEFLAG_IGNORE_STACKING_SELF | CvUnit::MOVEFLAG_NO_EMBARK, 0);

				//start from the outside
				for (int i=pLoopUnit->GetRange(); i>0 && !bCanReach; i--)
				{
					std::vector<CvPlot*> vPlots = TacticalAIHelpers::GetPlotsForRangedAttack(pTarget,pLoopUnit,i,false);

					for (std::vector<CvPlot*>::const_iterator it=vPlots.begin(); it!=vPlots.end() && !bCanReach; ++it)
						bCanReach = (reachablePlots.find( (*it)->GetPlotIndex() ) != reachablePlots.end());
				}
			}
		}
		else if (pLoopUnit->IsCombatUnit()) //melee. enough if we can get adjacent to the target
		{
			int iFlags = CvUnit::MOVEFLAG_APPROX_TARGET_RING1 | CvUnit::MOVEFLAG_IGNORE_STACKING_SELF;
			bCanReach = (pLoopUnit->TurnsToReachTarget(pTarget, iFlags, 0) <= 0);
		}
		else //civilian unit, general or similar, needs to be able to support the attack
		{
			int iFlags = CvUnit::MOVEFLAG_APPROX_TARGET_RING2 | CvUnit::MOVEFLAG_IGNORE_DANGER;
			bCanReach = (pLoopUnit->TurnsToReachTarget(pTarget, iFlags, 0) <= 0);
		}

		//include units which are very close even if they cannot do anything right now
		//but the combat sim should have control over them to move them out of the way
		if (!bCanReach && plotDistance(*pLoopUnit->plot(),*pTarget)>2)
			continue;

		if(pLoopUnit->IsCanAttackRanged())
		{
			// Will we do a significant amount of damage
			int iTargetHitpoints = pDefender ? pDefender->GetCurrHitPoints() : 0;
			if(IsExpectedToDamageWithRangedAttack(pLoopUnit, pTarget, MIN(iTargetHitpoints/20, 3)))
			{
				//first-line ranged and air
				CvTacticalUnit unit(pLoopUnit->GetID());
				if (bIsCityTarget)
					unit.SetAttackStrength(pLoopUnit->GetMaxRangedCombatStrength(NULL, pTarget->getPlotCity(), true, NULL, NULL, true, true));
				else
					unit.SetAttackStrength(pLoopUnit->GetMaxRangedCombatStrength(pDefender, NULL, true, NULL, NULL, true, true));

				unit.SetHealthPercent(pLoopUnit->GetCurrHitPoints(), pLoopUnit->GetMaxHitPoints());
				m_CurrentMoveUnits.push_back(unit);
				rtnValue = true;

				if (pLoopUnit->getDomainType()==DOMAIN_AIR)
					bAirUnitsAdded = true;
			}
		}
		else if (pLoopUnit->IsCombatUnit())  //melee
		{
			int iAttackStrength = pLoopUnit->GetMaxAttackStrength(NULL, pTarget, bIsCityTarget ? NULL : pDefender, true, true);

			CvTacticalUnit unit(pLoopUnit->GetID());
			unit.SetAttackStrength(iAttackStrength);
			unit.SetHealthPercent(pLoopUnit->GetCurrHitPoints(), pLoopUnit->GetMaxHitPoints());
			m_CurrentMoveUnits.push_back(unit);
			rtnValue = true;
		}
		else //civilian
		{
			CvTacticalUnit unit(pLoopUnit->GetID());
			unit.SetAttackStrength(0);
			unit.SetHealthPercent(pLoopUnit->GetCurrHitPoints(), pLoopUnit->GetMaxHitPoints());
			m_CurrentMoveUnits.push_back(unit);
			rtnValue = true;
		}
	}

	// As we have air units on the attack targets we should also check possible air sweeps
	if (bAirUnitsAdded)
		FindAirUnitsToAirSweep(pTarget);
	else
		m_CurrentAirSweepUnits.clear();

	// Now sort them in the order we'd like them to attack
	std::stable_sort(m_CurrentMoveUnits.begin(), m_CurrentMoveUnits.end());

	return rtnValue;
}

/// Fills m_CurrentMoveCities with all cities within bombard range of a target (returns TRUE if 1 or more found)
bool CvTacticalAI::FindCitiesWithinStrikingDistance(CvPlot* pTargetPlot)
{
	m_CurrentMoveCities.clear();

	// Loop through all of our cities
	int iLoop;
	for(CvCity* pLoopCity = m_pPlayer->firstCity(&iLoop); pLoopCity != NULL; pLoopCity = m_pPlayer->nextCity(&iLoop))
	{
		int iAttackStrength = 0;
		if (pLoopCity->canRangeStrikeAt(pTargetPlot->getX(), pTargetPlot->getY()) && !pLoopCity->isMadeAttack())
			iAttackStrength += pLoopCity->getStrengthValue(true);

		if (iAttackStrength>0)
		{
			CvTacticalCity city;
			city.SetID(pLoopCity->GetID());
			city.SetExpectedTargetDamage(iAttackStrength);
			m_CurrentMoveCities.push_back(city);
		}
	}

	// Now sort them in the order we'd like them to attack
	std::stable_sort(m_CurrentMoveCities.begin(), m_CurrentMoveCities.end());
	return !m_CurrentMoveCities.empty();
}


bool CvTacticalAI::FindEmbarkedUnitsAroundTarget(CvPlot* pTarget, int iMaxDistance)
{
	m_CurrentMoveUnits.clear();

	if (!pTarget)
		return false;

	// Loop through all units available to tactical AI this turn
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pLoopUnit = m_pPlayer->getUnit(*it);
		if(pLoopUnit && pLoopUnit->canUseForTacticalAI() && pLoopUnit->IsCombatUnit() && pLoopUnit->isEmbarked() && plotDistance(*pLoopUnit->plot(),*pTarget)<=iMaxDistance )
		{
			CvTacticalUnit unit(pLoopUnit->GetID());
			unit.SetAttackStrength(pLoopUnit->GetBaseCombatStrength());
			unit.SetHealthPercent(pLoopUnit->GetCurrHitPoints(), pLoopUnit->GetMaxHitPoints());
			m_CurrentMoveUnits.push_back(unit);
		}
	}

	// Now sort them in the order we'd like them to attack
	std::stable_sort(m_CurrentMoveUnits.begin(), m_CurrentMoveUnits.end());

	return m_CurrentMoveUnits.size()>0;
}


/// Fills m_CurrentMoveUnits with all paratrooper units (available to jump) to the target (returns TRUE if 1 or more found)
bool CvTacticalAI::FindParatroopersWithinStrikingDistance(CvPlot* pTarget, bool bCheckDanger)
{
	m_CurrentMoveUnits.clear();

	// Loop through all units available to tactical AI this turn
	for(list<int>::const_iterator it = m_CurrentTurnUnits.begin(); it != m_CurrentTurnUnits.end(); it++)
	{
		CvUnit* pLoopUnit = m_pPlayer->getUnit(*it);
		if(pLoopUnit && pLoopUnit->canUseForTacticalAI() && 
			pLoopUnit->canParadropAt(pLoopUnit->plot(), pTarget->getX(), pTarget->getY()) &&
			(!bCheckDanger || pLoopUnit->GetDanger(pTarget) < pLoopUnit->GetCurrHitPoints()))
		{
			CvTacticalUnit unit(pLoopUnit->GetID());
			unit.SetAttackStrength(pLoopUnit->GetBaseCombatStrength());
			unit.SetHealthPercent(pLoopUnit->GetCurrHitPoints(), pLoopUnit->GetMaxHitPoints());
			m_CurrentMoveUnits.push_back(unit);
		}
	}

	// Now sort them in the order we'd like them to attack
	std::stable_sort(m_CurrentMoveUnits.begin(), m_CurrentMoveUnits.end());

	return m_CurrentMoveUnits.size()>0;
}

//find units for pillaging, plundering, blockading, etc
bool CvTacticalAI::FindUnitsForHarassing(CvPlot* pTarget, int iNumTurnsAway, int iMinHitpoints, int iMaxHitpoints, DomainTypes eDomain, bool bMustHaveMovesLeft, bool bAllowEmbarkation, int iMaxNumUnits, bool bPlunderTradeRoute)
{
	m_CurrentMoveUnits.clear();
	//need to convert turns to max path length here, zero turns away is also valid!
	SPathFinderUserData data(m_pPlayer->GetID(), PT_ARMY_MIXED, NO_PLAYER, (iNumTurnsAway+1)*(eDomain==DOMAIN_LAND ? 3 : 5));
	ReachablePlots relevantPlots = GC.GetStepFinder().GetPlotsInReach(pTarget, data);

	//plots are ordered by turns to reach!
	for (ReachablePlots::const_iterator it = relevantPlots.begin(); it != relevantPlots.end(); ++it)
	{
		if (m_CurrentMoveUnits.size() >= (size_t)max(1, iMaxNumUnits))
			break;
		CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);
		const int candidates = CvStacking::IsEnabled() ? pPlot->getNumUnits() : 1;
		for (int unitIndex = 0; unitIndex < candidates; ++unitIndex)
		{
			CvUnit* pLoopUnit = CvStacking::IsEnabled() ? pPlot->getUnitByIndex(unitIndex) : pPlot->getBestDefender(m_pPlayer->GetID());
			if (!pLoopUnit || pLoopUnit->getOwner() != m_pPlayer->GetID() || !pLoopUnit->IsCombatUnit() || pLoopUnit->isCargo())
				continue;
			if (pLoopUnit->isDelayedDeath())
				continue;

			if (!pLoopUnit->canMove() || pLoopUnit->TurnProcessed())
				continue;

			// plundering a trade route on the current plot doesn't cost us anything, so we do it whenever possible and the following exclusions do not apply
			if (!bPlunderTradeRoute || pPlot != pTarget)
			{
				if (!pLoopUnit->canUseForTacticalAI())
					continue;

				//these units are too fragile for the moves we have in mind
				if (pLoopUnit->AI_getUnitAIType() == UNITAI_CITY_BOMBARD || pLoopUnit->AI_getUnitAIType() == UNITAI_CARRIER_SEA)
					continue;

				if (pLoopUnit->IsCoveringFriendlyCivilian())
					continue;

				if (iMinHitpoints > 0 && pLoopUnit->GetCurrHitPoints() < iMinHitpoints)
					continue;

				if (iMaxHitpoints > 0 && pLoopUnit->GetCurrHitPoints() > iMaxHitpoints)
					continue;

				if (pLoopUnit->GetDanger(pTarget) > pLoopUnit->GetCurrHitPoints())
					continue;

				//don't use garrisons if there is an enemy around. the garrison may still attack when we do garrison moves!
				if (pLoopUnit->IsGarrisoned() && pLoopUnit->GetGarrisonedCity()->NeedsGarrison() && pLoopUnit->getDomainType() != DOMAIN_SEA)
					continue;
			}

			if (pLoopUnit->isBarbarian() && pLoopUnit->plot()->getImprovementType() == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT))
				continue;

			if (eDomain != NO_DOMAIN && pLoopUnit->getDomainType() != eDomain)
				continue;

			//this should be a low-risk thing so don't get our units killed
			int iFlags = CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER;
			if (bAllowEmbarkation)
				iFlags |= CvUnit::MOVEFLAG_NO_EMBARK;
			if (pTarget->isEnemyUnit(m_pPlayer->GetID(), true, true) && !pLoopUnit->IsCanAttackWithMove())
				iFlags |= CvUnit::MOVEFLAG_APPROX_TARGET_RING1 | CvUnit::MOVEFLAG_APPROX_TARGET_NATIVE_DOMAIN;
			if (bMustHaveMovesLeft)
				iFlags |= CvUnit::MOVEFLAG_TURN_END_IS_NEXT_TURN;

			int iTurnsCalculated = pLoopUnit->TurnsToReachTarget(pTarget, iFlags, iNumTurnsAway);
			if (iTurnsCalculated <= iNumTurnsAway)
			{
				CvTacticalUnit unit(pLoopUnit->GetID());
				int iPlunderBonus = 0;
				if (bPlunderTradeRoute)
				{
					if (pLoopUnit->isHighSeaRaiderUnit())
					{
						iPlunderBonus += 500;
					}
					for (int iI = 0; iI < NUM_YIELD_TYPES; iI++)
					{
						iPlunderBonus += pLoopUnit->getYieldFromTRPlunder((YieldTypes)iI);
					}
				}
				unit.SetAttackStrength(1 + iNumTurnsAway - iTurnsCalculated + iPlunderBonus);
				unit.SetHealthPercent(1, 1);
				m_CurrentMoveUnits.push_back(unit);
				//pathfinding is expensive, don't return more than needed
				if (m_CurrentMoveUnits.size() >= (size_t)iMaxNumUnits)
					break;
			}
		}
	}

	// Now sort them in the order we'd like them to attack
	std::stable_sort(m_CurrentMoveUnits.begin(), m_CurrentMoveUnits.end());

	return m_CurrentMoveUnits.size()>0;
}

// search radius for units depending on map size and game turn
int CvTacticalAI::GetRecruitRange() const
{
	int iResult = m_iRecruitRange;
	//add some for duration
	iResult += (4*GC.getGame().getGameTurn()) / max(400, GC.getGame().getMaxTurns());
	//add some for map size
	if (GC.getMap().getWorldSize() == WORLDSIZE_LARGE)
		iResult += 1;
	if (GC.getMap().getWorldSize() == WORLDSIZE_HUGE)
		iResult += 2;

	return iResult;
}

/// Estimates the damage we can apply to a target
int CvTacticalAI::ComputeTotalExpectedDamage(const CvTacticalTarget& kTarget)
{
	CvPlot* pTargetPlot = GC.getMap().plot(kTarget.GetTargetX(), kTarget.GetTargetY());

	int rtnValue = 0;
	int iMeleeCount = 0;
	int iTotalGarrisonDamage = 0;

	CvUnit* pCurrentGarrison = kTarget.GetTargetType() == AI_TACTICAL_TARGET_ENEMY_CITY ? pTargetPlot->getPlotCity()->GetGarrisonedUnit() : NULL;
	int iCurrentGarrisonHealth = pCurrentGarrison ? pCurrentGarrison->GetCurrHitPoints() : 0;
	PlayerTypes eOwner = pTargetPlot->getOwner();
 SUnitIDValueContainer projectedGarrisonDamage;
 vector<const CvUnit*> projectedCityOccupants;
 if (CvStacking::IsEnabled() && pTargetPlot->isCity())
  for (int i = 0; i < pTargetPlot->getNumUnits(); ++i)
  {
   const CvUnit* unit = pTargetPlot->getUnitByIndex(i);
   if (unit && unit->IsCanDefend() && !unit->isCargo() && !unit->isDelayedDeath())
    projectedCityOccupants.push_back(unit);
  }


	// Loop through all units who can reach the target
	for(unsigned int iI = 0; iI < m_CurrentMoveUnits.size(); iI++)
	{
		CvUnit* pAttacker = m_pPlayer->getUnit(m_CurrentMoveUnits[iI].GetID());

		// Is target a unit?
		switch(kTarget.GetTargetType())
		{
		case AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT:
		{
			CvUnit* pDefender = pTargetPlot->getBestDefender(NO_PLAYER, m_pPlayer->GetID(), pAttacker, true);
			if (pDefender)
			{
				int iSelfDamage = 0;
				//attacker plot will likely change but this is just an estimation anyway
				int iDamage = TacticalAIHelpers::GetSimulatedDamageFromAttackOnUnit(pDefender, pAttacker, pTargetPlot, pAttacker->plot(), iSelfDamage, true, 0, 0, true);
				if (iDamage > iSelfDamage/5 && pAttacker->GetCurrHitPoints() > iSelfDamage/2) //exclude only the most extreme suicides, we will sort out the details during combat sim
				{
					m_CurrentMoveUnits[iI].SetExpectedTargetDamage(iDamage);
					m_CurrentMoveUnits[iI].SetExpectedSelfDamage(iSelfDamage);

					//if we have a lot of melee units, don't assume they all can be executed at once
					if (!pAttacker->IsCanAttackRanged() && !pAttacker->canMoveAfterAttacking())
					{
						if (iMeleeCount<3)
							rtnValue += iDamage;
						iMeleeCount++;
					}
					else
						rtnValue += iDamage;
				}
			}
		}
		break;

		case AI_TACTICAL_TARGET_ENEMY_CITY:
		{
			CvCity* pCity = pTargetPlot->getPlotCity();
			if(pCity != NULL)
			{
    if (CvStacking::IsEnabled())
    {
     // Preserve every projected victim's HP. Ignoring only the most recently
     // killed garrison can recycle an earlier casualty in a larger city stack.
     const CvUnit* garrison = TacticalAIHelpers::GetSimulatedGarrison(pCity, projectedCityOccupants, projectedGarrisonDamage);
     int selfDamage = 0, garrisonDamage = 0;
     const int previous = garrison ? projectedGarrisonDamage.GetValue(garrison->GetID()) : 0;
     const int cityDamage = TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(pCity, pAttacker, pAttacker->plot(),
      selfDamage, garrisonDamage, true, 0, rtnValue, previous, false, true, garrison);
     const vector<pair<const CvUnit*, int> > collateral = CvUnitCombat::GetStackCollateralDamage(pAttacker, pTargetPlot, NULL,
      cityDamage, projectedCityOccupants, projectedGarrisonDamage, garrison, garrisonDamage, rtnValue);
     const int actualGarrisonDamage = garrison ? min(garrisonDamage, max(0, garrison->GetCurrHitPoints() - previous)) : 0;
     int collateralDamage = 0;
     for (size_t j = 0; j < collateral.size(); ++j)
      collateralDamage += collateral[j].second;
     const int totalDamage = cityDamage + actualGarrisonDamage + collateralDamage;
     if (totalDamage > selfDamage || (totalDamage * 2 > selfDamage && pAttacker->GetCurrHitPoints() - selfDamage > pAttacker->GetMaxHitPoints() / 2))
     {
      if (garrison)
       projectedGarrisonDamage.ChangeValue(garrison->GetID(), garrisonDamage);
      for (size_t j = 0; j < collateral.size(); ++j)
       projectedGarrisonDamage.ChangeValue(collateral[j].first->GetID(), collateral[j].second);
      m_CurrentMoveUnits[iI].SetExpectedTargetDamage(cityDamage + actualGarrisonDamage + collateralDamage * StackCollateralWeight() / 100);
      m_CurrentMoveUnits[iI].SetExpectedSelfDamage(selfDamage);
      // Callers use this total for city-health thresholds, so secondary unit
      // damage affects ranking but never masquerades as damage to the city.
      rtnValue += cityDamage;
     }
     break;
    }

				int iSelfDamage = 0;
				int iGarrisonDamage = 0;
				bool bNeedsRecalculation = pCurrentGarrison != pCity->GetGarrisonedUnit();
				//attacker plot will likely change but this is just an estimation anyway
				int iDamage = TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(pCity, pAttacker, pAttacker->plot(), iSelfDamage, iGarrisonDamage, true, 0, rtnValue, iTotalGarrisonDamage, false, true, pCurrentGarrison);
				iTotalGarrisonDamage += iGarrisonDamage;

				if (pCurrentGarrison)
				{
					iCurrentGarrisonHealth -= iGarrisonDamage;
					if (iCurrentGarrisonHealth <= 0)
					{
						pCurrentGarrison = pTargetPlot->getBestDefender(eOwner, m_pPlayer->GetID(), NULL, true, true, false, false, pCurrentGarrison);
						iCurrentGarrisonHealth = pCurrentGarrison ? pCurrentGarrison->GetCurrHitPoints() : 0;
						iTotalGarrisonDamage = 0;
					}
				}
				if (iDamage + iGarrisonDamage > iSelfDamage || ((iDamage + iGarrisonDamage) * 2 > iSelfDamage && pAttacker->GetCurrHitPoints() - iSelfDamage > pAttacker->GetMaxHitPoints() / 2)) //exclude suicidal melee attacks
				{
					// If we did the previous calculation with the wrong garrisoned unit, we need to recompute the value assuming a garrison is present to ensure fair sorting
					// TODO we should probably sort m_CurrentMoveUnits so the ranged units and strongest units are processed first, weak units can then be used to finish off the city or attack when the garrison is dead
					int iNormalizedDamage = bNeedsRecalculation ? TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(pCity, pAttacker, pAttacker->plot(), iSelfDamage, iGarrisonDamage, true) : iDamage;

					m_CurrentMoveUnits[iI].SetExpectedTargetDamage(iNormalizedDamage);
					m_CurrentMoveUnits[iI].SetExpectedSelfDamage(iSelfDamage);
					rtnValue += iDamage;
				}
			}
		}
		break;
		default:
		UNREACHABLE(); // Other target types cannot be damaged.
		}
	}

	//sort by expected damage to target!
	std::stable_sort(m_CurrentMoveUnits.begin(), m_CurrentMoveUnits.end(), TacticalAIHelpers::SortByExpectedTargetDamageDescending);

	return rtnValue;
}

/// Estimates the bombard damage we can apply to a target
int CvTacticalAI::ComputeTotalExpectedCityBombardDamage(CvUnit* pTarget)
{
	int iExpectedDamage = 0;

	// Now loop through all the cities that can bombard it
	for(unsigned int iI = 0; iI < m_CurrentMoveCities.size(); iI++)
	{
		CvCity* pAttackingCity = m_pPlayer->getCity(m_CurrentMoveCities[iI].GetID());
		
		iExpectedDamage += pAttackingCity->rangeCombatDamage(pTarget);

		if (pAttackingCity->HasGarrison())
		{
			CvUnit* pGarrison = pAttackingCity->GetGarrisonedUnit();
			if (pGarrison->canRangeStrikeAt(pTarget->getX(), pTarget->getY()))
			{
				int iUnusedReferenceVariable = 0;
				int iUnitDamage = pGarrison->GetRangeCombatDamage(pTarget, NULL, 0, iUnusedReferenceVariable, false, 0, 0, NULL, NULL, true, true);
				//assume same damage for multiple attacks ...
				iExpectedDamage += iUnitDamage * pGarrison->getNumAttacks();
			}
		}

	}
	
	return iExpectedDamage;
}

bool CvTacticalAI::IsExpectedToDamageWithRangedAttack(CvUnit* pAttacker, CvPlot* pTargetPlot, int iMinDamage)
{
	int iExpectedDamage = 0;

	int iGarrisonDamage = 0;
	if(pTargetPlot->isCity())
	{
		CvCity* pCity = pTargetPlot->getPlotCity();
		int iGarrisonMaxHP = 0;
		if (pCity->HasGarrison() && !pCity->GetGarrisonedUnit()->isDelayedDeath())
		{
			iGarrisonMaxHP = pCity->GetGarrisonedUnit()->GetMaxHitPoints();
		}
		iExpectedDamage = pAttacker->GetRangeCombatDamage(NULL, pCity, iGarrisonMaxHP, iGarrisonDamage, /*bIncludeRand*/ false, 0, 0, NULL, NULL, true, true);
	}
	else
	{
		CvUnit* pDefender = pTargetPlot->getBestDefender(NO_PLAYER, m_pPlayer->GetID(), pAttacker, true);
		if(pDefender)
		{
			iExpectedDamage = pAttacker->GetRangeCombatDamage(pDefender, NULL, 0, iGarrisonDamage, false, 0, 0, NULL, NULL, true, true);
		}
	}

 const CvUnit* primary = pTargetPlot->isCity() ? NULL : pTargetPlot->getBestDefender(NO_PLAYER, m_pPlayer->GetID(), pAttacker, true);
 iExpectedDamage += StackCollateralValue(pAttacker, pTargetPlot, primary, iExpectedDamage, iGarrisonDamage);
 return iExpectedDamage >= iMinDamage;
}

/// Move up close to our target avoiding our own units if possible
bool CvTacticalAI::MoveToEmptySpaceNearTarget(CvUnit* pUnit, CvPlot* pTarget, DomainTypes eDomain, int iMaxTurns, bool bMustBeSafePath)
{
	if (!pUnit || !pTarget || pUnit->atPlot(*pTarget))
		return false;

	int iFlags = 0;
	//can we move there directly? if not try to move to an adjacent plot
	if (!pUnit->canMoveInto(*pTarget, CvUnit::MOVEFLAG_DESTINATION))
		iFlags |= CvUnit::MOVEFLAG_APPROX_TARGET_RING1;
	if (eDomain==pTarget->getDomain())
		iFlags |= CvUnit::MOVEFLAG_APPROX_TARGET_NATIVE_DOMAIN;
	if (bMustBeSafePath)
		iFlags |= CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER;

	int iTurns = pUnit->TurnsToReachTarget(pTarget,iFlags,iMaxTurns);

	//if not possible, try again with more leeway
	if (iTurns==INT_MAX)
	{
		if (iFlags & CvUnit::MOVEFLAG_APPROX_TARGET_RING1)
		{
			iFlags &= ~CvUnit::MOVEFLAG_APPROX_TARGET_RING1;
			iFlags |= CvUnit::MOVEFLAG_APPROX_TARGET_RING2;
		}
		else
			iFlags |= CvUnit::MOVEFLAG_APPROX_TARGET_RING1;

		iTurns = pUnit->TurnsToReachTarget(pTarget,iFlags,iMaxTurns);
	}

	if (iTurns <= iMaxTurns)
	{
		//for inspection in GUI
		pUnit->SetMissionAI(MISSIONAI_TACTMOVE,pTarget,NULL);

		//may not actually move if there is no safe path
		pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pTarget->getX(), pTarget->getY(), iFlags);

		//don't call finish moves, otherwise we won't heal!
		return true;
	}

	return false;
}

/// Find a multi-turn target for a land barbarian to wander towards
CvPlot* CvTacticalAI::FindBestBarbarianLandTarget(CvUnit* pUnit)
{
	CvPlot* pBestMovePlot = NULL;
	int iMaxTurns = m_iLandBarbarianRange;
	
	// combat units look at all offensive targets within x turns
	if (pUnit->IsCanDefend())
	{
		pBestMovePlot = FindNearbyTarget(pUnit, iMaxTurns, true);

		// alternatively explore
		if (pBestMovePlot == NULL)
			pBestMovePlot = FindBarbarianExploreTarget(pUnit);
	}

	// by default go back to camp or so
	if (pBestMovePlot == NULL)
	{
		if (!pUnit->IsCanDefend())
			iMaxTurns = 23;

		pBestMovePlot = FindNearbyTarget(pUnit, iMaxTurns, false);
	}

	return pBestMovePlot;
}

/// Find a multi-turn target for a sea barbarian to wander towards
CvPlot* CvTacticalAI::FindBestBarbarianSeaTarget(CvUnit* pUnit)
{
	CvPlot* pBestMovePlot = NULL;
	int iBestValue = MAX_INT;

	SPathFinderUserData data(pUnit, 0, m_iSeaBarbarianRange);
	ReachablePlots movePlots = GC.GetPathFinder().GetPlotsInReach(pUnit->plot(), data);

	// Loop through all unit targets to find the closest
	for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT); pTarget != NULL; pTarget = GetNextZoneTarget())
	{
		CvPlot* pPlot = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());

		ReachablePlots::const_iterator itPlot = movePlots.find(pPlot->GetPlotIndex());
		if (itPlot != movePlots.end() && itPlot->iPathLength < iBestValue)
		{
			iBestValue = itPlot->iPathLength;
			pBestMovePlot = pPlot;
		}
	}

	// No units to pick on, so sail to a tile adjacent to the second closest barbarian camp
	if(pBestMovePlot == NULL)
	{
		CvPlot* pNearestCamp = NULL;
		int iBestCampDistance = MAX_INT;

		// Start by finding the very nearest camp
		for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_BARBARIAN_CAMP); pTarget!=NULL; pTarget = GetNextZoneTarget())
		{
			CvPlot* pCamp = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
			if (pCamp->isAdjacentToShallowWater())
			{
				int iDistance = plotDistance(pUnit->getX(), pUnit->getY(), pTarget->GetTargetX(), pTarget->GetTargetY());
				if (iDistance < iBestCampDistance)
				{
					pNearestCamp = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
					iBestCampDistance = iDistance;
				}
			}
		}

		// Try to sail to the second closest camp - this should result in patrolling behavior
		for (CvTacticalTarget* pTarget = GetFirstZoneTarget(AI_TACTICAL_TARGET_BARBARIAN_CAMP); pTarget!=NULL; pTarget = GetNextZoneTarget())
		{
			CvPlot* pCamp = GC.getMap().plot(pTarget->GetTargetX(), pTarget->GetTargetY());
			if(pCamp != pNearestCamp && pCamp->isAdjacentToShallowWater())
			{
				for (ReachablePlots::const_iterator it = movePlots.begin(); it != movePlots.end(); ++it)
				{
					CvPlot* pTestPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);
					if (pTestPlot->isAdjacent(pCamp))
					{
						int iValue = it->iPathLength;
						if (iValue < iBestValue)
						{
							iBestValue = iValue;
							pBestMovePlot = pTestPlot;
						}
					}
				}
			}
		}
	}

	// No obvious target ... next try
	if (pBestMovePlot == NULL)
		pBestMovePlot = FindBarbarianExploreTarget(pUnit);

	return pBestMovePlot;
}

/// Scan nearby tiles for the best choice, borrowing code from the explore AI
CvPlot* CvTacticalAI::FindBarbarianExploreTarget(CvUnit* pUnit)
{
	CvPlot* pBestMovePlot = 0;
	int iBestValue = 0;

	ReachablePlots reachablePlots = pUnit->GetAllPlotsInReachThisTurn(true, true, false);
	for (ReachablePlots::const_iterator it = reachablePlots.begin(); it != reachablePlots.end(); ++it)
	{
		CvPlot* pConsiderPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);

		if (pUnit->atPlot(*pConsiderPlot))
			continue;

		//ignore cities
		if (!pConsiderPlot->isRevealed(pUnit->getTeam()) || pConsiderPlot->isCity())
			continue;

		//even barbarians consider danger sometimes
		if (pUnit->GetDanger(pConsiderPlot) > pUnit->GetCurrHitPoints())
			continue;

		int iValue = 0;
		for (int i = 0; i < RING1_PLOTS; i++)
		{
			CvPlot* pNeighbor = iterateRingPlots(pConsiderPlot, i);
			if (!pNeighbor)
				continue;

			if (!pNeighbor->isRevealed(pUnit->getTeam()))
				iValue += 3;
			else if (!pNeighbor->isVisible(pUnit->getTeam()) && pNeighbor->isOwned())
				iValue += 2;
		}

		// disembark if possible
		if (pUnit->isEmbarked() && pUnit->isNativeDomain(pConsiderPlot))
			iValue += 100;

		if (iValue > iBestValue)
		{
			pBestMovePlot = pConsiderPlot;
			iBestValue = iValue;
		}
	}

	return pBestMovePlot;
}

/// Do we want to move this air unit to a new base?
bool CvTacticalAI::ShouldRebase(CvUnit* pUnit) const
{
	if (!pUnit || pUnit->getDomainType()!=DOMAIN_AIR)
		return false;

	CvPlot* pUnitPlot = pUnit->plot();
	if (!pUnitPlot)
		return false;

	// Is this unit in a base in danger?
	if (pUnitPlot->isCity())
	{
		if (pUnitPlot->getPlotCity()->isInDangerOfFalling(true))
			return true;

		if (pUnit->shouldHeal(true) && m_pPlayer->GetPlotDanger(pUnitPlot->getPlotCity())>0)
			return true;
	}
	else
	{
		CvUnit *pCarrier = pUnit->getTransportUnit();
		if (pCarrier && pCarrier->isProjectedToDieNextTurn())
			return true;

		if (pUnit->shouldHeal(true) && pCarrier && pCarrier->GetDanger(pUnitPlot)>0)
			return true;
	}

	bool bIsNeeded = false;
	if (!m_pPlayer->GetPlayersAtWarWith().empty())
	{
		switch (pUnit->getUnitInfo().GetDefaultUnitAIType())
		{
		case UNITAI_DEFENSE_AIR:
			// Is this a fighter that doesn't have any useful missions nearby
			{
				int iNumNearbyEnemyAirUnits = m_pPlayer->GetMilitaryAI()->GetNumEnemyAirUnitsInRange(pUnitPlot, pUnit->GetRange(), true /*bCountFighters*/, true /*bCountBombers*/);
				if (iNumNearbyEnemyAirUnits > 0  || m_pPlayer->GetMilitaryAI()->GetBestAirSweepTarget(pUnit))
				{
					bIsNeeded = true;
				}
			}
			break;
		case UNITAI_ATTACK_AIR:
		case UNITAI_ICBM:
		case UNITAI_MISSILE_AIR:
			//Is this a bomber or a missile that lacks useful target?
			{
				//check for targets in tactical map
				for(unsigned int iI = 0; iI < m_AllTargets.size(); iI++)
				{
					// If it's a nuke, we only want city targets
					if (pUnit->canNuke())
					{
						if (m_AllTargets[iI].GetTargetType() != AI_TACTICAL_TARGET_ENEMY_CITY)
							continue;
						//if the city is already weak, no point in nuking it
						CvPlot* pTargetPlot = GC.getMap().plot(m_AllTargets[iI].GetTargetX(), m_AllTargets[iI].GetTargetY());
						if (pTargetPlot->getPlotCity()->isInDangerOfFalling())
							continue;
					}

					// Is the target of an appropriate type?
					if(m_AllTargets[iI].GetTargetType() == AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT)
					{
						// Is this target near enough?
						if(plotDistance(pUnit->getX(), pUnit->getY(), m_AllTargets[iI].GetTargetX(), m_AllTargets[iI].GetTargetY()) <= pUnit->GetRange())
						{
							bIsNeeded = true;
							break;
						}
					}
				}
			}
			break;
		default:
			UNREACHABLE(); // Unit type cannot rebase.
		}

	}

	return !bIsNeeded;
}

// Find a faraway target for a unit to wander towards
// Can be either a specific type or any offensive type
// Returns the closest matching target that is reachable for the unit
CvPlot* CvTacticalAI::FindNearbyTarget(CvUnit* pUnit, int iMaxTurns, bool bOffensive)
{
	if (pUnit == NULL)
		return NULL;

	vector<OptionWithScore<CvPlot*>> candidates;

	// Loop through all appropriate targets to find the closest
	for(unsigned int iI = 0; iI < m_AllTargets.size(); iI++)
	{
		CvTacticalTarget target = m_AllTargets[iI];

		// Is the target of an appropriate type?
		bool bTypeMatch = false;
		if(bOffensive)
		{
			if (target.GetTargetType() == AI_TACTICAL_TARGET_ENEMY_COMBAT_UNIT ||
				target.GetTargetType() == AI_TACTICAL_TARGET_ENEMY_CITY)
			{
				bTypeMatch = !TacticalAIHelpers::IsSuicideMeleeAttack(pUnit, GC.getMap().plotUnchecked(target.GetTargetX(), target.GetTargetY()));
			}

			if (target.GetTargetType() == AI_TACTICAL_TARGET_IMPROVEMENT ||
				target.GetTargetType() == AI_TACTICAL_TARGET_IMPROVEMENT_RESOURCE ||
				(target.GetTargetType() == AI_TACTICAL_TARGET_TRADE_UNIT_LAND && pUnit->getDomainType()==DOMAIN_LAND) ||
				(target.GetTargetType() == AI_TACTICAL_TARGET_TRADE_UNIT_SEA && pUnit->getDomainType()==DOMAIN_SEA) ||
 				target.GetTargetType() == AI_TACTICAL_TARGET_HIGH_PRIORITY_CIVILIAN ||
				target.GetTargetType() == AI_TACTICAL_TARGET_LOW_PRIORITY_CIVILIAN )
			{
				bTypeMatch = true;
			}
		}
		else //defensive targets
		{
			if (target.GetTargetType() == AI_TACTICAL_TARGET_FRIENDLY_CITY ||
				(pUnit->isBarbarian() && target.GetTargetType() == AI_TACTICAL_TARGET_BARBARIAN_CAMP))
			{
				bTypeMatch = true;
			}
		}

		// Is this unit near enough?
		if (bTypeMatch)
		{
			CvPlot* pPlot = GC.getMap().plot(target.GetTargetX(), target.GetTargetY());
			if (!pPlot)
				continue;

			if (plotDistance(target.GetTargetX(), target.GetTargetY(),pUnit->getX(),pUnit->getY()) > iMaxTurns*3)
				continue;

			//can't do anything if we would need to embark
			if (pPlot->needsEmbarkation(pUnit))
				continue;

			//Ranged naval unit? Let's get a water plot (naval melee can enter cities, don't care for others)
			if (!pPlot->isWater() && pUnit->IsCanAttackRanged() && pUnit->getDomainType() == DOMAIN_SEA)
			{
				pPlot = MilitaryAIHelpers::GetCoastalWaterNearPlot(pPlot);
				if (!pPlot)
					continue;
			}
	
			//shortcut, may happen often (do this after the domain checks so don't accidentally get stuck in the wrong domain)
			if (pUnit->plot() == pPlot)
				return pPlot;

			candidates.push_back(OptionWithScore<CvPlot*>(pPlot, plotDistance(*pPlot, *pUnit->plot())));
		}
	}

	//second round. default sort order is descending
	std::stable_sort(candidates.begin(), candidates.end());
	std::reverse(candidates.begin(), candidates.end());

	for (size_t i=0; i<candidates.size(); i++)
	{
		CvPlot* pPlot = candidates[i].option;
		if ( pUnit->TurnsToReachTarget(pPlot,CvUnit::MOVEFLAG_APPROX_TARGET_RING1|CvUnit::MOVEFLAG_IGNORE_STACKING_SELF|CvUnit::MOVEFLAG_AI_ABORT_IN_DANGER,iMaxTurns) < INT_MAX )
			return pPlot;
	}

	return NULL;
}

/// Remove a unit that we've allocated from list of units to move this turn
void CvTacticalAI::UnitProcessed(int iID)
{
	m_CurrentTurnUnits.remove(iID);

	CvUnit* pUnit = m_pPlayer->getUnit(iID);
	if (!pUnit)
		return;

	if (iID==gCurrentUnitToTrack)
	{
		CvPlayer& owner = GET_PLAYER(pUnit->getOwner());
		OutputDebugString( CvString::format("turn %03d: used %s %s %d for tactical move %s. hitpoints %d, pos (%d,%d), danger %d\n", 
			GC.getGame().getGameTurn(), owner.getCivilizationAdjective(), pUnit->getName().c_str(), gCurrentUnitToTrack,
			tacticalMoveNames[m_CurrentMoveUnits.getCurrentTacticalMove()], 
			pUnit->GetCurrHitPoints(), pUnit->getX(), pUnit->getY(), pUnit->GetDanger() ) );
	}

	pUnit->setTacticalMove(m_CurrentMoveUnits.getCurrentTacticalMove());
	pUnit->SetTurnProcessed(true);

	//try and upgrade units even if tactical AI is using them
	if (pUnit->CanUpgradeRightNow(false) && !pUnit->IsHurt())
	{
		// Don't upgrade if we will go over supply
		if (m_pPlayer->GetNumUnitsToSupply() < m_pPlayer->GetNumUnitsSupplied() || !pUnit->isNoSupply())
		{
			CvUnit* pNewUnit = pUnit->DoUpgrade();
			if (pNewUnit)
				pNewUnit->SetTurnProcessed(true);
		}
	}
}

/// Is this civilian target of high priority?
bool CvTacticalAI::IsHighPriorityCivilianTarget(CvTacticalTarget* pTarget)
{
	//barbarians don't care
	if (m_pPlayer->isBarbarian())
		return true;

	CvUnit* pUnit = pTarget->GetUnitPtr();
	if (pUnit && pUnit->IsCivilianUnit())
	{
		if (pUnit->IsCombatSupportUnit())
			return true;

		if (pUnit->AI_getUnitAIType() == UNITAI_SETTLE)
			return true;
	}

	return false;
}

FILogFile* CvTacticalAI::GetLogFile()
{
	return LOGFILEMGR.GetLog(GetLogFileName(m_pPlayer->getCivilizationShortDescription()), FILogFile::kDontTimeStamp | FILogFile::kDontFlushOnWrite);
}

/// Log current status of the operation
void CvTacticalAI::LogTacticalMessage(const CvString& strMsg)
{
	if(GC.getLogging() && GC.getAILogging())
	{
		CvString strOutBuf;
		CvString strBaseString;

		CvString strPlayerName(m_pPlayer->getCivilizationShortDescription());
		strPlayerName.Replace(' ', '_'); //no spaces!

		// Get the leading info for this line
		strBaseString.Format("%03d, ", GC.getGame().getElapsedGameTurns());
		strBaseString += strPlayerName + ", ";

		strOutBuf = strBaseString + strMsg;

		FILogFile* pLog = GetLogFile();
		if (pLog)
			pLog->Msg(strOutBuf);
	}
}

/// Build log filename
CvString CvTacticalAI::GetLogFileName(const CvString& playerName) const
{
	CvString strLogName;

	// Open the log file
	if(GC.getPlayerAndCityAILogSplit())
	{
		strLogName = "PlayerTacticalAILog_" + playerName + ".csv";
	}
	else
	{
		strLogName = "PlayerTacticalAILog.csv";
	}

	return strLogName;
}

// HELPER FUNCTIONS
bool TacticalAIHelpers::SortByExpectedTargetDamageDescending(const CvTacticalUnit& obj1, const CvTacticalUnit& obj2)
{
	return obj1.GetExpectedTargetDamage()*2-obj1.GetExpectedSelfDamage() > obj2.GetExpectedTargetDamage()*2-obj2.GetExpectedSelfDamage();
}

ReachablePlots TacticalAIHelpers::GetAllPlotsInReachThisTurn(const CvUnit* pUnit, const CvPlot* pStartPlot, int iFlags, int iMinMovesLeft, int iStartMoves, const PlotIndexContainer& plotsToIgnoreForZOC)
{
	if (!pStartPlot)
		return ReachablePlots();

	if (!plotsToIgnoreForZOC.empty())
		iFlags |= CvUnit::MOVEFLAG_SELECTIVE_ZOC;

	SPathFinderUserData data(pUnit, iFlags, 1);
	data.iMinMovesLeft = iMinMovesLeft;
	if (iStartMoves>-1) //overwrite this only if we have a sane value
		data.iStartMoves = iStartMoves;
	data.plotsToIgnoreForZOC = plotsToIgnoreForZOC;

	return GC.GetPathFinder().GetPlotsInReach(pStartPlot->getX(), pStartPlot->getY(), data);
}

vector<int> TacticalAIHelpers::GetPlotsUnderRangedAttackFrom(const CvUnit* pUnit, const CvPlot* pBasePlot, bool bOnlyWithEnemy, bool bIgnoreVisibility)
{
	vector<int> resultSet;

	if (!pUnit || !pBasePlot)
		return resultSet;

	int iRange = min(5,max(1,pUnit->GetRange()));
	for(int i=1; i<RING_PLOTS[iRange]; i++)
	{
		CvPlot* pLoopPlot = iterateRingPlots(pBasePlot,i);
		if (!pLoopPlot)
			continue;

		if (!bOnlyWithEnemy || pLoopPlot->isEnemyCity(*pUnit) || pLoopPlot->isEnemyUnit(pUnit->getOwner(),true,!bIgnoreVisibility))
			if (pUnit->canEverRangeStrikeAt(pLoopPlot->getX(), pLoopPlot->getY(), pBasePlot, bIgnoreVisibility))
				resultSet.push_back(pLoopPlot->GetPlotIndex());
	}

	return resultSet;
}

vector<int> TacticalAIHelpers::GetPlotsUnderRangedAttackFrom(const CvUnit* pUnit, ReachablePlots& basePlots, bool bOnlyWithEnemy, bool bIgnoreVisibility)
{
	vector<int> resultSet;

	if (!pUnit || !pUnit->IsCanAttackRanged() || basePlots.empty())
		return resultSet;

	// Ascending and unique, like the std::set this replaced, without one tree node per
	// attackable plot. The bitmap answers the "already attackable" test.
	vector<bool> attackable(GC.getMap().numPlots(), false);

	int iRange = min(5,max(1,pUnit->GetRange()));
	for (ReachablePlots::const_iterator base=basePlots.begin(); base!=basePlots.end(); ++base)
	{
		CvPlot* pBasePlot = GC.getMap().plotByIndexUnchecked( base->iPlotIndex );

		int iPlotMoves = base->iMovesLeft;
		if (iPlotMoves<=0)
			continue;

		//can't shoot if embarked
		if (!pUnit->isNativeDomain(pBasePlot))
			continue;

		//we have enough moves for an attack ...
		for(int i=1; i<RING_PLOTS[iRange]; i++)
		{
			CvPlot* pLoopPlot = iterateRingPlots(pBasePlot,i);

			//if the plot is already know to be attackable, don't check again
			//the reverse is not true: from another base plot the attack might work!
			if (!pLoopPlot || attackable[pLoopPlot->GetPlotIndex()])
				continue;

			if (!bOnlyWithEnemy || pLoopPlot->isEnemyCity(*pUnit) || pLoopPlot->isEnemyUnit(pUnit->getOwner(),true,!bIgnoreVisibility))
				if (pUnit->canEverRangeStrikeAt(pLoopPlot->getX(), pLoopPlot->getY(), pBasePlot, bIgnoreVisibility))
				{
					attackable[pLoopPlot->GetPlotIndex()] = true;
					resultSet.push_back(pLoopPlot->GetPlotIndex());
				}
		}
	}

	std::sort(resultSet.begin(), resultSet.end());
	return resultSet;
}

void TacticalAIHelpers::UpdatePlotDistanceToTarget(PlayerTypes ePlayer, CvPlot* pTargetPlot)
{
	CvStackingDiagnostics::TurnPhaseScope phase(ePlayer,"target_distance_fields"); // TARGET_DISTANCE_FIELD_TIMING_DIAGNOSTIC_ONLY
	gDistanceToTargetPlots.clear();

	SPathFinderUserData data(ePlayer, PT_LAND_UNIT_SIMPLE);
	if (!GET_PLAYER(ePlayer).CanEmbark())
		data.iFlags |= CvUnit::MOVEFLAG_NO_EMBARK;

	ReachablePlots eReachablePlots = GC.GetStepFinder().GetPlotsInReach(pTargetPlot, data);
	gDistanceToTargetPlots[DOMAIN_LAND] = eReachablePlots;

	data.ePath = PT_NAVAL_UNIT_SIMPLE;
	if (!GET_TEAM(GET_PLAYER(ePlayer).getTeam()).CanBuildOceanCrossingUnit())
		data.iFlags |= CvUnit::MOVEFLAG_NO_OCEAN;

	eReachablePlots = GC.GetStepFinder().GetPlotsInReach(pTargetPlot, data);
	gDistanceToTargetPlots[DOMAIN_SEA] = eReachablePlots;
	gTargetPlot = pTargetPlot;
}

int TacticalAIHelpers::GetPlotDistanceToTarget(int iPlotIndex, DomainTypes eDomain)
{
	if (gDistanceToTargetPlots.empty())
		return plotDistance(gTargetPlot->GetPlotIndex(), iPlotIndex);

	if (eDomain == DOMAIN_HOVER)
		eDomain = DOMAIN_LAND;

	ReachablePlots::const_iterator it = gDistanceToTargetPlots[eDomain].find(iPlotIndex);
	if (it == gDistanceToTargetPlots[eDomain].end())
		return INT_MAX;

	return it->iPathLength;
}

bool TacticalAIHelpers::IsAttackNetPositive(CvUnit* pUnit, const CvPlot* pTargetPlot, int iSelfDamage)
{
	if (!pUnit || !pTargetPlot)
		return false;

	//target can be city or a unit
	CvCity* pTargetCity = pTargetPlot->getPlotCity();
	//no visibility check, when we call this we already know there is an enemy unit ...
	CvUnit* pTargetUnit = pTargetPlot->getBestDefender( NO_PLAYER, pUnit->getOwner(), pUnit, false, true);

	int iDamageDealt = 0;
	int iGarrisonDamage = 0;
	int iDamageReceived = 1;
	if (pTargetCity)
	{
		//+2 to make sure it's positive if city has zero hitpoints left
		iDamageDealt = GetSimulatedDamageFromAttackOnCity(pTargetCity, pUnit, pUnit->plot(), iDamageReceived, iGarrisonDamage, false, iSelfDamage) + 2;
		return (iDamageDealt + iGarrisonDamage > iDamageReceived || iDamageDealt == pTargetCity->GetMaxHitPoints()-pTargetCity->getDamage());
	}
	else if (pTargetUnit)
	{
		iDamageDealt = GetSimulatedDamageFromAttackOnUnit(pTargetUnit, pUnit, pTargetUnit->plot(), pUnit->plot(), iDamageReceived, false, iSelfDamage);
		return (iDamageDealt > iDamageReceived || iDamageDealt == pTargetUnit->GetCurrHitPoints());
	}

	return false;
}

//see if there is a possible target around the unit
bool TacticalAIHelpers::PerformOpportunityAttack(CvUnit* pUnit, bool bAllowMovement)
{
	if (!pUnit || !pUnit->IsCanAttack() || !pUnit->canMove() || pUnit->isDelayedDeath())
		return false;

	//for ranged we have a readymade method
	if (pUnit->IsCanAttackRanged())
		return TacticalAIHelpers::PerformRangedOpportunityAttack(pUnit, bAllowMovement);

	//where can we go
	CvPlot* pOrigin = pUnit->plot();
	vector<CvPlot*> testPlots;
	if (bAllowMovement)
	{
		ReachablePlots reachablePlots = pUnit->GetAllPlotsInReachThisTurn(true, true, false);
		for (ReachablePlots::const_iterator it = reachablePlots.begin(); it != reachablePlots.end(); ++it)
		{
			CvPlot *pTestPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);
			testPlots.push_back(pTestPlot);
		}
	}
	else
	{
		//simply check all adjacent plots. if the unit is a garrison or the attack is not a kill, it will not advance after attacking
		for (int i = RING0_PLOTS; i < RING1_PLOTS; i++)
		{
			CvPlot* pTestPlot = iterateRingPlots(pOrigin, i);
			if (pTestPlot && pUnit->canMoveInto(*pTestPlot,CvUnit::MOVEFLAG_ATTACK))
				testPlots.push_back(pTestPlot);
		}
	}

	//what can we do?
	vector<SPlotWithScore> meleeTargets;
	int iScoreThreshold = 0;
	for (size_t i = 0; i < testPlots.size(); i++)
	{
		CvPlot* pTestPlot = testPlots[i];
		if (!pTestPlot || pTestPlot->isCity())
			continue;

		//attack an enemy?
		if (pTestPlot->isEnemyUnit(pUnit->getOwner(), true, true) && !pUnit->isOutOfAttacks())
		{
			CvUnit* pEnemy = pTestPlot->getBestDefender(NO_PLAYER, pUnit->getOwner(), pUnit, true);
			ASSERT(pEnemy, "isEnemyUnit is true, but getBestDefender didn't return a unit");
			if (!pEnemy)
				continue;
			int iDamageReceived = 0;
			int iDamageDealt = TacticalAIHelpers::GetSimulatedDamageFromAttackOnUnit(pEnemy, pUnit, pTestPlot, pOrigin, iDamageReceived);

			//no suicide
			if (iDamageReceived >= pUnit->GetCurrHitPoints())
				continue;

			//there might be stacking issues so do another pathfinder check
			if (pUnit->TurnsToReachTarget(pTestPlot, CvUnit::MOVEFLAG_ATTACK | CvUnit::MOVEFLAG_NO_EMBARK, 1) > 0)
				continue;

			if (iDamageDealt >= pEnemy->GetCurrHitPoints())
			{
				if (iDamageReceived < pUnit->GetCurrHitPoints())
					iDamageDealt += 30; //bonus for a kill, but no suicide

				int iHealFromKill = pUnit->getHPHealedIfDefeatEnemy();
				if (iHealFromKill > pUnit->getDamage() + iDamageReceived)
					iHealFromKill = pUnit->getDamage() + iDamageReceived;
				iDamageReceived -= iHealFromKill;

				if (!bAllowMovement && !pUnit->plot()->isFortification(pUnit->getTeam()))
					continue;
			}

			//we have just a single attacker, avoid enemy clusters
			if (iDamageReceived * 4 >= (pUnit->GetMaxHitPoints() - (pUnit->getDamage() + iDamageReceived)) * 3 && pTestPlot->GetNumEnemyUnitsAdjacent(pUnit->getTeam(), NO_DOMAIN) > 0)
				continue;

			//if the attacker is (almost) unhurt, we can be a bit more aggressive and assume we'll heal up next turn
			int iHealRate = pUnit->ActualHealRate(pUnit->plot());
			if (pUnit->getDamage() < iHealRate / 2 && iDamageReceived < pUnit->GetMaxHitPoints() / 2)
			{
				if (iHealRate > pUnit->getDamage() + iDamageReceived)
					iHealRate = pUnit->getDamage() + iDamageReceived;
				iDamageReceived -= iHealRate;
			}

			if (iDamageReceived <= 0)
			{
				iDamageDealt += iDamageReceived + 1;
				iDamageReceived = 0;
			}

			int iScore = (1000 * iDamageDealt) / (iDamageReceived + 10);
			meleeTargets.push_back(SPlotWithScore(pTestPlot, iScore));

			//increase the threshold for each new enemy we find
			iScoreThreshold += 1000;
		}
		//maybe capture a civilian?
		else if (pTestPlot->isEnemyUnit(pUnit->getOwner(), false, true))
		{
			bool bIsSafe = pUnit->GetDanger(pTestPlot) == 0 && pUnit->GetDanger() == 0;
			bool bCanReturn = pUnit->TurnsToReachTarget(pTestPlot, CvUnit::MOVEFLAG_ATTACK, 1) == 0;
			if (bIsSafe || bCanReturn)
				meleeTargets.push_back(SPlotWithScore(pTestPlot, 10 - plotDistance(*pTestPlot, *pUnit->plot())));
		}
	}

	//nothing to do?
	if (meleeTargets.empty())
		return false;

	std::stable_sort(meleeTargets.begin(), meleeTargets.end());

	//we will never do attacks with negative scores!
	if (meleeTargets.back().score < iScoreThreshold)
		return false;

	if (GC.getLogging() && GC.getAILogging())
	{
		CvString strMsg;
		strMsg.Format("Performing melee opportunity attack on (%d:%d) with %s at (%d:%d)",
			meleeTargets.front().pPlot->getX(), meleeTargets.front().pPlot->getY(), pUnit->getName().GetCString(), pUnit->getX(), pUnit->getY());
		GET_PLAYER(pUnit->getOwner()).GetTacticalAI()->LogTacticalMessage(strMsg);
	}

	pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), meleeTargets.back().pPlot->getX(), meleeTargets.back().pPlot->getY());
	if (pUnit->canMove() && !pUnit->atPlot(*pOrigin)) //try to move back to the original plot (if we advanced)
		pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pOrigin->getX(), pOrigin->getY());

	return true;
}

//see if we can hit anything from our current plot - with or without moving
bool TacticalAIHelpers::PerformRangedOpportunityAttack(CvUnit* pUnit, bool bAllowMovement, int bSaveMovement)
{
	if (!pUnit || !pUnit->IsCanAttackRanged() || !pUnit->canMove() || pUnit->isDelayedDeath())
		return false;

	CvPlot* pBasePlot = pUnit->plot();
	bool bIsAirUnit = pUnit->getDomainType() == DOMAIN_AIR;
	if (bIsAirUnit || (CvStackingAI::Enabled(pUnit->getOwner()) ? CvStackingAI::RetainCityUnit(pUnit) : (pUnit->IsGarrisoned() && pUnit->getDomainType() == DOMAIN_LAND && pUnit->plot()->getPlotCity()->NeedsGarrison())))
		bAllowMovement = false;

	if (bAllowMovement || pUnit->canMoveAfterAttacking())
	{
		//no loop needed, there is only one unit anyway
		set<int> dummy;
		gTargetPlot = pUnit->plot();
		vector<STacticalAssignment> vAssignments = TacticalAIHelpers::FindBestUnitAssignments(vector<CvUnit*>(1, pUnit), pUnit->plot(), AL_LOW, dummy, false, !bAllowMovement, bSaveMovement);
		if (vAssignments.empty())
			return false;

		if (GC.getLogging() && GC.getAILogging())
		{
			CvString strMsg;
			strMsg.Format("Performing ranged opportunity attack with %s at (%d:%d)", pUnit->getName().GetCString(), pUnit->getX(), pUnit->getY());
			GET_PLAYER(pUnit->getOwner()).GetTacticalAI()->LogTacticalMessage(strMsg);
		}

		return TacticalAIHelpers::ExecuteUnitAssignments(pUnit->getOwner(), vAssignments);
	}
	else
	{
		int iMaxDamage = 0;
		CvPlot* pBestTarget = NULL;

		int iRange = max(1,min(5,pUnit->GetRange()));
		for (int i=RING0_PLOTS; i<RING_PLOTS[iRange]; i++)
		{
			CvPlot* pLoopPlot = iterateRingPlots(pBasePlot, i);
			if (!pLoopPlot || pLoopPlot->isCity())
				continue;

			if (!pUnit->canRangeStrikeAt(pLoopPlot->getX(), pLoopPlot->getY()))
				continue;

			//don't blindly attack the first one we find, check how much damage we can do
			CvUnit* pOtherUnit = pLoopPlot->getBestDefender(NO_PLAYER, pUnit->getOwner(), pUnit, true /*testWar*/);
			if (pOtherUnit && !pOtherUnit->isDelayedDeath())
			{
				int  iUnusedReferenceVariable = 0;
				int iDamage = bIsAirUnit ? pUnit->GetAirCombatDamage(pOtherUnit, NULL, 0, iUnusedReferenceVariable, false) :
											pUnit->GetRangeCombatDamage(pOtherUnit, NULL, 0, iUnusedReferenceVariable, false) +  pUnit->GetRangeCombatSplashDamage(pOtherUnit->plot()) + (pUnit->hasMoved() ? 0 : pUnit->GetTileDamageIfNotMoved());

				const int collateralValue = StackCollateralValue(pUnit, pLoopPlot, pOtherUnit, iDamage);

				//kill bonus
				if (iDamage >= pOtherUnit->GetCurrHitPoints())
					iDamage += 30;
				iDamage += collateralValue;

				if (iDamage > iMaxDamage)
				{
					pBestTarget = pLoopPlot;
					iMaxDamage = iDamage;
				}
			}
		}

		if (!pBestTarget)
			return false;

		if (GC.getLogging() && GC.getAILogging())
		{
			CvString strMsg;
			strMsg.Format("Performing stationary ranged opportunity attack with %s at (%d:%d) on (%d:%d)",
				pUnit->getName().GetCString(), pUnit->getX(), pUnit->getY(), pBestTarget->getX(), pBestTarget->getY());
			GET_PLAYER(pUnit->getOwner()).GetTacticalAI()->LogTacticalMessage(strMsg);
		}

		pUnit->PushMission(bIsAirUnit ? CvTypes::getMISSION_MOVE_TO() : CvTypes::getMISSION_RANGE_ATTACK(), pBestTarget->getX(), pBestTarget->getY());
		return true;
	}
}

pair<CvPlot*, int> TacticalAIHelpers::FindSafestPlotInReach(const CvUnit* pUnit, bool bAllowEmbark, bool bConsiderPush)
{
	//use rebase moves for aircraft!
	if (!pUnit || pUnit->getDomainType() == DOMAIN_AIR)
		return make_pair(static_cast<CvPlot*>(NULL), 0);

	vector<OptionWithScore<pair<CvPlot*, int>>> aCityList;
	vector<OptionWithScore<pair<CvPlot*, int>>> aZeroDangerList;
	vector<OptionWithScore<pair<CvPlot*, int>>> aCoverList;
	vector<OptionWithScore<pair<CvPlot*, int>>> aDangerList;

	//special behavior for cities and citadels - don't run even if there is a "safe" plot somewhere else
	CvPlot* pCurrentPlot = pUnit->plot();
	bool bIsInCityOrCitadelNow = (pCurrentPlot->isFriendlyCity(*pUnit) && !pCurrentPlot->getPlotCity()->isInDangerOfFalling()) || 
								(pUnit->IsCombatUnit() && TacticalAIHelpers::IsPlayerCitadel(pCurrentPlot, pUnit->getOwner()) && pUnit->getDomainType() == DOMAIN_LAND);
	if (bIsInCityOrCitadelNow && !pUnit->isProjectedToDieNextTurn() && pUnit->canEndTurnAtPlot(pCurrentPlot))
		if (pUnit->AI_getUnitAIType()!=UNITAI_CITY_BOMBARD || pUnit->GetDanger(pCurrentPlot)<pUnit->GetCurrHitPoints())
			return make_pair(pCurrentPlot, pUnit->getMoves());

	//for current plot
	int iCurrentHealRate = pUnit->ActualHealRate(pUnit->plot());
	int iCurrentDanger = pUnit->GetDanger();

	//don't run if we are needed
	if (pUnit->IsCoveringFriendlyCivilian() && pUnit->GetDanger(pCurrentPlot)<pUnit->GetCurrHitPoints()*2)
		return make_pair(pCurrentPlot, pUnit->getMoves());

	//embarkation allowed for now, we sort it out below
	ReachablePlots eligiblePlots = pUnit->GetAllPlotsInReachThisTurn(); 
	for (ReachablePlots::const_iterator it = eligiblePlots.begin(); it != eligiblePlots.end(); ++it)
	{
		CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);

		// don't attack though
		if (pPlot->getNumVisibleEnemyDefenders(pUnit) > 0 || pPlot->isEnemyCity(*pUnit))
			continue;

		int iFlags = CvUnit::MOVEFLAG_DESTINATION;
		// allow capturing civilians!
		if (pPlot->isVisibleEnemyUnit(pUnit))
			iFlags |= CvUnit::MOVEFLAG_ATTACK;

		//if we cannot move in because one of our own units is blocking us
		if (!pUnit->canMoveInto(*pPlot, iFlags) && pUnit->canMoveInto(*pPlot, iFlags | CvUnit::MOVEFLAG_IGNORE_STACKING_SELF))
		{
			if (!bConsiderPush || !pUnit->CanPushOutUnitHere(*pPlot))
				continue;
		}

		//   prefer being in a city with the lowest danger value
		//   prefer being in a plot with no danger value
		//   prefer being under a unit with the lowest danger value
		//   prefer being in your own territory with the lowest danger value
		//   prefer the lowest danger value

		// plot danger is a bit unreliable, so we need extra checks
		CvPlayer& kPlayer = GET_PLAYER(pUnit->getOwner());
		int iDanger = pUnit->GetDanger(pPlot);
		int iCityDistance = kPlayer.GetCityDistancePathLength(pPlot);
		if (iCityDistance == INT_MAX)
			iCityDistance = 0; // No cities (e.g. barbarians) - distance irrelevant, use 0 to avoid overflow

		bool bIsZeroDanger = (iDanger <= 0);
		bool bIsInTerritory = (pPlot->getTeam() == kPlayer.getTeam());
		// citadels have low danger but not zero. so we need to make sure we're not abandoning them too easily
		bool bIsInCityOrCitadel = (pPlot->isFriendlyCity(*pUnit) && !pPlot->getPlotCity()->isInDangerOfFalling()) ||
			(pUnit->IsCombatUnit() && TacticalAIHelpers::IsPlayerCitadel(pPlot, pUnit->getOwner()) && pUnit->getDomainType() == DOMAIN_LAND);

		//civilians and embarked units want cover
		bool bIsInCover = false;
		if (pUnit->IsCivilianUnit() || !pUnit->isNativeDomain(pPlot))
		{
			CvUnit* pDefender = pPlot->getBestDefender(pUnit->getOwner());
			if (pDefender && pDefender != pUnit && !pDefender->isProjectedToDieNextTurn() && pDefender->GetDanger()<pDefender->GetCurrHitPoints())
			{
				bIsInCover = true;
				//otherwise we will get only INT_MAX for civilians
				iDanger = pDefender->GetDanger(pPlot);
			}
		}

		bool bWrongDomain = pPlot->needsEmbarkation(pUnit);
		bool bWouldEmbark = bWrongDomain && !pUnit->isEmbarked();

		//avoid overflow further down and useful handling for civilians
		if (iDanger == INT_MAX)
			iDanger = 10000;

		//map 144 to 144, everything above is not so important
		int iScore = (iDanger > 144) ? 12 * sqrti(iDanger) : iDanger;

		if (pPlot != pUnit->plot() && !pUnit->hasMoved())
		{
			//we can't heal after moving and lose fortification bonus, so the current plot gets a bonus (respectively all others a penalty)
			if (pUnit->canFortify(pUnit->plot()))
				iScore += 3;

			// We can outheal the danger, should stay and heal
			if (iCurrentHealRate > 0 && pUnit->getDamage() >= iCurrentHealRate && iCurrentHealRate > iCurrentDanger && !pUnit->isAlwaysHeal())
				iScore += max(0, iCurrentHealRate * 2);
		}

		//safer at home ... but not if we need to embark b/c we can't fight back then
		if (!bIsInTerritory || bWouldEmbark)
			iScore += 12;

		//try to hide - if there are few enemy units, this might be a tiebreaker
		if (pPlot->IsKnownVisibleToEnemy(pUnit->getOwner()))
			iScore += iScore / 4;

		//avoid enemy territory
		if (pPlot->IsAdjacentOwnedByEnemy(pUnit->getTeam()))
			iScore += iScore / 20;

		//avoid enemy units (for civilians danger may be infinite in a lot lof places)
		if (pPlot->IsEnemyUnitAdjacent(pUnit->getTeam()) || pPlot->IsEnemyCityAdjacent(pUnit->getTeam(), NULL))
			iScore += iScore / 10;

		//naval units should avoid enemy coast, never know what's hiding there
		if (pUnit->getDomainType() == DOMAIN_SEA)
			iScore += pPlot->countMatchingAdjacentPlots(DOMAIN_LAND, NO_PLAYER, pUnit->getOwner(), NO_PLAYER) * 7;

		if (!bIsInCityOrCitadel)
		{
			//try to go where our friends are
			int iFriendlyUnitsAdjacent = pPlot->GetNumFriendlyUnitsAdjacent(pUnit->getTeam(), NO_DOMAIN, true, pUnit);
			//don't go where our foes are
			int iEnemyUnitsAdjacent = pPlot->GetNumEnemyUnitsAdjacent(pUnit->getTeam(), pUnit->getDomainType());
			iScore += (iEnemyUnitsAdjacent - iFriendlyUnitsAdjacent) * 13;

			//use city distance as tiebreaker
			if (pUnit->getDomainType() != DOMAIN_SEA)
				iScore = iScore * 10 + iCityDistance;
			else
				// Naval units should try to go home to heal, even if it's considered dangerous
				iScore = iScore * 3 + iCityDistance;
		}

		//discourage water tiles for land units
		if (bWrongDomain)
			iScore += 250;

		if(bIsInCityOrCitadel)
		{
			aCityList.push_back( OptionWithScore<pair<CvPlot*, int>>(make_pair(pPlot, it->iMovesLeft),iScore) );
		}
		else if(bIsInCover) //mostly relevant for civilians
		{
			aCoverList.push_back( OptionWithScore<pair<CvPlot*, int>>(make_pair(pPlot, it->iMovesLeft),iScore) );
		}
		else if(bIsZeroDanger)
		{
			//if danger is zero, look at distance to closest owned city instead
			//idea: could also look at number of plots reachable from pPlot to avoid dead ends
			aZeroDangerList.push_back( OptionWithScore<pair<CvPlot*, int>>(make_pair(pPlot, it->iMovesLeft), bIsInTerritory ? -iCityDistance : -iCityDistance*2) );
		}
		else if(!bWouldEmbark || bAllowEmbark)
		{
			aDangerList.push_back( OptionWithScore<pair<CvPlot*, int>>(make_pair(pPlot, it->iMovesLeft),iScore) );
		}
	}

	//high scores are bad, we sort descending
	std::stable_sort(aCityList.begin(), aCityList.end());
	std::stable_sort(aCoverList.begin(), aCoverList.end());
	std::stable_sort(aZeroDangerList.begin(), aZeroDangerList.end());
	std::stable_sort(aDangerList.begin(), aDangerList.end());

	// Now that we've gathered up our lists of destinations, pick the most promising one
	if (aCityList.size()>0)
		return aCityList.back().option;
	else if (aCoverList.size() > 0)
	{
		pair<CvPlot*, int> pPlotMove = aCoverList.back().option;
		CvUnit* pDefender = pPlotMove.first->getBestDefender(pUnit->getOwner());
		if (pDefender && pDefender != pUnit)
		{
			//taking cover only works if the defender will not move away!
			//since we move civilians only after the combat units have moved it should be safe to pin the defender here (AI players only!)
			if (!pDefender->TurnProcessed() && !pDefender->isHuman(ISHUMAN_AI_UNITS))
			{
				TacticalAIHelpers::PerformRangedOpportunityAttack(pDefender, false);
				pDefender->PushMission(CvTypes::getMISSION_SKIP());
				pDefender->SetTurnProcessed(true);
			}
		}
		return pPlotMove;
	}
	else if (aZeroDangerList.size()>0)
		return aZeroDangerList.back().option;
	else if (aDangerList.size()>0)
		return aDangerList.back().option;

	return make_pair(static_cast<CvPlot*>(NULL), 0);
}

void CTacticalUnitArray::push_back(const CvTacticalUnit& unit)
{
	CheckDebugTrigger(unit.GetID());
	m_vec.push_back(unit);
}

bool TacticalAIHelpers::IsGoodPlotForStaging(CvPlayer* pPlayer, CvPlot* pCandidate, DomainTypes eDomain)
{
	if (!pPlayer || !pCandidate)
		return false;

	if (CvStacking::IsEnabled() ? !pCandidate->canPlaceCombatUnit(pPlayer->GetID()) : pCandidate->getBestDefender(pPlayer->GetID()) != NULL)
		return false;

	if (eDomain != NO_DOMAIN && pCandidate->getDomain() != eDomain)
		return false;

	int iCityDistance = pPlayer->GetCityDistancePathLength(pCandidate);
	if (iCityDistance>5)
		return false;

	if (pCandidate->getRouteType()!=NO_ROUTE)
		return false;

	int iFriendlyCombatUnitsAdjacent = 0;
	int iPassableNeighbors = 0;
	for (int iI = 0; iI < NUM_DIRECTION_TYPES; iI++)
	{
		CvPlot* pNeighbor = plotDirection(pCandidate->getX(), pCandidate->getY(), ((DirectionTypes)iI));
		if (!pNeighbor)
			continue;

		//don't want to provoke other players, stay away from their units
		if (pNeighbor->isNeutralUnit(pPlayer->GetID(),true,true,true) || pNeighbor->isEnemyUnit(pPlayer->GetID(),true,true,true))
			return false;

		//stay away from their borders as well
		if (pNeighbor->isOwned() && pNeighbor->getTeam() != pPlayer->getTeam())
			if (GET_PLAYER(pNeighbor->getOwner()).isMajorCiv())
				return false;

		if (pNeighbor->getBestDefender(pPlayer->GetID()) != NULL)
			iFriendlyCombatUnitsAdjacent++;

		if (eDomain == NO_DOMAIN || eDomain == pNeighbor->getDomain())
			if (!pNeighbor->isImpassable(pPlayer->getTeam()))
				iPassableNeighbors++;
	}

	//don't build a wall of units
	if (iFriendlyCombatUnitsAdjacent>3)
		return false;

	//don't move into dead ends
	if (iPassableNeighbors<3)
		return false;

	//we don't know the unit, so use a rough estimation ...
	if (pPlayer->GetPlotDanger(*pCandidate, false) > /*10*/ GD_INT_GET(NEUTRAL_HEAL_RATE))
		return false;

	return true;
}

bool TacticalAIHelpers::IsCloseToContestedBorder(CvPlayer* pPlayer, CvPlot* pPlot)
{
	bool bResult = false;

	for (int i = RING1_PLOTS; i < RING2_PLOTS; i++)
	{
		CvPlot* pTestPlot = iterateRingPlots(pPlot, i);
		if (pTestPlot && pPlayer->IsAtWarWith(pTestPlot->getOwner()) && pTestPlot->getDomain() == DOMAIN_LAND)
		{
			CvTacticalDominanceZone* pZone = pPlayer->GetTacticalAI()->GetTacticalAnalysisMap()->GetZoneByPlot(pTestPlot);
			if (pZone && pZone->GetOverallDominanceFlag() == TACTICAL_DOMINANCE_FRIENDLY)
				continue;

			bResult = true;
			break;
		}
	}

	return bResult;
}

pair<CvPlot*, int> TacticalAIHelpers::FindClosestSafePlotForHealing(CvUnit* pUnit, bool bConservative)
{
	if (!pUnit)
		return make_pair(static_cast<CvPlot*>(NULL), 0);

	//first see if the current plot is good
	int iCurrentHealRate = pUnit->ActualHealRate(pUnit->plot());
	if (pUnit->GetDanger() == 0 && iCurrentHealRate > 5 && !pUnit->isAlwaysHeal())
		return make_pair(pUnit->plot(), pUnit->getMoves());

	//check if we can outheal the damage
	if (iCurrentHealRate > 5 && iCurrentHealRate > pUnit->GetDanger() && !pUnit->isAlwaysHeal())
		return make_pair(pUnit->plot(), pUnit->getMoves());

	//doesn't get much safer than in a city
	//also garrisons should not run away!
	if (pUnit->plot()->isCity() && pUnit->getDomainType() == DOMAIN_LAND)
		return make_pair(pUnit->plot(), pUnit->getMoves());

	std::vector<OptionWithScore<pair<CvPlot*, int>>> vCandidates;
	ReachablePlots eligiblePlots = pUnit->GetAllPlotsInReachThisTurn(); //embarkation allowed for now, we sort it out below
	for (ReachablePlots::const_iterator it = eligiblePlots.begin(); it != eligiblePlots.end(); ++it)
	{
		CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);

		if (pPlot->isEnemyUnit(pUnit->getOwner(), true, true))
			continue;

		bool bPillage = (it->iMovesLeft > 0) && pUnit->shouldPillage(pPlot, false);
		//don't check movement, don't need to heal right now
		if (pUnit->getDomainType() == DOMAIN_LAND)
		{
			if (pUnit->ActualHealRate(pPlot, false) == 0)
				continue;

			//don't mess with (ranged) garrisons if enemies are around
			CvCity* pCity = pPlot->getPlotCity();
			if (pCity && pCity->HasGarrison() && pCity->isUnderSiege() && pCity->GetGarrisonedUnit()->IsCanAttackRanged() && pCity->GetGarrisonedUnit()->getDomainType() == DOMAIN_LAND)
				continue;
		}
		else
		{
			//naval units usually must pillage to heal ...
			if (!bPillage && pUnit->ActualHealRate(pPlot, false) == 0)
				continue;
		}

		//can we stay there?
		if (!pUnit->canMoveInto(*pPlot, CvUnit::MOVEFLAG_DESTINATION))
		{
			if (pUnit->canMoveInto(*pPlot, CvUnit::MOVEFLAG_DESTINATION | CvUnit::MOVEFLAG_IGNORE_STACKING_SELF))
			{
				//todo: we should maybe choose the target plot based on whether we can make a good swap?
				if (!pUnit->CanPushOutUnitHere(*pPlot))
					continue;
			}
			else
				continue;
		}

		int iDanger = min(pUnit->GetDanger(pPlot),10000); //handle INT_MAX for civilians
		int iHealRate = pUnit->ActualHealRate(pPlot, false);

		// a heal now is about as good as two heals next turn
		if (pPlot == pUnit->plot() && !pUnit->hasMoved() && !pUnit->isAlwaysHeal())
			iHealRate *= 2;

		//sometimes we want to ignore pillage health, it's a one-time effect and may lead into dead ends
		if (bPillage && !bConservative)
		{
			if (!pUnit->hasFreePillageMove())
				iHealRate = max(iHealRate, /*25*/ GD_INT_GET(PILLAGE_HEAL_AMOUNT));
			else
				iHealRate += /*25*/ GD_INT_GET(PILLAGE_HEAL_AMOUNT);
		}

		//make up a score function
		//don't try to go to heal in a plot where we will slowly die
		int iScore = iHealRate - iDanger;
		//is this safe enough?
		if (iScore > 0)
		{
			//tiebreaker
			int iCityDist = GET_PLAYER(pUnit->getOwner()).GetCityDistancePathLength(pPlot);
			if (iCityDist == INT_MAX)
				iCityDist = 0; // No cities (e.g. city-state lost capital) - distance irrelevant, use 0 to avoid overflow
			iScore -= plotDistance(pPlot->getX(), pPlot->getY(), pUnit->getX(), pUnit->getY()) * 2 - iCityDist;
			vCandidates.push_back(OptionWithScore<pair<CvPlot*, int>>(make_pair(pPlot, it->iMovesLeft), iScore));
		}
	}

	if (!vCandidates.empty())
	{
		std::stable_sort(vCandidates.begin(), vCandidates.end());
		//how to tell whether it's safe enough?
		return vCandidates.back().option;
	}

	return make_pair(static_cast<CvPlot*>(NULL), 0);
}

std::vector<CvPlot*> TacticalAIHelpers::GetPlotsForRangedAttack(const CvPlot* pTarget, const CvUnit* pUnit, int iRange, bool bCheckOccupied)
{
	std::vector<CvPlot*> vPlots;

	if (!pTarget || !pUnit)
		return vPlots;

	// Aircraft and special promotions make us ignore LOS
	bool bIgnoreLOS = pUnit->IsRangeAttackIgnoreLOS() || pUnit->getDomainType()==DOMAIN_AIR;
	// Can only bombard in domain? (used for Subs' torpedo attack)
	bool bOnlyInDomain = pUnit->getUnitInfo().IsRangeAttackOnlyInDomain();

	const vector<CvPlot*>& vCandidates = GC.getMap().GetPlotsAtRangeX(pTarget, iRange, false, !bIgnoreLOS);

	//filter and take only the half closer to origin
	CvPlot* pRefPlot = pUnit->plot();
	if(pRefPlot == NULL)
		return vPlots;

	int iRefDist = plotDistance(*pRefPlot,*pTarget);
	std::vector<SPlotWithScore> vIntermediate;
	for (size_t i=0; i<vCandidates.size(); i++)
	{
		if(vCandidates[i] == NULL)
			continue;

		int iDistance = plotDistance(*pRefPlot,*(vCandidates[i]));
		if (iDistance>iRefDist && iRefDist>iRange)
			continue;

		if (!vCandidates[i]->isRevealed(pUnit->getTeam()))
			continue;

		//this concerns not only embarked units but also ships in harbor!
		if (!pUnit->isNativeDomain(vCandidates[i]))
			continue;

		if (bCheckOccupied && vCandidates[i]!=pRefPlot && !pUnit->canMoveInto(*vCandidates[i], CvUnit::MOVEFLAG_DESTINATION))
			continue;

		if (bOnlyInDomain)
		{
			//subs can only attack within their (water) area or adjacent cities (VP only)
			if (pRefPlot->getLandmass() != vCandidates[i]->getLandmass())
			{
				if (!MOD_BALANCE_VP)
					continue;

				if (!vCandidates[i]->isCity())
					continue;

				if (!vCandidates[i]->getPlotCity()->HasAccessToLandmassOrOcean(pRefPlot->getLandmass()))
					continue;
			}
		}

		vIntermediate.push_back( SPlotWithScore(vCandidates[i],iDistance) );
	}

	//sort by increasing distance
	std::stable_sort(vIntermediate.begin(), vIntermediate.end());

	for (size_t i=0; i<vIntermediate.size(); i++)
		vPlots.push_back(vIntermediate[i].pPlot);

	return vPlots;
}

const CvUnit* TacticalAIHelpers::GetSimulatedGarrison(const CvCity* city, const vector<const CvUnit*>& candidates, const SUnitIDValueContainer& damage)
{
 if (!city)
  return NULL;
 const CvUnit* best = NULL;
 int bestContribution = 0;
 for (size_t i = 0; i < candidates.size(); ++i)
 {
  const CvUnit* unit = candidates[i];
  if (!unit || unit->getOwner() != city->getOwner() || !unit->CanGarrison() || unit->isCargo() || damage.GetValue(unit->GetID()) >= unit->GetCurrHitPoints())
   continue;
  int divisor = unit->getDomainType() == DOMAIN_LAND ? GD_INT_GET(CITY_STRENGTH_LAND_UNIT_DIVISOR) : GD_INT_GET(CITY_STRENGTH_NAVAL_UNIT_DIVISOR);
  int contribution = max(unit->GetBaseCombatStrength(), unit->GetBaseRangedCombatStrength()) * 100 / max(1, divisor);
  if (!best || contribution > bestContribution || (contribution == bestContribution && unit == city->GetGarrisonedUnit()))
  { best = unit; bestContribution = contribution; }
 }
 return best;
}

//helper function for city threat calculation
int TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(const CvCity* pCity, const CvUnit* pAttacker, const CvPlot* pAttackerPlot, int& iAttackerDamage,
	int& iGarrisonDamage, bool bIgnoreUnitAdjacencyBoni, int iExtraSelfDamage, int iExtraCityDamage, int iExtraGarrisonDamage, bool bQuickAndDirty, bool bOverrideGarrison, const CvUnit* pGarrisonOverride)
{
	CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_CITY_SIMULATION); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
	if (!pAttacker || !pCity || pAttacker->isDelayedDeath() || pAttacker->IsDead())
		return 0;
		
	int iDamage = 0;
	const CvUnit* pGarrison = bOverrideGarrison ? pGarrisonOverride : pCity->GetGarrisonedUnit();
	int iGarrisonMaxHP = (pGarrison != NULL && pGarrison->GetMaxHitPoints() > pGarrison->getDamage() + iExtraGarrisonDamage) ? pGarrison->GetMaxHitPoints() : 0;
	if (pAttacker->IsCanAttackRanged())
	{
		if (pAttacker->getDomainType() == DOMAIN_AIR)
			iDamage = pAttacker->GetAirCombatDamage(NULL, pCity, iGarrisonMaxHP, iGarrisonDamage, false, iExtraSelfDamage, iExtraCityDamage, NULL, pAttackerPlot, bQuickAndDirty, bOverrideGarrison, pGarrison);
		else
			iDamage = pAttacker->GetRangeCombatDamage(NULL, pCity, iGarrisonMaxHP, iGarrisonDamage, false, iExtraSelfDamage, iExtraCityDamage, NULL, pAttackerPlot, bIgnoreUnitAdjacencyBoni, bQuickAndDirty, bOverrideGarrison, pGarrison);

		iAttackerDamage = 0; //what about interceptions?
	}
	else
	{
		//just assume the unit can attack from its current location - modifiers might be different, but thats acceptable
		iDamage = pAttacker->getMeleeCombatDamageCity(
			pAttacker->GetMaxAttackStrength(pAttackerPlot, pCity->plot(), NULL, bIgnoreUnitAdjacencyBoni, bQuickAndDirty),
			pCity, //not affected by assumed extra damage
			iAttackerDamage, iGarrisonMaxHP, iGarrisonDamage, false, iExtraSelfDamage, iExtraCityDamage, pGarrisonOverride);
	}

	return iDamage;
}

//helper function for unit threat calculation
int TacticalAIHelpers::GetSimulatedDamageFromAttackOnUnit(const CvUnit* pDefender, const CvUnit* pAttacker, 
				const CvPlot* pDefenderPlot, const CvPlot* pAttackerPlot, int& iAttackerDamage, 
				bool bIgnoreUnitAdjacencyBoni, int iExtraSelfDamage, int iExtraDefenderDamage, bool bQuickAndDirty, bool bNextTurnThreat)
{
	CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_UNIT_SIMULATION); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
	if (!pAttacker || !pDefender || pDefender->isDelayedDeath() || pDefender->IsDead() || pAttacker->isDelayedDeath() || pAttacker->IsDead())
		return 0;
		
	int iDamage = 0;
	int iUnusedReferenceVariable = 0;
	if (pAttacker->IsCanAttackRanged())
	{
		if (pAttacker->getDomainType() == DOMAIN_AIR)
		{
			iAttackerDamage = 0;
			if (pAttacker->GetCurrHitPoints() - iExtraSelfDamage > 0)
			{
				const CvPlot* pTargetPlot = pDefenderPlot ? pDefenderPlot : pDefender->plot();
				int iStrikeChance = 10000;
				int iInterceptionDamage = 0;
				// Quick mode returns conditional/raw strike damage: stack danger and
				// collateral forecasts apply their own interception probability.
				const CvUnit* pInterceptor = bQuickAndDirty || !pTargetPlot ? NULL
					: pTargetPlot->GetBestInterceptor(pAttacker->getOwner(), pAttacker, false, true);
				if (pInterceptor)
				{
					const int iExtraInterceptorDamage = pInterceptor == pDefender ? max(0, iExtraDefenderDamage) : 0;
					const int iInterceptorHP = max(0, pInterceptor->GetCurrHitPoints() - iExtraInterceptorDamage);
					if (iInterceptorHP > 0)
					{
						// Match the live interception damage leaves, including prospective
						// bomber damage. Never mutate interception attempts while scoring.
						const int iBomberStrength = pAttacker->GetMaxRangedCombatStrength(pInterceptor, NULL, false,
							pTargetPlot, pTargetPlot, false, false, iExtraSelfDamage, iExtraInterceptorDamage);
						int iInterceptorStrength = pInterceptor->getDomainType() == DOMAIN_AIR
							? pInterceptor->GetMaxRangedCombatStrength(pAttacker, NULL, true, pTargetPlot, pTargetPlot,
								false, false, iExtraInterceptorDamage, iExtraSelfDamage)
							: pInterceptor->GetMaxAttackStrength(NULL, NULL, pAttacker, false, false,
								iExtraInterceptorDamage, iExtraSelfDamage);
						iInterceptorStrength = static_cast<int>(static_cast<int64>(iInterceptorStrength)
							* (100 + pInterceptor->GetInterceptionCombatModifier()) / 100);
						iInterceptionDamage = CvUnitCombat::DoDamageMath(iInterceptorStrength, iBomberStrength,
							GD_INT_GET(INTERCEPTION_SAME_STRENGTH_MIN_DAMAGE), GD_INT_GET(INTERCEPTION_SAME_STRENGTH_POSSIBLE_EXTRA_DAMAGE),
							false, CvSeeder(), pAttacker->GetInterceptionDefenseDamageModifier()) / 100;
						// A positive interception aborts bombing even if the bomber survives.
						// This uses nominal mean damage, not an exact random-outcome tree.
						if (iInterceptionDamage > 0)
						{
							const int iInterceptProbability = min(100, max(0, static_cast<int>(static_cast<int64>(pInterceptor->getInterceptChance())
								* iInterceptorHP / max(1, pInterceptor->GetMaxHitPoints()))));
							const int iEvasionProbability = min(100, max(0, pAttacker->evasionProbability()));
							iStrikeChance -= iInterceptProbability * (100 - iEvasionProbability);
						}
					}
				}
				const int iConditionalDamage = pAttacker->GetAirCombatDamage(pDefender, NULL, 0, iUnusedReferenceVariable,
					false, iExtraSelfDamage, iExtraDefenderDamage, pTargetPlot, pAttackerPlot, bQuickAndDirty);
				const int iConditionalRetaliation = max(0, pDefender->GetAirStrikeDefenseDamage(pAttacker, false, pTargetPlot));
				// Mutually exclusive outcomes. Round our damage down and incoming
				// damage up for conservative attack valuation; 0/100% stay exact.
				iDamage = static_cast<int>(static_cast<int64>(max(0, iConditionalDamage)) * iStrikeChance / 10000);
				iAttackerDamage = static_cast<int>((static_cast<int64>(iInterceptionDamage) * (10000 - iStrikeChance)
					+ static_cast<int64>(iConditionalRetaliation) * iStrikeChance + 9999) / 10000);
			}
		}
		else
		{
			// Naval units can't fire from cities
			const CvPlot* pFromPlot = pAttackerPlot ? pAttackerPlot : pAttacker->plot();
			if (pAttacker->getDomainType() == DOMAIN_SEA && pFromPlot->isCity())
				return 0;

			iDamage += pAttacker->GetRangeCombatDamage(pDefender, NULL, 0, iUnusedReferenceVariable, false, iExtraSelfDamage, iExtraDefenderDamage,
							pDefenderPlot, pAttackerPlot, bIgnoreUnitAdjacencyBoni, bQuickAndDirty);
			iDamage += (pAttacker->hasMoved() || pAttacker->plot() != pAttackerPlot) ? 0 : pAttacker->GetTileDamageIfNotMoved();
			iAttackerDamage = 0;
		}
	}
	else
	{
		// Tactical strikes use current attack readiness. Danger projects the next
		// enemy turn: its reach map already supplies movement/visibility, and an
		// exhausted unit regains moves and attacks before delivering that threat.
		if (pDefenderPlot)
		{
			if (!bNextTurnThreat)
			{
				if (!pAttacker->canMoveOrAttackInto(*pDefenderPlot))
					return 0;
			}
			else
			{
				const bool enemyCity = pDefenderPlot->isEnemyCity(*pAttacker);
				const TeamTypes plotTeam = pAttacker->isHuman(ISHUMAN_AI_UNITS)
					? pDefenderPlot->getRevealedTeam(pAttacker->getTeam()) : pDefenderPlot->getTeam();
				if (!pAttacker->IsCanAttackWithMove() || !GET_TEAM(pAttacker->getTeam()).isAtWar(pDefender->getTeam()) ||
					(pAttacker->IsCityAttackSupport() && !enemyCity) ||
					(!pAttacker->isNativeDomain(pDefenderPlot) && !enemyCity) ||
					(pDefenderPlot->isCity() && (!enemyCity || pAttacker->isNoCapture())) ||
					!pAttacker->canEnterTerritory(plotTeam, true) ||
					!pAttacker->canEnterTerrain(*pDefenderPlot, CvUnit::MOVEFLAG_ATTACK | CvUnit::MOVEFLAG_DESTINATION))
					return 0;
				if (MOD_EVENTS_CAN_MOVE_INTO && pAttacker->getUnitInfo().IsSendCanMoveIntoEvent())
					if (GAMEEVENTINVOKE_TESTALL(GAMEEVENT_CanMoveInto, pAttacker->getOwner(), pAttacker->GetID(),
						pDefenderPlot->getX(), pDefenderPlot->getY(), true, false) == GAMEEVENTRETURN_FALSE)
						return 0;
			}
		}

		if (pAttacker->isRangedSupportFire())
			iDamage += pAttacker->GetRangeCombatDamage(pDefender, NULL, 0, iUnusedReferenceVariable, false, iExtraSelfDamage, iExtraDefenderDamage,
							pDefenderPlot, pAttackerPlot, bIgnoreUnitAdjacencyBoni, bQuickAndDirty);

		// no melee attack if the RangedSupportFire has killed the defender
		if (pDefender->GetCurrHitPoints() > iDamage + iExtraDefenderDamage)
		{
			int iAttackerStrength = pAttacker->GetMaxAttackStrength(pAttackerPlot, pDefenderPlot, pDefender, bIgnoreUnitAdjacencyBoni, bQuickAndDirty, iExtraSelfDamage, iExtraDefenderDamage + iDamage);
			//do not override defender flanking/general bonus (it is known during combat simulation)
			int iDefenderStrength = pDefender->GetMaxDefenseStrength(pDefenderPlot, pAttacker, pAttackerPlot, false, bQuickAndDirty, iExtraDefenderDamage + iDamage);

			//just assume the unit can attack from its current location - modifiers might be different, but thats acceptable
			iDamage += pAttacker->getMeleeCombatDamage(
				iAttackerStrength,
				iDefenderStrength,
				iAttackerDamage,
				false, pDefender,
				iExtraSelfDamage,
				iExtraDefenderDamage + iDamage);

			iDamage += (pAttacker->hasMoved() || pAttacker->plot() != pAttackerPlot) ? 0 : pAttacker->GetTileDamageIfNotMoved();
		}
	}

	return iDamage;
}

bool TacticalAIHelpers::KillLoneEnemyIfPossible(CvUnit* pOurUnit, CvUnit* pEnemyUnit)
{
	if (!pOurUnit || !pEnemyUnit || pEnemyUnit->isDelayedDeath())
		return false;

	//aircraft are different
	if (pOurUnit->getDomainType()==DOMAIN_AIR || pEnemyUnit->getDomainType()==DOMAIN_AIR)
		return false;

 // An incoming target pointer may name an exposed unit in a larger stack.
 // Re-select the unit that this particular attacker will actually fight.
 if (CvStacking::IsEnabled())
 {
  pEnemyUnit = pEnemyUnit->plot()->getBestDefender(NO_PLAYER, pOurUnit->getOwner(), pOurUnit, true);
  if (!pEnemyUnit)
   return false;
 }

	//see how the attack would go
	int iDamageDealt = 0;
	int iDamageReceived = 0;
	iDamageDealt = TacticalAIHelpers::GetSimulatedDamageFromAttackOnUnit(pEnemyUnit, pOurUnit, pEnemyUnit->plot(), pOurUnit->plot(), iDamageReceived);

	//is it worth it? (take into account some randomness ...)
	if ( iDamageDealt-3 > pEnemyUnit->GetCurrHitPoints() && pOurUnit->GetCurrHitPoints()-iDamageReceived > 23 )
	{
		if (pOurUnit->IsCanAttackRanged())
		{
			//can we attack directly
			if (pOurUnit->canRangeStrikeAt(pEnemyUnit->getX(),pEnemyUnit->getY()))
			{
				pOurUnit->PushMission(CvTypes::getMISSION_RANGE_ATTACK(),pEnemyUnit->getX(),pEnemyUnit->getY());
				return true;
			}
			else if (pOurUnit->canRangeStrike())
			{
				//need to move and shoot
				bool bIgnoreLOS = pOurUnit->IsRangeAttackIgnoreLOS();
				const vector<CvPlot*>& vAttackPlots = GC.getMap().GetPlotsAtRangeX(pEnemyUnit->plot(), pOurUnit->GetRange(), false, !bIgnoreLOS);
				for (std::vector<CvPlot*>::const_iterator it = vAttackPlots.begin(); it != vAttackPlots.end(); ++it)
				{
					if (pOurUnit->TurnsToReachTarget(*it, CvUnit::MOVEFLAG_TURN_END_IS_NEXT_TURN, 1) == 0 && pOurUnit->canEverRangeStrikeAt(pEnemyUnit->getX(), pEnemyUnit->getY(), *it, false))
					{
						// PushMission might invalidate the iterator because of the shared buffer used in GetPlotsAtRangeX
						CvPlot* pPlot = *it;
						pOurUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pPlot->getX(), pPlot->getY(), CvUnit::MOVEFLAG_IGNORE_DANGER);
						//sometimes the unit takes an unexpected path
						if (pOurUnit->atPlot(*pPlot))
							pOurUnit->PushMission(CvTypes::getMISSION_RANGE_ATTACK(), pEnemyUnit->getX(), pEnemyUnit->getY());
						else
							OutputDebugString("pathfinding issue ...\n");
						return true;
					}
				}
			}
		}
		else //melee
		{
			if (pOurUnit->TurnsToReachTarget(pEnemyUnit->plot(),0,1)==0)
			{
				pOurUnit->PushMission(CvTypes::getMISSION_MOVE_TO(),pEnemyUnit->getX(),pEnemyUnit->getY());
				return true;
			}
		}
	}

	return false;
}

bool TacticalAIHelpers::IsSuicideMeleeAttack(const CvUnit * pAttacker, CvPlot * pTarget)
{
	//todo: add special code for air attacks!
	if (!pAttacker || !pTarget || pAttacker->IsCanAttackRanged() || pAttacker->getDomainType()==DOMAIN_AIR)
		return false;

	int iDamageReceived = 0;
	int iGarrisonDamage = 0;

	//if we're not adjacent we don't know the plot the attacker will use in the end
	CvPlot* pAttackerPlot = NULL;
	if (pAttacker->plot()->isAdjacent(pTarget))
		pAttackerPlot = pAttacker->plot();

	//unit attack or city attack?
	if (pTarget->isCity())
	{
		TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(pTarget->getPlotCity(), pAttacker, pAttackerPlot, iDamageReceived, iGarrisonDamage);
	}
	else
	{
		CvUnit* pDefender = pTarget->getBestDefender(NO_PLAYER, pAttacker->getOwner(), pAttacker);
		if (pDefender)
			TacticalAIHelpers::GetSimulatedDamageFromAttackOnUnit(pDefender, pAttacker, pTarget, pAttackerPlot, iDamageReceived);
		else
			return false;
	}

	//add some margin for randomness
	return (iDamageReceived+3 >= pAttacker->GetCurrHitPoints());
}

bool TacticalAIHelpers::CanKillTarget(const CvUnit* pAttacker, CvPlot* pTarget)
{
	if (!pAttacker || !pTarget)
		return false;

	CvCity* pTargetCity = pTarget->getPlotCity();
	if (pTargetCity)
	{
		if (!pAttacker->isEnemy(pTargetCity->getTeam()))
			return false;

		//shortcut
		if (pTargetCity->isInDangerOfFalling(true))
			return true;

		//see how an attack would go just in case
		int iDamageDealt = 0;
		int iDamageReceived = 0;
		int iGarrisonDamage = 0;
		iDamageDealt = TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(pTargetCity, pAttacker, pAttacker->plot(), iDamageReceived, iGarrisonDamage, true, 0, true);

		int iNumMelee = pTarget->GetNumFriendlyUnitsAdjacent(pAttacker->getTeam(), NO_DOMAIN, false, pAttacker);
		if (iNumMelee > 0)
		{
			// assume each melee unit does 1/4 of our damage
			iDamageDealt += iNumMelee * iDamageDealt / 4;
		}

		//ranged units can't capture themselves so we check for an adjacent melee unit
		if (pAttacker->IsCanAttackRanged())
		{
			if (iNumMelee == 0)
				return false;
		}
		else
		{
			//some melee units cannot capture either
			if (pAttacker->isNoCapture() && iNumMelee == 0)
				return false;
		}

		return iDamageDealt + pTargetCity->getDamage() >= pTargetCity->GetMaxHitPoints();
	}

	CvUnit* pDefender = pTarget->getBestDefender(NO_PLAYER, pAttacker->getOwner(), pAttacker, true);
	if (pDefender)
	{
		//see how the attack would go
		int iDamageDealt = 0;
		int iDamageReceived = 0;
		iDamageDealt = TacticalAIHelpers::GetSimulatedDamageFromAttackOnUnit(pDefender, pAttacker, pDefender->plot(), pAttacker->plot(), iDamageReceived, true, 0, true);
		//no suicide attacks ...
		return iDamageDealt >= pDefender->GetCurrHitPoints() && (iDamageReceived == 0 || iDamageReceived < pAttacker->GetCurrHitPoints()-3);
	}

	return false;
}

vector<pair<CvPlot*, bool>> TacticalAIHelpers::GetTargetsInRange(const CvUnit * pUnit, bool bMustBeAbleToKill, bool bIncludeCivilians)
{
	vector<pair<CvPlot*, bool>> result;
	if (!pUnit)
		return result;

	ReachablePlots reachablePlots = pUnit->GetAllPlotsInReachThisTurn(true, true, false);
	for (ReachablePlots::const_iterator it = reachablePlots.begin(); it != reachablePlots.end(); ++it)
	{
		CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);

		//only melee attacks here - ranged attacks are checked below
		bool bMilitaryTarget = (pPlot->isEnemyCity(*pUnit) && !pUnit->isNoCapture()) || pPlot->isEnemyUnit(pUnit->getOwner(), true, true);
		if (bMilitaryTarget && !pUnit->IsCanAttackRanged())
		{
			bool bCanKill = CanKillTarget(pUnit,pPlot);
			if (bMustBeAbleToKill && !bCanKill)
				continue;

			result.push_back( make_pair(pPlot,bCanKill) );
		}
		else if (bIncludeCivilians && pPlot->isEnemyUnit(pUnit->getOwner(), false, true))
			//we know the civilian is unescorted!
			result.push_back(make_pair(pPlot, true));
		else if (pPlot->getImprovementType() == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT))
			//unoccupied barb camp?
			result.push_back(make_pair(pPlot, true));
	}

	if (pUnit->IsCanAttackRanged())
	{
		//for ranged every tile we can enter with movement left is a base for attack
		const vector<int> attackableTiles = TacticalAIHelpers::GetPlotsUnderRangedAttackFrom(pUnit,reachablePlots,true,false);
		for (vector<int>::const_iterator attackTile=attackableTiles.begin(); attackTile!=attackableTiles.end(); ++attackTile)
		{
			CvPlot* pAttackTile = GC.getMap().plotByIndexUnchecked(*attackTile);
			bool bCanKill = CanKillTarget(pUnit,pAttackTile);

			if (bMustBeAbleToKill && !bCanKill)
				continue;

			result.push_back(make_pair(pAttackTile, bCanKill));
		}
	}

	return result;
}

pair<int, int> TacticalAIHelpers::EstimateLocalUnitPower(const ReachablePlots& plotsToCheck, TeamTypes eTeamA, TeamTypes eTeamB, bool bMustBeVisibleToBoth)
{
	if (plotsToCheck.empty())
		return make_pair(0, 0);

	int iTeamAPower = 0;
	int iTeamBPower = 0;

	for (ReachablePlots::const_iterator it = plotsToCheck.begin(); it != plotsToCheck.end(); ++it)
	{
		CvPlot* pLoopPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);
		ASSERT(pLoopPlot != NULL, "plotByIndexUnchecked returned null - invalid plot index");

		if (bMustBeVisibleToBoth && !(pLoopPlot->isVisible(eTeamA) && pLoopPlot->isVisible(eTeamB)))
			continue;

		// If there are Units here, loop through them
		if (pLoopPlot->getNumUnits() > 0)
		{
			IDInfo* pUnitNode = pLoopPlot->headUnitNode();
			while (pUnitNode != NULL)
			{
				CvUnit* pLoopUnit = ::GetPlayerUnit(*pUnitNode);
				pUnitNode = pLoopPlot->nextUnitNode(pUnitNode);

				// Is a combat unit
				if (pLoopUnit && (pLoopUnit->IsCombatUnit() || pLoopUnit->getDomainType() == DOMAIN_AIR))
				{
					int iScale = pLoopUnit->isNativeDomain(pLoopPlot) ? 1 : 2;

					if (pLoopUnit->getTeam() == eTeamA)
						iTeamAPower += pLoopUnit->GetPower() / iScale;
					if (pLoopUnit->getTeam() == eTeamB)
						iTeamBPower += pLoopUnit->GetPower() / iScale;
				}
			}
		}
	}

	return pair<int, int>(iTeamAPower,iTeamBPower);
}

//could we see additional plot when the unit moves to the test plot?
int TacticalAIHelpers::CountAdditionallyVisiblePlots(CvUnit * pUnit, CvPlot * pTestPlot)
{
	if (!pUnit || !pTestPlot)
		return 0;

	int iCount = 0;
	for (int iRange = 2; iRange <= pUnit->visibilityRange(); iRange++)
	{
		const vector<CvPlot*>& vPlots = GC.getMap().GetPlotsAtRangeX(pTestPlot, iRange, true, true);
		for (size_t i = 0; i < vPlots.size(); i++)
			if (vPlots[i] && !vPlots[i]->isVisible(pUnit->getTeam())) //we already know that would have line of sight
				iCount++;
	}
	
	return iCount;
}

//convenience
bool isCombatUnit(eUnitMovementStrategy eMoveType) { return eMoveType == MS_FIRSTLINE || eMoveType == MS_SECONDLINE || eMoveType == MS_THIRDLINE; }
bool isEmbarkedUnit(eUnitMovementStrategy eMoveType) { return eMoveType == MS_EMBARKED; }
bool isSupportUnit(eUnitMovementStrategy eMoveType) { return eMoveType == MS_SUPPORT; }

//Unbelievable bad logic but taken like this from CvUnitCombat
bool AttackEndsTurn(const CvUnit* pUnit, int iNumAttacksLeft)
{
	return !pUnit->canMoveAfterAttacking() && !pUnit->isRangedSupportFire() && iNumAttacksLeft<2;
}

static int NumAttacksForUnit(int iMovesLeft, int iMaxAttacks, bool bFreeAttackMoves)
{
	return bFreeAttackMoves ? max(0, iMaxAttacks) : max(0, min( (iMovesLeft+GD_INT_GET(MOVE_DENOMINATOR)-1)/GD_INT_GET(MOVE_DENOMINATOR), iMaxAttacks ));
}

CvTacticalPlot::eTactPlotDomain DomainForUnit(const CvUnit* pUnit)
{
	if (!pUnit)
		return CvTacticalPlot::TD_BOTH;

	switch (pUnit->getDomainType())
	{
	case DOMAIN_LAND:
		return CvTacticalPlot::TD_LAND;
	case DOMAIN_SEA:
		return CvTacticalPlot::TD_SEA;
	default:
		return CvTacticalPlot::TD_BOTH;
	}
}

void CDangerCache::clear()
{
	dangerStats.clear();
}

void CDangerCache::storeDanger(int iDefenderId, int iDefenderPlot, int iPrevDamage, const SUnitIDValueContainer& unitDamageDealt, int iDanger, size_t iStackHash)
{
	DefendKey key;
	key.iDefenderId = iDefenderId;
	key.iPlotId = iDefenderPlot;
	key.iPrevDamage = iPrevDamage;
	key.iDamageHash = unitDamageDealt.GetHash();
	key.iStackHash = iStackHash;

	dangerStats[key] = iDanger;
}

bool CDangerCache::findDanger(int iDefenderId, int iDefenderPlot, int iPrevDamage, const SUnitIDValueContainer& unitDamageDealt, int& iDanger, size_t iStackHash) const
{
	DefendKey key;
	key.iDefenderId = iDefenderId;
	key.iPlotId = iDefenderPlot;
	key.iPrevDamage = iPrevDamage;
	key.iDamageHash = unitDamageDealt.GetHash();
	key.iStackHash = iStackHash;

	std::tr1::unordered_map<DefendKey, int, DefendKeyHash>::const_iterator it =
		dangerStats.find(key);

	if (it != dangerStats.end())
	{
		iDanger = it->second;
		gDangerCacheHit++;
		return true;
	}

	iDanger = 0;
	gDangerCacheMiss++;
	return false;
}

void CAttackCache::clear()
{
	attackStats.clear();
}

void CAttackCache::storeAttack(int iAttackerId, int iAttackerPlot, int iDefenderId, int iGarrisonId, int iPrevSelfDamage, int iPrevUnitDamage, int iPrevCityDamage, int iUnitDamageDealt, int iCityDamageDealt, int iDamageTaken)
{
	AttackKey key;
	key.iAttackerId = iAttackerId;
	key.iAttackerPlot = iAttackerPlot;
	key.iDefenderId = iDefenderId;
	key.iGarrisonId = iGarrisonId;
	key.iPrevSelfDamage = iPrevSelfDamage;
	key.iPrevUnitDamage = iPrevUnitDamage;
	key.iPrevCityDamage = iPrevCityDamage;

	std::tr1::unordered_map<AttackKey, vector<int>, AttackKeyHash>::iterator it =
		attackStats.find(key);

	if (it != attackStats.end())
	{
		it->second[0] = iUnitDamageDealt;
		it->second[1] = iCityDamageDealt;
		it->second[2] = iDamageTaken;
	}
	else
	{
		vector<int> newValue(3);
		newValue[0] = iUnitDamageDealt;
		newValue[1] = iCityDamageDealt;
		newValue[2] = iDamageTaken;
		attackStats[key] = newValue;
	}
}

bool CAttackCache::findAttack(int iAttackerId, int iAttackerPlot, int iDefenderId, int iGarrisonId, int iPrevSelfDamage, int iPrevUnitDamage, int iPrevCityDamage, int& iUnitDamageDealt, int& iCityDamageDealt, int& iDamageTaken) const
{
	AttackKey key;
	key.iAttackerId = iAttackerId;
	key.iAttackerPlot = iAttackerPlot;
	key.iDefenderId = iDefenderId;
	key.iGarrisonId = iGarrisonId;
	key.iPrevSelfDamage = iPrevSelfDamage;
	key.iPrevUnitDamage = iPrevUnitDamage;
	key.iPrevCityDamage = iPrevCityDamage;

	std::tr1::unordered_map<AttackKey, vector<int>, AttackKeyHash>::const_iterator it =
		attackStats.find(key);

	if (it != attackStats.end())
	{
		iUnitDamageDealt = it->second[0];
		iCityDamageDealt = it->second[1];
		iDamageTaken = it->second[2];
		gAttackCacheHit++;
		return true;
	}

	iUnitDamageDealt = 0;
	iCityDamageDealt = 0;
	iDamageTaken = 0;
	gAttackCacheMiss++;
	return false;
}

const ReachablePlots& CvBasePosition::getReachablePlotsForUnit(const SUnitStats& unit) const
{
	static ReachablePlots emptyResult;

	SPathFinderStartPos key(unit, freedPlots.read(), SPathFinderStartPos::LookupOnly());
	TCachedMovePlots::const_iterator result = gReachablePlotsLookup.find(key);
	if (result != gReachablePlotsLookup.end())
		return result->second;

	return emptyResult;
}

//do we have to stop now
bool CvBasePosition::isExhausted() const
{
	return availableUnits.read().empty();
}

bool CvBasePosition::unitHasAssignmentOfType(int iUnitID, eUnitAssignmentType assignmentType) const
{
	const vector<STacticalAssignment>& assignedMoves_r = assignedMoves.read();
	for (size_t i = nFirstInterestingAssignment; i < assignedMoves_r.size(); i++)
	{
		const STacticalAssignment& a = assignedMoves_r[i];
		if (a.iUnitID == iUnitID && a.eAssignmentType == assignmentType)
			return true;
	}

	return false;
}

bool CvBasePosition::plotHasAssignmentOfType(int iToPlotIndex, eUnitAssignmentType assignmentType) const
{
	const vector<STacticalAssignment>& assignedMoves_r = assignedMoves.read();
	for (size_t i = nFirstInterestingAssignment; i < assignedMoves_r.size(); i++)
	{
		const STacticalAssignment& a = assignedMoves_r[i];
		if (a.iToPlotIndex == iToPlotIndex && a.eAssignmentType == assignmentType)
			return true;
	}

	return false;
}

bool CvBasePosition::lastAssignmentIsAfterRestart(int iUnitID) const
{
	bool bHaveRestart = false;
	const vector<STacticalAssignment>& assignedMoves_r = assignedMoves.read();
	for (size_t i = nFirstInterestingAssignment; i < assignedMoves_r.size(); i++)
	{
		const STacticalAssignment& a = assignedMoves_r[i];
		if (a.eAssignmentType == A_RESTART)
		{
			bHaveRestart = true;
			continue;
		}

		if (bHaveRestart && a.iUnitID == iUnitID && a.eAssignmentType != A_FINISH)
			return true;
	}

	return false;
}

const SUnitStats* CvBasePosition::getAvailableUnitStats(int iUnitID) const
{
	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	for (vector<SUnitStats>::const_iterator it = availableUnits_r.begin(); it != availableUnits_r.end(); ++it)
		if (it->iUnitID == iUnitID)
			return &(*it);

	return NULL;
}

const SUnitStats* CvBasePosition::GetUnitStats(int iUnitID) const
{
	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	for (vector<SUnitStats>::const_iterator it = availableUnits_r.begin(); it != availableUnits_r.end(); ++it)
		if (it->iUnitID == iUnitID)
			return &(*it);

	const vector<SUnitStats>& notQuiteFinishedUnits_r = notQuiteFinishedUnits.read();
	for (vector<SUnitStats>::const_iterator it = notQuiteFinishedUnits_r.begin(); it != notQuiteFinishedUnits_r.end(); ++it)
		if (it->iUnitID == iUnitID)
			return &(*it);

	const vector<SUnitStats>& finishedUnits_r = finishedUnits.read();
	for (vector<SUnitStats>::const_iterator it = finishedUnits_r.begin(); it != finishedUnits_r.end(); ++it)
		if (it->iUnitID == iUnitID)
			return &(*it);

	return NULL;
}

const STacticalAssignment* CvBasePosition::getInitialAssignment(int iUnitID) const
{
	const vector<STacticalAssignment>& assignedMoves_r = assignedMoves.read();
	for (vector<STacticalAssignment>::const_iterator it = assignedMoves_r.begin(); it != assignedMoves_r.end(); ++it)
		if (it->iUnitID == iUnitID && it->eAssignmentType == A_INITIAL)
			return &(*it);

	return NULL;
}

STacticalAssignment* CvBasePosition::getInitialAssignmentMutable(int iUnitID)
{
	vector<STacticalAssignment>& assignedMoves_w = assignedMoves.write();
	for (vector<STacticalAssignment>::iterator it = assignedMoves_w.begin(); it != assignedMoves_w.end(); ++it)
		if (it->iUnitID == iUnitID && it->eAssignmentType == A_INITIAL)
			return &(*it);

	return NULL;
}

const STacticalAssignment* CvBasePosition::getLatestMoveAssignment(int iUnitID) const
{
	const vector<STacticalAssignment>& assignedMoves_r = assignedMoves.read();
	for (size_t i = assignedMoves_r.size() - 1; i >= nFirstInterestingAssignment; i--)
		if (assignedMoves_r[i].iUnitID == iUnitID)
		{
			eUnitAssignmentType eAssignment = assignedMoves_r[i].eAssignmentType;
			if (eAssignment == A_MOVE || eAssignment == A_MOVE_SWAP || eAssignment == A_CAPTURE || eAssignment == A_MOVE_FORCED
				|| eAssignment == A_MOVE_SWAP_REVERSE || eAssignment == A_MOVE_DOUBLE || eAssignment == A_MELEEKILL)
				return &(assignedMoves_r[i]);
		}

	return NULL;
}

const STacticalAssignment* CvBasePosition::getLatestAssignment(int iUnitID) const
{
	const vector<STacticalAssignment>& assignedMoves_r = assignedMoves.read();
	for (vector<STacticalAssignment>::const_reverse_iterator it = assignedMoves_r.rbegin(); it != assignedMoves_r.rend(); ++it)
		if (it->iUnitID == iUnitID)
			return &(*it);

	return NULL;
}

STacticalAssignment* CvBasePosition::getLatestAssignmentMutable(int iUnitID)
{
	vector<STacticalAssignment>& assignedMoves_w = assignedMoves.write();
	for (vector<STacticalAssignment>::reverse_iterator it = assignedMoves_w.rbegin(); it != assignedMoves_w.rend(); ++it)
		if (it->iUnitID == iUnitID)
			return &(*it);

	return NULL;
}

//try to detect simple permutations in the unit assigments which result in equivalent results
static bool positionIsEquivalent(const CvBasePosition* ref, const CvBasePosition* other)
{
	//self comparison is false by definition!
	if (ref == other)
		return false;

	//"ref" is the new position we are evaluating. the "other" may already have finish moves tacked on, so size may be larger!
	if (ref->GetNumAssignments() > other->GetNumAssignments())
		return false;

	//now check the scores (ignoring any extra moves in other)
	int iRefScore = 0;
	int iOtherScore = 0;
	for (size_t i = ref->getFirstInterestingAssignment(); i < ref->GetNumAssignments(); i++)
	{
		iRefScore += ref->GetAssignment(i).Score();
		iOtherScore += other->GetAssignment(i).Score();
	}
	if (iRefScore != iOtherScore)
		return false;

	//now check for simple (A.B -> B.A) and less simple (A.B.C -> C.A.B | B.C.A), (A.B.C.D -> D.A.B.C | C.D.A.B | B.C.D.A ) permutations
	size_t A = INT_MAX;
	size_t B = INT_MAX;
	size_t C = INT_MAX;
	size_t D = INT_MAX;
	bool mismatch = false;
	//the "other" may have more moves assigned but they should all be of type FINISH ...
	//for performance do the iteration in reverse; we expect the differences at the end
	for (size_t cursor = ref->GetNumAssignments(); cursor > ref->getFirstInterestingAssignment(); )
	{
		const size_t i = --cursor;
		//ignore matching elements
		if (ref->GetAssignment(i) == other->GetAssignment(i))
			continue;

		//remember where the differences occurred
		if (A == INT_MAX)
			A = i;
		else if (B == INT_MAX)
			B = i;
		else if (C == INT_MAX)
			C = i;
		else if (D == INT_MAX)
			D = i;

		//if we found two differences, check if the elements are flipped
		if (A != INT_MAX && B != INT_MAX)
		{
			//simple flip?
			if (C == INT_MAX)
			{
				if (ref->GetAssignment(A) == other->GetAssignment(B) && ref->GetAssignment(B) == other->GetAssignment(A))
				{
					//go on checking
					A = INT_MAX;
					B = INT_MAX;
				}
				else
				{
					//check for a three-element permutation before giving up
				}
			}
			else //C != INT_MAX
			{
				if (D == INT_MAX)
				{
					bool CAB = ref->GetAssignment(A) == other->GetAssignment(C) &&
						ref->GetAssignment(B) == other->GetAssignment(A) &&
						ref->GetAssignment(C) == other->GetAssignment(B);
					bool BCA = ref->GetAssignment(A) == other->GetAssignment(B) &&
						ref->GetAssignment(B) == other->GetAssignment(C) &&
						ref->GetAssignment(C) == other->GetAssignment(A);

					if (CAB || BCA)
					{
						//go on checking
						A = INT_MAX;
						B = INT_MAX;
						C = INT_MAX;
					}
					else
					{
						//check for a four-element permutation before giving up
					}
				}
				else //D != INT_MAX
				{
					bool DABC = ref->GetAssignment(A) == other->GetAssignment(D) &&
						ref->GetAssignment(B) == other->GetAssignment(A) &&
						ref->GetAssignment(C) == other->GetAssignment(B) &&
						ref->GetAssignment(D) == other->GetAssignment(C);
					bool CDAB = ref->GetAssignment(A) == other->GetAssignment(C) &&
						ref->GetAssignment(B) == other->GetAssignment(D) &&
						ref->GetAssignment(C) == other->GetAssignment(A) &&
						ref->GetAssignment(D) == other->GetAssignment(B);
					bool BCDA = ref->GetAssignment(A) == other->GetAssignment(B) &&
						ref->GetAssignment(B) == other->GetAssignment(C) &&
						ref->GetAssignment(C) == other->GetAssignment(D) &&
						ref->GetAssignment(D) == other->GetAssignment(A);

					if (DABC || CDAB || BCDA)
					{
						//go on checking
						A = INT_MAX;
						B = INT_MAX;
						C = INT_MAX;
						D = INT_MAX;
					}
					else
					{
						//real difference or more complex permutations
						mismatch = true;
						break;
					}
				}
			}
		}
	}

	//gotcha - there might be an "unfinished" mismatch!
	if (A != INT_MAX)
		mismatch = true;

	if (mismatch)
	{
		giDifferentPos++;
		return false;
	}
	else
	{
		giEquivalentPos++;
		return true;
	}
}

void CvBasePosition::setFirstInterestingAssignment(size_t i)
{
	nFirstInterestingAssignment = i;
}

size_t CvBasePosition::getFirstInterestingAssignment() const
{
	return (size_t)nFirstInterestingAssignment;
}

void CvBasePosition::UpdateScore(const STacticalAssignment& assignment)
{
	UpdateScore(assignment.iUnitID, assignment.GetPlotScore(), assignment.GetOldPlotScore(), assignment.GetDamageDelta(), assignment.GetBonusScore());
}

void CvBasePosition::UpdateScore(int iUnitId, int iPlotScore, int iOldPlotScore, int iDamageDelta_, int iBonusScore_)
{
	iScoreOverParent += iBonusScore_ + iPlotScore - iOldPlotScore + iDamageDelta_;
	iDamageDelta += iDamageDelta_;
	iBonusScore += iBonusScore_;

	const STacticalPlotScores& plotScores_r = plotScores.read();

	//update total score and check for old plot score
	//total score is (iDamageDelta + iBonusScore) * 10 + sum(plotScores)
	//score over parent is (iBonusScore + iDamageDelta + iPlotScore - sPreviousPlotScore)
	iTotalScore = (iDamageDelta + iBonusScore) * 10;
	bool bFoundScore = false;
	for (STacticalPlotScores::const_iterator it = plotScores_r.begin(); it != plotScores_r.end(); ++it)
	{
		int iLoopUnitID = it->first;
		short sPreviousPlotScore = it->second;

		iTotalScore += CvStacking::IsEnabled() && iLoopUnitID == iUnitId ? iPlotScore : sPreviousPlotScore;
		if (iLoopUnitID == iUnitId)
		{
			bFoundScore = true;
			// The stored previous score replaces the caller's previous score;
			// subtracting both penalizes a second move by the same unit twice.
			if (CvStacking::IsEnabled())
				iScoreOverParent += iOldPlotScore;
			iScoreOverParent -= sPreviousPlotScore;
			if (iPlotScore != sPreviousPlotScore)
			{
				plotScores.write()[iUnitId] = iPlotScore;
			}
		}
	}
	//the unit didn't have a previous plot score, so we set it here
	if (!bFoundScore && iPlotScore != 0)
	{
		plotScores.write()[iUnitId] = iPlotScore;
		if (CvStacking::IsEnabled())
			iTotalScore += iPlotScore;
	}
}

// Search-scoped exact-state caches. Hashes locate buckets only; full vectors
// decide equality, so neither HP quantization nor a hash collision merges states.
struct StackForecastKey
{
 vector<int> state;
 bool operator==(const StackForecastKey& other) const { return state == other.state; }
};
struct StackForecastKeyHash
{
 size_t operator()(const StackForecastKey& key) const
 {
  size_t result = 0;
  for (size_t i = 0; i < key.state.size(); ++i)
   result ^= (size_t)key.state[i] + 0x9e3779b9 + (result << 6) + (result >> 2);
  return result;
 }
};
// Scalar hits read only this first integer. Odd packet keys retain the
// precomputed exact member integers in the same bounded danger table.
struct StackDangerForecastValue
{
 int scalar;
 vector<pair<int,int> > memberScores;
 StackDangerForecastValue(int value=0):scalar(value){}
};
typedef std::tr1::unordered_map<StackForecastKey, StackDangerForecastValue, StackForecastKeyHash> StackDangerForecasts;
typedef std::tr1::unordered_map<StackForecastKey, const CvUnit*, StackForecastKeyHash> StackDefenderForecasts;
static StackDangerForecasts gStackDangerForecasts;
static StackDefenderForecasts gStackDefenderForecasts;
// Node references survive unordered_map rehash; iterators do not. FIFO stores
// only key pointers, not duplicate key vectors, and removes them before erase.
static std::deque<const StackForecastKey*> gStackDangerOrder, gStackDefenderOrder;
typedef std::map<std::pair<int, int>, unsigned char> StackThreatFlags;
static StackThreatFlags gStackThreatFlags;
static bool gStackForecastsActive = false;
static unsigned int gStackForecastDepth = 0;
static volatile LONG gStackForecastOwnerThread = 0;
static long gStackForecastSceneEpoch = 0;
static unsigned long gStackForecastRevision = 0;
static unsigned long gStackDangerHits = 0, gStackDangerMisses = 0;
static unsigned long gStackOutcomeBuilds = 0, gStackOutcomeReuses = 0, gStackOutcomeBypasses = 0;
static size_t gStackOutcomeCurrentBytes = 0, gStackOutcomePeakBytes = 0;
static unsigned long gStackDefenderHits = 0, gStackDefenderMisses = 0;
static unsigned long gStackInsertBypasses = 0, gStackNestedBypasses = 0;
static unsigned long gStackDangerEvictions = 0, gStackDefenderEvictions = 0;
static size_t gStackPeakEntries = 0, gStackPeakKeyBytes = 0, gStackPeakEstimatedBytes = 0;
static size_t gStackKeyPayloadBytes = 0, gStackKeyPayloadLimit = 0, gStackEntryLimit = 0;
static bool IsStackForecastOwner()
{
 return (DWORD)gStackForecastOwnerThread == GetCurrentThreadId();
}
// Bounded owned forecast storage. Input key and result semantics remain unchanged.
// No slot/payload reference is permitted to escape a small table operation.
class IndexedStore
{
public:
 enum { INLINE_WORDS=32, DANGER=0, DEFENDER=1 };
 struct Pending
 {
  size_t keyWords,members;
  int scalar;
  const CvUnit* defender;
  int* heap;
  int words[INLINE_WORDS];
  Pending():keyWords(0),members(0),scalar(0),defender(NULL),heap(NULL){}
  ~Pending(){delete[] heap;}
  const int* Data()const{return heap?heap:words;}
  size_t Words()const{return keyWords+2*members;}
  void Assign(const StackForecastKey& key,const StackDangerForecastValue* value,const CvUnit* unit)
  {
   keyWords=key.state.size();members=value?value->memberScores.size():0;
   scalar=value?value->scalar:0;defender=unit;
   if(members>(static_cast<size_t>(-1)-keyWords)/2)throw std::bad_alloc();
   const size_t count=Words();
   if(count>static_cast<size_t>(-1)/sizeof(int))throw std::bad_alloc();
   if(count>INLINE_WORDS)heap=new int[count];
   int* out=heap?heap:words;
   if(keyWords)std::memcpy(out,&key.state[0],keyWords*sizeof(int));
   for(size_t i=0;i<members;++i){out[keyWords+2*i]=value->memberScores[i].first;out[keyWords+2*i+1]=value->memberScores[i].second;}
  }
 private:Pending(const Pending&);Pending&operator=(const Pending&);
 };
 struct Slot
 {
  size_t hash,keyWords,members;
  int hashPrev,hashNext,queueNext;
  int scalar;
  const CvUnit* defender;
  int* heap;
  unsigned char kind,used;
  int words[INLINE_WORDS];
  Slot():hash(0),keyWords(0),members(0),hashPrev(-1),hashNext(-1),queueNext(-1),scalar(0),defender(NULL),heap(NULL),kind(0),used(0){}
  ~Slot(){delete[] heap;}
  const int* Data()const{return heap?heap:words;}
  size_t PayloadBytes()const{return (keyWords+2*members)*sizeof(int);}
 };
 IndexedStore():slots(NULL),buckets(NULL),slotCapacity(0),bucketCount(0),firstFree(-1),nextUnused(0),overflowBytes(0)
 {for(int i=0;i<2;++i){heads[i]=tails[i]=-1;counts[i]=queued[i]=0;}}
 ~IndexedStore(){Release();}
 void Init(size_t limit)
 {
  Release();if(!limit)return;
  if(limit>=static_cast<size_t>(INT_MAX)||limit>=static_cast<size_t>(-1)/sizeof(Slot)-1)throw std::bad_alloc();
  const size_t needed=limit+1; // One uncharged packet node may precede FIFO eviction.
  if(needed>static_cast<size_t>(-1)/2)throw std::bad_alloc();
  size_t bucketsNeeded=1;
  while(bucketsNeeded<needed*2){if(bucketsNeeded>static_cast<size_t>(-1)/2)throw std::bad_alloc();bucketsNeeded*=2;}
  try{slots=new Slot[needed];buckets=new int[bucketsNeeded];}
  catch(...){delete[] slots;slots=NULL;delete[] buckets;buckets=NULL;throw;}
  slotCapacity=needed;bucketCount=bucketsNeeded;
  for(size_t i=0;i<bucketCount;++i)buckets[i]=-1;
  firstFree=-1;nextUnused=0;
 }
 void Clear()
 {
  for(size_t i=0;i<nextUnused;++i)
  {
   Slot& s=slots[i];delete[] s.heap;s.heap=NULL;s.used=0;s.keyWords=s.members=0;
   s.hashPrev=s.queueNext=s.hashNext=-1;
  }
  for(size_t i=0;i<bucketCount;++i)buckets[i]=-1;
  for(int i=0;i<2;++i){heads[i]=tails[i]=-1;counts[i]=queued[i]=0;}
  firstFree=-1;nextUnused=0;overflowBytes=0;
 }
 void Release()
 {
  delete[] slots;delete[] buckets;slots=NULL;buckets=NULL;slotCapacity=bucketCount=nextUnused=overflowBytes=0;firstFree=-1;
  for(int i=0;i<2;++i){heads[i]=tails[i]=-1;counts[i]=queued[i]=0;}
 }
 size_t Count(int kind)const{return counts[kind];}
 size_t Total()const{return counts[0]+counts[1];}
 size_t ReservedBytes()const{return slotCapacity*sizeof(Slot)+bucketCount*sizeof(int)+overflowBytes;}
 size_t Capacity()const{return slotCapacity;}
 size_t Buckets()const{return bucketCount;}
 size_t OverflowBytes()const{return overflowBytes;}
 int Find(const StackForecastKey& key,int kind)const
 {
  if(!bucketCount)return -1;
  const size_t hash=StackForecastKeyHash()(key);
  for(int i=buckets[hash&(bucketCount-1)];i!=-1;i=slots[i].hashNext)
  {
   const Slot& s=slots[i];
   if(s.used&&s.kind==kind&&s.hash==hash&&s.keyWords==key.state.size()&&
    (!s.keyWords||!std::memcmp(s.Data(),&key.state[0],s.keyWords*sizeof(int))))return i;
  }
  return -1;
 }
 // Stable handle. The caller copies scalar/pointer/member data before Context.
 const Slot& At(int handle)const{return slots[handle];}
 int Insert(const StackForecastKey& key,Pending& pending,int kind,bool& inserted)
 {
  int duplicate=Find(key,kind);if(duplicate!=-1){inserted=false;return duplicate;}
  int handle;
  if(firstFree!=-1){handle=firstFree;firstFree=slots[handle].hashNext;}
  else{if(nextUnused>=slotCapacity)throw std::bad_alloc();handle=static_cast<int>(nextUnused++);}
  Slot& s=slots[handle];
  s.hash=StackForecastKeyHash()(key);s.keyWords=pending.keyWords;s.members=pending.members;
  s.scalar=pending.scalar;s.defender=pending.defender;s.kind=static_cast<unsigned char>(kind);s.used=1;
  s.heap=pending.heap;pending.heap=NULL;
  if(!s.heap&&pending.Words())std::memcpy(s.words,pending.words,pending.Words()*sizeof(int));
  if(s.heap)overflowBytes+=s.PayloadBytes();
  size_t bucket=s.hash&(bucketCount-1);s.hashPrev=-1;s.hashNext=buckets[bucket];s.queueNext=-1;
  if(s.hashNext!=-1)slots[s.hashNext].hashPrev=handle;
  buckets[bucket]=handle;++counts[kind];inserted=true;return handle;
 }
 void Erase(int handle)
 {
  Slot& s=slots[handle];const size_t bucket=s.hash&(bucketCount-1);
  if(s.hashPrev!=-1)slots[s.hashPrev].hashNext=s.hashNext;else buckets[bucket]=s.hashNext;
  if(s.hashNext!=-1)slots[s.hashNext].hashPrev=s.hashPrev;
  if(s.heap)overflowBytes-=s.PayloadBytes();
  delete[] s.heap;s.heap=NULL;--counts[s.kind];s.used=0;s.keyWords=s.members=0;
  s.hashPrev=s.queueNext=-1;s.hashNext=firstFree;firstFree=handle;
 }
 void Push(int handle)
 {
  Slot& s=slots[handle];int kind=s.kind;
  if(tails[kind]!=-1)slots[tails[kind]].queueNext=handle;else heads[kind]=handle;
  tails[kind]=handle;
 }
 int Head(int kind)const{return heads[kind];}
 size_t QueueCount(int kind)const
 {
  size_t count=0;for(int i=heads[kind];i!=-1;i=slots[i].queueNext){if(i<0||static_cast<size_t>(i)>=slotCapacity||++count>slotCapacity)return static_cast<size_t>(-1);}return count;
 }
 // O(1) FIFO count is separate from total entries, including pending packet.
 size_t FIFOCount(int kind)const{return queued[kind];}
 void QueuePush(int handle){Push(handle);++queued[slots[handle].kind];}
 void QueuePop(int kind)
 {
  int handle=heads[kind];heads[kind]=slots[handle].queueNext;if(heads[kind]==-1)tails[kind]=-1;
  slots[handle].queueNext=-1;--queued[kind];
 }
 int NextQueued(int handle)const{return slots[handle].queueNext;}
 void ResetQueued(){queued[0]=queued[1]=0;}
 bool Invariant(size_t logicalBytes,size_t limit,size_t payloadLimit)const
 {
  size_t bytes=0,total=0,heapBytes=0,freeCount=0;
  for(size_t i=0;i<slotCapacity;++i)if(slots[i].used){bytes+=slots[i].PayloadBytes();if(slots[i].heap)heapBytes+=slots[i].PayloadBytes();++total;}
  for(int i=firstFree;i!=-1;i=slots[i].hashNext){if(i<0||static_cast<size_t>(i)>=slotCapacity||slots[i].used||++freeCount>slotCapacity)return false;}
  return bytes==logicalBytes&&total==Total()&&total<=limit&&bytes<=payloadLimit&&heapBytes==overflowBytes&&nextUnused<=slotCapacity&&total+freeCount==nextUnused&&
   QueueCount(0)==queued[0]&&QueueCount(1)==queued[1]&&queued[0]==counts[0]&&queued[1]==counts[1];
 }
private:
 Slot* slots;int* buckets;size_t slotCapacity,bucketCount;int firstFree;size_t nextUnused;
 int heads[2],tails[2];size_t counts[2],queued[2],overflowBytes;
 IndexedStore(const IndexedStore&);IndexedStore&operator=(const IndexedStore&);
};

static IndexedStore gIndexed;
static bool gUseIndexed=false;
static void ClearStackForecastEntries()
{
 gIndexed.Clear();gIndexed.ResetQueued();gStackDangerOrder.clear();gStackDefenderOrder.clear();
 gStackDangerForecasts.clear();gStackDefenderForecasts.clear();gStackThreatFlags.clear();gStackKeyPayloadBytes=0;++gStackForecastRevision;
}



static void InvalidateStackForecastScene()
{
 if (!IsStackForecastOwner())
  return;
 ClearStackForecastEntries();
 gStackForecastSceneEpoch = CvStackingStrengthCache::SceneEpoch();
}
static bool StackForecastContext()
{
 if (!IsStackForecastOwner() || !gStackForecastsActive || gStackForecastDepth != 1)
  return false;
 if (CvStackingStrengthCache::IsPreviewSuspended()) return false;
 long callbackGeneration;
 if (!CvStackingStrengthCache::Context(callbackGeneration)) return false;
 if (gStackForecastSceneEpoch != CvStackingStrengthCache::SceneEpoch())
  InvalidateStackForecastScene();
 return true;
}
// Most queries hit. Reuse their temporary vectors rather than allocating a key
// and two sorting buffers millions of times. A borrower owns the buffer through
// the leaf calculation; nested callbacks use private fallback vectors.
static StackForecastKey gStackDangerScratch, gStackDefenderScratch;
static vector<pair<int,int> > gStackSortScratch;
static bool gStackDangerScratchBusy=false, gStackDefenderScratchBusy=false, gStackSortScratchBusy=false;
static vector<const CvUnit*> gStackSoloScratch;
static bool gStackSoloScratchBusy=false;
struct StackForecastQuery
{
 StackForecastKey* scratch;
 bool* busy;
 StackForecastKey& key;
 StackForecastQuery(StackForecastKey& buffer,bool& inUse):
  scratch(StackForecastContext() && !inUse ? &buffer : NULL),busy(scratch ? &inUse : NULL),
  key(scratch ? *scratch : *new StackForecastKey)
 {
  if(busy) *busy=true;
  key.state.clear();
 }
 ~StackForecastQuery()
 {
  if(busy) *busy=false; else delete &key;
 }
private:
 StackForecastQuery(const StackForecastQuery&);
 StackForecastQuery& operator=(const StackForecastQuery&);
};
struct StackForecastPairQuery
{
 bool borrowed;
 vector<pair<int,int> >& entries;
 StackForecastPairQuery():borrowed(StackForecastContext() && !gStackSortScratchBusy),
  entries(borrowed ? gStackSortScratch : *new vector<pair<int,int> >)
 {
  if(borrowed) gStackSortScratchBusy=true;
  entries.clear();
 }
 ~StackForecastPairQuery()
 {
  if(borrowed) gStackSortScratchBusy=false; else delete &entries;
 }
private:
 StackForecastPairQuery(const StackForecastPairQuery&);
 StackForecastPairQuery& operator=(const StackForecastPairQuery&);
};

// A const preferred-assignment call does not mutate its enemy wound ledger.
// Bind only that lexical lifetime, never a persistent container-pointer cache.
// Keep a separate loan: holding gStackSortScratch here would allocate a private
// membership-sort vector for each scalar query in the same candidate loop.
struct StackImmutableEnemyDamageScope;
static StackImmutableEnemyDamageScope* gStackImmutableEnemyDamageScope = NULL;
static vector<pair<int,int> > gStackImmutableEnemyDamageScratch;
static bool gStackImmutableEnemyDamageScratchBusy = false;
struct StackImmutableEnemyDamageScope
{
 const SUnitIDValueContainer& damage;
 StackImmutableEnemyDamageScope* previous;
 unsigned long revision;
 long scene;
 bool registered, borrowed, ready, oversized;
 StackImmutableEnemyDamageScope(const SUnitIDValueContainer& immutableDamage):
  damage(immutableDamage),previous(NULL),revision(0),scene(0),
  registered(false),borrowed(false),ready(false),oversized(false)
 {
  // Check ownership before touching another thread's pointer or scratch flag.
  if (!IsStackForecastOwner() || !StackForecastContext())
   return;
  registered = true;
  previous = gStackImmutableEnemyDamageScope;
  gStackImmutableEnemyDamageScope = this;
  revision = gStackForecastRevision;
  scene = gStackForecastSceneEpoch;
  borrowed = !gStackImmutableEnemyDamageScratchBusy;
  if (borrowed)
  {
   gStackImmutableEnemyDamageScratchBusy = true;
   gStackImmutableEnemyDamageScratch.clear();
  }
 }
 ~StackImmutableEnemyDamageScope()
 {
  if (!registered)
   return;
  gStackImmutableEnemyDamageScope = previous;
  if (borrowed)
  {
   gStackImmutableEnemyDamageScratch.clear();
   gStackImmutableEnemyDamageScratchBusy = false;
  }
 }
 bool TryAppend(StackForecastKey& key, const SUnitIDValueContainer& queriedDamage,
  const vector<int>* freshSourceIDs)
 {
  if (!borrowed || oversized || &damage != &queriedDamage || !StackForecastContext() ||
   revision != gStackForecastRevision || scene != gStackForecastSceneEpoch)
   return false;
  vector<pair<int,int> >& entries = gStackImmutableEnemyDamageScratch;
  if (!ready)
  {
   size_t count = 0;
   for (SUnitIDValueContainer::const_iterator it = damage.begin(); it != damage.end(); ++it)
    if ((*it).second != 0)
     ++count;
   // One bounded temporary fragment; no new memo entries or admission policy.
   if (count > gStackKeyPayloadLimit / sizeof(pair<int,int>))
   {
    oversized = true;
    return false;
   }
   entries.reserve(count);
   if (entries.capacity() > gStackKeyPayloadLimit / sizeof(pair<int,int>))
   {
    vector<pair<int,int> >().swap(entries);
    oversized = true;
    return false;
   }
   for (SUnitIDValueContainer::const_iterator it = damage.begin(); it != damage.end(); ++it)
    if ((*it).second != 0)
     entries.push_back(*it);
   std::sort(entries.begin(), entries.end());
   ready = true;
  }
  const size_t countIndex = key.state.size();
  key.state.push_back(0);
  int count = 0;
  for (size_t i = 0; i < entries.size(); ++i)
   if (!freshSourceIDs || std::binary_search(freshSourceIDs->begin(), freshSourceIDs->end(), entries[i].first))
   {
    key.state.push_back(entries[i].first);
    key.state.push_back(entries[i].second);
    ++count;
   }
  key.state[countIndex] = count;
  return true;
 }
private:
 StackImmutableEnemyDamageScope(const StackImmutableEnemyDamageScope&);
 StackImmutableEnemyDamageScope& operator=(const StackImmutableEnemyDamageScope&);
};
static bool AppendImmutableEnemyDamage(StackForecastKey& key, const SUnitIDValueContainer& damage,
 const vector<int>* freshSourceIDs)
{
 if (!IsStackForecastOwner())
  return false;
 StackImmutableEnemyDamageScope* scope = gStackImmutableEnemyDamageScope;
 return scope && scope->TryAppend(key, damage, freshSourceIDs);
}

// Virtual membership is rebuilt for each query, but its temporary storage can
// survive between queries. Keep the borrow through all danger/score callbacks;
// a nested query uses private storage instead of overwriting the outer stack.
struct VirtualFriendlyStackBuffer
{
 vector<const CvUnit*> candidates;
 SUnitIDValueContainer damage;
 void release()
 {
  vector<const CvUnit*>().swap(candidates);
  SUnitIDValueContainer empty;
  damage.swap(empty);
 }
};
static void ReleaseParentStackPreparationStorage();
static VirtualFriendlyStackBuffer gStackVirtualScratch;
static bool gStackVirtualScratchBusy = false;
// Movement's destination survives intervening turn-end/flanking queries. Keep
// their ordinary scratch available instead of forcing private allocations.
static VirtualFriendlyStackBuffer gStackDestinationScratch;
static bool gStackDestinationScratchBusy = false;
struct VirtualFriendlyStackQuery
{
 bool borrowed;
 VirtualFriendlyStackBuffer& buffer;
 vector<const CvUnit*>& candidates;
 SUnitIDValueContainer& damage;
 VirtualFriendlyStackQuery():borrowed(StackForecastContext() && !gStackVirtualScratchBusy),
  buffer(borrowed ? gStackVirtualScratch : *new VirtualFriendlyStackBuffer),
  candidates(buffer.candidates),damage(buffer.damage)
 {
  if (borrowed) gStackVirtualScratchBusy = true;
  candidates.clear();
  damage.clear();
 }
 ~VirtualFriendlyStackQuery()
 {
  if (borrowed) gStackVirtualScratchBusy = false;
  else delete &buffer;
 }
private:
 VirtualFriendlyStackQuery(const VirtualFriendlyStackQuery&);
 VirtualFriendlyStackQuery& operator=(const VirtualFriendlyStackQuery&);
};

// Warmed owned packet query storage; nested/foreign calls retain private fallback.
struct StackDangerPacketBuffer
{
 StackForecastKey key;
 vector<int> source;
 vector<const CvUnit*> members;
 StackDangerForecastValue value;
 int descriptor[512];
 void clear(){key.state.clear();source.clear();members.clear();value.memberScores.clear();value.scalar=0;}
 void release(){vector<int>().swap(key.state);vector<int>().swap(source);vector<const CvUnit*>().swap(members);vector<pair<int,int> >().swap(value.memberScores);}
};
static StackDangerPacketBuffer gStackPacketScratch;
static bool gStackPacketScratchBusy=false;
static unsigned long gStackPacketHits=0,gStackPacketBuilds=0,gStackPacketBypasses=0;
struct StackDangerPacketQuery
{
 StackDangerPacketBuffer local;
 bool borrowed,storePacket,scalarValid;
 StackDangerPacketBuffer& buffer;
 StackDangerPacketQuery(bool cacheable):borrowed(cacheable&&!gStackPacketScratchBusy),storePacket(false),scalarValid(false),
  buffer(borrowed?gStackPacketScratch:local)
 {if(borrowed)gStackPacketScratchBusy=true;buffer.clear();}
 ~StackDangerPacketQuery(){if(borrowed)gStackPacketScratchBusy=false;}
private:StackDangerPacketQuery(const StackDangerPacketQuery&);StackDangerPacketQuery&operator=(const StackDangerPacketQuery&);
};

// Pure current-world capability proof. These bits are intentionally
// conservative: unsupported/custom AIR loading graphs disable reuse for the
// segment. Standard ranged aircraft with zero melee base preserve all caches.
static bool StackPreviewCallbackCapabilities(unsigned int& flags,bool scan)
{
 flags = 0;
 if (!gDLL->HasGameCoreLock() || MOD_EVENTS_CAN_MOVE_INTO || MOD_EVENTS_AIRLIFT ||
  MOD_EVENTS_SEALIFT || MOD_EVENTS_UNIT_RANGEATTACK || MOD_EVENTS_CITY_BOMBARD || MOD_EVENTS_REBASE || MOD_EVENTS_UNIT_ACTIONS)
  return false;
 if (!scan) return true; // Cheap live lock/options validation, no world reads.
 for (int i=0;i<MAX_PLAYERS;++i)
 {
  const CvPlayer& player=GET_PLAYER((PlayerTypes)i);
  int cursor=0;
  for (const CvUnit* unit=player.firstUnit(&cursor);unit;unit=player.nextUnit(&cursor))
   if (!unit->IsDead() && !unit->isDelayedDeath() && unit->getDomainType()==DOMAIN_AIR)
   {
    // Base strength and ranged readiness can be changed by Lua/native setters.
    if (unit->GetBaseCombatStrength()!=0) flags|=CvStackingStrengthCache::CALLBACK_AIR_BLOCKADER;
   }
  const vector<pair<int,int> >& interceptors=player.GetPossibleInterceptors();
  for (size_t j=0;j<interceptors.size();++j)
  {
   const CvUnit* unit=player.getUnit(interceptors[j].first);
   if (unit && !unit->IsDead() && !unit->isDelayedDeath() && unit->getDomainType()!=DOMAIN_AIR &&
    (unit->IsCanHeavyCharge() || unit->GetMoraleBreakChance()!=0))
    flags|=CvStackingStrengthCache::CALLBACK_AIR_ESCAPE;
  }
 }
 return true;
}
static bool StackPreviewInputsSupported(const vector<CvUnit*>& units)
{
 if (!gDLL->HasGameCoreLock() || MOD_EVENTS_CAN_MOVE_INTO || MOD_EVENTS_AIRLIFT ||
  MOD_EVENTS_SEALIFT || MOD_EVENTS_UNIT_RANGEATTACK || MOD_EVENTS_CITY_BOMBARD || MOD_EVENTS_REBASE || MOD_EVENTS_UNIT_ACTIONS)
  return false;
 // AIR actors only differ through the legacy CanLoadAt Lua query (carrier
 // rebasing). Excluding them disabled every cache for the whole search, which
 // made late-game searches with bombers about ten times slower. Set the XML
 // row to 0 when a mod registers a CanLoadAt listener with side effects.
 if (CvStacking::GetInt("AITacticalCacheAirActors",1))
  return true;
 for (size_t i=0;i<units.size();++i)
  if (units[i] && units[i]->getDomainType()==DOMAIN_AIR) return false;
 return true;
}

struct StackForecastScope
{
 bool owned;
 StackForecastScope(bool supported=false):owned(false)
 {
  const LONG thread = (LONG)GetCurrentThreadId();
  const LONG previous = InterlockedCompareExchange(&gStackForecastOwnerThread, thread, 0);
  if (previous != 0 && previous != thread)
   return;
  owned = true;
  ++gStackForecastDepth;
  gStackForecastsActive = gStackForecastDepth == 1;
  if (gStackForecastDepth==1 && !supported) gStackForecastsActive=false;
  if (gStackForecastDepth != 1)
  {
   // A nested search bypasses shared storage and cancels outer computations
   // in flight. The base tactical search itself is still nonreentrant.
   InvalidateStackForecastScene();
   ++gStackNestedBypasses;
   return;
  }
  InvalidateStackForecastScene();
  gStackDangerHits = gStackDangerMisses = gStackDefenderHits = gStackDefenderMisses = 0;
  gStackOutcomeBuilds = gStackOutcomeReuses = gStackOutcomeBypasses = 0;
  gStackOutcomeCurrentBytes = gStackOutcomePeakBytes = 0;
  gStackPacketHits = gStackPacketBuilds = gStackPacketBypasses = 0;
  gStackInsertBypasses = gStackNestedBypasses = 0;
  gStackDangerEvictions = gStackDefenderEvictions = 0;
  gStackPeakEntries = gStackPeakKeyBytes = gStackPeakEstimatedBytes = 0;
  gStackKeyPayloadBytes = 0;
  // Dense searches evict far more forecasts than they keep at one entry per
  // position; the XML row sets the entry count (about 172 bytes each).
  gStackEntryLimit = (size_t)max(gTactPosStorage.getSizeLimit(), CvStacking::GetInt("AITacticalForecastEntries", 24000));
  // An ID/damage pair per movable-unit slot as payload budget.
  gStackKeyPayloadLimit = gStackEntryLimit * TACTSIM_MAX_UNITS * 2 * sizeof(int);
  gUseIndexed=false;
  try { if(gStackForecastsActive){gIndexed.Init(gStackEntryLimit);gUseIndexed=true;} }
  catch (const std::bad_alloc&)
  {
   // Pick the original representation before any query or admission.
   // Partial arrays are already rolled back by Init; no in-search fallback.
   gIndexed.Release();gUseIndexed=false;
  }
  catch (...)
  {
   // Constructor failure will not invoke this object's destructor.
   gIndexed.Release();gStackKeyPayloadBytes=0;gStackEntryLimit=gStackKeyPayloadLimit=0;
   gStackForecastDepth=0;gStackForecastsActive=false;owned=false;
   InterlockedExchange(&gStackForecastOwnerThread,0);throw;
  }
 }
 ~StackForecastScope()
 {
  if (!owned)
   return;
  --gStackForecastDepth;
  gStackForecastsActive = gStackForecastDepth == 1;
  InvalidateStackForecastScene();
  if (gStackForecastDepth == 0)
  {
   // clear() can retain buckets. Release them as well in the 32-bit game.
   gIndexed.Release();gUseIndexed=false;
   std::deque<const StackForecastKey*>().swap(gStackDangerOrder);
   std::deque<const StackForecastKey*>().swap(gStackDefenderOrder);
   StackDangerForecasts().swap(gStackDangerForecasts);
   StackDefenderForecasts().swap(gStackDefenderForecasts);
   StackThreatFlags().swap(gStackThreatFlags);
   vector<int>().swap(gStackDangerScratch.state);
   vector<int>().swap(gStackDefenderScratch.state);
   vector<pair<int,int> >().swap(gStackSortScratch);
   vector<pair<int,int> >().swap(gStackImmutableEnemyDamageScratch);
   ReleaseParentStackPreparationStorage();
   gStackVirtualScratch.release();
   gStackDestinationScratch.release();
   gStackPacketScratch.release();
   gStackKeyPayloadBytes = 0;
   InterlockedExchange(&gStackForecastOwnerThread, 0);
  }
 }
private:
 StackForecastScope(const StackForecastScope&);
 StackForecastScope& operator=(const StackForecastScope&);
};

// Retained capacities, including packet outputs, share the original payload
// ceiling. Scalar value vectors are empty and retain no output allocation.
static size_t LegacyStackDangerForecastPayloadBytes(const StackDangerForecasts::value_type& entry)
{
 return entry.first.state.capacity() * sizeof(int)
  + entry.second.memberScores.capacity() * sizeof(pair<int,int>);
}

static bool LegacyEvictOldestStackForecast()
{
 // Refresh the larger pool first. This preserves the small, high-reuse
 // selector pool without letting either table permanently starve the other.
 if (!gStackDangerOrder.empty() && gStackDangerOrder.size() >= gStackDefenderOrder.size())
 {
  StackDangerForecasts::iterator victim = gStackDangerForecasts.find(*gStackDangerOrder.front());
  if (victim == gStackDangerForecasts.end())
   return false;
  const size_t payload = LegacyStackDangerForecastPayloadBytes(*victim);
  if (payload > gStackKeyPayloadBytes)
   return false;
  gStackDangerOrder.pop_front();
  gStackKeyPayloadBytes -= payload;
  gStackDangerForecasts.erase(victim);
  ++gStackDangerEvictions;
  return true;
 }
 if (!gStackDefenderOrder.empty())
 {
  StackDefenderForecasts::iterator victim = gStackDefenderForecasts.find(*gStackDefenderOrder.front());
  if (victim == gStackDefenderForecasts.end())
   return false;
  const size_t payload = victim->first.state.capacity() * sizeof(int);
  if (payload > gStackKeyPayloadBytes)
   return false;
  gStackDefenderOrder.pop_front();
  gStackKeyPayloadBytes -= payload;
  gStackDefenderForecasts.erase(victim);
  ++gStackDefenderEvictions;
  return true;
 }
 return false;
}

static bool LegacyCanStoreStackForecast(const StackForecastKey& key)
{
 if (!StackForecastContext())
  return false;
 const size_t payload = key.state.capacity() * sizeof(int);
 // Reject a key that can never fit before evicting any useful entries.
 if (gStackEntryLimit == 0 || payload > gStackKeyPayloadLimit)
 {
  ++gStackInsertBypasses;
  return false;
 }
 while (gStackDangerForecasts.size() + gStackDefenderForecasts.size() >= gStackEntryLimit ||
  payload > gStackKeyPayloadLimit - gStackKeyPayloadBytes)
 {
  if (!LegacyEvictOldestStackForecast())
  {
   ++gStackInsertBypasses;
   return false;
  }
 }
 return true;
}

static size_t LegacyEstimatedStackForecastBytes()
{
 const size_t entries = gStackDangerForecasts.size() + gStackDefenderForecasts.size();
 // Key payload is measured; allocator/node/bucket overhead is an estimate.
 // FIFO adds only one key pointer per retained entry plus its two containers.
 return gStackKeyPayloadBytes + entries * (sizeof(StackForecastKey) + sizeof(const CvUnit*) + 9 * sizeof(void*))
  + gStackDangerForecasts.size() * (sizeof(StackDangerForecastValue) - sizeof(int))
  + sizeof(gStackDangerOrder) + sizeof(gStackDefenderOrder)
  + sizeof(gStackThreatFlags) + gStackThreatFlags.size() * (sizeof(StackThreatFlags::value_type) + 4 * sizeof(void*));
}

static void LegacyUpdateStackForecastPeaks()
{
 gStackPeakEntries = max(gStackPeakEntries, gStackDangerForecasts.size() + gStackDefenderForecasts.size());
 gStackPeakKeyBytes = max(gStackPeakKeyBytes, gStackKeyPayloadBytes);
 gStackPeakEstimatedBytes = max(gStackPeakEstimatedBytes, LegacyEstimatedStackForecastBytes());
}

static void LegacyStoreStackDangerForecast(const StackForecastKey& key, int result)
{
 if (!LegacyCanStoreStackForecast(key))
  return;
 pair<StackDangerForecasts::iterator, bool> stored = gStackDangerForecasts.insert(make_pair(key, StackDangerForecastValue(result)));
 if (stored.second)
 {
  const size_t payload = LegacyStackDangerForecastPayloadBytes(*stored.first);
  if (payload <= gStackKeyPayloadLimit - gStackKeyPayloadBytes)
  {
   gStackKeyPayloadBytes += payload;
   gStackDangerOrder.push_back(&stored.first->first);
   LegacyUpdateStackForecastPeaks();
  }
  else
  {
   gStackDangerForecasts.erase(stored.first);
   ++gStackInsertBypasses;
  }
 }
}

// Insert one temporary uncharged node to measure its ACTUAL copied vector
// capacities before evicting useful entries. No node reference escapes this
// helper; retained entries still use the original shared FIFO/entry ceiling.
static void LegacyStoreStackDangerPacketForecast(const StackForecastKey& key, const StackDangerForecastValue& value)
{
 if (!StackForecastContext())
  return;
 if (key.state.size() % 2 == 0 || value.memberScores.size() < 2 || gStackEntryLimit == 0)
 {
  ++gStackInsertBypasses;
  return;
 }
 if (gStackDangerForecasts.find(key) != gStackDangerForecasts.end())
  return;
 const unsigned long revision = gStackForecastRevision;
 const long scene = gStackForecastSceneEpoch;
 pair<StackForecastKey,StackDangerForecastValue> pending(key,value);
 // Reject copied payloads that cannot fit before inserting or evicting.
 if (pending.first.state.capacity() > gStackKeyPayloadLimit / sizeof(int))
 {
  ++gStackInsertBypasses;
  return;
 }
 const size_t copiedKeyBytes = pending.first.state.capacity() * sizeof(int);
 if (pending.second.memberScores.capacity() > (gStackKeyPayloadLimit - copiedKeyBytes) / sizeof(pair<int,int>))
 {
  ++gStackInsertBypasses;
  return;
 }
 // Copying may allocate; observe a changed scene before touching the table.
 if (!StackForecastContext() || revision != gStackForecastRevision || scene != gStackForecastSceneEpoch)
 {
  ++gStackInsertBypasses;
  return;
 }
 pair<StackDangerForecasts::iterator,bool> stored = gStackDangerForecasts.insert(pending);
 if (!stored.second)
  return;
 // Do not call a clearing context helper while owning this iterator. These
 // reads only validate the still-owned pure preview; erase first on failure.
 if (!gStackForecastsActive || gStackForecastDepth != 1 || revision != gStackForecastRevision ||
  scene != gStackForecastSceneEpoch || scene != CvStackingStrengthCache::SceneEpoch())
 {
  gStackDangerForecasts.erase(stored.first);
  ++gStackInsertBypasses;
  return;
 }
 if (stored.first->first.state.capacity() > gStackKeyPayloadLimit / sizeof(int))
 {
  gStackDangerForecasts.erase(stored.first);
  ++gStackInsertBypasses;
  return;
 }
 const size_t keyBytes = stored.first->first.state.capacity() * sizeof(int);
 if (stored.first->second.memberScores.capacity() > (gStackKeyPayloadLimit - keyBytes) / sizeof(pair<int,int>))
 {
  gStackDangerForecasts.erase(stored.first);
  ++gStackInsertBypasses;
  return;
 }
 const size_t payload = LegacyStackDangerForecastPayloadBytes(*stored.first);
 // The pending node is already included in size(), but is not in either
 // FIFO yet. Use > for entries; eviction still chooses the larger FIFO.
 while (gStackDangerForecasts.size() + gStackDefenderForecasts.size() > gStackEntryLimit ||
  payload > gStackKeyPayloadLimit - gStackKeyPayloadBytes)
 {
  if (!LegacyEvictOldestStackForecast())
  {
   gStackDangerForecasts.erase(stored.first);
   ++gStackInsertBypasses;
   return;
  }
 }
 try
 {
  gStackDangerOrder.push_back(&stored.first->first);
 }
 catch (...)
 {
  // The payload has not been charged. Roll back the otherwise orphan node;
  // previous FIFO evictions are not transactional and remain, as with the
  // legacy preflight. Preserve the caller's allocation failure by rethrowing.
  gStackDangerForecasts.erase(stored.first);
  throw;
 }
 gStackKeyPayloadBytes += payload;
 LegacyUpdateStackForecastPeaks();
}

static void LegacyStoreStackDefenderForecast(const StackForecastKey& key, const CvUnit* result)
{
 if (!LegacyCanStoreStackForecast(key))
  return;
 pair<StackDefenderForecasts::iterator, bool> stored = gStackDefenderForecasts.insert(make_pair(key, result));
 if (stored.second)
 {
  const size_t payload = stored.first->first.state.capacity() * sizeof(int);
  if (payload <= gStackKeyPayloadLimit - gStackKeyPayloadBytes)
  {
   gStackKeyPayloadBytes += payload;
   gStackDefenderOrder.push_back(&stored.first->first);
   LegacyUpdateStackForecastPeaks();
  }
  else
  {
   gStackDefenderForecasts.erase(stored.first);
   ++gStackInsertBypasses;
  }
 }
}


// Admission/control flow preserves the original storage helpers. Only the
// representation, owned-copy construction and key/queue lookup are replaced.
static bool EvictOldestStackForecast()
{
 if(!gUseIndexed)return LegacyEvictOldestStackForecast();
 if(gIndexed.FIFOCount(IndexedStore::DANGER)&&gIndexed.FIFOCount(IndexedStore::DANGER)>=gIndexed.FIFOCount(IndexedStore::DEFENDER))
 {
  int victim=gIndexed.Head(IndexedStore::DANGER);const size_t payload=gIndexed.At(victim).PayloadBytes();
  if(payload>gStackKeyPayloadBytes)return false;
  gIndexed.QueuePop(IndexedStore::DANGER);gStackKeyPayloadBytes-=payload;gIndexed.Erase(victim);++gStackDangerEvictions;return true;
 }
 if(gIndexed.FIFOCount(IndexedStore::DEFENDER))
 {
  int victim=gIndexed.Head(IndexedStore::DEFENDER);const size_t payload=gIndexed.At(victim).PayloadBytes();
  if(payload>gStackKeyPayloadBytes)return false;
  gIndexed.QueuePop(IndexedStore::DEFENDER);gStackKeyPayloadBytes-=payload;gIndexed.Erase(victim);++gStackDefenderEvictions;return true;
 }
 return false;
}
static bool CanStoreStackForecast(const StackForecastKey& key)
{
 if(!gUseIndexed)return LegacyCanStoreStackForecast(key);
 if(!StackForecastContext())return false;
 const size_t payload=key.state.capacity()*sizeof(int);
 if(gStackEntryLimit==0||payload>gStackKeyPayloadLimit){++gStackInsertBypasses;return false;}
 while(gIndexed.Total()>=gStackEntryLimit||payload>gStackKeyPayloadLimit-gStackKeyPayloadBytes)
  if(!EvictOldestStackForecast()){++gStackInsertBypasses;return false;}
 return true;
}
static size_t EstimatedStackForecastBytes()
{
 if(!gUseIndexed)return LegacyEstimatedStackForecastBytes();
 // The original empty fallback containers remain available throughout search.
 // This is requested-payload/container estimation, excluding heap bookkeeping.
 return gIndexed.ReservedBytes()+sizeof(gIndexed)+sizeof(gStackDangerForecasts)+sizeof(gStackDefenderForecasts)
  +(gStackDangerForecasts.bucket_count()+gStackDefenderForecasts.bucket_count()+2)*sizeof(void*)
  +sizeof(StackDangerForecasts::value_type)+sizeof(StackDefenderForecasts::value_type)+4*sizeof(void*)
  +sizeof(gStackDangerOrder)+sizeof(gStackDefenderOrder)+sizeof(gStackThreatFlags)
  +gStackThreatFlags.size()*(sizeof(StackThreatFlags::value_type)+4*sizeof(void*));
}
static void UpdateStackForecastPeaks()
{
 if(!gUseIndexed){LegacyUpdateStackForecastPeaks();return;}
 gStackPeakEntries=max(gStackPeakEntries,gIndexed.Total());
 gStackPeakKeyBytes=max(gStackPeakKeyBytes,gStackKeyPayloadBytes);
 gStackPeakEstimatedBytes=max(gStackPeakEstimatedBytes,EstimatedStackForecastBytes());
}
static void StoreStackDangerForecast(const StackForecastKey& key,int result)
{
 if(!gUseIndexed){LegacyStoreStackDangerForecast(key,result);return;}
 if(!CanStoreStackForecast(key))return;
 IndexedStore::Pending pending;StackDangerForecastValue value(result);pending.Assign(key,&value,NULL);
 bool inserted=false;int handle=gIndexed.Insert(key,pending,IndexedStore::DANGER,inserted);
 if(inserted)
 {
  const size_t payload=gIndexed.At(handle).PayloadBytes();
  if(payload<=gStackKeyPayloadLimit-gStackKeyPayloadBytes)
  {gStackKeyPayloadBytes+=payload;gIndexed.QueuePush(handle);UpdateStackForecastPeaks();}
  else{gIndexed.Erase(handle);++gStackInsertBypasses;}
 }
}
static void StoreStackDangerPacketForecast(const StackForecastKey& key,const StackDangerForecastValue& value)
{
 if(!gUseIndexed){LegacyStoreStackDangerPacketForecast(key,value);return;}
 if(!StackForecastContext())return;
 if(key.state.size()%2==0||value.memberScores.size()<2||gStackEntryLimit==0){++gStackInsertBypasses;return;}
 if(gIndexed.Find(key,IndexedStore::DANGER)!=-1)return;
 const unsigned long revision=gStackForecastRevision;const long scene=gStackForecastSceneEpoch;
 IndexedStore::Pending pending;pending.Assign(key,&value,NULL);
 if(pending.keyWords>gStackKeyPayloadLimit/sizeof(int)){++gStackInsertBypasses;return;}
 const size_t copiedKeyBytes=pending.keyWords*sizeof(int);
 if(pending.members>(gStackKeyPayloadLimit-copiedKeyBytes)/sizeof(pair<int,int>)){++gStackInsertBypasses;return;}
 if(!StackForecastContext()||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch){++gStackInsertBypasses;return;}
 bool inserted=false;int handle=gIndexed.Insert(key,pending,IndexedStore::DANGER,inserted);
 if(!inserted)return;
 if(!gStackForecastsActive||gStackForecastDepth!=1||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch||scene!=CvStackingStrengthCache::SceneEpoch())
 {gIndexed.Erase(handle);++gStackInsertBypasses;return;}
 const IndexedStore::Slot& stored=gIndexed.At(handle);
 if(stored.keyWords>gStackKeyPayloadLimit/sizeof(int)){gIndexed.Erase(handle);++gStackInsertBypasses;return;}
 const size_t keyBytes=stored.keyWords*sizeof(int);
 if(stored.members>(gStackKeyPayloadLimit-keyBytes)/sizeof(pair<int,int>)){gIndexed.Erase(handle);++gStackInsertBypasses;return;}
 const size_t payload=stored.PayloadBytes();
 while(gIndexed.Total()>gStackEntryLimit||payload>gStackKeyPayloadLimit-gStackKeyPayloadBytes)
  if(!EvictOldestStackForecast()){gIndexed.Erase(handle);++gStackInsertBypasses;return;}
 try{gIndexed.QueuePush(handle);}
 catch(...){gIndexed.Erase(handle);throw;}
 gStackKeyPayloadBytes+=payload;UpdateStackForecastPeaks();
}
static void StoreStackDefenderForecast(const StackForecastKey& key,const CvUnit* result)
{
 if(!gUseIndexed){LegacyStoreStackDefenderForecast(key,result);return;}
 if(!CanStoreStackForecast(key))return;
 IndexedStore::Pending pending;pending.Assign(key,NULL,result);
 bool inserted=false;int handle=gIndexed.Insert(key,pending,IndexedStore::DEFENDER,inserted);
 if(inserted)
 {
  const size_t payload=gIndexed.At(handle).PayloadBytes();
  if(payload<=gStackKeyPayloadLimit-gStackKeyPayloadBytes)
  {gStackKeyPayloadBytes+=payload;gIndexed.QueuePush(handle);UpdateStackForecastPeaks();}
  else{gIndexed.Erase(handle);++gStackInsertBypasses;}
 }
}

// Backend queries copy results before any caller validation can clear storage.
static size_t StackDangerForecastSize(){return gUseIndexed?gIndexed.Count(IndexedStore::DANGER):gStackDangerForecasts.size();}
static size_t StackDefenderForecastSize(){return gUseIndexed?gIndexed.Count(IndexedStore::DEFENDER):gStackDefenderForecasts.size();}
static bool FindStackDangerForecastScalar(const StackForecastKey& key,int& result)
{
 if(gUseIndexed){int handle=gIndexed.Find(key,IndexedStore::DANGER);if(handle==-1)return false;result=gIndexed.At(handle).scalar;return true;}
 StackDangerForecasts::const_iterator hit=gStackDangerForecasts.find(key);
 if(hit==gStackDangerForecasts.end())return false;result=hit->second.scalar;return true;
}
static bool FindStackDangerForecastMember(const StackForecastKey& key,const CvUnit* unit,int& result)
{
 if(gUseIndexed)
 {
  int handle=gIndexed.Find(key,IndexedStore::DANGER);if(handle==-1)return false;
  const IndexedStore::Slot& slot=gIndexed.At(handle);
  for(size_t i=0;i<slot.members;++i)if(slot.Data()[slot.keyWords+2*i]==unit->GetID())
  {result=slot.Data()[slot.keyWords+2*i+1];return true;}
  return false;
 }
 StackDangerForecasts::const_iterator hit=gStackDangerForecasts.find(key);
 if(hit!=gStackDangerForecasts.end())for(size_t i=0;i<hit->second.memberScores.size();++i)
  if(hit->second.memberScores[i].first==unit->GetID()){result=hit->second.memberScores[i].second;return true;}
 return false;
}
static bool FindStackDefenderForecast(const StackForecastKey& key,const CvUnit*& result)
{
 if(gUseIndexed){int handle=gIndexed.Find(key,IndexedStore::DEFENDER);if(handle==-1)return false;result=gIndexed.At(handle).defender;return true;}
 StackDefenderForecasts::const_iterator hit=gStackDefenderForecasts.find(key);
 if(hit==gStackDefenderForecasts.end())return false;result=hit->second;return true;
}

static void AppendStackCandidates(StackForecastKey& key, const vector<const CvUnit*>& candidates, const SUnitIDValueContainer& damage, bool canonicalOrder = true)
{
 StackForecastPairQuery query;
 vector<pair<int, int> >& members=query.entries;
 members.reserve(candidates.size());
 for (size_t i = 0; i < candidates.size(); ++i)
  if (candidates[i])
   members.push_back(make_pair(candidates[i]->GetID(), damage.GetValue(candidates[i]->GetID())));
 // City garrison replacement uses candidate order for otherwise equal ties.
 // Preserve that order for danger; unit defender selection has an ID tie-break.
 if (canonicalOrder)
  std::sort(members.begin(), members.end());
 key.state.push_back((int)members.size());
 for (size_t i = 0; i < members.size(); ++i)
 {
  key.state.push_back(members[i].first);
  key.state.push_back(members[i].second);
 }
}

static void AppendStackDamage(StackForecastKey& key, const SUnitIDValueContainer& damage)
{
 StackForecastPairQuery query;
 vector<pair<int, int> >& entries=query.entries;
 for (SUnitIDValueContainer::const_iterator it = damage.begin(); it != damage.end(); ++it)
  if ((*it).second != 0)
   entries.push_back(make_pair((*it).first, (*it).second));
 std::sort(entries.begin(), entries.end());
 key.state.push_back((int)entries.size());
 for (size_t i = 0; i < entries.size(); ++i)
 {
  key.state.push_back(entries[i].first);
  key.state.push_back(entries[i].second);
 }
}

static void AppendStackDamageProjected(StackForecastKey& key, const SUnitIDValueContainer& damage,
 const CvUnit* unit, const CvPlot* plot)
{
 // The danger leaf reads only sources in this plot's attack-reach map. Raw
 // IDs preserve the existing owner aliases and negative city-ID convention;
 // retain every exact nonzero HP value for those sources, never a hash alone.
 const vector<int>* sourceIDs = GET_PLAYER(unit->getOwner()).GetDangerPlots()->GetStackDangerDamageIDs(*plot);
 if (AppendImmutableEnemyDamage(key, damage, sourceIDs))
  return;
 if (!sourceIDs)
 {
  AppendStackDamage(key, damage);
  return;
 }
 StackForecastPairQuery query;
 vector<pair<int, int> >& entries = query.entries;
 for (SUnitIDValueContainer::const_iterator it = damage.begin(); it != damage.end(); ++it)
 {
  const SUnitIDValueContainer::value_type entry = *it;
  if (entry.second != 0 && std::binary_search(sourceIDs->begin(), sourceIDs->end(), entry.first))
   entries.push_back(entry);
 }
 std::sort(entries.begin(), entries.end());
 key.state.push_back((int)entries.size());
 for (size_t i = 0; i < entries.size(); ++i)
 {
  key.state.push_back(entries[i].first);
  key.state.push_back(entries[i].second);
 }
}

// Bind immutable inputs only for this short helper call. Reuse sits behind
// scalar memo hits, so its key/FIFO admission and fast path remain unchanged.
// The capacity ceiling bounds retained local outcomes, not the temporary copy
// already required while simulating an original scalar leaf.
struct StackDangerOutcomeBatch
{
 const CvPlot* plot;
 const vector<const CvUnit*>& candidates;
 const SUnitIDValueContainer& friendlyDamage;
 const SUnitIDValueContainer& enemyDamage;
 SUnitIDValueContainer finalDamage;
 bool ready, building, cityCanFall, friendlyCity;
 PlayerTypes owner;
 TeamTypes team;
 unsigned long revision;
 long scene;
 size_t retainedBytes;
 StackDangerOutcomeBatch(const CvPlot* target, const vector<const CvUnit*>& members,
  const SUnitIDValueContainer& friendly, const SUnitIDValueContainer& enemy):
  plot(target),candidates(members),friendlyDamage(friendly),enemyDamage(enemy),
  ready(false),building(false),cityCanFall(false),friendlyCity(false),owner(NO_PLAYER),team(NO_TEAM),
  revision(0),scene(0),retainedBytes(0) {}
 ~StackDangerOutcomeBatch() { Release(); }
 void Release()
 {
  if (retainedBytes)
   gStackOutcomeCurrentBytes -= retainedBytes;
  retainedBytes = 0;
  ready = false;
  SUnitIDValueContainer empty;
  finalDamage.swap(empty);
 }
 bool TryGet(const CvUnit* unit, const CvPlot* target, const vector<const CvUnit*>& members,
  const SUnitIDValueContainer& friendly, const SUnitIDValueContainer& enemy, int& result)
 {
  // A foreign callback cannot touch an owning thread's payload or counters.
  if (!IsStackForecastOwner())
   return false;
  if (building)
  {
   ++gStackOutcomeBypasses;
   return false;
  }
  if (plot != target || &candidates != &members || &friendlyDamage != &friendly || &enemyDamage != &enemy ||
   !unit || !plot || !StackForecastContext() || MOD_EVENTS_CAN_MOVE_INTO)
  {
   if (IsStackForecastOwner()) ++gStackOutcomeBypasses;
   Release();
   return false;
  }
  CvDangerPlots* danger = GET_PLAYER(unit->getOwner()).GetDangerPlots();
  // Dirty refresh can rebuild source vectors and invalidate the current scene.
  if (danger->IsDirty())
   danger->GetStackDangerDamageIDs(*plot);
  if (!StackForecastContext())
  {
   ++gStackOutcomeBypasses;
   Release();
   return false;
  }
  const unsigned long currentRevision = gStackForecastRevision;
  const long currentScene = gStackForecastSceneEpoch;
  const PlayerTypes currentOwner = unit->getOwner();
  const TeamTypes currentTeam = unit->getTeam();
  const bool currentFriendlyCity = plot->isFriendlyCity(*unit);
  if (ready && revision == currentRevision && scene == currentScene && owner == currentOwner && team == currentTeam &&
   friendlyCity == currentFriendlyCity && danger->TryGetStackDangerFromOutcome(*plot, unit, friendlyDamage, finalDamage, cityCanFall, result))
  {
   ++gStackOutcomeReuses;
   if (!StackForecastContext() || revision != gStackForecastRevision || scene != gStackForecastSceneEpoch)
    Release();
   return true;
  }
  Release();
  building = true;
  ++gStackOutcomeBuilds;
  const bool computed = danger->GetStackDangerOutcome(*plot, unit, candidates, friendlyDamage, enemyDamage, finalDamage, cityCanFall, result);
  building = false;
  const size_t bytes = finalDamage.m_aExtraStorage.capacity() * sizeof(SUnitIDValueContainer::value_type);
  ready = computed && StackForecastContext() && currentRevision == gStackForecastRevision && currentScene == gStackForecastSceneEpoch &&
   gStackOutcomeCurrentBytes <= gStackKeyPayloadLimit && bytes <= gStackKeyPayloadLimit - gStackOutcomeCurrentBytes;
  if (ready)
  {
   revision = currentRevision; scene = currentScene;
   owner = currentOwner; team = currentTeam; friendlyCity = currentFriendlyCity;
   retainedBytes = bytes;
   gStackOutcomeCurrentBytes += bytes;
   gStackOutcomePeakBytes = max(gStackOutcomePeakBytes, gStackOutcomeCurrentBytes);
  }
  else
  {
   ++gStackOutcomeBypasses;
   Release();
  }
  // Even if invalidated after the build, return this call's computed value once.
  // Repeating the simulation here would duplicate scripted or engine callbacks.
  return computed;
 }
private:
 StackDangerOutcomeBatch(const StackDangerOutcomeBatch&);
 StackDangerOutcomeBatch& operator=(const StackDangerOutcomeBatch&);
};

// Exact shared packet keys and outcome resolution after ordinary scalar hits.
static bool AppendUniquePacketDamage(StackForecastKey* key,const SUnitIDValueContainer& damage)
{
 StackForecastPairQuery query;vector<pair<int,int> >& entries=query.entries;
 for(SUnitIDValueContainer::const_iterator i=damage.begin();i!=damage.end();++i)entries.push_back(*i);
 std::sort(entries.begin(),entries.end());
 int nonzero=0;
 for(size_t i=0;i<entries.size();++i)
 {
  if(i&&entries[i-1].first==entries[i].first)return false;
  if(entries[i].second)++nonzero;
 }
 if(key){key->state.push_back(nonzero);for(size_t i=0;i<entries.size();++i)if(entries[i].second){key->state.push_back(entries[i].first);key->state.push_back(entries[i].second);}}
 return true;
}
static bool StackPacketSourcesHaveNoLoadingCallback(const vector<int>& source)
{
 // Custom air melee can enter canEnterTerrain -> canLoad -> CanLoadAt, whose
 // fallback Lua hook is independent of CAN_MOVE_INTO/CITY_BOMBARD flags.
 // Standard ranged aircraft do not use that ground-attack legality route.
 if(source.size()<6||source[0]!=1||source[4]<0||(size_t)source[4]>(source.size()-6)/2)return false;
 for(int i=0;i<source[4];++i)
 {
  const CvUnit* threat=GET_PLAYER((PlayerTypes)source[5+2*i]).getUnit(source[6+2*i]);
  if(threat&&threat->getDomainType()==DOMAIN_AIR&&!threat->IsCanAttackRanged())return false;
 }
 return true;
}
static bool PrepareStackDangerPacket(StackDangerPacketQuery& query,const CvUnit* unit,const CvPlot* plot,
 const vector<const CvUnit*>& roster,const SUnitIDValueContainer& friendly,const SUnitIDValueContainer& enemy,const StackForecastKey& legacy)
{
 if(!query.borrowed||MOD_EVENTS_CAN_MOVE_INTO||MOD_EVENTS_CITY_BOMBARD||!unit||!plot||!unit->IsCombatUnit()||!unit->isNativeDomain(plot)||
  legacy.state.size()<6||legacy.state.size()%2)return false;
 StackDangerPacketBuffer& b=query.buffer;const bool city=plot->isFriendlyCity(*unit);bool found=false;
 for(size_t i=0;i<roster.size();++i)
 {
  const CvUnit* member=roster[i];
  if(!member||member->getOwner()!=unit->getOwner()||member->getTeam()!=unit->getTeam()||member->getDomainType()!=unit->getDomainType()||!member->IsCombatUnit()||!member->isNativeDomain(plot)||
   plot->isFriendlyCity(*member)!=city||GET_PLAYER(member->getOwner()).getUnit(member->GetID())!=member)return false;
  found|=member==unit;if(std::find(b.members.begin(),b.members.end(),member)==b.members.end())b.members.push_back(member);
 }
 if(!found||b.members.size()<2)return false;
 const int count=legacy.state[4];if(count<0||(size_t)count!=roster.size()||(size_t)count>(legacy.state.size()-5)/2)return false;
 const size_t suffix=5+2*(size_t)count;
 if(suffix>=legacy.state.size()||legacy.state[suffix]<0||legacy.state.size()-suffix!=1+2*(size_t)legacy.state[suffix])return false;
 // Scalars: 6+2*N (even). Complete packets: 15+2*N (odd), deliberately
 // disjoint without adding a kind/hash field to millions of scalar hits.
 b.key.state.push_back(unit->getOwner());b.key.state.push_back(unit->getTeam());b.key.state.push_back(plot->GetPlotIndex());
 b.key.state.push_back(city?1:0);b.key.state.push_back((int)roster.size());
 b.key.state.push_back(legacy.state[3]);b.key.state.push_back(plot->getPlotCity()?plot->getPlotCity()->getDamage():-1);
 for(size_t i=0;i<roster.size();++i){b.key.state.push_back(roster[i]->getOwner());b.key.state.push_back(roster[i]->GetID());}
 if(!AppendUniquePacketDamage(&b.key,friendly)||!AppendUniquePacketDamage(NULL,enemy))return false;
 const CvDangerPlots* map=GET_PLAYER(unit->getOwner()).GetDangerPlots();unsigned used=0;
 if(!map->AppendStackDangerCacheDescriptor(*plot,b.descriptor,sizeof(b.descriptor)/sizeof(b.descriptor[0]),used))return false;
 b.source.assign(b.descriptor,b.descriptor+used);b.key.state.insert(b.key.state.end(),b.source.begin(),b.source.end());
 if(!StackPacketSourcesHaveNoLoadingCallback(b.source))return false;
 b.key.state.insert(b.key.state.end(),legacy.state.begin()+suffix,legacy.state.end());
 return b.key.state.size()%2&&b.key.state.size()<=gStackKeyPayloadLimit/sizeof(int);
}
static bool ValidateStackDangerPacket(StackDangerPacketQuery& query,const CvUnit* unit,const CvPlot* plot,
 unsigned long revision,long scene)
{
 if(!StackForecastContext()||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch||scene!=CvStackingStrengthCache::SceneEpoch()||
  MOD_EVENTS_CAN_MOVE_INTO||MOD_EVENTS_CITY_BOMBARD)return false;
 StackDangerPacketBuffer& b=query.buffer;const CvDangerPlots* map=GET_PLAYER(unit->getOwner()).GetDangerPlots();
 if(map->IsDirty()||b.key.state.size()<7||CvStacking::GetCityProtection(plot->getPlotCity())!=b.key.state[5]||
  (plot->getPlotCity()?plot->getPlotCity()->getDamage():-1)!=b.key.state[6])return false;
 unsigned used=0;if(!map->AppendStackDangerCacheDescriptor(*plot,b.descriptor,sizeof(b.descriptor)/sizeof(b.descriptor[0]),used)||used!=b.source.size())return false;
 if(!std::equal(b.source.begin(),b.source.end(),b.descriptor)||!StackPacketSourcesHaveNoLoadingCallback(b.source))return false;
 // Descriptor/source-unit getters are additional preparation work. Recheck
 // the owning scene after them, before using an iterator or admitting values.
 return StackForecastContext()&&revision==gStackForecastRevision&&scene==gStackForecastSceneEpoch&&scene==CvStackingStrengthCache::SceneEpoch();
}
static bool ResolveStackDangerPacket(StackDangerPacketQuery& query,const CvUnit* unit,const CvPlot* plot,
 const vector<const CvUnit*>& roster,const SUnitIDValueContainer& friendly,const SUnitIDValueContainer& enemy,
 const StackForecastKey& legacy,unsigned long revision,long scene,StackDangerOutcomeBatch* outcome,int& result)
{
 if(!PrepareStackDangerPacket(query,unit,plot,roster,friendly,enemy,legacy))return false;
 if(!ValidateStackDangerPacket(query,unit,plot,revision,scene))return false;
 StackDangerPacketBuffer& b=query.buffer;
 int cachedResult=0;
 if(FindStackDangerForecastMember(b.key,unit,cachedResult))
 {
  // The backend copied the integer before validation may clear storage.
  if(!ValidateStackDangerPacket(query,unit,plot,revision,scene))return false;
  result=cachedResult;query.scalarValid=true;++gStackPacketHits;return true;
 }
 CvDangerPlots* map=GET_PLAYER(unit->getOwner()).GetDangerPlots();
 SUnitIDValueContainer localFinal;const SUnitIDValueContainer* finalDamage=NULL;bool cityCanFall=false,computed=false;
 if(outcome)
 {
  computed=outcome->TryGet(unit,plot,roster,friendly,enemy,result);
  if(computed)
  {
   // The lexical batch already supplies subsequent member queries. Retain
   // this one value and its queried scalar entry without seeding a packet.
   // Released/invalidated builds must never replay their original math.
   query.scalarValid=ValidateStackDangerPacket(query,unit,plot,revision,scene);
   if(!outcome->ready||!query.scalarValid)++gStackPacketBypasses;
   return true;
  }
 }
 if(!computed)
 {
  ++gStackPacketBuilds;++gStackOutcomeBuilds;
  computed=map->GetStackDangerOutcome(*plot,unit,roster,friendly,enemy,localFinal,cityCanFall,result);finalDamage=&localFinal;
 }
 if(!computed)return false; // The native false-return contract computes no leaf.
 if(!ValidateStackDangerPacket(query,unit,plot,revision,scene)){++gStackPacketBypasses;return true;}
 b.value.scalar=result;
 for(size_t i=0;i<b.members.size();++i)
 {
  int memberResult=result;
  if(b.members[i]!=unit&&!map->TryGetStackDangerFromOutcome(*plot,b.members[i],friendly,*finalDamage,cityCanFall,memberResult))
  {++gStackPacketBypasses;return true;}
  b.value.memberScores.push_back(make_pair(b.members[i]->GetID(),memberResult));
 }
 if(ValidateStackDangerPacket(query,unit,plot,revision,scene)){query.storePacket=true;query.scalarValid=true;}
 else ++gStackPacketBypasses;
 return true;
}

// BEGIN PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
// Metadata only: no result/assignment/cache admission reads these fields.
enum { PACKET_PROBE_SLOTS=128, PACKET_PROBE_WORDS=512, PACKET_PROBE_PAIRS=128 };
struct PacketProbeSlot
{
 bool used,city;
 unsigned count;
 unsigned long hash,seen,fresh;
 unsigned outputUpper;
 int words[PACKET_PROBE_WORDS];
};
struct PacketProbeState
{
 PacketProbeSlot slots[PACKET_PROBE_SLOTS];
 int key[PACKET_PROBE_WORDS],source[PACKET_PROBE_WORDS];
 unsigned count,sourceStart,sourceCount,next;
 unsigned long serial,thread,revision;
 long epoch,scene;
 PlayerTypes actor;
 int target;
 bool busy;
 unsigned __int64 misses,prefilter,cohort,groups,repeats,sameMember,crossMember;
 unsigned __int64 freshQueries,batchReuseQueries,packetResultReuseQueries,freshRepeatQueries,freshCrossMemberQueries;
 unsigned __int64 rawCalls,outcomeBuildAttempts;
 unsigned __int64 fallback,oversized,unavailable,invalidated,reentrant,evictions,clears;
 unsigned __int64 fieldGroups,cityGroups,keyBytes,peakKeyBytes,outputUpperBytes,peakOutputUpperBytes;
 PacketProbeState():count(0),sourceStart(0),sourceCount(0),next(0),serial(0),thread(0),revision(0),epoch(0),scene(0),actor(NO_PLAYER),target(-1),busy(false),
  misses(0),prefilter(0),cohort(0),groups(0),repeats(0),sameMember(0),crossMember(0),freshQueries(0),batchReuseQueries(0),packetResultReuseQueries(0),freshRepeatQueries(0),freshCrossMemberQueries(0),rawCalls(0),outcomeBuildAttempts(0),
  fallback(0),oversized(0),unavailable(0),invalidated(0),reentrant(0),evictions(0),clears(0),fieldGroups(0),cityGroups(0),keyBytes(0),peakKeyBytes(0),outputUpperBytes(0),peakOutputUpperBytes(0)
 { for(unsigned i=0;i<PACKET_PROBE_SLOTS;++i)slots[i].used=false; }
 void Clear(){for(unsigned i=0;i<PACKET_PROBE_SLOTS;++i)slots[i].used=false;next=0;keyBytes=outputUpperBytes=0;++clears;}
 bool Add(int value){if(count==PACKET_PROBE_WORDS)return false;key[count++]=value;return true;}
};
static __declspec(thread) PacketProbeState* gPacketProbeState=NULL;
static unsigned long PacketProbeMix(unsigned long value)
{ value^=value>>16;value*=0x7feb352dUL;value^=value>>15;value*=0x846ca68bUL;value^=value>>16;return value; }
static unsigned long PacketProbeHash(const int* words,unsigned count,unsigned long seed)
{ for(unsigned i=0;i<count;++i)seed^=(unsigned long)words[i]+0x9e3779b9UL+(seed<<6)+(seed>>2);return PacketProbeMix(seed); }
static bool PacketProbeUnique(const SUnitIDValueContainer& damage)
{
 int ids[PACKET_PROBE_PAIRS];unsigned count=0;
 for(SUnitIDValueContainer::const_iterator i=damage.begin();i!=damage.end();++i)
 {if(count==PACKET_PROBE_PAIRS)return false;int id=(*i).first;for(unsigned j=0;j<count;++j)if(ids[j]==id)return false;ids[count++]=id;}
 return true;
}
static bool PacketProbeDamage(PacketProbeState& state,const SUnitIDValueContainer& damage)
{
 pair<int,int> pairs[PACKET_PROBE_PAIRS];unsigned count=0;
 for(SUnitIDValueContainer::const_iterator i=damage.begin();i!=damage.end();++i)
 {if(count==PACKET_PROBE_PAIRS)return false;const SUnitIDValueContainer::value_type entry=*i;if(entry.second)pairs[count++]=entry;}
 std::sort(pairs,pairs+count);if(!state.Add((int)count))return false;
 for(unsigned i=0;i<count;++i)if(!state.Add(pairs[i].first)||!state.Add(pairs[i].second))return false;
 return true;
}
struct PacketProbeScope
{
 PacketProbeState* state;
 const void* threadState;
 PacketProbeScope(PlayerTypes actor,int target):state(NULL),threadState(&gPacketProbeState)
 {
  unsigned long serial=0;long epoch=0;
  if(gPacketProbeState||!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch))return;
  // Check once after the disabled TLS gate, before any owner-only shared reads.
  if(!IsStackForecastOwner()||!gStackForecastsActive||gStackForecastDepth!=1||MOD_EVENTS_CAN_MOVE_INTO)return;
  // A hard diagnostic bound, independent of every gameplay/result-cache cap.
  if(sizeof(PacketProbeState)>3*1024*1024)return;
  state=new(std::nothrow)PacketProbeState;if(!state)return;
  state->serial=serial;state->epoch=epoch;state->actor=actor;state->target=target;state->thread=GetCurrentThreadId();
  state->revision=gStackForecastRevision;state->scene=gStackForecastSceneEpoch;gPacketProbeState=state;
 }
 ~PacketProbeScope(){Finish();}
 void Finish()
 {
  if(!state||threadState!=&gPacketProbeState||gPacketProbeState!=state)return;
  PacketProbeState* done=state;state=NULL;gPacketProbeState=NULL;
  unsigned long serial=0;long epoch=0;
  if(CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)&&serial==done->serial&&epoch==done->epoch)
   CvStackingDiagnostics::Record(1,done->actor,"PLAN_PACKET_PROBE",
    "targetPlot=%d serial=%lu thread=%lu version=2 prefilterBits=2 cohortBits=3 slots=128 maxKeyWords=512 metadataBytes=%u misses=%I64u prefiltered=%I64u cohortQueries=%I64u groups=%I64u repeats=%I64u sameMember=%I64u crossMember=%I64u freshQueries=%I64u batchReuseQueries=%I64u packetResultReuseQueries=%I64u freshRepeatQueries=%I64u freshCrossMemberQueries=%I64u rawCalls=%I64u outcomeBuildAttempts=%I64u fieldGroups=%I64u cityGroups=%I64u fallback=%I64u oversized=%I64u sourceUnavailable=%I64u invalidated=%I64u reentrant=%I64u evictions=%I64u clears=%I64u keyBytes=%I64u peakKeyBytes=%I64u outputUpperBytes=%I64u peakOutputUpperBytes=%I64u; metadata cohorts are censored by sampling/bounds/eviction; fresh fields count queries, build attempts may fail; no stride-scaled saved simulations; output bytes are an upper estimate, not actual retained capacity",
    done->target,done->serial,done->thread,(unsigned)sizeof(PacketProbeState),done->misses,done->prefilter,done->cohort,done->groups,done->repeats,done->sameMember,done->crossMember,
    done->freshQueries,done->batchReuseQueries,done->packetResultReuseQueries,done->freshRepeatQueries,done->freshCrossMemberQueries,done->rawCalls,done->outcomeBuildAttempts,done->fieldGroups,done->cityGroups,done->fallback,done->oversized,done->unavailable,done->invalidated,done->reentrant,
    done->evictions,done->clears,done->keyBytes,done->peakKeyBytes,done->outputUpperBytes,done->peakOutputUpperBytes);
  delete done;
 }
private:PacketProbeScope(const PacketProbeScope&);PacketProbeScope&operator=(const PacketProbeScope&);
};
struct PacketProbeCall
{
 PacketProbeState* state;
 const void* threadState;
 const CvDangerPlots* danger;
 const CvPlot* plot;
 unsigned member,outputUpper;
 unsigned long beforeBuilds,beforePacketHits,revision;
 long scene;
 bool raw,city;
 PacketProbeCall(const CvUnit* unit,const CvPlot* target,const vector<const CvUnit*>& roster,
  const SUnitIDValueContainer& friendly,const SUnitIDValueContainer& enemy,const StackForecastKey& scalarKey,bool eligible):
  state(NULL),threadState(&gPacketProbeState),danger(NULL),plot(target),member(0),outputUpper(0),beforeBuilds(0),beforePacketHits(0),revision(0),scene(0),raw(false),city(false)
 {
  PacketProbeState* active=gPacketProbeState;unsigned long serial=0;long epoch=0;
  if(!active||!eligible)return;
  if(!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)||serial!=active->serial||epoch!=active->epoch)return;
  ++active->misses;if(active->busy){++active->reentrant;return;}
  if(active->revision!=gStackForecastRevision||active->scene!=gStackForecastSceneEpoch)
  {active->Clear();active->revision=gStackForecastRevision;active->scene=gStackForecastSceneEpoch;}
  if(scalarKey.state.size()<5){++active->fallback;return;}
  const unsigned long salt=PacketProbeMix(active->serial*2246822519UL+(unsigned long)active->scene+active->revision*3266489917UL);
  unsigned long hash=salt;
  // Equal supported full packet keys imply this same scalar tail. Omit only
  // query-ID and own-wound prefix; malformed injury storage is unsupported.
  for(size_t i=1;i<scalarKey.state.size();++i)if(i!=2)hash^=(unsigned long)scalarKey.state[i]+0x9e3779b9UL+(hash<<6)+(hash>>2);
  if(PacketProbeMix(hash)&3UL)return;++active->prefilter;
  if(!unit||!target||!unit->IsCombatUnit()||!unit->isNativeDomain(target)||roster.size()<2||!PacketProbeUnique(friendly)||!PacketProbeUnique(enemy))
  {++active->fallback;return;}
  const CvUnit* unique[32];unsigned uniques=0;bool found=false;
  for(size_t i=0;i<roster.size();++i)
  {
   const CvUnit* u=roster[i];
   if(!u||u->getOwner()!=unit->getOwner()){++active->fallback;return;}
   const CvPlayer& owner=GET_PLAYER(u->getOwner());if(owner.getUnit(u->GetID())!=u){++active->fallback;return;}
   unsigned j=0;for(;j<uniques;++j)if(unique[j]==u)break;
   if(j==uniques){if(uniques==32){++active->oversized;return;}unique[uniques++]=u;}
   if(u==unit){member=j;found=true;}
  }
  if(!found||uniques<2){++active->fallback;return;}
  active->count=0;city=target->isFriendlyCity(*unit);
  if(!active->Add(unit->getOwner())||!active->Add(unit->getTeam())||!active->Add(target->GetPlotIndex())||!active->Add(city?1:0)||!active->Add((int)roster.size())){++active->oversized;return;}
  for(size_t i=0;i<roster.size();++i)if(!active->Add(roster[i]->getOwner())||!active->Add(roster[i]->GetID())){++active->oversized;return;}
  if(!PacketProbeDamage(*active,friendly)){++active->oversized;return;}
  danger=GET_PLAYER(unit->getOwner()).GetDangerPlots();active->sourceStart=active->count;
  if(!danger||!danger->AppendStackDangerProbeSources(*target,active->key,PACKET_PROBE_WORDS,active->count)){++active->unavailable;return;}
  active->sourceCount=active->count-active->sourceStart;
  // The original scalar key has already freshly projected enemy injuries.
  const unsigned rosterWords=(unsigned)scalarKey.state[4];
  if(rosterWords!=roster.size()||rosterWords>(scalarKey.state.size()-5)/2){++active->fallback;return;}
  const size_t suffix=5+2*rosterWords;
  if(suffix>=scalarKey.state.size()||scalarKey.state[suffix]<0||scalarKey.state.size()-suffix!=1+2*(size_t)scalarKey.state[suffix]){++active->fallback;return;}
  for(size_t i=suffix;i<scalarKey.state.size();++i)if(!active->Add(scalarKey.state[i])){++active->oversized;return;}
  if(PacketProbeHash(active->key,active->count,salt^0xa5a5a5a5UL)&7UL)return;
  // Union of input-stored IDs and roster IDs bounds a copied final-ledger size;
  // it is not a measured vector capacity or a predicted packet residency cost.
  int ids[PACKET_PROBE_PAIRS+32];unsigned unions=0;
  for(SUnitIDValueContainer::const_iterator i=friendly.begin();i!=friendly.end();++i)ids[unions++]=(*i).first;
  for(unsigned i=0;i<uniques;++i){unsigned j=0;for(;j<unions;++j)if(ids[j]==unique[i]->GetID())break;if(j==unions)ids[unions++]=unique[i]->GetID();}
  outputUpper=unions*sizeof(SUnitIDValueContainer::value_type);
  ++active->cohort;active->busy=true;state=active;revision=gStackForecastRevision;scene=gStackForecastSceneEpoch;beforeBuilds=gStackOutcomeBuilds;beforePacketHits=gStackPacketHits;
 }
 void MarkRaw(){raw=true;}
 ~PacketProbeCall(){Finish();}
 void Finish()
 {
  if(!state||threadState!=&gPacketProbeState||gPacketProbeState!=state)return;
  PacketProbeState* done=state;state=NULL;done->busy=false;
  unsigned long serial=0;long epoch=0;unsigned used=0;
  if(!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)||serial!=done->serial||epoch!=done->epoch||gStackForecastDepth!=1||
   revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch||scene!=CvStackingStrengthCache::SceneEpoch()||
   !danger->AppendStackDangerProbeSources(*plot,done->source,PACKET_PROBE_WORDS,used)||used!=done->sourceCount||
   std::memcmp(done->source,done->key+done->sourceStart,used*sizeof(int))){++done->invalidated;return;}
  const unsigned long attempts=gStackOutcomeBuilds-beforeBuilds;
  done->rawCalls+=raw?1:0;done->outcomeBuildAttempts+=attempts;
  const bool fresh=raw||attempts!=0;
  if(fresh)++done->freshQueries;else if(gStackPacketHits!=beforePacketHits)++done->packetResultReuseQueries;else ++done->batchReuseQueries;
  const unsigned long hash=PacketProbeHash(done->key,done->count,0);
  unsigned selected=PACKET_PROBE_SLOTS;
  for(unsigned i=0;i<PACKET_PROBE_SLOTS;++i)if(done->slots[i].used&&done->slots[i].hash==hash&&done->slots[i].count==done->count&&
   !std::memcmp(done->slots[i].words,done->key,done->count*sizeof(int))){selected=i;break;}
  bool repeat=selected!=PACKET_PROBE_SLOTS;
  if(!repeat)
  {
   selected=done->next;done->next=(done->next+1)%PACKET_PROBE_SLOTS;PacketProbeSlot& s=done->slots[selected];
   if(s.used){done->keyBytes-=s.count*sizeof(int);done->outputUpperBytes-=s.outputUpper;++done->evictions;}
   s.used=true;s.city=city;s.count=done->count;s.hash=hash;s.seen=s.fresh=0;s.outputUpper=outputUpper;std::memcpy(s.words,done->key,done->count*sizeof(int));
   done->keyBytes+=s.count*sizeof(int);done->peakKeyBytes=std::max(done->peakKeyBytes,done->keyBytes);++done->groups;if(city)++done->cityGroups;else ++done->fieldGroups;
   done->outputUpperBytes+=outputUpper;done->peakOutputUpperBytes=std::max(done->peakOutputUpperBytes,done->outputUpperBytes);
  }
  PacketProbeSlot& s=done->slots[selected];const unsigned long bit=1UL<<member;
  if(repeat){++done->repeats;if(s.seen&bit)++done->sameMember;else ++done->crossMember;}
  if(fresh&&s.fresh){++done->freshRepeatQueries;if(!(s.fresh&bit))++done->freshCrossMemberQueries;}
  s.seen|=bit;if(fresh)s.fresh|=bit;
 }
private:PacketProbeCall(const PacketProbeCall&);PacketProbeCall&operator=(const PacketProbeCall&);
};
// END PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY

// BEGIN DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
// Observe original destination kernels. This metadata NEVER returns a score,
// admits a forecast, changes a candidate or substitutes for original work.
enum { KERNEL_PROBE_SLOTS=128,KERNEL_PROBE_WORDS=2048,KERNEL_PROBE_PARTICIPANTS=128,KERNEL_PROBE_SOURCE_WORDS=512,KERNEL_PROBE_STRIDE=64,KERNEL_PROBE_STATES=8192,KERNEL_PROBE_STATE_LOOKUP_LIMIT=64 };
struct DestinationKernelProbeSlot
{
 bool used;unsigned count,kind;unsigned long hash;int result;
 unsigned __int64 incarnation;
 int words[KERNEL_PROBE_WORDS];
};
struct DestinationKernelProbeCounts
{
 unsigned __int64 calls,selected,complete,groups,repeats,sameState,crossState,parentChild,unknownRelation,mismatches,zeroKeys;
 unsigned __int64 keyVisits,scalarHits,scalarMisses,outcomeBuilds,prepInsideTicks,prepOutsideTicks,kernelTicks;
 DestinationKernelProbeCounts():calls(0),selected(0),complete(0),groups(0),repeats(0),sameState(0),crossState(0),parentChild(0),unknownRelation(0),mismatches(0),zeroKeys(0),keyVisits(0),scalarHits(0),scalarMisses(0),outcomeBuilds(0),prepInsideTicks(0),prepOutsideTicks(0),kernelTicks(0){}
};
struct DestinationKernelStateIncarnation{const CvTacticalPosition* state;unsigned __int64 incarnation,parent;DestinationKernelStateIncarnation():state(NULL),incarnation(0),parent(0){}};
struct DestinationKernelProbeState
{
 DestinationKernelProbeSlot slots[KERNEL_PROBE_SLOTS];DestinationKernelProbeCounts kinds[2];
 DestinationKernelStateIncarnation states[KERNEL_PROBE_STATES];unsigned __int64 nextIncarnation,unknownStates;
 int words[KERNEL_PROBE_WORDS],beforeSource[KERNEL_PROBE_SOURCE_WORDS],afterSource[KERNEL_PROBE_SOURCE_WORDS];
 const CvUnit* participants[KERNEL_PROBE_PARTICIPANTS];unsigned participantOffsets[KERNEL_PROBE_PARTICIPANTS];
 unsigned count,sourceCount,participantCount,next;bool busy;
 unsigned long serial,revision;long epoch,scene;PlayerTypes owner;int target;
 unsigned __int64 frequency,evictions,clears,oversized,unavailable,invalidated,nested,allocationFailed,keyBytes,peakKeyBytes;
 DestinationKernelProbeState():nextIncarnation(0),unknownStates(0),count(0),sourceCount(0),participantCount(0),next(0),busy(false),serial(0),revision(0),epoch(0),scene(0),owner(NO_PLAYER),target(-1),frequency(0),evictions(0),clears(0),oversized(0),unavailable(0),invalidated(0),nested(0),allocationFailed(0),keyBytes(0),peakKeyBytes(0)
 {for(unsigned i=0;i<KERNEL_PROBE_SLOTS;++i)slots[i].used=false;}
 void Clear(){for(unsigned i=0;i<KERNEL_PROBE_SLOTS;++i)slots[i].used=false;next=0;keyBytes=0;++clears;}
 bool Add(int v){if(count==KERNEL_PROBE_WORDS)return false;words[count++]=v;return true;}
};
typedef char DestinationKernelProbeMetadataBound[sizeof(DestinationKernelProbeState)<=3*1024*1024?1:-1];
static __declspec(thread) DestinationKernelProbeState* gDestinationKernelProbe=NULL;
struct DestinationKernelProbeFrame;
static __declspec(thread) DestinationKernelProbeFrame* gDestinationKernelFrame=NULL;
static unsigned long KernelProbeHash(const int* words,unsigned count,unsigned long seed=0)
{for(unsigned i=0;i<count;++i)seed^=(unsigned long)words[i]+0x9e3779b9UL+(seed<<6)+(seed>>2);seed^=seed>>16;seed*=0x7feb352dUL;seed^=seed>>15;seed*=0x846ca68bUL;return seed^(seed>>16);}
static DestinationKernelStateIncarnation* KernelProbeIncarnation(DestinationKernelProbeState& probe,const CvTacticalPosition* position)
{
 if(!position)return NULL;const int pointer=(int)(size_t)position;const unsigned bucket=KernelProbeHash(&pointer,1)&(KERNEL_PROBE_STATES-1);
 for(unsigned i=0;i<KERNEL_PROBE_STATE_LOOKUP_LIMIT;++i)
 {DestinationKernelStateIncarnation& slot=probe.states[(bucket+i)&(KERNEL_PROBE_STATES-1)];if(slot.state==position)return &slot;if(!slot.state){slot.state=position;slot.incarnation=++probe.nextIncarnation;return &slot;}}
 ++probe.unknownStates;return NULL;
}
// Reused stack temporaries and rejected position slots can share their old
// address, ID and generation. Explicit reset/mutation hooks give each a fresh
// diagnostic token; these tokens never participate in gameplay or equality.
static inline void ObserveKernelStateMutation(const CvTacticalPosition* position,const CvTacticalPosition* parent)
{
 DestinationKernelProbeState* probe=gDestinationKernelProbe;if(!probe)return;
 DestinationKernelStateIncarnation* slot=KernelProbeIncarnation(*probe,position);if(!slot)return;
 DestinationKernelStateIncarnation* ancestor=KernelProbeIncarnation(*probe,parent);
 slot->incarnation=++probe->nextIncarnation;slot->parent=ancestor?ancestor->incarnation:0;
}
static unsigned __int64 KernelProbeTick(){LARGE_INTEGER tick;if(!QueryPerformanceCounter(&tick)||tick.QuadPart<0)return 0;return(unsigned __int64)tick.QuadPart;}
static unsigned __int64 KernelProbeElapsed(unsigned __int64 a,unsigned __int64 b){return a&&b>=a?b-a:0;}
// Direct values deliberately strengthen the old scalar keys. This is still
// an observed footprint, NOT certification of every deeper combat dependency.
static unsigned KernelProbeUnitWords(const CvUnit* unit,int* values)
{
 if(!unit)return 0;
 values[0]=(int)(size_t)unit;values[1]=unit->getOwner();values[2]=unit->getTeam();values[3]=unit->GetID();
 values[4]=unit->getDomainType();values[5]=unit->GetCurrHitPoints();values[6]=unit->GetMaxHitPoints();
 values[7]=unit->IsCombatUnit()?1:0;values[8]=unit->isCargo()?1:0;values[9]=unit->isDelayedDeath()?1:0;
 values[10]=unit->IsCanAttackRanged()?1:0;values[11]=unit->IsCanDefend()?1:0;values[12]=CvStacking::IsAntiCavalry(unit)?1:0;
 values[13]=unit->ignoreTerrainDamage()?1:0;values[14]=unit->ignoreFeatureDamage()?1:0;
 values[15]=unit->extraTerrainDamage();values[16]=unit->extraFeatureDamage();return 17;
}
static bool KernelProbeAddUnit(DestinationKernelProbeState& state,const CvUnit* unit)
{
 if(state.participantCount==KERNEL_PROBE_PARTICIPANTS)return false;
 int values[17];unsigned count=KernelProbeUnitWords(unit,values);if(!count)return false;
 state.participants[state.participantCount]=unit;state.participantOffsets[state.participantCount++]=state.count;
 for(unsigned i=0;i<count;++i)if(!state.Add(values[i]))return false;return true;
}
static bool KernelProbeAddDamage(DestinationKernelProbeState& state,const SUnitIDValueContainer& damage)
{
 unsigned at=state.count;if(!state.Add(0))return false;unsigned count=0;
 for(SUnitIDValueContainer::const_iterator i=damage.begin();i!=damage.end();++i)
 {if(!state.Add((*i).first)||!state.Add((*i).second))return false;++count;}
 state.words[at]=(int)count;return true; // Raw order/zeros/duplicates are retained.
}
struct DestinationKernelProbeSession
{
 DestinationKernelProbeState* state;
 DestinationKernelProbeSession(PlayerTypes owner,int target):state(NULL)
 {
  unsigned long serial=0;long epoch=0;
  if(gDestinationKernelProbe||!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch))return;
  if(!IsStackForecastOwner()||!StackForecastContext())return;
  try{state=new DestinationKernelProbeState;}catch(std::bad_alloc&){return;}
  LARGE_INTEGER frequency;if(QueryPerformanceFrequency(&frequency)&&frequency.QuadPart>0)state->frequency=(unsigned __int64)frequency.QuadPart;
  state->serial=serial;state->epoch=epoch;state->revision=gStackForecastRevision;state->scene=gStackForecastSceneEpoch;state->owner=owner;state->target=target;
  gDestinationKernelProbe=state;
 }
 ~DestinationKernelProbeSession(){Finish();}
 void Finish()
 {
  if(!state||gDestinationKernelProbe!=state)return;
  DestinationKernelProbeState* done=state;unsigned long serial=0;long epoch=0;
  if(CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)&&serial==done->serial&&epoch==done->epoch)
  {
   const DestinationKernelProbeCounts& a=done->kinds[0];const DestinationKernelProbeCounts& b=done->kinds[1];
   CvStackingDiagnostics::Record(1,done->owner,"PLAN_KERNEL_PROBE",
    "version=1 serial=%lu target=%d thread=%lu stride=64 slots=128 words=2048 stateSlots=8192 frequency=%I64u metadataBytes=%u unitCalls=%I64u unitSelected=%I64u unitComplete=%I64u unitGroups=%I64u unitRepeats=%I64u unitSameIncarnation=%I64u unitCrossIncarnation=%I64u unitParentAtMutation=%I64u unitUnknownRelation=%I64u unitMismatches=%I64u unitZeroKeys=%I64u unitKeyVisits=%I64u unitScalarHits=%I64u unitScalarMisses=%I64u unitOutcomeBuilds=%I64u unitPrepInsideTicks=%I64u unitPrepOutsideTicks=%I64u unitKernelTicks=%I64u stackCalls=%I64u stackSelected=%I64u stackComplete=%I64u stackGroups=%I64u stackRepeats=%I64u stackSameIncarnation=%I64u stackCrossIncarnation=%I64u stackParentAtMutation=%I64u stackUnknownRelation=%I64u stackMismatches=%I64u stackZeroKeys=%I64u stackKeyVisits=%I64u stackScalarHits=%I64u stackScalarMisses=%I64u stackOutcomeBuilds=%I64u stackPrepInsideTicks=%I64u stackPrepOutsideTicks=%I64u stackKernelTicks=%I64u evictions=%I64u clears=%I64u oversized=%I64u unavailable=%I64u invalidated=%I64u nested=%I64u unknownStates=%I64u keyBytes=%I64u peakKeyBytes=%I64u note=observed_footprint_not_certified_reuse_no_stride_scaling_inclusive_kernel_overlaps_prepInside",
    done->serial,done->target,GetCurrentThreadId(),done->frequency,(unsigned)sizeof(*done),
    a.calls,a.selected,a.complete,a.groups,a.repeats,a.sameState,a.crossState,a.parentChild,a.unknownRelation,a.mismatches,a.zeroKeys,a.keyVisits,a.scalarHits,a.scalarMisses,a.outcomeBuilds,a.prepInsideTicks,a.prepOutsideTicks,a.kernelTicks,
    b.calls,b.selected,b.complete,b.groups,b.repeats,b.sameState,b.crossState,b.parentChild,b.unknownRelation,b.mismatches,b.zeroKeys,b.keyVisits,b.scalarHits,b.scalarMisses,b.outcomeBuilds,b.prepInsideTicks,b.prepOutsideTicks,b.kernelTicks,
    done->evictions,done->clears,done->oversized,done->unavailable,done->invalidated,done->nested,done->unknownStates,done->keyBytes,done->peakKeyBytes);
  }
  gDestinationKernelProbe=NULL;gDestinationKernelFrame=NULL;state=NULL;delete done;
 }
private:DestinationKernelProbeSession(const DestinationKernelProbeSession&);DestinationKernelProbeSession& operator=(const DestinationKernelProbeSession&);
};
struct DestinationKernelProbeFrame
{
 DestinationKernelProbeState* state;const CvUnit* unit;const CvPlot* plot;const CvTacticalPosition* position;
 unsigned kind,keyVisits;bool valid;unsigned long revision;long scene;
 unsigned __int64 begun,prepTicks,insideTicks,incarnation,parentIncarnation;unsigned long beforeHits,beforeMisses,beforeBuilds;
 DestinationKernelProbeFrame(unsigned kind,const CvUnit* unit,const CvPlot* plot,const CvTacticalPosition& position,int extra,
  const vector<const CvUnit*>* candidates=NULL,const SUnitIDValueContainer* damage=NULL):state(NULL)
 {if(gDestinationKernelProbe)BeginActive(kind,unit,plot,position,extra,candidates,damage);}
 void BeginActive(unsigned kind,const CvUnit* unit,const CvPlot* plot,const CvTacticalPosition& position,int extra,
  const vector<const CvUnit*>* candidates,const SUnitIDValueContainer* damage)
 {
  this->unit=unit;this->plot=plot;this->position=&position;this->kind=kind;keyVisits=0;valid=false;revision=0;scene=0;begun=prepTicks=insideTicks=incarnation=parentIncarnation=0;beforeHits=beforeMisses=beforeBuilds=0;
  DestinationKernelProbeState* active=gDestinationKernelProbe;if(!active||kind>1)return;
  ++active->kinds[kind].calls;
  if(gDestinationKernelFrame||active->busy){++active->nested;return;}
  if(!unit||!plot||sizeof(void*)!=4){++active->unavailable;return;}
  const int cohort[4]={(int)kind,unit->getOwner(),unit->GetID(),plot->GetPlotIndex()};
  if(KernelProbeHash(cohort,4)&(KERNEL_PROBE_STRIDE-1))return;
  ++active->kinds[kind].selected;unsigned __int64 prepare=KernelProbeTick();
  unsigned long serial=0;long epoch=0;
  if(!CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)||serial!=active->serial||epoch!=active->epoch||!StackForecastContext())
  {++active->unavailable;return;}
  if(active->revision!=gStackForecastRevision||active->scene!=gStackForecastSceneEpoch)
  {active->Clear();active->revision=gStackForecastRevision;active->scene=gStackForecastSceneEpoch;}
  const unsigned long preparingRevision=gStackForecastRevision;const long preparingScene=gStackForecastSceneEpoch;
  struct PreparingGuard{bool& busy;bool committed;PreparingGuard(bool& b):busy(b),committed(false){busy=true;}~PreparingGuard(){if(!committed)busy=false;}} preparing(active->busy);
  const CvDangerPlots* map=GET_PLAYER(unit->getOwner()).GetDangerPlots();unsigned used=0;
  if(map->IsDirty()||!map->AppendStackDangerCacheDescriptor(*plot,active->beforeSource,KERNEL_PROBE_SOURCE_WORDS,used))
  {++active->unavailable;return;} // Never refresh a source before original work.
  active->count=active->participantCount=0;active->sourceCount=used;
  bool okay=active->Add((int)kind)&&active->Add(plot->GetPlotIndex())&&active->Add(extra)&&KernelProbeAddUnit(*active,unit)&&KernelProbeAddDamage(*active,position.GetUnitDamageDealt());
  for(unsigned i=0;i<used&&okay;++i)okay=active->Add(active->beforeSource[i]);
  if(candidates&&damage)
  {okay=okay&&active->Add((int)candidates->size())&&KernelProbeAddDamage(*active,*damage);for(size_t i=0;i<candidates->size()&&okay;++i)okay=KernelProbeAddUnit(*active,(*candidates)[i]);}
  if(!okay){++active->oversized;return;}
  if(!StackForecastContext()||preparingRevision!=gStackForecastRevision||preparingScene!=gStackForecastSceneEpoch||preparingScene!=CvStackingStrengthCache::SceneEpoch()){++active->invalidated;return;}
  DestinationKernelStateIncarnation* identity=KernelProbeIncarnation(*active,&position);if(identity){incarnation=identity->incarnation;parentIncarnation=identity->parent;}
  revision=gStackForecastRevision;scene=gStackForecastSceneEpoch;beforeHits=gStackDangerHits;beforeMisses=gStackDangerMisses;beforeBuilds=gStackOutcomeBuilds;
  state=active;valid=true;gDestinationKernelFrame=this;preparing.committed=true;prepTicks=KernelProbeElapsed(prepare,KernelProbeTick());begun=KernelProbeTick();
 }
 ~DestinationKernelProbeFrame(){if(state)Release();} // Exceptions never complete a result.
 void Release(){if(state&&state==gDestinationKernelProbe&&gDestinationKernelFrame==this){state->busy=false;gDestinationKernelFrame=NULL;state=NULL;}}
 void AddDanger(const CvUnit* queried,const CvPlot* target,const vector<const CvUnit*>& candidates,
  const SUnitIDValueContainer& friendly,const StackForecastKey& key,bool cacheable)
 {
  if(!state||state!=gDestinationKernelProbe||gDestinationKernelFrame!=this||!valid)return;
  unsigned __int64 prepare=KernelProbeTick();
  if(!cacheable||target!=plot){valid=false;++state->unavailable;return;}
  ++keyVisits;bool okay=state->Add(0x4b4559)&&state->Add((int)key.state.size())&&KernelProbeAddUnit(*state,queried)&&state->Add((int)candidates.size())&&KernelProbeAddDamage(*state,friendly);
  for(size_t i=0;i<candidates.size()&&okay;++i)okay=KernelProbeAddUnit(*state,candidates[i]);
  for(size_t i=0;i<key.state.size()&&okay;++i)okay=state->Add(key.state[i]);
  if(!okay){valid=false;++state->oversized;}
  insideTicks+=KernelProbeElapsed(prepare,KernelProbeTick());
 }
 int Finish(int result){if(state)FinishActive(result);return result;}
 void FinishActive(int result)
 {
  if(!state||state!=gDestinationKernelProbe||gDestinationKernelFrame!=this)return;
  unsigned __int64 end=KernelProbeTick(),prepare=KernelProbeTick();DestinationKernelProbeState& s=*state;DestinationKernelProbeCounts& counts=s.kinds[kind];
  unsigned long serial=0;long epoch=0;unsigned used=0;
  bool okay=valid&&CvStackingDiagnostics::TryGetPlanSamplingContext(serial,epoch)&&serial==s.serial&&epoch==s.epoch&&StackForecastContext()&&
   revision==gStackForecastRevision&&scene==gStackForecastSceneEpoch;
  if(okay)
  {
   const CvDangerPlots* map=GET_PLAYER(unit->getOwner()).GetDangerPlots();
   okay=!map->IsDirty()&&map->AppendStackDangerCacheDescriptor(*plot,s.afterSource,KERNEL_PROBE_SOURCE_WORDS,used)&&
    used==s.sourceCount&&std::equal(s.beforeSource,s.beforeSource+used,s.afterSource)&&
    StackForecastContext()&&revision==gStackForecastRevision&&scene==gStackForecastSceneEpoch;
  }
  for(unsigned i=0;i<s.participantCount&&okay;++i){int values[17];unsigned n=KernelProbeUnitWords(s.participants[i],values);okay=n==17&&std::equal(values,values+n,s.words+s.participantOffsets[i]);}
  okay=okay&&StackForecastContext()&&revision==gStackForecastRevision&&scene==gStackForecastSceneEpoch;
  if(!okay){++s.invalidated;Release();return;}
  ++counts.complete;counts.keyVisits+=keyVisits;counts.scalarHits+=gStackDangerHits-beforeHits;counts.scalarMisses+=gStackDangerMisses-beforeMisses;counts.outcomeBuilds+=gStackOutcomeBuilds-beforeBuilds;if(!keyVisits)++counts.zeroKeys;
  unsigned long hash=KernelProbeHash(s.words,s.count);DestinationKernelProbeSlot* found=NULL;
  for(unsigned i=0;i<KERNEL_PROBE_SLOTS;++i)if(s.slots[i].used&&s.slots[i].hash==hash&&s.slots[i].count==s.count&&std::equal(s.words,s.words+s.count,s.slots[i].words)){found=&s.slots[i];break;}
  if(found)
  {
   ++counts.repeats;if(found->result!=result)++counts.mismatches;
   if(!incarnation||!found->incarnation)++counts.unknownRelation;
   else if(found->incarnation==incarnation)++counts.sameState;else ++counts.crossState;
   if(parentIncarnation&&parentIncarnation==found->incarnation)++counts.parentChild;
  }
  else
  {
   ++counts.groups;found=&s.slots[s.next];s.next=(s.next+1)%KERNEL_PROBE_SLOTS;
   if(found->used){++s.evictions;s.keyBytes-=found->count*sizeof(int);}found->used=true;found->count=s.count;found->hash=hash;found->kind=kind;found->result=result;
   std::copy(s.words,s.words+s.count,found->words);s.keyBytes+=s.count*sizeof(int);s.peakKeyBytes=std::max(s.peakKeyBytes,s.keyBytes);
  }
  found->incarnation=incarnation;
  counts.kernelTicks+=KernelProbeElapsed(begun,end);counts.prepInsideTicks+=insideTicks;counts.prepOutsideTicks+=prepTicks+KernelProbeElapsed(prepare,KernelProbeTick());Release();
 }
private:DestinationKernelProbeFrame(const DestinationKernelProbeFrame&);DestinationKernelProbeFrame& operator=(const DestinationKernelProbeFrame&);
};
static inline void ObserveDestinationDangerKey(const CvUnit* unit,const CvPlot* plot,const vector<const CvUnit*>& candidates,
 const SUnitIDValueContainer& friendly,const StackForecastKey& key,bool cacheable)
{if(gDestinationKernelFrame)gDestinationKernelFrame->AddDanger(unit,plot,candidates,friendly,key,cacheable);}
// END DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY

static __declspec(noinline) int ResolveStackDangerForecastMiss(const CvUnit* unit,const CvPlot* plot,
 const vector<const CvUnit*>& candidates,const SUnitIDValueContainer& friendlyDamage,
 const SUnitIDValueContainer& enemyDamage,const StackForecastKey& key,bool cacheable,
 unsigned long revision,long scene,StackDangerOutcomeBatch* outcome)
{
 PacketProbeCall packetProbeCall(unit,plot,candidates,friendlyDamage,enemyDamage,key,cacheable); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
 int result = 0;
 const bool tryPacket = cacheable && (!outcome || !outcome->ready);
 StackDangerPacketQuery packetQuery(tryPacket);
 CvStackingDiagnostics::PlanSampleScope leafSample(CvStackingDiagnostics::PLAN_DANGER_LEAF); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
 const bool packetResolved = tryPacket && ResolveStackDangerPacket(packetQuery,unit,plot,candidates,friendlyDamage,enemyDamage,key,revision,scene,outcome,result);
 if (!packetResolved)
 {
 if (!outcome || !outcome->TryGet(unit, plot, candidates, friendlyDamage, enemyDamage, result))
  result = (packetProbeCall.MarkRaw(), GET_PLAYER(unit->getOwner()).GetDangerPlots()->GetStackDanger(*plot, unit, candidates, friendlyDamage, enemyDamage)); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
 }
 leafSample.Finish(); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
 packetProbeCall.Finish(); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY
 if (cacheable && StackForecastContext() && gStackForecastRevision == revision && gStackForecastSceneEpoch == scene)
 {
  if (packetResolved)
  {
   if (packetQuery.scalarValid && ValidateStackDangerPacket(packetQuery,unit,plot,revision,scene))
   {
    if (packetQuery.storePacket) StoreStackDangerPacketForecast(packetQuery.buffer.key,packetQuery.buffer.value);
    // Only this queried even key is admitted, last under tiny shared budgets.
    if (ValidateStackDangerPacket(packetQuery,unit,plot,revision,scene)) StoreStackDangerForecast(key,result);
   }
  }
  else StoreStackDangerForecast(key,result);
 }
 return result;
}

static int GetCachedStackDanger(const CvUnit* unit, const CvPlot* plot, const vector<const CvUnit*>& candidates,
 const SUnitIDValueContainer& friendlyDamage, const SUnitIDValueContainer& enemyDamage, StackDangerOutcomeBatch* outcome = NULL)
{
 int fixedDanger = 0;
 if (CvStacking::IsEnabled() && GET_PLAYER(unit->getOwner()).GetDangerPlots()->TryGetFixedStackDanger(*plot, unit, fixedDanger))
  return fixedDanger;
 StackForecastQuery query(gStackDangerScratch,gStackDangerScratchBusy);
 StackForecastKey& key=query.key;
 bool cacheable = query.scratch != NULL || StackForecastContext();
 const unsigned long revision = cacheable ? gStackForecastRevision : 0;
 const long scene = cacheable ? gStackForecastSceneEpoch : 0;
 CvStackingDiagnostics::PlanSampleScope keySample(CvStackingDiagnostics::PLAN_DANGER_KEY,cacheable); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
 if (cacheable)
 {
  key.state.push_back(unit->GetID());
  key.state.push_back(plot->GetPlotIndex());
  key.state.push_back(friendlyDamage.GetValue(unit->GetID()));
  key.state.push_back(CvStacking::GetCityProtection(plot->getPlotCity()));
  AppendStackCandidates(key, candidates, friendlyDamage, !plot->isCity() && CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled, 1) != 0);
  AppendStackDamageProjected(key, enemyDamage, unit, plot);
  cacheable = StackForecastContext() && gStackForecastRevision == revision && gStackForecastSceneEpoch == scene;
  ObserveDestinationDangerKey(unit,plot,candidates,friendlyDamage,key,cacheable); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
  int cachedResult=0;
  if (cacheable && FindStackDangerForecastScalar(key,cachedResult))
  {
   ++gStackDangerHits;
   return cachedResult;
  }
 }
 keySample.Finish(); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
 if (cacheable)
  ++gStackDangerMisses;
 return ResolveStackDangerForecastMiss(unit,plot,candidates,friendlyDamage,enemyDamage,key,cacheable,revision,scene,outcome);
}

static const CvUnit* SelectCachedStackDefender(const CvUnit* attacker, const CvPlot* from, const CvPlot* target,
 const vector<const CvUnit*>& candidates, const SUnitIDValueContainer& damage, bool ranged, int attackerDamage)
{
 StackForecastQuery query(gStackDefenderScratch,gStackDefenderScratchBusy);
 StackForecastKey& key=query.key;
 bool cacheable = query.scratch != NULL || StackForecastContext();
 const unsigned long revision = cacheable ? gStackForecastRevision : 0;
 const long scene = cacheable ? gStackForecastSceneEpoch : 0;
 if (cacheable)
 {
  key.state.push_back(attacker->GetID());
  key.state.push_back(from ? from->GetPlotIndex() : -1);
  key.state.push_back(target->GetPlotIndex());
  key.state.push_back(ranged ? 1 : 0);
  key.state.push_back(attackerDamage);
  AppendStackCandidates(key, candidates, damage, CvStacking::IsEnabled() && CvStacking::GetIntByKey(CvStacking::HOT_DefenderSelectionEnabled, 1) != 0);
  cacheable = StackForecastContext() && gStackForecastRevision == revision && gStackForecastSceneEpoch == scene;
  const CvUnit* cachedResult=NULL;
  if (cacheable && FindStackDefenderForecast(key,cachedResult))
  {
   ++gStackDefenderHits;
   return cachedResult;
  }
 }
 if (cacheable)
  ++gStackDefenderMisses;
 const CvUnit* result = CvUnitCombat::SelectStackDefender(attacker, from, target, candidates, damage, ranged, attackerDamage);
 if (cacheable && StackForecastContext() && gStackForecastRevision == revision && gStackForecastSceneEpoch == scene)
  StoreStackDefenderForecast(key, result);
 return result;
}

static void GetVirtualFriendlyStack(const CvTacticalPosition& position, const CvPlot* plot, const CvUnit* arriving,
 int extraDamage, vector<const CvUnit*>& candidates, SUnitIDValueContainer& damage)
{
 const CvTacticalPlot* tactical = position.getTactPlot(plot->GetPlotIndex());
 if (tactical)
 {
  const CvTacticalPlot::FixedUnitList& fixedUnits = tactical->getFixedFriendlyUnits();
  candidates.assign(fixedUnits.begin(), fixedUnits.end());
  const CvTacticalPlot::UnitList& units = tactical->getUnitsAtPlot();
  for (size_t i = 0; i < units.size(); ++i)
  {
   const CvUnit* unit = GET_PLAYER(position.getPlayer()).getUnit(units[i].iUnitID);
   if (unit && unit->IsCombatUnit() && !unit->isCargo() && unit->getDomainType() != DOMAIN_AIR)
   {
    candidates.push_back(unit);
    const SUnitStats* stats = position.GetUnitStats(unit->GetID());
    if (stats)
     damage.SetValue(unit->GetID(), stats->iSelfDamage);
   }
  }
 }
 if (arriving)
 {
  if (std::find(candidates.begin(), candidates.end(), arriving) == candidates.end())
   candidates.push_back(arriving);
  damage.SetValue(arriving->GetID(), extraDamage);
 }
}

// A preparation view lasts only through one parent's const preferred-unit batch.
// No danger result or serialized key is retained. Borrowed query ownership is
// the admission witness; a private/nested query always follows the old builder.
struct ParentStackPreparationCell
{
 int plotIndex;
 VirtualFriendlyStackBuffer base;
 ParentStackPreparationCell():plotIndex(-1) {}
};
struct ParentStackPreparationStorage
{
 enum { MAX_CELLS = 255 };
 ParentStackPreparationCell cells[MAX_CELLS];
 pair<int,int> lookup[MAX_CELLS];
 size_t count,retainedBytes;
 bool busy;
 ParentStackPreparationStorage():count(0),retainedBytes(0),busy(false) {}
 void Reset()
 {
  for (size_t i=0;i<count;++i)
  {cells[i].base.candidates.clear();cells[i].base.damage.clear();cells[i].plotIndex=-1;}
  count=0;
 }
 size_t CellBytes(size_t i) const
 {
  return cells[i].base.candidates.capacity()*sizeof(const CvUnit*)+
   cells[i].base.damage.m_aExtraStorage.capacity()*sizeof(SUnitIDValueContainer::value_type);
 }
 size_t RetainedBytes() const {return retainedBytes;}
 void ReleaseCell(size_t i)
 {
  retainedBytes-=CellBytes(i);cells[i].base.release();
 }
 void ReleasePayload()
 {
  for(size_t i=0;i<MAX_CELLS;++i) cells[i].base.release();
  count=0;retainedBytes=0;
 }
 void Release(){ReleasePayload();busy=false;}
};
static ParentStackPreparationStorage gParentStackPreparationStorage;
struct ParentStackPreparationView;
static __declspec(thread) ParentStackPreparationView* gParentStackPreparationView=NULL;
static void ReleaseParentStackPreparationStorage()
{gParentStackPreparationStorage.Release();}

struct ParentStackPreparationView
{
 const CvTacticalPosition& parent;
 const CvTacticalPosition* child;
 ParentStackPreparationView* previous;
 unsigned long revision;
 long scene;
 bool disabled,borrowed;
 ParentStackPreparationView(const CvTacticalPosition& position):parent(position),child(NULL),
  previous(gParentStackPreparationView),revision(0),scene(0),disabled(previous!=NULL),borrowed(false)
 {
  if(previous) previous->disabled=true;
  gParentStackPreparationView=this;
 }
 ~ParentStackPreparationView()
 {
  if(borrowed) gParentStackPreparationStorage.busy=false;
  gParentStackPreparationView=previous;
 }
 void MarkChild(const CvTacticalPosition& from,const CvTacticalPosition& to)
 {
  child=NULL;
  if(!disabled&&&from==&parent&&&to!=&parent&&to.SharesVirtualStackInputs(parent)) child=&to;
 }
 bool CanPrepare(const CvTacticalPosition& position,bool ownedLoan)
 {
  // Short-circuit before owner-only globals/storage on a foreign/private call.
  if(!ownedLoan||disabled||(&position!=&parent&&&position!=child)||
   !position.SharesVirtualStackInputs(parent)) return false;
  if(!borrowed)
  {
   if(gParentStackPreparationStorage.busy) return false;
   // ownedLoan was granted by this callsite's original fresh Context check.
   revision=gStackForecastRevision;scene=gStackForecastSceneEpoch;
   gParentStackPreparationStorage.Reset();gParentStackPreparationStorage.busy=true;borrowed=true;
  }
  if(revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch) {disabled=true;return false;}
  return true;
 }
 bool Prepare(const CvTacticalPosition& position,const CvPlot* plot,const CvUnit* arriving,int extraDamage,
  vector<const CvUnit*>& candidates,SUnitIDValueContainer& damage,bool ownedLoan)
 {
  if(!candidates.empty()||(damage.begin()!=damage.end())||!CanPrepare(position,ownedLoan)) return false;
  ParentStackPreparationStorage& storage=gParentStackPreparationStorage;
  const int index=plot->GetPlotIndex();
  size_t lo=0,hi=storage.count;
  while(lo<hi){const size_t mid=lo+(hi-lo)/2;if(storage.lookup[mid].first<index)lo=mid+1;else hi=mid;}
  size_t cellIndex;
  if(lo<storage.count&&storage.lookup[lo].first==index) cellIndex=storage.lookup[lo].second;
  else
  {
   if(storage.count==ParentStackPreparationStorage::MAX_CELLS) return false;
   cellIndex=storage.count;
   ParentStackPreparationCell& cell=storage.cells[cellIndex];
   const size_t before=storage.CellBytes(cellIndex);
   try
   {
    GetVirtualFriendlyStack(parent,plot,NULL,0,cell.base.candidates,cell.base.damage);
    storage.retainedBytes=storage.retainedBytes-before+storage.CellBytes(cellIndex);
    if(storage.RetainedBytes()>gStackKeyPayloadLimit)
    {storage.ReleasePayload();disabled=true;return false;}
   }
   catch(const std::bad_alloc&)
   {storage.retainedBytes=storage.retainedBytes-before+storage.CellBytes(cellIndex);storage.ReleasePayload();disabled=true;return false;}
   if(disabled||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch||
    scene!=CvStackingStrengthCache::SceneEpoch())
   {storage.ReleaseCell(cellIndex);disabled=true;return false;}
   cell.plotIndex=index;
   for(size_t i=storage.count;i>lo;--i) storage.lookup[i]=storage.lookup[i-1];
   storage.lookup[lo]=make_pair(index,(int)cellIndex);++storage.count;
  }
  try
  {candidates=storage.cells[cellIndex].base.candidates;damage=storage.cells[cellIndex].base.damage;}
  catch(const std::bad_alloc&)
  {candidates.clear();damage.clear();storage.ReleasePayload();disabled=true;return false;}
  // Keep the original pointer-dedup and exact arrival-wound overwrite order.
  if(arriving)
  {
   if(std::find(candidates.begin(),candidates.end(),arriving)==candidates.end()) candidates.push_back(arriving);
   damage.SetValue(arriving->GetID(),extraDamage);
  }
  // Warm reuse contains only vector copies and native GetID/GetPlotIndex.
  // Their caller already validated the live scene before granting ownedLoan.
  if(disabled||revision!=gStackForecastRevision||scene!=gStackForecastSceneEpoch)
  {candidates.clear();damage.clear();disabled=true;return false;}
  return true;
 }
private:
 ParentStackPreparationView(const ParentStackPreparationView&);
 ParentStackPreparationView& operator=(const ParentStackPreparationView&);
};
static void MarkParentStackPreparationChild(const CvTacticalPosition& from,const CvTacticalPosition& to)
{if(gParentStackPreparationView) gParentStackPreparationView->MarkChild(from,to);}
static void GetPreparedVirtualFriendlyStack(const CvTacticalPosition& position,const CvPlot* plot,
 const CvUnit* arriving,int extraDamage,vector<const CvUnit*>& candidates,SUnitIDValueContainer& damage,bool ownedLoan)
{
 ParentStackPreparationView* view=gParentStackPreparationView;
 if(!view||!view->Prepare(position,plot,arriving,extraDamage,candidates,damage,ownedLoan))
  GetVirtualFriendlyStack(position,plot,arriving,extraDamage,candidates,damage);
}

// This is the exact size produced by GetVirtualFriendlyStack, including fixed
// and movable duplicates. The caller only needs that count, so avoid creating
// membership/damage vectors and looking up every movable member's HP state.
static size_t CountVirtualFriendlyStack(const CvTacticalPosition& position, const CvPlot* plot, const CvUnit* arriving)
{
 size_t count = 0;
 bool arrivingPresent = false;
 const CvTacticalPlot* tactical = position.getTactPlot(plot->GetPlotIndex());
 if (tactical)
 {
  const CvTacticalPlot::FixedUnitList& fixed = tactical->getFixedFriendlyUnits();
  count = fixed.size();
  arrivingPresent = arriving && std::find(fixed.begin(), fixed.end(), arriving) != fixed.end();
  const CvTacticalPlot::UnitList& units = tactical->getUnitsAtPlot();
  for (size_t i = 0; i < units.size(); ++i)
  {
   const CvUnit* unit = GET_PLAYER(position.getPlayer()).getUnit(units[i].iUnitID);
   if (unit && unit->IsCombatUnit() && !unit->isCargo() && unit->getDomainType() != DOMAIN_AIR)
   {
    ++count;
    arrivingPresent |= unit == arriving;
   }
  }
 }
 return count + (arriving && !arrivingPresent ? 1 : 0);
}

// One movement evaluation asks about this exact destination twice. Materialize
// its roster only when required, and rebuild after a nested/dirty/foreign scene.
// This reuses temporary membership, not a forecast or a tactical decision.
struct MovementDestinationStackQuery
{
 VirtualFriendlyStackBuffer* buffer;
 bool borrowed, reusable;
 const CvTacticalPosition* savedPosition;
 const CvPlot* savedPlot;
 const CvUnit* savedUnit;
 int savedDamage;
 unsigned long revision;
 long scene;
 MovementDestinationStackQuery():buffer(NULL),borrowed(false),reusable(false),
  savedPosition(NULL),savedPlot(NULL),savedUnit(NULL),savedDamage(0),revision(0),scene(0) {}
 ~MovementDestinationStackQuery() { Release(); }
 void Release()
 {
  if (!buffer)
   return;
  if (borrowed) gStackDestinationScratchBusy = false;
  else delete buffer;
  buffer = NULL;
  borrowed = reusable = false;
 }
 const VirtualFriendlyStackBuffer& Get(const CvTacticalPosition& position, const CvPlot* plot,
  const CvUnit* unit, int selfDamage)
 {
  const bool context = StackForecastContext();
  if (buffer && reusable && context && revision == gStackForecastRevision && scene == gStackForecastSceneEpoch &&
   savedPosition == &position && savedPlot == plot && savedUnit == unit && savedDamage == selfDamage)
   return *buffer;
  // A query resumed inside a nested search no longer owns shared storage.
  if (buffer && borrowed && !context)
   Release();
  if (!buffer)
  {
   borrowed = context && !gStackDestinationScratchBusy;
   buffer = borrowed ? &gStackDestinationScratch : new VirtualFriendlyStackBuffer;
   if (borrowed) gStackDestinationScratchBusy = true;
  }
  revision = context ? gStackForecastRevision : 0;
  scene = context ? gStackForecastSceneEpoch : 0;
  buffer->candidates.clear();
  buffer->damage.clear();
  GetPreparedVirtualFriendlyStack(position, plot, unit, selfDamage, buffer->candidates, buffer->damage, borrowed && context);
  savedPosition = &position;
  savedPlot = plot;
  savedUnit = unit;
  savedDamage = selfDamage;
  reusable = context && StackForecastContext() && revision == gStackForecastRevision && scene == gStackForecastSceneEpoch;
  return *buffer;
 }
private:
 MovementDestinationStackQuery(const MovementDestinationStackQuery&);
 MovementDestinationStackQuery& operator=(const MovementDestinationStackQuery&);
};

// A same-tile escort counts only when removing eligible melee members would
// expose this unit to more real forecast damage, and those escorts survive.
// This also rejects a weak defender or a cavalry-bypassed escort that adds no cover.
static bool HasSurvivingStackProtection(const CvUnit* unit, const CvPlot* plot,
 const vector<const CvUnit*>& candidates, const SUnitIDValueContainer& friendlyDamage,
 const SUnitIDValueContainer& enemyDamage, int /*callerDanger*/)
{
 if (!StackPreferencesEnabled() || !unit->IsCombatUnit() || !unit->isNativeDomain(plot))
  return false;
 int fixedDanger = 0;
 if (GET_PLAYER(unit->getOwner()).GetDangerPlots()->TryGetFixedStackDanger(*plot, unit, fixedDanger))
  return false;
 // Some intermediate callers scale danger by aggression. Protection and survival
 // must compare raw forecasts on both sides, never raw solo against scaled stack.
 StackDangerOutcomeBatch fullOutcome(plot, candidates, friendlyDamage, enemyDamage);
 const int protectedDanger = GetCachedStackDanger(unit, plot, candidates, friendlyDamage, enemyDamage, &fullOutcome);
 if (protectedDanger >= unit->GetCurrHitPoints() - friendlyDamage.GetValue(unit->GetID()))
  return false;
 vector<const CvUnit*> withoutProtectors;
 bool hasProtector = false;
 for (size_t i = 0; i < candidates.size(); ++i)
 {
  const CvUnit* member = candidates[i];
  const bool eligible = member && member != unit && member->getOwner() == unit->getOwner() &&
   member->IsCombatUnit() && !member->IsStackingUnit() && !member->isCargo() && !member->isDelayedDeath() &&
   !member->IsCanAttackRanged() && member->IsCanDefend() && member->getDomainType() == unit->getDomainType() &&
   member->isNativeDomain(plot) && member->GetCurrHitPoints() > friendlyDamage.GetValue(member->GetID());
  if (eligible)
  {
   if (GetCachedStackDanger(member, plot, candidates, friendlyDamage, enemyDamage, &fullOutcome) >=
    member->GetCurrHitPoints() - friendlyDamage.GetValue(member->GetID()))
    return false;
   hasProtector = true;
  }
  else if (member)
   withoutProtectors.push_back(member);
 }
 return hasProtector && GetCachedStackDanger(unit, plot, withoutProtectors, friendlyDamage, enemyDamage) > protectedDanger;
}

static bool CanApproachInProtectedStack(const CvUnit* unit, const CvPlot* destination, int destinationDanger)
{
 if (!StackPreferencesEnabled() || !destination || destination == unit->plot() ||
  !unit->canMoveInto(*destination, CvUnit::MOVEFLAG_DESTINATION))
  return false;
 vector<const CvUnit*> before;
 for (int i = 0; i < destination->getNumUnits(); ++i)
 {
  const CvUnit* member = destination->getUnitByIndex(i);
  if (member && member != unit && member->getOwner() == unit->getOwner() && member->IsCombatUnit() &&
   !member->isCargo() && !member->isDelayedDeath())
   before.push_back(member);
 }
 if (before.empty())
  return false;
 vector<const CvUnit*> after = before;
 after.push_back(unit);
 SUnitIDValueContainer noDamage;
 if (!HasSurvivingStackProtection(unit, destination, after, noDamage, noDamage, destinationDanger) ||
  destinationDanger > unit->GetDanger(unit->plot()))
  return false;
 // Do not improve the siege unit by making an existing member less safe.
 for (size_t i = 0; i < before.size(); ++i)
 {
  const int joinedDanger = GetCachedStackDanger(before[i], destination, after, noDamage, noDamage);
  if (joinedDanger >= before[i]->GetCurrHitPoints() ||
   joinedDanger > GetCachedStackDanger(before[i], destination, before, noDamage, noDamage))
   return false;
 }
 return true;
}

// Geometric encirclement counts occupied passable hexes, never units in a stack.
// This remains a conservative addition to the live blockade/zone-of-control rules.
static bool HasVirtualCityEncirclement(const CvTacticalPosition& position, const CvCity* city)
{
 CvPlot** neighbors = GC.getMap().getNeighborsUnchecked(city->plot());
 for (int d = 0; d < NUM_DIRECTION_TYPES; ++d)
 {
  const CvPlot* plot = neighbors[d];
  if (!plot || plot->isImpassable(city->getTeam()))
   continue;
  if (plot->isCity())
   return false;
  VirtualFriendlyStackQuery stack;
  vector<const CvUnit*>& members = stack.candidates;
  SUnitIDValueContainer& damage = stack.damage;
  GetVirtualFriendlyStack(position, plot, NULL, 0, members, damage);
  bool occupied = false;
  for (size_t i = 0; i < members.size(); ++i)
  {
   const CvUnit* member = members[i];
   if (member && member->getOwner() == position.getPlayer() && member->IsCombatUnit() && !member->isCargo() &&
    !member->isDelayedDeath() && member->IsCanDefend() && member->isNativeDomain(plot) &&
    member->GetCurrHitPoints() > damage.GetValue(member->GetID()))
   { occupied = true; break; }
  }
  if (!occupied)
   return false;
 }
 return true;
}

static int GetUnitDangerForPlot(const CvUnit* pUnit, const CvPlot* pPlot, int iSelfDamage, const CvTacticalPosition& assumedPosition,
 MovementDestinationStackQuery* destinationStack = NULL)
{
 CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_UNIT_DANGER); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
 DestinationKernelProbeFrame kernelProbe(0,pUnit,pPlot,assumedPosition,iSelfDamage); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
 int iDanger = 0;
 if (CvStacking::IsEnabled() && pUnit->IsCombatUnit() && pUnit->getDomainType() != DOMAIN_AIR)
 {
  if (!GET_PLAYER(pUnit->getOwner()).GetDangerPlots()->TryGetFixedStackDanger(*pPlot, pUnit, iDanger))
  {
   if (destinationStack)
   {
    const VirtualFriendlyStackBuffer& stack = destinationStack->Get(assumedPosition, pPlot, pUnit, iSelfDamage);
    iDanger = GetCachedStackDanger(pUnit, pPlot, stack.candidates, stack.damage, assumedPosition.GetUnitDamageDealt());
   }
   else
   {
    VirtualFriendlyStackQuery stack;
    GetPreparedVirtualFriendlyStack(assumedPosition, pPlot, pUnit, iSelfDamage, stack.candidates, stack.damage, stack.borrowed);
    iDanger = GetCachedStackDanger(pUnit, pPlot, stack.candidates, stack.damage, assumedPosition.GetUnitDamageDealt());
   }
  }
 }
 else if (!gTactPosStorage.getDangerCache().findDanger(pUnit->GetID(), pPlot->GetPlotIndex(), iSelfDamage, assumedPosition.GetUnitDamageDealt(), iDanger))
 {
  iDanger = pUnit->GetDanger(pPlot, assumedPosition.GetUnitDamageDealt(), iSelfDamage);
  gTactPosStorage.getDangerCache().storeDanger(pUnit->GetID(), pPlot->GetPlotIndex(), iSelfDamage, assumedPosition.GetUnitDamageDealt(), iDanger);
 }
 return kernelProbe.Finish(iDanger == INT_MAX ? 10 * pUnit->GetMaxHitPoints() : iDanger); // DESTINATION_KERNEL_SHADOW_WRAP_ORIGINAL_RETURN
}

// Live attack-source roles are unchanged by hypothetical tactical assignments.
static unsigned char GetStackAttackThreatFlags(const CvUnit* unit, const CvPlot* plot)
{
 const bool cacheable = StackForecastContext();
 const unsigned long revision = cacheable ? gStackForecastRevision : 0;
 const long scene = cacheable ? gStackForecastSceneEpoch : 0;
 const std::pair<int, int> key(unit->getOwner(), plot->GetPlotIndex());
 if (cacheable)
 {
  StackThreatFlags::const_iterator cached = gStackThreatFlags.find(key);
  if (cached != gStackThreatFlags.end())
   return cached->second;
 }
 // Match GetPossibleAttackers(NO_TEAM): cities are omitted; delayed/dead
 // units are removed, and there is no extra visibility/virtual-damage filter.
 const vector<CvUnit*> attackers = GET_PLAYER(unit->getOwner()).GetPossibleAttackers(*plot, NO_TEAM);
 unsigned char flags = 0;
 for (size_t i = 0; i < attackers.size(); ++i)
 {
  if (!(flags & 1) && CvStacking::CanFlank(attackers[i]))
   flags |= 1;
  if (!(flags & 2) && CvStacking::GetCollateralTargetLimit(attackers[i]) > 0 && CvStacking::GetIntByKey(CvStacking::HOT_CollateralPercent, 20) > 0)
   flags |= 2;
  if (flags == 3)
   break;
 }
 // These are live-scene flags, independent of hypothetical HP/movement. A
 // callback that dirtied/reentered the scene cancels admission of its result.
 if (cacheable && StackForecastContext() && gStackForecastRevision == revision && gStackForecastSceneEpoch == scene &&
  gStackThreatFlags.size() < gStackEntryLimit)
 {
  gStackThreatFlags.insert(std::make_pair(key, flags));
  UpdateStackForecastPeaks();
 }
 return flags;
}

// Value actual protection and its cost in collateral exposure. This considers
// the candidate position, including friendly units omitted from the search.
static int ScoreStackPositionMembers(const CvUnit* unit, const CvPlot* plot, const CvTacticalPosition& position,
 const vector<const CvUnit*>& candidates, const SUnitIDValueContainer& damage)
{
 DestinationKernelProbeFrame kernelProbe(1,unit,plot,position,0,&candidates,&damage); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
 if (candidates.size() < 2)
  return kernelProbe.Finish(0); // DESTINATION_KERNEL_SHADOW_WRAP_ORIGINAL_RETURN
 // City bombardment alone can make a protective pair valuable. The forecast
 // below includes cities; these unit attackers only identify flanking/collateral.
 const unsigned char threat = GetStackAttackThreatFlags(unit, plot);
 const bool cavalryThreat = (threat & 1) != 0, collateralThreat = (threat & 2) != 0;
 bool antiCavalry = false;
 int otherProtectors = 0;
 const CvUnit* vulnerable = NULL;
 for (size_t i = 0; i < candidates.size(); ++i)
 {
  const CvUnit* other = candidates[i];
  if (other->GetCurrHitPoints() <= damage.GetValue(other->GetID()) || other->getDomainType() != unit->getDomainType())
   continue;
  if (cavalryThreat && !antiCavalry)
   antiCavalry = CvStacking::IsAntiCavalry(other);
  if (other != unit && !other->IsCanAttackRanged())
   ++otherProtectors;
  if (other->IsCanAttackRanged() && (!vulnerable || other->GetCurrHitPoints() < vulnerable->GetCurrHitPoints()))
   vulnerable = other;
 }
 int score = 0;
 if (vulnerable)
 {
  // Scored for every destination: the owning search thread reuses one buffer,
  // while nested or foreign queries build their own.
  vector<const CvUnit*> soloLocal;
  const bool borrowed = IsStackForecastOwner() && !gStackSoloScratchBusy;
  vector<const CvUnit*>& solo = borrowed ? gStackSoloScratch : soloLocal;
  solo.assign(1, vulnerable);
  int alone;
  {
   struct BusyGuard { bool active; BusyGuard(bool b):active(b){if(active)gStackSoloScratchBusy=true;} ~BusyGuard(){if(active)gStackSoloScratchBusy=false;} } busy(borrowed);
   alone = GetCachedStackDanger(vulnerable, plot, solo, damage, position.GetUnitDamageDealt());
  }
  int protectedDamage = GetCachedStackDanger(vulnerable, plot, candidates, damage, position.GetUnitDamageDealt());
  // INT_MAX means city capture; do not let sentinel arithmetic overflow.
  alone = min(alone, vulnerable->GetMaxHitPoints());
  protectedDamage = min(protectedDamage, vulnerable->GetMaxHitPoints());
  int saved = max(0, alone - protectedDamage);
  score += saved * CvStacking::GetIntByKey(CvStacking::HOT_AIStackProtectionWeight, 20) / max(1, vulnerable->GetMaxHitPoints());
  if (saved > 0 && ((unit == vulnerable && otherProtectors > 0) || (!unit->IsCanAttackRanged() && otherProtectors == 0)))
   score += CvStacking::GetIntByKey(CvStacking::HOT_AIStackJoinBonus, 12);
  if (cavalryThreat && antiCavalry)
   score += CvStacking::GetIntByKey(CvStacking::HOT_AIStackAntiFlankBonus, 12);
 }
 if (collateralThreat)
 {
  int vulnerableCount = 0;
  const int floorPercent = CvStacking::GetIntByKey(CvStacking::HOT_CollateralHPFloorPercent, 50);
  for (size_t i = 0; i < candidates.size(); ++i)
  {
   const CvUnit* member = candidates[i];
   if (!member->IsCombatUnit() || member->isCargo() || member->getDomainType() == DOMAIN_AIR || !CvStacking::IsCollateralTargetDomain(member->getDomainType())
    || (member->getDomainType() == DOMAIN_LAND && plot->needsEmbarkation(member)))
    continue;
   const int floorHP = (member->GetMaxHitPoints() * floorPercent + 99) / 100;
   if (member->GetCurrHitPoints() - damage.GetValue(member->GetID()) > floorHP)
    ++vulnerableCount;
  }
  int penalty = max(0, vulnerableCount - CvStacking::GetIntByKey(CvStacking::HOT_AIStackConcentrationFreeUnits, 2)) * CvStacking::GetIntByKey(CvStacking::HOT_AIStackConcentrationPenalty, 10);
  penalty = penalty * (100 - CvStacking::GetCityProtection(plot->getPlotCity())) / 100;
  score -= penalty;
 }
 return kernelProbe.Finish(score); // DESTINATION_KERNEL_SHADOW_WRAP_ORIGINAL_RETURN
}

static int ScoreStackPosition(const CvUnit* unit, const CvPlot* plot, int selfDamage, const CvTacticalPosition& position,
 MovementDestinationStackQuery* destinationStack = NULL)
{
 CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_STACK_SCORE); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
 if (!StackPreferencesEnabled())
  return 0;
 int fixedDanger = 0;
 if (GET_PLAYER(unit->getOwner()).GetDangerPlots()->TryGetFixedStackDanger(*plot, unit, fixedDanger))
  return 0;
 if (destinationStack)
 {
  const VirtualFriendlyStackBuffer& stack = destinationStack->Get(position, plot, unit, selfDamage);
  return ScoreStackPositionMembers(unit, plot, position, stack.candidates, stack.damage);
 }
 VirtualFriendlyStackQuery stack;
 GetVirtualFriendlyStack(position, plot, unit, selfDamage, stack.candidates, stack.damage);
 return ScoreStackPositionMembers(unit, plot, position, stack.candidates, stack.damage);
}

// what is the rough state looking like after this assignment
static void GetNextPosition(const CvTacticalPosition& previousPosition, const STacticalAssignment* assignment, CvTacticalPosition& newPosition)
{
	newPosition.initFromParent(previousPosition);

	for (SUnitIDValueContainer::const_iterator it2 = assignment->unitDamage.begin(); it2 != assignment->unitDamage.end(); ++it2)
	{
		const SUnitIDValueContainer::value_type& p = *it2;
		newPosition.ChangeUnitDamage(p.first, p.second);
	}
	if (assignment->iDamagedCityId != -1)
		newPosition.ChangeCityDamage(assignment->iDamagedCityId, assignment->iCityDamage);
 MarkParentStackPreparationChild(previousPosition,newPosition);
}

// what does the unit look like after this assignment
static SUnitStats GetNextUnit(const SUnitStats& previousUnit, const STacticalAssignment* assignment)
{
	SUnitStats newUnit = previousUnit;

	newUnit.iSelfDamage += assignment->iSelfDamage;
	newUnit.iMovesLeft = assignment->iRemainingMoves;

	return newUnit;
}

static int VirtualFlankPower(const CvTacticalPosition& position, const CvPlot* plot, DomainTypes domain, bool friendly, const CvUnit* exclude)
{
 int power = 0;
 CvPlot** neighbors = GC.getMap().getNeighborsUnchecked(plot);
 for (int d = 0; d < NUM_DIRECTION_TYPES; ++d)
 {
  if (!neighbors[d])
   continue;
  const CvTacticalPlot* tactical = position.getTactPlot(neighbors[d]->GetPlotIndex());
  if (!tactical)
   continue;
  VirtualFriendlyStackQuery stack;
  vector<const CvUnit*>& units = stack.candidates;
  SUnitIDValueContainer& damage = stack.damage;
  if (friendly)
   GetVirtualFriendlyStack(position, neighbors[d], NULL, 0, units, damage);
  else
  { units = tactical->getEnemyUnits(); damage = position.GetUnitDamageDealt(); }
  for (size_t i = 0; i < units.size(); ++i)
   if (units[i] != exclude && !units[i]->isEmbarked() && units[i]->getDomainType() == domain && damage.GetValue(units[i]->GetID()) < units[i]->GetCurrHitPoints())
    power += units[i]->GetFlankPower();
 }
 return power;
}

//note that the score returned from this function is not multiplied by 10 yet
bool ScoreAttackDamage(const CvTacticalPlot* tactPlot, const CvUnit* pUnit, const CvTacticalPlot* assumedPlot, const CvTacticalPosition& assumedPosition, CAttackCache& cache, STacticalAssignment* result, int iSelfDamage)
{
	eAggressionLevel eAggLvl = assumedPosition.getAggressionLevel();
	float fAggBias = assumedPosition.getAggressionBias();

	int iCityDamageDealt = 0;
	SUnitIDValueContainer unitDamageDealt;
	int iDamageReceived = 0; //always zero for ranged attack
	int iBonusScore = 0; //splash damage and other bonuses
	bool bRanged = pUnit->IsCanAttackRanged();

	//the damage calculation doesn't know about hypothetical flanking units, so we ignore it here and add it ourselves 
	int iPrevCityDamage = 0;
	SUnitIDValueContainer prevUnitDamage;
	int iPrevCityHitPoints = 0;
	SUnitIDValueContainer prevUnitHitPoints;

	const CvPlot* pUnitPlot = assumedPlot->getPlot();
	const CvPlot* pTestPlot = tactPlot->getPlot();

	CvCity* pEnemyCity = NULL;
	CvUnit* pEnemyUnit = NULL;

	bool bScoreReduction = false;

	//AL_LOW, AL_MEDIUM, AL_HIGH, AL_BRAVEHEART
	//braveheart allows attacks for which you need luck to survive
	int hpLimit[5] = {70,40,20,-5};

	if (tactPlot->isEnemyCity()) //a plot can be both a city and a unit - in that case we would attack the city
	{
		pEnemyCity = pTestPlot->getPlotCity();
		if (!pEnemyCity)
		{
			result->SetImpossible();
			return false;
		}

		iPrevCityDamage = assumedPosition.GetCityDamage(pEnemyCity->GetID());
		result->iDamagedCityId = pEnemyCity->GetID();
		int iPrevUnitDamage = 0;
		int iPrevUnitHitPoints = 0;

		pEnemyUnit = const_cast<CvUnit*>(TacticalAIHelpers::GetSimulatedGarrison(pEnemyCity, tactPlot->getEnemyUnits(), assumedPosition.GetUnitDamageDealt()));
		if (pEnemyUnit)
		{
			iPrevUnitDamage = assumedPosition.GetUnitDamage(pEnemyUnit->GetID());
			prevUnitDamage.SetValue(pEnemyUnit->GetID(), iPrevUnitDamage);
			iPrevUnitHitPoints = pEnemyUnit->GetMaxHitPoints() - pEnemyUnit->getDamage() - iPrevUnitDamage;
			prevUnitHitPoints.SetValue(pEnemyUnit->GetID(), iPrevUnitHitPoints);
		}

		int iGarrisonDamage = 0;

		//first try the cache
		if (!cache.findAttack(pUnit->GetID(),pUnitPlot->GetPlotIndex(), pEnemyCity->GetID(), pEnemyUnit ? pEnemyUnit->GetID() : -1, iSelfDamage, iPrevUnitDamage, iPrevCityDamage, iGarrisonDamage, iCityDamageDealt, iDamageReceived))
		{
			iCityDamageDealt = TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(pEnemyCity, pUnit, pUnitPlot, iDamageReceived, iGarrisonDamage, true, iSelfDamage, iPrevCityDamage, iPrevUnitDamage, true, true, pEnemyUnit);
			cache.storeAttack(pUnit->GetID(),pUnitPlot->GetPlotIndex(), pEnemyCity->GetID(), pEnemyUnit ? pEnemyUnit->GetID() : -1, iSelfDamage, iPrevUnitDamage, iPrevCityDamage, iGarrisonDamage, iCityDamageDealt, iDamageReceived);
		}

		iBonusScore += pUnit->GetRangeCombatSplashDamage(pTestPlot) + (pUnit->GetCityAttackPlunderModifier() / 50);
		iPrevCityHitPoints = pEnemyCity->GetMaxHitPoints() - pEnemyCity->getDamage() - iPrevCityDamage;


		bool bBlockaded = pEnemyCity->IsBlockadedWaterAndLand() || (CvStacking::IsEnabled()
			? HasVirtualCityEncirclement(assumedPosition, pEnemyCity)
			: tactPlot->getNumAdjacentFriendlies(CvTacticalPlot::TD_BOTH, -1) == pTestPlot->countPassableNeighbors(NO_DOMAIN));

		//but we don't want our melee units to die so take into account self damage and counterattacks
		if (!bRanged)
		{
			if (iCityDamageDealt >= iPrevCityHitPoints - 1)
			{
				// If we take the city, the unit also dies
				if (iPrevUnitHitPoints > 0)
				{
					iGarrisonDamage = iPrevUnitHitPoints;
				}
			}
			else
			{
				//if we have multiple units encircling the city, try to take into account their attacks as well
				//easiest way is to consider damage from last turn. so ideally ranged units start attacking and melee joins in later
				float fRemainingTurnsOnCity = iPrevCityHitPoints / (max(iCityDamageDealt * fAggBias, pEnemyCity->getDamageTakenLastTurn() * 1.0f) + 1);
				if (iPrevUnitHitPoints > 0)
					// killing the garrisoned unit is also valuable
					fRemainingTurnsOnCity = min(fRemainingTurnsOnCity, iPrevUnitHitPoints / (max(iGarrisonDamage + fAggBias, pEnemyUnit->GetDamageTakenLastTurn() * 1.0f) + 1));

				//if the city cannot heal, be even more aggressive
				if (bBlockaded)
					fRemainingTurnsOnCity = max(0.f, fRemainingTurnsOnCity - 1);

				//consider that we have other units around which can soak damage
				int iCounterattackDamage = pEnemyCity->canRangeStrike() ? pEnemyCity->rangeCombatDamage(pUnit, false, pUnitPlot, true) : 0;
				float fScaledCounterattackDamage = iCounterattackDamage / fAggBias;
				float fRemainingTurnsOnAttacker = pUnit->GetCurrHitPoints() / (iDamageReceived + fScaledCounterattackDamage + 1);

				//no attack if it's too early yet
				bool bGoodFirstAttack = pUnit->getDamage() < 13 && iCityDamageDealt + iGarrisonDamage > iDamageReceived && iDamageReceived < 23;
				if (fRemainingTurnsOnAttacker < fRemainingTurnsOnCity && !bGoodFirstAttack)
				{
					result->SetImpossible();
					return false;
				}
			}
		}

		//city blockaded? not 100% accurate, but anyway TODO actual figure out if it's blockaded
		if (bBlockaded)
		{
			iCityDamageDealt *= max(100 + /*0 in CP, 20 in VP*/ GD_INT_GET(BLOCKADED_CITY_ATTACK_MODIFIER), 0);
			iCityDamageDealt /= 100;
			iGarrisonDamage *= max(100 + /*0 in CP, 20 in VP*/ GD_INT_GET(BLOCKADED_CITY_ATTACK_MODIFIER), 0);
			iGarrisonDamage /= 100;
		}

		if (pEnemyUnit)
			unitDamageDealt.ChangeValue(pEnemyUnit->GetID(), iGarrisonDamage);
	}
	else if (tactPlot->isEnemyCombatUnit())
	{
		pEnemyUnit = const_cast<CvUnit*>(SelectCachedStackDefender(pUnit, pUnitPlot, pTestPlot, tactPlot->getEnemyUnits(), assumedPosition.GetUnitDamageDealt(), bRanged, iSelfDamage));
		if (!pEnemyUnit)
		{
			result->SetImpossible();
			return false;
		}

		int iPrevUnitDamage = assumedPosition.GetUnitDamage(pEnemyUnit->GetID());
		int iPrevUnitHitPoints = pEnemyUnit->GetCurrHitPoints() - iPrevUnitDamage;

		prevUnitDamage.SetValue(pEnemyUnit->GetID(), iPrevUnitDamage);
		prevUnitHitPoints.SetValue(pEnemyUnit->GetID(), iPrevUnitHitPoints);

		int iUnitDamageDealt = 0;

		//first use the cache
		int iCityDamageDealt;
		if (!cache.findAttack(pUnit->GetID(), pUnitPlot->GetPlotIndex(), pEnemyUnit->GetID(), -1, iSelfDamage, iPrevUnitDamage, 0, iUnitDamageDealt, iCityDamageDealt, iDamageReceived))
		{
			//use the quick and dirty method ... and don't check for general bonus etc (their position isn't official yet - we handle that below)
			iUnitDamageDealt = TacticalAIHelpers::GetSimulatedDamageFromAttackOnUnit(pEnemyUnit, pUnit, pTestPlot, pUnitPlot, iDamageReceived, true, iSelfDamage, iPrevUnitDamage, true);
			cache.storeAttack(pUnit->GetID(), pUnitPlot->GetPlotIndex(), pEnemyUnit->GetID(), -1, iSelfDamage, iPrevUnitDamage, 0, iUnitDamageDealt, iCityDamageDealt, iDamageReceived);
		}

		iBonusScore += pUnit->EstimatePlagueDamage(pEnemyUnit);

		//problem is flanking bonus affects combat strength, not damage, so the effect is nonlinear. anyway just assume 10% per adjacent unit
		if (!bRanged) //only for melee
		{
			//it works both ways!
			//note that this can go quite wrong if we're facing multiple enemy players!
   int iDelta = tactPlot->getNumAdjacentFriendlies(DomainForUnit(pUnit), assumedPlot->getPlotIndex()) - assumedPlot->getNumAdjacentEnemies(DomainForUnit(pUnit));
   if (CvStacking::IsEnabled())
   {
    iDelta = VirtualFlankPower(assumedPosition, pTestPlot, pEnemyUnit->getDomainType(), true, pUnit)
     - VirtualFlankPower(assumedPosition, pUnitPlot, pUnit->getDomainType(), false, pEnemyUnit);
    const int modifier = max(0, GD_INT_GET(BONUS_PER_ADJACENT_FRIEND));
    const int ratio = 100 + abs(iDelta) * modifier;
    // A stack can provide far more than six flankers. A linear subtraction
    // would turn retaliation negative and reward fictitious healing.
    iUnitDamageDealt = iDelta >= 0 ? iUnitDamageDealt * ratio / 100 : iUnitDamageDealt * 100 / ratio;
    iDamageReceived = iDelta >= 0 ? iDamageReceived * 100 / ratio : iDamageReceived * ratio / 100;
   }
   else
   {
    iUnitDamageDealt += (iDelta * iUnitDamageDealt) / 10;
    iDamageReceived -= (iDelta * iDamageReceived) / 10;
   }
		}

		//repeat attacks may give extra bonus
		if (iPrevUnitDamage > 0)
		{
			int iBonus = pUnit->getMultiAttackBonus() + GET_PLAYER(pUnit->getOwner()).GetPlayerTraits()->GetMultipleAttackBonus();
			if (iBonus > 0) //the bonus affects attack strength, so the effect is hard to predict ...
				iUnitDamageDealt += (iBonus * (iUnitDamageDealt + iPrevUnitDamage)) / 100;
		}

		//don't be as aggressive when attacking embarked units
		if (!pEnemyUnit->IsCanAttack())
			fAggBias /= 2;

		//don't be distracted by attacks on barbarians or melee units in other domain when there are real enemies around
		if ((pEnemyUnit->getOwner() == BARBARIAN_PLAYER || (!pEnemyUnit->IsCanAttackRanged() && pEnemyUnit->getDomainType() != pUnit->getDomainType())) && !tactPlot->isEnemyCity())
			bScoreReduction = true;

		unitDamageDealt.ChangeValue(pEnemyUnit->GetID(), iUnitDamageDealt);
	}

	// Splash damage is always applied
	int iSplashDamage = pUnit->getSplashDamage();
	if (iSplashDamage > 0)
	{
		CvPlot** aNeighbors = GC.getMap().getNeighborsUnchecked(pTestPlot);
		for (int i = 0; i < NUM_DIRECTION_TYPES; i++)
		{
			CvPlot* pAdjacentPlot = aNeighbors[i];
			if (!pAdjacentPlot)
				continue;

			const CvTacticalPlot* adjacentTactPlot = assumedPosition.getTactPlot(pAdjacentPlot->GetPlotIndex());
			if (!adjacentTactPlot)
				continue;

   const vector<const CvUnit*>& adjacentEnemies = adjacentTactPlot->getEnemyUnits();
   for (size_t j = 0; j < adjacentEnemies.size(); ++j)
   {
    const CvUnit* pAdjacentUnit = adjacentEnemies[j];
    if (pAdjacentPlot->isFortification(pAdjacentUnit->getTeam()))
     continue;
    prevUnitHitPoints.SetValue(pAdjacentUnit->GetID(), pAdjacentUnit->GetCurrHitPoints() - assumedPosition.GetUnitDamage(pAdjacentUnit->GetID()));
    unitDamageDealt.ChangeValue(pAdjacentUnit->GetID(), iSplashDamage);
   }
		}
	}

	//fake general bonus
	if (assumedPosition.HasSupport(pUnit->getDomainType()))
	{
		if (pEnemyUnit)
			unitDamageDealt.ChangeValue(pEnemyUnit->GetID(), unitDamageDealt.GetValue(pEnemyUnit->GetID()) / 10);
		iCityDamageDealt += iCityDamageDealt / 10;
		iDamageReceived -= iDamageReceived / 10;
	}

	//fake siege tower bonus
	if (assumedPosition.HasCitySupport() && tactPlot->isEnemyCity())
	{
		if (pEnemyUnit)
			unitDamageDealt.ChangeValue(pEnemyUnit->GetID(), unitDamageDealt.GetValue(pEnemyUnit->GetID()) / 5);
		iCityDamageDealt += iCityDamageDealt / 5;
		iDamageReceived -= iDamageReceived / 5;
	}

 if (CvStacking::IsEnabled() && bRanged)
 {
  const int primaryDamage = pEnemyCity ? iCityDamageDealt : (pEnemyUnit ? unitDamageDealt.GetValue(pEnemyUnit->GetID()) : 0);
  const vector<pair<const CvUnit*, int> > collateral = CvUnitCombat::GetStackCollateralDamage(pUnit, pTestPlot,
   pEnemyCity ? NULL : pEnemyUnit, primaryDamage, tactPlot->getEnemyUnits(), assumedPosition.GetUnitDamageDealt(),
   pEnemyCity ? pEnemyUnit : NULL, pEnemyCity && pEnemyUnit ? unitDamageDealt.GetValue(pEnemyUnit->GetID()) : 0, iPrevCityDamage);
  for (size_t i = 0; i < collateral.size(); ++i)
  {
   const CvUnit* victim = collateral[i].first;
   prevUnitHitPoints.SetValue(victim->GetID(), victim->GetCurrHitPoints() - assumedPosition.GetUnitDamage(victim->GetID()));
   unitDamageDealt.ChangeValue(victim->GetID(), collateral[i].second);
   iBonusScore += collateral[i].second * (StackCollateralWeight() - 100) / 100;
  }
 }

	int iTotalUnitDamageDealt = 0;
	SUnitIDValueContainer actualDamageDealt;
	int iTotalActualUnitDamageDealt = 0;
	bool bCityKill = false;
	bool bUnitKill = false;

	//bonus for a kill
	//don't be too precise because of randomness in damage calculation added later
	//if it doesn't work out we can try again
	//better than assuming it's not a kill and having a melee unit end up in a bad place
	if (iPrevCityHitPoints > 0 && iCityDamageDealt >= iPrevCityHitPoints)
	{
		bScoreReduction = false;

		iBonusScore += pUnit->GetExtraXPOnKill();

		//only melee can capture/kill a city!
		if (!bRanged && pUnit->IsCanAttackWithMove())
			bCityKill = true;
		else
		{
			if (iPrevCityHitPoints > 1)
				iBonusScore += min(iCityDamageDealt - iPrevCityHitPoints + 1, 3);
			iCityDamageDealt = min(iCityDamageDealt, iPrevCityHitPoints - 1);
		}
	}
	for (SUnitIDValueContainer::const_iterator it = unitDamageDealt.begin(); it != unitDamageDealt.end(); ++it)
	{
		int iPrevUnitHitPoints = prevUnitHitPoints.GetValue((*it).first);
		int iUnitDamageDealt = (*it).second;

		if (iUnitDamageDealt > iPrevUnitHitPoints)
			iBonusScore += min(iUnitDamageDealt - iPrevUnitHitPoints, 10);

		actualDamageDealt.SetValue((*it).first, min(iPrevUnitHitPoints, iUnitDamageDealt));

		iTotalUnitDamageDealt += iUnitDamageDealt;
		iTotalActualUnitDamageDealt += min(iPrevUnitHitPoints, iUnitDamageDealt);

		if (iPrevUnitHitPoints > 0 && iUnitDamageDealt >= iPrevUnitHitPoints)
		{
			if (pEnemyUnit && pEnemyUnit->GetID() == (*it).first)
				bUnitKill = true;

			iBonusScore += pUnit->GetExtraXPOnKill();

			bScoreReduction = false;

			if (pUnit->getHPHealedIfDefeatEnemy() > 0)
				iDamageReceived = max(iDamageReceived - pUnit->getHPHealedIfDefeatEnemy(), -pUnit->getDamage()); //may turn negative, but can't heal more than current damage

			// pillage fortification on kill?
			if (pUnit->IsPillageFortificationsOnKill())
			{
				if (pTestPlot->getImprovementType() != NO_IMPROVEMENT && !pTestPlot->IsImprovementPillaged())
				{
					CvImprovementEntry* pkImprovementInfo = GC.getImprovementInfo(pTestPlot->getImprovementType());
					if (pkImprovementInfo->IsNoFollowUp() && GET_PLAYER(pUnit->getOwner()).IsAtWarWith(pTestPlot->getOwner()))
					{
						iBonusScore += 15;
						// Citadel
						if (pkImprovementInfo->GetNearbyEnemyDamage() > 0 || pkImprovementInfo->GetDefenseModifier() >= 50)
						{
							iBonusScore += 15;
						}
					}
				}
			}

			// Only consider yield bonus for direct kills (not kills via splash damage)
			bool bYieldBonus = false;
			if (pEnemyUnit && pEnemyUnit->GetID() == (*it).first && pEnemyUnit->IsCombatUnit())
			{
				bYieldBonus = pUnit->GetGoldenAgeValueFromKills() > 0;

				if (!bYieldBonus)
				{
					UnitTypes eUnitType = pUnit->getUnitType();
					CvUnitEntry* pkUnitInfo = GC.getUnitInfo(eUnitType);

					for (int iI = 0; iI < NUM_YIELD_TYPES; iI++)
					{
						YieldTypes eYield = (YieldTypes)iI;

						bYieldBonus = (pEnemyUnit->isBarbarian() && (pUnit->getYieldFromBarbarianKills(eYield) || pkUnitInfo->GetYieldFromBarbarianKills(eYield)))
							|| pUnit->getYieldFromKills(eYield) || pkUnitInfo->GetYieldFromKills(eYield);

						if (bYieldBonus)
							break;
					}
				}

				if (bYieldBonus)
					iBonusScore += 20;
			}
		}
	}

	if (bCityKill)
		result->eAssignmentType = A_MELEEKILL;
	else if (bUnitKill)
	{
		if (bRanged)
			result->eAssignmentType = A_RANGEKILL;
		else if (pTestPlot->isFortification(pEnemyUnit->getTeam()) || iPrevCityHitPoints > 0 || tactPlot->getEnemyUnits().size() > 1)
			result->eAssignmentType = A_MELEEKILL_NO_ADVANCE;
		else
			result->eAssignmentType = A_MELEEKILL;
	}
	else
		result->eAssignmentType = bRanged ? A_RANGEATTACK : A_MELEEATTACK;

	result->iSelfDamage = iDamageReceived;
	result->unitDamage = unitDamageDealt;
    // Primary identity belongs to this projected attack, not to the savegame.
    // City garrison selection and stack defense can choose different units.
    result->iPrimaryUnitID = pEnemyUnit ? pEnemyUnit->GetID() : -1;
    result->ePrimaryUnitOwner = pEnemyUnit ? pEnemyUnit->getOwner() : (pEnemyCity ? pEnemyCity->getOwner() : NO_PLAYER);
	result->iCityDamage = iCityDamageDealt;

	//for melee units we check if the damage received is worth it ...
	if (iDamageReceived > 0 && gSafePlotCount[pUnit->GetID()] > 0)
	{
		float fAggFactor = /*100*/ GD_INT_GET(COMBAT_AI_OFFENSE_DAMAGEWEIGHT) / 100.f;
		switch (eAggLvl)
		{
		case AL_LOW:
			//want to do more damage than we take
			fAggFactor *= 0.7f;
			break;
		case AL_MEDIUM:
			//accept slightly more damage than we deal
			fAggFactor *= 1.1f;
			break;
		case AL_HIGH:
			//we check whether we can survive a counterattack in ScoreCombatUnitTurnEnd
			fAggFactor *= 2.3f;
			break;
		case AL_BRAVEHEART:
			//basically suicide
			fAggFactor *= 4.2f;
			break;
		default:
			result->SetImpossible();
			return false;
		}

		//need to consider danger as well
		//if there are many enemies around we need our melee units as shields, don't waste hp on attacks
		const CvPlot* pPlotAfterAttack = result->eAssignmentType == A_MELEEKILL ? pTestPlot : pUnitPlot;

		CvTacticalPosition pNewPosition;
		GetNextPosition(assumedPosition, result, pNewPosition);
		int iDanger = GetUnitDangerForPlot(pUnit, pPlotAfterAttack, iSelfDamage + iDamageReceived, pNewPosition);

		bool bBelowHpLimitAfterMeleeAttack = iDanger > pUnit->GetMaxHitPoints();
		//should consider self-damage from previous attacks here ... blitz
		if (iDamageReceived > 0 && pUnit->GetCurrHitPoints() - iDamageReceived < hpLimit[eAggLvl])
			bBelowHpLimitAfterMeleeAttack = true;

		//bias depends on the ratio of friendly to enemy units
		int iScaledDamage = int((iTotalUnitDamageDealt + iCityDamageDealt) * fAggBias * fAggFactor + 0.5f);
		int iDamageDelta = iScaledDamage - iDamageReceived;
		bool bVoluntaryCancel = (bBelowHpLimitAfterMeleeAttack && iDamageDelta < 0 && result->eAssignmentType != A_MELEEKILL && result->eAssignmentType != A_MELEEKILL_NO_ADVANCE);
		bool bSuicideCancel = (pUnit->GetCurrHitPoints() - iDamageReceived < 3) && eAggLvl != AL_BRAVEHEART; //in the real event there will be some randomness!
		if (bVoluntaryCancel || bSuicideCancel)
		{
			result->SetImpossible();
			return false;
		}
	}

	//finally the almighty score
	//add previous damage again and again to make concentrated fire attractive
	//todo: consider pEnemy->getUnitInfo().GetProductionCost() and pEnemy->GetBaseCombatStrength()
	//todo: normalize damage done by max hp to balance between city attacks and unit attacks?

	int iActualCityDamageDealt = min(iCityDamageDealt, iPrevCityHitPoints + (pUnit->IsCanAttackRanged() ? 2 : 10));

	int iActualDamageTaken = min(iDamageReceived, pUnit->GetCurrHitPoints() - iSelfDamage);
	if (iActualDamageTaken < 0)
		iActualDamageTaken = max(iActualDamageTaken, -(pUnit->getDamage() + iSelfDamage));


	// Focus on low HP units/cities
	int iTotalActualDamageDealt = iActualCityDamageDealt + iTotalActualUnitDamageDealt;
	if (iTotalActualDamageDealt > 0)
	{
		int iPrevUnitHitPoints = pEnemyUnit ? prevUnitHitPoints.GetValue(pEnemyUnit->GetID()) : 0;
		int iHpAfterAttack = iPrevUnitHitPoints > 0 ? iPrevUnitHitPoints - actualDamageDealt.GetValue(pEnemyUnit->GetID()) : -1;
		if (iHpAfterAttack == -1 || iHpAfterAttack > iPrevCityHitPoints - iActualCityDamageDealt)
			iHpAfterAttack = iPrevCityHitPoints - iActualCityDamageDealt;
		iBonusScore += min(max(30 - iHpAfterAttack, 0), iTotalActualDamageDealt);
	}

	if (bScoreReduction)
		iBonusScore -= 10;

	if (bCityKill)
		iBonusScore += 100;
	else if (bUnitKill)
		iBonusScore += 15;

	result->SetScore(0, iBonusScore, iActualCityDamageDealt + iTotalActualUnitDamageDealt - iActualDamageTaken);

	return bCityKill || bUnitKill;
}

bool TacticalAIHelpers::IsPlayerCitadel(const CvPlot* pPlot, PlayerTypes ePlayer)
{
	if (!pPlot || ePlayer==NO_PLAYER || pPlot->getOwner() != ePlayer)
		return false;

	// Citadel here?
	ImprovementTypes eImprovement = pPlot->getImprovementType();
	if (eImprovement != NO_IMPROVEMENT && !pPlot->IsImprovementPillaged())
	{
		CvImprovementEntry* pInfo = GC.getImprovementInfo(eImprovement);
		if (pInfo->GetNearbyEnemyDamage() <= /*10 in CP, 5 in VP*/ GD_INT_GET(ENEMY_HEAL_RATE))
			return false;

		if (pInfo->GetDefenseModifier() < 50)
			return false;

		return true;
	}
	
	return false;
}

int TacticalAIHelpers::GetOtherPlayerImprovementDamage(const CvPlot* pPlot, PlayerTypes ePlayer, bool bCheckWar)
{
	if (!pPlot || ePlayer==NO_PLAYER || !pPlot->isOwned())
		return 0;

	// Citadel here?
	ImprovementTypes eImprovement = pPlot->getImprovementType();
	if (eImprovement != NO_IMPROVEMENT && !pPlot->IsImprovementPillaged())
	{
		CvImprovementEntry* pInfo = GC.getImprovementInfo(eImprovement);
		if (pInfo->GetNearbyEnemyDamage() == 0)
			return 0;

		if (!bCheckWar || GET_PLAYER(ePlayer).IsAtWarWith(pPlot->getOwner()))
			return pInfo->GetNearbyEnemyDamage();
	}
	
	return 0;
}

int TacticalAIHelpers::SentryScore(const CvPlot * pPlot, PlayerTypes ePlayer)
{
	TeamTypes eTeam = GET_PLAYER(ePlayer).getTeam();
	int iScore = pPlot->defenseModifier(eTeam, false, false);

	//basically check for plots with good visibility
	const vector<CvPlot*>& possibleEnemyPlots = GC.getMap().GetPlotsAtRangeX(pPlot, 2, true, true);
	for (size_t i = 0; i < possibleEnemyPlots.size(); i++)
	{
		//there may be a sentinel null pointer
		if (possibleEnemyPlots[i] == NULL)
			continue;
		//really we should consider whether the enemy can move there, not our team ...
		if (!possibleEnemyPlots[i]->isValidMovePlot(ePlayer, false))
			continue;

		iScore += 23; //less than a good defense bonus ...
	}

	return iScore;
}

static int HealUnitsInPlot(SUnitIDValueContainer& unitHealing, int& iDamageDelta, const CvTacticalPlot* tactPlot, int iHealAmount, const CvTacticalPosition& assumedPosition)
{
	if (!tactPlot)
		return 0;

	const CvTacticalPlot::UnitList& units = tactPlot->getUnitsAtPlot();
	for (CvTacticalPlot::UnitList::const_iterator it = units.begin(); it != units.end(); ++it)
	{
		CvUnit* pUnit = GET_PLAYER(assumedPosition.getPlayer()).getUnit(it->iUnitID);
		if (!pUnit)
			continue;

		const SUnitStats* unit = assumedPosition.GetUnitStats(it->iUnitID);

		int iActualHealAmount = min(iHealAmount, pUnit->GetCurrHitPoints() - (unit ? unit->iSelfDamage : 0));
		unitHealing.ChangeValue(pUnit->GetID(), iActualHealAmount);
		iDamageDelta += iActualHealAmount;
	}

	return iDamageDelta;
}

static int HealAdjacentUnits(SUnitIDValueContainer& unitHealing, int& iDamageDelta, const CvPlot* pPlot, int iDamageAmount, const CvTacticalPosition& assumedPosition)
{
	CvPlot** aNeighbors = GC.getMap().getNeighborsUnchecked(pPlot);
	int iHealing = 0;
	for (int i = 0; i < NUM_DIRECTION_TYPES; i++)
	{
		CvPlot* pAdjacentPlot = aNeighbors[i];
		if (!pAdjacentPlot)
			continue;

		const CvTacticalPlot* adjacentTactPlot = assumedPosition.getTactPlot(pAdjacentPlot->GetPlotIndex());
		if (!adjacentTactPlot)
			continue;

		iHealing += HealUnitsInPlot(unitHealing, iDamageDelta, adjacentTactPlot, iDamageAmount, assumedPosition);
	}
	return iHealing;
}

static int DamageUnitInPlot(SUnitIDValueContainer& unitDamage, int& iDamageDelta, const CvPlot* pPlot, const CvTacticalPlot* tactPlot, int iDamageAmount, const CvTacticalPosition& assumedPosition)
{
 int total = 0;
 const vector<const CvUnit*>& enemies = tactPlot->getEnemyUnits();
 for (size_t i = 0; i < enemies.size(); ++i)
 {
  const CvUnit* unit = enemies[i];
  if (pPlot->isFortification(unit->getTeam()))
   continue;
  const int hit = min(iDamageAmount, max(0, unit->GetCurrHitPoints() - assumedPosition.GetUnitDamage(unit->GetID())));
  unitDamage.ChangeValue(unit->GetID(), hit);
  total += hit;
 }
 iDamageDelta += total;
 return total;
}

static int DamageAdjacentUnits(SUnitIDValueContainer& unitDamage, int& iDamageDelta, const CvPlot* pPlot, int iDamageAmount, const CvTacticalPosition& assumedPosition)
{
	int iDamage = 0;
	CvPlot** aNeighbors = GC.getMap().getNeighborsUnchecked(pPlot);
	for (int i = 0; i < NUM_DIRECTION_TYPES; i++)
	{
		const CvPlot* pAdjacentPlot = aNeighbors[i];
		if (!pAdjacentPlot)
			continue;

		const CvTacticalPlot* adjacentTactPlot = assumedPosition.getTactPlot(pAdjacentPlot->GetPlotIndex());
		if (!adjacentTactPlot)
			continue;

		iDamage += DamageUnitInPlot(unitDamage, iDamageDelta, pAdjacentPlot, adjacentTactPlot, iDamageAmount, assumedPosition);
	}
	return iDamage;
}

static int GetPrevPlotScore(int iUnitID, const CvBasePosition& position)
{
	const STacticalAssignment* prevAssignment = position.getLatestAssignment(iUnitID);
	return prevAssignment ? prevAssignment->GetPlotScore() : 0;
}

// Preferred scoring holds one actor and one immutable assignment history.
// Damage-only previews borrow that same history; other histories/actors retain
// the ordinary accessor. Forecast revision/depth guards reject nested searches
// and yields which can recycle shared position slots. No pointer escapes.
struct PreviousPlotScoreQuery
{
 const int unitID;
 const vector<STacticalAssignment>* const history;
 const bool eligible;
 const unsigned long revision;
 const long scene;
 bool ready;
 int score;
 PreviousPlotScoreQuery(int actor, const CvBasePosition& position):
  unitID(actor),history(&position.getAssignments()),eligible(StackForecastContext()),
  revision(eligible ? gStackForecastRevision : 0),
  scene(eligible ? CvStackingStrengthCache::SceneEpoch() : 0),ready(false),score(0) {}
 int Get(int actor, const CvBasePosition& position)
 {
  if (!eligible || !gStackForecastsActive || gStackForecastDepth != 1 ||
   revision != gStackForecastRevision || actor != unitID || &position.getAssignments() != history ||
   scene != CvStackingStrengthCache::SceneEpoch())
   return GetPrevPlotScore(actor, position);
  if (!ready)
  {
   score = GetPrevPlotScore(actor, position);
   ready = true;
  }
  return score;
 }
private:
 PreviousPlotScoreQuery(const PreviousPlotScoreQuery&);
 PreviousPlotScoreQuery& operator=(const PreviousPlotScoreQuery&);
};

static int GetPrevPlotScore(int unitID, const CvBasePosition& position, PreviousPlotScoreQuery* previousScore)
{
 return previousScore ? previousScore->Get(unitID, position) : GetPrevPlotScore(unitID, position);
}


static STacticalAssignment* ScorePlotForPillageMove(const SUnitStats& unit, const CvTacticalPlot* testPlot, int iAssumedMovesLeft, const CvTacticalPosition& assumedPosition, PreviousPlotScoreQuery* previousScore = NULL)
{
	//default action is do nothing and invalid score (not -INT_MAX, to prevent overflows!)
	STacticalAssignment* result = gAssignmentStorage.peekNext();
	result->init(unit.iPlotIndex,testPlot->getPlotIndex(), unit.iUnitID, iAssumedMovesLeft, unit.eMoveStrategy, A_PILLAGE, GetPrevPlotScore(unit.iUnitID, assumedPosition, previousScore));

	//the plot we're checking right now
	const CvPlot* pTestPlot = testPlot->getPlot();
	const CvUnit* pUnit = unit.pUnit;

	int iDamageDelta = 0;
	int iSelfDamage = 0;
	int iBonusScore = 0;

	if (!pUnit->canPillage(pTestPlot) || assumedPosition.plotHasAssignmentOfType(testPlot->getPlotIndex(), A_PILLAGE))
		return result;

	if (pUnit->canPillage(pTestPlot) && !assumedPosition.plotHasAssignmentOfType(testPlot->getPlotIndex(), A_PILLAGE))
	{
		if (!unit.pUnit->hasFreePillageMove())
			result->iRemainingMoves -= min((int)result->iRemainingMoves, GD_INT_GET(MOVE_DENOMINATOR));

		int iImprovementDamage = TacticalAIHelpers::GetOtherPlayerImprovementDamage(pTestPlot, assumedPosition.getPlayer(), true);
		if (iImprovementDamage > 0)
			iBonusScore += iImprovementDamage;
		if (iImprovementDamage < 15 && pTestPlot->getResourceType(pUnit->getTeam()) != NO_RESOURCE && GC.getResourceInfo(pTestPlot->getResourceType(pUnit->getTeam()))->getResourceUsage() == RESOURCEUSAGE_STRATEGIC)
			iBonusScore += 15;
		else if (iImprovementDamage < 10 && pTestPlot->getOwner() != NO_PLAYER && pTestPlot->getRouteType() != NO_ROUTE && (pTestPlot->isHills() || pTestPlot->IsTerrainDesert() || pTestPlot->IsFeatureMarsh() || pTestPlot->IsFeatureForest() || pTestPlot->isRiver()))
		{
			// route in rough terrain?
			iBonusScore += 10;
		}
		
		if (pUnit->getPillageHealAmount(pTestPlot) > 0)
		{
			int iHealAmount = pUnit->getPillageHealAmount(pTestPlot);
			if (iHealAmount > pUnit->getDamage() + unit.iSelfDamage)
				iHealAmount = pUnit->getDamage() + unit.iSelfDamage;

			if (iHealAmount > 0)
			{
				iSelfDamage -= iHealAmount;
				iDamageDelta += iHealAmount;
			}
		}

		if (pTestPlot->getImprovementType() != NO_IMPROVEMENT && !pTestPlot->IsImprovementPillaged())
		{
			iBonusScore += pUnit->GetXPFromPillaging();

			int iAOEHeal = pUnit->getAOEHealOnPillage() > 0;
			if (iAOEHeal > 0)
				HealAdjacentUnits(result->unitHealing, iDamageDelta, pTestPlot, iAOEHeal, assumedPosition);

			int iAOEDamage = pUnit->getAOEDamageOnPillage() > 0;
			if (iAOEDamage > 0)
				DamageAdjacentUnits(result->unitDamage, iDamageDelta, pTestPlot, iAOEDamage, assumedPosition);
		}
	}

	result->iSelfDamage = iSelfDamage;
	result->SetScore(0, iBonusScore, iDamageDelta);
	
	return result;
}


bool isKillAssignment(eUnitAssignmentType eAssignmentType)
{
	return eAssignmentType == A_MELEEKILL ||
		eAssignmentType == A_MELEEKILL_NO_ADVANCE ||
		eAssignmentType == A_RANGEKILL;
}

int ScoreCombatUnitTurnEnd(const CvUnit* pUnit, eUnitAssignmentType eLastAssignment, const CvTacticalPlot* testPlot, int iDanger,
							CvTacticalPlot::eTactPlotDomain eRelevantDomain, int iSelfDamage,
							const CvTacticalPosition& assumedPosition, eUnitMoveEvalMode evalMode, bool bRelaxedCheck, bool bOnlyCheckImpossible)
{
 CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_TURN_END); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
	int iResult = 0;
	const CvPlot* pTestPlot = testPlot->getPlot();

	//the danger value reflects any defensive terrain bonuses
	//but unfortunately danger is not very useful here
	// * ZOC is unclear during simulation
	// * freshly revealed enemy units are not considered
	int iNumAdjFriendlies = (evalMode==EM_FINAL) ? testPlot->getNumAdjacentFriendliesEndTurn(eRelevantDomain) : testPlot->getNumAdjacentFriendlies(eRelevantDomain, -1);
 if (StackPreferencesEnabled())
 {
  iNumAdjFriendlies += max(0, (int)CountVirtualFriendlyStack(assumedPosition, pTestPlot, pUnit) - 1);
 }

	if (bRelaxedCheck) //assume we have friends which might catch up to us later
		iNumAdjFriendlies++;
	bool bIsFrontlineCitadelOrCity = (TacticalAIHelpers::IsPlayerCitadel(pTestPlot, assumedPosition.getPlayer()) || pTestPlot->isCity()) && pUnit->getDomainType() == DOMAIN_LAND && testPlot->getEnemyDistance() < 3;

	//don't do it if it's a death trap (unless there is no other choice ...)
	int iNumAdjEnemies = testPlot->getNumAdjacentEnemies(CvTacticalPlot::TD_BOTH);
	if (iNumAdjEnemies > 3 || (iNumAdjEnemies == 3 && assumedPosition.getAggressionBias() < 1))
		if (!bIsFrontlineCitadelOrCity)
			return INT_MAX;

	int iMaxHitPoints = pUnit->GetMaxHitPoints();
	int iCurrHitPoints = iMaxHitPoints - pUnit->getDamage() - iSelfDamage;

	//unseen enemies might be hiding behind the edge, so assume danger there
	if (testPlot->isEdgePlot())
	{
		//siege units (with limited visibility) should not move there unless covered (the -1 is important)
		if (pUnit->visibilityRange() < 2 && testPlot->getNumAdjacentFriendlies(DomainForUnit(pUnit), -1) < 2)
		{
			VirtualFriendlyStackQuery stack;
			GetVirtualFriendlyStack(assumedPosition, pTestPlot, pUnit, iSelfDamage, stack.candidates, stack.damage);
			if (!HasSurvivingStackProtection(pUnit, pTestPlot, stack.candidates, stack.damage, assumedPosition.GetUnitDamageDealt(), iDanger))
				return INT_MAX;
		}
		
		iDanger = max(iMaxHitPoints / 2, iDanger);
	}
	// Stack danger already assigns each hit to its actual protecting member.
	// Legacy adjacent-cover discount would credit that protection a second time.
	if (!MOD_COMBATAI_TWO_PASS_DANGER && !bOnlyCheckImpossible && !CvStacking::IsEnabled())
	{
		if (iDanger > 0 && (iDanger > iMaxHitPoints || !testPlot->isEdgePlot()) && testPlot->hasCoverFromOtherUnits(assumedPosition))
			//check for cover and assume this would help us
			iDanger /= 2;
	}

	if (iDanger > 0)
	{
		//avoid extreme danger, except in citadels
		if (!bIsFrontlineCitadelOrCity && assumedPosition.getAggressionLevel() != AL_BRAVEHEART)
		{
			//extra careful with ranged / siege units / carriers
			if (pUnit->AI_getUnitAIType() == UNITAI_RANGED || pUnit->AI_getUnitAIType() == UNITAI_CITY_BOMBARD || pUnit->AI_getUnitAIType() == UNITAI_CARRIER_SEA)
			{
				if (iDanger > iCurrHitPoints)
					return INT_MAX;
			}

			//the minimum amount of hitpoint we want a standalone unit to have for the expected counterattacks
			bool isForKill = (eLastAssignment == A_MELEEKILL || eLastAssignment == A_MELEEKILL_NO_ADVANCE || eLastAssignment == A_RANGEKILL);
			bool couldFlee = (gSafePlotCount[pUnit->GetID()] > 0);
			int iMagicNumber = (isForKill || !couldFlee)  ? 23 : 42;

			//if this is the only enemy ...
			if (assumedPosition.getNumEnemies() == 1 && isForKill)
				iMagicNumber = 12;

			//if there is nothing we would cover or that covers us or we are low on health, don't do it
			if (iCurrHitPoints * iCurrHitPoints < iMagicNumber * iDanger)
				return INT_MAX;
		}

		if (!bOnlyCheckImpossible)
		{
			//make it relative to current hitpoints
			int iScaledDanger = (iDanger * /*100*/ GD_INT_GET(COMBAT_AI_OFFENSE_DANGERWEIGHT)) / max(1, iCurrHitPoints);

			//danger values can get very high if there are many enemy units around, so try to normalize this a bit
			//this maps 225 to 225, higher values get flattened
			if (iScaledDanger > 225)
				iScaledDanger = 15 * sqrti(iScaledDanger);

			//try to be more careful with highly promoted units
			iScaledDanger += (pUnit->getExperienceTimes100() - GET_PLAYER(assumedPosition.getPlayer()).GetAvgUnitExp100()) / 200;

			//no reason to run into the enemy alone
			if (iNumAdjFriendlies == 0)
				iScaledDanger *= 2;

			//penalty for high danger plots (should this be personality dependent?)
			iResult -= iScaledDanger;
		}
	}

	if (bOnlyCheckImpossible)
		return 1;

	//try to stay together, in pairs at least
	if (iNumAdjFriendlies > 0)
	{
		//very vulnerable units
		if (pUnit->AI_getUnitAIType() == UNITAI_CARRIER_SEA || pUnit->AI_getUnitAIType() == UNITAI_CITY_BOMBARD)
			iResult += iNumAdjFriendlies * 11;
		else
			iResult += 7 + iNumAdjFriendlies;
	}
	//when in doubt, stay under air cover
	if (testPlot->hasAirCover())
		iResult+=3;
	//when in doubt, hide from the enemy
	if (!pTestPlot->IsKnownVisibleToEnemy(pUnit->getOwner()))
		iResult++;

	//try to occupy enemy citadels!
	int iImprovementDamage = TacticalAIHelpers::GetOtherPlayerImprovementDamage(pTestPlot, assumedPosition.getPlayer(), true);
	if (iImprovementDamage > 0)
		iResult += iImprovementDamage / 3;

	//also occupy our own citadels
	if (bIsFrontlineCitadelOrCity)
	{
		if (pUnit->GetRange() > 1 || testPlot->getNumAdjacentFriendlies(CvTacticalPlot::TD_LAND, -1)==0 || testPlot->getNumAdjacentEnemies(CvTacticalPlot::TD_LAND)>0)
			iResult += TACTICAL_COMBAT_CITADEL_BONUS;
		else
			iResult += TACTICAL_COMBAT_CITADEL_BONUS/2;
	}

	//try not to be a sitting duck (faster than isNativeDomain but not entirely accurate)
	if (pUnit->getDomainType() != pTestPlot->getDomain())
		iResult-=3;

	//sometimes danger is zero, but maybe we're wrong, so look at plot defense too
	iResult += pTestPlot->defenseModifier(pUnit->getTeam(),false,false) / 5;

	//todo: take into account mobility at the proposed plot
	//todo: take into account ZOC when ending the turn

	return iResult;
}

static int CalculateLeavingStackProtectionScore(const SUnitStats& unit, const CvTacticalPosition& assumedPosition)
{
 const CvUnit* pUnit = unit.pUnit;
 const CvPlot* source = GC.getMap().plotByIndexUnchecked(unit.iPlotIndex);
 VirtualFriendlyStackQuery stack;
 vector<const CvUnit*>& before = stack.candidates;
 SUnitIDValueContainer& damage = stack.damage;
 GetVirtualFriendlyStack(assumedPosition, source, pUnit, unit.iSelfDamage, before, damage);
 vector<const CvUnit*> after = before;
 after.erase(std::remove(after.begin(), after.end(), pUnit), after.end());
 StackDangerOutcomeBatch beforeOutcome(source, before, damage, assumedPosition.GetUnitDamageDealt());
 StackDangerOutcomeBatch afterOutcome(source, after, damage, assumedPosition.GetUnitDamageDealt());
 int score = 0;
 for (size_t i = 0; i < after.size(); ++i)
 {
  const CvUnit* ranged = after[i];
  if (!ranged->IsCanAttackRanged())
   continue;
  const int oldDanger = min(ranged->GetMaxHitPoints(), GetCachedStackDanger(ranged, source, before, damage, assumedPosition.GetUnitDamageDealt(), &beforeOutcome));
  const int newDanger = min(ranged->GetMaxHitPoints(), GetCachedStackDanger(ranged, source, after, damage, assumedPosition.GetUnitDamageDealt(), &afterOutcome));
  if (newDanger > oldDanger)
   score -= (newDanger - oldDanger) * CvStacking::GetIntByKey(CvStacking::HOT_AIStackLeaveProtectorPenalty, 30) / max(1, ranged->GetMaxHitPoints());
 }
 return score;
}

// Ordinary destination siblings share one immutable source position. Keep this
// memo local to that unit's enumeration, never across hypothetical attacks or
// different searches, and reject reuse/admission after any scene callback.
struct LeavingStackProtectionMemo
{
 bool ready;
 const CvTacticalPosition* position;
 const CvUnit* protector;
 int sourceIndex, selfDamage, score;
 unsigned long revision;
 long scene;
 LeavingStackProtectionMemo():ready(false),position(NULL),protector(NULL),sourceIndex(-1),selfDamage(0),score(0),revision(0),scene(0) {}
 int Get(const SUnitStats& unit, const CvTacticalPosition& assumedPosition)
 {
  const bool cacheable = StackForecastContext();
  const unsigned long currentRevision = cacheable ? gStackForecastRevision : 0;
  const long currentScene = cacheable ? gStackForecastSceneEpoch : 0;
  if (cacheable && ready && position == &assumedPosition && protector == unit.pUnit &&
   sourceIndex == unit.iPlotIndex && selfDamage == unit.iSelfDamage && revision == currentRevision && scene == currentScene)
   return score;
  const int result = CalculateLeavingStackProtectionScore(unit, assumedPosition);
  ready = cacheable && StackForecastContext() && gStackForecastRevision == currentRevision && gStackForecastSceneEpoch == currentScene;
  if (ready)
  {
   position = &assumedPosition; protector = unit.pUnit;
   sourceIndex = unit.iPlotIndex; selfDamage = unit.iSelfDamage;
   revision = currentRevision; scene = currentScene; score = result;
  }
  return result;
 }
};

static STacticalAssignment* ScorePlotForCombatUnitMove(const SUnitStats& unit, const CvTacticalPlot* testPlot, const CvTacticalPosition& assumedPosition, eUnitMoveEvalMode evalMode, LeavingStackProtectionMemo* leavingProtection = NULL, PreviousPlotScoreQuery* previousScore = NULL)
{
 CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_COMBAT_MOVE); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
	//default action is do nothing and invalid score (not -INT_MAX, to prevent overflows!)
	STacticalAssignment* result = gAssignmentStorage.peekNext();
	result->init(unit.iPlotIndex,testPlot->getPlotIndex(), unit.iUnitID, unit.iMovesLeft, unit.eMoveStrategy, A_MOVE, GetPrevPlotScore(unit.iUnitID, assumedPosition, previousScore));

	//the plot we're checking right now
	const CvPlot* pTestPlot = testPlot->getPlot();
	const CvUnit* pUnit = unit.pUnit;

	//different contributions
	int iDangerScore = 0;
	int iPlotScore = 0;
	int iBonusScore = 0;
	int iDamageDelta = 0;
	int iSelfDamage = 0;

	int iCurrentHealth = pUnit->GetCurrHitPoints() - unit.iSelfDamage;

	bool bMoving = unit.iPlotIndex != pTestPlot->GetPlotIndex();

	if (!bMoving)
		result->eAssignmentType = A_FINISH_TEMP;

	//ranged attacks are cross-domain
	CvTacticalPlot::eTactPlotDomain eRelevantDomain = pUnit->IsCanAttackRanged() ? CvTacticalPlot::TD_BOTH : pTestPlot->isWater() ? CvTacticalPlot::TD_SEA : CvTacticalPlot::TD_LAND;

	// Skirmishers should go to the front line when they can attack
	eUnitMovementStrategy eMoveStrategy = unit.eMoveStrategy;
	bool bSkirmisher = unit.iAttacksLeft > 0 && pUnit->GetRange() == 1 && (unit.iMovesLeft > GD_INT_GET(MOVE_DENOMINATOR) || (!pUnit->canMoveAfterAttacking() && unit.iMovesLeft > 0));
	if (bSkirmisher)
		eMoveStrategy = MS_FIRSTLINE;

	//zero to TACTICAL_COMBAT_MAX_TARGET_DISTANCE
	static const int iPlotScoreForEnemyDistanceLandAttack[5][5] = {
		{ -1,-1,-1,-1,-1 }, //none (should not occur)
		{ 12, 12, 6, 1, -1 }, //firstline (note that it's ok to evaluate the score in an enemy plot for a firstline unit -> meleekill) 
		{ -1, 8, 12, 2, -1 }, //secondline
		{  1, 1, 8, 12, -1 }, //thirdline (ranged and damaged melee units)
		{ -1, 1, 8,  8, -1 }, //support (can also happen for damaged melee units)
	};
	static const int iPlotScoreForEnemyDistanceSeaAttack[5][5] = {
		{ -1,-1,-1,-1,-1 }, //none (should not occur)
		{ 12, 8, 6, 1, -1 }, //firstline (note that it's ok to evaluate the score in an enemy plot for a firstline unit -> meleekill) 
		{ -1, 8, 8, 6, -1 }, //secondline
		{  1, 6, 8, 8, -1 }, //thirdline (ranged and damaged melee units)
		{ -1, 1, 8,  8, -1 }, //support (can also happen for damaged melee units)
	};
	static const int iPlotScoreForTargetDistanceEscort[5][5] = {
		{ -1,-1,-1,-1,-1 }, //none (should not occur)
		{  6, 6, 5, 3, 1 }, //firstline can go anywhere but outside when in doubt
		{  8, 8, 3, 2, 1 }, //secondline prefers "inside"
		{  10, 10, 2, 1, 1 }, //thirdline prefers inside even more
		{  8, 8, 2, 1, 1 }, //support (can also happen for damaged melee units)
	};

	//lookup desirability by unit strategy / enemy distance
	//even for intermediate plots, so as not to bias against them
	if (assumedPosition.haveEnemies())
	{
		int iEnemyDistance = !pUnit->IsCanAttackRanged() || pUnit->IsRangeAttackIgnoreLOS() || pUnit->GetRange() < 2
			? testPlot->getEnemyDistance(eRelevantDomain)
			: testPlot->getRangedAttackEnemyDistance(eRelevantDomain);

		iPlotScore = pUnit->getDomainType() != DOMAIN_SEA
			? iPlotScoreForEnemyDistanceLandAttack[eMoveStrategy][iEnemyDistance]
			: iPlotScoreForEnemyDistanceSeaAttack[eMoveStrategy][iEnemyDistance];

		if (pTestPlot->isFriendlyCity(*pUnit))
		{
			// Rear-city safety is not an objective for every healthy member of a stack.
			const bool rearSurplus = CvStackingAI::Enabled(pUnit->getOwner()) && iEnemyDistance>=3 &&
				(!pUnit->IsGarrisoned() || pUnit->getArmyID()!=-1) && iCurrentHealth*100>=pUnit->GetMaxHitPoints()*CvStacking::GetInt("AIRearCityHealthyPercent",70);
			iPlotScore = rearSurplus ? CvStacking::GetInt("AIRearCityPlotScore",6) : 12;
		}
		// wounded units and scouts can go wherever as long as they don't die (danger checked later)
		else if (iCurrentHealth < gMinHpForTactsim || pUnit->getUnitInfo().GetDefaultUnitAIType() == UNITAI_EXPLORE)
			iPlotScore = 12;

		// move skirmishers in to fire
		if (bSkirmisher && iEnemyDistance == 1)
			iPlotScore += 3;

		// if we are not in a good spot, try moving
		if (iPlotScore <= 6 && pTestPlot == pUnit->plot() && pUnit->getDamage() + unit.iSelfDamage < 10)
			iPlotScore -= 2;

		// Move melee units in to capture cities
		if (!pUnit->IsCanAttackRanged() && testPlot->getEnemyDistance() == 1)
		{
			CvCity* pAdjacentCity = pTestPlot->GetAdjacentCity();
			if (pAdjacentCity && pAdjacentCity->GetMaxHitPoints() - pAdjacentCity->getDamage() <= 5 && GET_PLAYER(pAdjacentCity->getOwner()).IsAtWarWith(pUnit->getOwner()))
				iPlotScore += 5;
		}

		//if we made a kill, assume we are in a good plot
		//this is very important because enemy distance changes and we might end up with -1
		if (isKillAssignment(unit.eLastAssignment))
			iPlotScore = max(6, iPlotScore);
	}
	else
	{
		//we have no enemies around prepare for the unexpected, melee units screening far from the target, other units closer
		int iTargetDistance = min(plotDistance(*assumedPosition.getTarget(), *pTestPlot), (int)TACTICAL_COMBAT_MAX_TARGET_DISTANCE);

		iPlotScore += iPlotScoreForTargetDistanceEscort[eMoveStrategy][iTargetDistance];
	}

	if (bMoving && testPlot->isEnemyCivilian()) //unescorted civilian
	{
		if (unit.iMovesLeft > 0 || testPlot->getNumAdjacentEnemies(CvTacticalPlot::TD_LAND) == 0)
		{
			CvUnit* pCivilian;
			for (int iI = 0; iI < pTestPlot->getNumUnits(); iI++)
			{
				pCivilian = pTestPlot->getUnitByIndex(iI);
				if (pCivilian && pCivilian->IsCivilianUnit() && GET_PLAYER(pUnit->getOwner()).IsAtWarWith(pCivilian->getOwner()))
				{
					//workers are not so important ...
					iBonusScore += (pCivilian->AI_getUnitAIType() == UNITAI_WORKER) ? 20 : 150;
					result->eAssignmentType = A_CAPTURE; //important so that the next assignment can be a move again
				}
			}
		}
	}

	// empty barbarian camp
	if (bMoving && pTestPlot->getRevealedImprovementType(pUnit->getTeam()) == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT))
	{
		if (!testPlot->isEnemyCombatUnit())
		{
			if (assumedPosition.isEarlyFinish(true))
				iPlotScore = 12;
			iBonusScore += 100;
		}
	}

	//give a bonus for potential fortifying/healing
	if (result->eAssignmentType == A_FINISH_TEMP)
	{
		if (unit.iMovesLeft == unit.iMaxMoves)
		{
			if (pUnit->getDamage() + unit.iSelfDamage > 0 && !pUnit->IsCannotHeal(/*bConsiderResourceShortage*/ false) && !pUnit->isEmbarked())
			{
				int iHealRate = pUnit->ActualHealRate(pTestPlot, false);

				if (iHealRate > 0)
				{
					if (iHealRate > pUnit->getDamage() + unit.iSelfDamage)
						iHealRate = pUnit->getDamage() + unit.iSelfDamage;

					iDamageDelta += iHealRate;
					iSelfDamage -= iHealRate;

					result->eAssignmentType = A_HEAL;
				}
			}
			if (pUnit->IsEverFortifyable() && !pUnit->isEmbarked())
			{
				// This happens at the beginning of our next turn, so we can't assume enemy units will stick around, and we won't deal any damage this turn
				if (pUnit->GetDamageAoEFortified() > 0)
					iBonusScore += testPlot->getNumAdjacentEnemies(CvTacticalPlot::TD_BOTH) * pUnit->GetDamageAoEFortified() / 3;

				if (unit.eMoveStrategy == MS_FIRSTLINE)
					iPlotScore += 1;
			}
		}
		else
		{
			if (pUnit->getDamage() + unit.iSelfDamage > 0 && !pUnit->IsCannotHeal(/*bConsiderResourceShortage*/ true) && !pUnit->isEmbarked())
			{
				if (pUnit->isAlwaysHeal())
				{
					int iHealRate = pUnit->ActualHealRate(pTestPlot, false);
					if (iHealRate > pUnit->getDamage() + unit.iSelfDamage)
						iHealRate = pUnit->getDamage() + unit.iSelfDamage;

					iSelfDamage -= iHealRate;
				}
				else if (pUnit->GetFlatHealRate() > 0)
				{
					int iHealRate = pUnit->GetFlatHealRate();
					if (iHealRate > pUnit->getDamage() + unit.iSelfDamage)
						iHealRate = pUnit->getDamage() + unit.iSelfDamage;

					iSelfDamage -= iHealRate;
				}
			}
		}

		int iCitadelDamage = testPlot->GetAdjacentImprovementDamage();
		if (iCitadelDamage > 0)
		{
			int iDamageTaken = min(iCurrentHealth, iCitadelDamage);

			iDamageDelta -= iDamageTaken;
			iSelfDamage += iDamageTaken;
		}

		// unit giving extra strength to an adjacent city?
		if (pUnit->GetAdjacentCityDefenseMod() > 0 && pTestPlot->IsAdjacentCity(pUnit->getTeam()))
			iPlotScore++;
	}

	// aoe damage on move
	if (bMoving && pUnit->getAoEDamageOnMove() > 0)
		DamageAdjacentUnits(result->unitDamage, iDamageDelta, pTestPlot, pUnit->getAoEDamageOnMove(), assumedPosition);

	// assume difference in danger from AoE damage on move is negligible (it's definitely not worth the CPU time)
	MovementDestinationStackQuery destinationStack;
	int iDanger = GetUnitDangerForPlot(pUnit, pTestPlot, unit.iSelfDamage + iSelfDamage, assumedPosition, &destinationStack);

	//many considerations are only relevant if we end the turn here (critical for skirmishers which can move after attacking ...)
	//we only consider this when explicitly ending the turn!
	if (evalMode != EM_INTERMEDIATE)
	{
		result->eAssignmentType = evalMode == EM_FINAL ? A_FINISH : A_INITIAL;

		iDangerScore = ScoreCombatUnitTurnEnd(pUnit, unit.eLastAssignment, testPlot, iDanger,
			eRelevantDomain, unit.iSelfDamage + iSelfDamage, assumedPosition, evalMode, false, false);

		if (iDangerScore == INT_MAX)
		{
			if (gSafePlotCount[unit.iUnitID] > 0)
				return result; //don't do it

			//unit has no safe plots and must end turn somewhere (EM_FINAL)
			//clamp the sentinel to worst-possible arithmetic-safe value
			iDangerScore = SHRT_MIN;
		}
	}
	else
	{
		iDangerScore = -iDanger / 2;

		//scale it up a bit to reduce truncation error during division
		int iOverkillPercent = (100*iDanger) / max(1, iCurrentHealth);
		iDangerScore -= iOverkillPercent / 20;

		//there is a tendency for fast units to move too far ahead without a chance to withdraw later
		//so try to catch this case right here, cannot wait until the end of the sim when it's too late
		//if (iOverkillPercent > 300 && unit.iMovesLeft < 3 * GD_INT_GET(MOVE_DENOMINATOR) && unit.iMovesLeft > 3 * GD_INT_GET(MOVE_DENOMINATOR))
		//	return result; //don't do it

		//give a bonus for occupying a citadel even if it's just intermediate for now
		//but we want our units to take turns soaking damage, so we have to incentivise moving in.
		//bonus should be larger than 60 to override the difference between firstline/secondline base score.
		bool bIsFrontlineCitadelOrCity = (TacticalAIHelpers::IsPlayerCitadel(pTestPlot, assumedPosition.getPlayer()) || pTestPlot->isCity()) && pUnit->getDomainType() == DOMAIN_LAND && testPlot->getEnemyDistance() < 3;
		if (bIsFrontlineCitadelOrCity)
		{
			if (pUnit->GetRange()>1 || testPlot->getNumAdjacentFriendlies(CvTacticalPlot::TD_LAND, unit.iPlotIndex) == 0 || testPlot->getNumAdjacentEnemies(CvTacticalPlot::TD_LAND) > 0)
	 			iDangerScore += TACTICAL_COMBAT_CITADEL_BONUS;
			else
				iDangerScore += TACTICAL_COMBAT_CITADEL_BONUS/2;
		}
		else if (TacticalAIHelpers::GetOtherPlayerImprovementDamage(pTestPlot, assumedPosition.getPlayer(), true) >= 25)
		{
			if (unit.iMovesLeft > 0) //can pillage this turn
				iDangerScore += TACTICAL_COMBAT_CITADEL_BONUS*2;
			else
				iDangerScore += TACTICAL_COMBAT_CITADEL_BONUS;
		}
	}

	// Check if we are moving into an improvement that restores our moves
	if (bMoving && pTestPlot->getOwner() == pUnit->getOwner() && testPlot->getPlotIndex() != unit.iPlotIndex && pTestPlot->IsRestoreMoves())
	{
		if (evalMode == EM_INTERMEDIATE)
			iBonusScore += unit.iMaxMoves - unit.iMovesLeft;
		result->iRemainingMoves = pUnit->baseMoves(false);
	}

	//final score
	//danger values (typically negative!) are mostly useful as tiebreaker
	result->iSelfDamage = iSelfDamage;

	//small bias for staying close to our cities, to have a way to retreat if necessary
	int iCityDistanceScore = 10 - GET_PLAYER(assumedPosition.getPlayer()).GetCityDistanceInPlots(pTestPlot);
	int iExtra = max(iCityDistanceScore, 0);

	//often there are multiple identical units which could move into a plot (eg in naval battles)
	//in that case we want to prefer the one which has more movement points left to make the movement animation look better
	iExtra += result->iRemainingMoves / GD_INT_GET(MOVE_DENOMINATOR);

 if (StackPreferencesEnabled())
 {
  iDangerScore += ScoreStackPosition(pUnit, pTestPlot, unit.iSelfDamage + iSelfDamage, assumedPosition, &destinationStack);
  destinationStack.Release();
  if (bMoving && !pUnit->IsCanAttackRanged())
   iBonusScore += leavingProtection ? leavingProtection->Get(unit, assumedPosition) : CalculateLeavingStackProtectionScore(unit, assumedPosition);
 }
	result->SetScore(iPlotScore * 10 + iDangerScore + iExtra, iBonusScore, iDamageDelta);

	return result;
}

//stacking with combat units is allowed here!
static STacticalAssignment* ScorePlotForNonFightingUnitMove(const SUnitStats& unit, const CvTacticalPlot* testPlot, const CvTacticalPosition& assumedPosition, eUnitMoveEvalMode evalMode, PreviousPlotScoreQuery* previousScore = NULL)
{
	//default action is do nothing and invalid score (not -INT_MAX, to prevent overflows!)
	STacticalAssignment* result = gAssignmentStorage.peekNext();
	result->init(unit.iPlotIndex,testPlot->getPlotIndex(), unit.iUnitID, unit.iMovesLeft, unit.eMoveStrategy, A_MOVE, GetPrevPlotScore(unit.iUnitID, assumedPosition, previousScore));
	// Staying put is a terminal choice, just as for fighting units. An embarked
	// unit otherwise receives A_MOVE to its own plot with unchanged moves forever.
	if (unit.iPlotIndex == testPlot->getPlotIndex())
		result->eAssignmentType = A_FINISH_TEMP;
	if (evalMode == EM_INITIAL)
		result->eAssignmentType = A_INITIAL;
	else if (evalMode == EM_FINAL)
		result->eAssignmentType = A_FINISH;
	int iScore = 0;
		
	//the plot we're checking right now
	const CvPlot* pTestPlot = testPlot->getPlot();
	const CvUnit* pUnit = unit.pUnit;

	//cannot deal with enemies here, only friendly/empty plots
	if (testPlot->isEnemy())
		return result;

	if (evalMode == EM_FINAL && unit.eLastAssignment == A_USE_POWER)
	{
		result->SetScore(0, 0, 0);
		return result;
	}

	//check distance to target if gathering (not attacking)
	const CvTacticalPlot* targetPlot = assumedPosition.getTactPlot( assumedPosition.getTarget()->GetPlotIndex() );
	if (targetPlot && !targetPlot->isEnemy())
	{
		//can be treacherous with impassable terrain in between but everything else is much more complex
		int iPlotDistance = plotDistance(*assumedPosition.getTarget(),*pTestPlot);
		iScore += 3 - iPlotDistance;
	}

	//plain embarked units
	if (unit.eMoveStrategy == MS_EMBARKED)
	{
		//check distance to enemy in any case
		switch (testPlot->getEnemyDistance())
		{
		case 0:
			return result; //don't ever go there, wouldn't work anyway
			break;
		case 1:
			iScore = 2; //dangerous, only in emergencies
			break;
		default:
			iScore = 23; //embarked units don't care about getting close to enemies
			break;
		}

		if (evalMode!=EM_INTERMEDIATE)
		{
			//catch the case with infinite danger
			int iDanger = min(1000, pUnit->GetDanger(pTestPlot, assumedPosition.GetUnitDamageDealt(), 0));

			//embarked units have limited vision so be careful
			if (testPlot->isEdgePlot())
				iDanger += 50;

			iScore -= iDanger;
		}
	}

	//often there are multiple identical units which could move into a plot
	//in that case we want to prefer the one which has more movement points left
	int iExtra = result->iRemainingMoves / GD_INT_GET(MOVE_DENOMINATOR);

	//scale to be in range with actual fighting units
	result->SetScore(iScore * 10 + iExtra, 0, 0);

	return result;
}

static STacticalAssignment* ScorePlotForRangedAttack(const SUnitStats& unit, const CvTacticalPlot* assumedUnitPlot, const CvTacticalPlot* enemyPlot, const CvTacticalPosition& assumedPosition, PreviousPlotScoreQuery* previousScore = NULL)
{
	STacticalAssignment* result = gAssignmentStorage.peekNext();
	result->init(unit.iPlotIndex, enemyPlot->getPlotIndex(), unit.iUnitID, unit.iMovesLeft, unit.eMoveStrategy, A_RANGEATTACK, GetPrevPlotScore(unit.iUnitID, assumedPosition, previousScore));

	int iBonusScore = 0;

	//received damage is zero here but still use the correct unit number ratio so as not to distort scores
	ScoreAttackDamage(enemyPlot, unit.pUnit, assumedUnitPlot, assumedPosition, gTactPosStorage.getAttackCache(), result, unit.iSelfDamage);
	if (!result->IsAcceptable())
		return result;
	if(enemyPlot->isEnemyCity() && !CvStackingOffensiveAI::AllowCityAttack(unit.pUnit,
		enemyPlot->getPlot()->getPlotCity(),assumedUnitPlot->getPlot(),false))
	{ result->SetImpossible();return result; }

	//what happens next?
	if (AttackEndsTurn(unit.pUnit, unit.iAttacksLeft))
	{
		result->iRemainingMoves = 0;
	}
	else
	{
		if (!unit.pUnit->IsFreeAttackMoves())
			result->iRemainingMoves -= min((int)result->iRemainingMoves, GD_INT_GET(MOVE_DENOMINATOR));

		//a bonus the further we can disengage after attacking
		iBonusScore += (result->iRemainingMoves * 2) / GD_INT_GET(MOVE_DENOMINATOR);
	}

	//a slight boost for attacking the "real" target
	if ( enemyPlot->getPlotIndex()==assumedPosition.getTarget()->GetPlotIndex() )
		iBonusScore += 2;

	result->AddScore(0, iBonusScore, 0);

	return result;
}

static STacticalAssignment* ScorePlotForMeleeAttack(const SUnitStats& unit, const CvTacticalPlot* assumedUnitPlot, const CvTacticalPlot* enemyPlot, int iAssumedMovesLeft, const CvTacticalPosition& assumedPosition, PreviousPlotScoreQuery* previousScore = NULL)
{
	//default action is invalid
	STacticalAssignment* result = gAssignmentStorage.peekNext();
	result->init(unit.iPlotIndex, enemyPlot->getPlotIndex(), unit.iUnitID, 0, unit.eMoveStrategy, A_MELEEATTACK, GetPrevPlotScore(unit.iUnitID, assumedPosition, previousScore));

	int iBonusScore = 0;

	//the plot we're checking right now
	const CvPlot* pEnemyPlot = enemyPlot->getPlot();

	//sanity check
	if (!enemyPlot || !assumedUnitPlot)
		return result;

	//this is only for melee attacks - ranged attacks are handled separately
	const CvUnit* pUnit = unit.pUnit;
	if (!enemyPlot->isEnemy() || pUnit->IsCanAttackRanged())
		return result;

	//how often can we attack this turn (depending on moves left on the unit)
	int iMaxAttacks = NumAttacksForUnit(unit.iMovesLeft, unit.iAttacksLeft, pUnit->IsFreeAttackMoves());

	if (iMaxAttacks == 0)
		return result;

	//check how much damage we could do
	ScoreAttackDamage(enemyPlot, pUnit, assumedUnitPlot, assumedPosition, gTactPosStorage.getAttackCache(), result, unit.iSelfDamage);
	if (!result->IsAcceptable())
		return result;
	if(enemyPlot->isEnemyCity() && !CvStackingOffensiveAI::AllowCityAttack(pUnit,
		pEnemyPlot->getPlotCity(),assumedUnitPlot->getPlot(),result->eAssignmentType==A_MELEEKILL))
	{ result->SetImpossible();return result; }

	//what happens next? capturing a city always ends the turn
	if (AttackEndsTurn(pUnit, iMaxAttacks) ||
		CvUnitMovement::IsSlowedByZOC(pUnit,assumedUnitPlot->getPlot(),pEnemyPlot,assumedPosition.getFreedPlots()) ||
		(enemyPlot->isEnemyCity() && result->eAssignmentType == A_MELEEKILL))
		//end turn cost will be checked in time, no need to panic yet
		result->iRemainingMoves = 0;
	else
	{
		int iMoveCost = unit.iMovesLeft - iAssumedMovesLeft;
		int iAttackCost = pUnit->IsFreeAttackMoves() ? 0 : max(iMoveCost, GD_INT_GET(MOVE_DENOMINATOR));
		result->iRemainingMoves = max(0,unit.iMovesLeft - iAttackCost);
	}

	//don't break formation if there are many enemies around
	if (result->eAssignmentType == A_MELEEKILL && !enemyPlot->isEnemyCity() && enemyPlot->getNumAdjacentEnemies(DomainForUnit(pUnit)) > 3
		&& result->iRemainingMoves == 0)
	{
		result->SetImpossible();
		return result;
	}

	//a slight boost for attacking the "real" target or a citadel
	int iImprovementDamage = TacticalAIHelpers::GetOtherPlayerImprovementDamage(pEnemyPlot, assumedPosition.getPlayer(), true);
	if (pEnemyPlot == assumedPosition.getTarget())
		iBonusScore += 3;
	else if (iImprovementDamage > 0)
		iBonusScore += iImprovementDamage / 10;

	//combo bonus
	if (result->eAssignmentType == A_MELEEKILL && enemyPlot->isEnemyCivilian())
	{
		CvUnit* pCivilian;
		for (int iI = 0; iI < pEnemyPlot->getNumUnits(); iI++)
		{
			pCivilian = pEnemyPlot->getUnitByIndex(iI);
			if (pCivilian && pCivilian->IsCivilianUnit() && GET_PLAYER(pUnit->getOwner()).IsAtWarWith(pCivilian->getOwner()))
			{
				//workers are not so important ...
				iBonusScore += (pCivilian->AI_getUnitAIType() == UNITAI_WORKER) ? 20 : 150;
			}
		}
	}

	// barbarian camp
	if (result->eAssignmentType == A_MELEEKILL && pEnemyPlot->getRevealedImprovementType(pUnit->getTeam()) == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT))
		iBonusScore += 100;

	result->AddScore(0, iBonusScore, 0);

	return result;
}

static STacticalAssignment* ScorePlotForAdmiralHeal(const SUnitStats& unit, const CvTacticalPlot* assumedUnitPlot, int iAssumedMovesLeft, const CvTacticalPosition& assumedPosition, PreviousPlotScoreQuery* previousScore = NULL)
{
	STacticalAssignment* result = gAssignmentStorage.peekNext();
	result->init(unit.iPlotIndex, assumedUnitPlot->getPlotIndex(), unit.iUnitID, 0, unit.eMoveStrategy, A_USE_POWER, GetPrevPlotScore(unit.iUnitID, assumedPosition, previousScore));

	if (iAssumedMovesLeft == 0)
		return result;

	int iDamageDelta = 0;

	int iNearbyFriendly = assumedUnitPlot->getNumAdjacentFriendlies(CvTacticalPlot::TD_SEA, -1) + (assumedUnitPlot->hasFriendlyCombatUnit() ? 1 : 0);
	if (iNearbyFriendly >= 3)
	{
		vector<SUnitStats> units = assumedPosition.getAvailableUnits();
		units.insert(units.end(), assumedPosition.getFinishedUnits().begin(), assumedPosition.getFinishedUnits().end());
		for (vector<SUnitStats>::const_iterator it = units.begin(); it != units.end(); ++it)
		{
			const CvUnit* pLoopUnit = it->pUnit;
			if (!pLoopUnit->IsCombatUnit() || (pLoopUnit->getDomainType() != DOMAIN_SEA && it->eMoveStrategy != MS_EMBARKED) || pLoopUnit->IsCannotHeal(true))
				continue;

			if (plotDistance(it->iPlotIndex, assumedUnitPlot->getPlotIndex()) > 1)
				continue;

			const CvTacticalPlot* adjacentTactPlot = assumedPosition.getTactPlot(pLoopUnit->plot()->GetPlotIndex());
			if (!adjacentTactPlot)
				continue;

			HealUnitsInPlot(result->unitHealing, iDamageDelta, adjacentTactPlot, 1000, assumedPosition);
		}
	}

	result->SetScore(0, 0, iDamageDelta);

	return result;
}

// Empty copies own no control block and perform no reference-count atomics.
static const vector<const CvUnit*> gEmptyTacticalEnemyRoster;
const vector<const CvUnit*>& STacticalEnemyRoster::Empty()
{
 return gEmptyTacticalEnemyRoster;
}

CvTacticalPlot::CvTacticalPlot(const CvPlot* plot, PlayerTypes ePlayer, const vector<const CvUnit*>& allOurUnits) :
	pPlot(NULL), eSimPlayer(ePlayer), bEnemyCityPresent(false) //important, invalid by default
{
	if (!plot || ePlayer == NO_PLAYER)
		return;

	//minor players ignore barb camps and the units inside
	CvPlayerAI& kPlayer = GET_PLAYER(ePlayer);
	if (plot->getRevealedImprovementType(kPlayer.getTeam()) == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT) && kPlayer.isMinorCiv() && !kPlayer.isBarbarian())
		return;

	//the most important thing
	pPlot = plot;

	//constant
	bfBlockedByNonSimCombatUnit = 0;
	bHasAirCover = pPlot->HasAirCover(ePlayer);
	bIsVisibleToEnemy = pPlot->IsKnownVisibleToEnemy(kPlayer.GetID());

	//updated once at the beginning
	nVisiblePlotsNearEnemyRange2 = 0;
	nVisiblePlotsNearEnemyRange3 = 0;
	//maybe only plant citadels if we're not winning anyhow or if we have many generals? kPlayer.GetDiplomacyAI()->GetStateAllWars()
	bMightWantCitadel = kPlayer.IsNicePlotForCitadel(pPlot);

	//updated if necessary
	bEdgeOfTheKnownWorldUnknown = true;
	bEnemyCivilianPresent = false;
	bEdgeOfTheKnownWorld = false;
	nAdjacentEnemyImprovementDamage = 0;
	vEnemyUnits.clear();
	vFixedFriendlyUnits.clear();

	//set only once
	bFriendlyDefenderEndTurn = false;
	bSimUnitBlocking[TD_BOTH] = false;
	bSimUnitBlocking[TD_LAND] = false;
	bSimUnitBlocking[TD_SEA] = false;

	//set initial state, update after every move
	aiFriendlyCombatUnitsAdjacent[TD_BOTH] = 0;
	aiFriendlyCombatUnitsAdjacent[TD_LAND] = 0;
	aiFriendlyCombatUnitsAdjacent[TD_SEA] = 0;
	aiFriendlyCombatUnitsAdjacentEndTurn[TD_BOTH] = 0;
	aiFriendlyCombatUnitsAdjacentEndTurn[TD_LAND] = 0;
	aiFriendlyCombatUnitsAdjacentEndTurn[TD_SEA] = 0;

	aiEnemyDistance[TD_BOTH] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
	aiEnemyDistance[TD_LAND] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
	aiEnemyDistance[TD_SEA] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
	aiEnemyCombatUnitsAdjacent[TD_BOTH] = 0;
	aiEnemyCombatUnitsAdjacent[TD_LAND] = 0;
	aiEnemyCombatUnitsAdjacent[TD_SEA] = 0;
	aiRangedAttackEnemyDistance[TD_BOTH] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
	aiRangedAttackEnemyDistance[TD_LAND] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
	aiRangedAttackEnemyDistance[TD_SEA] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;

	// Keep all defenders. Attack-specific selection uses virtual HP later.
	//so here comes tricky logic to figure out whether we can use this plot
	for (int i = 0; i < pPlot->getNumUnits(); i++)
	{
		CvUnit* pPlotUnit = pPlot->getUnitByIndex(i);

		// Cargo uses its transport, never a combat stacking slot.
		if (!pPlotUnit || pPlotUnit->isDelayedDeath() || pPlotUnit->isCargo())
			continue;

		//enemies
		if (GET_PLAYER(ePlayer).IsAtWarWith(pPlotUnit->getOwner()))
		{
			//combat units (embarked or not)
			if (pPlotUnit->IsCanDefend() && !pPlotUnit->isCargo())
			{
				vEnemyUnits.push_back(pPlotUnit);
				//enemy distance for other plots will be set afterwards in refreshVolatilePlotProperties
				//but we need to set the zeros here!
				aiEnemyDistance[TD_BOTH] = 0;
				if (pPlotUnit->getDomainType() == DOMAIN_LAND)
					aiEnemyDistance[TD_LAND] = 0;
				else if (pPlotUnit->getDomainType() == DOMAIN_SEA)
					aiEnemyDistance[TD_SEA] = 0;
			}
			else
				//civilian
				bEnemyCivilianPresent = true;
		}
		//neutral units
		else if (ePlayer != pPlotUnit->getOwner())
		{
			//check if we can use the plot for combat units
			if (pPlotUnit->IsCanDefend() && (!CvStacking::IsEnabled() || !pPlotUnit->IsStackingUnit()))
			{
				if (pPlotUnit->getDomainType() == DOMAIN_LAND)
					bfBlockedByNonSimCombatUnit |= 1;
				else if (pPlotUnit->getDomainType() == DOMAIN_SEA)
					bfBlockedByNonSimCombatUnit |= 2;
			}

			//rules for cities are complex so just don't try it
			if (pPlot->isCity() && (!CvStacking::IsEnabled() || pPlot->getOwner() != ePlayer))
				bfBlockedByNonSimCombatUnit |= 3;
		}
		//owned units not included in sim
		else if (std::find(allOurUnits.begin(), allOurUnits.end(), pPlotUnit) == allOurUnits.end())
		{
			if (pPlotUnit->IsCanDefend())
			{
				vFixedFriendlyUnits.push_back(pPlotUnit);
				//mark as friendly
				bfBlockedByNonSimCombatUnit |= 4;

				if (!CvStacking::IsEnabled() && pPlotUnit->getDomainType() == DOMAIN_LAND)
					bfBlockedByNonSimCombatUnit |= 1;
				else if (!CvStacking::IsEnabled() && pPlotUnit->getDomainType() == DOMAIN_SEA)
					bfBlockedByNonSimCombatUnit |= 2;

				if (pPlotUnit->TurnProcessed())
				{
					//we need to update the adjacent friendly unit count for adjacent plots
					//but they are not guaranteed to exist at this point so we have to defer this
					bFriendlyDefenderEndTurn = true;
				}

				//rules for cities are complex so just don't try it
				//note that owned cities without a garrison are fine to use for tactsim
				if (!CvStacking::IsEnabled() && pPlot->isCity())
					bfBlockedByNonSimCombatUnit |= 3;
			}
		}
	}

	//important, not every enemy city has a garrison!
	if (pPlot->isCity() && GET_PLAYER(ePlayer).IsAtWarWith(pPlot->getOwner()))
	{
		bEnemyCityPresent = true;
		aiEnemyDistance[TD_BOTH] = 0;
		aiEnemyDistance[TD_LAND] = 0;
		aiEnemyDistance[TD_SEA] = 0;
	}
}

void CvTacticalPlot::resetVolatileProperties()
{
	bEdgeOfTheKnownWorld = false;
	nAdjacentEnemyImprovementDamage = 0;
	//set the distance to maximum but only if it's not a plot with an enemy
	if (aiEnemyDistance[TD_BOTH] != 0)
		aiEnemyDistance[TD_BOTH] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
	if (aiEnemyDistance[TD_LAND] != 0)
		aiEnemyDistance[TD_LAND] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
	if (aiEnemyDistance[TD_SEA] != 0)
		aiEnemyDistance[TD_SEA] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
	aiEnemyCombatUnitsAdjacent[TD_BOTH] = 0;
	aiEnemyCombatUnitsAdjacent[TD_LAND] = 0;
	aiEnemyCombatUnitsAdjacent[TD_SEA] = 0;
	aiRangedAttackEnemyDistance[TD_BOTH] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
	aiRangedAttackEnemyDistance[TD_LAND] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
	aiRangedAttackEnemyDistance[TD_SEA] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
}

int CvTacticalPlot::getFixedFriendlyCount(DomainTypes eDomain) const
{
 int count = 0;
 for (size_t i = 0; i < vFixedFriendlyUnits.size(); ++i)
  if (!vFixedFriendlyUnits[i]->isCargo() && !vFixedFriendlyUnits[i]->IsStackingUnit() && (eDomain == NO_DOMAIN || vFixedFriendlyUnits[i]->getDomainType() == eDomain))
   ++count;
 return count;
}

bool CvTacticalPlot::isBlockedByNonSimUnit(eTactPlotDomain eDomain, bool bMustBeFriendly) const
{
 if (CvStacking::IsEnabled() && pPlot)
 {
  const bool landFull = getFixedFriendlyCount(DOMAIN_LAND) >= CvStacking::GetCapacity(eSimPlayer, DOMAIN_LAND, pPlot->isCity());
  const bool seaFull = getFixedFriendlyCount(DOMAIN_SEA) >= CvStacking::GetCapacity(eSimPlayer, DOMAIN_SEA, pPlot->isCity());
  if ((eDomain == TD_BOTH && (landFull || seaFull)) || (eDomain == TD_LAND && landFull) || (eDomain == TD_SEA && seaFull))
   return true;
 }

	if (bMustBeFriendly && (bfBlockedByNonSimCombatUnit & 4) == 0)
		return false;

	if (eDomain == TD_BOTH)
		return (bfBlockedByNonSimCombatUnit & 3) != 0;
	else if (eDomain == TD_LAND)
		return (bfBlockedByNonSimCombatUnit & 1) != 0;
	else if (eDomain == TD_SEA)
		return (bfBlockedByNonSimCombatUnit & 2) != 0;

	return false;
}

bool CvTacticalPlot::hasFriendlyCombatUnit() const
{
	for (size_t i = 0; i < vUnitsHere.size(); i++)
		if (isCombatUnit(vUnitsHere[i].eMoveType))
			return true;
	
	return false;
}

bool CvTacticalPlot::hasFriendlyEmbarkedUnit() const
{
	for (size_t i = 0; i < vUnitsHere.size(); i++)
		if (isEmbarkedUnit(vUnitsHere[i].eMoveType))
			return true;

	return false;
}

void CvTacticalPlot::setCombatUnitEndTurn(CvTacticalPosition& currentPosition, eTactPlotDomain unitDomain, bool bOverride)
{
	//can't do anything before initialization is done
	if (!pPlot)
		return;
	
	//don't do this twice unless override
	if (bFriendlyDefenderEndTurn && !bOverride)
		return;

	bFriendlyDefenderEndTurn = true;

	CvPlot** aNeighbors = GC.getMap().getNeighborsUnchecked(pPlot);
	for (int i = 0; i < NUM_DIRECTION_TYPES; i++)
	{
		CvPlot* pNeighbor = aNeighbors[i];
		if (pNeighbor)
		{
			CvTacticalPlot* tactPlot = currentPosition.getTactPlotMutable(pNeighbor->GetPlotIndex());
			if (tactPlot)
			{
				tactPlot->aiFriendlyCombatUnitsAdjacentEndTurn[unitDomain]++;
				if (unitDomain != TD_BOTH)
					tactPlot->aiFriendlyCombatUnitsAdjacentEndTurn[TD_BOTH]++;

				if (tactPlot->aiFriendlyCombatUnitsAdjacentEndTurn[TD_LAND] > 6 || tactPlot->aiFriendlyCombatUnitsAdjacentEndTurn[TD_SEA] > 6)
					OutputDebugString("implausible amount of neighbors");
			}
		}
	}
}

bool CvTacticalPlot::hasCoverFromOtherUnits(const CvTacticalPosition& currentPosition) const
{
	//performance optimization
	if (getEnemyDistance() < 2)
		return false;
	if (getEnemyDistance() > 3)
		return true;

	eTactPlotDomain eDomain = getPlot()->isWater() ? TD_SEA : TD_LAND;
	int iMyEnemyDist = getEnemyDistance(eDomain);

	const vector<CvTacticalPlot>& plots = currentPosition.getTactPlots();
	for (int iI = 0; iI < (int)plots.size(); iI++)
	{
		if (plots[iI].getEnemyDistance(eDomain) < iMyEnemyDist && !plots[iI].isCombatEndTurn())
			if (plots[iI].getPlot()->isAdjacent(getPlot()))
				return false;
	}

	return true;
}

void CvTacticalPlot::changeNeighboringUnitCount(CvTacticalPosition& currentPosition, eUnitMovementStrategy moveType, eTactPlotDomain unitDomain, int iChange) const
{
	//we don't count embarked units
	if (!pPlot || isEmbarkedUnit(moveType))
		return;

	CvPlot** aNeighbors = GC.getMap().getNeighborsUnchecked(pPlot);
	for (int i = 0; i < NUM_DIRECTION_TYPES; i++)
	{
		CvPlot* pNeighbor = aNeighbors[i];
		if (pNeighbor)
		{
			CvTacticalPlot* tactPlot = currentPosition.getTactPlotMutable(pNeighbor->GetPlotIndex());
			if (tactPlot)
			{
				if (isCombatUnit(moveType)) //embarked is already handled
				{
					tactPlot->aiFriendlyCombatUnitsAdjacent[unitDomain] += iChange;
					if (unitDomain != TD_BOTH)
						tactPlot->aiFriendlyCombatUnitsAdjacent[TD_BOTH] += iChange;

					if (tactPlot->aiFriendlyCombatUnitsAdjacentEndTurn[TD_LAND] > 6 || tactPlot->aiFriendlyCombatUnitsAdjacentEndTurn[TD_SEA] > 6)
						OutputDebugString("implausible amount of neighbors");
				}
			}
		}
	}
}

void CvTacticalPlot::friendlyUnitMovingIn(CvTacticalPosition& currentPosition, const STacticalAssignment& assignment)
{
	// Casualties are removed explicitly before advancing; movement never deletes defenders.
	bEnemyCivilianPresent = false;

	CvUnit* pUnit = GET_PLAYER(currentPosition.getPlayer()).getUnit(assignment.iUnitID);
	CvTacticalPlot::eTactPlotDomain unitDomain = DomainForUnit(pUnit);

	vUnitsHere.push_back( STacticalUnit(assignment.iUnitID,assignment.eMoveType));
	changeNeighboringUnitCount(currentPosition, assignment.eMoveType, unitDomain, +1);
}

void CvTacticalPlot::friendlyUnitMovingOut(CvTacticalPosition& currentPosition, const STacticalAssignment& assignment)
{
	for (UnitList::iterator it = vUnitsHere.begin(); it != vUnitsHere.end(); it++)
	{
		if (assignment.iUnitID == it->iUnitID)
		{
			CvUnit* pUnit = GET_PLAYER(currentPosition.getPlayer()).getUnit(assignment.iUnitID);
			CvTacticalPlot::eTactPlotDomain unitDomain = DomainForUnit(pUnit);

			vUnitsHere.erase(it);
			changeNeighboringUnitCount(currentPosition, assignment.eMoveType, unitDomain, -1);
			return;
		}
	}

	OutputDebugString("invalid move\n");
}

int CvTacticalPlot::getNumAdjacentFriendlies(eTactPlotDomain eDomain, int iIgnoreUnitPlot) const 
{
	if (iIgnoreUnitPlot >= 0)
	{
		CvPlot* pIgnorePlot = GC.getMap().plotByIndexUnchecked(iIgnoreUnitPlot);
		if (pIgnorePlot->isAdjacent(pPlot))
			return aiFriendlyCombatUnitsAdjacent[eDomain] - 1;
	}

	return aiFriendlyCombatUnitsAdjacent[eDomain];
}

int CvTacticalPlot::getNumAdjacentFriendliesEndTurn(eTactPlotDomain eDomain) const 
{ 
	return aiFriendlyCombatUnitsAdjacentEndTurn[eDomain]; 
}

bool CvTacticalPlot::removeEnemyUnitIfPresent(int iUnitID)
{
 const vector<const CvUnit*>& enemies = vEnemyUnits.read();
 for (size_t index = 0; index < enemies.size(); ++index)
 {
  if (enemies[index]->GetID() != iUnitID)
   continue;
  // Search without detaching. Convert the matching iterator to an index before
  // write(), so no iterator/reference into shared storage survives its copy.
  vector<const CvUnit*>& remaining = vEnemyUnits.write();
  remaining.erase(remaining.begin() + index);
  aiEnemyDistance[TD_BOTH] = bEnemyCityPresent || !remaining.empty() ? 0 : TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
  aiEnemyDistance[TD_LAND] = aiEnemyDistance[TD_SEA] = bEnemyCityPresent ? 0 : TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
  for (size_t i = 0; i < remaining.size(); ++i)
   aiEnemyDistance[DomainForUnit(remaining[i])] = 0;
  // No reader in this method uses remaining after this last test. Drop the
  // final empty payload so later empty-plot copies have no refcount traffic.
  if (remaining.empty())
   vEnemyUnits.clear();
  return true;
 }
 return false;
}

void CvTacticalPlot::clearCapturedCity()
{
 vEnemyUnits.clear();
 bEnemyCityPresent = false;
 bEnemyCivilianPresent = false;
 aiEnemyDistance[TD_BOTH] = aiEnemyDistance[TD_LAND] = aiEnemyDistance[TD_SEA] = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
}

unsigned char CvTacticalPlot::getEnemyDistance(eTactPlotDomain eDomain) const
{
	return aiEnemyDistance[eDomain];
}

void CvTacticalPlot::setEnemyDistance(eTactPlotDomain eDomain, int iDistance)
{
	aiEnemyDistance[eDomain] = static_cast<unsigned char>(iDistance);
}

unsigned char CvTacticalPlot::getRangedAttackEnemyDistance(eTactPlotDomain eDomain) const
{
	return aiRangedAttackEnemyDistance[eDomain];
}

void CvTacticalPlot::setRangedAttackEnemyDistance(eTactPlotDomain eDomain, int iDistance)
{
	aiRangedAttackEnemyDistance[eDomain] = static_cast<unsigned char>(iDistance);
}

bool CvTacticalPlot::checkEdgePlotsForSurprises(const CvTacticalPosition& currentPosition, vector<int>& landEnemies, vector<int>& seaEnemies)
{
	//we only ever add plots, so if it's not a new plot and not an edge plot, nothing to do
	if (!bEdgeOfTheKnownWorld && !bEdgeOfTheKnownWorldUnknown)
		return false;

	//performance optimization ... only look at outward neighbors!
	CvPlot* pTarget = currentPosition.getTarget();
	int iRefDistance = plotDistance(pPlot->getX(), pPlot->getY(), pTarget->getX(), pTarget->getY());

	CvPlot** aNeighbors = GC.getMap().getNeighborsUnchecked(pPlot);
	for (int i = 0; i < NUM_DIRECTION_TYPES; i++)
	{
		CvPlot* pNeighbor = aNeighbors[i];
		if (!pNeighbor)
			continue;

		int iNeighborDistance = plotDistance(pNeighbor->getX(), pNeighbor->getY(), pTarget->getX(), pTarget->getY());
		if (iNeighborDistance < iRefDistance)
			continue;

		//minor players ignore barb camps and the units inside
		CvPlayer& kPlayer = GET_PLAYER(currentPosition.getPlayer());
		if (pNeighbor->getRevealedImprovementType(kPlayer.getTeam()) == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT) && kPlayer.isMinorCiv() && !kPlayer.isBarbarian())
			continue;

		const CvTacticalPlot* tactPlot = currentPosition.getTactPlot(pNeighbor->GetPlotIndex());
		//if the tactical plot is invalid, it's out of range or invisible on the main map.
		//these are the ones we need to check here
		if (!tactPlot)
		{
			//don't ignore enemy cities, we know they exist even if invisible
			if (pNeighbor->isCity() && GET_PLAYER(currentPosition.getPlayer()).IsAtWarWith(pNeighbor->getOwner()))
			{
				//poor man's deduplication
				if (landEnemies.empty() || landEnemies.back()!=pNeighbor->GetPlotIndex())
					landEnemies.push_back(pNeighbor->GetPlotIndex());
			}
			else if (pNeighbor->isVisible(GET_PLAYER(currentPosition.getPlayer()).getTeam()))
			{
				CvUnit* pEnemy = pNeighbor->getBestDefender(NO_PLAYER, currentPosition.getPlayer(), NULL, true);
				if (pEnemy)
				{
					if (pEnemy->getDomainType() == DOMAIN_LAND)
					{
						//poor man's deduplication
						if (landEnemies.empty() || landEnemies.back()!=pNeighbor->GetPlotIndex())
							landEnemies.push_back(pNeighbor->GetPlotIndex());
					}
					else if (pEnemy->getDomainType() == DOMAIN_SEA)
					{
						//poor man's deduplication
						if (seaEnemies.empty() || seaEnemies.back()!=pNeighbor->GetPlotIndex())
							seaEnemies.push_back(pNeighbor->GetPlotIndex());
					}
				}
			}
			else
				//if the neighbor is invisible but passable be careful as well, enemies might be hiding there
				bEdgeOfTheKnownWorld |= !pNeighbor->isImpassable();

			int iImprovementDamage = TacticalAIHelpers::GetOtherPlayerImprovementDamage(pNeighbor, currentPosition.getPlayer(), true);
			if (iImprovementDamage > 0)
				nAdjacentEnemyImprovementDamage = max((int)nAdjacentEnemyImprovementDamage, iImprovementDamage);
		}

	}

	bEdgeOfTheKnownWorldUnknown = false;
	return bEdgeOfTheKnownWorld;
}

const vector<int>& CvTacticalPosition::getRangeAttackPlotsForUnit(const SUnitStats& unit) const
{
	static vector<int> emptyResult;

	TCachedRangeAttackPlots::const_iterator result = gRangeAttackPlotsLookup.find( make_pair(unit.iUnitID,unit.iPlotIndex) );
	if (result != gRangeAttackPlotsLookup.end())
		return result->second;

	return emptyResult;
}

bool IsCombatUnit(const SUnitStats& unit)
{
	switch (unit.eMoveStrategy)
	{
	case MS_FIRSTLINE:
	case MS_SECONDLINE:
	case MS_THIRDLINE:
		return true;
		break;
	default:
		return false;
	}
}

static STacticalAssignment* ScorePlotForMove(const SUnitStats& unit, const CvTacticalPlot* testPlot, const CvTacticalPosition& assumedPosition, eUnitMoveEvalMode evalMode, LeavingStackProtectionMemo* leavingProtection = NULL, PreviousPlotScoreQuery* previousScore = NULL)
{
	if (IsCombatUnit(unit))
		return ScorePlotForCombatUnitMove(unit, testPlot, assumedPosition, evalMode, leavingProtection, previousScore);
	else
		return ScorePlotForNonFightingUnitMove(unit, testPlot, assumedPosition, evalMode, previousScore);
}

void CvTacticalPosition::getPreferredAssignmentsForUnit(const SUnitStats& unit, int nMaxCount) const
{
 CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_PREFERRED_ASSIGNMENTS); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
	//the challenge is that often a move can be good or bad depending on what our *other* units end up doing. so there are two strategies:
	//a) return as many moves as possible and check validity at the end.
	//b) return only "safe" moves in the sense that we dare to actually do them.
	//problem eg are generals, we want to move them close to the action but there might not be cover there or the cover might move away.
	//anyway experience shows if we choose an attractive but invalid move at the beginning of the sim this can poison everything
	//because so many positions can be generated from that we never get to examine at alternative beginnings in depth.
	//so we go with option B, even if it means we need to skip some daring moves.
	//on the other hand, the daring moves may still be possible later in the sim when they are not so daring anymore.
	//todo: try "fixup moves", meaning if a possible move is invalid, see if it can be made valid by moving another unit.
	gPossibleMoves.clear();
	gPossibleRangedAttacks.clear();

	const CvTacticalPlot* assumedUnitPlot = getTactPlot(unit.iPlotIndex);
	CvUnit* pUnit = GET_PLAYER(getPlayer()).getUnit(unit.iUnitID);
	if (!pUnit || !assumedUnitPlot)
		return;

	StackImmutableEnemyDamageScope immutableEnemyDamage(GetUnitDamageDealt());

	PreviousPlotScoreQuery previousScore(unit.iUnitID, *this);
	CvTacticalPosition tempPosition;
	int iOldPlotDistanceToTarget = bTargetDistanceRelevant ? TacticalAIHelpers::GetPlotDistanceToTarget(unit.iPlotIndex, pUnit->getDomainType()) : 0;
	if (iOldPlotDistanceToTarget < TACTICAL_COMBAT_MAX_TARGET_DISTANCE)
		iOldPlotDistanceToTarget = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;

	//check moves and melee attacks first
	const ReachablePlots& reachablePlots = getReachablePlotsForUnit(unit);
	LeavingStackProtectionMemo leavingProtection;
	for (ReachablePlots::const_iterator it = reachablePlots.begin(); it != reachablePlots.end(); ++it)
	{
		//the plot we're checking right now
		const CvTacticalPlot* testPlot = getTactPlot(it->iPlotIndex);
		if (!testPlot)
			continue;

		//if there is an enemy in the plot, we want to attack
		if (testPlot->isEnemy())
		{
			//ranged attacks are handled separately below
			if (pUnit->IsCanAttackRanged() || !IsCombatUnit(unit))
				continue;

			//for a melee attack we need to move to a defined adjacent plot first
			if (!assumedUnitPlot->getPlot()->isAdjacent(testPlot->getPlot()))
				continue;

			//does the attack make sense
			STacticalAssignment* attack = ScorePlotForMeleeAttack(unit,assumedUnitPlot,testPlot,it->iMovesLeft,*this, &previousScore);
			if (!attack->IsAcceptable())
				continue;

			GetNextPosition(*this, attack, tempPosition);
			SUnitStats tempUnit = GetNextUnit(unit, attack);

			//where would we end the turn? ie are we advancing or not
			const CvTacticalPlot* newPlot = (attack->eAssignmentType == A_MELEEKILL) ? testPlot : assumedUnitPlot;
			if (attack->iRemainingMoves == 0 && !tempPosition.canProbablyEndTurnAfterAssignment(tempUnit, newPlot, attack->eAssignmentType))
				continue;

			gAssignmentStorage.consumeOne();

			//also consider which plot we end up in
			STacticalAssignment* moveToPlot = ScorePlotForMove(tempUnit, newPlot, tempPosition, EM_INTERMEDIATE, NULL, &previousScore);
			attack->AddScore(moveToPlot);

			gPossibleMoves.push_back(OptionWithScore<STacticalAssignment*>(attack, attack->Score()));
			//done with this plot
			continue;
		}

		//already there?
		if (unit.iPlotIndex == it->iPlotIndex)
		{
			//try pillaging as an intermediate step
			STacticalAssignment* pillaging = ScorePlotForPillageMove(unit, testPlot, it->iMovesLeft, *this, &previousScore);
			if (pillaging->Score() > 0 && pillaging->IsAcceptable())
			{
				GetNextPosition(*this, pillaging, tempPosition);
				SUnitStats tempUnit = GetNextUnit(unit, pillaging);
				
				if (pillaging->iRemainingMoves > 0 || tempPosition.canProbablyEndTurnAfterAssignment(tempUnit, testPlot, pillaging->eAssignmentType))
				{
					gAssignmentStorage.consumeOne();
					STacticalAssignment* stayAfterPillage = ScorePlotForMove(tempUnit, testPlot, tempPosition, EM_INTERMEDIATE, NULL, &previousScore);

					pillaging->AddScore(stayAfterPillage);
					//continue with the same plot, maybe in the final analysis we will skip the pillage because we need the movement points
					gPossibleMoves.push_back(OptionWithScore<STacticalAssignment*>(pillaging, pillaging->Score()));
				}
			}

			//try ranged attacks
			if (pUnit->IsCanAttackRanged() && unit.iAttacksLeft > 0 && unit.iMovesLeft > 0)
			{
				const vector<int>& rangeAttackPlots = getRangeAttackPlotsForUnit(unit);
				for (vector<int>::const_iterator it = rangeAttackPlots.begin(); it != rangeAttackPlots.end(); ++it)
				{
					//the plot we're checking right now
					const CvTacticalPlot* enemyPlot = getTactPlot(*it);

					//note: all valid plots are visible by definition
					if (enemyPlot && enemyPlot->isEnemy())
					{
						STacticalAssignment* rangedAttack = ScorePlotForRangedAttack(unit, assumedUnitPlot, enemyPlot, *this, &previousScore);
						if (rangedAttack->Score() <= 0 || !rangedAttack->IsAcceptable())
							continue;

						GetNextPosition(*this, rangedAttack, tempPosition);
						SUnitStats tempUnit = GetNextUnit(unit, rangedAttack);

						//this is a catch-22: we really want to allow dangerous attacks because we might be able to kill the enemy unit making it safe.
						//experience shows this leads to a lot of "impossible" positions which have to be discarded later, killing performance.
						//but canProbablyEndTurnAfterThisAssignment() will consider near-kills for danger estimation!
						if (rangedAttack->iRemainingMoves == 0 && !tempPosition.canProbablyEndTurnAfterAssignment(tempUnit, testPlot, rangedAttack->eAssignmentType))
							continue;

						//discourage attacks on cities with non-siege units if the real target is something else
						if (enemyPlot->isEnemyCity() && getTarget() != enemyPlot->getPlot() && pUnit->GetRange() > 1 && pUnit->AI_getUnitAIType() != UNITAI_CITY_BOMBARD)
						{
							rangedAttack->SetScore(0, rangedAttack->GetBonusScore() / 2, rangedAttack->GetDamageDelta() / 2);
						}

						gAssignmentStorage.consumeOne();
						STacticalAssignment* stayAfterAttack = ScorePlotForMove(tempUnit, testPlot, tempPosition, EM_INTERMEDIATE, NULL, &previousScore);

						rangedAttack->AddScore(stayAfterAttack);
						gPossibleRangedAttacks.push_back(OptionWithScore<STacticalAssignment*>(rangedAttack, rangedAttack->Score()));
					}
				}
			}

			// Check if we should perform a admiral heal bomb
			if (pUnit->IsGreatAdmiral() && pUnit->canRepairFleet(testPlot->getPlot()))
			{
				STacticalAssignment* repairFleet = ScorePlotForAdmiralHeal(unit, testPlot, it->iMovesLeft, *this, &previousScore);
				if (repairFleet->Score() >= 2000)
				{
					gPossibleMoves.push_back(OptionWithScore<STacticalAssignment*>(repairFleet, repairFleet->Score()));
					gAssignmentStorage.consumeOne();
				}
			}

			if (gPossibleRangedAttacks.empty())
			{
				//what is the score for simply staying put and not attacking anybody?
				//use EM_INTERMEDIATE so we're less strict concerning danger, enemies might be killed in the course of the sim
				STacticalAssignment* moveToPlot = ScorePlotForMove(unit, testPlot, *this, EM_INTERMEDIATE, NULL, &previousScore);

				GetNextPosition(*this, moveToPlot, tempPosition);
				SUnitStats tempUnit = GetNextUnit(unit, moveToPlot);

				//also try just staying in place
				//doesn't matter if we have movement left in this case
				if (tempPosition.canProbablyEndTurnAfterAssignment(tempUnit, testPlot, moveToPlot->eAssignmentType))
				{
					gPossibleMoves.push_back(OptionWithScore<STacticalAssignment*>(moveToPlot, moveToPlot->Score()));
					gAssignmentStorage.consumeOne();
				}
			}
		}
		else //moving to a different plot
		{
			if (unit.eLastAssignment == A_MOVE)
				continue;

			//make sure we have a chance to execute this move ... so skip it if there is an unmoveable block
			if (IsCombatUnit(unit) && testPlot->IsSimUnitBlocking(DomainForUnit(pUnit)) && !CvStacking::IsEnabled())
				continue;

			bool bPreviousWasMove = unit.eLastAssignment == A_MOVE_SWAP || unit.eLastAssignment == A_MOVE_SWAP_REVERSE;

			// Only combat units may ever do two moves in a row
			if (bPreviousWasMove && !IsCombatUnit(unit))
				continue;

			int iMoveTowardsTargetScore = 0;

			if (bTargetDistanceRelevant)
			{
				// Try to move towards the target
				int iNewPlotDistanceToTarget = TacticalAIHelpers::GetPlotDistanceToTarget(it->iPlotIndex, pUnit->getDomainType());
				if (iNewPlotDistanceToTarget < TACTICAL_COMBAT_MAX_TARGET_DISTANCE)
					iNewPlotDistanceToTarget = TACTICAL_COMBAT_MAX_TARGET_DISTANCE;
				if (iNewPlotDistanceToTarget > iOldPlotDistanceToTarget)
					continue;
				if (iOldPlotDistanceToTarget != INT_MAX)
					iMoveTowardsTargetScore = (iOldPlotDistanceToTarget - iNewPlotDistanceToTarget) * 40;
			}
			SUnitStats tempUnit = unit;
			tempUnit.iMovesLeft = it->iMovesLeft;

			STacticalAssignment* moveToPlot = ScorePlotForMove(tempUnit, testPlot, *this, EM_INTERMEDIATE, &leavingProtection, &previousScore);
			tempUnit = GetNextUnit(tempUnit, moveToPlot);

			//if the last assignment was a move, we should only do another move if another unit wants to swap us out
			//note: if a move increases tile visibility we change it to MOVE_FORCED so we can move again!
			if (bPreviousWasMove)
				moveToPlot->eAssignmentType = A_MOVE_DOUBLE;

			bool bRanged = pUnit->IsCanAttackRanged();

			//may not be able to end the turn ... 
			bool bMoveInForSkirmish = bRanged && unit.iAttacksLeft > 0 && moveToPlot->iRemainingMoves > (!pUnit->IsFreeAttackMoves() ? GC.getMOVE_DENOMINATOR() : 0) && pUnit->canMoveAfterAttacking();
			bool bMoveInForFrontlineUnit = !bRanged && moveToPlot->iRemainingMoves > 0 && unit.iAttacksLeft > 0 && testPlot->getEnemyDistance() == 1; // need to move here in order to check possible attacks
			bool bCanStay = false;

			if (!bMoveInForSkirmish && !bMoveInForFrontlineUnit)
				bCanStay = canProbablyEndTurnAfterAssignment(tempUnit, testPlot, moveToPlot->eAssignmentType);

			if (bMoveInForSkirmish || bMoveInForFrontlineUnit || bCanStay)
			{
				moveToPlot->AddScore(iMoveTowardsTargetScore, 0, 0);

				gPossibleMoves.push_back(OptionWithScore<STacticalAssignment*>(moveToPlot, moveToPlot->Score()));
				gAssignmentStorage.consumeOne();
			}
		}
	}

	//it can happen that there are a lot of targets to attack - typically this means we should retreat!
	//so make sure we consider at least one MOVE and not only RANGE_ATTACK assignments
	//but keep at least one ranged attack!
	if (gPossibleRangedAttacks.size() >= (size_t)nMaxCount && nMaxCount>1)
	{
		std::stable_sort(gPossibleRangedAttacks.begin(), gPossibleRangedAttacks.end());
		gPossibleRangedAttacks.erase(gPossibleRangedAttacks.begin() + nMaxCount - 1, gPossibleRangedAttacks.end());
	}

	//only now add the ranged attacks
	gPossibleMoves.insert(gPossibleMoves.end(), gPossibleRangedAttacks.begin(), gPossibleRangedAttacks.end());

	//need to return in sorted order. note that we don't filter out bad (negative moves) they just are unlikely to get picked
	std::stable_sort(gPossibleMoves.begin(),gPossibleMoves.end());

	//don't return more than requested unless there is a tie
	if (gPossibleMoves.size() > (size_t)nMaxCount)
	{
		while ((size_t)nMaxCount < gPossibleMoves.size() && gPossibleMoves[nMaxCount].score == gPossibleMoves[nMaxCount - 1].score)
			nMaxCount++;

		gPossibleMoves.erase(gPossibleMoves.begin() + nMaxCount, gPossibleMoves.end());
	}

	//always add a 'do-nothing' move; this does not guarantee that it will get picked but it allows move-attack-flee for damaged units
	//order does not matter, the parent function will sort again ... BLOCKED should be strictly worse than FINISH_TEMP
	//would be nice to have a way to make sure the "important" blocks (no other options) are picked over unimportant blocks (many other options)
	//but we should not give a bonus score for wasting movement points to paint ourselves into a corner!
	//also cannot check for the existamce of good moves here because we don't know yet if we can actually execute the good-looking moves
	//could also sort the moves by a secondary criterion, but best solution seems to be the "bad unit' mechanism to restart the sim
	STacticalAssignment* blocked = gAssignmentStorage.peekNext();
	blocked->init(unit.iPlotIndex, unit.iPlotIndex, unit.iUnitID, unit.iMovesLeft, unit.eMoveStrategy, A_BLOCKED, GetPrevPlotScore(unit.iUnitID, *this, &previousScore));
	blocked->SetScore(-10, 0, 0);
	gPossibleMoves.push_back(OptionWithScore<STacticalAssignment*>(blocked, blocked->Score()));
	gAssignmentStorage.consumeOne();
}

//if we have many units we won't look at all of them (for performance reasons)
//obviously needs plot types to be defined
void CvTacticalPosition::dropSuperfluousUnits(int iMaxUnitsToKeep)
{
	//if we have weak units without a clear purpose we drop them
	int iNumAvailableUnits = GetNumAvailableUnits();
	if (iMaxUnitsToKeep > iNumAvailableUnits)
		iMaxUnitsToKeep = iNumAvailableUnits;

	//temporarily raise aggression level to make sure we consider all possible melee attacks (even those which only make sense after other attacks)
	eAggressionLevel actualLevel = getAggressionLevel();

	//very important before calling getPreferredAssignmentsForUnit()
	updateMovePlotsIfRequired();

	vector<SUnitStats>& availableUnits_w = availableUnits.write();

	//get the best move for each unit
	for (size_t i = 0; i < availableUnits_w.size() && iMaxUnitsToKeep>0; i++)
	{
		//this always returns at least one move
		getPreferredAssignmentsForUnit(availableUnits_w[i], 1);
		availableUnits_w[i].iImportanceScore = gPossibleMoves.front().score;
  if (StackPreferencesEnabled())
  {
   const CvUnit* unit = availableUnits_w[i].pUnit;
   for (size_t j = 0; j < availableUnits_w.size(); ++j)
   {
    const CvUnit* other = availableUnits_w[j].pUnit;
    if (i != j && unit->getDomainType() == other->getDomainType() && unit->IsCanAttackRanged() != other->IsCanAttackRanged()
     && plotDistance(*unit->plot(), *other->plot()) <= CvStacking::GetInt("AIStackPairRecruitRange", 1))
    {
     availableUnits_w[i].iImportanceScore += CvStacking::GetInt("AIStackPairRecruitBonus", 25);
     break;
    }
   }
  }

		gAssignmentStorage.reset(false);
	}

	//reset aggression to the original value
	eAggression = actualLevel;

	std::stable_sort(availableUnits_w.begin(), availableUnits_w.end());

 if (StackPreferencesEnabled() && (int)availableUnits_w.size() > iMaxUnitsToKeep)
 {
  vector<SUnitStats> ordered;
  set<int> chosen;
  for (size_t i = 0; i < availableUnits_w.size() && (int)ordered.size() < iMaxUnitsToKeep; ++i)
  {
   const SUnitStats& candidate = availableUnits_w[i];
   if (chosen.count(candidate.iUnitID))
    continue;
   ordered.push_back(candidate);
   chosen.insert(candidate.iUnitID);
   if (!candidate.pUnit->IsCanAttackRanged() || (int)ordered.size() >= iMaxUnitsToKeep)
    continue;
   // Preserve a nearby protective partner before filling remaining slots.
   for (size_t j = 0; j < availableUnits_w.size(); ++j)
   {
    const SUnitStats& partner = availableUnits_w[j];
    if (!chosen.count(partner.iUnitID) && !partner.pUnit->IsCanAttackRanged() && candidate.pUnit->getDomainType() == partner.pUnit->getDomainType()
     && plotDistance(candidate.iPlotIndex, partner.iPlotIndex) <= CvStacking::GetInt("AIStackPairRecruitRange", 1))
    { ordered.push_back(partner); chosen.insert(partner.iUnitID); break; }
   }
  }
  for (size_t i = 0; i < availableUnits_w.size(); ++i)
   if (!chosen.count(availableUnits_w[i].iUnitID))
    ordered.push_back(availableUnits_w[i]);
  availableUnits_w.swap(ordered);
 }

	//simply consider those extra units as blocked.
	//since addAssignment will modify availableUnits, we copy the relevant units first
	vector<SUnitStats> unitsToDrop(availableUnits_w.begin()+iMaxUnitsToKeep, availableUnits_w.end() );
	if (!unitsToDrop.empty())
	{
		vector<STacticalAssignment>& assignedMoves_w = assignedMoves.write();
		for (vector<SUnitStats>::const_iterator itUnit = unitsToDrop.begin(); itUnit != unitsToDrop.end(); ++itUnit)
		{
			vector<SUnitStats>::iterator toDrop = find_if(availableUnits_w.begin(), availableUnits_w.end(), PrMatchingUnit(itUnit->iUnitID));
			availableUnits_w.erase(toDrop);
			finishedUnits.write().push_back(*itUnit);
			CvStackingDiagnostics::Record(2, getPlayer(), "RECRUIT_DROP", "target=%d:%d unit=%d reason=search_budget importance=%d cap=%d",
				getTarget()->getX(), getTarget()->getY(), itUnit->iUnitID, itUnit->iImportanceScore, iMaxUnitsToKeep);
			STacticalAssignment blocked;
			blocked.init(itUnit->iPlotIndex, itUnit->iPlotIndex, itUnit->iUnitID, itUnit->iMovesLeft, itUnit->eMoveStrategy, A_BLOCKED, GetPrevPlotScore(itUnit->iUnitID, *this));
			blocked.SetScore(0, 0, 0);
			assignedMoves_w.push_back(blocked);
		}
	}
}

void CvTacticalPosition::addInitialAssignments()
{
	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	//first pass. problem is scores might be off because officially we don't know where our units are yet
	for (vector<SUnitStats>::const_iterator itUnit = availableUnits_r.begin(); itUnit != availableUnits_r.end(); ++itUnit)
	{
		const CvTacticalPlot* tactPlot = getTactPlot(itUnit->iPlotIndex);
		if (tactPlot) //failsafe
		{
			SUnitStats tmp = *itUnit;
			tmp.iMovesLeft = 0;
			//we pretend the unit has zero moves, this means we do not score any possible attacks
			//this is important for symmetry with canStayInPlot()
			STacticalAssignment eInitialAssignmentNoMoves = *ScorePlotForMove(tmp, tactPlot, *this, EM_INITIAL);
			eInitialAssignmentNoMoves.iRemainingMoves = itUnit->iMovesLeft;
			eInitialAssignmentNoMoves.eAssignmentType = A_INITIAL;
			addAssignment(eInitialAssignmentNoMoves);
		}
	}

	//second pass. fix up the scores with correct number of adjacent units
	for (vector<SUnitStats>::const_iterator itUnit = availableUnits_r.begin(); itUnit != availableUnits_r.end(); ++itUnit)
	{
		const CvTacticalPlot* tactPlot = getTactPlot(itUnit->iPlotIndex);
		if (tactPlot) //failsafe
		{
			SUnitStats tmp = *itUnit;
			tmp.iMovesLeft = 0;
			STacticalAssignment eInitialAssignmentNoMoves = *ScorePlotForMove(tmp, tactPlot, *this, EM_INITIAL);
			STacticalAssignment* pInitial = getInitialAssignmentMutable(itUnit->iUnitID);
			if (pInitial)
			{
				pInitial->SetScore(&eInitialAssignmentNoMoves);
			}
		}
	}
}

//finding a particular unit
struct PrIsMoveForUnit
{
	int iUnitID;
	PrIsMoveForUnit(int iID) : iUnitID(iID) {}
	bool operator()(const STacticalAssignment& other) { return iUnitID == other.iUnitID; }
};

bool CvTacticalPosition::makeNextAssignments(int iMaxBranches, int iMaxChoicesPerUnit, CvTactPosStorage& storage,
	vector<CvTacticalPosition*>& openPositionsHeap, vector<CvTacticalPosition*>& completedPositions, const PrPositionSortHeapGeneration& heapSort,
	const vector<const CvUnit*>& ourUnits)
{
 CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_NEXT_ASSIGNMENTS); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
	/*
	abstract:
	get preferred plots for all combat units
	choose M best overall moves (combine as far as possible)
	create child positions
		assign moves
		update affected tact plots
		update unit reachable plots
	*/

	//very important, lazy update
	updateMovePlotsIfRequired();

	gMovesToAdd.clear();
	gOverAllChoices.clear();
	gAssignmentStorage.reset(false);
	const vector<SUnitStats>& availableUnits_r = availableUnits.read();

	{
	 ParentStackPreparationView preparation(*this);
	for (size_t i=0; i< availableUnits_r.size(); i++)
	{
		getPreferredAssignmentsForUnit(availableUnits_r[i], iMaxChoicesPerUnit);
		gOverAllChoices.insert( gOverAllChoices.end(), gPossibleMoves.begin(), gPossibleMoves.end() );
	}
	}

	//important that moves are ordered by quality instead of unit id
	std::stable_sort(gOverAllChoices.begin(), gOverAllChoices.end());

	//sometimes we want to do combo moves, ie swaps should have the combined score of two moves
	//be generous when checking the candidates, so 5x the number of children we want in the end
	const size_t iMaxCandidates = max(iMaxBranches * 5u, gOverAllChoices.size() / 2);
	const size_t nChoices = gOverAllChoices.size();

	for (size_t iI = 0; iI < min(nChoices, iMaxCandidates); iI++)
	{
		const STacticalAssignment& assignment = *gOverAllChoices[iI].option;

		if (assignment.eAssignmentType == A_MOVE_DOUBLE)
			continue;

		if (assignment.eAssignmentType != A_MOVE)
		{
			gMovesToAdd.push_back(SComboMove());
			SComboMove& move = gMovesToAdd.back();
			move.addMove(assignment);

			// Bundle a following block/finish move to reduce search depth
			if (heapSort.bDepthFirst && iI + 1 < nChoices)
			{
				eUnitAssignmentType nextType = gOverAllChoices[iI + 1].option->eAssignmentType;
				if (nextType == A_FINISH_TEMP || nextType == A_BLOCKED || nextType == A_HEAL)
					if (move.addMove(*gOverAllChoices[iI + 1].option))
						iI++;
			}
			continue;
		}

		DomainTypes eDomain = GET_PLAYER(ePlayer).getUnit(assignment.iUnitID)->getDomainType();
		if (eDomain != DOMAIN_SEA)
			eDomain = DOMAIN_LAND;

		// A_MOVE: target plot may still be occupied
		int blocks = countBlockingUnitsAtPlot(assignment.iToPlotIndex, assignment.eMoveType, eDomain);

		if (blocks == 0)
		{ 
			gMovesToAdd.push_back(SComboMove()); gMovesToAdd.back().addMove(assignment);
			continue;
		}
		if (blocks > 1)
		{
			continue;
		}

		// blocks == 1: find best non-blocked move for the blocking unit
		int iBlockID = getFirstBlockingUnitIDAtPlot(assignment.iToPlotIndex, assignment.eMoveType, eDomain);

		for (size_t iJ = 0; iJ < nChoices; iJ++)
		{
			const STacticalAssignment& other = *gOverAllChoices[iJ].option;

			if (other.eAssignmentType != A_MOVE && other.eAssignmentType != A_MOVE_DOUBLE)
				continue;
			if (other.iUnitID != iBlockID)
			{
				// A full stack needs one slot, not one specific occupant. Keep the
				// existing sorted-choice and one-combo budget, but try other legal exits.
				const SUnitStats* alternative = getAvailableUnitStats(other.iUnitID);
				if (!CvStacking::IsEnabled() || !(isCombatUnit(assignment.eMoveType) || isEmbarkedUnit(assignment.eMoveType)) ||
					!alternative || alternative->iMovesLeft <= 0 || alternative->iPlotIndex != assignment.iToPlotIndex ||
					other.iFromPlotIndex != assignment.iToPlotIndex || other.iFromPlotIndex == other.iToPlotIndex ||
					!alternative->pUnit->IsCombatUnit() || alternative->pUnit->IsStackingUnit() || alternative->pUnit->isCargo() ||
					alternative->pUnit->getDomainType() != eDomain)
					continue;
			}

			// Swap: blocker wants to move into our current plot
			if (other.iUnitID == iBlockID && (iI < iJ || other.eAssignmentType == A_MOVE_DOUBLE) && assignment.iFromPlotIndex == other.iToPlotIndex)
			{
				const STacticalAssignment* pLA = getLatestAssignment(other.iUnitID);
				if (pLA->eAssignmentType == A_MOVE_SWAP)
					continue; // don't swap out a unit that was just swapped in

				const CvUnit* pOtherUnit = GET_PLAYER(ePlayer).getUnit(other.iUnitID);
				if (!pOtherUnit->ReadyToSwap())
					continue;

				gMovesToAdd.push_back(SComboMove());
				SComboMove& move = gMovesToAdd.back();
				move.addMove(assignment);
				move.a().eAssignmentType = A_MOVE_SWAP;
				move.addMove(other);
				move.b().eAssignmentType = A_MOVE_SWAP_REVERSE;
				break;
			}

			// Chain: blocker can vacate to a free plot
			if (!isMoveBlockedByOtherUnit(other, eDomain))
			{
				gMovesToAdd.push_back(SComboMove());
				SComboMove& move = gMovesToAdd.back();
				move.addMove(other);
				move.a().eAssignmentType = A_MOVE;
				move.addMove(assignment);
				break;
			}
		}
	}

	//note that this is a stable sort, meaning in case of ties the original order is maintained
	//since we have a fixed cutoff, the simulation result depends on the order the moves were created in, ie the order of units
	std::stable_sort(gMovesToAdd.begin(), gMovesToAdd.end(), SComboMove::PrEvalOrder());

	for (size_t i = 0; i < gMovesToAdd.size(); i++)
	{
		//we need memory for the new child but we'll commit it only later after the uniqueness check
		CvTacticalPosition* pNewChild = storage.peekNext();
		if (!pNewChild)
			break;

		//important, hook it up to the parent so we can access the history
		addChild(pNewChild);
		gCheckedPositions++;

		const STacticalAssignment& aRef = gMovesToAdd[i].getA();

		AddAssignmentResult a = pNewChild->addAssignment(aRef);

		AddAssignmentResult b = RESULT_NOOP;
		if (gMovesToAdd[i].hasB())
			b = pNewChild->addAssignment(gMovesToAdd[i].getB());

		//cannot add a RESTART in the middle of a combo move for consistency, so add afterwards
		if (a == RESULT_ADDED_W_VIS_CHANGE || b == RESULT_ADDED_W_VIS_CHANGE)
		{
			STacticalAssignment restart;
			restart.init(-1, -1, aRef.iUnitID, 0, aRef.eMoveType, A_RESTART, GetPrevPlotScore(aRef.iUnitID, *this));
			restart.SetScore(0, 0, 0);
			pNewChild->assignedMoves.write().push_back(restart);
		}

		//try to detect duplicates ...
		bool isConsistent = (a != RESULT_NOT_ADDED && b != RESULT_NOT_ADDED);
		if (isConsistent && pNewChild->isUnique(TACTSIM_UNIQUENESS_CHECK_GENERATIONS))
		{
			//do we need to keep working on this one?
			if (pNewChild->isEarlyFinish() || pNewChild->isExhausted())
			{
				int iProblemUnit = -1;
				bool bSuccess = true;

				// This returns true as soon as it's found a valid move
				if (bHasGeneral || bHasAdmiral || bHasSiegetower)
					bSuccess = TacticalAIHelpers::AddSupportMoves(*pNewChild, ourUnits, true);

				if (bSuccess && pNewChild->addFinishMovesIfAcceptable(pNewChild->isEarlyFinish(), iProblemUnit))
				{
					//good case, we're done
					completedPositions.push_back(pNewChild);
					giValidEndPos++;
					storage.consumeOne();
				}
				else
				{
					//position is illegal, do not remember it so we can re-use the memory
					giInvalidEndPos++;
					removeChild(pNewChild);

					//remember the id of the bad unit so if necessary we can try again without that unit
					//there might be double-counting or omissions of bad units but we just need to produce a plausible candidate
					if (iProblemUnit != -1)
						gBadUnitsCount[iProblemUnit]++;
				}
			}
			else
			{
				//also good case, keep this for the next round
				openPositionsHeap.push_back(pNewChild);
				push_heap(openPositionsHeap.begin(), openPositionsHeap.end(), heapSort);
				storage.consumeOne();
			}
		}
		else
			removeChild(pNewChild);

		if (childPositions.size() >= (size_t)iMaxBranches)
			break;
	}

	//can happen we have no children if all were considered redundant or invalid
	//note that we also considered blocked moves for all children, but those also may turn out to be invalid if the unit doesn't have enough moves to flee 
	return !childPositions.empty();
}

//lazy update of move plots
void CvTacticalPosition::updateMovePlotsIfRequired()
{
 CvStackingDiagnostics::PlanSampleScope sample(CvStackingDiagnostics::PLAN_MOVE_UPDATE); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	if (movePlotUpdateFlagA==-1 && movePlotUpdateFlagB==-1)
	{
		for (vector<SUnitStats>::const_iterator itUnit = availableUnits_r.begin(); itUnit != availableUnits_r.end(); ++itUnit)
			updateMoveAndAttackPlotsForUnit(*itUnit);
	}
	else
	{
		for (vector<SUnitStats>::const_iterator itUnit = availableUnits_r.begin(); itUnit != availableUnits_r.end(); ++itUnit)
			if (itUnit->iUnitID == movePlotUpdateFlagA || itUnit->iUnitID == movePlotUpdateFlagB)
				updateMoveAndAttackPlotsForUnit(*itUnit);
	}

	movePlotUpdateFlagA = 0;
	movePlotUpdateFlagB = 0;
}

bool CvTacticalPosition::isMoveBlockedByOtherUnit(const STacticalAssignment& move, DomainTypes eDomain) const
{
	//only movement can be blocked
	if (move.eAssignmentType != A_MOVE && move.eAssignmentType != A_MOVE_DOUBLE)
		return false;

	return countBlockingUnitsAtPlot(move.iToPlotIndex, move.eMoveType, eDomain) != 0;
}

int CvTacticalPosition::countBlockingUnitsAtPlot(int iPlotIndex, eUnitMovementStrategy moveType, DomainTypes eDomain) const
{
 const CvTacticalPlot* plot = getTactPlot(iPlotIndex);
 if (!plot)
  return 0;
 int count = 0;
 const bool stackCombat = CvStacking::IsEnabled() && (isCombatUnit(moveType) || isEmbarkedUnit(moveType));
 const CvTacticalPlot::UnitList& units = plot->getUnitsAtPlot();
 for (size_t i = 0; i < units.size(); ++i)
 {
  const CvUnit* other = GET_PLAYER(ePlayer).getUnit(units[i].iUnitID);
  if (!other || other->getDomainType() != eDomain || other->IsStackingUnit())
   continue;
  if (stackCombat ? other->IsCombatUnit() : ((isCombatUnit(moveType) && isCombatUnit(units[i].eMoveType)) || (isEmbarkedUnit(moveType) && isEmbarkedUnit(units[i].eMoveType))))
   ++count;
 }
 if (stackCombat)
  return max(0, count + plot->getFixedFriendlyCount(eDomain) - CvStacking::GetCapacity(ePlayer, eDomain, plot->getPlot()->isCity()) + 1);
 return count;
}

int CvTacticalPosition::getFirstBlockingUnitIDAtPlot(int iPlotIndex, eUnitMovementStrategy moveType, DomainTypes eDomain) const
{
	int result = -1;

	const CvTacticalPlot* tactPlot = getTactPlot(iPlotIndex);
	if (!tactPlot)
		return result;

	const CvTacticalPlot::UnitList& units = tactPlot->getUnitsAtPlot();
	const CvPlayer& kPlayer = GET_PLAYER(ePlayer);

	for (size_t i = 0; i < units.size(); i++)
	{
		const SUnitStats* blocker = getAvailableUnitStats(units[i].iUnitID);
		if (CvStacking::IsEnabled() && (!blocker || blocker->iMovesLeft <= 0))
			continue;
		DomainTypes eOtherDomain = kPlayer.getUnit(units[i].iUnitID)->getDomainType();
		if (eOtherDomain != DOMAIN_SEA)
			eOtherDomain = DOMAIN_LAND;

		if (eOtherDomain != eDomain)
			continue;

		if (isCombatUnit(moveType) && isCombatUnit(units[i].eMoveType))
			return units[i].iUnitID;
		if (isEmbarkedUnit(moveType) && isEmbarkedUnit(units[i].eMoveType))
			return units[i].iUnitID;
	}

	return result;
}

//can we stop now?
bool CvTacticalPosition::isEarlyFinish(bool bExtraKill) const
{ 
	//simple - all enemies are gone (check for non-zero to make sure we aren't trivially complete)
	return nOriginalEnemies > 0 && nOriginalEnemies == nKilledEnemies + (bExtraKill ? 1 : 0);
}

//see if all the plots where our units would end their turn are acceptable
//this is a deferred check because in the beginning it's not clear how many enemy units we can eliminate
bool CvTacticalPosition::addFinishMovesIfAcceptable(bool bEarlyFinish, int& iBadUnitID)
{ 
	//we allow some "bad" units depending on context
	int iUnitLossThreshold = gDefaultUnitLossThreshold + nKilledEnemies;
	int iPotentialUnitLossCounter = 0;

	const vector<SUnitStats>& notQuiteFinishedUnits_r = notQuiteFinishedUnits.read();
	const vector<SUnitStats>& availableUnits_r = availableUnits.read();

	//only units which have exhausted their moves are in this array! if the sim was aborted, somebody else will hopefully pick up the pieces
	for (size_t i=0; i < notQuiteFinishedUnits_r.size(); i++)
	{
		const SUnitStats& unit = notQuiteFinishedUnits_r[i];
		const STacticalAssignment* pInitial = getInitialAssignment(unit.iUnitID);
		if (!pInitial)
			return false; //something wrong

		//if the unit is blocked but has movement left and can flee, let's assume that is ok
		if (unit.eLastAssignment == A_BLOCKED && unit.iMovesLeft>0)
			continue;

		//make sure we don't leave a unit in an impossible position
		const CvTacticalPlot* tactPlot = getTactPlot(unit.iPlotIndex);
		SUnitStats tmp = unit;
		tmp.iMovesLeft = 0;
		STacticalAssignment* nextAssignment = ScorePlotForMove(unit, tactPlot, *this, EM_FINAL);

		if (bReturnToStartPositions && unit.pUnit->plot()->GetPlotIndex() != tactPlot->getPlotIndex())
			return false;

		if (unit.iMovesLeft < nSaveMovement)
			return false;

		bool bAccept = nextAssignment->IsAcceptable();
		if (!bAccept)
		{
			//second chance
			//allow putting the unit in danger if we can afford it and it's not one of our high-xp champions
			if (unit.pUnit->getExperienceTimes100() < gMedianUnitXP && iPotentialUnitLossCounter < iUnitLossThreshold)
			{
				iPotentialUnitLossCounter++;
				bAccept = true;
			}
		}

		if (bAccept)
		{
			// Replace only position value. Reapplying synthetic finish damage or
			// bonuses would count earlier attacks/healing a second time.
			if (CvStacking::IsEnabled() && nextAssignment->IsAcceptable())
				plotScores.write()[unit.iUnitID] = STacticalAssignment::ClampShort(nextAssignment->GetPlotScore());
			//if the score is acceptable, end their turn. unless the unit is blocked, then we may use them for other tasks
			if (unit.eLastAssignment != A_BLOCKED)
			{
				nextAssignment->iRemainingMoves = unit.iMovesLeft;
				nextAssignment->eAssignmentType = A_FINISH;
				assignedMoves.write().push_back(*nextAssignment);
			}
		}
		else
		{
			iBadUnitID = unit.iUnitID;
			return false;
		}
	}

	//try to enforce some sort of sparsity, we should use only the minimum amount of units. 
	//so give a bonus for unmoved units. especially important in earlyFinish situations with many units.
	for (size_t i = 0; i < availableUnits_r.size(); i++)
	{
		const SUnitStats& unit = availableUnits_r[i];
		if (unit.eLastAssignment == A_INITIAL)
			plotScores.write()[unit.iUnitID] += isEarlyFinish() ? 123 : 45;
	}

	if (CvStacking::IsEnabled())
	{
		iTotalScore = (iDamageDelta + iBonusScore) * 10;
		const STacticalPlotScores& finalScores = plotScores.read();
		for (STacticalPlotScores::const_iterator it = finalScores.begin(); it != finalScores.end(); ++it)
			iTotalScore += it->second;
	}

	//scores look good and target was killed, we're done
	//second chance: did we kill anything (offensive), heal a unit, or at least improve the arrangement of our units (defensive)?
	//order is important here, need to add finish moves first!
	if (bEarlyFinish || isKillOrImprovedPosition())
	{
		vector<SUnitStats>& finishedUnits_w = finishedUnits.write();
		finishedUnits_w.insert(finishedUnits_w.end(), notQuiteFinishedUnits_r.begin(), notQuiteFinishedUnits_r.end());
		notQuiteFinishedUnits.write().clear();
		iBadUnitID = -1;
		return true;
	}

	//do not clear notQuiteFinishedUnits for better debugging
	return false;
}

//although we try to pick "positive" moves only sometimes there are only bad choices
bool CvTacticalPosition::isKillOrImprovedPosition() const
{
	const vector<STacticalAssignment>& assignedMoves_r = assignedMoves.read();
	//if we made a kill, that is always good
	//on the other hand it messes up the enemy distance, so we cannot really compare before/after in that case!
	//note that regular attacks are checked below!
	//also a restart means we discovered new enemies so that is also okay
	for (size_t i = nFirstInterestingAssignment; i < assignedMoves_r.size(); i++)
		if (isKillAssignment(assignedMoves_r[i].eAssignmentType) || assignedMoves_r[i].eAssignmentType==A_RESTART)
			return true;

	//find the original position to look up the unit move strategies
	const CvTacticalPosition* root = this;
	while (root->getParent())
		root = root->getParent();

	//if we did not make an attack, see if our units moved in the right way at least
	//note that this comparison only works because we know we did not kill an enemy, which would change enemyDistance!
	int iPositive = 0; //enemy distance change
	int iNegative = 0; //enemy distance change
	int iBefore = 0; //target distance change
	int iAfter = 0; //target distance change
	int iAttacksNoMove = 0;
	int iHealingUnits = 0;
	for (size_t i = nFirstInterestingAssignment; i < assignedMoves_r.size(); i++)
	{
		const STacticalAssignment& move = assignedMoves_r[i];
		if (move.eAssignmentType == A_FINISH)
		{
			//compare final to initial and see whether we came closer to the ideal distance
			const STacticalAssignment* initial = getInitialAssignment(move.iUnitID);
			const SUnitStats* unit = root->getAvailableUnitStats(move.iUnitID);

			// support units are not part of combat simulation
			if (!unit)
				continue;

			CvUnit* pUnit = GET_PLAYER(ePlayer).getUnit(unit->iUnitID);
			const CvTacticalPlot* initialPlot = root->getTactPlot(initial->iFromPlotIndex);
			const CvTacticalPlot* finalPlot = getTactPlot(move.iFromPlotIndex);

			//only relevant in degenerate cases without enemies
			int iDistBefore = TacticalAIHelpers::GetPlotDistanceToTarget(initial->iFromPlotIndex, pUnit->getDomainType());
			int iDistAfter = TacticalAIHelpers::GetPlotDistanceToTarget(move.iFromPlotIndex, pUnit->getDomainType());
			// Only count if both are reachable - can't meaningfully compare if either is INT_MAX
			if (iDistBefore != INT_MAX && iDistAfter != INT_MAX)
			{
				iBefore += iDistBefore;
				iAfter += iDistAfter;
			}

			//which domain to use here? for simplicity assume firstline is melee and in-domain, everything else cross-domain
			CvTacticalPlot::eTactPlotDomain eRelevantDomain = unit->eMoveStrategy == MS_FIRSTLINE ? (finalPlot->getPlot()->isWater() ? CvTacticalPlot::TD_SEA : CvTacticalPlot::TD_LAND) : CvTacticalPlot::TD_BOTH;
			int iInitialDistance = initialPlot->getEnemyDistance(eRelevantDomain);
			int iFinalDistance = finalPlot->getEnemyDistance(eRelevantDomain);

			//occupying a citadel is always fine
			bool bIsStayingInFrontlineCitadel = (initialPlot->getPlotIndex() == finalPlot->getPlotIndex()) &&
				finalPlot->getEnemyDistance() < 3 && TacticalAIHelpers::IsPlayerCitadel(finalPlot->getPlot(), getPlayer()) && pUnit->getDomainType() == DOMAIN_LAND;

			switch (unit->eMoveStrategy)
			{
			case MS_NONE:
				UNREACHABLE(); // Units are always supposed to be assigned a strategy.
			case MS_FIRSTLINE:
				if (bIsStayingInFrontlineCitadel)
					iPositive++;
				else if (iInitialDistance != 1 && iFinalDistance == 1)
					iPositive++;
				else if (iInitialDistance == 1 && iFinalDistance != 1)
					iNegative++;
				break;
			case MS_SECONDLINE:
				if (bIsStayingInFrontlineCitadel)
					iPositive++;
				else if (iInitialDistance != 2 && iFinalDistance == 2)
					iPositive++;
				else if (iInitialDistance == 2 && iFinalDistance != 2)
					iNegative++;
				break;
			case MS_THIRDLINE:
				//thirdline is a bit different, ignore citadels
				if (iInitialDistance == 1 && iFinalDistance > 1)
					iPositive++;
				if (iInitialDistance > 1 && iFinalDistance == 1)
					iNegative++;
				break;
			case MS_SUPPORT:
			case MS_EMBARKED:
				//ignore for now
				break;
			}
		}
		else if (move.eAssignmentType == A_RANGEATTACK || move.eAssignmentType == A_MELEEATTACK)
			//we already checked for kills!
			iAttacksNoMove++;
		else if (move.eAssignmentType == A_HEAL)
			iHealingUnits++;
		else if (move.eAssignmentType == A_USE_POWER)
			return true;

		//note that RESTARTS are ignored here ... just hope that we still find good moves after the restart
	}

	bool bMovingTowardsTarget = (bTargetDistanceRelevant && iAfter < iBefore);
	if (haveEnemies())
	{
		//staying in place and bombarding is fine!
		//staying in place and healing is also progress TODO: should we check whether we are healing more than we are taking damage?
		//note that retreating a damaged unit counts as positive because it should be MS_THIRDLINE
		return (iNegative < iPositive) || (iNegative == iPositive && (bMovingTowardsTarget || iAttacksNoMove > 0 || iHealingUnits > 1 || (iHealingUnits == root->GetNumAvailableUnits())));
	}
	else
	{
		//did we get closer to the target plot?
		return bMovingTowardsTarget || iHealingUnits > 0;
	}
}

//this influences how daring we'll be
void CvTacticalPosition::countEnemiesAndCheckVisibility()
{
	if (parentPosition != NULL)
		CUSTOMLOG("should not happen");

	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	PlotIndexContainer& enemyPlots_w = enemyPlots.write();
	vector<CvTacticalPlot>& tactPlots_w = tactPlots.write();

	//will add non-sim friendly units later
	nOurOriginalUnits = availableUnits_r.size();
	nOriginalEnemies = 0;
	enemyPlots_w.clear();

	for (size_t i = 0; i < tactPlots_w.size(); i++)
	{
		bool bEnemyBarbarianCamp = !GET_PLAYER(ePlayer).isBarbarian() ? tactPlots_w[i].getPlot()->getRevealedImprovementType(GET_PLAYER(ePlayer).getTeam()) == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT) : false;
		if (tactPlots_w[i].isEnemy() || bEnemyBarbarianCamp)
		{
			// Cities and barbarian camps count as one enemy each
			if (tactPlots_w[i].isEnemyCity())
				nOriginalEnemies++;
			else if (bEnemyBarbarianCamp)
				nOriginalEnemies++;

			nOriginalEnemies += (int)tactPlots_w[i].getEnemyUnits().size();
			enemyPlots_w.push_back(tactPlots_w[i].getPlotIndex());
		}

		//also count our non-sim units which are close to the front
		if (tactPlots_w[i].getEnemyDistance() < 3)
			nOurOriginalUnits += tactPlots_w[i].getFixedFriendlyCount(NO_DOMAIN);

		//ignore range 1, we can always see those plots so they are boring
		//ignore range 4+, this is too far out and we don't have those plots cached
		const vector<CvPlot*>& vSeeToPlots2 = GC.getMap().GetPlotsAtRangeX(tactPlots_w[i].getPlot(), 2, true, true);
		const vector<CvPlot*>& vSeeToPlots3 = GC.getMap().GetPlotsAtRangeX(tactPlots_w[i].getPlot(), 3, true, true);
		int iVisiblityScore2 = 0;
		int iVisiblityScore3 = 0;

		//give a bonus to plots with high outward visibility, an enemy might come into range next turn!
		//however, we are only interested in the direction towards the enemy ... look at enemy distance as a proxy 
		for (size_t j = 0; j < vSeeToPlots2.size(); j++)
		{
			//null is used as a sentinel value
			if (vSeeToPlots2[j] == NULL)
				continue;

			const CvTacticalPlot* testPlot = getTactPlot(vSeeToPlots2[j]->GetPlotIndex());
			if (testPlot && testPlot->getEnemyDistance() <= 3)
				iVisiblityScore2++;
		}
		for (size_t j = 0; j < vSeeToPlots3.size(); j++)
		{
			//null is used as a sentinel value
			if (vSeeToPlots3[j] == NULL)
				continue;

			const CvTacticalPlot* testPlot = getTactPlot(vSeeToPlots3[j]->GetPlotIndex());
			if (testPlot && testPlot->getEnemyDistance() <= 3)
				iVisiblityScore3++;
		}

		tactPlots_w[i].setNumVisiblePlotsRange2(iVisiblityScore2);
		tactPlots_w[i].setNumVisiblePlotsRange3(iVisiblityScore3);
	}

	//need this to be sorted for binary search
	std::stable_sort(enemyPlots_w.begin(), enemyPlots_w.end());
}

void CvTacticalPosition::refreshVolatilePlotProperties(bool bInitial)
{
	gLandEnemies.clear();
	gSeaEnemies.clear();
	gCitadels.clear();
	gCities.clear();

	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	vector<CvTacticalPlot>& tactPlots_w = tactPlots.write();

	for (vector<CvTacticalPlot>::iterator it = tactPlots_w.begin(); it != tactPlots_w.end(); ++it)
	{
		//need to check whether this is a city or actual units
		if (it->isEnemyCity())
			gCities.push_back(it->getPlotIndex());
		//ignore garrisons for enemy distance consideration
		else if (it->isEnemyCombatUnit())
		{
			if (it->getEnemyDistance(CvTacticalPlot::TD_LAND) == 0)
				gLandEnemies.push_back(it->getPlotIndex());
			if (it->getEnemyDistance(CvTacticalPlot::TD_SEA) == 0)
				gSeaEnemies.push_back(it->getPlotIndex());
		}

		it->resetVolatileProperties();

		//include plots with enemies if they are just outside of the simulation range
		//we won't attack them but we won't ignore them either
		it->checkEdgePlotsForSurprises(*this,gLandEnemies,gSeaEnemies);

		int iImprovementDamage = TacticalAIHelpers::GetOtherPlayerImprovementDamage(it->getPlot(), getPlayer(), true);
		if (iImprovementDamage > 0 && !plotHasAssignmentOfType(it->getPlotIndex(), A_PILLAGE))
			gCitadels.push_back(make_pair(it->getPlotIndex(), iImprovementDamage));
	}

	// Some teams have bonus sight range in certain circumstances
	TeamTypes eTeam = !availableUnits_r.empty() ? availableUnits_r[0].pUnit->getTeam() : NO_TEAM;

	//distance transform
	for (vector<CvTacticalPlot>::iterator it = tactPlots_w.begin(); it != tactPlots_w.end(); ++it)
	{
		const CvPlot* pSourcePlot = it->getPlot();
		const CvPlot* pTargetPlot;
		//pt1
		for (size_t i = 0; i < gLandEnemies.size(); i++)
		{
			pTargetPlot = GC.getMap().plotByIndexUnchecked(gLandEnemies[i]);
			int iDistance = plotDistance(*pSourcePlot, *pTargetPlot);
			if (iDistance < it->getEnemyDistance(CvTacticalPlot::TD_BOTH))
				it->setEnemyDistance(CvTacticalPlot::TD_BOTH, iDistance);
			if (iDistance < it->getEnemyDistance(CvTacticalPlot::TD_LAND))
				it->setEnemyDistance(CvTacticalPlot::TD_LAND, iDistance);
			if (iDistance == 1)
			{
				it->setNumAdjacentEnemies(CvTacticalPlot::TD_BOTH, it->getNumAdjacentEnemies(CvTacticalPlot::TD_BOTH) + 1);
				it->setNumAdjacentEnemies(CvTacticalPlot::TD_LAND, it->getNumAdjacentEnemies(CvTacticalPlot::TD_LAND) + 1);
			}
			if (iDistance < it->getRangedAttackEnemyDistance(CvTacticalPlot::TD_BOTH))
			{
				if (pSourcePlot->canSeePlot(pTargetPlot, eTeam, iDistance, NO_DIRECTION))
					it->setRangedAttackEnemyDistance(CvTacticalPlot::TD_BOTH, iDistance);
			}
			if (iDistance < it->getRangedAttackEnemyDistance(CvTacticalPlot::TD_LAND))
			{
				if (pSourcePlot->canSeePlot(pTargetPlot, eTeam, iDistance, NO_DIRECTION))
					it->setRangedAttackEnemyDistance(CvTacticalPlot::TD_LAND, iDistance);
			}
		}

		//pt2
		for (size_t i = 0; i < gSeaEnemies.size(); i++)
		{
			pTargetPlot = GC.getMap().plotByIndexUnchecked(gSeaEnemies[i]);
			int iDistance = plotDistance(*pSourcePlot, *pTargetPlot);
			if (iDistance < it->getEnemyDistance(CvTacticalPlot::TD_BOTH))
				it->setEnemyDistance(CvTacticalPlot::TD_BOTH, iDistance);
			if (iDistance < it->getEnemyDistance(CvTacticalPlot::TD_SEA))
				it->setEnemyDistance(CvTacticalPlot::TD_SEA, iDistance);
			if (iDistance == 1)
			{
				it->setNumAdjacentEnemies(CvTacticalPlot::TD_BOTH, it->getNumAdjacentEnemies(CvTacticalPlot::TD_BOTH) + 1);
				it->setNumAdjacentEnemies(CvTacticalPlot::TD_SEA, it->getNumAdjacentEnemies(CvTacticalPlot::TD_SEA) + 1);
			}
			if (iDistance < it->getRangedAttackEnemyDistance(CvTacticalPlot::TD_BOTH))
			{
				if (pSourcePlot->canSeePlot(pTargetPlot, eTeam, iDistance, NO_DIRECTION))
					it->setRangedAttackEnemyDistance(CvTacticalPlot::TD_BOTH, iDistance);
			}
			if (iDistance < it->getRangedAttackEnemyDistance(CvTacticalPlot::TD_SEA))
			{
				if (pSourcePlot->canSeePlot(pTargetPlot, eTeam, iDistance, NO_DIRECTION))
					it->setRangedAttackEnemyDistance(CvTacticalPlot::TD_SEA, iDistance);
			}
		}

		//pt3
		for (size_t i = 0; i < gCities.size(); i++)
		{
			pTargetPlot = GC.getMap().plotByIndexUnchecked(gCities[i]);
			int iDistance = plotDistance(*pSourcePlot, *pTargetPlot);
			if (iDistance < it->getEnemyDistance(CvTacticalPlot::TD_BOTH))
				it->setEnemyDistance(CvTacticalPlot::TD_BOTH, iDistance);
			if (iDistance < it->getEnemyDistance(CvTacticalPlot::TD_LAND))
				it->setEnemyDistance(CvTacticalPlot::TD_LAND, iDistance);
			if (iDistance < it->getEnemyDistance(CvTacticalPlot::TD_SEA))
				it->setEnemyDistance(CvTacticalPlot::TD_SEA, iDistance);
			if (iDistance == 1)
			{
				it->setNumAdjacentEnemies(CvTacticalPlot::TD_BOTH, it->getNumAdjacentEnemies(CvTacticalPlot::TD_BOTH) + 1);
				it->setNumAdjacentEnemies(CvTacticalPlot::TD_LAND, it->getNumAdjacentEnemies(CvTacticalPlot::TD_LAND) + 1);
				it->setNumAdjacentEnemies(CvTacticalPlot::TD_SEA, it->getNumAdjacentEnemies(CvTacticalPlot::TD_SEA) + 1);
			}
			if (iDistance < it->getRangedAttackEnemyDistance(CvTacticalPlot::TD_BOTH))
			{
				if (pSourcePlot->canSeePlot(pTargetPlot, eTeam, iDistance, NO_DIRECTION))
					it->setRangedAttackEnemyDistance(CvTacticalPlot::TD_BOTH, iDistance);
			}
			if (iDistance < it->getRangedAttackEnemyDistance(CvTacticalPlot::TD_LAND))
			{
				if (pSourcePlot->canSeePlot(pTargetPlot, eTeam, iDistance, NO_DIRECTION))
					it->setRangedAttackEnemyDistance(CvTacticalPlot::TD_LAND, iDistance);
			}
			if (iDistance < it->getRangedAttackEnemyDistance(CvTacticalPlot::TD_SEA))
			{
				if (pSourcePlot->canSeePlot(pTargetPlot, eTeam, iDistance, NO_DIRECTION))
					it->setRangedAttackEnemyDistance(CvTacticalPlot::TD_SEA, iDistance);
			}
		}
	}

	//citadels
	for (size_t i=0; i<gCitadels.size(); i++)
	{
		//iterate neighbors
		CvPlot** aNeighbors = GC.getMap().getNeighborsUnchecked(GC.getMap().plotByIndexUnchecked(gCitadels[i].first));
		for (int iDir = 0; iDir < NUM_DIRECTION_TYPES; iDir++)
		{
			CvPlot* pNeighbor = aNeighbors[iDir];
			if (!pNeighbor)
				continue;

			CvTacticalPlot* tactPlot = getTactPlotMutable(pNeighbor->GetPlotIndex());
			if (tactPlot)
				tactPlot->SetAdjacentImprovementDamage(max(tactPlot->GetAdjacentImprovementDamage(), gCitadels[i].second));
		}
	}

	//deferred update of adjacent unit count for non-sim units
	if (bInitial)
	{
		for (vector<CvTacticalPlot>::iterator it = tactPlots_w.begin(); it != tactPlots_w.end(); ++it)
		{
			//even if we're not sure whether the unit is going to stay, we can get temporary benefits
			if (it->getFixedFriendlyCount(DOMAIN_LAND) > 0)
			{
				it->changeNeighboringUnitCount(*this, MS_FIRSTLINE, CvTacticalPlot::TD_LAND, +1);
				if (it->isCombatEndTurn())
					it->setCombatUnitEndTurn(*this, CvTacticalPlot::TD_LAND, true);
			}
			//don't count cities twice
			if (it->getFixedFriendlyCount(DOMAIN_SEA) > 0 && !it->getPlot()->isCity())
			{
				it->changeNeighboringUnitCount(*this, MS_FIRSTLINE, CvTacticalPlot::TD_SEA, +1);
				if (it->isCombatEndTurn())
					it->setCombatUnitEndTurn(*this, CvTacticalPlot::TD_SEA, true);
			}
		}
	}
}

//need a default constructor for stl containers ...
CvTacticalPosition::CvTacticalPosition()
{
	initFromScratch(NO_PLAYER, AL_LOW, NULL, false, false, false);
}

void CvTacticalPosition::initFromScratch(PlayerTypes player, eAggressionLevel eAggLvl, CvPlot* pTarget, bool bTargetDistanceRelevant_, bool bReturnToStartPositions_, int iSaveMovement_)
{
 ObserveKernelStateMutation(this,NULL); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
	ePlayer = player;
	pTargetPlot = pTarget;
	bTargetDistanceRelevant = bTargetDistanceRelevant_;
	bReturnToStartPositions = bReturnToStartPositions_;
	bHasGeneral = false;
	bHasAdmiral = false;
	bHasSiegetower = false;
	nSaveMovement = iSaveMovement_;
	eAggression = eAggLvl;
	nOurOriginalUnits = 0;
	nOriginalEnemies = 0;
	nKilledEnemies = 0;
	nFirstInterestingAssignment = 0;
	iBonusScore = 0;
	iDamageDelta = 0;
	iTotalScore = 0;
	iScoreOverParent = 0; 
	parentPosition = NULL;
	iGeneration = 0;
	iID = 1; //zero doesn't work here
	movePlotUpdateFlagA = 0;
	movePlotUpdateFlagB = 0;

	childPositions.clear();
	tactPlotLookup.clear();
	tactPlots.clear();
	availableUnits.clear();
	notQuiteFinishedUnits.clear();
	finishedUnits.clear();
	assignedMoves.clear();
	enemyPlots.clear();
	freedPlots.clear();
	unitDamageDealt.clear();
	plotScores.clear();
}

void CvTacticalPosition::initFromParent(const CvTacticalPosition& parent)
{
 ObserveKernelStateMutation(this,&parent); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
	ePlayer = parent.ePlayer;
	pTargetPlot = parent.pTargetPlot;
	bTargetDistanceRelevant = parent.bTargetDistanceRelevant;
	bReturnToStartPositions = parent.bReturnToStartPositions;
	bHasGeneral = parent.bHasGeneral;
	bHasAdmiral = parent.bHasAdmiral;
	bHasSiegetower = parent.bHasSiegetower;
	nSaveMovement = parent.nSaveMovement;
	eAggression = parent.eAggression;
	nOurOriginalUnits = parent.nOurOriginalUnits;
	nOriginalEnemies = parent.nOriginalEnemies;
	nKilledEnemies = parent.nKilledEnemies;
	nFirstInterestingAssignment = parent.nFirstInterestingAssignment;
	iBonusScore = parent.iBonusScore;
	iDamageDelta = parent.iDamageDelta;
	iTotalScore = parent.iTotalScore;
	iScoreOverParent = 0;
	parentPosition = &parent;
	movePlotUpdateFlagA = parent.movePlotUpdateFlagA;
	movePlotUpdateFlagB = parent.movePlotUpdateFlagB;
	iGeneration = parent.iGeneration + 1;

	//clever scheme to encode the tree structure into IDs
	//works only if the tree is not too wide or too deep
	if (parent.getID() < ULLONG_MAX / 10 - 10)
		iID = parent.getID() * 10 + parent.childPositions.size();
	else
		iID = ULLONG_MAX;

	//childPositions stays empty!
	childPositions.clear();

	//copied from parent, modified when addAssignment is called
	tactPlotLookup.inheritFrom(parent.tactPlotLookup.read());
	tactPlots.inheritFrom(parent.tactPlots.read());
	assignedMoves.inheritFrom(parent.assignedMoves.read());
	availableUnits.inheritFrom(parent.availableUnits.read());
	notQuiteFinishedUnits.inheritFrom(parent.notQuiteFinishedUnits.read());
	finishedUnits.inheritFrom(parent.finishedUnits.read());
	freedPlots.inheritFrom(parent.freedPlots.read());
	enemyPlots.inheritFrom(parent.enemyPlots.read());
	unitDamageDealt.inheritFrom(parent.unitDamageDealt.read());
	plotScores.inheritFrom(parent.plotScores.read());
}

bool CvTacticalPosition::haveEnemies() const
{
	return nOriginalEnemies > 0;
}

bool CvTacticalPosition::removeChild(CvTacticalPosition* pChild)
{
	//just unlink the child - do not delete it, the memory is allocated statically
	vector<CvTacticalPosition*>::iterator it = find(childPositions.begin(), childPositions.end(), pChild);
	if (it!=childPositions.end())
		childPositions.erase(it);

	return false;
}

size_t CvTacticalPosition::addChild(CvTacticalPosition* pChild)
{
	if (pChild)
	{
		childPositions.push_back(pChild); //this order is better for generating an ID for the child
		pChild->initFromParent(*this);
	}
	return childPositions.size();
}

void CvTacticalPosition::getPlotsWithChangedVisibility(const STacticalAssignment& assignment, vector<int>& madeVisible) const
{
	madeVisible.clear();

	CvUnit* pUnit = GET_PLAYER(ePlayer).getUnit(assignment.iUnitID);
	CvPlot* pNewPlot = GC.getMap().plotByIndexUnchecked(assignment.iToPlotIndex);

	for (int i=1; i<RING3_PLOTS; i++)
	{
		CvPlot* pTestPlot = iterateRingPlots(pNewPlot,i); //iterate around the new plot, not the old plot
		if (!pTestPlot)
			continue;

		//todo: check for distance to target? TACTICAL_COMBAT_MAX_TARGET_DISTANCE

		if (pTestPlot->getVisibilityCount(pUnit->getTeam())==0)
		{
			if (pNewPlot->canSeePlot(pTestPlot, pUnit->getTeam(), pUnit->visibilityRange(), pUnit->getFacingDirection(true)))
				madeVisible.push_back(pTestPlot->GetPlotIndex());
		}
	}
}

void CvTacticalPosition::updateMoveAndAttackPlotsForUnit(SUnitStats unit)
{
	CvUnit* pUnit = GET_PLAYER(ePlayer).getUnit(unit.iUnitID);
	CvPlot* pStartPlot = GC.getMap().plotByIndexUnchecked(unit.iPlotIndex);
	const PlotIndexContainer& freedPlots_r = freedPlots.read();

	TCachedMovePlots::const_iterator itP = gReachablePlotsLookup.find(SPathFinderStartPos(unit, freedPlots_r, SPathFinderStartPos::LookupOnly()));
	if (itP != gReachablePlotsLookup.end())
	{
		gMovePlotsCacheHit++;
	}
	else
	{
		gMovePlotsCacheMiss++;

		//note: we allow (intermediate) embarkation here but filter out the non-native plots later (useful for denmark and lategame)
		int iMoveFlags = CvUnit::MOVEFLAG_IGNORE_STACKING_SELF | CvUnit::MOVEFLAG_IGNORE_DANGER;
		ReachablePlots reachablePlots = TacticalAIHelpers::GetAllPlotsInReachThisTurn(pUnit, pStartPlot, iMoveFlags, 0, unit.iMovesLeft, freedPlots_r);

		//need to know this if we're doing defensive positioning
		bool bTargetIsEnemy = pTargetPlot->isEnemyUnit(ePlayer, true, true) || pTargetPlot->isEnemyCity(*pUnit);
		CvPlayer& kPlayer = GET_PLAYER(ePlayer);

		//try to save some memory here
		ReachablePlots reachablePlotsPruned;
		for (ReachablePlots::const_iterator it = reachablePlots.begin(); it != reachablePlots.end(); ++it)
		{
			CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);

			//this is a performance fix / logic simplification
			//all open positions share just one instance of gSafePlotCount
			//we only update the count once at the start of the sim
			//if there is no safe plot then, there will never be one!
			if (!parentPosition)
			{
				bool bIsSafe = GET_PLAYER(ePlayer).GetPlotDanger(*pPlot, pUnit, GetUnitDamageDealt(), 0) < pUnit->GetCurrHitPoints();
				if (bIsSafe && pUnit->canEndTurnAtPlot(pPlot))
					gSafePlotCount[unit.iUnitID]++;
			}

			//note that if the unit is far away, it won't have any good plots and will be considered blocked
			//this is just a rough check, we check the existance of a corresponding tact plot below
			//+2 is due to the "maneuver space" around each enemy
			if (TacticalAIHelpers::GetPlotDistanceToTarget(it->iPlotIndex, pUnit->getDomainType()) > TACTICAL_COMBAT_MAX_TARGET_DISTANCE+2)
				continue;

			if (unit.eMoveStrategy == MS_EMBARKED)
			{
				//only allow disembarking if it takes us closer to the target
				if (TacticalAIHelpers::GetPlotDistanceToTarget(it->iPlotIndex, pUnit->getDomainType()) >= TacticalAIHelpers::GetPlotDistanceToTarget(pUnit->plot()->GetPlotIndex(), pUnit->getDomainType()))
					continue;
			}
			else
			{
				if (haveEnemies())
				{
					//ignore all plots where we cannot fight. allow ships to capture/garrison cities though!
					if (!pUnit->isNativeDomain(pPlot) && !pPlot->isCoastalCityOrPassableImprovement(pUnit->getOwner(),false,false))
						continue;
				}
				else
				{
					//we don't want to fight so embarkation is ok if we're careful
					if (!pUnit->isNativeDomain(pPlot))
					{
						//for embarked units, every attacker is bad news
						if (bTargetIsEnemy || !kPlayer.GetPossibleAttackers(*pPlot, NO_TEAM).empty())
							continue;

						CvTacticalDominanceZone* pZone = GET_PLAYER(ePlayer).GetTacticalAI()->GetTacticalAnalysisMap()->GetZoneByPlot(pPlot);
						if (pZone && pZone->GetOverallDominanceFlag() != TACTICAL_DOMINANCE_FRIENDLY)
							continue;
					}
				}
			}

			//last (expensive) check, need to have a tact plot for each reachable plot
			const CvTacticalPlot* plot = getTactPlot(it->iPlotIndex);
			if (plot && !plot->isBlockedByNonSimUnit(DomainForUnit(pUnit)))
				reachablePlotsPruned.insertNoIndex(*it);
		}

		reachablePlotsPruned.createIndex();
		gReachablePlotsLookup[SPathFinderStartPos(unit, freedPlots_r)] = reachablePlotsPruned;
	}

	//simply ignore visibility here, later there's a check if there is a valid tactical plot for the targets
	TCachedRangeAttackPlots::const_iterator itA = gRangeAttackPlotsLookup.find(make_pair(unit.iUnitID, unit.iPlotIndex));
	if (itA != gRangeAttackPlotsLookup.end())
		gAttackPlotsCacheHit++;
	else
	{
		gAttackPlotsCacheMiss++;
		vector<int> rangeAttackPlots = TacticalAIHelpers::GetPlotsUnderRangedAttackFrom(pUnit, pStartPlot, true, true);
		gRangeAttackPlotsLookup[make_pair(unit.iUnitID, unit.iPlotIndex)] = rangeAttackPlots;
	}
}

bool CvTacticalPosition::isAttackablePlot(int iPlotIndex) const
{
	const PlotIndexContainer& enemyPlots_r = enemyPlots.read();
	return std::binary_search(enemyPlots_r.begin(), enemyPlots_r.end(), iPlotIndex );
}

pair<int,int> CvTacticalPosition::doVisibilityUpdate(const STacticalAssignment& newAssignment)
{
	int nNewEnemies = 0;

	//may need to add some new tactical plots - ideally we should reconsider all queued assignments afterwards
	//the next round of assignments will take into account the new plots in any case
	getPlotsWithChangedVisibility(newAssignment, gNewlyVisiblePlots);
	for (size_t i=0; i<gNewlyVisiblePlots.size(); i++)
	{
		//since it was invisible before, we know there are no friendly units around
		CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(gNewlyVisiblePlots[i]);
		if (pPlot) //also create plots for neutral units - otherwise edgeOfTheKnownWorld is not correct
		{
			//can pass empty set of units - the plot was invisible before so we know there is none of our units there
			if (addTacticalPlot(pPlot, vector<const CvUnit*>()))
			{
				//we revealed a new enemy ... need to execute moves up to here, do a danger plot update and reconsider
				if (pPlot->isEnemyUnit(ePlayer, true, false))
					nNewEnemies++;

#if defined(MOD_CORE_DEBUGGING)
				if (MOD_CORE_DEBUGGING)
				{
					//make sure that the adjacent unit count is correct
					//normally it should because adjacent plots are visible from the beginning but ...
					CvPlot** aNeighbors = GC.getMap().getNeighborsUnchecked(GC.getMap().plotByIndexUnchecked(pPlot->GetPlotIndex()));
					for (int i = 0; i < NUM_DIRECTION_TYPES; i++)
					{
						CvPlot* pNeighbor = aNeighbors[i];
						if (!pNeighbor)
							continue;

						const CvTacticalPlot* neighborPlot = getTactPlot(pNeighbor->GetPlotIndex());
						if (neighborPlot)
						{
							const CvTacticalPlot::UnitList& units = neighborPlot->getUnitsAtPlot();
							for (size_t j = 0; j < units.size(); j++)
								ASSERT(!isCombatUnit(units[j].eMoveType));
						}
					}
				}
#endif
			}
		}
	}

	if (nNewEnemies>0)
		refreshVolatilePlotProperties();

	return make_pair( (int)gNewlyVisiblePlots.size(), nNewEnemies);
}

bool CvTacticalPosition::HasKilledEnemyUnit(const CvTacticalPlot& plot) const
{
	const vector<const CvUnit*>& enemies = plot.getEnemyUnits();
	for (size_t j = 0; j < enemies.size(); ++j)
		if (GetUnitDamage(enemies[j]->GetID()) >= enemies[j]->GetCurrHitPoints())
			return true;
	return false;
}

CvTacticalPosition::AddAssignmentResult CvTacticalPosition::addAssignment(const STacticalAssignment& newAssignment)
{
	// A movement assignment must change plots. Same-tile attacks, pillaging,
	// healing and finish/initial markers have their own types and remain valid.
	if (newAssignment.iFromPlotIndex == newAssignment.iToPlotIndex &&
		(newAssignment.eAssignmentType == A_MOVE || newAssignment.eAssignmentType == A_MOVE_FORCED ||
		 newAssignment.eAssignmentType == A_MOVE_DOUBLE || newAssignment.eAssignmentType == A_MOVE_SWAP ||
		 newAssignment.eAssignmentType == A_MOVE_SWAP_REVERSE))
		return RESULT_NOT_ADDED;

	//if we killed an enemy ZOC will change
	bool bRecomputeAllMoves = false;
	//newly visible plots, newly visible enemies
	std::pair<int, int> visibilityResult(0, 0);
	vector<SUnitStats>& availableUnits_w = availableUnits.write();
	
	vector<SUnitStats>::iterator itUnit = find_if(availableUnits_w.begin(), availableUnits_w.end(), PrMatchingUnit(newAssignment.iUnitID));

	if (itUnit == availableUnits_w.end() || itUnit->iPlotIndex != newAssignment.iFromPlotIndex)
		return RESULT_NOT_ADDED;


	//tactical plots are only touched for "real" moves. blocked units may be on invalid plots.
	//a unit may also start out on an invalid plot (eg. too far away)
	if (newAssignment.eAssignmentType != A_BLOCKED && itUnit->eLastAssignment != A_INITIAL)
	{
		if (!getTactPlotMutable(newAssignment.iToPlotIndex))
			return RESULT_NOT_ADDED;
		if (!getTactPlotMutable(newAssignment.iFromPlotIndex))
			return RESULT_NOT_ADDED;
	}

	//i know what you did last summer!
	ObserveKernelStateMutation(this,parentPosition); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
	itUnit->eLastAssignment = newAssignment.eAssignmentType;

	// Observe pathological history growth before the allocation; never cap gameplay.
	if (CvStackingDiagnostics::Enabled(1, ePlayer))
	{
		const size_t threshold = (size_t)max(0, CvStacking::GetInt("DiagnosticsLongPlanThreshold", 256));
		const vector<STacticalAssignment>& history = assignedMoves.read();
		if (threshold > 0 && history.size() >= threshold && history.size() % threshold == 0)
		{
			const STacticalAssignment& previous = history.back();
			CvStackingDiagnostics::Record(1, ePlayer, "LONG_PLAN", "target=%d:%d generation=%u length=%u capacity=%u unit=%d type=%d from=%d to=%d movesBefore=%d movesAfter=%d attacks=%d previousUnit=%d previousType=%d previousFrom=%d previousTo=%d previousMoves=%d",
				pTargetPlot->getX(), pTargetPlot->getY(), (unsigned int)iGeneration, (unsigned int)history.size(), (unsigned int)history.capacity(),
				newAssignment.iUnitID, (int)newAssignment.eAssignmentType, newAssignment.iFromPlotIndex, newAssignment.iToPlotIndex,
				itUnit->iMovesLeft, (int)newAssignment.iRemainingMoves, itUnit->iAttacksLeft, previous.iUnitID, (int)previous.eAssignmentType,
				previous.iFromPlotIndex, previous.iToPlotIndex, (int)previous.iRemainingMoves);
		}
	}
	//store the assignment
	assignedMoves.write().push_back(newAssignment);

	//now deal with the consequencess
	bool bAffectsScore = true;
	bool bEndOfSim = false;
	switch (newAssignment.eAssignmentType)
	{
	case A_INITIAL:
		getTactPlotMutable(newAssignment.iToPlotIndex)->friendlyUnitMovingIn(*this, newAssignment);
		bAffectsScore = false;
		break;
	case A_MOVE_FORCED:
	case A_MOVE_SWAP_REVERSE:
	case A_MOVE:
	case A_MOVE_SWAP:
	case A_CAPTURE:
	{
		itUnit->iMovesLeft = newAssignment.iRemainingMoves;
		itUnit->iPlotIndex = newAssignment.iToPlotIndex;

		//do the visibility update first so all newly neighboring plots become part of the sim
		visibilityResult = doVisibilityUpdate(newAssignment);

		//now do the accounting for the neighbor plots
		getTactPlotMutable(newAssignment.iFromPlotIndex)->friendlyUnitMovingOut(*this, newAssignment);
		getTactPlotMutable(newAssignment.iToPlotIndex)->friendlyUnitMovingIn(*this, newAssignment);

		//in case this was a move which revealed new enemies, pretend it was a forced move so we can move again
		if (visibilityResult.second > 0 && newAssignment.eAssignmentType == A_MOVE)
			itUnit->eLastAssignment = A_MOVE_FORCED;

		if (!GET_PLAYER(ePlayer).isBarbarian())
		{
			CvPlot* pFuturePlot = GC.getMap().plotByIndexUnchecked(newAssignment.iToPlotIndex);
			if (pFuturePlot->getRevealedImprovementType(GET_PLAYER(ePlayer).getTeam()) == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT))
			{
				//barbarian camps are counted as a separate enemy
				nKilledEnemies++;
			}
		}
		//aoe damage on move
		for (SUnitIDValueContainer::const_iterator it = newAssignment.unitDamage.begin(); it != newAssignment.unitDamage.end(); ++it)
			ChangeUnitDamage((*it).first, (*it).second);
		if (newAssignment.iDamagedCityId != -1)
			ChangeCityDamage(newAssignment.iDamagedCityId, newAssignment.iCityDamage);
		break;
	}
 case A_RANGEATTACK:
 case A_MELEEATTACK:
 case A_RANGEKILL:
 case A_MELEEKILL_NO_ADVANCE:
 case A_MELEEKILL:
 {
  itUnit->iMovesLeft = newAssignment.iRemainingMoves;
  itUnit->iAttacksLeft--;
  itUnit->iSelfDamage += newAssignment.iSelfDamage;
  for (SUnitIDValueContainer::const_iterator it = newAssignment.unitDamage.begin(); it != newAssignment.unitDamage.end(); ++it)
   ChangeUnitDamage((*it).first, (*it).second);
  if (newAssignment.iDamagedCityId != -1)
   ChangeCityDamage(newAssignment.iDamagedCityId, newAssignment.iCityDamage);

  CvTacticalPlot* target = getTactPlotMutable(newAssignment.iToPlotIndex);
  const bool captureCity = newAssignment.eAssignmentType == A_MELEEKILL && target->isEnemyCity();
  if (captureCity)
  {
   nKilledEnemies += 1 + (int)target->getEnemyUnits().size();
   target->clearCapturedCity();
  }
  // Damage can kill primary or splash victims on any affected plot.
  vector<CvTacticalPlot>& plots = tactPlots.write();
  for (size_t i = 0; i < plots.size(); ++i)
  {
   bool changed = false;
   // Copy the list (removal rewrites it) only for plots where a unit died.
   if (HasKilledEnemyUnit(plots[i]))
   {
    const vector<const CvUnit*> enemies = plots[i].getEnemyUnits();
    for (size_t j = 0; j < enemies.size(); ++j)
     if (GetUnitDamage(enemies[j]->GetID()) >= enemies[j]->GetCurrHitPoints())
     {
      changed |= plots[i].removeEnemyUnitIfPresent(enemies[j]->GetID());
      ++nKilledEnemies;
     }
   }
   if ((changed || (captureCity && plots[i].getPlotIndex() == newAssignment.iToPlotIndex)) && !plots[i].isEnemy())
   {
    const int index = plots[i].getPlotIndex();
    freedPlots.write().push_back(index);
    PlotIndexContainer& enemyPlots_w = enemyPlots.write();
    enemyPlots_w.erase(std::remove(enemyPlots_w.begin(), enemyPlots_w.end(), index), enemyPlots_w.end());
   }
   bRecomputeAllMoves |= changed || captureCity;
  }
  if (newAssignment.eAssignmentType == A_MELEEKILL && !getTactPlot(newAssignment.iToPlotIndex)->isEnemy())
  {
   itUnit->iPlotIndex = newAssignment.iToPlotIndex;
   visibilityResult = doVisibilityUpdate(newAssignment);
   getTactPlotMutable(newAssignment.iFromPlotIndex)->friendlyUnitMovingOut(*this, newAssignment);
   getTactPlotMutable(newAssignment.iToPlotIndex)->friendlyUnitMovingIn(*this, newAssignment);
   if (!captureCity && !GET_PLAYER(ePlayer).isBarbarian() && GC.getMap().plotByIndexUnchecked(newAssignment.iToPlotIndex)->getRevealedImprovementType(GET_PLAYER(ePlayer).getTeam()) == GD_INT_GET(BARBARIAN_CAMP_IMPROVEMENT))
    ++nKilledEnemies;
  }
  if (bRecomputeAllMoves)
   refreshVolatilePlotProperties();
  break;
 }
	case A_PILLAGE:
		itUnit->iMovesLeft = newAssignment.iRemainingMoves;
		if (TacticalAIHelpers::GetOtherPlayerImprovementDamage( GC.getMap().plotByIndexUnchecked(newAssignment.iToPlotIndex), getPlayer(), true) > 0)
			refreshVolatilePlotProperties();
		//aoe damage on pillage
		for (SUnitIDValueContainer::const_iterator it = newAssignment.unitDamage.begin(); it != newAssignment.unitDamage.end(); ++it)
			ChangeUnitDamage((*it).first, (*it).second);
		//aoe heal on pillage
		for (SUnitIDValueContainer::const_iterator it = newAssignment.unitHealing.begin(); it != newAssignment.unitHealing.end(); ++it)
			HealFriendlyUnit((*it).first, (*it).second);
		break;
	case A_USE_POWER:
		itUnit->iMovesLeft = newAssignment.iRemainingMoves;
		bEndOfSim = true;
		//admiral heal
		for (SUnitIDValueContainer::const_iterator it = newAssignment.unitHealing.begin(); it != newAssignment.unitHealing.end(); ++it)
			HealFriendlyUnit((*it).first, (*it).second);
		break;
	case A_FINISH:
		OutputDebugString("this should not happen\n");
	case A_HEAL:
	case A_FINISH_TEMP:
		bEndOfSim = true;
		break;
	case A_BLOCKED:
		bAffectsScore = false;
		bEndOfSim = true;
		break;
	default:
		UNREACHABLE();
	}

 if ((newAssignment.eAssignmentType == A_MOVE || newAssignment.eAssignmentType == A_MOVE_FORCED || newAssignment.eAssignmentType == A_MOVE_SWAP
  || newAssignment.eAssignmentType == A_MOVE_SWAP_REVERSE || newAssignment.eAssignmentType == A_CAPTURE || newAssignment.eAssignmentType == A_PILLAGE)
  && newAssignment.unitDamage.begin() != newAssignment.unitDamage.end())
 {
  vector<CvTacticalPlot>& plots = tactPlots.write();
  for (size_t i = 0; i < plots.size(); ++i)
  {
   bool changed = false;
   if (HasKilledEnemyUnit(plots[i]))
   {
    const vector<const CvUnit*> enemies = plots[i].getEnemyUnits();
    for (size_t j = 0; j < enemies.size(); ++j)
     if (GetUnitDamage(enemies[j]->GetID()) >= enemies[j]->GetCurrHitPoints())
     { changed |= plots[i].removeEnemyUnitIfPresent(enemies[j]->GetID()); ++nKilledEnemies; }
   }
   if (changed && !plots[i].isEnemy())
   {
    const int index = plots[i].getPlotIndex();
    freedPlots.write().push_back(index);
    PlotIndexContainer& enemyPlots_w = enemyPlots.write();
    enemyPlots_w.erase(std::remove(enemyPlots_w.begin(), enemyPlots_w.end(), index), enemyPlots_w.end());
   }
   bRecomputeAllMoves |= changed;
  }
  if (bRecomputeAllMoves)
   refreshVolatilePlotProperties();
 }

	//we update the moveplots lazily because it takes a while and we don't know yet if we will ever follow up on this position
	if (bRecomputeAllMoves)
	{
		movePlotUpdateFlagA = -1;
		movePlotUpdateFlagB = -1;
	}
	else if (itUnit->iMovesLeft>0 && !bEndOfSim)
	{
		//make sure we don't regress to a "lower" level
		if (movePlotUpdateFlagA==0) 
			movePlotUpdateFlagA = itUnit->iUnitID; //need to update only this one
		else if (movePlotUpdateFlagB==0)
			movePlotUpdateFlagB = itUnit->iUnitID; //need to update this one as well
		else
		{
			//need to update more than 2 units, simply do all
			movePlotUpdateFlagA = -1;
			movePlotUpdateFlagB = -1;
		}
	}

	//forced moves don't even affect the score
	if (bAffectsScore)
	{
		//when in doubt, increasing our visibility is good
		//but only for our first line units ... need to be careful with the others
		//(the same clamped arithmetic as AddScore(0, visibility, 0) on a copy, without
		//copying the assignment's damage containers)
		int iBonusScore = newAssignment.GetBonusScore();
		if (newAssignment.iRemainingMoves > 0)
			iBonusScore = STacticalAssignment::ClampShort(iBonusScore + visibilityResult.first);

		UpdateScore(newAssignment.iUnitID, newAssignment.GetPlotScore(), newAssignment.GetOldPlotScore(), newAssignment.GetDamageDelta(), iBonusScore);

	}

	//are we done or can we do further moves with this unit?
	if (itUnit->iMovesLeft == 0 || bEndOfSim)
	{
		//blocked units might still move away
		if (IsCombatUnit(*itUnit))
		{
			CvTacticalPlot::eTactPlotDomain tactDomain = DomainForUnit(itUnit->pUnit);
			CvTacticalPlot* tactPlot = getTactPlotMutable(itUnit->iPlotIndex);
			tactPlot->SetSimUnitBlocking(tactDomain);
			//if the unit is blocked, we won't assume anything about it ending its turn here, but it is blocking our other moves
			if (newAssignment.eAssignmentType != A_BLOCKED)
			{
				CvUnit* pUnit = GET_PLAYER(ePlayer).getUnit(itUnit->iUnitID);
				// Need to check these cases, otherwise the unit can run away!
				if (itUnit->iMovesLeft == 0 || pUnit->isBarbarian() || !pUnit->shouldHeal(false))
					tactPlot->setCombatUnitEndTurn(*this, tactDomain);
			}
		}
		notQuiteFinishedUnits.write().push_back(*itUnit);
		availableUnits_w.erase(itUnit);
	}

	//todo: should we stop the simulation? how to include this in position scoring?
	//don't do restarts if we have a lot of units, the simulation can take very long then
	//also don't do a restart if this was the last unit
	//any new enemies in sight or borders changed?
	bool bCityCapture = (newAssignment.eAssignmentType == A_MELEEKILL && GC.getMap().plotByIndexUnchecked(newAssignment.iToPlotIndex)->isCity());
	bool bRestartRequired = (visibilityResult.second > 0) || bCityCapture;
	if (bRestartRequired && availableUnits_w.size() > 0)
		return RESULT_ADDED_W_VIS_CHANGE;

	return RESULT_ADDED;
}

static bool EqualAssignedUnitValues(const SUnitIDValueContainer& left, const SUnitIDValueContainer& right)
{
 for (SUnitIDValueContainer::const_iterator it = left.begin(); it != left.end(); ++it)
  if (right.GetValue((*it).first) != (*it).second)
   return false;
 for (SUnitIDValueContainer::const_iterator it = right.begin(); it != right.end(); ++it)
  if (left.GetValue((*it).first) != (*it).second)
   return false;
 return true;
}

bool STacticalAssignment::operator==(const STacticalAssignment& rhs) const
{
 return iTotalScore == rhs.iTotalScore &&
  iUnitID == rhs.iUnitID && iFromPlotIndex == rhs.iFromPlotIndex && iToPlotIndex == rhs.iToPlotIndex &&
  iRemainingMoves == rhs.iRemainingMoves && eMoveType == rhs.eMoveType && eAssignmentType == rhs.eAssignmentType &&
  iPrimaryUnitID == rhs.iPrimaryUnitID && ePrimaryUnitOwner == rhs.ePrimaryUnitOwner &&
  iSelfDamage == rhs.iSelfDamage && iCityDamage == rhs.iCityDamage && iDamagedCityId == rhs.iDamagedCityId &&
  EqualAssignedUnitValues(unitDamage, rhs.unitDamage) && EqualAssignedUnitValues(unitHealing, rhs.unitHealing);
}

//do not allow one unit to be present multiple times!
bool SComboMove::addMove(const STacticalAssignment& move)
{
	if (!aPtr)
	{
		aPtr = &move;
		aIsLocal = false;
		return true;
	}
	else if (!bPtr && aPtr->iUnitID != move.iUnitID)
	{
		bPtr = &move;
		bIsLocal = false;
		return true;
	}
	else
	{
		return false;
	}
}

//try to detect whether this new position is equivalent to one we already have
static bool tacticalPositionIsEquivalentToAnyChild(const CvTacticalPosition* ref, const CvTacticalPosition* current)
{
	//go depth first
	const vector<CvTacticalPosition*>& children = current->getChildren();
	for (size_t i = 0; i < children.size(); i++)
	{
		bool bMatch = tacticalPositionIsEquivalentToAnyChild(ref, children[i]);
		if (bMatch)
			return bMatch;
	}

	return positionIsEquivalent(ref, current);
}

bool CvTacticalPosition::isUnique(int levels) const
{
	//go up x levels
	const CvTacticalPosition* start = this;
	while (start->parentPosition && levels > 0)
	{
		start = start->parentPosition;
		levels--;
	}

	//then recurse downwards to all leaves
	return !tacticalPositionIsEquivalentToAnyChild(this, start);
}

struct TacticalPosition_PairCompareFirst
{
	bool operator() (const std::pair<unsigned short, unsigned char>& l, const std::pair<unsigned short, unsigned char>& r) const { return l.first < r.first; }
};

struct TacticalPosition_EqualRangeComparison
{
	bool operator() (const pair<unsigned short, unsigned char>& a, unsigned short b) const { return a.first < b; }
	bool operator() (unsigned short a, const pair<unsigned short, unsigned char>& b) const { return a < b.first; }
};

CvTacticalPlot* CvTacticalPosition::findTactPlotMutable(int iPlotIndex)
{
	if (iPlotIndex >= 0 && iPlotIndex < USHRT_MAX)
	{
		const TactPlotIndexByPlotIndex& tactPlotLookup_r = tactPlotLookup.read();
		TactPlotIndexByPlotIndex::const_iterator it =
			lower_bound(tactPlotLookup_r.begin(), tactPlotLookup_r.end(),
				(unsigned short)iPlotIndex, TacticalPosition_EqualRangeComparison());
		if (it != tactPlotLookup_r.end() && it->first == (unsigned short)iPlotIndex)
			return &tactPlots.write()[it->second];
	}
	return NULL;
}

const CvTacticalPlot* CvTacticalPosition::findTactPlot(int iPlotIndex) const
{
	if (iPlotIndex >= 0 && iPlotIndex < USHRT_MAX)
	{
		const TactPlotIndexByPlotIndex& tactPlotLookup_r = tactPlotLookup.read();
		TactPlotIndexByPlotIndex::const_iterator it =
			lower_bound(tactPlotLookup_r.begin(), tactPlotLookup_r.end(),
				(unsigned short)iPlotIndex, TacticalPosition_EqualRangeComparison());
		if (it != tactPlotLookup_r.end() && it->first == (unsigned short)iPlotIndex)
			return &tactPlots.read()[it->second];
	}
	return NULL;
}

bool CvTacticalPosition::addTacticalPlot(const CvPlot* pPlot, const vector<const CvUnit*>& allOurUnits)
{
	//don't check the official visibility here, we might want to create a tactplot that only became visible during simulation
	if (!pPlot)
		return false;

	//already added?
	if (getTactPlot(pPlot->GetPlotIndex()))
		return false; 

	//cannot process more than this
	if (tactPlots.read().size() == 255)
		return false;

	CvTacticalPlot newPlot(pPlot, ePlayer, allOurUnits);
	if (newPlot.getPlot() != NULL)
	{
		TactPlotIndexByPlotIndex& tactPlotLookup_w = tactPlotLookup.write();
		vector<CvTacticalPlot>& tactPlots_w = tactPlots.write();
		//cast to smaller types to save memmory ...
		TactPlotIndexByPlotIndex::value_type newEntry( (TactPlotIndexByPlotIndex::value_type::first_type)pPlot->GetPlotIndex(), (TactPlotIndexByPlotIndex::value_type::second_type)tactPlots_w.size());
		tactPlotLookup_w.insert(upper_bound(tactPlotLookup_w.begin(), tactPlotLookup_w.end(), newEntry, TacticalPosition_PairCompareFirst()), newEntry);
		tactPlots_w.push_back(newPlot);

#if defined(MOD_CORE_DEBUGGING)
		if (GC.getLogging() && GC.getAILogging() && MOD_CORE_DEBUGGING && iID==1) //log only initial position
		{
			CvString strMsg;
			strMsg.Format("added sim plot (%d:%d), %s, %s",
				pPlot->getX(), pPlot->getY(),
				newPlot.isEnemy() ? "enemy" : (newPlot.isBlockedByNonSimUnit(CvTacticalPlot::TD_BOTH) ? "blocked" : "available"),
				newPlot.isVisibleToEnemy() ? "enemy_can_see" : "enemy_cannot_see"
			);
			GET_PLAYER(ePlayer).GetTacticalAI()->LogTacticalMessage(strMsg);
		}
#endif

		return true;
	}

	return false;
}

bool CvTacticalPosition::addAvailableUnit(const CvUnit* pUnit)
{
	if (!pUnit || !pUnit->canMove() || !pUnit->canEndTurnAtPlot(pUnit->plot()))
		return false;

	eUnitMovementStrategy eStrategy = MS_NONE;

	//ok this is a bit involved
	//case a) we want to fight (enemies around). units should stay in their native domain so they can fight.
	//case b) we don't want to fight (no enemies). units may embark if the target is not their native domain
	//later in updateMoveAndAttackPlotsForUnits we try and filter the reachable plots according to unit strategy
	//also, only land units can embark and but melee ships can move into certain land plots (cities) so it's tricky

	//if were not looking to fight but about to embark then keep the unit away from enemies
	if (!haveEnemies() && !pUnit->isNativeDomain(pTargetPlot) && pUnit->CanEverEmbark() && pUnit->IsCombatUnit())
	{
		eStrategy = MS_EMBARKED;
	}
	else
	{
		//normal combat units
		switch (pUnit->getUnitInfo().GetDefaultUnitAIType())
		{
			//front line units
		case UNITAI_ATTACK:
		case UNITAI_DEFENSE:
		case UNITAI_COUNTER:
		case UNITAI_PARADROP:
		case UNITAI_ATTACK_SEA:
		case UNITAI_RESERVE_SEA:
		case UNITAI_ESCORT_SEA:
		case UNITAI_FAST_ATTACK:
			//ranged units
		case UNITAI_RANGED:
		case UNITAI_CITY_BOMBARD:
		case UNITAI_ASSAULT_SEA:
		case UNITAI_SKIRMISHER:
		case UNITAI_SUBMARINE:
			if (pUnit->GetRange() > 2 || (MOD_AI_UNIT_PRODUCTION && pUnit->canIntercept())) // MOD_AI_UNIT_PRODUCTION : AA to back
				eStrategy = MS_THIRDLINE;
			else if (pUnit->GetRange() == 2)
				eStrategy = MS_SECONDLINE;
			else
			{
				//the unit AI type is unreliable, so we do this manually
				if (pUnit->IsCanAttackRanged() && pUnit->getDomainType() == DOMAIN_SEA && pUnit->maxMoves() > 3 && pUnit->canMoveAfterAttacking())
					eStrategy = MS_THIRDLINE; //very fast units can stay even further back
				else if (pUnit->IsCanAttackRanged() && pUnit->canMoveAfterAttacking() && pUnit->maxMoves() > 2)
					eStrategy = MS_SECONDLINE; //skirmishers are second line always
				else
					eStrategy = MS_FIRSTLINE; //regular melee and slingers
			}
			break;
		//carriers should stay back
		case UNITAI_CARRIER_SEA:
			eStrategy = MS_THIRDLINE;
			break;

		//explorers are an edge case, the visibility can be useful, so include them
		//they shouldn't fight if the odds are bad
		case UNITAI_EXPLORE:
		case UNITAI_EXPLORE_SEA:
			eStrategy = MS_THIRDLINE;
			break;

		//combat support, stay out of danger
		case UNITAI_GENERAL:
			bHasGeneral = true;
			eStrategy = MS_SUPPORT;
			break;
		case UNITAI_ADMIRAL:
			bHasAdmiral = true;
			eStrategy = MS_SUPPORT;
			break;
		case UNITAI_CITY_SPECIAL:
			bHasSiegetower = true;
			eStrategy = MS_SUPPORT;
			break;

		//air units. ignore here, attack / rebase is handled elsewhere
		case UNITAI_ATTACK_AIR:
		case UNITAI_DEFENSE_AIR:
		case UNITAI_MISSILE_AIR:
		case UNITAI_ICBM:
		default:
			//skip the unit (other civilians as well)
			return false;
		}
	}

	// We want to set the properties above, but not actually add them to the combat sim
	if (pUnit->IsGreatGeneral() || pUnit->IsGreatAdmiral() || pUnit->IsSapper())
		return false;

	//careful with damaged units
	if (pUnit->isProjectedToDieNextTurn())
	{
		//do not use for purely defensive moves
		if (!haveEnemies())
			return false;
		//pull back our melee units if they have soaked enough damage, but maybe we can still score a kill!
		if (eStrategy == MS_FIRSTLINE)
			eStrategy = MS_THIRDLINE;
	}

	//we will update the importance later, use 0 for now
	availableUnits.write().push_back(SUnitStats(pUnit, 0, eStrategy));

	//lazy update of move plots later
	movePlotUpdateFlagA = -1; 
	movePlotUpdateFlagB = -1;

#if defined(MOD_CORE_DEBUGGING)
	if (GC.getLogging() && GC.getAILogging() && MOD_CORE_DEBUGGING)
	{
		CvString strMsg;
		strMsg.Format("added sim unit %s, id %d, at (%d:%d), moves %d, damage %d, pathfinder count %d",
			pUnit->getName().c_str(),
			pUnit->GetID(),
			pUnit->getX(),
			pUnit->getY(),
			pUnit->getMoves(),
			pUnit->getDamage(),
			GC.GetPathFinder().GetCurrentGenerationID()
		);
		GET_PLAYER(ePlayer).GetTacticalAI()->LogTacticalMessage(strMsg);
	}
#endif

	return true;
}

static bool IsAttackMove(eUnitAssignmentType eAssignmentType)
{
	return eAssignmentType == A_MELEEATTACK || eAssignmentType == A_MELEEKILL || eAssignmentType == A_MELEEKILL_NO_ADVANCE
		|| eAssignmentType == A_RANGEATTACK || eAssignmentType == A_RANGEKILL;
}

static STacticalAssignment* ScorePlotForSupportMove(const SUnitStats& unit, const CvPlot* pPlot, int iAssumedMovesLeft, const CvSupportPosition& assumedPosition, eUnitMoveEvalMode evalMode, bool bLastPosition)
{
	STacticalAssignment* result = gAssignmentStorage.peekNext();
	result->init(unit.iPlotIndex, pPlot->GetPlotIndex(), unit.iUnitID, iAssumedMovesLeft, unit.eMoveStrategy, A_MOVE, GetPrevPlotScore(unit.iUnitID, assumedPosition));

	int iPlotScore = 0;
	int iBonusScore = 0;
	int iDangerScore = 0;

	const STacticalAssignment& lastTacticalAssignment = assumedPosition.GetTacticalPosition()->getAssignments().back();

	int iLastAttackFromPlotIndex = lastTacticalAssignment.iFromPlotIndex;
	int iLastAttackToPlotIndex = lastTacticalAssignment.iToPlotIndex;

	bool bAttackMove = !bLastPosition || IsAttackMove(lastTacticalAssignment.eAssignmentType);

	CvPlayer& kPlayer = GET_PLAYER(assumedPosition.getPlayer());

	CvUnit* pUnit = kPlayer.getUnit(unit.iUnitID);
	int iEffectRange = pUnit->GetAuraRangeChange() + /*2*/ GD_INT_GET(GREAT_GENERAL_RANGE);
	CvUnit* pAttackingUnit = kPlayer.getUnit(lastTacticalAssignment.iUnitID);
	DomainTypes eAttackerDomain = pAttackingUnit->getDomainType();

	const CvUnit* pDefender = NULL;
	int iDefenderDamage = 0;
	int iDanger = bLastPosition ? assumedPosition.GetUnitDanger(unit, pPlot, pDefender, iDefenderDamage) : 0;
	bool bIsSafe = true;

	if (pDefender)
	{
		int iProjectedDamage = iDanger + pDefender->getDamage() + iDefenderDamage;
		bIsSafe = (iProjectedDamage * 3 <= pDefender->GetMaxHitPoints() * 2);
	}
	else
	{
		bIsSafe = (iDanger == 0);
	}

	if ((iAssumedMovesLeft == 0 || bLastPosition) && !bIsSafe)
		return result;

	DomainTypes eDomain = pUnit->getDomainType();
	bool bInNativeDomain = (eDomain == DOMAIN_LAND && pPlot->getDomain() == DOMAIN_LAND) || eDomain == DOMAIN_SEA;

	if (evalMode == EM_INTERMEDIATE)
	{
		if (unit.iPlotIndex == pPlot->GetPlotIndex())
		{
			if (bLastPosition)
				result->eAssignmentType = A_FINISH_TEMP;
			else
				result->eAssignmentType = A_WAIT;
		}
		else
		{
			// unit may not move twice in a row (if we are in a new position, there was a "wait" assignment before this)
			if (unit.eLastAssignment == A_MOVE)
				return result;
		}

		if (bAttackMove)
		{
			if (pUnit->IsGreatGeneral() || pUnit->IsGreatAdmiral())
			{
				bool bCorrectDomain = bInNativeDomain &&
					((eDomain != DOMAIN_SEA && eAttackerDomain != DOMAIN_SEA)
					|| (eDomain == DOMAIN_SEA && eAttackerDomain == DOMAIN_SEA));
				// if the attack is already receiving a bonus, do nothing (including if it's us giving the bonus)
				bool bWillGiveBonus = bCorrectDomain && !assumedPosition.HasCombatBonus(iLastAttackFromPlotIndex, eDomain) && iEffectRange >= plotDistance(pPlot->GetPlotIndex(), iLastAttackFromPlotIndex);

				if (bWillGiveBonus)
					iBonusScore += (kPlayer.GetGreatGeneralCombatBonus() + kPlayer.GetPlayerTraits()->GetGreatGeneralExtraBonus() + pUnit->GetAuraEffectChange());
				else if (!bLastPosition && result->eAssignmentType != A_WAIT)
					return result;
			}
			else if (pUnit->IsSapper())
			{
				int iBonusDelta = 0;
				if (bInNativeDomain && GC.getMap().plotByIndexUnchecked(iLastAttackToPlotIndex)->isCity())
				{
					int iOldCityAttackBonus = assumedPosition.GetCityAttackBonus(iLastAttackToPlotIndex);

					int iPlotDistance = plotDistance(pPlot->GetPlotIndex(), iLastAttackToPlotIndex);

					int iNewCityAttackBonus = 0;
					if (iPlotDistance <= iEffectRange)
						iNewCityAttackBonus = iEffectRange == iPlotDistance ? 1 : 2;

					iBonusDelta = iNewCityAttackBonus - iOldCityAttackBonus;
				}

				if (iBonusDelta > 0)
					iBonusScore += (/*50 in CP, 40 in VP*/ GD_INT_GET(SAPPED_CITY_ATTACK_MODIFIER) * iBonusDelta) / 2;
				else if (!bLastPosition && result->eAssignmentType != A_WAIT)
					return result;
			}
		}

		// For the final position, do some extra work to figure out if we're well positioned for the end of the turn
		if (bLastPosition)
		{
			const vector<SUnitStats>& finalCombatPositionUnits = assumedPosition.GetFinalCombatPositions();
			const CvPlot* pLoopPlot;
			const CvUnit* pLoopUnit;

			if (bInNativeDomain)
			{
				if (pUnit->IsGreatGeneral() || pUnit->IsGreatAdmiral())
				{
					for (vector<SUnitStats>::const_iterator it = finalCombatPositionUnits.begin(); it != finalCombatPositionUnits.end(); ++it)
					{
						pLoopUnit = kPlayer.getUnit(it->iUnitID);

						if (pUnit->IsGreatGeneral() && (pLoopUnit->getDomainType() == DOMAIN_SEA || pLoopUnit->isEmbarked()))
							continue;

						if (pUnit->IsGreatAdmiral() && pLoopUnit->getDomainType() != DOMAIN_SEA)
							continue;

						pLoopPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);
						int iPlotDistance = plotDistance(*pPlot, *pLoopPlot);

						if (iPlotDistance <= iEffectRange)
						{
							iPlotScore += kPlayer.GetGreatGeneralCombatBonus() + kPlayer.GetPlayerTraits()->GetGreatGeneralExtraBonus() + pUnit->GetAuraEffectChange();
							if (pLoopUnit->IsRequiresLeadership())
								iPlotScore += 50;
						}
					}
				}

				int iSameTileHeal = pUnit->getSameTileHeal();
				int iAdjacentTileHeal = pUnit->getAdjacentTileHeal();

				if (iSameTileHeal > 0 || iAdjacentTileHeal > 0)
				{
					for (vector<SUnitStats>::const_iterator it = finalCombatPositionUnits.begin(); it != finalCombatPositionUnits.end(); ++it)
					{
						pLoopUnit = kPlayer.getUnit(it->iUnitID);
						pLoopPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);

						int iPlotDistance = plotDistance(*pPlot, *pLoopPlot);
						int iBonusHeal = iPlotDistance == 0 ? iSameTileHeal : (iPlotDistance == 1 ? iAdjacentTileHeal : 0);

						if (iBonusHeal == 0)
							continue;

						int iDamage = pLoopUnit->getDamage() + it->iSelfDamage;
						bool bHealing = it->iMovesLeft == pLoopUnit->maxMoves() || pLoopUnit->isAlwaysHeal();

						if (!bHealing || iDamage <= 5)
							continue;

						TeamTypes ePlotTeam = pLoopPlot->getTeam();
						if (ePlotTeam == kPlayer.getTeam())
							iBonusHeal += pUnit->getExtraFriendlyHeal();
						else if (kPlayer.IsAtWarWith(pLoopPlot->getOwner()))
							iBonusHeal += pUnit->getExtraEnemyHeal();
						else
							iBonusHeal += pUnit->getExtraNeutralHeal();

						// TODO real healing numbers?
						iPlotScore += min(iBonusHeal, iDamage - 5) * 4;
					}
				}
			}

			const CvTacticalPlot* finalTactPlot = assumedPosition.GetFinalTacticalPosition()->getTactPlot(pPlot->GetPlotIndex());

			if (!pPlot->isCity())
			{
				if (!pDefender)
				{
					iDangerScore -= min(max(iDanger, pUnit->GetMaxHitPoints() / 3), pUnit->GetMaxHitPoints());
				}
				else
				{
					int iDefenderDamageTotal = iDanger + iDefenderDamage + pDefender->getDamage();
					// if the unit is not close to dying, consider it safe
					if (iDefenderDamageTotal * 3 > pDefender->GetMaxHitPoints() * 2)
					{
						if (iDanger == 0)
							iDefenderDamageTotal /= 3;
						iDangerScore -= iDefenderDamageTotal * pUnit->GetMaxHitPoints() / (pDefender->GetMaxHitPoints() * 3);
					}
				}
			}

			if (finalTactPlot)
			{
				switch (finalTactPlot->getEnemyDistance())
				{
				case 0:
					return result; //don't ever go there, wouldn't work anyway
					break;
				case 1:
					iPlotScore += pPlot->isCity() ? 1 : 0; //dangerous to end the turn, avoid
					break;
				case 2:
					iPlotScore += 1; //good for defense support, good for attack support, but risky
					break;
				case 3:
					iPlotScore += 1; //good for defense support, not so good for attack support
					break;
				default:
					break; //usual case for gathering moves, otherwise not really interesting
				}
			}
		}
	}
	else if (evalMode == EM_FINAL)
	{
		if (bIsSafe)
			result->SetScore(0, 0, 0);

		return result;
	}

	//small bias for staying close to our cities, to have a way to retreat if necessary
	int iCityDistanceScore = 10 - GET_PLAYER(assumedPosition.getPlayer()).GetCityDistanceInPlots(pPlot);
	int iExtra = max(iCityDistanceScore, 0);

	// Stay close to the center of the army
	iExtra -= plotDistance(*assumedPosition.GetCenterOfMass(), *pPlot);

	iExtra += result->iRemainingMoves / GD_INT_GET(MOVE_DENOMINATOR);

	result->SetScore(iPlotScore * 10 + iDangerScore + iExtra, iBonusScore, 0);

	return result;
}

bool CvSupportPosition::HasCombatBonus(int iPlotIndex, DomainTypes eDomain) const
{
	const CvUnit* pUnit;

	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	for (vector<SUnitStats>::const_iterator it = availableUnits_r.begin(); it != availableUnits_r.end(); ++it)
	{
		pUnit = it->pUnit;
		bool bProvidesBuff = (pUnit->IsGreatGeneral() && eDomain != DOMAIN_SEA) || (pUnit->IsGreatAdmiral() && eDomain == DOMAIN_SEA);

		if (!bProvidesBuff)
			continue;

		int iEffectRange = pUnit->GetAuraRangeChange() + /*2*/ GD_INT_GET(GREAT_GENERAL_RANGE);
		if (iEffectRange < plotDistance(iPlotIndex, it->iPlotIndex))
			continue;

		return true;
	}

	const vector<SUnitStats>& notQuiteFinishedUnits_r = notQuiteFinishedUnits.read();
	for (vector<SUnitStats>::const_iterator it = notQuiteFinishedUnits_r.begin(); it != notQuiteFinishedUnits_r.end(); ++it)
	{
		pUnit = it->pUnit;
		bool bProvidesBuff = (pUnit->IsGreatGeneral() && eDomain != DOMAIN_SEA) || (pUnit->IsGreatAdmiral() && eDomain == DOMAIN_SEA);

		if (!bProvidesBuff)
			continue;

		int iEffectRange = pUnit->GetAuraRangeChange() + /*2*/ GD_INT_GET(GREAT_GENERAL_RANGE);
		if (iEffectRange < plotDistance(iPlotIndex, it->iPlotIndex))
			continue;

		return true;
	}

	return false;
}

int CvSupportPosition::GetCityAttackBonus(int iPlotIndex) const
{
	const CvUnit* pUnit;

	int iMaxBuff = 0;

	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	const vector<SUnitStats>& notQuiteFinishedUnits_r = notQuiteFinishedUnits.read();

	for (vector<SUnitStats>::const_iterator it = availableUnits_r.begin(); it != availableUnits_r.end(); ++it)
	{
		pUnit = it->pUnit;

		if (!pUnit->IsSapper())
			continue;

		int iEffectRange = pUnit->GetAuraRangeChange() + /*2*/ GD_INT_GET(GREAT_GENERAL_RANGE);
		int iPlotDist = plotDistance(iPlotIndex, it->iPlotIndex);

		if (iEffectRange < iPlotDist)
			continue;

		iMaxBuff = max(iMaxBuff, iEffectRange == iPlotDist ? 1 : 2);
	}

	for (vector<SUnitStats>::const_iterator it = notQuiteFinishedUnits_r.begin(); it != notQuiteFinishedUnits_r.end(); ++it)
	{
		pUnit = it->pUnit;

		if (!pUnit->IsSapper())
			continue;

		int iEffectRange = pUnit->GetAuraRangeChange() + /*2*/ GD_INT_GET(GREAT_GENERAL_RANGE);
		int iPlotDist = plotDistance(iPlotIndex, it->iPlotIndex);

		if (iEffectRange < iPlotDist)
			continue;

		iMaxBuff = max(iMaxBuff, iEffectRange == iPlotDist ? 1 : 2);
	}

	return iMaxBuff;
}

int CvSupportPosition::GetUnitDanger(const SUnitStats& unit, const CvPlot* pPlot, const CvUnit*& pDefender, int& iDefenderDamage) const
{
	if (!pPlot)
		return INT_MAX;

	if (pPlot->isCity())
	{
		return pPlot->getPlotCity()->isInDangerOfFalling() ? INT_MAX : 0;
	}

	CvUnit* pUnit = GET_PLAYER(ePlayer).getUnit(unit.iUnitID);
	if (!pUnit)
		return INT_MAX;

	const CvTacticalPlot* pTactPlot = finalTacticalPosition->getTactPlot(pPlot->GetPlotIndex());

	if (pTactPlot && pTactPlot->isCombatEndTurn())
	{
		const CvTacticalPlot::UnitList& unitsAtPlot = pTactPlot->getUnitsAtPlot();
		if (!unitsAtPlot.empty())
		{
			for (CvTacticalPlot::UnitList::const_iterator it = unitsAtPlot.begin(); it != unitsAtPlot.end(); ++it)
			{
				int iCoveringUnitId = it->iUnitID;

				const SUnitStats* pCoveringUnitStats = finalTacticalPosition->GetUnitStats(iCoveringUnitId);
				if (!pCoveringUnitStats || !IsCombatUnit(*pCoveringUnitStats))
					continue;

				pDefender = GET_PLAYER(ePlayer).getUnit(iCoveringUnitId);
				iDefenderDamage = pCoveringUnitStats->iSelfDamage;
			}
		}
	}
	if (!pDefender)
	{
		pDefender = pPlot->getBestDefender(ePlayer);
		if (pDefender && !pDefender->TurnProcessed() && pDefender->getMoves() > 0)
			pDefender = NULL;
	}

	if (pDefender)
		return GetUnitDangerForPlot(pDefender, pPlot, iDefenderDamage, *finalTacticalPosition);
	else
		return GetUnitDangerForPlot(pUnit, pPlot, 0, *finalTacticalPosition);
}

void CvSupportPosition::getPreferredAssignmentsForUnit(const SUnitStats& unit, int nMaxCount, bool bLastPosition) const
{
	gPossibleMoves.clear();

	const CvPlot* pAssumedUnitPlot = GC.getMap().plotByIndexUnchecked(unit.iPlotIndex);
	CvUnit* pUnit = GET_PLAYER(getPlayer()).getUnit(unit.iUnitID);
	if (!pUnit || !pAssumedUnitPlot)
		return;

	int iOldPlotDistanceToTarget = GetFinalTacticalPosition()->IsTargetToDistanceRelevant() ? TacticalAIHelpers::GetPlotDistanceToTarget(unit.iPlotIndex, pUnit->getDomainType()) : 0;

	//check moves and melee attacks first
	const ReachablePlots& reachablePlots = getReachablePlotsForUnit(unit);
	for (ReachablePlots::const_iterator it = reachablePlots.begin(); it != reachablePlots.end(); ++it)
	{
		//the plot we're checking right now
		const CvPlot* pTestPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);
		if (!pTestPlot)
			continue;

		int iMoveTowardsTargetScore = 0;

		if (GetFinalTacticalPosition()->IsTargetToDistanceRelevant())
		{
			// Try to move towards the target
			int iNewPlotDistanceToTarget = TacticalAIHelpers::GetPlotDistanceToTarget(it->iPlotIndex, pUnit->getDomainType());
			// INT_MAX means unreachable - can't meaningfully compare distances then
			if (iOldPlotDistanceToTarget != INT_MAX && iNewPlotDistanceToTarget != INT_MAX)
				iMoveTowardsTargetScore = iOldPlotDistanceToTarget - iNewPlotDistanceToTarget;
		}

		STacticalAssignment* moveToPlot = ScorePlotForSupportMove(unit, pTestPlot, it->iMovesLeft, *this, EM_INTERMEDIATE, bLastPosition);

		if (moveToPlot->IsAcceptable())
		{
			moveToPlot->AddScore(iMoveTowardsTargetScore, 0, 0);
			gPossibleMoves.push_back(OptionWithScore<STacticalAssignment*>(moveToPlot, moveToPlot->Score()));
			gAssignmentStorage.consumeOne();
		}
	}

	//need to return in sorted order. note that we don't filter out bad (negative moves) they just are unlikely to get picked
	std::stable_sort(gPossibleMoves.begin(), gPossibleMoves.end());

	//don't return more than requested unless there is a tie
	if (gPossibleMoves.size() > (size_t)nMaxCount)
	{
		while (gPossibleMoves[nMaxCount].score == gPossibleMoves[nMaxCount - 1].score && (size_t)nMaxCount < gPossibleMoves.size())
			nMaxCount++;

		gPossibleMoves.erase(gPossibleMoves.begin() + nMaxCount, gPossibleMoves.end());
	}
}

bool CvSupportPosition::addInitialAssignments()
{
	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	for (vector<SUnitStats>::const_iterator itUnit = availableUnits_r.begin(); itUnit != availableUnits_r.end(); ++itUnit)
	{
		CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(itUnit->iPlotIndex);
		// Check if there's a valid move
		STacticalAssignment eInitialAssignmentNoMoves = *ScorePlotForSupportMove(*itUnit, pPlot, 0, *this, EM_INITIAL, false);
		eInitialAssignmentNoMoves.iRemainingMoves = itUnit->iMovesLeft;
		eInitialAssignmentNoMoves.eAssignmentType = A_INITIAL;
		addAssignment(eInitialAssignmentNoMoves, NULL);
	}
	return true;
}

bool CvSupportPosition::makeNextAssignments(int iMaxBranches, int iMaxChoicesPerUnit, CvSupportPosStorage& storage,
	vector<CvSupportPosition*>& openPositionsHeap, vector<CvSupportPosition*>& completedPositions, const PrPositionSortHeapGeneration& heapSort,
	const map<const CvTacticalPosition*, const CvTacticalPosition*> nextAttackPosition)
{
	/*
	abstract:
	get preferred plots for all combat units
	choose M best overall moves (combine as far as possible)
	create child positions
		assign moves
		update affected tact plots
		update unit reachable plots
	*/

	//very important, lazy update
	updateMovePlotsIfRequired();

	// Is this the final tactical position, if so, just try to find the best plot to go to to prepare for the next turn
	map<const CvTacticalPosition*, const CvTacticalPosition*>::const_iterator nextPosIt = nextAttackPosition.find(tacticalPosition);
	bool bLastPosition = nextPosIt->second == NULL;

	gOverAllChoices.clear();
	gAssignmentStorage.reset(false);
	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	for (size_t i = 0; i < availableUnits_r.size(); i++)
	{
		getPreferredAssignmentsForUnit(availableUnits_r[i], iMaxChoicesPerUnit, bLastPosition);
		gOverAllChoices.insert(gOverAllChoices.end(), gPossibleMoves.begin(), gPossibleMoves.end());
	}

	//important that moves are ordered by quality instead of unit id
	std::stable_sort(gOverAllChoices.begin(), gOverAllChoices.end());

	for (size_t i = 0; i < gOverAllChoices.size(); i++)
	{
		//we need memory for the new child but we'll commit it only later after the uniqueness check
		CvSupportPosition* pNewChild = storage.peekNext();
		if (!pNewChild)
			break;

		//important, hook it up to the parent so we can access the history
		addChild(pNewChild);
		gCheckedPositions++;

		pNewChild->initFromParent(*this);

		AddAssignmentResult assignmentResult = pNewChild->addAssignment(*gOverAllChoices[i].option, nextPosIt->second);

		//cannot add a RESTART in the middle of a combo move for consistency, so add afterwards
		if (assignmentResult == RESULT_ADDED_W_VIS_CHANGE)
		{
			STacticalAssignment restart;
			restart.init(-1, -1, gOverAllChoices[i].option->iUnitID, 0, gOverAllChoices[i].option->eMoveType, A_RESTART, GetPrevPlotScore(gOverAllChoices[i].option->iUnitID, *this));
			restart.SetScore(0, 0, 0);
			pNewChild->assignedMoves.write().push_back(restart);
		}

		//try to detect duplicates ...
		bool isConsistent = assignmentResult != RESULT_NOT_ADDED;
		if (isConsistent && pNewChild->isUnique(TACTSIM_UNIQUENESS_CHECK_GENERATIONS))
		{
			//do we need to keep working on this one?
			if (pNewChild->isExhausted())
			{
				if (pNewChild->addFinishMovesIfAcceptable())
				{
					//good case, we're done
					completedPositions.push_back(pNewChild);
					giValidEndPos++;
					storage.consumeOne();
				}
				else
				{
					//position is illegal, do not remember it so we can re-use the memory
					giInvalidEndPos++;
					removeChild(pNewChild);
				}
			}
			else
			{
				//also good case, keep this for the next round
				openPositionsHeap.push_back(pNewChild);
				push_heap(openPositionsHeap.begin(), openPositionsHeap.end(), heapSort);
				storage.consumeOne();
			}
		}
		else
			removeChild(pNewChild);

		if (childPositions.size() >= (size_t)iMaxBranches)
			break;
	}

	//can happen we have no children if all were considered redundant or invalid
	//note that we also considered blocked moves for all children, but those also may turn out to be invalid if the unit doesn't have enough moves to flee 
	return !childPositions.empty();
}

//lazy update of move plots
void CvSupportPosition::updateMovePlotsIfRequired()
{
	const vector<SUnitStats>& availableUnits_r = availableUnits.read();
	if (movePlotUpdateFlagA == -1 && movePlotUpdateFlagB == -1)
	{
		for (vector<SUnitStats>::const_iterator itUnit = availableUnits_r.begin(); itUnit != availableUnits_r.end(); ++itUnit)
			updateMovePlotsForUnit(*itUnit);
	}
	else
	{
		for (vector<SUnitStats>::const_iterator itUnit = availableUnits_r.begin(); itUnit != availableUnits_r.end(); ++itUnit)
			if (itUnit->iUnitID == movePlotUpdateFlagA || itUnit->iUnitID == movePlotUpdateFlagB)
				updateMovePlotsForUnit(*itUnit);
	}

	movePlotUpdateFlagA = 0;
	movePlotUpdateFlagB = 0;
}

//see if all the plots where our units would end their turn are acceptable
//this is a deferred check because in the beginning it's not clear how many enemy units we can eliminate
bool CvSupportPosition::addFinishMovesIfAcceptable()
{
	const vector<SUnitStats>& notQuiteFinishedUnits_r = notQuiteFinishedUnits.read();
	//only units which have exhausted their moves are in this array! if the sim was aborted, somebody else will hopefully pick up the pieces
	for (size_t i = 0; i < notQuiteFinishedUnits_r.size(); i++)
	{
		const SUnitStats& unit = notQuiteFinishedUnits_r[i];
		const STacticalAssignment* pInitial = getInitialAssignment(unit.iUnitID);
		if (!pInitial)
			return false; //something wrong

		//if the unit is blocked but has movement left and can flee, let's assume that is ok
		if (unit.eLastAssignment == A_BLOCKED && unit.iMovesLeft > 0)
			continue;

		//make sure we don't leave a unit in an impossible position
		const CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(unit.iPlotIndex);
		STacticalAssignment* nextAssignment = ScorePlotForSupportMove(unit, pPlot, 0, *this, EM_FINAL, true);

		if (nextAssignment->IsAcceptable())
		{
			//if the score is acceptable, end their turn. unless the unit is blocked, then we may use them for other tasks
			if (unit.eLastAssignment != A_BLOCKED)
			{
				nextAssignment->iRemainingMoves = unit.iMovesLeft;
				nextAssignment->eAssignmentType = A_FINISH;
				assignedMoves.write().push_back(*nextAssignment);
			}
		}
		else
		{
			return false;
		}
	}

	vector<SUnitStats>& finishedUnits_w = finishedUnits.write();
	finishedUnits_w.insert(finishedUnits_w.end(), notQuiteFinishedUnits_r.begin(), notQuiteFinishedUnits_r.end());
	notQuiteFinishedUnits.write().clear();

	return true;
}

//need a default constructor for stl containers ...
CvSupportPosition::CvSupportPosition()
{
	ePlayer = NO_PLAYER;
	nFirstInterestingAssignment = 0;
	iBonusScore = 0;
	iDamageDelta = 0;
	iScoreOverParent = 0;
	parentPosition = NULL;
	tacticalPosition = NULL;
	finalTacticalPosition = NULL;
	iGeneration = 0;
	iID = 1; //zero doesn't work here
	movePlotUpdateFlagA = 0;
	movePlotUpdateFlagB = 0;
	iWaitingUnits = 0;

	iLastFromAttackPlotIndex = -1;
	iLastToAttackPlotIndex = -1;

	childPositions.clear();
	assignedMoves.clear();
	availableUnits.clear();
	freedPlots.clear();
	availableUnits.clear();
	notQuiteFinishedUnits.clear();
	finishedUnits.clear();
	finalCombatPositionUnits.clear();
	plotScores.clear();

	pCenterOfMass = NULL;
}

static const CvPlot* CalculateCenterOfMass(const vector<SUnitStats>& positions)
{
	if (positions.empty())
		return NULL;

	int iTotalX = 0;
	int iTotalY = 0;

	int iTotalX2 = 0;
	int iTotalY2 = 0;
	int iWorldWidth = GC.getMap().getGridWidth();
	int iWorldHeight = GC.getMap().getGridHeight();

	//the first unit is our reference ...

	CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(positions.front().iPlotIndex);

	int iRefX = pPlot->getX();
	int iRefY = pPlot->getY();

	for (vector<SUnitStats>::const_iterator it = positions.begin() + 1; it != positions.end(); ++it)
	{
		pPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);
		int iDX = pPlot->getX() - iRefX;
		int iDY = pPlot->getY() - iRefY;

		if (GC.getMap().isWrapX())
		{
			if (iDX > +(iWorldWidth / 2))
				iDX -= iWorldWidth;
			if (iDX < -(iWorldWidth / 2))
				iDX += iWorldWidth;
		}
		if (GC.getMap().isWrapY())
		{
			if (iDY > +(iWorldHeight / 2))
				iDY -= iWorldHeight;
			if (iDY < -(iWorldHeight / 2))
				iDY += iWorldHeight;
		}

		iTotalX += iDX;
		iTotalY += iDY;
		iTotalX2 += iDX * iDX;
		iTotalY2 += iDY * iDY;
	}

	//finally, compute average
	float fNUnits = (float)positions.size();
	float fAvgX = (iTotalX / fNUnits) + iRefX;
	float fAvgY = (iTotalY / fNUnits) + iRefY;

	//rounding to nearest integer
	int iAvgX = fAvgX > 0 ? int(fAvgX + 0.5f) : int(fAvgX - 0.5f);
	int iAvgY = fAvgY > 0 ? int(fAvgY + 0.5f) : int(fAvgY - 0.5f);

	//this handles wrapped coordinates
	CvPlot* pCOM = GC.getMap().plot(iAvgX, iAvgY);
	if (!pCOM)
		return NULL;

	return pCOM;
}

void CvSupportPosition::initFromTacticalPosition(const CvTacticalPosition& tactPos, const CvTacticalPosition& finalTactPos, const vector<const CvUnit*>& ourUnits)
{
	ePlayer = tactPos.getPlayer();
	nFirstInterestingAssignment = 0;
	iBonusScore = 0;
	iDamageDelta = 0;
	iScoreOverParent = 0;
	parentPosition = NULL;
	tacticalPosition = &tactPos;
	finalTacticalPosition = &finalTactPos;
	iGeneration = 0;
	iID = 1; //zero doesn't work here
	movePlotUpdateFlagA = -1;
	movePlotUpdateFlagB = -1;
	bHasGeneral = false;
	bHasAdmiral = false;
	bHasSiegetower = false;

	iLastFromAttackPlotIndex = tactPos.getAssignments().back().iFromPlotIndex;
	iLastToAttackPlotIndex = tactPos.getAssignments().back().iToPlotIndex;

	childPositions.clear();
	assignedMoves.clear();
	availableUnits.clear();
	notQuiteFinishedUnits.clear();
	finishedUnits.clear();
	finalCombatPositionUnits.clear();
	plotScores.clear();

	freedPlots.inheritFrom(tactPos.getFreedPlots());

	vector<SUnitStats>& finalCombatPositionUnits_w = finalCombatPositionUnits.write();
	finalCombatPositionUnits_w.clear();

	for (vector<const CvUnit*>::const_iterator it = ourUnits.begin(); it != ourUnits.end(); ++it)
	{
		const CvUnit* pUnit = *it;

		const STacticalAssignment* lastAssignment = finalTacticalPosition->getLatestMoveAssignment(pUnit->GetID());
		if (!AddAvailableUnit(pUnit) && pUnit->IsCombatUnit())
		{
			int iPlotIndex = lastAssignment ? lastAssignment->iToPlotIndex : pUnit->plot()->GetPlotIndex();
			finalCombatPositionUnits_w.push_back(SUnitStats(pUnit, pUnit->GetID(), iPlotIndex, 0, 0, 0, MS_NONE));
		}
	}

	pCenterOfMass = CalculateCenterOfMass(finalCombatPositionUnits_w);
}

void CvSupportPosition::UpdateTacticalPosition(const CvTacticalPosition& tactPos)
{
	tacticalPosition = &tactPos;
	iLastFromAttackPlotIndex = tactPos.getAssignments().back().iFromPlotIndex;
	iLastToAttackPlotIndex = tactPos.getAssignments().back().iToPlotIndex;
}

void CvSupportPosition::initFromParent(const CvSupportPosition& parent)
{
	ePlayer = parent.ePlayer;
	nFirstInterestingAssignment = parent.nFirstInterestingAssignment;
	iBonusScore = parent.iBonusScore;
	iDamageDelta = parent.iDamageDelta;
	iScoreOverParent = 0;
	parentPosition = &parent;
	tacticalPosition = parent.tacticalPosition;
	finalTacticalPosition = parent.finalTacticalPosition;
	movePlotUpdateFlagA = parent.movePlotUpdateFlagA;
	movePlotUpdateFlagB = parent.movePlotUpdateFlagB;
	bHasGeneral = parent.bHasGeneral;
	bHasAdmiral = parent.bHasAdmiral;
	bHasSiegetower = parent.bHasSiegetower;
	iLastFromAttackPlotIndex = parent.iLastFromAttackPlotIndex;
	iLastToAttackPlotIndex = parent.iLastToAttackPlotIndex;
	iGeneration = parent.iGeneration + 1;
	pCenterOfMass = parent.pCenterOfMass;
	iWaitingUnits = parent.iWaitingUnits;

	//clever scheme to encode the tree structure into IDs
	//works only if the tree is not too wide or too deep
	if (parent.getID() < ULLONG_MAX / 10 - 10)
		iID = parent.getID() * 10 + parent.childPositions.size();
	else
		iID = ULLONG_MAX;

	//childPositions stays empty!
	childPositions.clear();

	//copied from parent, modified when addAssignment is called
	assignedMoves.inheritFrom(parent.assignedMoves.read());
	availableUnits.inheritFrom(parent.availableUnits.read());
	notQuiteFinishedUnits.inheritFrom(parent.notQuiteFinishedUnits.read());
	finishedUnits.inheritFrom(parent.finishedUnits.read());
	freedPlots.inheritFrom(parent.freedPlots.read());
	finalCombatPositionUnits.inheritFrom(parent.finalCombatPositionUnits.read());
	plotScores.inheritFrom(parent.plotScores.read());
}

bool CvSupportPosition::removeChild(CvSupportPosition* pChild)
{
	//just unlink the child - do not delete it, the memory is allocated statically
	vector<CvSupportPosition*>::iterator it = find(childPositions.begin(), childPositions.end(), pChild);
	if (it != childPositions.end())
		childPositions.erase(it);

	return false;
}

size_t CvSupportPosition::addChild(CvSupportPosition* pChild)
{
	if (pChild)
	{
		childPositions.push_back(pChild); //this order is better for generating an ID for the child
		pChild->initFromParent(*this);
	}
	return childPositions.size();
}

void CvSupportPosition::updateMovePlotsForUnit(SUnitStats unit)
{
	CvUnit* pUnit = GET_PLAYER(ePlayer).getUnit(unit.iUnitID);
	CvPlot* pStartPlot = GC.getMap().plotByIndexUnchecked(unit.iPlotIndex);

	const PlotIndexContainer& freedPlots_r = freedPlots.read();

	TCachedMovePlots::const_iterator itP = gReachablePlotsLookup.find(SPathFinderStartPos(unit, freedPlots_r, SPathFinderStartPos::LookupOnly()));
	if (itP != gReachablePlotsLookup.end())
	{
		gMovePlotsCacheHit++;
	}
	else
	{
		gMovePlotsCacheMiss++;

		//note: we allow (intermediate) embarkation here but filter out the non-native plots later (useful for denmark and lategame)
		int iMoveFlags = CvUnit::MOVEFLAG_IGNORE_STACKING_SELF | CvUnit::MOVEFLAG_IGNORE_DANGER;
		ReachablePlots reachablePlots = TacticalAIHelpers::GetAllPlotsInReachThisTurn(pUnit, pStartPlot, iMoveFlags, 0, unit.iMovesLeft, freedPlots_r);

		//try to save some memory here
		ReachablePlots reachablePlotsPruned;
		for (ReachablePlots::const_iterator it = reachablePlots.begin(); it != reachablePlots.end(); ++it)
		{
			CvPlot* pPlot = GC.getMap().plotByIndexUnchecked(it->iPlotIndex);

			//note that if the unit is far away, it won't have any good plots and will be considered blocked
			//this is just a rough check, we check the existance of a corresponding tact plot below
			//+2 is due to the "maneuver space" around each enemy
			if (TacticalAIHelpers::GetPlotDistanceToTarget(it->iPlotIndex, pUnit->getDomainType()) > TACTICAL_COMBAT_MAX_TARGET_DISTANCE + 2)
				continue;

			//this is a performance fix / logic simplification
			//all open positions share just one instance of gSafePlotCount
			//we only update the count once at the start of the sim
			//if there is no safe plot then, there will never be one!
			if (!parentPosition)
			{
				bool bIsSafe = GET_PLAYER(ePlayer).GetPlotDanger(*pPlot, pUnit, SUnitIDValueContainer(), 0) < pUnit->GetCurrHitPoints();
				if (bIsSafe && pUnit->canEndTurnAtPlot(pPlot))
					gSafePlotCount[unit.iUnitID]++;
			}

			//last (expensive) check, need to have a tact plot for each reachable plot
			reachablePlotsPruned.insertNoIndex(*it);
		}

		reachablePlotsPruned.createIndex();
		gReachablePlotsLookup[SPathFinderStartPos(unit, freedPlots_r)] = reachablePlotsPruned;
	}
}

static bool supportPositionIsEquivalentToAnyChild(const CvSupportPosition* ref, const CvSupportPosition* current)
{
	//go depth first
	const vector<CvSupportPosition*>& children = current->getChildren();
	for (size_t i = 0; i < children.size(); i++)
	{
		bool bMatch = supportPositionIsEquivalentToAnyChild(ref, children[i]);
		if (bMatch)
			return bMatch;
	}

	return positionIsEquivalent(ref->GetTacticalPosition(), current->GetTacticalPosition()) && positionIsEquivalent(ref, current);
}

bool CvSupportPosition::isUnique(int levels) const
{
	//go up x levels
	const CvSupportPosition* start = this;
	while (start->parentPosition && levels > 0)
	{
		start = start->parentPosition;
		levels--;
	}

	//then recurse downwards to all leaves
	return !supportPositionIsEquivalentToAnyChild(this, start);
}

CvSupportPosition::AddAssignmentResult CvSupportPosition::addAssignment(const STacticalAssignment& newAssignment, const CvTacticalPosition* nextTacticalPosition)
{
	vector<SUnitStats>& availableUnits_w = availableUnits.write();
	vector<SUnitStats>::iterator itUnit = find_if(availableUnits_w.begin(), availableUnits_w.end(), PrMatchingUnit(newAssignment.iUnitID));

	if (itUnit == availableUnits_w.end() || itUnit->iPlotIndex != newAssignment.iFromPlotIndex)
		return RESULT_NOT_ADDED;

	//i know what you did last summer!
	itUnit->eLastAssignment = newAssignment.eAssignmentType;

	//store the assignment
	assignedMoves.write().push_back(newAssignment);

	//now deal with the consequences
	bool bAffectsScore = true;
	bool bEndOfSim = false;
	bool bNoMove = false;
	switch (newAssignment.eAssignmentType)
	{
	case A_INITIAL:
		bAffectsScore = false;
		break;
	case A_MOVE:
	{
		itUnit->iMovesLeft = newAssignment.iRemainingMoves;
		itUnit->iPlotIndex = newAssignment.iToPlotIndex;
		break;
	}
	case A_USE_POWER:
		itUnit->iMovesLeft = newAssignment.iRemainingMoves;
		bEndOfSim = true;
		break;
	case A_FINISH:
		OutputDebugString("this should not happen\n");
	case A_HEAL:
	case A_FINISH_TEMP:
		bEndOfSim = true;
		break;
	case A_BLOCKED:
		bAffectsScore = false;
		bEndOfSim = true;
		break;
	case A_WAIT:
		bNoMove = true;
		bAffectsScore = false;
		iWaitingUnits++;
		if (iWaitingUnits == GetNumAvailableUnits())
		{
			iWaitingUnits = 0;
			if (nextTacticalPosition)
				UpdateTacticalPosition(*nextTacticalPosition);
		}
		break;
	default:
		UNREACHABLE();
	}

	//we update the moveplots lazily because it takes a while and we don't know yet if we will ever follow up on this position
	if (itUnit->iMovesLeft > 0 && !bEndOfSim && !bNoMove)
	{
		//make sure we don't regress to a "lower" level
		if (movePlotUpdateFlagA == 0)
			movePlotUpdateFlagA = itUnit->iUnitID; //need to update only this one
		else if (movePlotUpdateFlagB == 0)
			movePlotUpdateFlagB = itUnit->iUnitID; //need to update this one as well
		else
		{
			//need to update more than 2 units, simply do all
			movePlotUpdateFlagA = -1;
			movePlotUpdateFlagB = -1;
		}
	}

	//forced moves don't even affect the score
	if (bAffectsScore)
	{
		UpdateScore(newAssignment);
	}

	//are we done or can we do further moves with this unit?
	if (itUnit->iMovesLeft == 0 || bEndOfSim)
	{
		notQuiteFinishedUnits.write().push_back(*itUnit);
		availableUnits.write().erase(itUnit);
	}

	return RESULT_ADDED;
}

bool CvSupportPosition::AddAvailableUnit(const CvUnit* pUnit)
{
	if (!pUnit || !pUnit->canMove() || !pUnit->canEndTurnAtPlot(pUnit->plot()))
		return false;

	if (!pUnit->IsGreatGeneral() && !pUnit->IsGreatAdmiral() && !pUnit->IsSapper())
		return false;

	if (pUnit->IsGreatGeneral())
	{
		if (bHasGeneral)
			return false;
		else
			bHasGeneral = true;
	}

	if (pUnit->IsGreatAdmiral())
	{
		if (bHasAdmiral)
			return false;
		else
			bHasAdmiral = true;
	}

	if (pUnit->IsSapper())
	{
		if (bHasSiegetower)
			return false;
		else
			bHasSiegetower = true;
	}

	availableUnits.write().push_back(SUnitStats(pUnit, 0, MS_SUPPORT));

	//lazy update of move plots later
	movePlotUpdateFlagA = -1;
	movePlotUpdateFlagB = -1;

	return true;
}

int CvTacticalPosition::countChildren() const
{
	int iCount = (int)childPositions.size();
	for (size_t i = 0; i < childPositions.size(); i++)
		iCount += childPositions[i]->countChildren();

	return iCount;
}

float CvTacticalPosition::getAggressionBias() const
{
	//avoid extreme ratios, use the sqrt
	float fUnitNumberRatio = sqrtf(nOurOriginalUnits / float(max(1,(int)nOriginalEnemies)));
	return max( 0.9f, fUnitNumberRatio ); //<1 indicates we're fewer but don't stop attacking because of that
}

//this is intended to filter out the no-chance-in-hell moves
//it's not intended to be the final check, the situation can still change as the sim progresses
bool CvTacticalPosition::canProbablyEndTurnAfterAssignment(const SUnitStats& unit, const CvTacticalPlot* assumedUnitPlot, eUnitAssignmentType eAssignmentType) const
{
	const CvUnit* pUnit = unit.pUnit;
	if (!pUnit || !assumedUnitPlot)
		return false;

	if (pUnit->IsCanDefend())
	{
		//if we have nowhere to flee to, we can just as well stay?
		if (gSafePlotCount[unit.iUnitID] == 0)
			return true;

		int iDanger = GetUnitDangerForPlot(pUnit, assumedUnitPlot->getPlot(), unit.iSelfDamage, *this);

		iDanger /= max(1, (int)getAggressionLevel());

		return ScoreCombatUnitTurnEnd(pUnit, eAssignmentType, assumedUnitPlot, iDanger, CvTacticalPlot::TD_BOTH,
			unit.iSelfDamage, *this, EM_FINAL, availableUnits.read().size() > 1, true) != INT_MAX;
	}
	else
		//civilians need cover. full scoring logic in ScorePlotForNonFightingUnitMove is more complex; here we just need a rule of thumb
		return assumedUnitPlot->isCombatEndTurn();
}

std::ostream& operator<<(ostream& os, const CvPlot& p)
{
    os << "(" << p.getX() << "," << p.getY() << ")";
    return os;
}

ostream& operator << (ostream& out, const STacticalAssignment& arg)
{
	const char* eType = assignmentTypeNames[arg.eAssignmentType];
	//CvPlot* pFromPlot = GC.getMap().plotByIndexUnchecked( arg.iFromPlotIndex );
	//CvPlot* pToPlot = GC.getMap().plotByIndexUnchecked( arg.iToPlotIndex );
	out << arg.iUnitID << " " << eType << " from " << arg.iFromPlotIndex << " to " << arg.iToPlotIndex << " (" << arg.Score() << ")";
	return out;
}

void CvTacticalPosition::dumpChildren(ofstream& out) const
{
	out << "n" << (void*)this << " [ label = \"id " << (void*)this << ": score " << getScoreTotal() << ", " << GetNumAvailableUnits() << " units\" ";
	if (isEarlyFinish() || isExhausted())
		out << " shape=box ";
	out << "];\n";

	size_t nAssignments = assignedMoves.read().size();
	for (size_t i = 0; i < childPositions.size(); i++)
	{
		out << "n" << (void*)this << " -> n" << (void*)childPositions[i] << " [ label = \"";

		size_t nAssignmentsChild = childPositions[i]->getAssignments().size();
		for (size_t j = nAssignments; j < nAssignmentsChild; j++)
		{
			const STacticalAssignment& assignment = childPositions[i]->getAssignments()[j];
			CvUnit* pUnit = GET_PLAYER(ePlayer).getUnit(assignment.iUnitID);
			out << pUnit->getName().c_str() << " " << assignment << "\\n";
		}
		out << "\" color=blue ];\n";
	}

	for (size_t i = 0; i < childPositions.size(); i++)
		childPositions[i]->dumpChildren(out);
}

void CvTacticalPosition::dumpPlotStatus(const char* fname) const
{
	ofstream out(fname);
	if (out)
	{
		const vector<CvTacticalPlot>& tactPlots_r = tactPlots.read();
		out << "#x,y,terrain,owner,isEnemy,isFriendly,nAdjEnemy,nAdjFriendly,nAdjFirstline,isEdge,iEnemyDist\n"; 
		for (vector<CvTacticalPlot>::const_iterator it = tactPlots_r.begin(); it != tactPlots_r.end(); ++it)
		{
			CvPlot* pPlot =  GC.getMap().plotByIndexUnchecked( it->getPlotIndex() );
			out << pPlot->getX() << "," << pPlot->getY() << "," << pPlot->getTerrainType() << "," << pPlot->getOwner() << "," << (it->isEnemy() ? 1 : 0) << "," << (it->hasFriendlyCombatUnit() ? 1 : 0) << "," 
				<< it->getNumAdjacentEnemies(CvTacticalPlot::TD_BOTH) << "," << it->getNumAdjacentFriendlies(CvTacticalPlot::TD_BOTH,-1) << "," << it->getNumAdjacentFriendliesEndTurn(CvTacticalPlot::TD_BOTH) << "," 
				<< (it->isEdgePlot() ? 1 : 0) << "," << (int)(it->getEnemyDistance()) << "\n";
		}
	}
	out.close();
}

void CvTacticalPosition::exportToDotFile(const char* fname) const
{
	std::ofstream out;
	out.open(fname);
	if (out)
	{
		out << "digraph tacticalmoves {\n";
		dumpChildren(out);
		out << "}\n";
	}
	out.close();
}

//warning: only keep the reference returned around if you know what you are doing!
//it may get invalidated by additional calls to this function!
CvTacticalPlot* CvTacticalPosition::getTactPlotMutable(int plotindex)
{
	return findTactPlotMutable(plotindex);
}

const CvTacticalPlot* CvTacticalPosition::getTactPlot(int plotindex) const
{
	return findTactPlot(plotindex);
}

int CvTacticalPosition::GetUnitDamage(int iUnitID) const
{
	return unitDamageDealt.read().GetValue(iUnitID);
}

int CvTacticalPosition::GetCityDamage(int iCityID) const
{
	return unitDamageDealt.read().GetValue(-iCityID);
}

void CvTacticalPosition::ChangeUnitDamage(int iUnitID, int iChange)
{
 ObserveKernelStateMutation(this,parentPosition); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
	unitDamageDealt.write().ChangeValue(iUnitID, iChange);
}
void CvTacticalPosition::ChangeCityDamage(int iCityID, int iChange)
{
 ObserveKernelStateMutation(this,parentPosition); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
	unitDamageDealt.write().ChangeValue(-iCityID, iChange);
}

void CvTacticalPosition::HealFriendlyUnit(int iUnitID, int iChange)
{
 ObserveKernelStateMutation(this,parentPosition); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
	vector<SUnitStats>& availableUnits_w = availableUnits.write();
	vector<SUnitStats>::iterator it = find_if(availableUnits_w.begin(), availableUnits_w.end(), PrMatchingUnit(iUnitID));
	if (it != availableUnits_w.end())
		it->iSelfDamage -= iChange;
}

// Summary-only execution evidence. Basic state/signatures deliberately omit
// terrain, visibility, other units and policy state: equality is not a proof
// that two tactical searches have identical inputs, and never drives gameplay.
struct StackPlanDiagnosticUnitState
{
	int values[21];
};

static StackPlanDiagnosticUnitState ReadStackPlanDiagnosticUnitState(const CvUnit* unit)
{
	StackPlanDiagnosticUnitState result;
	for (size_t i=0;i<21;++i) result.values[i]=-1;
	result.values[0]=unit?1:0;
	if (!unit) return result;
	result.values[1]=unit->getOwner();result.values[2]=unit->GetID();
	result.values[3]=unit->plot()?unit->plot()->GetPlotIndex():-1;
	result.values[4]=unit->getMoves();result.values[5]=unit->GetCurrHitPoints();result.values[6]=unit->GetMaxHitPoints();
	result.values[7]=unit->getNumAttacksMadeThisTurn();result.values[8]=unit->getNumAttacks();
	result.values[9]=unit->TurnProcessed()?1:0;result.values[10]=unit->GetActivityType();
	result.values[11]=unit->GetMissionTimer();result.values[12]=unit->GetLengthMissionQueue();
	result.values[13]=unit->GetMissionAIType();
	const MissionData* mission=unit->GetHeadMissionData();
	if (mission)
	{
		result.values[14]=mission->eMissionType;result.values[15]=mission->iData1;result.values[16]=mission->iData2;
		result.values[17]=mission->iFlags;result.values[18]=mission->iPushTurn;
	}
	result.values[19]=unit->getArmyID();result.values[20]=unit->isEmbarked()?1:0;
	return result;
}

static void AddStackPlanDiagnosticHash(unsigned __int64& hash,int value)
{
	unsigned int bits=(unsigned int)value;
	for (unsigned int i=0;i<4;++i) { hash^=(bits&255);hash*=1099511628211ULL;bits>>=8; }
}

static unsigned __int64 StackPlanDiagnosticInputHash(PlayerTypes owner,const vector<int>& ids)
{
	unsigned __int64 hash=14695981039346656037ULL;
	AddStackPlanDiagnosticHash(hash,(int)ids.size());
	for (size_t i=0;i<ids.size();++i)
	{
		AddStackPlanDiagnosticHash(hash,ids[i]);
		const StackPlanDiagnosticUnitState state=ReadStackPlanDiagnosticUnitState(GET_PLAYER(owner).getUnit(ids[i]));
		for (size_t field=0;field<21;++field) AddStackPlanDiagnosticHash(hash,state.values[field]);
	}
	return hash;
}

class StackPlanRetryDiagnostic
{
public:
	StackPlanRetryDiagnostic(PlayerTypes owner_,const CvPlot* target_,int batch_,int attempt_,const vector<CvUnit*>& units)
		: active(CvStackingDiagnostics::EnabledCategory(1,owner_,"PLAN_RETRY")),owner(owner_),target(target_),batch(batch_),attempt(attempt_),before(0)
	{
		if (!active) return;
		ids.reserve(units.size());
		for (size_t i=0;i<units.size();++i) ids.push_back(units[i]->GetID());
		before=StackPlanDiagnosticInputHash(owner,ids);
	}
	void Failed(size_t assignments) const
	{
		if (!active || !CvStackingDiagnostics::EnabledCategory(1,owner,"PLAN_RETRY")) return;
		const unsigned __int64 after=StackPlanDiagnosticInputHash(owner,ids);
		std::ostringstream ordered;
		for (size_t i=0;i<ids.size() && i<40;++i) { if (i) ordered<<",";ordered<<ids[i]; }
		CvStackingDiagnostics::Record(1,owner,"PLAN_RETRY","target=%d:%d batch=%d attempt=%d input=%u assignments=%u beforeBasicSignature=%016I64X afterBasicSignature=%016I64X sameBasicSignature=%d idsShown=%u idsTruncated=%d ids=%s; signatures cover ordered input unit basic state only, not complete tactical scene",
			target->getX(),target->getY(),batch+1,attempt+1,(unsigned int)ids.size(),(unsigned int)assignments,before,after,before==after?1:0,
			(unsigned int)min(ids.size(),(size_t)40),ids.size()>40?1:0,ordered.str().c_str());
	}
private:
	bool active;PlayerTypes owner;const CvPlot* target;int batch,attempt;
	unsigned __int64 before;vector<int> ids;
};

static void RecordStackPlanExecutionFailure(PlayerTypes owner,const STacticalAssignment& assignment,size_t index,const char* reason,
	bool precondition,bool postcondition,unsigned int missionOrders,unsigned int ordersBefore,const StackPlanDiagnosticUnitState& before,
	PlayerTypes nativePrimaryOwner=NO_PLAYER,int nativePrimaryID=-1)
{
	// Missions/combat may remove or replace the actor. Never inspect the old
	// execution pointer to collect its diagnostic after-state.
	const StackPlanDiagnosticUnitState after=ReadStackPlanDiagnosticUnitState(GET_PLAYER(owner).getUnit(assignment.iUnitID));
	CvStackingDiagnostics::Record(1,owner,"PLAN_EXEC_FAIL","index=%u unit=%d type=%d from=%d to=%d reason=%s pre=%d post=%d issuedOrders=%u currentOrderIssued=%d expectedPrimaryOwner=%d expectedPrimaryUnit=%d nativePrimaryOwner=%d nativePrimaryUnit=%d beforePresent=%d afterPresent=%d beforePlot=%d afterPlot=%d beforeMoves=%d afterMoves=%d beforeHP=%d afterHP=%d beforeAttacksMade=%d afterAttacksMade=%d beforeProcessed=%d afterProcessed=%d beforeActivity=%d afterActivity=%d beforeMissionTimer=%d afterMissionTimer=%d beforeMissionCount=%d afterMissionCount=%d beforeMissionAI=%d afterMissionAI=%d beforeHeadMission=%d afterHeadMission=%d beforeHeadData1=%d afterHeadData1=%d beforeHeadData2=%d afterHeadData2=%d beforeHeadFlags=%d afterHeadFlags=%d beforeHeadTurn=%d afterHeadTurn=%d",
		(unsigned int)index,assignment.iUnitID,(int)assignment.eAssignmentType,assignment.iFromPlotIndex,assignment.iToPlotIndex,reason,precondition?1:0,postcondition?1:0,missionOrders,missionOrders>ordersBefore?1:0,
		(int)assignment.ePrimaryUnitOwner,assignment.iPrimaryUnitID,(int)nativePrimaryOwner,nativePrimaryID,
		before.values[0],after.values[0],before.values[3],after.values[3],before.values[4],after.values[4],before.values[5],after.values[5],before.values[7],after.values[7],before.values[9],after.values[9],
		before.values[10],after.values[10],before.values[11],after.values[11],before.values[12],after.values[12],before.values[13],after.values[13],before.values[14],after.values[14],
		before.values[15],after.values[15],before.values[16],after.values[16],before.values[17],after.values[17],before.values[18],after.values[18]);
}

bool TacticalAIHelpers::FindAndExecuteBestUnitAssignments(PlayerTypes ePlayer, vector<CvUnit*>& vUnits, CvPlot* pTarget, eAggressionLevel eAggLvl)
{
    if (!pTarget || vUnits.empty()) return false;
    vector<int> unitIDs;
    for (size_t i=0;i<vUnits.size();++i)
        if (vUnits[i] && vUnits[i]->getOwner()==ePlayer) unitIDs.push_back(vUnits[i]->GetID());
    set<int> assigned, rejected;
    const bool wasEnemyCity=pTarget->isCity() && pTarget->getOwner()!=ePlayer;
    const int batches=CvStackingOffensiveAI::Enabled(ePlayer) && unitIDs.size()>TACTSIM_MAX_UNITS
        ? CvStacking::GetInt("AIAssaultTacticalBatches",3) : 1;
    bool anySuccess=false;
    for (int batch=0;batch<batches;++batch)
    {
        if (batch && wasEnemyCity && pTarget->getOwner()==ePlayer) break;
        bool success=false;
        const int retries=CvStacking::GetInt("AIAssaultTacticalRetries",4);
        for (int attempt=0;attempt<retries && !success;++attempt)
        {
            vector<CvUnit*> currentUnits;
            for (size_t i=0;i<unitIDs.size();++i)
            {
                // Combat can delete units. Resolve saved IDs after every execution.
                CvUnit* unit=GET_PLAYER(ePlayer).getUnit(unitIDs[i]);
                if (unit && !unit->isDelayedDeath() && !unit->TurnProcessed() && unit->canUseNow() &&
                    assigned.count(unitIDs[i])==0 && rejected.count(unitIDs[i])==0 &&
                    !CvStackingOffensiveAI::HoldForAssembly(unit,pTarget)) currentUnits.push_back(unit);
            }
            if (currentUnits.empty()) break;
            if (batch && attempt==0 && !CvStackingOffensiveAI::ConsumeAdditionalTacticalBatch(ePlayer)) break;
            TacticalAIHelpers::UpdatePlotDistanceToTarget(ePlayer,pTarget);
            set<int> unusable;
            StackPlanRetryDiagnostic diagnostic(ePlayer,pTarget,batch,attempt,currentUnits);
            vector<STacticalAssignment> plan=TacticalAIHelpers::FindBestUnitAssignments(currentUnits,pTarget,eAggLvl,unusable,true);
            if (plan.empty())
            {
                const size_t before=rejected.size(); rejected.insert(unusable.begin(),unusable.end());
                if (rejected.size()==before) break;
                continue;
            }
            success=TacticalAIHelpers::ExecuteUnitAssignments(ePlayer,plan);
            if (!success) diagnostic.Failed(plan.size());
            if (success)
            {
                anySuccess=true;
                for (size_t i=0;i<plan.size();++i) assigned.insert(plan[i].iUnitID);
                if (batches>1) CvStackingDiagnostics::Record(1,ePlayer,"ASSAULT_BATCH","target=%d batch=%d supplied=%u assignedTotal=%u result=executed",pTarget->GetPlotIndex(),batch+1,(unsigned int)currentUnits.size(),(unsigned int)assigned.size());
            }
        }
        if (!success) break;
    }
    gDistanceToTargetPlots.clear();
    return anySuccess;
}

//make sure our units come in a defined order (important for reproducability, don't want to sort pointers!)
template<typename T>
struct PrSortPairBySecondAsc
{
	bool operator()(const pair<T, T>& lhs, const pair<T, T>& rhs) const { return lhs.second < rhs.second; }
};

//try to find a combination of unit actions (move, attack etc) which does maximal damage to the enemy while exposing us to minimal risk
vector<STacticalAssignment> TacticalAIHelpers::FindBestUnitAssignments(
	const vector<CvUnit*>& vUnits, CvPlot* pTarget, eAggressionLevel eAggLvl, set<int>& unuseableUnits, bool bTargetDistanceRelevant, bool bReturnToStartPositions, int iSaveMovement)
{
	/*
	abstract:

	----
	create tactical plots
	add all units with reachable plots
 
	create open position
	while (pop open positions)
	 if (make next assignments)
	  add children to open positions
	 else if (completed and legal)
	   add to completed positions

	return best completed position
	----

	units are position according to their attack range (melee has range 1 for this purpose)
	distance to enemy is main criterion, danger is secondary
	ranged attack are always possible; melee attacks are accepted or not depending on aggression level
	final confirmation whether an assignement is acceptable happens only at the end

	if aggression level is zero, we do not plan any attacks. only movement.
		if target is friendly, we try to stay within N plots around it with melee units covering ranged units.
		if target is hostile, we try to come close but no closer than N plots with melee units covering ranged units.
	*/

	vector<STacticalAssignment> result;
	if (vUnits.empty() || vUnits.front()==NULL || pTarget==NULL)
		return result;
	const DWORD planningBegin=GetTickCount();

	//meta parameters depending on difficulty setting
	int iMaxBranches = range(GC.getGame().getHandicapInfo().getTacticalSimMaxBranches(),2,9); //cannot do more, else our ID scheme doesn't work
	int iMaxChoicesPerUnit = range(GC.getGame().getHandicapInfo().getTacticalSimMaxChoicesPerUnit(),2,9);
	int iMaxCompletedPositions = range(GC.getGame().getHandicapInfo().getTacticalSimMaxCompletedPositions(), 1, 4000);
	gCheckedPositions = 0;

	PlayerTypes ePlayer = vUnits.front()->getOwner();
	TeamTypes ourTeam = GET_PLAYER(ePlayer).getTeam();
	const bool callbackFreeInputs=StackPreviewInputsSupported(vUnits);
	StackForecastScope stackForecastScope(callbackFreeInputs);
	CvStackingStrengthCache::Scope strengthCacheScope(callbackFreeInputs && CvStacking::IsEnabled() ? CvStacking::GetInt("AITacticalStrengthCacheEntries", 16384) : 0,
		callbackFreeInputs ? StackPreviewCallbackCapabilities : NULL);
	CvStackingDiagnostics::PlanSampleSession sampleSession(ePlayer,pTarget->GetPlotIndex()); // PLAN_SAMPLE_DIAGNOSTIC_ONLY
	DestinationKernelProbeSession kernelProbeSession(ePlayer,pTarget->GetPlotIndex()); // DESTINATION_KERNEL_SHADOW_DIAGNOSTIC_ONLY
	PacketProbeScope packetProbeScope(ePlayer,pTarget->GetPlotIndex()); // PLAN_PACKET_PROBE_DIAGNOSTIC_ONLY

	static vector<CvTacticalPosition*> openPositionsHeap;
	static vector<CvTacticalPosition*> completedPositions;

#if defined(VPDEBUG)
	if (GC.getLogging() && GC.getAILogging())
	{
		CvString strMsg = CvString::format("simulating assignments around %d:%d with %d units, agg level %d", pTarget->getX(), pTarget->getY(), vUnits.size(), eAggLvl);
		for (size_t i = 0; i < vUnits.size(); i++)
			strMsg += CvString::format("; %d", vUnits[i]->GetID());

		GET_PLAYER(ePlayer).GetTacticalAI()->LogTacticalMessage(strMsg);

		// Assertions for critical conditions
		ASSERT(iMaxBranches >= 2 && iMaxBranches <= 9 && "Invalid branch count");
		ASSERT(iMaxChoicesPerUnit >= 2 && iMaxChoicesPerUnit <= 9 && "Invalid choices per unit");
	}
#endif

	//clean up from the last run, more if the player changed to limit memory usage
	gTactPosStorage.reset(eLastTactSimPlayer!=ePlayer);
	gSupportPosStorage.reset(eLastTactSimPlayer!=ePlayer);
	gAssignmentStorage.reset(eLastTactSimPlayer != ePlayer);
	eLastTactSimPlayer = ePlayer;

	gReachablePlotsLookup.clear();
	gRangeAttackPlotsLookup.clear();
	gSafePlotCount.clear();
	gBadUnitsCount.clear();
	unuseableUnits.clear();

	//basic leader trait dependence
	int iOffenseFlavor = range(GET_PLAYER(ePlayer).GetGrandStrategyAI()->GetPersonalityAndGrandStrategy((FlavorTypes)GC.getInfoTypeForString("FLAVOR_OFFENSE")), 0, 10);
	gDefaultUnitLossThreshold = (iOffenseFlavor>6 && vUnits.size()>6) ? 1 : 0;
	gMinHpForTactsim = 50 - 2 * iOffenseFlavor;
	
	//set up the initial position
	CvTacticalPosition* initialPosition = gTactPosStorage.peekNext(); gTactPosStorage.consumeOne();
	if (!initialPosition)
		return result;

	initialPosition->initFromScratch(ePlayer, eAggLvl, pTarget, bTargetDistanceRelevant, bReturnToStartPositions, iSaveMovement);

	//first pass: make sure there are no duplicates and other invalid inputs
	vector<const CvUnit*> ourUnits;
	vector<int> unitXP;

	ourUnits.reserve(vUnits.size());
	unitXP.reserve(vUnits.size());

	for (size_t i = 0; i < vUnits.size(); i++)
	{
		CvUnit* pUnit = vUnits[i];

		//do not use a set for enforcing uniqueness - the iteration order would depend on memory address by default
		//unfortunately the simulation result sometimes seems to depend on the order of the units being processed ...
		if (std::find(ourUnits.begin(), ourUnits.end(), pUnit) != ourUnits.end())
		{
			CvStackingDiagnostics::Record(2, ePlayer, "RECRUIT_FILTER", "target=%d:%d unit=%d reason=duplicate", pTarget->getX(), pTarget->getY(), pUnit ? pUnit->GetID() : -1);
			continue;
		}

		// Embarked combat stacks use the same domain-slot accounting. Cargo and
		// aircraft retain their separate transport/rebase handling. Legacy mode
		// keeps its original restriction on non-native units sharing a plot.
		if (pUnit && pUnit->canUseNow())
		{
			if ((CvStacking::IsEnabled() && pUnit->IsCombatUnit() && !pUnit->isCargo()) || pUnit->isNativeDomain(pUnit->plot()) || pUnit->plot()->getNumUnits() == 1 || pUnit->plot()->isCity())
			{
				ourUnits.push_back(vUnits[i]);
				unitXP.push_back(vUnits[i]->getExperienceTimes100());
			}
			else
				CvStackingDiagnostics::Record(2, ePlayer, "RECRUIT_FILTER", "target=%d:%d unit=%d reason=domain_occupancy", pTarget->getX(), pTarget->getY(), pUnit->GetID());
		}
		else
			CvStackingDiagnostics::Record(2, ePlayer, "RECRUIT_FILTER", "target=%d:%d unit=%d reason=null_or_not_usable", pTarget->getX(), pTarget->getY(), pUnit ? pUnit->GetID() : -1);
	}

	if (ourUnits.empty())
		return result;

	//remember the median xp so that we can protect our experienced units over the rookies
	std::nth_element(unitXP.begin(), unitXP.begin() + unitXP.size()/2, unitXP.end());
	gMedianUnitXP = (unitXP[unitXP.size()/2]);

	//create the tactical plots around the target (up to distance 5)
	//not equivalent to the union of all reachable plots: we need to consider unreachable enemies as well!
	//some units may have their initial plots outside of this range but that's ok, we'll fix it later
	vector<CvPlot*> enemyPlots;
	for (int i = 0; i < RING_PLOTS[TACTICAL_COMBAT_MAX_TARGET_DISTANCE + 1]; i++)
	{
		CvPlot* pPlot = iterateRingPlots(pTarget, i);
		if (pPlot && pPlot->isVisible(ourTeam))
		{
			initialPosition->addTacticalPlot(pPlot, ourUnits);
			//need this for later
			if (pPlot->isEnemyUnit(initialPosition->getPlayer(), true, false))
				enemyPlots.push_back(pPlot);
		}
	}

	//second pass, ensure we have space to maneuver around our enemies
	//this might reveal new enemies but there has to be a line somewhere ...
	for (size_t j = 0; j < enemyPlots.size(); j++)
	{
		for (int i = RING0_PLOTS; i < RING_PLOTS[2]; i++)
		{
			CvPlot* pPlot = iterateRingPlots(enemyPlots[j], i);
			if (pPlot && pPlot->isVisible(ourTeam))
				initialPosition->addTacticalPlot(pPlot, ourUnits);
		}
	}

	//do this once before we start adding units
	initialPosition->countEnemiesAndCheckVisibility();

	//third pass, now that we know which units will be used, add them to the initial position
	for(vector<const CvUnit*>::const_iterator it=ourUnits.begin(); it!=ourUnits.end(); ++it)
	{
		const CvUnit* pUnit = *it;
		if (initialPosition->addAvailableUnit(pUnit))
		{
			//make sure we know the immediate surroundings of every unit
			for (int j = 0; j < RING1_PLOTS; j++)
			{
				CvPlot* pPlot = iterateRingPlots(pUnit->plot(), j);
				if (pPlot)
					initialPosition->addTacticalPlot(pPlot, ourUnits);
			}
		}
		else
			CvStackingDiagnostics::Record(2, ePlayer, "RECRUIT_FILTER", "target=%d:%d unit=%d reason=not_admitted_to_combat_sim", pTarget->getX(), pTarget->getY(), pUnit->GetID());
	}

	//find out which plot is frontline, second line etc
	initialPosition->refreshVolatilePlotProperties(true);

	//now associate our units with their initial plots (after we know the plot types)
	initialPosition->addInitialAssignments();

	//number of enemies influences how aggressive we can be
	//note that for defensive positioning we do not require any enemies to be nearby
	initialPosition->countEnemiesAndCheckVisibility();

	//small performance optimization
	initialPosition->setFirstInterestingAssignment(initialPosition->getAssignments().size());

	//around 15 units everything becomes slow so don't use too many
	const int iRecruitedUnits = initialPosition->GetNumAvailableUnits();
	initialPosition->dropSuperfluousUnits(TACTSIM_MAX_UNITS);
	const int iKeptUnits = initialPosition->GetNumAvailableUnits();
	CvStackingDiagnostics::Record(1, ePlayer, "RECRUIT", "target=%d:%d input=%u usable=%u recruited=%d kept=%d budgetDropped=%d cap=%d",
		pTarget->getX(), pTarget->getY(), (unsigned int)vUnits.size(), (unsigned int)ourUnits.size(), iRecruitedUnits, iKeptUnits, iRecruitedUnits-iKeptUnits, TACTSIM_MAX_UNITS);

	openPositionsHeap.clear();
	completedPositions.clear();
	size_t iUsedPositions = 0;
	DWORD yieldMs=0;unsigned int yieldCount=0;
	//each UI yield also discards the search caches, see AITacticalYieldPositions
	const size_t iYieldPositions = (size_t)max(1, CvStacking::GetInt("AITacticalYieldPositions", 500));

	//don't need to call make_heap for a single element
	openPositionsHeap.push_back(initialPosition);

	//initially we go breadth-first, later switch to depth-first
	CvTacticalPosition::PrPositionSortHeapGeneration heapSort(false);

	cvStopWatch timer("tactsim", NULL, 0, true);
	const DWORD searchBegin=GetTickCount();
	timer.StartPerfTest();
	while (!openPositionsHeap.empty())
	{
		pop_heap( openPositionsHeap.begin(), openPositionsHeap.end(), heapSort);
		CvTacticalPosition* current = openPositionsHeap.back();

		//switch our strategy?
		if (!heapSort.bDepthFirst && current->getGeneration() > TACTSIM_BREADTH_FIRST_GENERATIONS)
		{
			heapSort.bDepthFirst = true;
			make_heap(openPositionsHeap.begin(), openPositionsHeap.end(), heapSort);
			//pick again after re-sorting
			continue;
		}
		else
			//go on with the selected position, remove it from the heap
			openPositionsHeap.pop_back();

		//just pick the "best" move in depth first mode
		int iMaxBranchesNow = heapSort.bDepthFirst ? 1 : iMaxBranches;
		//allow two moves per unit in case one is invalid
		int iMaxChoicesPerUnitNow = heapSort.bDepthFirst ? 2 : iMaxChoicesPerUnit;

		//here the magic happens!
		current->makeNextAssignments(iMaxBranchesNow, iMaxChoicesPerUnitNow, gTactPosStorage, openPositionsHeap, completedPositions, heapSort, ourUnits);

		int iOldPauseCount = iUsedPositions / iYieldPositions;
		iUsedPositions += current->getChildren().size();
		int iNewPauseCount = iUsedPositions / iYieldPositions;

		//at some point we have seen enough good positions to pick one
		if (completedPositions.size() > (size_t)iMaxCompletedPositions)
			break;

		//be a good citizen and let the UI run in between ... stupid design
		if (iOldPauseCount!=iNewPauseCount && gDLL->HasGameCoreLock())
		{
			const DWORD yieldBegin=GetTickCount();
			CvStackingStrengthCache::Invalidate();
			InvalidateStackForecastScene();
			gDLL->ReleaseGameCoreLock();
			Sleep(1);
			gDLL->GetGameCoreLock();
			InvalidateStackForecastScene();
			yieldMs+=GetTickCount()-yieldBegin;++yieldCount;
		}

		//did we run out of resources?
		//this typically happens if there are only invalid positions to be found ...
		if (gTactPosStorage.peekNext() == NULL)
		{
			timer.EndPerfTest();
			int iStartingUnits = initialPosition->GetNumAvailableUnits();

			std::stringstream ss;
			ss << "warning: tactsim abandoned after, " << std::setprecision(3) << timer.GetDeltaInSeconds() << " s, " <<
				completedPositions.size() << " completed, " <<
				openPositionsHeap.size() << " open, " <<
				iUsedPositions << " processed, " <<
				iStartingUnits << " starting units, " <<
				current->GetNumAvailableUnits() << " remaining units";
				CUSTOMLOG(ss.str().c_str());
			break;
		}
	}
	timer.EndPerfTest();
	int durationMs = int(timer.GetDeltaInSeconds() * 1000);
	const DWORD searchEnd=GetTickCount();

	if (completedPositions.empty())
	{
		//bad but maybe we can recover ... we should have picked BLOCKED moves for impossible units but that doesn't always happen
		//since search breadth is limited and it only turns out at the end whether a chosen move was actually impossible
		//the next best thing is to try again without the problematic units
		for (map<int,int>::const_iterator i = gBadUnitsCount.begin(); i != gBadUnitsCount.end(); ++i)
			unuseableUnits.insert(i->first);
	}
	else
	{
		//good case, pick the best one
		//need the predicate, else we sort the pointers by address!
		std::stable_sort(completedPositions.begin(), completedPositions.end(), CvTacticalPosition::PrPositionSortArrayTotalScore());

		if (completedPositions.front()->HasSupport(DOMAIN_LAND) || completedPositions.front()->HasSupport(DOMAIN_SEA) || completedPositions.front()->HasCitySupport())
			TacticalAIHelpers::AddSupportMoves(*completedPositions.front(), ourUnits);
		result = completedPositions.front()->getAssignments();
	}

	if(GC.getLogging() && GC.getAILogging())
	{
		if (true)
		{
			GET_PLAYER(ePlayer).GetTacticalAI()->LogTacticalMessage(CvString::format("tactsim around (%d:%d) with agg %d finished in %d ms. started with %d units and %d enemies on %d plots. used %d positions, %d completed.",
				pTarget->getX(),pTarget->getY(), eAggLvl, durationMs, initialPosition->GetNumAvailableUnits(), initialPosition->getNumEnemies(), initialPosition->getNumPlots(), iUsedPositions, completedPositions.size()));
		}

		if (CvStacking::IsEnabled() && StackForecastContext())
			GET_PLAYER(ePlayer).GetTacticalAI()->LogTacticalMessage(CvString::format("stack forecast cache: danger %lu hit/%lu miss (%u entries), defender %lu hit/%lu miss (%u entries); peak %u/%u entries, key bytes %u/%u, estimated bytes %u, insertion bypasses %lu, nested bypasses %lu; retained %u entries/%u key bytes, evictions %lu danger/%lu defender",
				gStackDangerHits, gStackDangerMisses, (unsigned int)StackDangerForecastSize(),
				gStackDefenderHits, gStackDefenderMisses, (unsigned int)StackDefenderForecastSize(),
				(unsigned int)gStackPeakEntries, (unsigned int)gStackEntryLimit,
				(unsigned int)gStackPeakKeyBytes, (unsigned int)gStackKeyPayloadLimit, (unsigned int)gStackPeakEstimatedBytes,
				gStackInsertBypasses, gStackNestedBypasses,
				(unsigned int)(StackDangerForecastSize() + StackDefenderForecastSize()), (unsigned int)gStackKeyPayloadBytes,
				gStackDangerEvictions, gStackDefenderEvictions));

		//debug dump
#if defined(MOD_CORE_DEBUGGING)
		if (gCurrentUnitToTrack == -1)
		{
			ofstream out("c:\\temp\\positionscores.csv", std::ios::app);
			if (out)
			{
				for (int i = 0; i < gTactPosStorage.getSize(); i++)
				{
					CvTacticalPosition* pos = gTactPosStorage.first() + i;
					bool isComplete = pos->isEarlyFinish() || pos->isExhausted();
					out << pos->getID() << "," << pos->getScoreLastRound() << "," << pos->getScoreTotal() << "," << (isComplete ? 1:0) << ";";
				}
				out << std::endl;
			}
			out.close();
		}
#endif
	}


#if defined(VPDEBUG)
	// Additional debug info
	char szDebugInfo[256];
	sprintf_s(szDebugInfo, "TacticalAI: Target (%d,%d), Units %lu, Agg %d, Enemies %d, Checked Positions %d, Used %d, Completed %lu, Bad Units %lu, %d ms, Player %d\n",
		pTarget->getX(), pTarget->getY(), (unsigned long)vUnits.size(), eAggLvl, initialPosition->getNumEnemies(), gCheckedPositions, iUsedPositions, (unsigned long)completedPositions.size(), (unsigned long)unuseableUnits.size(), durationMs, ePlayer);
	OutputDebugString(szDebugInfo);
#endif

	const int perfInterval=CvStacking::GetInt("DiagnosticsPerformanceInterval",1);
	if(perfInterval && GC.getGame().getGameTurn()%perfInterval==0)
	{
		const CvStackingStrengthCache::Stats strength = CvStackingStrengthCache::GetStats();
		CvStackingDiagnostics::Record(1,ePlayer,"PLAN_PERF","target=%d:%d setupMs=%lu searchMs=%lu finalizeMs=%lu yieldMs=%lu yields=%u dangerHits=%lu dangerMisses=%lu defenderHits=%lu defenderMisses=%lu entries=%u payloadBytes=%u dangerEvictions=%lu defenderEvictions=%lu meleeStrengthHits=%lu meleeStrengthMisses=%lu rangedStrengthHits=%lu rangedStrengthMisses=%lu attackStrengthHits=%lu attackStrengthMisses=%lu defenseStrengthHits=%lu defenseStrengthMisses=%lu strengthEntries=%u strengthPeakEntries=%u strengthLimit=%u strengthEvictions=%lu strengthInvalidations=%lu outcomeBuilds=%lu outcomeReuses=%lu outcomeBypasses=%lu outcomeRetainedBytes=%u outcomePeakRetainedBytes=%u packetHits=%lu packetBuilds=%lu packetBypasses=%lu callbackProofScans=%lu callbackProofFlags=%lu callbackValidationBypasses=%lu callbackSuspensions=%lu forecastBackend=%s forecastEstimatedBytes=%u; phase tick timing is coarse, search includes yields and shares the PLAN timer",
			pTarget->getX(),pTarget->getY(),searchBegin-planningBegin,searchEnd-searchBegin,GetTickCount()-searchEnd,yieldMs,yieldCount,
			gStackDangerHits,gStackDangerMisses,gStackDefenderHits,gStackDefenderMisses,
			(unsigned int)(StackDangerForecastSize()+StackDefenderForecastSize()),(unsigned int)gStackKeyPayloadBytes,gStackDangerEvictions,gStackDefenderEvictions,
			strength.meleeHits,strength.meleeMisses,strength.rangedHits,strength.rangedMisses,
			strength.attackHits,strength.attackMisses,strength.defenseHits,strength.defenseMisses,
			strength.entries,strength.peakEntries,strength.limit,strength.evictions,strength.invalidations,
			gStackOutcomeBuilds,gStackOutcomeReuses,gStackOutcomeBypasses,(unsigned int)gStackOutcomeCurrentBytes,(unsigned int)gStackOutcomePeakBytes,
			gStackPacketHits,gStackPacketBuilds,gStackPacketBypasses,
			strength.capabilityScans,strength.capabilityFlags,strength.capabilityValidationBypasses,strength.capabilitySuspensions,gUseIndexed?"indexed":"legacy",(unsigned int)EstimatedStackForecastBytes());
	}
	CvStackingDiagnostics::Record(1, ePlayer, "PLAN", "target=%d:%d aggression=%d input=%u kept=%d states=%d completed=%u assignments=%u milliseconds=%d",
		pTarget->getX(), pTarget->getY(), (int)eAggLvl, (unsigned int)vUnits.size(), iKeptUnits, iUsedPositions,
		(unsigned int)completedPositions.size(), (unsigned int)result.size(), durationMs);
	if (CvStackingDiagnostics::EnabledCategory(2, ePlayer, "PLAN_ASSIGN"))
		for (size_t i = 0; i < result.size(); ++i)
		{
			const STacticalAssignment& a = result[i];
			CvStackingDiagnostics::Record(2, ePlayer, "PLAN_ASSIGN", "target=%d:%d index=%u unit=%d from=%d to=%d type=%d moves=%d score=%d plotScore=%d bonus=%d damageDelta=%d selfDamage=%d cityDamage=%d primaryOwner=%d primaryUnit=%d",
				pTarget->getX(), pTarget->getY(), (unsigned int)i, a.iUnitID, a.iFromPlotIndex, a.iToPlotIndex, (int)a.eAssignmentType,
				(int)a.iRemainingMoves, a.Score(), a.GetPlotScore(), a.GetBonusScore(), a.GetDamageDelta(), (int)a.iSelfDamage, (int)a.iCityDamage,(int)a.ePrimaryUnitOwner,a.iPrimaryUnitID);
		}
	return result;
}

// Execution identities are ephemeral tactical evidence, never save data.
// Native combat can delete a victim (or capturing actor); do not retain a
// dereferenceable pointer across a mission and mistake another stack member
// for the victim selected by the forecast.
struct StackPlanVictim
{
    PlayerTypes owner;
    int id;
    bool present;
    StackPlanVictim() : owner(NO_PLAYER), id(-1), present(false) {}
    explicit StackPlanVictim(const CvUnit* unit)
        : owner(unit ? unit->getOwner() : NO_PLAYER), id(unit ? unit->GetID() : -1), present(unit != NULL) {}
};
static CvUnit* StackPlanNativeVictim(CvPlot* target, CvUnit* actor, PlayerTypes owner)
{
    return target->isEnemyCity(*actor) ? target->getPlotCity()->GetGarrisonedUnit()
        : target->getBestDefender(NO_PLAYER,owner,actor);
}
static bool StackPlanVictimDefeated(const StackPlanVictim& victim)
{
    if (!victim.present) return false;
    CvUnit* live = GET_PLAYER(victim.owner).getUnit(victim.id);
    return !live || live->IsDead() || live->isDelayedDeath();
}
static bool StackPlanPrimaryMatches(const STacticalAssignment& assignment, const StackPlanVictim& victim)
{
    // NO_PLAYER marks an assignment not produced by the combat scorer.
    // A scored no-garrison city has its owner and ID -1, so absence is known.
    if (assignment.ePrimaryUnitOwner == NO_PLAYER) return true;
    return assignment.iPrimaryUnitID < 0 ? !victim.present
        : victim.present && assignment.iPrimaryUnitID == victim.id && assignment.ePrimaryUnitOwner == victim.owner;
}

bool TacticalAIHelpers::ExecuteUnitAssignments(PlayerTypes ePlayer, const std::vector<STacticalAssignment>& vAssignments)
{
	static const BuildTypes eCitadel = (BuildTypes)GC.getInfoTypeForString("BUILD_CITADEL");
	static const BuildTypes eOrdo = MOD_BALANCE_VP ? (BuildTypes)GC.getInfoTypeForString("BUILD_ORDO") : NO_BUILD;
	static const BuildTypes eIsibaya = MOD_BALANCE_VP ? (BuildTypes)GC.getInfoTypeForString("BUILD_ISIBAYA") : NO_BUILD;

	//take the assigned moves one by one and try to execute them faithfully. 
	//may fail if a melee kill unexpectedly happens or does not happen

	vector<CvUnit*> finishedUnits;
	const bool diagnose=CvStackingDiagnostics::EnabledCategory(1,ePlayer,"PLAN_EXEC_FAIL");
	unsigned int missionOrders=0;

	for (size_t i = 0; i < vAssignments.size(); i++)
	{
		CvUnit* pUnit = GET_PLAYER(ePlayer).getUnit(vAssignments[i].iUnitID);
		//be extra careful with the unit here, if we capture cities and liberate them strange instakills can happen
		//so we need to guess whether the pointer is still valid
		if (!pUnit || pUnit->IsDead() || pUnit->isDelayedDeath() || pUnit->plot()==NULL)
			continue;

		CvPlot* pFromPlot = GC.getMap().plotByIndexUnchecked(vAssignments[i].iFromPlotIndex);
		CvPlot* pToPlot = GC.getMap().plotByIndexUnchecked(vAssignments[i].iToPlotIndex);

		//abort movement and retry if we find eg an enemy submarine
		int iMoveflags = CvUnit::MOVEFLAG_IGNORE_DANGER | CvUnit::MOVEFLAG_NO_STOPNODES | CvUnit::MOVEFLAG_ABORT_IF_NEW_ENEMY_REVEALED;
		bool bPrecondition = false;
		bool bPostcondition = false;
		const unsigned int ordersBefore=missionOrders;
		StackPlanDiagnosticUnitState diagnosticBefore;
		if (diagnose) diagnosticBefore=ReadStackPlanDiagnosticUnitState(pUnit);

		CvUnit* pEnemy = NULL;
		StackPlanVictim expectedVictim;
		const int actorID=pUnit->GetID();
		const PlayerTypes actorOwner=pUnit->getOwner();

		switch (vAssignments[i].eAssignmentType)
		{
		case A_INITIAL:
		case A_FINISH_TEMP:
		case A_MOVE_DOUBLE:
		case A_WAIT:
			continue; //skip this!
			break;
		case A_MOVE:
		case A_MOVE_FORCED:
		case A_CAPTURE:
			pUnit->ClearPathCache(); //make sure there's no stale path which coincides with our target
			bPrecondition = pUnit->canMove() && (pUnit->plot() == pFromPlot) && !(pToPlot->isEnemyUnit(ePlayer,true,true) || pToPlot->isEnemyCity(*pUnit)); //no enemy
#ifdef TACTDEBUG
			if (bPrecondition)
			{
				//see if we can indeed reach the target plot this turn ... 
				pUnit->ClearPathCache(); 
				if (!pUnit->GeneratePath(pToPlot, iMoveflags) || pUnit->GetPathEndFirstTurnPlot() != pToPlot)
					OutputDebugString("ouch, pathfinding problem\n");
			}
#endif
			if (bPrecondition)
			{
				if (diagnose) ++missionOrders;
				pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pToPlot->getX(), pToPlot->getY(), iMoveflags, false, false, MISSIONAI_OPMOVE);
			}

			//movement may indeed fail if we stumble upon an invisible unit!
			bPostcondition = (pUnit->plot() == pToPlot);

#ifdef TACTDEBUG
			//check this only for moves, eg melee kills can fail this check because the pathfinder assumes attacks end the turn!
			if (vAssignments[i].iRemainingMoves != pUnit->getMoves() && bPostcondition)
				OutputDebugString("ouch, inconsistent movement points\n");
#endif
			break;
		case A_MOVE_SWAP:
			pUnit->ClearPathCache(); //make sure there's no stale path which coincides with our target
			bPrecondition = (pUnit->plot() == pFromPlot) && !(pToPlot->isEnemyUnit(ePlayer,true,true) || pToPlot->isEnemyCity(*pUnit)); //no enemy
			if (bPrecondition)
			{
				if (diagnose) ++missionOrders;
				pUnit->PushMission(CvTypes::getMISSION_SWAP_UNITS(), pToPlot->getX(), pToPlot->getY(), iMoveflags, false, false, MISSIONAI_OPMOVE);
			}
			bPostcondition = (pUnit->plot() == pToPlot); //plot changed
			break;
		case A_MOVE_SWAP_REVERSE:
			//nothing to do, this is just a dummy which always occurs after MOVE_SWAP for bookkeeping
			bPrecondition = (pUnit->plot() == pToPlot);
			bPostcondition = (pUnit->plot() == pToPlot);
			break;
		case A_RANGEATTACK:
		{
			bool bCityBefore = pToPlot->isEnemyCity(*pUnit);
			if(bCityBefore && !CvStackingOffensiveAI::AllowCityAttack(pUnit,pToPlot->getPlotCity(),pFromPlot,false,true))
			{
				if (diagnose) RecordStackPlanExecutionFailure(ePlayer,vAssignments[i],i,"city_attack_gate",bPrecondition,bPostcondition,missionOrders,ordersBefore,diagnosticBefore);
				return false;
			}
			bool bUnitBefore = pToPlot->isEnemyUnit(ePlayer, true, true);
			bPrecondition = (pUnit->plot() == pFromPlot) && (bCityBefore || bUnitBefore); //enemy present
			pEnemy = StackPlanNativeVictim(pToPlot,pUnit,ePlayer);
			expectedVictim=StackPlanVictim(pEnemy);
			bPrecondition=bPrecondition && StackPlanPrimaryMatches(vAssignments[i],expectedVictim);
			if (bPrecondition)
			{
				if (diagnose) ++missionOrders;
				pUnit->PushMission(CvTypes::getMISSION_RANGE_ATTACK(), pToPlot->getX(), pToPlot->getY());
                pUnit = GET_PLAYER(actorOwner).getUnit(actorID);
                if (!pUnit || pUnit->IsDead() || pUnit->isDelayedDeath() || !pUnit->plot())
                {
                    if (diagnose)
                        RecordStackPlanExecutionFailure(actorOwner,vAssignments[i],i,
                            !pUnit ? "actor_removed" : "actor_unavailable",bPrecondition,false,
                            missionOrders,ordersBefore,diagnosticBefore,expectedVictim.owner,expectedVictim.id);
                    return false;
                }
			}
			bPostcondition = (!bCityBefore || pToPlot->isEnemyCity(*pUnit)) && (!expectedVictim.present || !StackPlanVictimDefeated(expectedVictim)); //enemy should survive
			break;
		}
		case A_RANGEKILL:
		{
			const bool bCityBefore=pToPlot->isEnemyCity(*pUnit);
			if (bCityBefore && !CvStackingOffensiveAI::AllowCityAttack(pUnit,pToPlot->getPlotCity(),pFromPlot,false,true))
			{
				if (diagnose) RecordStackPlanExecutionFailure(ePlayer,vAssignments[i],i,"city_attack_gate",false,false,missionOrders,ordersBefore,diagnosticBefore);
				return false;
			}
			bPrecondition = (pUnit->plot() == pFromPlot) && (bCityBefore || pToPlot->isEnemyUnit(ePlayer,true,true));
			pEnemy = StackPlanNativeVictim(pToPlot,pUnit,ePlayer);
			expectedVictim=StackPlanVictim(pEnemy);
			bPrecondition=bPrecondition && StackPlanPrimaryMatches(vAssignments[i],expectedVictim);
			if (bPrecondition)
			{
				if (diagnose) ++missionOrders;
				pUnit->PushMission(CvTypes::getMISSION_RANGE_ATTACK(), pToPlot->getX(), pToPlot->getY());
                pUnit = GET_PLAYER(actorOwner).getUnit(actorID);
                if (!pUnit || pUnit->IsDead() || pUnit->isDelayedDeath() || !pUnit->plot())
                {
                    if (diagnose)
                        RecordStackPlanExecutionFailure(actorOwner,vAssignments[i],i,
                            !pUnit ? "actor_removed" : "actor_unavailable",bPrecondition,false,
                            missionOrders,ordersBefore,diagnosticBefore,expectedVictim.owner,expectedVictim.id);
                    return false;
                }
			}
			bPostcondition = StackPlanVictimDefeated(expectedVictim) && (!bCityBefore || pToPlot->isEnemyCity(*pUnit));
			break;
		}
		case A_MELEEATTACK:
			if(pToPlot->isEnemyCity(*pUnit) && !CvStackingOffensiveAI::AllowCityAttack(pUnit,pToPlot->getPlotCity(),pFromPlot,false,true))
			{
				if (diagnose) RecordStackPlanExecutionFailure(ePlayer,vAssignments[i],i,"city_attack_gate",bPrecondition,bPostcondition,missionOrders,ordersBefore,diagnosticBefore);
				return false;
			}
			pEnemy=StackPlanNativeVictim(pToPlot,pUnit,ePlayer);
			expectedVictim=StackPlanVictim(pEnemy);
			bPrecondition = (pUnit->plot() == pFromPlot) && (pToPlot->isEnemyUnit(ePlayer,true,true) || pToPlot->isEnemyCity(*pUnit)); //enemy present
			bPrecondition=bPrecondition && StackPlanPrimaryMatches(vAssignments[i],expectedVictim);
			if (bPrecondition)
			{
				if (diagnose) ++missionOrders;
				pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pToPlot->getX(), pToPlot->getY());
                pUnit = GET_PLAYER(actorOwner).getUnit(actorID);
                if (!pUnit || pUnit->IsDead() || pUnit->isDelayedDeath() || !pUnit->plot())
                {
                    if (diagnose)
                        RecordStackPlanExecutionFailure(actorOwner,vAssignments[i],i,
                            !pUnit ? "actor_removed" : "actor_unavailable",bPrecondition,false,
                            missionOrders,ordersBefore,diagnosticBefore,expectedVictim.owner,expectedVictim.id);
                    return false;
                }
			}
			bPostcondition = (pUnit->plot() == pFromPlot) && (pToPlot->isEnemyUnit(ePlayer,true,true) || pToPlot->isEnemyCity(*pUnit)) && (!expectedVictim.present || !StackPlanVictimDefeated(expectedVictim)); //expected enemy still present
			break;
		case A_MELEEKILL:
		case A_MELEEKILL_NO_ADVANCE:
		{
			bPrecondition = (pUnit->plot() == pFromPlot) && (pToPlot->isEnemyUnit(ePlayer, true, true) || pToPlot->isEnemyCity(*pUnit)); //enemy present
			CvCity* pCity = pToPlot->getPlotCity();
			CvUnit* pEnemy = StackPlanNativeVictim(pToPlot,pUnit,ePlayer);
			expectedVictim=StackPlanVictim(pEnemy);
			bPrecondition=bPrecondition && StackPlanPrimaryMatches(vAssignments[i],expectedVictim);
			bool bCityKill = false;
			bool bUnitKill = false;
			const bool bCityBefore=pToPlot->isEnemyCity(*pUnit);
			if (vAssignments[i].eAssignmentType==A_MELEEKILL_NO_ADVANCE)
			{
				if (bCityBefore && !CvStackingOffensiveAI::AllowCityAttack(pUnit,pToPlot->getPlotCity(),pFromPlot,false,true))
                {
                    if (diagnose) RecordStackPlanExecutionFailure(ePlayer,vAssignments[i],i,"city_attack_gate",bPrecondition,false,missionOrders,ordersBefore,diagnosticBefore);
                    return false;
                }
			}
			//because of randomness in previous combat results, it may happen that we cannot actually kill the enemy
			if (bPrecondition)
			{
				int iDamageDealt = 0;
				int iDamageReceived = 0;
				int iGarrisonDamageDealt = 0;
				if (pToPlot->isEnemyCity(*pUnit))
				{
					iDamageDealt = TacticalAIHelpers::GetSimulatedDamageFromAttackOnCity(pCity, pUnit, pUnit->plot(), iDamageReceived, iGarrisonDamageDealt);
					if (iDamageDealt >= (pCity->GetMaxHitPoints() - pCity->getDamage()))
						bCityKill = true;
					if (pEnemy && (bCityKill || iGarrisonDamageDealt >= pEnemy->GetCurrHitPoints()))
						bUnitKill = true;
				}
				else
				{
					iDamageDealt = TacticalAIHelpers::GetSimulatedDamageFromAttackOnUnit(pEnemy, pUnit, pEnemy->plot(), pUnit->plot(), iDamageReceived);
					if (iDamageDealt >= pEnemy->GetCurrHitPoints())
						bUnitKill = true;
				}
			}

			if (bPrecondition)
			{
				if (diagnose) ++missionOrders;
				pUnit->PushMission(CvTypes::getMISSION_MOVE_TO(), pToPlot->getX(), pToPlot->getY());
                pUnit = GET_PLAYER(actorOwner).getUnit(actorID);
                if (!pUnit || pUnit->IsDead() || pUnit->isDelayedDeath() || !pUnit->plot())
                {
                    if (diagnose)
                        RecordStackPlanExecutionFailure(actorOwner,vAssignments[i],i,
                            !pUnit ? "actor_removed" : "actor_unavailable",bPrecondition,false,
                            missionOrders,ordersBefore,diagnosticBefore,expectedVictim.owner,expectedVictim.id);
                    return false;
                }
			}

			//because of randomness in previous combat results, it may happen that we cannot actually kill the enemy
			if (vAssignments[i].eAssignmentType == A_MELEEKILL)
			{
				bPostcondition = pUnit->plot() == pToPlot; //advanced into enemy plot
			}
			else
			{
				bPostcondition = pUnit->plot() == pFromPlot;
			}
			if (bPostcondition && bCityBefore && vAssignments[i].eAssignmentType==A_MELEEKILL)
				bPostcondition = pToPlot->isCity() && pToPlot->getOwner()==ePlayer && !pToPlot->isEnemyCity(*pUnit) && !pToPlot->isEnemyUnit(ePlayer,true,true) && (!expectedVictim.present || StackPlanVictimDefeated(expectedVictim));
			else if (bPostcondition)
				bPostcondition = StackPlanVictimDefeated(expectedVictim) && (!bCityBefore || pToPlot->isEnemyCity(*pUnit));
			break;
		}
		case A_PILLAGE:
			if (diagnose) ++missionOrders;
			pUnit->PushMission(CvTypes::getMISSION_PILLAGE());
			bPrecondition = true;
			bPostcondition = true;
			break;
		case A_USE_POWER:
			if (eOrdo != NO_BUILD && pUnit->canBuild(pUnit->plot(), eOrdo))
			{
				if (diagnose) ++missionOrders;
				pUnit->PushMission(CvTypes::getMISSION_BUILD(), eOrdo);
			}
			else if (eIsibaya != NO_BUILD && pUnit->canBuild(pUnit->plot(), eIsibaya))
			{
				if (diagnose) ++missionOrders;
				pUnit->PushMission(CvTypes::getMISSION_BUILD(), eIsibaya);
			}
			else if (pUnit->canBuild(pUnit->plot(), eCitadel))
			{
				if (diagnose) ++missionOrders;
				pUnit->PushMission(CvTypes::getMISSION_BUILD(), eCitadel);
			}
			else if (pUnit->canRepairFleet(pUnit->plot()))
			{
				if (diagnose) ++missionOrders;
				pUnit->PushMission(CvTypes::getMISSION_REPAIR_FLEET());
			}
			else
				bPrecondition = false;
			break;
		case A_HEAL:
		case A_FINISH:
			if (diagnose) ++missionOrders;
			pUnit->PushMission(CvTypes::getMISSION_SKIP());
			//this is the difference to a blocked unit, we prevent anyone else from moving it unless we want it to heal
			if (!pUnit->shouldHeal(false) || pUnit->getMoves() == 0 || pUnit->isBarbarian()) //barbarians don't heal
				//important ... this allows civilian units to use this one as cover!
				finishedUnits.push_back(pUnit);
			bPrecondition = true;
			bPostcondition = true;
			break;
		case A_BLOCKED:
			if (diagnose) ++missionOrders;
			pUnit->PushMission(CvTypes::getMISSION_SKIP());
			//do not mark the unit as processed, it can be reused for other tasks!
			bPrecondition = true;
			bPostcondition = true;
			break;
		case A_RESTART:
			if (diagnose) RecordStackPlanExecutionFailure(ePlayer,vAssignments[i],i,"visibility_restart",bPrecondition,bPostcondition,missionOrders,ordersBefore,diagnosticBefore);
			return false; //the previous move revealed a new enemy (which cause a danger update). restart the combat simulation with the remaining units.
			break;
		}
		if (diagnose && (!bPrecondition || !bPostcondition))
			RecordStackPlanExecutionFailure(ePlayer,vAssignments[i],i,!bPrecondition?
				(!StackPlanPrimaryMatches(vAssignments[i],expectedVictim)?"primary_changed":"precondition"):"postcondition",
				bPrecondition,bPostcondition,missionOrders,ordersBefore,diagnosticBefore,expectedVictim.owner,expectedVictim.id);

#ifdef TACTDEBUG
		//this can happen sometimes because of randomness or splash damage etc
		if (!bPrecondition || !bPostcondition)
		{
			CvString strLogString;
			const char* unitName = pUnit->getUnitInfo().GetDescription();
			strLogString.Format(
				"Turn %d: tactsim: could not execute %s from (%d,%d) to (%d,%d) with %s (%d) now at (%d,%d) (%s failed)\n",
				GC.getGame().getGameTurn(),
				assignmentTypeNames[vAssignments[i].eAssignmentType],
				pFromPlot ? pFromPlot->getX() : -1,
				pFromPlot ? pFromPlot->getY() : -1,
				pToPlot ? pToPlot->getX() : -1,
				pToPlot ? pToPlot->getY() : -1,
				unitName,
				vAssignments[i].iUnitID,
				(pUnit&& pUnit->plot()) ? pUnit->plot()->getX() : -1,
				(pUnit&& pUnit->plot()) ? pUnit->plot()->getY() : -1,
				!bPrecondition ? "precondition" : "postcondition"
			);
			OutputDebugString(strLogString);
			return false;
		}
#else
		if (!bPrecondition || !bPostcondition)
			return false;
#endif
	}

	// Only do this once we know were successful
	for (vector<CvUnit*>::const_iterator it = finishedUnits.begin(); it != finishedUnits.end(); ++it)
	{
		GET_PLAYER(ePlayer).GetTacticalAI()->UnitProcessed((*it)->GetID());
	}

	return true;
}

bool TacticalAIHelpers::AddSupportMoves(CvTacticalPosition& positionAfterCombatMoves, const vector<const CvUnit*>& ourUnits, bool bEarlyExit)
{
	vector<STacticalAssignment> result;

	gSupportPosStorage.reset(false);

	static vector<CvSupportPosition*> openPositionsHeap;
	static vector<CvSupportPosition*> completedPositions;
	size_t iUsedPositions = 0;
	const size_t iYieldPositions = (size_t)max(1, CvStacking::GetInt("AITacticalYieldPositions", 500));

	int iMaxBranches = range(GC.getGame().getHandicapInfo().getTacticalSimMaxBranches(), 2, 9); //cannot do more, else our ID scheme doesn't work
	int iMaxChoicesPerUnit = range(GC.getGame().getHandicapInfo().getTacticalSimMaxChoicesPerUnit(), 2, 9);
	int iMaxCompletedPositions = range(GC.getGame().getHandicapInfo().getTacticalSimMaxCompletedPositions(), 1, 4000);

	vector<const CvTacticalPosition*> allCombatPositions;
	map<const CvTacticalPosition*, const CvTacticalPosition*> nextAttackPosition;
	const CvTacticalPosition* tactPos = &positionAfterCombatMoves;
	while (tactPos != NULL)
	{
		allCombatPositions.push_back(tactPos);
		tactPos = tactPos->getParent();
	}

	std::reverse(allCombatPositions.begin(), allCombatPositions.end());

	// Insert all assignments from the initial position
	const CvTacticalPosition* previousPosition = NULL;

	for (vector<const CvTacticalPosition*>::const_iterator it = allCombatPositions.begin(); it != allCombatPositions.end(); ++it)
	{
		tactPos = *it;

		bool bAttackMove = IsAttackMove(tactPos->getAssignments().back().eAssignmentType);

		if (bAttackMove)
		{
			if (previousPosition)
				nextAttackPosition[previousPosition] = tactPos;

			previousPosition = tactPos;
		}
		if (it == allCombatPositions.end() - 1)
		{
			if (previousPosition && !bAttackMove)
				nextAttackPosition[previousPosition] = tactPos;

			nextAttackPosition[tactPos] = NULL;
		}
	}

	CvSupportPosition* initialPosition = gSupportPosStorage.peekNext(); gSupportPosStorage.consumeOne();
	if (!initialPosition)
	{
		return true;
	}

	// breadth first
	CvTacticalPosition::PrPositionSortHeapGeneration heapSort(false);

	if (bEarlyExit)
	{
		initialPosition->initFromTacticalPosition(positionAfterCombatMoves, positionAfterCombatMoves, ourUnits);
		initialPosition->addInitialAssignments();
		initialPosition->setFirstInterestingAssignment(initialPosition->getAssignments().size());

		initialPosition->updateMovePlotsIfRequired();

		for (size_t i = 0; i < initialPosition->GetNumAvailableUnits(); i++)
		{
			initialPosition->getPreferredAssignmentsForUnit(initialPosition->getAvailableUnits()[i], iMaxChoicesPerUnit, true);
			if (gPossibleMoves.empty())
				return false;
		}

		return true;
	}

	initialPosition->initFromTacticalPosition(*nextAttackPosition.begin()->first, positionAfterCombatMoves, ourUnits);
	initialPosition->addInitialAssignments();
	initialPosition->setFirstInterestingAssignment(initialPosition->getAssignments().size());

	openPositionsHeap.clear();
	completedPositions.clear();

	openPositionsHeap.push_back(initialPosition);

	while (!openPositionsHeap.empty())
	{
		pop_heap(openPositionsHeap.begin(), openPositionsHeap.end(), heapSort);
		CvSupportPosition* current = openPositionsHeap.back();

		//switch our strategy?
		if (!heapSort.bDepthFirst && current->getGeneration() > TACTSIM_BREADTH_FIRST_GENERATIONS)
		{
			heapSort.bDepthFirst = true;
			make_heap(openPositionsHeap.begin(), openPositionsHeap.end(), heapSort);
			//pick again after re-sorting
			continue;
		}
		else
			//go on with the selected position, remove it from the heap
			openPositionsHeap.pop_back();

		//just pick the "best" move in depth first mode
		int iMaxBranchesNow = heapSort.bDepthFirst ? 1 : iMaxBranches;
		//allow two moves per unit in case one is invalid
		int iMaxChoicesPerUnitNow = heapSort.bDepthFirst ? 2 : iMaxChoicesPerUnit;

		//here the magic happens!
		current->makeNextAssignments(iMaxBranchesNow, iMaxChoicesPerUnitNow, gSupportPosStorage, openPositionsHeap, completedPositions, heapSort, nextAttackPosition);

		int iOldPauseCount = iUsedPositions / iYieldPositions;
		iUsedPositions += current->getChildren().size();
		int iNewPauseCount = iUsedPositions / iYieldPositions;

		//at some point we have seen enough good positions to pick one
		if (completedPositions.size() > (size_t)iMaxCompletedPositions)
			break;

		//be a good citizen and let the UI run in between ... stupid design
		if (iOldPauseCount != iNewPauseCount && gDLL->HasGameCoreLock())
		{
			CvStackingStrengthCache::Invalidate();
			InvalidateStackForecastScene();
			gDLL->ReleaseGameCoreLock();
			Sleep(1);
			gDLL->GetGameCoreLock();
			InvalidateStackForecastScene();
		}
	}

	if (!completedPositions.empty())
	{
		//good case, pick the best one
		//need the predicate, else we sort the pointers by address!
		std::stable_sort(completedPositions.begin(), completedPositions.end(), CvTacticalPosition::PrPositionSortArrayTotalScore());

		vector<STacticalAssignment>::const_iterator combatIt = positionAfterCombatMoves.getAssignments().begin();
		vector<STacticalAssignment>::const_iterator supportIt = completedPositions.front()->getAssignments().begin();

		int iAvailableUnits = initialPosition->GetNumAvailableUnits();

		while (combatIt != positionAfterCombatMoves.getAssignments().end())
		{
			if (IsAttackMove(combatIt->eAssignmentType) || combatIt == positionAfterCombatMoves.getAssignments().end() - 1)
			{
				int iWaitingUnits = 0;
				while (supportIt != completedPositions.front()->getAssignments().end())
				{
					if (supportIt->eAssignmentType == A_WAIT)
					{
						supportIt++;
						iWaitingUnits++;
						if (iWaitingUnits == iAvailableUnits)
							break;
					}
					else
					{
						if (supportIt->eAssignmentType == A_FINISH)
							iAvailableUnits--;
						result.push_back(*supportIt);
						positionAfterCombatMoves.UpdateScore(*supportIt);
						++supportIt;
					}
				}
			}

			result.push_back(*combatIt);
			++combatIt;
		}
	}
	else
		// no viable positions found
		return false;

	positionAfterCombatMoves.SetAssignments(result);
	return true;
}

void CvTactPosStorage::reset(bool bHard)
{ 
	//this is normally enough
	iCount = 0; 
	attackCache.clear(); 
	dangerCache.clear();

	//in a hard reset we recreate all stl containers from scratch
	//because their capacity tends to increase over time otherwise
	if (bHard)
	{
		//PrintMemoryInfo("before hard reset");

		for (int i = 0; i < iSize; i++)
			aPositions[i].wipe();

		//for some reason the memory usage is not affected immediately ... but the wiping works
		//PrintMemoryInfo("after hard reset");
	}
}

void CvSupportPosStorage::reset(bool bHard)
{
	//this is normally enough
	iCount = 0;

	//in a hard reset we recreate all stl containers from scratch
	//because their capacity tends to increase over time otherwise
	if (bHard)
	{
		//PrintMemoryInfo("before hard reset");

		for (int i = 0; i < iSize; i++)
			aPositions[i].wipe();

		//for some reason the memory usage is not affected immediately ... but the wiping works
		//PrintMemoryInfo("after hard reset");
	}
}

void CvTactAssignmentStorage::reset(bool bHard)
{
	//this is normally enough
	iCount = 0;

	//in a hard reset we recreate all stl containers from scratch
	//because their capacity tends to increase over time otherwise
	if (bHard)
	{
		//PrintMemoryInfo("before hard reset");

		for (int i = 0; i < iSize; i++)
			aAssignments[i].wipe();

		//for some reason the memory usage is not affected immediately ... but the wiping works
		//PrintMemoryInfo("after hard reset");
	}
}

const char* tacticalMoveNames[] =
{
	"T_NONE",

	"T_UNASSIGNED",
	"T_GUARD",
	"T_GARRISON",
	"T_OPERATION",

	"T_PILLAGE",
	"T_PLUNDER",
	"T_GOODY",

	"T_HEAL",
	"T_SAFETY",
	"T_REPOSITION",
	"T_ESCORT",

	"T_AIRSWEEP",
	"T_AIRPATROL",

	"T_HEDGEHOG",
	"T_COUNTERATTACK",
	"T_WITHDRAW",
	"T_REINFORCE",
	"T_ATTRITION",
	"T_SURGICAL_STRIKE",
	"T_STEAMROLL",
	"T_FLANKATTACK",

	"T_AIRLIFT",
	"T_BLOCKADE",
	"T_CAPTURE",

	"B_CAMP",
	"B_ROAM",
	"B_HUNT",
};

const char* postureNames[] =
{
	"P_NONE",
    "P_WITHDRAW",
    "P_ATTRIT_FROM_RANGE",
    "P_EXPLOIT_FLANKS",
    "P_STEAMROLL",
    "P_SURGICAL_CITY_STRIKE",
    "P_HEDGEHOG",
    "P_COUNTERATTACK",
    "P_SHORE_BOMBARDMENT",
};

const char* assignmentTypeNames[] = 
{
	"INITIAL",
	"MOVE", 
	"MELEEATTACK", 
	"MELEEKILL", 
	"RANGEATTACK", 
	"RANGEKILL", 
	"FINISH",
	"BLOCKED",
	"PILLAGE",
	"CAPTURE",
	"FORCEDMOVE",
	"RESTART",
	"MELEEKILL_NOADVANCE",
	"SWAP",
	"SWAPREVERSE",
	"MOVEDOUBLE",
	"USEPOWER",
	"FINISHTEMP",
	"HEAL",
	"WAIT"
};

