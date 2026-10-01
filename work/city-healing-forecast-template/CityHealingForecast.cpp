// Estimate healing at the target owner's next city turn from information the
// attacker can normally inspect. This does not perform healing or refresh data.
int CvCity::GetAssaultHealingForecast(PlayerTypes eObserver, int iExpectedCityDamage, bool* pCompleteInformation) const
{
	if (pCompleteInformation)
		*pCompleteInformation = false;
	if (eObserver < 0 || eObserver >= MAX_PLAYERS)
		return 0;
	const CvPlayer& kObserver = GET_PLAYER(eObserver);
	if (kObserver.isObserver())
		return 0;
	const bool bSameTeam = kObserver.getTeam() == getTeam();
	if (!bSameTeam && !isVisible(kObserver.getTeam(), false))
		return 0;

	iExpectedCityDamage = max(0, iExpectedCityDamage);
	if ((getDamage() <= 0 && iExpectedCityDamage == 0) || IsBlockadedWaterAndLand())
	{
		if (pCompleteInformation)
			*pCompleteInformation = true;
		return 0;
	}

	// CanOpenCityScreen's observer grant is excluded above. Its remaining foreign
	// grant is normal espionage permission, rather than debug/observer knowledge.
	const bool bCityDetails = bSameTeam || GC.getGame().CanOpenCityScreen(eObserver, const_cast<CvCity*>(this));
	int iHitsHealed = GD_INT_GET(CITY_HIT_POINTS_HEALED_PER_TURN);
	if (bCityDetails)
	{
		int iBuildingDefense = m_pCityBuildings->GetBuildingDefense();
		iBuildingDefense *= (100 + m_pCityBuildings->GetBuildingDefenseMod());
		iBuildingDefense /= 100;
		iHitsHealed += iBuildingDefense / 1000;
	}

	bool bComplete = bCityDetails;
	if (MOD_BALANCE_VP)
	{
		iHitsHealed += getPopulation();
		if (bSameTeam)
		{
			// setTurnActive flips damage history before doTurn heals cities. Widen
			// only the forecast arithmetic; ordinary bounded values match the
			// native integer 80/20 smoothing, including its rounding to zero.
			const long long iRecentDamage = ((static_cast<long long>(getDamageTakenThisTurn()) + iExpectedCityDamage) * 80 +
				static_cast<long long>(getDamageTakenLastTurn()) * 20) / 100;
			if (iRecentDamage == 0 && !GetCityCitizens()->AnyPlotBlockaded())
				iHitsHealed *= 3;
		}
		else if (iExpectedCityDamage < 2)
		{
			// City-screen espionage does not expose exact smoothed damage history
			// or the cached citizen blockade list. Two new HP damage alone makes
			// the native smoothed value nonzero; a smaller attack is uncertain.
			bComplete = false;
		}
	}

	if (bCityDetails && getProductionProcess() != NO_PROCESS)
	{
		CvProcessInfo* pkProcessInfo = GC.getProcessInfo(getProductionProcess());
		if (pkProcessInfo && (pkProcessInfo->getDefenseValue() != 0 || pkProcessInfo->getDefenseValuePerTurn() != 0))
		{
			int iDefenseValue = pkProcessInfo->getDefenseValue() + GetDefenseProcessTurns() * pkProcessInfo->getDefenseValuePerTurn();
			if (pkProcessInfo->getDefenseValueCap() > 0)
				iDefenseValue = min(iDefenseValue, pkProcessInfo->getDefenseValueCap());
			int iPile = getYieldRateTimes100(YIELD_PRODUCTION) * iDefenseValue;
			iHitsHealed += iPile / 10000;
		}
	}
	if (pCompleteInformation)
		*pCompleteInformation = bComplete;
	return iHitsHealed;
}
