#pragma once
#ifndef CV_STACKING_RULES_H
#define CV_STACKING_RULES_H

#include "CvEnums.h"
#include <cstddef>

class CvUnit;
class CvPlot;
class CvCity;

// Database configuration only is cached. Technology, promotions and buildings
// are read from live game state, so no additional save-game state is needed.
namespace CvStacking
{
	void ResetCache();
	bool IsEnabled();
	bool CityRangedAttacksEnabled();
	int GetInt(const char* szName, int iFallback);
	enum HotSettingKey
	{
		HOT_DefenderSelectionEnabled,
		HOT_FlankingEnabled,
		HOT_CollateralEnabled,
		HOT_DisableCityRangedAttacks,
		HOT_AIEnabled,
		HOT_BaseCapacity,
		HOT_MaximumCapacity,
		HOT_LandCapacityBonus,
		HOT_SeaCapacityBonus,
		HOT_CityCapacityBonus,
		HOT_MinorCapacityBonus,
		HOT_BarbarianCapacityBonus,
		HOT_CollateralPercent,
		HOT_CollateralHPFloorPercent,
		HOT_CollateralMinimumDamage,
		HOT_CityProtectionMaximumPercent,
		HOT_CityProtectionScalesWithHP,
		HOT_AIStackCollateralWeight,
		HOT_AIStackProtectionWeight,
		HOT_AIStackJoinBonus,
		HOT_AIStackAntiFlankBonus,
		HOT_AIStackConcentrationFreeUnits,
		HOT_AIStackConcentrationPenalty,
		HOT_AIStackLeaveProtectorPenalty,
		HOT_SETTING_COUNT
	};
	int GetIntByKey(HotSettingKey eKey, int iFallback);

	int GetCapacity(const CvUnit* pUnit, const CvPlot* pDestination = NULL);
	int GetCapacity(PlayerTypes eOwner, DomainTypes eDomain, bool bInCity = false);
	bool CanFlank(const CvUnit* pUnit);
	bool IsAntiCavalry(const CvUnit* pUnit);
	bool IsFlankTarget(const CvUnit* pUnit);
	int GetCollateralTargetLimit(const CvUnit* pUnit);
	bool IsCollateralTargetDomain(DomainTypes eDomain);
	int GetCityProtection(const CvCity* pCity, int iExtraCityDamage = 0);
}

#endif
