# Tactical siege follow-up — 2026-09-27

This checkpoint modifies only `CvGameCoreDLL_Expansion2/CvTacticalAI.cpp`. It does not change the 13-unit recruitment limit, 6000-position storage, branch budgets or formation sizes. Root integrates the shared diagnostic logger and configuration separately.

## Behavior changes

- Fog-edge endpoints may count same-tile melee protection only when exact raw stack danger is strictly lower than the counterfactual without eligible melee escorts, and the unit and all eligible escorts survive. Cargo, support, foreign/wrong-domain, dead and non-native members do not qualify. Both forecasts remain raw even when an intermediate caller scales ordinary danger by aggression. The existing fog-danger floor and other safety checks remain.
- Stack joining preferences now evaluate city bombardment even when no enemy unit can attack. Cav/flanking and collateral-source flags still come from actual unit attackers. No preference weights changed.
- Simulated city encirclement requires an eligible surviving friendly occupant on each passable neighboring hex. Extra members on one hex cannot substitute for another. The live city's existing blockade result remains authoritative; this new geometric alternative does not reconstruct every virtual ZOC halo.
- A distant siege unit may pass the former zero-danger approach gate only with real surviving stack protection, danger no worse than its current position, legal placement, and no existing destination member facing greater or lethal damage after joining. This deliberately does not allow every defended forward advance.
- Entry into a full stack may use another movable combat member's valid exit from the existing sorted choice list. It still produces at most one combo for that incoming choice and uses the same search budgets. Existing native reverse-swap handling remains restricted to the original blocker; arbitrary stacked swap-partner selection is not assumed.

## Diagnostic rows

`CITY_GATE` records target coordinates and reasons: enemy dominance, insufficient expected damage, no melee, no eligible units, or attempted attack with candidate/melee counts. `ATTACK_GATE` reports failed visibility/spotting. `SIEGE_APPROACH` records only actual approach decisions, including whether the protected exception admitted the destination.

`RECRUIT` records input, usable, recruited, kept and budget-dropped counts; level2 `RECRUIT_FILTER` and `RECRUIT_DROP` identify units and actual filter stage. `PLAN` reports selected-plan counts, search states and existing elapsed time; level2 `PLAN_ASSIGN` includes IDs, from/to plot indices, action type, moves and score components. None of these rows recomputes danger or consumes RNG solely for logging.

`LONG_PLAN` reports history length/capacity, generation, current and preceding action, unit IDs, coordinates, movement and remaining attacks **before** the history push. `DiagnosticsLongPlanThreshold` defaults to256, with0 disabling this anomaly check; repeats occur only at threshold multiples and remain subject to the logger's per-turn budget. No plan is truncated. Crash245's failed allocation and2074-entry history are evidence. Its incomplete dump does not identify the unit or full prior action sequence. The subsequent instrumented replay now directly demonstrates the stationary-move loop described below.

## Focused validation

Run `python work/test-ai-siege.py` using the bundled Python and existing local VC9 toolchain. The harness extracts the actual four protection/approach/encirclement/preference functions and alternative-blocker filter from current C++ and compiles them as a native32-bit VC9 executable with deterministic engine/forecast stubs.41 checks pass. Cases cover useful vs ineffective/bypassed/sacrificial protection, virtual wounds, aggression scaling, eligibility, no-worse approach, city-only joining, unique hexes, virtual casualties, naval/cargo handling, alternative exits and disabled legacy behavior. Forecast values are controlled test inputs: this is a decision-boundary regression, not proof of native combat math or actual AI turn behavior.

Independent review found the initial raw-versus-aggression-scaled comparison issue; it was fixed and a negative test added before handoff. Root's full DLL build and live tests remain necessary.

## Representative live checks still needed

Use a disposable natural map and record the loaded DLL/configuration. Enable diagnostics for the selected AI player. Do not alter a running production game for these fixtures.

1. City-only cover: an enemy city can bombard a ranged AI unit, with no enemy combat unit in reach. A nearby melee escort can legally join. Record solo/covered danger, capacity, IDs and one normal AI turn; distinguish chosen protection from a simply unreachable alternate move.
2. Fog-edge siege: compare a reachable partially occupied endpoint with a strong, surviving escort against a weak/cavalry-bypassed or doomed escort. The useful case must reduce raw danger; an aggressive posture must not admit the ineffective case merely because its ordinary danger was scaled down. Inspect chosen plan and actual final positions.
3. Crowded ring: an incoming melee unit wants a full friendly tile. The first movable member cannot vacate, but another member has a legal free exit. Verify selected assignments move the second member out before entering and keep capacity legal. A foreign/cargo/wrong-domain member cannot free that slot.
4. Jakarta-style diagnosis: compare `CITY_GATE`, `ATTACK_GATE`, `RECRUIT` and `PLAN` on an unedited saved turn. A 7-unit plan is not evidence of hitting the13-unit limit; record upstream candidates and rejection reasons.

Do not infer optimal strategy, completed crash repair or long-run stability from these helper checks.


## Instrumented replay: stationary move loop and correction

The native093917 replay from the unchanged turn240 save exposed a concrete non-progress loop on turn244, Spain player0, target103:20. `LONG_PLAN` repeatedly recorded unit7508, A_MOVE/type1, from2040 to2040, moves120 to120, one attack left, with the previous assignment identical. Length increased256,512,...,3072 while generation increased249,...,3065. The operation log identifies7508 as a Tercio assigned to army7564. The parent stopped the game through its external guard after rapid memory growth; this run did not create a new crash dump. See [native diagnostics live evidence](NATIVE-DIAGNOSTICS-LIVE-20260927.md) and `work/test-runs/turn240-replay-20260927/Logs`.

Source diagnosis: `ScorePlotForNonFightingUnitMove` initialized every result as A_MOVE, including a request to remain on the current tile. The current-tile candidate branch reoffers this action; the previous-A_MOVE restriction applies only to different-tile choices. `addAssignment` consequently kept the unit available with unchanged movement and appended another action. This scorer behavior exists in unmodified VP5.4.6 (`dcb33a6`); the stacking campaign exposed it. Nonfighting movement strategy includes embarked units and some units assigned that strategy for a non-native target, so the correction is not restricted to the live `isEmbarked` flag.

The minimal correction has two parts:

- Classify a stationary intermediate nonfighting choice as A_FINISH_TEMP; use A_INITIAL and A_FINISH for the respective evaluation modes, matching the combat scorer.
- Reject same-from/to movement, forced movement and swap bookkeeping types at the start of `CvTacticalPosition::addAssignment`, before any copy-on-write state mutation or history append. The guard does not reject stationary ranged/melee attack, heal, pillage, power, wait, finish or initial types. Distinct-tile movement remains unchanged.

There is no plan-length cap, movement-budget relaxation or change to search limits. The separate support scorer's meaningful WAIT semantics are unchanged. The original245 dump confirms failed allocation during A_MOVE history growth but lacks the unit/history needed to prove it was exactly the same unit and target as this replay.

Run `python work/test-ai-noop.py`. The native VC9 harness compiles the actual nonfighting scorer, admission guard and existing terminal-action switch cases. Its in-memory pre-fix negative control reproduces3072 same-tile actions with120 movement; the fixed branch terminates with one finish assignment.39 checks pass, including both nonfighting strategies, initial/final/power behavior, enemy rejection, real movement, guard-before-mutation ordering, and permitted stationary actions. The existing41 siege helper checks also pass. These are controlled engine-stub regressions; the full DLL build and identical turn240 live replay of this correction remain pending.

Frozen tactical source SHA256: `2D5F5CD402F31DC721CA6518A12AFF80126107F5CCB02CDCD8B27F7A928D48A0`. Root reviewed the small correction and owns the next build/deployment/replay. No later runtime success is implied here.


## Second replay crash: diagnostic path endpoint

Release102519 (`13252af`, DLL `C6FC9A64C422C231D03E40A8F438B8DF3C3E4B2C5F653C11E7D5423454752125`) reached a different crash at turn244 with substantial free virtual address space. The exact PDB/minidump mapping identifies a null `CvPlot::GetPlotIndex` call (RVA0064A660), immediately after `PositionUnitsAroundTarget` calls `GetPathEndFirstTurnPlot` while preparing the new SIEGE_APPROACH log arguments. This dereference was introduced by the diagnostic line; it is separate from the inherited stationary-move loop. Ordinary C++ argument evaluation means the unsafe argument could be evaluated even with diagnostics disabled.

A successful approximate path does not guarantee a first-turn endpoint. `GeneratePath` permits an already-satisfied empty path, and `CvPathNodeArray::GetTurnDestinationPlot` also returns null when there is no turn0 node. `GetDanger(NULL)` instead falls back to the unit's current plot, which let the old approach code proceed to the unguarded log argument. The dump does not distinguish an empty path from the no-turn0-node case; cache corruption/invalidation is not needed to explain the failure.

The correction captures the first-turn endpoint once immediately after successful path generation, skips that approach when it is absent, and reuses the checked plot for danger, protection, diagnostic destination and dominance checks. It neither changes movement budgets nor converts an absent path into a guessed destination. This also remains safe if a later forecast invalidates the path cache.

`python work/test-ai-endpoint.py` compiles the actual approach block under VC9 with controlled engine stubs.16 checks pass, covering successful-empty paths with diagnostics on/off, failed paths, unchanged ordinary and protected approaches, unprotected danger rejection, and endpoint preservation when forecasting clears the cached path. The39 no-op and41 siege regressions also pass against this checkpoint. These tests do not replace a fresh identical-save live replay.

Current frozen tactical source SHA256: `DEAB0634BE272BDC20F0817CCB78A16741745D958864CBB2AEF520E982298A6E`. The endpoint review passed before the final comment-only clarification of the approximate-path contract. The next integrated DLL build/replay is pending. Raw second-crash evidence is in `work/test-runs/turn240-fixed-20260927`; root owns the overall runtime report and build/deployment.
