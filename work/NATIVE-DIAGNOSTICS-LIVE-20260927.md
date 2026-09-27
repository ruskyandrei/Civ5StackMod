# Native diagnostics live validation — 27 September 2026

The initial runtime checks used native Release `20260927-093917`, DLL SHA256 `DEA164B78A048141AAF0812AE6D11474989163B6B8F6A9ECBDBD69C818CA7D75`, PDB `9BC896E626DF0FE48B886AF418EFCB504319E2B07BCA5F82D7A11A946A114533`. The loaded module path and hash were checked against the installed Community Patch DLL. This build incorporates the five siege/planning improvements, danger-vector capacity fix, and native diagnostics. No Lua autoplay observer was injected.

## Controls and files

The original Additional Information entry proved inaccessible in EUI: it hides the classic dropdown and skips entries with empty artwork. The corrected standalone **Diagnostics** button was deployed in archive `work/backups/deployment-replaced-20260927-095814-6f88875f` (2,367 files verified, unchanged DLL). Actual UI tests covered opening it without a stack, selecting Off/Summary/Verbose, status/path wrapping, Escape, Close, and opening it in observer mode. The corrected UI passed 43 Lua regressions, including the actual EUI filtering/order behavior.

The native output is in the engine's normal Documents game `Logs` directory, named `Stacking-<UTC>-p<PID>-r<session>-<slot>.log`. It was successfully read while the game held it open. Off produced no diagnostic files in the baseline process. Switching Off appended a LEVEL record and closed the file; switching back on retained the run prefix and opened segment 1. Reloading in a fresh process restored the XML default Off, despite leaving the prior test session on Verbose.

## Matched saved-turn comparison

Two fresh DX11 processes loaded the original `auto_test_1.Civ5Save` (SHA256 `5C2749C3DFDADBAFA0A66B883C091E27D410EAAE100EE21B846D84AC74CEC3C2`). Each executed one normal `Game.SetAIAutoPlay(1,0)` turn, with no fixture mutation before comparison. One used logging Off; the other used Verbose. The native DLL and gameplay XML were identical; only the UI access correction differed.

At settled human turn 1, all captured fields for **60 units and 30 cities matched**, with no units reporting illegal positions. Fields include owner/ID/type, position, HP/max HP, movement, stacking capacity/legality, city population/damage/max HP and garrison identity. This is not a complete internal-state/RNG equivalence proof or a precise performance benchmark.

Evidence: `work/test-runs/diagnostics-live-20260927/off-on-comparison.json`, the two archived `Lua.log` files and `verbose/provenance.json`. The pre-fixture native log contains 395 retained records, including structural summaries, units, cities, configuration, memory and sampling duration. No truncation was needed in that short run.

## Actual combat trace

After the comparison, a disposable catapult fixture executed an actual ranged attack from a protected stack. The shot did **34 primary damage** and **6 damage to each of two secondary targets**. The other secondary candidates remained unchanged. All **30 fixture assertions passed**. Native combat records captured four unique identities before and after resolution and matched their observed HP changes: attacker 100→100, defender 100→66, two secondary targets 100→94. The combat bracket was complete, with no mismatched identities. No save was made from the fixture state.

Evidence: `work/test-runs/diagnostics-live-20260927/combat`, `final`, and `final-summary.json`. The final 494-record archive also includes the later Off/On control check; it must not be confused with the 395-record pre-fixture archive.

## Bounded pre-crash replay

A fresh DX11 process loaded the original post-turn-240 autosave, SHA256 `CC9D87490A5D7F4EA392C71294A9806F0C5A4DDAB350DA699B9E10E986D96574`. Its saved observer/autoplay state resumed automatically. Verbose was enabled during turn 241; the first part of turn 240 was therefore not captured by native logging. At turn 244 the console verified `StackAutoplayObserver == nil`, then bounded autoplay to return as Spain at turn 246. A separately verified process-identity memory guard remained active throughout.

The replay exposed a repeated **same-tile A_MOVE** by Spain's Tercio 7508 toward target (103,20): from/to plot 2040, movement 120→120, repeated through 3,072 assignments. It generated 12 LONG_PLAN warnings. Over roughly four seconds, sampled private bytes rose from 2,375,831,552 to 3,371,323,392, with only 38,780,928 bytes of virtual free space in the final sample. At 115.888 seconds the guard terminated exactly the test process because it crossed the configured memory limit. This was a deliberate safety stop, not another recorded crash.

Evidence: `work/test-runs/turn240-replay-20260927/{Logs,memory,memory.out,native-summary.json,provenance.json}`. The original crash's failed allocation and this repeatable assignment loop are consistent, but the minidump does not establish that the original crashing unit had the same identity. A narrow stationary-assignment fix and same-save replay are the next validation step.

## Limits

The earlier 41 native AI checks cover individual decision boundaries, not live proof of all five new tactical behaviors. The logger does not provide exhaustive alternative-choice reasoning. Whole-campaign memory stability, large-game logging overhead, and balance still require longer playtests after the no-op planner loop is fixed. Raw archives remain local and are not committed or uploaded.
