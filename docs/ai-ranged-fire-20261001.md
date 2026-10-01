# Ranged fire discipline and naval targets — 1 October 2026

Follow-up to the campaign-102 notes in `stacking-todo.md`. The user wants
ranged and siege units to fire whenever they can and don't need to heal or
retreat. That applies to enemy units and stacks as well as cities.

## Changes

1. **Stationary city fire.** A ranged unit shooting a city from the tile it
   already occupies is no longer held to the zero-danger staging rule.
   - **Early siege pass and tactical search:** the real stack's forecast danger
     is compared with `AIStationaryFireDangerPercent` (50) of the shooter's
     current HP.
   - **Plan execution:** an executed plan isn't re-vetoed after other planned
     units leave the stack. That would only force a re-plan.
   - **Logging:** refusals are logged once per unit and turn as `FIRE_REFUSAL`.
   - **Off switch:** 0 restores the previous rule.
2. **End-of-turn ranged fire** (`AIEndTurnRangedFireEnabled`, default 1).
   - **When:** after the tactical and homeland AI have moved a player's units.
   - **Who:** every idle ranged unit, meaning no queued mission, an unused
     attack, and not needing to heal.
   - **What:** it fires from where it stands at a visible enemy unit, stack or
     city in range. A unit that stays put loses nothing by firing.
   - **Target choice:**
     - a predicted kill first, using stacking defender selection and the damage
       preview;
     - otherwise siege units prefer the weakest city;
     - other ranged units prefer the defender losing the largest share of its HP;
     - each falls back to the other kind of target.
   - **Skipped:** futile sieges (`ContinueSiege`) and cities at 1 HP.
   - **Logging:** `END_TURN_FIRE`.
3. **Naval and combined operation targets.** VP stores a coastal water tile
   within two rings of the target city. `CityTarget` keeps the adjacent match
   and now also accepts a unique enemy city in the second ring; if there are two
   candidates, it leaves the target unresolved.

Why the end-of-turn pass is needed: forecast danger sums every enemy that could
attack a tile, so it often exceeds a unit's HP. On turns 269–271, Babylon's
siege units at tile 3803 were refused city shots with forecast danger 100–140
against 100 HP. They stayed in place, unharmed, every turn.

## Evidence (same save, same seed)

Campaign-102 autosave from turn 260, replayed to 272 with Summary diagnostics
(`work/test-runs/ai-c102-*-260-272`, compared with `work/compare-offense.py`):

| Turns 260–271 | C5 (previous rules) | C7 (this change) |
|---|---:|---:|
| City attacks | 72 | 169 |
| City damage | 1,739 | 3,807 |
| All combats | 600 | 816 |
| Damage to units | 17,084 | 20,721 |
| Cities captured | 2 (T261, T264) | 3 (T261, T266, T271) |
| Average turn | 21.7 s | 22.3 s |

The captures are all player 6 taking player 7's cities. In C5, player 6's city
pressure nearly stops after its second capture (1–7 city shots per turn). In C7
it continues at 14–21 per turn and takes a third city. These are single runs
whose games diverge after the first changed action. They are behavior evidence,
not statistics.

## Assault readiness: thresholds are not the main blocker

A third arm relaxed `AIAssaultStrengthPercent` 125→100,
`AIAssaultIncompleteDamagePercent` 125→100 and `AIAssaultDamageHorizon` 4→5.
- The values loaded, and some failure masks lost their strength bit.
- But every action, capture and plan phase was identical to C7.
- The XML was restored afterwards.

The most common failure masks, out of 130 `ASSAULT_PLAN` rows, are:
- 30 (31 rows): siege, count, strength and damage;
- 63: every role missing;
- 191: the same plus unknown paths.

Desired forces are large: 22 units and 6 siege units at capacity 7. Siege units
counted for the objective are often not in the cohesive first wave
(`waveSiege=0` while `siege=3`). Slow siege arrival and wave composition need
investigating before thresholds.

## Not changed

`CvArmyAI::GetDomainType` returns DOMAIN_SEA for ARMY_TYPE_COMBINED, so the
combined-invasion readiness and core counts ignore embarked land units. The
replayed window has no combined operation to test a fix against; see
`stacking-todo.md`.
