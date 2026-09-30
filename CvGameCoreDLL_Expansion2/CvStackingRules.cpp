#include "CvGameCoreDLLPCH.h"
#include "CvStackingRules.h"
#include "CvStackingDiagnostics.h"
#include "CvStackingAI.h"
#include "CvStackingAIPolicy.h"
#include "CvUnit.h"
#include "CvPlot.h"
#include "CvCity.h"
#include "CvBuildingClasses.h"
#include "CvPlayerAI.h"
#include "CvTeam.h"
#include "CvTechClasses.h"
#include <map>
#include <string>
#include <vector>
#include <climits>
#include "LintFree.h"

namespace
{
	// Arithmetic guard, not a gameplay cap. Actual maximum is XML-configured.
	const int SAFE_INTEGER = INT_MAX / 4;
	struct Setting
	{
		const char* name;
		int value;
		int minimum;
		int maximum;
	};
	const Setting SETTINGS[] =
	{
		{"Enabled", 1, 0, 1},
		{"DefenderSelectionEnabled", 1, 0, 1},
		{"FlankingEnabled", 1, 0, 1},
		{"CollateralEnabled", 1, 0, 1},
		{"DisableCityRangedAttacks", 1, 0, 1},
		{"AIEnabled", 1, 0, 1},
		{"AIMilitaryAllocationEnabled", 1, 0, 1},
		{"CityProtectionScalesWithHP", 1, 0, 1},
		{"UIStackCombatPreviewGap", 8, 0, 100},
		{"AIAssaultBaseUnits", 6, 1, 32},
		{"AIAssaultUnitsPerCapacity", 2, 0, 8},
		{"AIAssaultStrongCityStrength", 25, 1, 5000},
		{"AIAssaultStrongCityExtraUnits", 4, 0, 32},
		{"AIAssaultOpportunityHPPercent", 30, 0, 100},
		{"AIAssaultOpportunityUnits", 4, 1, 20},
		{"AIAssaultMaximumReadyUnits", 24, 4, 64},
		{"AIAssaultMinimumReadyUnits", 4, 1, 32},
		{"AIAssaultNavalMinimumRanged", 4, 0, 12},
		{"AIAssaultMaximumSiege", 8, 0, 24},
		{"AIAssaultBaseSiege", 2, 0, 12},
		{"AIAssaultCapacityPerExtraSiege", 2, 1, 10},
		{"AIAssaultStrongCityExtraSiege", 2, 0, 12},
		{"AIAssaultCoordinationEnabled", 1, 0, 1},
		{"AIAssaultApproachTurns", 3, 0, 4},
		{"AIAssaultHealthyPercent", 65, 1, 100},
		{"AIAssaultStrengthPercent", 125, 50, 400},
		{"AIAssaultDamageHorizon", 4, 1, 12},
		{"AIAssaultGatherTurns", 6, 1, 30},
		{"AIAssaultAbandonTurns", 24, 6, 100},
		{"AIAssaultStageRadius", 6, 2, 10},
		{"AIAssaultStageCohesionRadius", 2, 0, 4},
		{"AIAssaultStagePlacementCandidates", 8, 1, 64},
		{"AIAssaultStageCandidates", 96, 1, 192},
		{"AIAssaultPathQueriesPerTurn", 64, 1, 256},
		{"AIAssaultFiringPositionCandidates", 6, 0, 32},
		{"AIAssaultFiringPositionScanPlots", 96, 1, 192},
		{"AIAssaultFiringPositionRadiusMaximum", 6, 1, 10},
		{"AIAssaultStageDangerPercent", 0, 0, 50},
		{"AIAssaultReviewInterval", 3, 1, 20},
		{"AIAssaultObjectiveSummaryInterval", 5, 1, 50},
		{"AIAssaultWaveArrivalSpreadTurns", 1, 0, 4},
		{"AIAssaultSmallExtraSiegeSlots", 3, 0, 8},
		{"AIAssaultSmallExtraFrontSlots", 3, 0, 8},
		{"AIAssaultBasicExtraSiegeSlots", 4, 0, 8},
		{"AIAssaultBasicExtraFrontSlots", 4, 0, 8},
		{"AIAssaultBiggerExtraSiegeSlots", 5, 0, 8},
		{"AIAssaultBiggerExtraFrontSlots", 5, 0, 8},
		{"AIOffensiveSupportEnabled", 1, 0, 1},
		{"AIWarPreparationEnabled", 1, 0, 1},
		{"AIWarOpeningMaximumTurns", 3, 1, 10},
		{"AIWarOpeningMinimumUnits", 4, 2, 20},
		{"AIWarOpeningReadyPercent", 75, 50, 100},
		{"AIWarOpeningMinimumRanged", 1, 0, 10},
		{"AIWarOpeningStrengthPercent", 150, 100, 300},
		{"AIOffensiveSupportMaximumObjectives", 8, 1, 24},
		{"AIOffensiveSupportMemoryTurns", 12, 2, 40},
		{"AIOffensiveSupportMinimumUnits", 12, 2, 40},
		{"AIOffensiveSupportMaximumUnits", 32, 4, 64},
		{"AIOffensiveSupportReserveUnits", 4, 0, 16},
		{"AIOffensiveSupportStrengthPercent", 150, 100, 400},
		{"AIOffensiveSupportReservePercent", 25, 0, 100},
		{"AIOffensiveSupportTravelReservePercentPerTurn", 2, 0, 10},
		{"AIOffensiveSupportMaximumReservePercent", 60, 0, 200},
		{"AIOffensiveSupportMinimumCapturers", 2, 1, 6},
		{"AIOffensiveSupportMinimumRanged", 2, 0, 8},
		{"AIOffensiveSupportLocalRadius", 4, 2, 6},
		{"AIOffensiveSupportStallTurns", 5, 2, 20},
		{"AIOffensiveSupportRolePriority", 80, 0, 300},
		{"AIOffensiveProductionMaximumUnits", 4, 0, 12},
		{"AIOffensiveProductionMaximumTurns", 12, 1, 30},
		{"AIOffensiveProductionStallTurns", 6, 1, 30},
		{"AIOffensiveProductionSiegeReserves", 2, 0, 8},
		{"AIOffensiveProductionPriority", 400, 0, 5000},
		{"AIOffensiveProductionRolePriority", 400, 0, 5000},
		{"AICapturePlanMaximumTurns", 6, 1, 15},
		{"AICapturePlanPathQueriesPerTurn", 32, 1, 128},
		{"AICapturePlanMinimumHPPercent", 60, 1, 100},
		{"AICaptureNoProgressTurns", 6, 2, 30},
		{"AICaptureRetryTurns", 4, 0, 20},
		{"AICaptureContinuityBonus", 120, 0, 500},
		{"AIAssaultTacticalBatches", 3, 1, 6},
		{"AIAssaultExtraBatchesPerTurn", 16, 0, 64},
		{"AIAssaultTacticalRetries", 4, 1, 8},
		{"AISiegeNoCaptureReviewTurns", 8, 2, 30},
		{"AISiegeNoCaptureLowHPPercent", 25, 0, 100},
		{"AIOperationRouteRetryTurns", 6, 0, 30},
		{"AIOperationRouteRepairCandidates", 4, 0, 16},
		{"AIOperationMovingStallTurns", 12, 4, 40},
		{"AIOperationContactStallTurns", 20, 6, 60},
		{"AIOperationContactHoldPercent", 50, 0, 100},
		{"AICityApproachRadius", 6, 1, 8},
		{"AICityApproachWeight", 35, 0, 100},
		{"AICitySafeDefenders", 1, 0, 10},
		{"AICityMaximumDefenders", 3, 1, 10},
		{"AICityRoleDefenseEnabled", 1, 0, 1},
		{"AICityMaximumMeleeDefenders", 1, 0, 10},
		{"AICityThreatenedMinimumRanged", 2, 0, 10},
		{"AICityRangedSharePercent", 75, 0, 100},
		{"AICityUnitStrengthEstimate", 25, 1, 1000},
		{"AICityGarrisonValuePercent", 50, 0, 200},
		{"AICityRangedValuePercent", 100, 0, 300},
		{"AICityMeleeReserveValuePercent", 25, 0, 200},
		{"AICityRangedProductionPriority", 800, 0, 10000},
		{"AICityRangedTransferPriority", 80, 0, 500},
		{"AICityEmergencyDefenders", 2, 1, 10},
		{"AICityMaximumNavalDefenders", 2, 0, 10},
		{"AICityStrengthCreditPercent", 50, 0, 100},
		{"AICityDefenseStrengthPercent", 120, 50, 300},
		{"AICapitalDefensePercent", 125, 100, 300},
		{"AIGarrisonRangedBonus", 20, 0, 100},
		{"AIGarrisonReplacementPercent", 20, 0, 100},
		{"AIAssemblyNoProgressTurns", 3, 1, 10},
		{"AIFailedAssignmentCooldown", 3, 0, 10},
		{"AIRecruitmentReviewTurns", 5, 1, 30},
		{"AIAssemblyMinimumCombatUnits", 4, 2, 20},
		{"AIAssemblyRequiredPercent", 75, 50, 100},
		{"AIAssemblyMaximumMissing", 1, 0, 3},
		{"AIAssemblyMinimumRanged", 2, 0, 10},
		{"AIAssemblyStrengthPercent", 150, 100, 300},
		{"AIAssemblyStallReviewTurns", 12, 6, 40},
		{"AIReassignmentCooldown", 3, 0, 10},
		{"AIReassignmentContinuityBonus", 40, 0, 300},
		{"AIReinforcementUnitsPerTurn", 8, 0, 32},
		{"AIReinforcementPathQueriesPerTurn", 32, 0, 128},
		{"AIReinforcementMaximumTargets", 8, 1, 32},
		{"AIReinforcementMaximumTurns", 12, 1, 30},
		{"AIReinforcementTravelWeight", 15, 1, 100},
		{"AIReinforcementDefensePriority", 300, 1, 1000},
		{"AIReinforcementAttackPriority", 200, 1, 1000},
		{"AIRearCityPlotScore", 6, 0, 12},
		{"AIRearCityHealthyPercent", 70, 1, 100},
		{"AICityAssaultMinimumSiege", 1, 0, 4},
		{"AIPatrolCurrentZoneBonus", 20, 0, 1000},
		{"AIOffensiveOperationsPerDomain", 2, 0, 6},
		{"AIOffensiveReserveMinimumUnits", 4, 1, 20},
		{"DiagnosticsLevel", 0, 0, 2},
		{"DiagnosticsImmediateFlush", 0, 0, 1},
		{"DiagnosticsBufferKB", 64, 4, 256},
		{"DiagnosticsFlushEveryRows", 256, 1, 8192},
		{"DiagnosticsFlushIntervalMilliseconds", 1000, 0, 60000},
		{"DiagnosticsCategoryMask", 63, 0, 63},
		{"DiagnosticsVerboseStartTurn", -1, -1, 536870911},
		{"DiagnosticsVerboseEndTurn", -1, -1, 536870911},
		{"DiagnosticsCombatSummary", 1, 0, 1},
		{"DiagnosticsPerformanceInterval", 1, 0, 10000},
		{"UIStackDiagnosticsHotkeyEnabled", 1, 0, 1},
		{"DiagnosticsSummaryInterval", 1, 1, 10000},
		{"DiagnosticsDetailInterval", 10, 0, 10000},
		{"DiagnosticsMemoryInterval", 10, 0, 10000},
		{"DiagnosticsPlayer", -1, -1, MAX_PLAYERS-1},
		{"DiagnosticsMaxFileKB", 4096, 64, 65536},
		{"DiagnosticsMaxFiles", 8, 1, 32},
		{"DiagnosticsMaxRowsPerTurn", 4096, 32, 65536},
		{"DiagnosticsHistogramMaxStack", 32, 1, 256},
		{"DiagnosticsLongPlanThreshold", 256, 0, 10000},
		{"BaseCapacity", 2, 1, SAFE_INTEGER},
		{"MaximumCapacity", 9, 1, SAFE_INTEGER},
		{"LandCapacityBonus", 0, 0, SAFE_INTEGER},
		{"SeaCapacityBonus", 0, 0, SAFE_INTEGER},
		{"CityCapacityBonus", 0, 0, SAFE_INTEGER},
		{"MinorCapacityBonus", 0, 0, SAFE_INTEGER},
		{"BarbarianCapacityBonus", 0, 0, SAFE_INTEGER},
		{"CollateralPercent", 20, 0, 100},
		{"CollateralHPFloorPercent", 50, 0, 100},
		{"CollateralMinimumDamage", 1, 0, SAFE_INTEGER},
		{"CityProtectionMaximumPercent", 90, 0, 100},
		{"AIStackProtectionWeight", 20, 0, 10000},
		{"AIStackJoinBonus", 12, 0, 10000},
		{"AIStackLeaveProtectorPenalty", 30, 0, 10000},
		{"AIStackAntiFlankBonus", 12, 0, 10000},
		{"AIStackCollateralWeight", 100, 0, 10000},
		{"AIStackConcentrationPenalty", 10, 0, 10000},
		{"AIStackPairRecruitBonus", 25, 0, 10000},
		{"UIStackEnabled", 1, 0, 1},
		{"UIStackMoveMinimumUnits", 2, 2, 10000},
		{"UIStackRosterWidth", 360, 1, 10000},
		{"UIStackRosterRowHeight", 38, 1, 10000},
		{"UIStackRosterMaximumHeight", 430, 1, 10000},
		{"UIStackRosterOffsetX", 110, 0, 10000},
		{"UIStackRosterOffsetY", 220, 0, 10000},
		{"UIStackFlagCollapseThreshold", 3, 2, 10000},
		{"AIStackConcentrationFreeUnits", 2, 0, 100},
		{"AIStackPairRecruitRange", 1, 0, 10},
		{"UIStackResultDelayMilliseconds", 250, 0, 10000}
	};
	typedef std::map<std::pair<int, std::string>, int> RoleMap;
	struct RulesCache
	{
		bool loaded;
		std::map<std::string, int> settings;
		std::vector<std::pair<int, int> > technologies;
		RoleMap combatRoles;
		RoleMap classRoles;
		RoleMap unitRoles;
		RoleMap promotionRoles;
		std::map<int, int> buildingClasses;
		std::map<int, int> buildings;
		std::map<int, int> effectiveBuildingProtection;
		std::map<int, int> targetDomains;
		RulesCache() : loaded(false) {}
	};
	RulesCache& Cache()
	{
		static RulesCache cache;
		return cache;
	}
	int Clamp(int value, int minimum, int maximum)
	{
		return value < minimum ? minimum : (value > maximum ? maximum : value);
	}
	int SaturatingAdd(int a, int b)
	{
		return b > SAFE_INTEGER - a ? SAFE_INTEGER : a + b;
	}
	void LoadValues(Database::Connection* db, const char* table, const char* referenceColumn,
		const char* referenceTable, const char* valueColumn, std::map<int, int>& values, int maximum)
	{
		CvString sql;
		sql.Format("SELECT r.%s AS ReferenceType, t.Type AS MatchedType, t.ID AS ReferenceID, r.%s AS Value FROM %s r LEFT JOIN %s t ON t.Type=r.%s ORDER BY r.%s", referenceColumn, valueColumn, table, referenceTable, referenceColumn, referenceColumn);
		Database::Results rows;
		if (!db->Execute(rows, sql.c_str()))
		{
			CUSTOMLOG("Stacking: cannot read %s; check StackingSchema.sql registration.", table);
			return;
		}
		while (rows.Step())
		{
			if (!rows.GetText("MatchedType"))
			{
				CUSTOMLOG("Stacking: unknown reference '%s' in %s; row ignored.", rows.GetText("ReferenceType"), table);
				continue;
			}
			const int raw = rows.GetInt("Value");
			const int value = Clamp(raw, 0, maximum);
			if (raw != value)
				CUSTOMLOG("Stacking: %s '%s' value %d outside 0..%d; clamped to %d.", table, rows.GetText("ReferenceType"), raw, maximum, value);
			values[rows.GetInt("ReferenceID")] = value;
		}
	}
	void LoadRoles(Database::Connection* db, const char* table, const char* referenceColumn,
		const char* referenceTable, RoleMap& values)
	{
		CvString sql;
		sql.Format("SELECT r.%s AS ReferenceType, t.Type AS MatchedType, t.ID AS ReferenceID, r.Role, r.Value FROM %s r LEFT JOIN %s t ON t.Type=r.%s ORDER BY r.%s,r.Role", referenceColumn, table, referenceTable, referenceColumn, referenceColumn);
		Database::Results rows;
		if (!db->Execute(rows, sql.c_str()))
		{
			CUSTOMLOG("Stacking: cannot read %s; check StackingSchema.sql registration.", table);
			return;
		}
		while (rows.Step())
		{
			const char* role = rows.GetText("Role");
			if (!rows.GetText("MatchedType") || !role)
			{
				CUSTOMLOG("Stacking: unknown reference '%s' in %s; row ignored.", rows.GetText("ReferenceType"), table);
				continue;
			}
			const bool collateral = strcmp(role, "COLLATERAL_LIMIT") == 0;
			if (!collateral && strcmp(role, "FLANK") && strcmp(role, "ANTI_CAVALRY") && strcmp(role, "FLANK_TARGET"))
			{
				CUSTOMLOG("Stacking: unknown role '%s' in %s; row ignored.", role, table);
				continue;
			}
			// CvCombatInfo has 32 damage-member slots; resolution also checks space.
			const int maximum = collateral ? 32 : 1;
			const int raw = rows.GetInt("Value");
			const int value = Clamp(raw, 0, maximum);
			if (raw != value)
				CUSTOMLOG("Stacking: %s role %s value %d outside 0..%d; clamped.", rows.GetText("ReferenceType"), role, raw, maximum);
			values[std::make_pair(rows.GetInt("ReferenceID"), std::string(role))] = value;
		}
	}
	void EnsureCache()
	{
		RulesCache& cache = Cache();
		if (cache.loaded)
			return;
		Database::Connection* db = GC.GetGameDatabase();
		if (!db)
			return;
		cache.loaded = true;
		// A core DLL may be loaded before CP is activated. Missing schema safely
		// disables the feature until cacheGlobals() resets this cache.
		Database::Results exists;
		if (!db->Execute(exists, "SELECT name FROM sqlite_master WHERE type='table' AND name='Stacking_Settings'") || !exists.Step())
		{
			cache.settings["Enabled"] = 0;
			return;
		}
		for (size_t i = 0; i < sizeof(SETTINGS) / sizeof(SETTINGS[0]); ++i)
			cache.settings[SETTINGS[i].name] = SETTINGS[i].value;
		Database::Results rows;
		if (db->Execute(rows, "SELECT Name, Value FROM Stacking_Settings ORDER BY Name"))
		{
			while (rows.Step())
			{
				const char* name = rows.GetText("Name");
				bool recognized = false;
				for (size_t i = 0; name && i < sizeof(SETTINGS) / sizeof(SETTINGS[0]); ++i)
				{
					if (strcmp(name, SETTINGS[i].name))
						continue;
					const int raw = rows.GetInt("Value");
					const int value = Clamp(raw, SETTINGS[i].minimum, SETTINGS[i].maximum);
					if (raw != value)
						CUSTOMLOG("Stacking: setting %s=%d outside %d..%d; using %d.", name, raw, SETTINGS[i].minimum, SETTINGS[i].maximum, value);
					cache.settings[name] = value;
					recognized = true;
					break;
				}
				if (!recognized)
					CUSTOMLOG("Stacking: unknown setting '%s'; check StackingConfig.xml spelling.", name ? name : "NULL");
			}
		}
		std::map<int, int> techs;
		LoadValues(db, "Stacking_Technologies", "TechType", "Technologies", "CapacityBonus", techs, SAFE_INTEGER);
		cache.technologies.assign(techs.begin(), techs.end());
		LoadRoles(db, "Stacking_UnitCombatRoles", "UnitCombatType", "UnitCombatInfos", cache.combatRoles);
		LoadRoles(db, "Stacking_UnitClassRoles", "UnitClassType", "UnitClasses", cache.classRoles);
		LoadRoles(db, "Stacking_UnitRoles", "UnitType", "Units", cache.unitRoles);
		LoadRoles(db, "Stacking_PromotionRoles", "PromotionType", "UnitPromotions", cache.promotionRoles);
		LoadValues(db, "Stacking_BuildingClassProtection", "BuildingClassType", "BuildingClasses", "ProtectionPercent", cache.buildingClasses, 100);
		LoadValues(db, "Stacking_BuildingProtection", "BuildingType", "Buildings", "ProtectionPercent", cache.buildings, 100);
		Database::Results buildingRows;
		if (db->Execute(buildingRows, "SELECT b.ID, c.ID AS ClassID FROM Buildings b INNER JOIN BuildingClasses c ON c.Type=b.BuildingClass ORDER BY b.ID"))
		{
			while (buildingRows.Step())
			{
				std::map<int, int>::const_iterator inherited = cache.buildingClasses.find(buildingRows.GetInt("ClassID"));
				if (inherited != cache.buildingClasses.end())
					cache.effectiveBuildingProtection[buildingRows.GetInt("ID")] = inherited->second;
			}
		}
		for (std::map<int, int>::const_iterator it = cache.buildings.begin(); it != cache.buildings.end(); ++it)
			cache.effectiveBuildingProtection[it->first] = it->second;
		LoadValues(db, "Stacking_CollateralDomains", "DomainType", "Domains", "Enabled", cache.targetDomains, 1);
		CUSTOMLOG("Stacking: loaded XML configuration, enabled=%d, base=%d, maximum=%d, technology rows=%d.", cache.settings["Enabled"], cache.settings["BaseCapacity"], cache.settings["MaximumCapacity"], (int)cache.technologies.size());
	}
	bool Lookup(const RoleMap& values, int id, const char* role, int& result)
	{
		RoleMap::const_iterator found = values.find(std::make_pair(id, std::string(role)));
		if (found == values.end())
			return false;
		result = found->second;
		return true;
	}
	int Role(const CvUnit* unit, const char* role)
	{
		if (!unit)
			return 0;
		EnsureCache();
		RulesCache& cache = Cache();
		int value = 0;
		Lookup(cache.combatRoles, unit->getUnitCombatType(), role, value);
		Lookup(cache.classRoles, unit->getUnitClassType(), role, value);
		for (RoleMap::const_iterator it = cache.promotionRoles.begin(); it != cache.promotionRoles.end(); ++it)
		{
			if (it->first.second == role && unit->isHasPromotion((PromotionTypes)it->first.first))
				value = std::max(value, it->second);
		}
		Lookup(cache.unitRoles, unit->getUnitType(), role, value);
		return value;
	}
}

namespace CvStacking
{
	void ResetCache()
	{
		CvStackingDiagnostics::Reset();
		CvStackingAI::Reset();
		Cache() = RulesCache();
	}
	int GetInt(const char* name, int fallback)
	{
		EnsureCache();
		if (!name)
			return fallback;
		const std::map<std::string, int>& settings = Cache().settings;
		std::map<std::string, int>::const_iterator it = settings.find(name);
		return it == settings.end() ? fallback : it->second;
	}
	bool IsEnabled()
	{
		return GetInt("Enabled", 0) != 0;
	}
	bool CityRangedAttacksEnabled()
	{
		return !IsEnabled() || GetInt("DisableCityRangedAttacks", 1) == 0;
	}
	int GetCapacity(PlayerTypes owner, DomainTypes domain, bool inCity)
	{
		if (!IsEnabled() || owner == NO_PLAYER || (domain != DOMAIN_LAND && domain != DOMAIN_SEA))
			return 1;
		const CvPlayer& player = GET_PLAYER(owner);
		const int maximum = GetInt("MaximumCapacity", 9);
		int capacity = GetInt("BaseCapacity", 2);
		capacity = SaturatingAdd(capacity, GetInt(domain == DOMAIN_LAND ? "LandCapacityBonus" : "SeaCapacityBonus", 0));
		if (inCity)
			capacity = SaturatingAdd(capacity, GetInt("CityCapacityBonus", 0));
		if (player.isMinorCiv())
			capacity = SaturatingAdd(capacity, GetInt("MinorCapacityBonus", 0));
		if (player.isBarbarian())
			capacity = SaturatingAdd(capacity, GetInt("BarbarianCapacityBonus", 0));
		const CvTeamTechs* techs = GET_TEAM(player.getTeam()).GetTeamTechs();
		const std::vector<std::pair<int, int> >& bonuses = Cache().technologies;
		for (size_t i = 0; techs && i < bonuses.size(); ++i)
			if (techs->HasTech((TechTypes)bonuses[i].first))
				capacity = SaturatingAdd(capacity, bonuses[i].second);
		return std::min(capacity, maximum);
	}
	int GetCapacity(const CvUnit* unit, const CvPlot* destination)
	{
		if (!unit)
			return 1;
		return GetCapacity(unit->getOwner(), unit->getDomainType(), destination && destination->isCity());
	}
	bool CanFlank(const CvUnit* unit)
	{
		return IsEnabled() && GetInt("FlankingEnabled", 1) && unit && unit->IsCombatUnit()
			&& unit->getDomainType() == DOMAIN_LAND && !unit->isCargo() && !unit->IsCanAttackRanged() && Role(unit, "FLANK") > 0;
	}
	bool IsAntiCavalry(const CvUnit* unit)
	{
		return IsEnabled() && unit && unit->IsCombatUnit() && unit->getDomainType() == DOMAIN_LAND && !unit->isCargo() && Role(unit, "ANTI_CAVALRY") > 0;
	}
	bool IsFlankTarget(const CvUnit* unit)
	{
		return IsEnabled() && unit && unit->IsCombatUnit() && unit->getDomainType() == DOMAIN_LAND && !unit->isCargo() && Role(unit, "FLANK_TARGET") > 0;
	}
	int GetCollateralTargetLimit(const CvUnit* unit)
	{
		return IsEnabled() && GetInt("CollateralEnabled", 1) && unit ? Role(unit, "COLLATERAL_LIMIT") : 0;
	}
	bool IsCollateralTargetDomain(DomainTypes domain)
	{
		if (!IsEnabled() || !GetInt("CollateralEnabled", 1))
			return false;
		std::map<int, int>::const_iterator it = Cache().targetDomains.find(domain);
		return it != Cache().targetDomains.end() && it->second != 0;
	}
	int GetCityProtection(const CvCity* city, int extraCityDamage)
	{
		if (!IsEnabled() || !city)
			return 0;
		// Specific rows replace inherited class values, including zero. Only
		// database rules are cached: constructed/free/captured buildings are live.
		int protection = 0;
		const int maximum = GetInt("CityProtectionMaximumPercent", 90);
		CvCityBuildings* buildings = city->GetCityBuildings();
		for (std::map<int, int>::const_iterator it = Cache().effectiveBuildingProtection.begin(); it != Cache().effectiveBuildingProtection.end(); ++it)
		{
			const int count = buildings->GetNumBuilding((BuildingTypes)it->first);
			if (count <= 0)
				continue;
			protection += it->second * std::min(count, maximum);
			if (protection >= maximum)
				break;
		}
		return CvStackingAIPolicy::CityProtection(protection, maximum, city->GetMaxHitPoints() - city->getDamage() - max(0,extraCityDamage),
			city->GetMaxHitPoints(), GetInt("CityProtectionScalesWithHP", 1) != 0);
	}
}
