"""Apply the stacking-independent fixes and performance changes to an upstream VP checkout.

Usage: python port.py <upstream worktree> <stacking checkout>
Every replacement asserts its expected match count; nothing is written unless all succeed.
"""
from pathlib import Path
import re, sys

WT = Path(sys.argv[1]); MAIN = Path(sys.argv[2])
D = 'CvGameCoreDLL_Expansion2/'
files = {}


def load(name):
    if name not in files:
        raw = (WT / name).read_bytes()
        bom = raw.startswith(b'\xef\xbb\xbf')
        text = raw[3:].decode('utf-8') if bom else raw.decode('utf-8')
        crlf = '\r\n' in text
        files[name] = [text.replace('\r\n', '\n'), bom, crlf]
    return files[name]


def rep(name, old, new, count=1, after=None):
    entry = load(name); text = entry[0]
    start = 0
    if after is not None:
        start = text.index(after)
    head, tail = text[:start], text[start:]
    found = tail.count(old)
    if after is not None:
        assert found >= 1, (name, old[:70], found)
        tail = tail.replace(old, new, count)
    else:
        assert found == count, (name, old[:70], found)
        tail = tail.replace(old, new)
    entry[0] = head + tail


def resub(name, pattern, new, count=1):
    entry = load(name)
    text, n = re.subn(pattern, lambda m: new, entry[0], flags=re.S)
    assert n == count, (name, pattern[:70], n)
    entry[0] = text


# ---------------- bug fixes ----------------
# Muster cities are our own cities; the inverted test made this always false.
rep(D + 'CvMilitaryAI.cpp',
    'bool CvMilitaryAI::IsPossibleMusterCity(const CvCity* pCity, ArmyType eArmyType) const\n{\n\tif (!pCity || pCity->getOwner() == m_pPlayer->GetID())',
    'bool CvMilitaryAI::IsPossibleMusterCity(const CvCity* pCity, ArmyType eArmyType) const\n{\n\tif (!pCity || pCity->getOwner() != m_pPlayer->GetID())')

T = D + 'CvTacticalAI.cpp'
# Extra city damage was passed the garrison's damage.
rep(T, 'true, iSelfDamage, iPrevUnitDamage, iPrevUnitDamage, true, true, pEnemyUnit);',
    'true, iSelfDamage, iPrevCityDamage, iPrevUnitDamage, true, true, pEnemyUnit);')
# Bounds check must precede the element access.
rep(T, 'while (gPossibleMoves[nMaxCount].score == gPossibleMoves[nMaxCount - 1].score && (size_t)nMaxCount < gPossibleMoves.size())',
    'while ((size_t)nMaxCount < gPossibleMoves.size() && gPossibleMoves[nMaxCount].score == gPossibleMoves[nMaxCount - 1].score)', 2)
# A cache hit was counted as a miss.
rep(T, '\t\tiDamageTaken = it->second[2];\n\t\tgAttackCacheMiss++;', '\t\tiDamageTaken = it->second[2];\n\t\tgAttackCacheHit++;')
# Unsigned reverse loops must not rely on i >= 0.
rep(T, '\tfor (size_t i = ref->GetNumAssignments() - 1; i >= ref->getFirstInterestingAssignment(); i--)\n\t{\n',
    '\tfor (size_t cursor = ref->GetNumAssignments(); cursor > ref->getFirstInterestingAssignment(); )\n\t{\n\t\tconst size_t i = --cursor;\n')
rep(T, '\tfor (size_t i = assignedMoves_r.size() - 1; i >= nFirstInterestingAssignment; i--)\n\t\tif (assignedMoves_r[i].iUnitID == iUnitID)\n\t\t{\n\t\t\teUnitAssignmentType eAssignment',
    '\tfor (size_t cursor = assignedMoves_r.size(); cursor > nFirstInterestingAssignment; )\n\t{\n\t\tconst size_t i = --cursor;\n\t\tif (assignedMoves_r[i].iUnitID == iUnitID)\n\t\t{\n\t\t\teUnitAssignmentType eAssignment')
rep(T, '\t\t\t\treturn &(assignedMoves_r[i]);\n\t\t}\n\n\treturn NULL;\n}\n\nconst STacticalAssignment* CvBasePosition::getLatestAssignment(int iUnitID) const',
    '\t\t\t\treturn &(assignedMoves_r[i]);\n\t\t}\n\t}\n\n\treturn NULL;\n}\n\nconst STacticalAssignment* CvBasePosition::getLatestAssignment(int iUnitID) const')
rep(T, 'nFirstInterestingAssignment = (unsigned char)i;', 'nFirstInterestingAssignment = i;')
rep(D + 'CvTacticalAI.h', 'unsigned char nFirstInterestingAssignment;', 'size_t nFirstInterestingAssignment;')
# A unit killed by an earlier assignment must not execute a later one.
rep(T, 'if (!pUnit || pUnit->isDelayedDeath() || pUnit->plot()==NULL)', 'if (!pUnit || pUnit->IsDead() || pUnit->isDelayedDeath() || pUnit->plot()==NULL)', 1,
    after='bool TacticalAIHelpers::ExecuteUnitAssignments(')

U = D + 'CvUnit.cpp'
# Projected damage: the attacker's was ignored, the defender's and attacker's were swapped.
rep(U, 'pFromPlot, pTargetPlot, bIgnoreUnitAdjacencyBoni, bQuickAndDirty);\n\tif (iAttackerStrength==0)',
    'pFromPlot, pTargetPlot, bIgnoreUnitAdjacencyBoni, bQuickAndDirty, iAssumeExtraSelfDamage, iAssumeExtraDefenderDamage);\n\tif (iAttackerStrength==0)')
rep(U, 'pDefender->GetMaxRangedCombatStrength(this, /*pCity*/ NULL, false, pTargetPlot, pFromPlot, false, bQuickAndDirty, iAssumeExtraSelfDamage, iAssumeExtraDefenderDamage);',
    'pDefender->GetMaxRangedCombatStrength(this, /*pCity*/ NULL, false, pTargetPlot, pFromPlot, false, bQuickAndDirty, iAssumeExtraDefenderDamage, iAssumeExtraSelfDamage);')

C = D + 'CvCity.cpp'
# bAllowCenterPlot=false still offered the city plot through the ring loop.
rep(C, '\tvector<CvPlot*> validChoices;\n\tfor (int i = 0; i < RING1_PLOTS; i++)', '\tvector<CvPlot*> validChoices;\n\tfor (int i = bAllowCenterPlot ? 0 : 1; i < RING1_PLOTS; i++)', 1,
    after='CvPlot* CvCity::GetPlotForNewUnit(')

O = D + 'CvAIOperation.cpp'
rep(O, 'CvMultiUnitFormationInfo* pkFormation = pThisArmy->GetFormation();', 'CvMultiUnitFormationInfo* pkFormation = pThisArmy ? pThisArmy->GetFormation() : NULL;', 1,
    after='void CvAIOperation::UnitWasRemoved(')
rep(O, '\t\t\tif (fX < iGatherTolerance && fY < iGatherTolerance)\n', '\t\t\tif (pCoM && fX < iGatherTolerance && fY < iGatherTolerance)\n')

# A captured/upgraded/reserve-filled slot must not lose its current member.
rep(D + 'CvPlayerAI.cpp', '\t\tpThisArmy->AddUnit(pThisUnit->GetID(), thisSlot.m_iSlotID, pThisArmy->GetSlotInfo(thisSlot.m_iSlotID).m_requiredSlot);\n\t\tpThisOperation->FinishedBuildingUnit(thisSlot);',
    '\t\tif (thisSlot.m_iSlotID >= 0 && (size_t)thisSlot.m_iSlotID < pThisArmy->GetNumFormationEntries() && pThisArmy->GetSlotStatus(thisSlot.m_iSlotID)->IsFree())\n\t\t\tpThisArmy->AddUnit(pThisUnit->GetID(), thisSlot.m_iSlotID, pThisArmy->GetSlotInfo(thisSlot.m_iSlotID).m_requiredSlot);\n\t\tpThisOperation->FinishedBuildingUnit(thisSlot);')

# Dead units are not defenders.
rep(D + 'CvPlot.cpp', 'if(pLoopUnit && (bNoncombatAllowed || pLoopUnit->IsCanDefend()) && pLoopUnit != pAttacker)',
    'if(pLoopUnit && !pLoopUnit->IsDead() && !pLoopUnit->isDelayedDeath() && (bNoncombatAllowed || pLoopUnit->IsCanDefend()) && pLoopUnit != pAttacker)')

# City capture/destruction: defer Lua hooks until the city is consistent again.
rep(C, '\tPreKill();\n\n\t// Delete the city\'s information here!!!',
    '\t// The dying city is inconsistent until it is deleted; Lua hooks would\n\t// release the game core lock and let UI scripts read it (see\n\t// LuaSupport::DeferredHookScope). They run after the deletion instead.\n\tLuaSupport::DeferredHookScope kDeferHooks;\n\tPreKill();\n\n\t// Delete the city\'s information here!!!')
rep(C, '\tGET_PLAYER(eOwner).GetCityConnections()->SetDirty();\n\n\t// clean up\n\tPostKill(',
    '\tGET_PLAYER(eOwner).GetCityConnections()->SetDirty();\n\tkDeferHooks.Flush();\n\n\t// clean up\n\tPostKill(')
P = D + 'CvPlayer.cpp'
rep(P, '\t// Prepare the city to be destroyed\n\tpCity->PreKill();',
    '\t// From here until the new city is complete, the plot\'s city is inconsistent:\n\t// population 0, then deleted, then rebuilt. Lua hooks release the game core\n\t// lock and let UI scripts read it (crash in CvCity::GetStaticYield), so\n\t// they are queued and run just before CityCaptureComplete.\n\tLuaSupport::DeferredHookScope kDeferHooks;\n\n\t// Prepare the city to be destroyed\n\tpCity->PreKill();')
rep(P, '\t// Update events\n\tICvEngineScriptSystem1* pkScriptSystem = gDLL->GetScriptSystem();', '\t// Update events\n\tkDeferHooks.Flush();\n\tICvEngineScriptSystem1* pkScriptSystem = gDLL->GetScriptSystem();')
L = D + 'Lua/CvLuaSupport.cpp'
rep(L, '#include "../CvStackingDiagnostics.h"\n', '')
resub(L, r'\tif \(!vHooks\.empty\(\) \|\| s_iDeferredHookRefused > 0\)\n\t\tCvStackingDiagnostics::Record\(.*?\);\n(?=\ts_iDeferredHookRefused = 0;)', '')

# ---------------- performance ----------------
# UNITCOMBAT_MOUNTED: one lookup instead of a string search per strength query.
rep(U, 'UnitCombatTypes mountedCombat = static_cast<UnitCombatTypes>(GC.getInfoTypeForString("UNITCOMBAT_MOUNTED", true));', 'UnitCombatTypes mountedCombat = MountedUnitCombatType();', 5)
rep(U, 'int CvUnit::GetGenericMeleeStrengthModifier(const CvUnit* pOtherUnit, const CvPlot* pBattlePlot, bool bAttacking,',
    '''// Combat strength code runs very often during AI turns; avoid a string lookup
// per call. Info type IDs are fixed once the database is loaded.
static UnitCombatTypes MountedUnitCombatType()
{
	static UnitCombatTypes eMounted = NO_UNITCOMBAT;
	static bool bResolved = false;
	if (!bResolved)
	{
		eMounted = static_cast<UnitCombatTypes>(GC.getInfoTypeForString("UNITCOMBAT_MOUNTED", true));
		bResolved = GC.getNumUnitCombatClassInfos() > 0;
	}
	return eMounted;
}

int CvUnit::GetGenericMeleeStrengthModifier(const CvUnit* pOtherUnit, const CvPlot* pBattlePlot, bool bAttacking,''')
# Hit point getters inline.
resub(U, r'int CvUnit::GetMaxHitPoints\(\) const\n\{.*?\n\}\n\n\n//\t-+\nint CvUnit::GetCurrHitPoints\(\)\s*const\n\{.*?\n\}\n', '// GetMaxHitPoints and GetCurrHitPoints are inline in CvUnit.h.\n')
resub(U, r'int CvUnit::getDamage\(\) const\n\{.*?\n\}\n', '// getDamage is inline in CvUnit.h.\n')
H = D + 'CvUnit.h'
rep(H, '\tint GetMaxHitPoints() const;\n\tint GetCurrHitPoints() const;',
    '''	// Inline: called very often from other translation units.
	int GetMaxHitPoints() const
	{
		VALIDATE_OBJECT();
		int iMaxHP = m_iMaxHitPointsBase;
		iMaxHP *= (100 + m_iMaxHitPointsModifier);
		iMaxHP /= 100;
		iMaxHP += m_iMaxHitPointsChange;
		return iMaxHP;
	}
	int GetCurrHitPoints() const
	{
		VALIDATE_OBJECT();
		return (GetMaxHitPoints() - getDamage());
	}''')
rep(H, '\tint getDamage() const;', '\tint getDamage() const\n\t{\n\t\tVALIDATE_OBJECT();\n\t\treturn m_iDamage;\n\t}')
rep(H, '\t\t\t\t// promote to vector\n', '\t\t\t\t// promote to vector; one allocation covers the common small cases\n\t\t\t\tm_aExtraStorage.reserve(4);\n', 2)

# Ranged-attack plots: sorted unique vector built with a plot bitmap instead of a std::set.
rep(T, '''std::set<int> TacticalAIHelpers::GetPlotsUnderRangedAttackFrom(const CvUnit* pUnit, ReachablePlots& basePlots, bool bOnlyWithEnemy, bool bIgnoreVisibility)
{
	std::set<int> resultSet;

	if (!pUnit || !pUnit->IsCanAttackRanged())
		return resultSet;
''', '''vector<int> TacticalAIHelpers::GetPlotsUnderRangedAttackFrom(const CvUnit* pUnit, ReachablePlots& basePlots, bool bOnlyWithEnemy, bool bIgnoreVisibility)
{
	vector<int> resultSet;

	if (!pUnit || !pUnit->IsCanAttackRanged() || basePlots.empty())
		return resultSet;

	// Ascending and unique, like the std::set this replaced, without one tree node per
	// attackable plot. The bitmap answers the "already attackable" test.
	vector<bool> attackable(GC.getMap().numPlots(), false);
''')
rep(T, 'if (!pLoopPlot || resultSet.find(pLoopPlot->GetPlotIndex())!=resultSet.end())', 'if (!pLoopPlot || attackable[pLoopPlot->GetPlotIndex()])')
rep(T, '\t\t\t\t\tresultSet.insert(pLoopPlot->GetPlotIndex());\n\t\t}\n\t}\n\n\treturn resultSet;',
    '\t\t\t\t{\n\t\t\t\t\tattackable[pLoopPlot->GetPlotIndex()] = true;\n\t\t\t\t\tresultSet.push_back(pLoopPlot->GetPlotIndex());\n\t\t\t\t}\n\t\t}\n\t}\n\n\tstd::sort(resultSet.begin(), resultSet.end());\n\treturn resultSet;')
rep(T, '\t\tstd::set<int> attackableTiles = TacticalAIHelpers::GetPlotsUnderRangedAttackFrom(pUnit,reachablePlots,true,false);\n\t\tfor (std::set<int>::const_iterator attackTile',
    '\t\tconst vector<int> attackableTiles = TacticalAIHelpers::GetPlotsUnderRangedAttackFrom(pUnit,reachablePlots,true,false);\n\t\tfor (vector<int>::const_iterator attackTile')
rep(D + 'CvTacticalAI.h', 'std::set<int> GetPlotsUnderRangedAttackFrom(const CvUnit* pUnit, ReachablePlots& basePlots, bool bOnlyWithEnemy,  bool bIgnoreVisibility);',
    'vector<int> GetPlotsUnderRangedAttackFrom(const CvUnit* pUnit, ReachablePlots& basePlots, bool bOnlyWithEnemy,  bool bIgnoreVisibility); //sorted, unique')
G = D + 'CvDangerPlots.cpp'
rep(G, 'std::set<int> attackableTiles = TacticalAIHelpers::GetPlotsUnderRangedAttackFrom(pLoopUnit,reachablePlots,false,false);', 'const vector<int> attackableTiles = TacticalAIHelpers::GetPlotsUnderRangedAttackFrom(pLoopUnit,reachablePlots,false,false);')
rep(G, 'for (std::set<int>::iterator attackTile=attackableTiles.begin()', 'for (vector<int>::const_iterator attackTile=attackableTiles.begin()')
rep(D + 'CvDangerPlots.h', '{ m_apUnits = DangerUnitVector(); m_apUnits.reserve(5); }', '{ DangerUnitVector().swap(m_apUnits); m_apUnits.reserve(5); }')

# Reachable-plot cache lookups borrow the freed-plot list instead of copying it.
ours = (MAIN / D / 'CvTacticalAI.h').read_bytes().decode('utf-8-sig').replace('\r\n', '\n')
entry = load(D + 'CvTacticalAI.h')
a, b = 'struct SPathFinderStartPos\n', 'struct SIntPairHash'
assert entry[0].count(a) == 1 and entry[0].count(b) == 1 and ours.count(a) == 1 and ours.count(b) == 1
entry[0] = entry[0][:entry[0].index(a)] + ours[ours.index(a):ours.index(b)] + entry[0][entry[0].index(b):]
rep(T, 'gReachablePlotsLookup.find(SPathFinderStartPos(unit, freedPlots_r));', 'gReachablePlotsLookup.find(SPathFinderStartPos(unit, freedPlots_r, SPathFinderStartPos::LookupOnly()));', 2)

# Healing eligibility: ActualHealRate repeats the resource-shortage test.
rep(T, '!pUnit->IsCannotHeal(/*bConsiderResourceShortage*/ true) && !pUnit->isEmbarked())\n\t\t\t{\n\t\t\t\tint iHealRate = pUnit->ActualHealRate(pTestPlot, false);',
    '!pUnit->IsCannotHeal(/*bConsiderResourceShortage*/ false) && !pUnit->isEmbarked())\n\t\t\t{\n\t\t\t\tint iHealRate = pUnit->ActualHealRate(pTestPlot, false);')

# Containers returned by value.
rep(C, 'std::set<int> CvCity::GetPlotList() const', 'const std::set<int>& CvCity::GetPlotList() const')
rep(D + 'CvCity.h', '\tstd::set<int> GetPlotList() const;', '\tconst std::set<int>& GetPlotList() const;')
rep(C, 'std::map<int, std::map<int, int>> m_BuildingYieldsFromAccomplishments = pkBuildingInfo->GetYieldChangesFromAccomplishments();',
    'const std::map<int, std::map<int, int>>& m_BuildingYieldsFromAccomplishments = pkBuildingInfo->GetYieldChangesFromAccomplishments();')
rep(C, 'std::map<int, std::map<int, int>> m_BuildingModifiersFromAccomplishments = pkBuildingInfo->GetYieldModifiersFromAccomplishments();',
    'const std::map<int, std::map<int, int>>& m_BuildingModifiersFromAccomplishments = pkBuildingInfo->GetYieldModifiersFromAccomplishments();')

# Unit resource checks only visit resources the unit can need.
rep(P, '\tfor (int iResourceLoop = 0; iResourceLoop < GC.getNumResourceInfos(); iResourceLoop++)\n\t{\n\t\tconst ResourceTypes eResource = static_cast<ResourceTypes>(iResourceLoop);',
    '\tconst std::vector<int>* resourceIDs = pUnitInfo->GetResourceQuantityCheckIDs();\n\tfor (int iResourceCheck = 0; iResourceCheck < (resourceIDs ? (int)resourceIDs->size() : GC.getNumResourceInfos()); iResourceCheck++)\n\t{\n\t\tconst int iResourceLoop = resourceIDs ? (*resourceIDs)[iResourceCheck] : iResourceCheck;\n\t\tconst ResourceTypes eResource = static_cast<ResourceTypes>(iResourceLoop);',
    1, after='bool CvPlayer::HasResourceForNewUnit(')

# TContainer::Get lookup cache is used on the game core thread only.
K = D + 'CvGame.cpp'
rep(K, 'int GetNextGlobalID() { return GC.getGame().GetNextGlobalID(); }\n', 'int GetNextGlobalID() { return GC.getGame().GetNextGlobalID(); }\nunsigned long g_ulTContainerCacheThread = 0;\n')
rep(K, 'void CvGame::update()\n{\n', 'void CvGame::update()\n{\n\tg_ulTContainerCacheThread = GetCurrentThreadId(); // see TContainer::Get\n')

for name, (text, bom, crlf) in files.items():
    if crlf: text = text.replace('\n', '\r\n')
    (WT / name).write_bytes((b'\xef\xbb\xbf' if bom else b'') + text.encode('utf-8'))
print('patched', len(files), 'files')
