# Late-game performance: campaign 102, turns 269–272

Session date: 1 October 2026. Source save: the user's most recent autoplay,
campaign 102, saved at turn 267 and replayed from the observer save
`work/test-runs/c102-t269-source/C102 Observer T269.Civ5Save`
(SHA256 `ED7C2FA9…39AD`). Standard map, standard view, Summary diagnostics on.

## Result

| Build | Turn 269 | Turn 270 | Turn 271 | Turn 272 |
|---|---:|---:|---:|---:|
| DLL102 (installed baseline), Win7 compatibility mode | 93.2 s | 621.1 s | 405.6 s | — |
| C1, Win7 compatibility mode | 23.9 s | 37.1 s | 34.6 s | 38.3 s |
| C1, compatibility mode removed | 20.0 s | 30.2 s | 28.6 s | 31.2 s |
| C5 + yield interval 2000, compatibility mode removed | **17.6 s** | **25.4 s** | **23.9 s** | **26.2 s** |

Every candidate was replayed from the same save with the same seed. All 2,343
recorded AI events for turns 269–272 (550 plans, 550 recruitments, 419 capture
candidates, 277 combats, operation records…) are identical between C1 and C5,
checked with `work/compare-replay-events.py`. None of the changes alters AI
decisions, search budgets or combat formulas.

Turn 272 at C5 consists of 10.3 s of tactical search, 6.0 s of engine
update gaps and about 10 s of other game-core work (pathfinding, danger maps,
cities, diplomacy, unit missions).

## Changes

### C1: aircraft no longer disable the search caches (exact, 18× on the slow searches)

`StackPreviewInputsSupported` refused every tactical cache when an air unit took
part in a search, because air units are the only actors whose movement queries
reach the legacy `CanLoadAt` Lua hook (carrier rebasing). Late-game armies with
bombers therefore ran every search uncached: the same 6,000-position search took
about 18 times longer. This explains the 60+ s Babylon/Morocco turns.
`AITacticalCacheAirActors` (default 1) keeps the caches. Set it to 0 if a mod
registers a `CanLoadAt` listener with side effects.

C1 also introduced:
- `AITacticalForecastEntries` (24000; previously the 6000-position budget), so
  dense searches stop evicting their own danger forecasts.
- Small inline vectors for tactical-plot unit lists.
- A cached `UNITCOMBAT_MOUNTED` lookup in the strength functions.
- Const references instead of map copies in city yield code.
- A per-epoch live-validation shortcut in the strength cache.
- A small game-core-thread lookup cache in `TContainer::Get`.

### C2–C5: allocation and call overhead (exact, about 15% more)

- **Collateral damage:** `CvUnitCombat::GetStackCollateralDamageInto` writes
  into a caller-owned vector. The three danger-simulation loops reuse one vector
  across all attackers.
- **`SUnitIDValueContainer`:** reserves four entries when it first holds a
  second unit, instead of reallocating at sizes 1, 2, 3 and 4.
- **Ranged-attack plots:** the reachable-plot form of
  `GetPlotsUnderRangedAttackFrom` returns a sorted unique vector, using a plot
  bitmap instead of a `std::set<int>` node per plot. Same ascending order. This
  had been 5.6% of all non-search game-core time.
- **Tactical assignments:**
  - `ScoreStackPositionMembers` reuses its one-unit stack vector.
  - `addAssignment` copies a plot's enemy list only when a unit there died.
  - `addAssignment` applies the visibility bonus arithmetically instead of
    copying the whole assignment.
- **Settings:** `CvStacking::IsEnabled` and `GetIntByKey` read a published
  copy of the loaded settings inline. These calls run millions of times per
  turn; the uncached path still serves lookups during loading.
- **`Role()`:** stacking roles are flattened into per-role arrays. They keep
  the original precedence (combat, class, best promotion, unit), and the role
  maps remain the fallback while loading.
- **Hit points:** `CvUnit::GetMaxHitPoints`, `GetCurrHitPoints` and `getDamage`
  are inline.

### Yield interval (exact, about 12% of search time)

The tactical search releases the game lock every 500 positions so the UI can
run. Every yield also discards the danger forecasts and strength caches, because
the UI could in principle change game state while it holds the lock.
`AITacticalYieldPositions` now sets the interval, defaulting to 500 when the row
is absent. The shipped XML uses 2000:
- danger-forecast misses fell from 3.41 M to 2.17 M over the four turns;
- yields fell from 1,570 to 272;
- search time fell 11–13%, with identical decisions.

At 2000, a dense late-game search hands the lock to the UI about every 0.5 s
instead of every 0.14 s. Lower the value if the interface stutters during AI
turns.

## Windows compatibility mode

`CivilizationV_DX11.exe` had the per-user compatibility layer
`~ WIN7RTM HIGHDPIAWARE`. With WIN7RTM, every heap free goes through the
AcLayers shim. Removing it made the same replay about 18% faster with identical
decisions. The user chose to keep it removed: the value is now `~ HIGHDPIAWARE`.
The original is backed up in
`work/test-runs/c102-t269-source/appcompat-layers-backup.json`.

## What remains

- **Engine update gaps:** about 6 s per turn. The engine suspends the game-core
  thread between a player's turn activation and its first unit update (0.5–1.3
  s for each major civ, about 0.1 s for city-states). A per-thread CPU recording
  during these gaps found no thread near full use, so this is an engine-side
  wait rather than computation. Earlier engine-setting trials did not change it.
- **Tactical search:** the profile is now flat, with no function above 2.5%.
  Further large gains need fewer danger evaluations, for example reusing
  results across sibling positions, rather than cheaper lookups.
- **Pathfinding danger:** `PathEndTurnCost` runs the full stack-danger simulation
  for every end-of-turn plot, about 3% of all game-core time.
- **Turn-272 quit crash:** quitting the game during turn 272 of the DLL102
  baseline crashed at DLL+0x15038 (a shutdown race near the rules cache). It has
  not been investigated.

## Reproducing

```bash
pwsh -NoProfile -ExecutionPolicy Bypass -File work/run-c102-replay.ps1 -RunName <name> -ExpectedDLLSHA <installed DLL SHA256>
python work/summarize-replay-turns.py work/test-runs/<baseline> work/test-runs/<name>
python work/compare-replay-events.py work/test-runs/<baseline> work/test-runs/<name> 269 272
```

The wrapper launches a fresh game with guards and restores the benchmark mods.
It then replays turns 269–273 as observer and quits normally.
`work/start-replay-samplers.py` attaches the stack sampler
(`work/profile-gamecore.py`) for game-core and main-thread profiles.
`work/profile-nonplan.py` splits samples inside and outside tactical searches.

Run directories: `work/test-runs/perf-c102-*-269-273` (replays) and
`work/test-runs/prof-c102-*` (profiles).

Installed C5 DLL: `work/msvc-output/Release/20261001-182522`, SHA256
`1BD377112CE2E876DDA38D7F7AB2BA73AF99C22D26CF9F09A74E794B059E81DD`.
Each deployment's replaced files are in `work/backups/deployment-replaced-*`.
The DLL102 original (SHA256 `5CC28920…22E4`) is in
`deployment-replaced-20261001-172916-414bfda5`.
