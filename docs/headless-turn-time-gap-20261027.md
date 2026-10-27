# StackMod 0.3.4 against Vox Populi 5.4.8: the headless turn-time gap (27 October 2026)

The VP stats series (`E:\Projects\civ5-vp-stats`) found that StackMod 0.3.4 takes about 2.5 times the CPU of plain
VP 5.4.8 per AI turn in the civ5-headless host, growing from 1.6x early to about 3x after turn 200. This note explains
where that time goes, and what would reduce it. The handoff with the original measurements is
`E:\Projects\civ5-vp-stats\checks\stackmod-speed-handoff.md`.

## Summary

- **The gap is two factors multiplied.**
  - **Compiler, about 1.2x early to 1.6x late.** The pinned plain-VP DLL is upstream's release build: clang with
    link-time optimisation and SSE3. StackMod's release DLL is built here with Visual C++ 2008 (VC9), `/Ox`, x87
    floating point, no whole-program optimisation. Built with the same VC9 settings, plain VP 5.4.8 is 1.57 times
    slower than its own release DLL on the same turn-250 position.
  - **StackMod's own extra work, about 1.05x early to 1.6x late,** measured with both codebases built the same way.
- **Most of StackMod's own extra work is one mechanism: danger-map rebuilds** (`CvDangerPlots::UpdateDanger`).
  - StackMod marks danger maps dirty whenever a move reveals or hides an enemy, and on enemy moves, deaths, promotions
    and creation.
  - The next danger query then rebuilds the whole map, with reach pathfinding for every visible enemy unit. That
    happens about once per moving unit instead of once per turn.
  - At turns 250 to 258 this is a quarter of StackMod's turn: 7.6 of 30.0 Gcycles per turn, against 0.8 in plain VP.
  - It grows with army sizes and wars (moving units times visible enemies), which is why the gap grows.
- **A prototype that stops those rebuilds makes StackMod 24% faster per late turn** (commit `92a6d310a` on branch
  `perf-turn-time-gap`). It removes about 60% of StackMod's same-compiler excess. It changes AI decisions, partly
  towards VP's own danger rules (see section 5.1).
- **DLL logging is not the cause.** It costs about 0.3 to 0.5 s per late turn in both variants, which is about 10%
  of plain VP's turn and 3 to 4% of StackMod's. Under 1% of either profile is in logging functions.
- **The README's "6.1 s against 6.5 s" was a real-game measurement** that hid both factors:
  - Both DLLs were built with VC9, so there was no compiler gap.
  - The StackMod build was from 1 October, before the offensive AI work.
  - It was one game each, and the StackMod game had half as many war declarations.
  - Real-game wall time is floored at about 3.8 s per turn by frame pacing and carries about 6 s of rendering and
    engine waits per late turn.
  - README line 16 is corrected on this branch.
- **Ranked fixes** (section 6):
  1. Stop the danger rebuild churn: large gain, changes AI.
  2. Build releases with clang and link-time optimisation like upstream: large gain, no source change, but the local
     clang toolchain currently produces DLLs that fail to load.
  3. Turn on VC9 whole-program optimisation (`/GL /LTCG`): about 12% gain on plain VP, no source change, but
     StackMod's LTCG link hangs.

## 1. Measurements

All runs used the stats project's pinned inputs (DLLs, built databases, MODS folders, the same Lua probes) with kit
0.3.0. Each game ran in its own host process in Windows efficiency mode, side by side with the runs it is compared
with. Efficiency mode lowers clocks, so absolute seconds are slower than the stats check's P-core runs, but variants
run together are comparable.

### 1.1 Full games, continental-drift-p05 (seeds 900005/910005), to turn 300

Seconds per turn. The plain-VP clang run and the StackMod run replay the stats pilot games of this seed exactly
(the probe rows agree through turn 290).

| Segment | VP, upstream clang DLL | VP, VC9 build | StackMod 0.3.4 (VC9) | compiler (VP VC9 / clang) | StackMod (SM / VP, both VC9) |
|---|---:|---:|---:|---:|---:|
| T1-50 | 0.54 | 0.66 | 0.69 | 1.22 | 1.05 |
| T51-100 | 0.84 | 1.08 | 1.45 | 1.29 | 1.34 |
| T101-150 | 1.30 | 1.87 | 2.79 | 1.44 | 1.49 |
| T151-200 | 2.40 | 3.59 | 4.99 | 1.50 | 1.39 |
| T201-250 | 3.48 | 5.08 | 7.53 | 1.46 | 1.48 |
| T251-300 | 4.25 | 6.85 | 11.80 | 1.61 | 1.72 |
| T1-300 | 640 s | 957 s | 1,462 s | 1.50 | 1.53 |

StackMod against the pinned plain-VP DLL is 2.29x over the game and 2.78x in turns 251 to 300, close to the stats
check (2.45x, 2.8x). The VC9 and clang VP builds play different games from turn 50 (floating-point differences), so
the per-segment ratios compare like with like only on average.

### 1.2 Compiler, same position

Plain VP 5.4.8 from the same turn-250 save (the clang game), turns 251 to 258:

| Build | Seconds | Relative |
|---|---:|---:|
| Upstream release: clang, `-msse3 /Ox -flto` | 28.4 | 1.00 |
| VC9 `/Ox`, x87, no whole-program optimisation (StackMod's release settings) | 44.5 | 1.57 |
| VC9 `/Ox` plus `/GL` and `/LTCG` | 39.2 | 1.38 |
| VC9 `/Ox /arch:SSE2` | 43.1 | 1.52 |

How each DLL was built is read from its headers. The pinned VP DLL (262AEE88) has an lld linker header and a PDB path
under `clang-output\Release` on the VP maintainer's machine, and VP's `build_vp_clang_sdk.py` gives its flags.
StackMod 0.3.4 (0F9F3B88) is `work/msvc-output/Release/20261027-130028`: `work/build-vp.ps1` passes `--no-ltcg`.

### 1.3 StackMod's own work, same compiler, same position

StackMod 0.3.4 against the prototype from section 5.1, from the same turn-250 save, VC9 for both:

| Turns | 0.3.4 | Prototype P1 | Change |
|---|---:|---:|---:|
| T251-253 | 32.8 s | 25.3 s | -23% |
| T251-258 | 77.8 s | 59.3 s | -24% |
| T251-258, frame-pointer builds under the profiler | 92.0 s | 69.5 s | -24% |

The two games drift apart within the first ten turns. Over 20 turns the prototype's game had heavier turns later
(170 s against 179 s in total), so compare the first turns.

## 2. Where StackMod's extra time goes

### 2.1 Method

- `work/profile-gamecore.py` (the earlier sampler) loses the caller at every indirect call, such as the A* callbacks,
  so its inclusive shares were unreliable for this comparison.
- So both codebases were rebuilt with VC9 release flags plus `/Oy-` (frame pointers kept).
  `work/perf-gap/tools/fpsample.py` then suspends the host's game thread 400 to 500 times a second and walks the
  saved-EBP chain. Each sample is weighted by the CPU cycles the thread used since the previous one.
- Only samples under `CvGame::update` count; that excludes save loading.
- Positions:
  - turn 250 of continental-drift-p05, 8 turns per variant (StackMod's and VP's own games);
  - turn 280 of communitu-p00 from the stats speed check: 4 StackMod turns (the game ends at 284) and 10 VP turns.
  Both positions agree.

### 2.2 Breakdown, Gcycles per turn

Phases are the outermost AI subsystem on the stack. Functions are inclusive and overlap.

| | StackMod T250 | P1 T250 | VP T250 | StackMod T280 | VP T280 |
|---|---:|---:|---:|---:|---:|
| **Total** | **29.96** | **23.01** | **18.61** | **24.10** | **16.66** |
| Phase: tactical (incl. operations' army moves) | 13.92 | 9.82 | 8.41 | 12.54 | 5.01 |
| Phase: homeland | 7.12 | 4.80 | 3.11 | 3.99 | 4.45 |
| Phase: city | 2.12 | 2.11 | 2.21 | 1.95 | 2.53 |
| Phase: diplomacy | 1.90 | 1.47 | 1.01 | 1.51 | 1.05 |
| Phase: military AI | 1.49 | 1.43 | 0.71 | 1.45 | 0.56 |
| `CvDangerPlots::UpdateDanger` | **7.62** | 1.38 | 0.82 | **6.65** | 0.46 |
| `CvPlayer::AddKnownAttacker` (mostly its rebuilds) | 4.51 | 0.13 | 0.00 | 3.54 | 0.00 |
| `CvUnitMission::PushMission` (unit moves) | 5.46 | 0.96 | 0.76 | 4.42 | 0.92 |
| `TacticalAIHelpers::FindBestUnitAssignments` | 9.07 | 8.19 | 5.17 | 7.18 | 3.11 |
| `ScorePlotForCombatUnitMove` | 4.11 | 3.55 | 1.12 | 3.19 | 0.43 |
| `CvTacticalAI::PlotStackingOffensiveMoves` | 2.35 | 1.76 | - | 3.33 | - |
| A* pathfinding (`FindPathWithCurrentConfiguration`) | 11.71 | 6.70 | 5.85 | 9.27 | 4.94 |
| reach pathfinding (`GetAllPlotsInReachThisTurn`) | 6.70 | 1.54 | 1.52 | 6.01 | 1.07 |

- **Danger rebuilds are the biggest item:** 7.6 Gcycles per turn against 0.8. Through the moves that trigger them,
  they also explain most of StackMod's extra homeland time and its extra reach pathfinding. The 0.3.4 profile shows
  `UpdateDanger` called from:
  - unit moves: `CvUnit::setXY` → `CvPlot::changeAdjacentSight` → `changeVisibilityCount` → `AddKnownAttacker`
    (10.5% of the T280 turn);
  - combat damage: `addDamageReceivedThisTurn` → `AddKnownAttacker` (3.6%);
  - diplomacy and military danger checks (`IsInDangerFromPlayers`, `IsInDanger`) and pathfinder configuration
    (`GetPlotDanger`).

  In plain VP the same call paths cost almost nothing, because VP's map is rarely dirty mid-turn.
- **What remains after P1 is StackMod's tactical design:** about 4.4 Gcycles per turn (24%) over plain VP at
  turn 250.
  - Stack-aware position search and scoring: `FindBestUnitAssignments` +3.0, `ScorePlotForCombatUnitMove` +2.4,
    `GetCachedStackDanger` 1.7.
  - The stacking offensive and operations (`PlotStackingOffensiveMoves` 1.8, `CvAIOperation::DoTurn` +2.2).
  - More homeland work (opportunity attacks, patrols, inquisitors), partly because the games differ.

  None of it is a single hotspot.
- **Not significant:**
  - the stacking rules lookups (`CvStacking::GetInt` 0.1, `GetCapacity` 0.1 to 0.3);
  - the strength cache context (0.15);
  - the diagnostics phase timers, which do not appear at all;
  - city, economy and trade work, the same in both.

### 2.3 The danger-rebuild mechanism

- **The triggers.** The first stacking commit (`47a24f95f`, 27 September) added two helpers:
  - `DirtyStackDangerForVisibility` (`CvPlot.cpp`, called from `changeVisibilityCount` and the invisibility updates)
    marks a team's danger maps dirty whenever its visibility of a plot with an enemy unit or enemy city changes.
  - `DirtyStackDangerObservers` (`CvUnit.cpp`, called from `setXY`, `init`, `startDelayedDeath`,
    `setInvisibleType` and `setHasPromotion`) marks every enemy that can see a unit as dirty when it moves, appears,
    dies or changes.
  - `CvDangerPlots::SetDirty` also invalidates the global stacking strength cache.
- **The rebuild.** `CvPlayer::AddKnownAttacker`, `IsKnownAttacker` and `GetPlotDanger` rebuild a dirty map in full
  (`UpdateDanger`, two passes with `MOD_COMBATAI_TWO_PASS_DANGER`). Each pass runs `UpdateDangerSingleUnit`, with
  reach pathfinding, for every unit of every enemy.
- **The effect.** A unit that moves next to enemies dirties its owner's map through visibility changes. The next
  visibility change, one step later or by the next unit, calls `AddKnownAttacker` on the dirty map and rebuilds it.
  - Cost per turn is roughly the number of moving units near enemies, times the number of visible enemy units,
    times one reach search.
  - That grows with army sizes and the number of wars, which explains why StackMod's same-compiler ratio rises from
    1.05x to 1.7x over the game.
- **Plain VP** rebuilds danger once per player turn (`doTurnPostDiplomacy`) and on war changes. It adds newly seen
  attackers incrementally through `AddKnownAttacker` → `UpdateDangerSingleUnit`.
- **A behavioural side effect.** A mid-turn rebuild takes the `bWarChange` branch of `UpdateDangerInternal`. That
  clears `m_knownUnits` and keeps only enemies visible at that moment, without re-adding vanished units. So after the
  first rebuild of a turn, StackMod's AI forgets attackers it saw at turn start but has since lost sight of; plain VP
  keeps them for the turn.

## 3. DLL logging

Both variants run with the game's logging on (`gameLogFlags: 15`), as in the real game's config. Measured with
`--host-arg=--no-game-logging` against logging on, from the same turn-250 saves:

| Variant | Logging on, T251-253 | Off, T251-253 | Difference |
|---|---:|---:|---:|
| Plain VP (upstream DLL) | 10.4 s | 9.3 s | -0.37 s per turn (-11%) |
| StackMod 0.3.4 | 32.8 s | 31.7 s | -0.37 s per turn (-3%) |

- The saving is the same in absolute terms in both variants, so logging does not explain the gap. Turning it off
  would widen the ratio slightly.
- In the profiles, named logging functions take 0.6% (StackMod) and 0.9% (VP) of the turn, and string formatting
  0.2% and 0.4%. Host code called from the DLL (log manager, allocator, Lua events) takes about 2% in both.
- Logging changes the games: both pairs diverge within ten turns, and StackMod's 20-turn run without logging was
  slower (199 s against 179 s) because it played a different game. Keep comparing both variants in the same mode, as
  the stats series does.

## 4. Why the README benchmark showed no gap

README line 16 said "in one 250-turn autoplay benchmark the mod took 6.1 s per turn against 6.5 s for VP". The
source is `work/test-runs/vpbench-20261001-comparison.txt`, written on 1 October:

- **It was the real game, not the host.**
  - vpbench autoplayed one game per DLL from the same turn-0 save: `work/test-runs/vpbench-20261001-newgame`,
    Continents, Standard, 8 majors, observer slot at Prince.
  - It ran to turn 250, measuring wall time with a 5-second poll.
  - Process CPU (4,624 s against 5,069 s) counts all threads, including rendering, so it does not measure AI work.
- **Both DLLs were VC9 builds, so the compiler factor was absent.**
  - StackMod: DLL 5CBB5B3A = `work/msvc-output/Release/20261001-235141`, a build from 1 October before the
    offensive AI work, at "Release-5.4.6-109-g30284b325".
  - Vanilla: DLL 8B50F3DB = upstream master `d79cd781c` built locally with the same VC9 `/Ox` script
    (`work/wt/vp/work/msvc-output/Release/20261001-224028`).
- **Real-game wall time hides AI cost.**
  - The real game handles one player per update, about 105 ms apart, so early turns take about 3.8 s whatever the AI
    does (kit `docs\user-guide.md` section 10). Both runs show it: 3.55 and 3.76 s per turn in turns 0 to 50.
  - Late turns carry about 6 s of rendering, UI and engine waits on top of the AI: the kit's real games take
    10 to 12 s per turn where the host takes 4 s.
- **The two games differed.** The StackMod game had 27 war declarations against 59, so it was far calmer, and the
  danger churn scales with wars and contact.
- **It would not hold for 0.3.4 now.**
  - Since then the AI gained the offensive, siege, support-group and flanking work (October 2 to 11) and the
    later rounds.
  - Against the release DLL players actually compare with (upstream's clang build), the compiler factor applies on
    top.
  - The README line is corrected on this branch to describe the headless measurement.

## 5. Prototypes

### 5.1 P1: no danger rebuild on visibility changes and moves (commit `92a6d310a`)

- **The change.** Both helpers keep their checks but only invalidate the strength cache; they no longer call
  `SetDangerPlotsDirty`. Newly visible attackers are still added through `AddKnownAttacker`, and dead attackers are
  already skipped by every danger lookup.
- **Speed.** 24% faster per turn from the same late save (section 1.3). `UpdateDanger` drops from 7.6 to 1.4
  Gcycles per turn, near VP's 0.8.
- **Behaviour.** It changes AI decisions in two ways:
  - Within a turn, danger no longer reflects enemy moves made during other players' turns, or the ZOC changes from
    the player's own moves, until the next rebuild. Plain VP has the same staleness.
  - Attackers that leave sight stay in the map for the rest of the turn, as in VP. Version 0.3.4 dropped them at the
    first mid-turn rebuild.

  Whether stack-danger forecasts relied on the mid-turn rebuilds needs an AI A/B in the host before adopting it.
  `docs/ai-improvement-plan.md` "Testing with the headless host" has the recipe.

**Two-game A/B.** One full game of continental-drift-p05 (seeds 900005/910005) in each build: the 0.3.4 DLL and the
P1 DLL for every player. Both played side by side in efficiency mode, to victory, with the stats probes. The 0.3.4
game replays the stats pilot exactly (identical through turn 360).

| | 0.3.4 | P1 |
|---|---:|---:|
| Result | Maya, space race, turn 369 | Brazil, culture, turn 308 |
| Wall time | 3,032 s | 1,137 s |
| Turns 1-308 | 1,595 s | 1,137 s (-29%) |
| War declarations / peace treaties | 125 / 334 | 68 / 240 |
| Cities captured | 47 | 40 |
| Majors eliminated | 1 (Huns) | 3 (France, Maya, Assyria) |

Seconds per turn by segment (P1 / 0.3.4):

| | T1-50 | T51-100 | T101-150 | T151-200 | T201-250 | T251-300 |
|---|---:|---:|---:|---:|---:|---:|
| 0.3.4 | 0.71 | 1.47 | 2.85 | 5.08 | 7.49 | 11.97 |
| P1 | 0.69 | 1.22 | 2.14 | 3.84 | 6.73 | 6.69 |
| ratio | 0.98 | 0.83 | 0.75 | 0.76 | 0.90 | 0.56 |
| military units at the segment end, 0.3.4 / P1 | 79 / 80 | 136 / 137 | 201 / 202 | 316 / 279 | 431 / 327 | 524 / 480 |
| major wars at the segment end, 0.3.4 / P1 | 0 / 2 | 6 / 8 | 4 / 14 | 10 / 12 | 14 / 12 | 20 / 12 |

- **Speed.** Turns 101 to 200 are the fair comparison: the P1 game had as many units and more wars there, and was
  24 to 25% faster, the same as the controlled measurement from one save (section 1.3). The 44% saving in turns
  251 to 300 also reflects a calmer P1 game, with fewer units and wars.
- **Outcome.** The games differ from turn 10, because danger values feed early moves too, and end differently. One
  pair cannot say whether P1 plays better or worse: with every player changed, any difference is mostly a different
  game.
  - The P1 game had about half the war declarations but more eliminations.
  - Whether that is systematic needs more seeds, or a head-to-head game where only some majors run P1.
  - Branch `perf-gap-p1-ab` (commit `998bcde87`) has a per-player gate for that: `Game.SetStackingAIImprovedMask`,
    the host's `--improved-mask`. With mask 0 it replays 0.3.4 exactly (checked to turn 60). It was not run here.

### 5.2 Compiler variants

- **Clang (blocked).**
  - The clang build scripts lacked four stacking sources; fixed in commit `233fc7436`.
  - With them, a clang 19 build of StackMod compiles and links. It then fails at DLL load (error 1114): an access
    violation in `CvString::formatv`.
  - The same local toolchain fails the same way on unchanged upstream VP 5.4.8, so this is the local clang setup
    (clang 19.1.7 with `-fms-compatibility-version=15.00`, VC9 headers, `work/build-vp-local.py`), not StackMod code.
  - The build without `-flto` shows the caller: Firaxis's prebuilt `FDebugHelper::LoadSymbols`
    (`FirePlace\lib\FireWorksWin32.obj`), run from `_DllMainCRTStartup`, calls the clang-compiled
    `CvString::formatv` and its variable arguments arrive as garbage. That is an ABI mismatch between what this clang
    emits and the prebuilt Firaxis object.
  - Without the compatibility flag the link fails on `___std_terminate`; adding a shim links but fails to load the
    same way.
  - Upstream's clang build of the same source works (the pinned DLL). Upstream's setup is VS2008/SDK 7 with an older
    clang (`clang.cpp` mentions clang 14), so matching that version and its flags is the likely fix.
  - No StackMod clang timing exists yet; plain VP's 1.57x is the estimate.
- **VC9 whole-program optimisation.** `/GL` with `/LTCG`:
  - Plain VP links in 3 min 15 s and gains 12%.
  - StackMod's link hangs: twice, at about 5 s of linker CPU with no further progress for three minutes. That is the
    same symptom as the September attempt in `work/ltcg-experiment-review.md`, and the cause is unknown.
- **`/arch:SSE2`** gains 3% and changes floating-point results.

## 6. Fixes, ranked

Gains are per late turn (turn 250 and after); "behaviour" is the risk of changing AI decisions.

| # | Fix | Expected gain | Behaviour risk | Notes |
|---:|---|---|---|---|
| 1 | Stop full danger rebuilds on visibility changes and moves (P1) | -24% measured | Medium: danger semantics move to VP's | Removes about 60% of StackMod's same-compiler excess. Needs an AI A/B. Variants: keep the dirty marks only for deaths or for the moving player's own map, or rebuild lazily once per tactical pass. |
| 2 | Build releases with clang `-flto -msse3` like upstream | about -35% (VP: 44.5 → 28.4 s) | Low to medium: same source; floating-point differences change some decisions, as between the two VP builds | Needs a working clang toolchain first (section 5.2). Also makes StackMod and plain VP comparable on the compiler. |
| 3 | VC9 `/GL /LTCG` for releases (drop `--no-ltcg` in `work/build-vp.ps1`) | about -12% (VP measured) | Low: same source and x87 math; optimisation can change evaluation order | StackMod's LTCG link hangs (section 5.2), so this needs that hang solved first. |
| 4 | Lighter stack-aware tactical search: reuse stack-danger results across sibling positions, fewer scored candidates | up to -15% (the remaining 4.4 Gcycles) | Medium to high | The earlier performance docs list the exact-reuse candidates (`docs/late-game-performance-investigation.md`, `docs/performance-checkpoint-20261001.md`). |
| 5 | `/arch:SSE2` on VC9 | about -3% | Low to medium | Not worth it alone. |
| - | DLL logging off | -0.4 s per turn in both | Changes games | Not a StackMod fix; keep both variants in the same mode. |

Fix 1 alone brings late StackMod turns to about 1.2x of plain VP built with VC9, and about 2.1x of the clang
release DLL, from 2.8x now. With a working clang build (fix 2) as well, StackMod would be about 1.2 to 1.3x of the
release DLL. These products are estimates from separate measurements.

For the 600-game stats series, the choice affects only run time, not what is compared, provided both variants keep
the same logging. The present gap is mostly StackMod's build and danger handling, not unit counts or the host.

## 7. Reproduction

Everything lives in `work/perf-gap/` (ignored by Git). `RESUME.md` at the repository root lists the layout.

- **Builds:**
  - VC9 release: `work/build-vp-msvc.py --config release --jobs N --embedded-compiler-debug --no-ltcg --pch-memory
    400`; drop `--no-ltcg` for LTCG.
  - Frame-pointer and other extra flags: `work/perf-gap/tools/msvc_fp_build.py CHECKOUT/work/build-vp-msvc.py ...`
    (`PERF_GAP_CFLAGS`, default `/Oy-`).
  - Plain VP 5.4.8 builds from the `work/wt/vp548` worktree with a copy of the build script and a junction to the
    toolchain.
- **Runs:** `work/perf-gap/tools/prun.py NAME --variant vp|sm --dll DIR (--spec SPEC --seeds M S | --load SAVE)
  --turns T [--profile fp] [--host-arg=...]`.
  - It uses the stats kit with a private config (`work/perf-gap/civ5headless.toml`), the stats project's pinned
    MODS folders and databases, and copies of its mods databases.
  - It runs in efficiency mode, with the stats probes.
- **Profiles:**
  - Report: `tools/fpsample.py report RUN/fp.bin --dll DLL --pdb PDB --need CvGame::update`.
  - Call tree: `tools/fpsample.py callees ... --func REGEX --depth N` (negative N for callers).
  - Comparison: `tools/compare_profiles.py NAME=RUN:TURNS ...`.
- **Tables and replay checks:**
  - Turn-time tables: `tools/segments.py RUN...`.
  - Same-game check against another run: `tools/samegame.py RUN_A RUN_B`.
