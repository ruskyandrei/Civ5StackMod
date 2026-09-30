static bool IsStackCombatCandidate(const CvUnit* pUnit, const SUnitIDValueContainer& extraDamage)
{
	return pUnit && pUnit->IsCanDefend() && !pUnit->isCargo() &&
		pUnit->getDomainType() != DOMAIN_AIR && !pUnit->IsDead() && !pUnit->isDelayedDeath() &&
		pUnit->GetCurrHitPoints() > extraDamage.GetValue(pUnit->GetID());
}

static void GetStackExchange(const CvUnit* pAttacker, const CvUnit* pDefender,
	const CvPlot* pFromPlot, const CvPlot* pTargetPlot, bool bRangedAttack,
	int iExtraAttackerDamage, int iExtraDefenderDamage, int& iDamage, int& iRetaliation)
{
	iDamage = 0;
	iRetaliation = 0;
	if (bRangedAttack || pAttacker->getDomainType() == DOMAIN_AIR)
	{
		int iUnused = 0;
		iDamage = pAttacker->GetRangeCombatDamage(pDefender, NULL, 0, iUnused, false,
			iExtraAttackerDamage, iExtraDefenderDamage, pTargetPlot, pFromPlot, false, false);
		if (pAttacker->getDomainType() == DOMAIN_AIR)
			iRetaliation = pDefender->GetAirStrikeDefenseDamage(pAttacker, false, pTargetPlot);
	}
	else
	{
		int iAttack = pAttacker->GetMaxAttackStrength(pFromPlot, pTargetPlot, pDefender,
			false, false, iExtraAttackerDamage, iExtraDefenderDamage);
		int iDefense = pDefender->GetMaxDefenseStrength(pTargetPlot, pAttacker, pFromPlot,
			false, false, iExtraDefenderDamage);
		iDamage = pAttacker->getMeleeCombatDamage(iAttack, iDefense, iRetaliation, false,
			pDefender, iExtraAttackerDamage, iExtraDefenderDamage);
	}
}

const CvUnit* CvUnitCombat::SelectStackDefender(const CvUnit* pAttacker, const CvPlot* pFromPlot,
	const CvPlot* pTargetPlot, const std::vector<const CvUnit*>& candidates,
	const SUnitIDValueContainer& extraDamage, bool bRangedAttack, int iExtraAttackerDamage)
{
	if (!pAttacker || !pTargetPlot)
		return NULL;
	if (!pFromPlot)
		pFromPlot = pAttacker->plot();

	const bool bUseStackRules = CvStacking::IsEnabled() && CvStacking::GetInt("DefenderSelectionEnabled", 1) != 0;
	const bool bCanFlank = bUseStackRules && !bRangedAttack && CvStacking::CanFlank(pAttacker);
	bool bHasExposedTarget = false;
	bool bHasInterceptor = false;
	for (size_t i = 0; i < candidates.size(); ++i)
	{
		const CvUnit* pUnit = candidates[i];
		if (!IsStackCombatCandidate(pUnit, extraDamage))
			continue;
		bHasExposedTarget = bHasExposedTarget || CvStacking::IsFlankTarget(pUnit);
		bHasInterceptor = bHasInterceptor || CvStacking::IsAntiCavalry(pUnit);
	}

	const CvUnit* pBest = NULL;
	bool bBestSurvives = false;
	int iBestExchange = INT_MIN;
	int iBestRemainingHP = 0;
	int iBestMaxHP = 1;
	for (size_t i = 0; i < candidates.size(); ++i)
	{
		const CvUnit* pUnit = candidates[i];
		if (!IsStackCombatCandidate(pUnit, extraDamage) || pUnit == pAttacker)
			continue;
		if (bCanFlank && bHasExposedTarget &&
			!(bHasInterceptor ? CvStacking::IsAntiCavalry(pUnit) : CvStacking::IsFlankTarget(pUnit)))
			continue;
		if (!bUseStackRules)
		{
			if (pUnit->isBetterDefenderThan(pBest, pAttacker))
				pBest = pUnit;
			continue;
		}

		int iDamage = 0, iRetaliation = 0;
		int iExtraDefenderDamage = extraDamage.GetValue(pUnit->GetID());
		GetStackExchange(pAttacker, pUnit, pFromPlot, pTargetPlot, bRangedAttack,
			iExtraAttackerDamage, iExtraDefenderDamage, iDamage, iRetaliation);
		int iHP = max(0, pUnit->GetCurrHitPoints() - iExtraDefenderDamage);
		int iRemainingHP = max(0, iHP - iDamage);
		bool bSurvives = iRemainingHP > 0;
		int iExchange = min(iRetaliation, max(0, pAttacker->GetCurrHitPoints() - iExtraAttackerDamage)) - min(iDamage, iHP);
		int iMaxHP = max(1, pUnit->GetMaxHitPoints());
		bool bBetter = !pBest || (bSurvives != bBestSurvives ? bSurvives :
			iExchange != iBestExchange ? iExchange > iBestExchange :
			static_cast<int64>(iRemainingHP) * iBestMaxHP != static_cast<int64>(iBestRemainingHP) * iMaxHP ? static_cast<int64>(iRemainingHP) * iBestMaxHP > static_cast<int64>(iBestRemainingHP) * iMaxHP :
			pUnit->getOwner() != pBest->getOwner() ? pUnit->getOwner() < pBest->getOwner() : pUnit->GetID() < pBest->GetID());
		if (bBetter)
		{
			pBest = pUnit;
			bBestSurvives = bSurvives;
			iBestExchange = iExchange;
			iBestRemainingHP = iRemainingHP;
			iBestMaxHP = iMaxHP;
		}
	}
	return pBest;
}

// City bombardment uses the same survival / damage-exchange ordering as unit
// attacks, with no cavalry bypass and no retaliation against the city.
const CvUnit* CvUnitCombat::SelectStackDefenderForCity(const CvCity* pAttacker, const CvPlot* pTargetPlot,
 const std::vector<const CvUnit*>& candidates, const SUnitIDValueContainer& extraDamage)
{
 if (!pAttacker || !pTargetPlot)
  return NULL;
 const bool enabled = CvStacking::IsEnabled() && CvStacking::GetInt("DefenderSelectionEnabled", 1) != 0;
 const CvUnit* best = NULL;
 bool bestSurvives = false;
 int bestLoss = INT_MAX, bestRemaining = 0, bestMaxHP = 1;
 for (size_t i = 0; i < candidates.size(); ++i)
 {
  const CvUnit* unit = candidates[i];
  if (!IsStackCombatCandidate(unit, extraDamage) || !unit->isEnemy(pAttacker->getTeam(), pTargetPlot)
   || unit->isInvisible(pAttacker->getTeam(), false))
   continue;
  if (MOD_GLOBAL_SUBS_UNDER_ICE_IMMUNITY && unit->getInvisibleType() == 0 && pTargetPlot->getFeatureType() == FEATURE_ICE)
   continue;
  if (!enabled)
  {
   if (unit->isBetterDefenderThan(best, NULL)) best = unit;
   continue;
  }
  const int hp = unit->GetCurrHitPoints() - extraDamage.GetValue(unit->GetID());
  const int hit = pAttacker->rangeCombatDamage(unit, false, pTargetPlot, false, extraDamage.GetValue(unit->GetID()));
  const int remaining = max(0, hp - hit);
  const int loss = min(hp, hit);
  const bool survives = remaining > 0;
  const int maxHP = max(1, unit->GetMaxHitPoints());
  const bool better = !best || (survives != bestSurvives ? survives : loss != bestLoss ? loss < bestLoss :
   static_cast<int64>(remaining) * bestMaxHP != static_cast<int64>(bestRemaining) * maxHP ?
   static_cast<int64>(remaining) * bestMaxHP > static_cast<int64>(bestRemaining) * maxHP : unit->GetID() < best->GetID());
  if (better)
  { best = unit; bestSurvives = survives; bestLoss = loss; bestRemaining = remaining; bestMaxHP = maxHP; }
 }
 return best;
}

