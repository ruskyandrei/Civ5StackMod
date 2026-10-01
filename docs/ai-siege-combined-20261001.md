# Siege units, bombardment and combined invasions — 1 October 2026

Follow-up to `ai-ranged-fire-20261001.md`. The user asked why siege units rarely
join assault waves and whether combined land-and-sea invasions count their land
troops.

## Findings

### Peer wars never reached the cities

Over campaign 102 (turns 0–269), the major civilizations' attacks on each other:

| Attacker → defender | Combats | City attacks |
|---|---:|---:|
| Mongolia → Carthage | 218 | 0 |
| Carthage → Mongolia | 251 | 0 |
| Carthage → Songhai | 215 | 0 |
| Morocco → Babylon | 163 | 0 |
| Mongolia → Rome | 91 | 0 |
| Songhai → Rome | 607 | 207 |

Songhai against a weak Rome made 8 of the 9 captures. Wars between evenly
matched civilizations were fought entirely in the field.

### Why: gathering units never come within range

While an assault plan is not ready, every unit near the target, siege included,
is moved to a staging tile with zero forecast danger. In campaign 102, 215 of 317
land staging tiles were 5–6 tiles from the city. From there:

- **Siege arrives late.** Siege units move 2 tiles per turn, so they are two
  turns from a firing tile. The first wave only counts units that can fire this
  turn or next (`AIAssaultFirstWaveMaximumTurns` 1). In the turn-260 replay, a
  third of siege units near objectives were two turns out, for example Morocco's
  seven siege units at Babylon (`waveSiege=0`) for five turns or more.
- **Defended cities never pass.** For objectives with at least four units
  present, the failing checks were:
  - damage within 4 turns: 100 of 137 plans;
  - strength (125% of the city plus defenders within two tiles): 88;
  - siege: 52.
  In the turn-260 replay, Mongolia had 18 units including 9 siege at
  Carthage's capital on turn 265 and failed only the strength check (wave
  strength 425 against 807 × 125%).
- **VP's zone gate adds to this.** A city whose tactical zone the enemy dominates
  is skipped before the assault logic runs (`CITY_GATE reason=enemy_dominance`):
  417 times for Mongolia and 288 for Carthage over the campaign.

The siege units are not missing from the armies (`SIEGE_ROSTER`, turns 260–270):
- they make up about a sixth of land units (160 of 968 unit-samples);
- two thirds are in operation armies or support commitments;
- two thirds are within eight tiles of an objective.

Nothing lets them approach while the assault is not ready.

### Combined invasions ignored their troops

`CvArmyAI::GetDomainType` reports DOMAIN_SEA for ARMY_TYPE_COMBINED. The pre-war
opening forecast, the at-war first-wave check and the objective bookkeeping all
filtered units by that domain, so they saw only the ships. Example from
campaign 102: Mongol operation 5307 sailed against Amsterdam (turns 188–221),
reached it on turn 213 and waited there for nine turns. Its war readiness never
passed: `capture=0` and `failedMask=25`, because the embarked troops (the only
capturers) and their strength were not counted. It was then abandoned.

## Changes

1. **Bombardment phase** (`AIAssaultBombardStrengthPercent` 60,
   `AIAssaultBombardMinimumRanged` 2).
   - **When:** an assault is not ready, but its force within reach has at least
     60% of the local enemy strength, at least two ranged or siege units, and
     their sustained damage exceeds the city's forecast healing.
   - **What:** the force advances with its escorts instead of staging. Ranged
     and siege units may fire at the city from wherever the tactical search puts
     them. Melee city attacks still wait for readiness or a capture.
   - **Effect:** city HP falls, so readiness follows. The opportunity rule drops
     the requirements once a city is at 30% HP or less.
2. **Dominance override** (`AIAssaultDominanceOverride` 1). A city in an
   enemy-dominated zone is still engaged when the local assault forecast finds
   a ready wave or a bombarding force (`CITY_GATE reason=dominance_override`).
3. **Combined armies count their troops.**
   - **Objectives:** the fleet and the troops each get their own domain's
     objective, both owned by the operation. Land reinforcements gather at the
     muster city, not at the fleet's water tile.
   - **Readiness:** the opening forecast and the first-wave check include
     embarked land units, with no damage forecast from the water, and apply the
     land siege rules. Ranged ships and land siege both fill the siege role.
4. **Diagnostics** (Summary level, every 5 turns):
   - `SIEGE_ROSTER`: where siege and other land units are (army, commitment,
     own city, healing, free) and their distance to the nearest land objective.
   - `ASSAULT_PLAN` adds `siegeEta=a/b/c/d` (siege units by turns to a firing
     tile) and `bombard`.

## Evidence

### Fresh game from turn 0 (same map and civilizations as campaign 102)

`work/run-fresh-campaign.ps1` with C9 (bombardment, dominance override, combined
armies) to turn 232, where it crashed (see below). It was continued with C10
(the crash fix) from its turn-230 autosave to turn 270. Compared with
`work/compare-campaigns.py`:

| | Campaign 102 | Fresh game (C9, then C10) |
|---|---:|---:|
| Cities captured by major civilizations, turns 0–270 | 8 (all Songhai) | 18 (seven civilizations) |
| Attacks on cities between major civilizations, turns 0–231 | 35 | 497 |
| Mongolia ↔ Carthage city attacks, turns 0–231 | 0 / 0 | 50 / 95 |
| Seconds per turn, turns 200–231 | 20.9 | 17.6 |
| Seconds per turn, turns 230–270 (C10) | — | 19.7 average, 28.5 peak |

Captures in the fresh game:
- Carthage took two Mongol cities, and Mongolia took one Carthaginian city.
- The Netherlands took two Arabian cities, Morocco three and Babylon two.
- Rome took a Songhai city and a city-state; Songhai took four Roman cities.
- Carthage also took a city-state, and Morocco retook a city from barbarians.

These are single games, whose courses diverge from the first different
decision, so they show behaviour rather than statistics.

Bombardment did most of the work: about 165 sampled assault plans were
bombarding. The
dominance override engaged only 28 cities, against about 2,300 dominance skips.

**Combined invasions.** Their pre-war readiness now counts the land troops: 14–23
units per operation instead of the ships alone. No pre-war combined invasion
reached its target in this game, so declaring war after landing is not yet
observed end to end.

### Turn-260 replay of campaign 102 (turns 260–269)

| | C7 | C8 (combined fix) | C9 (bombardment) |
|---|---:|---:|---:|
| Combats | 720 | 677 | 797 |
| City attacks | 137 | 145 | 156 |
| Captures | 2 | 3 | 3 |
| Average turn (260–271) | 22.3 s | 23.0 s | 24.0 s |

In C9, Morocco bombarded Babylon's cities (19 shots, none before). Mongolia's
force at Carthage's capital qualified for bombardment but spent its attacks on
the defenders around the city. Unit totals per civilization changed by at most
a few units, so the extra aggression did not throw armies away.

## Crash at a city capture

The first fresh campaign crashed on turn 233 while Babylon captured Damascus:
- first an assertion, "Population of city should be at least 1"
  (`CvPlayer::getGrowthThreshold`);
- then an access violation in `CvCity::GetStaticYield`, called from Lua through
  `CvLuaCity::lGetYieldRateTimes100`. The city's yield vector had already been
  freed.

**Cause.** `LuaSupport::CallHook` releases the game core lock around every Lua
hook, so the UI thread can run its scripts. `CvPlayer::acquireCity` raises hooks
while the city is inconsistent:
1. `PreKill` sets the old city's population to 0 (`SetPopulation`); UI scripts
   such as the EUI city banners then compute its growth (the assertion).
2. The old city is deleted, and the new city's `setPopulation` raises the hook
   again, so UI scripts can run between deletion and reconstruction. The
   minidump shows the game core thread inside a `setPopulation` hook while the
   UI thread read a city whose data had been freed.

`CvCity::kill` (razing, disbanding) has the same window. This is upstream VP
behaviour; more captures make it more likely.

**Timing-dependent.** Replaying the turn-230 autosave with the same DLL made
the same captures on turn 233 without crashing.

**Fix.** `LuaSupport::DeferredHookScope`:
- Inside `acquireCity` (from `PreKill` until just before `CityCaptureComplete`)
  and `CvCity::kill` (until the city is deleted), hooks raised on the game core
  thread are queued with copies of their arguments and run in order afterwards.
- Test and accumulator hooks still run immediately, because callers use their
  results.
- In the turn-230 replay, each capture deferred 5 hooks (`LUA_HOOK_DEFER`);
  all 3,237 recorded AI events are identical to the run without the fix.

The crash save, dump and Lua log are in
`work/test-runs/campaign-c9-20261001/crash-t233`.

## Not changed

- **Siege lag in weak forces.** A force too weak to bombard keeps its siege on
  the safe staging tile, so siege can still be two turns behind the first wave.
  That is deliberate: such a force should not advance.
- **Readiness thresholds.** Strength 125%, damage horizon 4 turns and first-wave
  window 1 turn are unchanged.
