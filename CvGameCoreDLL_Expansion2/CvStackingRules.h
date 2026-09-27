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
	int GetInt(const char* szName, int iFallback);
	int GetCapacity(const CvUnit* pUnit, const CvPlot* pDestination = NULL);
	int GetCapacity(PlayerTypes eOwner, DomainTypes eDomain, bool bInCity = false);
	bool CanFlank(const CvUnit* pUnit);
	bool IsAntiCavalry(const CvUnit* pUnit);
	bool IsFlankTarget(const CvUnit* pUnit);
	int GetCollateralTargetLimit(const CvUnit* pUnit);
	bool IsCollateralTargetDomain(DomainTypes eDomain);
	int GetCityProtection(const CvCity* pCity);
}

#endif
