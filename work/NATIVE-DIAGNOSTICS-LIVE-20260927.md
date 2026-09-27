# Native diagnostics live validation — 27 September 2026

The initial runtime checks used native Release `20260927-093917`, DLL SHA256 `DEA164B78A048141AAF0812AE6D11474989163B6B8F6A9ECBDBD69C818CA7D75`, PDB `9BC896E626DF0FE48B886AF418EFCB504319E2B07BCA5F82D7A11A946A114533`. The loaded module path and hash were checked against the installed Community Patch DLL. This build incorporates the five siege/planning improvements, danger-vector capacity fix, and native diagnostics. No Lua autoplay observer was injected.

## Controls and files

The original Additional Information entry proved inaccessible in EUI: it hides the classic dropdown and skips entries with empty artwork. The corrected standalone **Diagnostics** button was deployed in archive `work/backups/deployment-replaced-20260927-095814-6f88875f` (2,367 files verified, unchanged DLL). Actual UI tests covered opening it without a stack, selecting Off/Summary/Verbose, status/path wrapping, Escape, Close, and opening it in observer mode. The corrected UI passed 43 Lua regressions, including the actual EUI filtering/order behavior.

The native output is in the engine's normal Documents game `Logs` directory, named `Stacking-<UTC>-p<PID>-r<session>-<slot>.log`. It was successfully read while the game held it open. Off produced no diagnostic files in the baseline process. Switching Off appended a LEVEL record and closed the file; switching back on retained the run prefix and opened segment 1. Reloading in a fresh process restored the XML default Off, despite leaving the prior test session on Verbose.

## Matched saved-turn comparison

Two fresh DX11 processes loaded the original `auto_test_1.Civ5Save` (SHA256 `5C2749C3DFDADBAFA0A66B883C091E27D410EAAE100EE21B846D84AC74CEC3C2`). Each executed one normal `Game.SetAIAutoPlay(1,0)` turn, with no fixture mutation before comparison. One used logging Off; the other used Verbose. The native DLL and gameplay XML were identical; only the UI access correction differed.

At settled human turn 1, all captured fields for **60 units and 30 cities matched**, with no units reporting illegal positions. Fields include owner/ID/type, position, HP/max HP, movement, stacking capacity/legality, city population/damage/max HP and garrison identity. This is not a complete internal-state/RNG equivalence proof or a precise performance benchmark.

Evidence: `work/test-runs/diagnostics-live-20260927/off-on-comparison.json`, the two archived `Lua.log` files and `verbose/provenance.json`. The pre-fixture native log contains 395 retained records, including structural summaries (with city counts), unit details, configuration, memory and sampling duration. No truncation was needed in that short run.

## Actual combat trace

After the comparison, a disposable catapult fixture executed an actual ranged attack from a protected stack. The shot did **34 primary damage** and **6 damage to each of two secondary targets**. The other secondary candidates remained unchanged. All **30 fixture assertions passed**. Native combat records captured four unique identities before and after resolution and matched their observed HP changes: attacker 100→100, defender 100→66, two secondary targets 100→94. The combat bracket was complete, with no mismatched identities. No save was made from the fixture state.

Evidence: `work/test-runs/diagnostics-live-20260927/combat`, `final`, and `final-summary.json`. The final 494-record archive also includes the later Off/On control check; it must not be confused with the 395-record pre-fixture archive.

## Bounded pre-crash replay

A fresh DX11 process loaded the original post-turn-240 autosave, SHA256 `CC9D87490A5D7F4EA392C71294A9806F0C5A4DDAB350DA699B9E10E986D96574`. Its saved observer/autoplay state resumed automatically. Verbose was enabled during turn 241; the retained native trace covers turns 241–244, with turn 240 absent. At turn 244 the console verified `StackAutoplayObserver == nil`, then bounded autoplay to return as Spain at turn 246. A separately verified process-identity memory guard remained active throughout.

The replay exposed a repeated **same-tile A_MOVE** by Spain's Tercio 7508 toward target (103,20): from/to plot 2040, movement 120→120, repeated through 3,072 assignments. It generated 12 LONG_PLAN warnings. Over roughly four seconds, sampled private bytes rose from 2,375,831,552 to 3,371,323,392, with only 38,780,928 bytes of virtual free space in the final sample. At 115.888 seconds the guard terminated exactly the test process because it crossed the configured memory limit. Later inspection of crashes.log and a new dump confirmed that the game had already crashed at 10:18:46 BST, before the guard closed it. The initial assumption that the guard had prevented a crash was incorrect. This replay dump is archived under the run's crash directory.

Evidence: `work/test-runs/turn240-replay-20260927/{Logs,memory,memory.out,native-summary.json,provenance.json,crash}`. The original crash's failed allocation and this repeatable assignment loop are consistent, but the original minidump does not establish the same unit identity.

## Stationary-loop fix replay: separate crash remains

The reviewed stationary-assignment correction was built as Release `20260927-102519` (`Release-5.4.6-7-g13252af Clean`), DLL SHA256 `C6FC9A64C422C231D03E40A8F438B8DF3C3E4B2C5F653C11E7D5423454752125`, matching PDB `77D283C251FE26D86953E21E2890BDF6B5868E525359563E62465DE6ECED5255`. Deployment archive: `deployment-replaced-20260927-102730-5faa4c91`. The same original turn-240 bytes were restored and verified before loading; Civ V's test-generated autosave was preserved separately.

The exact Spain target (103,20) now completes with 24 assignments; unit 7508 receives a finish action, and no LONG_PLAN warning occurs. However, the game then crashes at turn 244, 10:36:44 BST, at DLL RVA `0x0064a660`, with 999,032 KiB of free virtual address space and a 910,592 KiB largest free region. This is a separate fault from the allocation failure. The three-minute guard later closes the crash dialog process; its duration-stop record must not be interpreted as a crash-free replay.

Evidence: `work/test-runs/turn240-fixed-20260927`, including `crash/CvMiniDump_20260927_103644_5.4.6-7-g13252af_Release.dmp` (SHA256 `D874C2A67ADD84C070312E0E7AF8412E3F48D2BD8A1ABEFF39143D51836C9D0C`). Investigation of the separate fault is pending. Turn 246 has not been reached.

## Final integrated replay

Release `20260927-105159` (`Release-5.4.6-8-gef54698 Clean`) includes the checked endpoint and both requested UI changes. DLL SHA256: `D25416742EE592C3673DFED18F1C6816D8A4685C91707362C2B5DDA3A26BC3E7`; matching PDB: `141182FE191B4B2E02FB3CD459683C8849E37CD4601CCEBDCF3B3E63FAD44F5C`. Deployment archive `deployment-replaced-20260927-105445-e3f58adf` verified all 2,367 mapped files. The loaded DLL and original CC9D8749... autosave hashes were recorded before replay.

The fresh process resumed the saved autoplay settings without changing the return player/count. Native Verbose was selected in the actual observer-only panel. The read-only console check at turn 244 reported remaining autoplay 4757, observer player 10, and no injected Lua observer. The retained trace reaches **turn 246, player 41**: 5,836 records, 573 selected-plan records, 161 complete combat brackets, no LONG_PLAN warnings and no TRUNCATED markers. The formerly failing Spain target (103,20) completes with 24 assignments; Tercio 7508 receives the proper temporary/final finish markers. That plan took 405 ms, with 1,524 searched states and 256 completed candidates.

The 176 external memory samples peak at 2,541,572,096 private bytes, with at least 919,613,440 bytes free and a 759,496,704-byte largest free block. The three-minute guard closes the game at 180.034 seconds during turn 246. The attempt to signal completion happened after this stop, so the outcome is **a bounded replay that reached partway through turn 246**, not a normal return or completion of that turn. Crash-log size/time remained unchanged (15,925 bytes, 09:36:45 UTC), and no new minidump appeared. This is the first replay that passed both observed crash sites without another crash.

Evidence: `work/test-runs/turn240-final-20260927/{Logs,memory,memory.out,native-summary.json,provenance.json}`. The original autosave and test-generated replacements are preserved separately. The observer-only Diagnostics control was visible and usable in this build.

## Final normal-play UI check and cleanup

A separate fresh process loaded the original `auto_test_1` at turn 0 with the same final DLL. No autoplay, fixture setup, Lua commands, turn advance or movement order was used. Diagnostics was absent from the normal-play map. Selecting the existing Warrior/Pathfinder stack opened the Land 2/2 roster; left-clicking an empty grassland hex dismissed it. Selecting the same Warrior flag reopened it, and selecting the Pathfinder row left it open. Starting Move Stack and left-clicking the map cancelled the pending order; a further empty-map click dismissed the roster. Both units remained at 100 HP, with their original 2 and 1 movement points. The game then closed normally without a manual save.

Evidence: `work/test-runs/ui-final-20260927/{provenance.json,ui-observations.json,Lua.log}`. The three autosaves automatically rewritten by tests (initial turn 0, post-turn 0, post-turn 240) were preserved under `autosaves-generated-by-tests` and restored from the original crash archive. All eight archived autosave hashes matched afterward, and the original manual `auto_test_1` hash remained unchanged. See `autosave-restoration.json`.

## Limits

The 41 native AI checks cover individual decision boundaries, not live proof of all five new tactical behaviors. The logger does not provide exhaustive alternative-choice reasoning. Whole-campaign memory stability, large-game logging overhead, and balance still require longer playtests. Raw archives remain local and are not committed or uploaded.
