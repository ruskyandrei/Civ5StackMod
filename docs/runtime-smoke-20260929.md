# Runtime smoke validation — 29–30 September 2026

The current stacking DLL and UI passed the bounded smoke checks below. Long campaign balance, offensive effectiveness and whole-game diagnostic overhead remain unmeasured.

## Build and correction

- DLL: `Release-5.4.6-18-gef5f17dc6 Clean`, VC9 x86 Release `work/msvc-output/Release/20260929-221436`.
- SHA256: `691F897329A4F04C5C7D999B1F38CAAD3B02D4FE73BD4F4165BC4FA08E479F86`.
- Live testing found that the engine exports the letter key as `Keys.D=68`, while `Keys.VK_D` is absent. Commit `014d9cc76` corrects both WorldView bridges and the regression stub. All 84 offline diagnostic/UI assertions pass after correction. No C++ code or DLL was changed during this session.
- Restaged and deployed all 2367 files, hash-verified, with replacement archive `work/backups/deployment-replaced-20260929-233258-657172a9`. Loaded DLL path and hash were verified in both runtime processes.
- The user manually confirmed Ctrl+Shift+D opens/closes diagnostics on the map. The automated chord did not reliably retain modifier state until engine processing, so it is not counted as a passing live shortcut test.

## Mechanics and UI

The explicit disposable-game helpers report **152 mechanics assertions and 51 movement assertions passed, zero failures**. No injected autoplay observer was attached.

- Actual capacity boundaries and team-specific technology progression: 2 → 3 → 5 → 7 → 9. Cavalry selects the ranged defender, an anti-cavalry unit intercepts, and a healthy ranged defender is selected ahead of nearly dead melee.
- Catapult firing from a protected two-unit stack: primary loses 26 HP, two collateral victims lose 5 HP each; exact roll, victim limit, unaffected units and the 50% floor checks pass. Native COMBAT_SUMMARY records the same 36 HP lost.
- Fortified city max HP 858: live preview reports protection 90% at full HP, 45% at 429 HP, 0% at zero HP, and 0% at 1 HP. Actual artillery hits at full/half/1 HP pass independent collateral formulas. Native summaries record pre-hit protection 90/45/0 and city HP 858→837, 429→408, 1→1. Bystander damage totals 9/14/22 include normal garrison absorption. Zero HP was a read-only preview query after deliberately setting fixture HP, not an actual ranged attack at an invalid negative city-damage boundary.
- A very strong bomber kills a 3-HP early unit; collateral removes 50/50/50/2 HP from secondary units and leaves already-floor targets unchanged. This checks the floor and limits, not late-game combat balance. The native summary reports primary damage 3, retaliation 1, bystanders 152 and total present-unit HP loss 156.
- Partial stack movement sends the selected melee unit and civilian; the ranged member blocked by reserved capacity stays behind. Actual positions, survival, unchanged HP and squad membership pass.
- Live two-unit roster sits entirely above the combat-preview banner/panel. A nine-combat-unit roster shows all members at the current window size, the last row selects the correct Horseman, and left-clicking an empty map hex dismisses it. Observer Diagnostics is visible and opens the Summary panel; normal play has no Diagnostics button. Nine rows fit here, so scrolling at a smaller viewport and the ten-combat-unit XML profile were not exercised today.

## Save/reload

A separately named fixture save was created through `UI.SaveGame`, then reloaded through the ordinary load-game event. All captured fields for **80 units and 2 cities match exactly**; every unit reports legal placement after reload. Captured fields include identity/type, position, HP/max HP, movement, stacking capacity/legality, city population/damage/max HP and garrison identity. This does not establish full internal-state/RNG equivalence.

The disposable save is archived at `work/test-runs/smoke-20260929/Stack Smoke Fixture 20260929.Civ5Save`, with a second copy in the C-drive evidence folder. It is no longer listed among the user's campaign saves. No terrain fixture was used.

## Bounded campaign replay

Process 23760 loaded the existing `autoplay(2)_236.Civ5Save` (SHA256 `308528AD39B7231ABC4A214AE375A2858AEF6254B93B8C5A910BE73C28673B0B`) without fixture mutation. Its saved autoplay was bounded to two turns and Summary enabled before Continue Your Journey.

The run **completed turn 236 and reached player 7 in turn 237**. A 120-second memory/time guard then stopped the exact process at 120.015 seconds after arming, before the second turn completed. An attempted guard extension arrived after termination and created no replacement watcher. This was an imposed cutoff: the last trace was still advancing, no new crash-log entry appeared, and memory limits were not crossed. It must not be described as two completed turns or a normal human return.

The retained current-run trace contains **1583 records**, 51 COMBAT_SUMMARY, 20 OPERATION_STATUS, 36 DIAGNOSTIC_COST, 11 REINFORCEMENT, 9 OFFENSIVE_SUPPORT and 2 WAR_READINESS records. It has zero malformed rows or row-budget truncations. It shows support units moving toward remembered city objectives, unit 8850 arriving for operation 8720, and a failed operation route rejected before recruiting and put on cooldown. Arrival logging alone does not prove a formation join or effective sustained reinforcement.

The guard's peak private memory was 2519 MiB, with at least 773 MiB free address space. Crash log remained 15925 bytes, last modified 2026-09-27 09:36:45 UTC. Formatting/write/flush timing commonly rounded to zero at this logger's coarse tick resolution; this is not zero logging cost or a measured whole-game speedup. No matched Off/Summary/Verbose replay was done.

The particular closed-border, naval city, across-water Edirne and voluntary-war opening scenarios still need dedicated tests or campaign observations. No new combat balance conclusion follows from this short replay.

## Cleanup and handoff

The original `Stack Smoke Test 0` save SHA256 remains `9437442A028598D1586DF589F92008D23B4C01CEE83FBB9C22319046F8292CBC`. All pre-test ModdedSaves hashes matched at final verification, so no restoration writes were needed. The fresh process 30344 was verified at turn 0, active player 0, autoplay 0, Summary level 1, with both StackTests and StackAutoplayObserver absent. It is left focused for the user's fresh autoplay. All watchers have exited/disarmed. No AI/gameplay source edits, DLL rebuild, push or publication occurred during these runtime checks.

Final active mods are Community Patch, VP, EUI compatibility, Squads, and UI Small Resource Icons. The initial automated restart enabled the four core test mods; the user restored their final UI selection. The extra mod only affects presentation.

Evidence: `work/test-runs/smoke-20260929/{smoke-results.json,world-save-comparison.json}` and guard directories; raw logs, screenshots, saved-turn snapshots, JSON summaries and backups remain local at `C:/Users/rusit/Documents/Codex/Civ5StackMod-analysis/smoke-20260929`. `campaign-current-summary.json` selects only the newly tested run; `campaign-native-summary.json` also contains older retained runs and must not be treated as this replay's totals.
