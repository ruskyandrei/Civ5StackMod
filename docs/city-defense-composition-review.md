# City defender composition under stacking

Recorded 2026-09-30 after the user observed four melee and one ranged unit in a city and asked whether more ranged defenders would be useful. Source review and TODO only; no gameplay/default/deployment changes or game interaction.

## What stacked occupants actually contribute

City attacks retain VP's unit-versus-city combat path. `CvUnitCombat::GenerateMeleeCombatInfo` (around line 404), ranged city combat (around line 948) and air city combat use the city plus its single designated garrison. They do not resolve a series of normal unit-versus-unit fights against every melee occupant. The ordinary stack best-defender selector applies to unit combat outside this city branch; additional melee occupants do not each become a separate mandatory defender before city capture.

`CvCity::updateStrengthValue` (around line 27609) adds the contribution of one `GetGarrisonedUnit`, based on the greater of its base melee and ranged strength and the appropriate domain divisor. Other occupants' strengths are not summed into city combat strength. A ranged unit can be that designated garrison: the passive bonus does not require a melee unit. `CvPlot::getBestGarrison` (around line 3604) selects an eligible unit by that contribution.

VP's enabled garrison absorption also uses only that one unit. `CvUnit::getMeleeCombatDamageCity` and `GetRangeCombatDamage` divide some primary damage between the city and the designated garrison; our collateral logic can separately damage other occupants. The absorption share does not multiply with the number of melee occupants. `CvUnitCombat::ApplyExtraUnitDamage` replaces a killed designated garrison with another eligible occupant when available. Extra melee can therefore provide replacement depth and can counterattack, break a blockade, protect nearby tiles or rotate out, but those are distinct active/reserve tasks. They are not equivalent to several additional ranged attacks each turn.

Ranged units stationed on the city can each attack eligible targets under their normal movement/range/attack rules. With multiple units, this gives additional damage against approaching attackers. The planned city-bombardment toggle removes only the city's own attack; it will make the composition and availability of actual ranged defenders more significant. The city's melee retaliation against a melee attacker is a separate existing combat behavior.

## Current allocation gap

`CvStackingAI::GarrisonScore` (around line 71) already gives non-siege ranged units a configurable preference. `RetentionOrder` also favors units free of army assignments and includes an anti-cavalry preference when cavalry is nearby. These are selection preferences, not a required role mix.

`AssessCity`, `RetainCityUnit` and `NeedsCityDefender` (around lines 133–229) still assess generic enemy/friendly strength and stop reserving/requesting troops once the count/strength requirement is met. Summing several melee occupants can meet that requirement without sufficient defensive firepower, even though those units do not all contribute passive city strength. The model does not separately value the designated garrison, additional usable ranged attacks, replacements and intended counterattacks.

The default reservation cap is three land defenders, also bounded by stack capacity. A physical stack of five does not necessarily mean five reserved defenders: army assembly, newly produced units, healing and transit can put additional troops on the city. The observation needs unit-role/commitment diagnostics before attributing every occupant to permanent defense.

## Planned composition policy

- For a threatened city, prefer a useful designated garrison and a ranged-heavy defending force, reserving additional melee for a concrete counterattack, replacement or nearby screen task. Do not impose a melee requirement where a ranged garrison provides adequate strength and survival. Safe rear cities still need only economical appropriate coverage.
- Separate passive city/garrison strength and damage absorption from expected defensive ranged damage, counterattack/blockade relief, garrison replacement depth and air/naval defense. Value the marginal benefit of each additional unit using legitimate threat/route information and bounded forecasts rather than counting every occupant as another full city defender.
- Request/produce missing ranged defense even when generic melee strength is sufficient; distinguish ordinary ranged defense from siege weapons committed to offensives. Preserve urgent exceptions when available melee is the only immediate reinforcement, and retain suitable field/anti-cavalry screens where they can actually participate.
- Make ranged/melee desired shares, role minima/maxima, reserve allowances, health/readiness margins, role priorities and forecast budgets XML-configurable. Coordinate role claims with offensive commitments, healing and production so city defense does not unnecessarily consume assault troops.
- Add compact city-role/commitment and designated-garrison summaries, including intended counterattack/replacement roles, without repeated per-occupant forecasts. Test one ranged garrison, one strong garrison plus several ranged, four melee plus one ranged, garrison death/replacement, melee counterattack/blockade relief, ranged-only and melee-only availability, collateral exposure, transit/healing armies and city bombardment on/off. Compare actual city damage, defensive shots, survival, freed frontline troops and planning cost.

The user's suggested ranged priority is supported by the mechanics, but several melee can still be justified for specific active/reserve duties. The implementation should determine what each unit contributes rather than use a fixed universal city stack composition.
