# Stacking development TODO

## Current checkpoint

Release20260927-105159 (`Release-5.4.6-8-gef54698 Clean`) compiled 176 translation units with native VC9 in 67.968 s and is deployment-verified (`105445-e3f58adf`). DLL SHA256: `D25416742EE592C3673DFED18F1C6816D8A4685C91707362C2B5DDA3A26BC3E7`. The final bounded Turn240 replay progressed into turn246 with no new crash, no LONG_PLAN warnings and no memory threshold. The guard stopped it at180 seconds during player41; turn246 and the campaign were not completed.

## Completed implementation and validation

- [x] Add native DLL diagnostics without an injected Lua observer. The direct top-center Diagnostics button is deployed and visually usable; Off, Summary, Verbose, Close and Escape were tested in game. The original EUI dropdown access problem is resolved. `StackAutoplayObserver` was nil during native validation.
- [x] Add XML defaults for summary/detail/memory intervals, player filtering, row/file limits, histogram overflow bucket and long-plan warnings. Runtime level changes apply only to the loaded session.
- [x] Record per-player/turn structural statistics, wounded/illegal units, stack-size histograms and bounded virtual-memory samples. Verbose records expose unit roles and city/garrison identities. Composition is explicitly separate from a safety forecast.
- [x] Record city-attack gates, recruitment filters/budget drops, chosen assignments and score components, operation messages, and bounded long-history warnings before assignment insertion. Search limits remain 13 units and 6,000 states.
- [x] Add actual-combat before/after logging using saved owner/unit IDs, including primary/secondary/garrison participants, explicit inflicted-versus-received damage labels, and post-resolution positions. Missing-unit records do not automatically assert combat death.
- [x] Add run/build/configuration identifiers and immediately flushed, live-readable rolling files. Off/On retains the loaded session's ring; new sessions have separate prefixes. Fixed workspace, cached settings, recursive locking and TLS status snapshots avoid unbounded diagnostic state.
- [x] Validate logger policy with 36 actual-source VC9 checks and the corrected UI with 55 Lua checks plus the existing roster suite. Observer/autoplay visibility is implemented and the button was visible in the live observer run; normal-player hiding, empty-hex dismissal, same-unit flag reopening, row selection and movement cancellation also passed in a separate live check. Confirm no gameplay orders or RNG calls in the diagnostics code. Live logs are in the correct engine Logs directory and readable while the game runs; Off/resume retains the same prefix and opens segment 1.
- [x] Implement the selected AI improvements: stronger protection at visible fog edges, conservative protected siege approaches, city-specific bombard protection preferences, unique-hex blockade estimates, and a bounded alternative exit for a full-stack blocker. All 41 targeted actual-source VC9 checks pass; representative live coverage remains pending.
- [x] Correct the ineffective VC9 danger-vector shrink expression. All 71 actual-source checks and independent review pass. This establishes capacity release, not a measured memory saving or a crash fix.
- [x] Prepare the bounded external memory watcher; 28 offline checks pass. The coordinator also recorded one successful read-only sample of the actual DX11 game. The final replay also exercised the exact-process duration stop at 180.034 s. Memory thresholds did not fire; earlier guards closed already-crashed processes and must not be counted as crash prevention.

- [x] Compare fresh processes loading `auto_test_1` from Turn 0 through one autoplay turn with logging Off versus Verbose. All captured fields match for 60 units and 30 cities, with no illegal-unit flags. This is one captured-state comparison, not proof of every game-state value or long-run equivalence.
- [x] Verify an actual catapult shot and its native combat trace: 30 assertions pass, primary damage is 34, two secondary victims take 6 each, and all four logged participant IDs/HP before and after agree with the fixture. The pre-fixture native archive has 395 rows; the final 494-row archive includes the fixture and level toggles and is not a second benchmark.

## Remaining validation and extensions

- [ ] Extend off/on equivalence, event-count and save/reload validation to later turns and more event types. The single-turn comparison and one collateral shot do not establish whole-campaign determinism or exhaustive logging coverage.
- [x] Diagnose and correct the demonstrated same-tile no-op loop and separate NULL endpoint fault (39 and16 native checks). Replay the original Turn240 save without a Lua observer on105159: progress into246,5,836 native records, no LONG_PLAN/TRUNCATED and no new crash. The former Spain244 target103:20 finishes with24 assignments, including terminal markers for unit7508. The180-second stop leaves246 incomplete; the retention-only fix was insufficient in the earlier run.
- [ ] Measure overhead on a large late-game position, including disabled logging, collection time, output cost and the effect of truncation/rotation. The duration stop is now exercised; memory-threshold/completion-signal behavior remains a separate validation scope. Preserve original saves.
- [ ] Extend decision explanations where needed: the current chosen-plan components are not an exhaustive trace of every protector, concentration penalty, defender or cavalry-interception alternative. The actual catapult trace proves one result path; broader forecast-to-result correlation still needs runtime evidence.
- [ ] Add area/category filters if useful; current filtering is by player. Add explicit city-stack and anti-cavalry aggregate statistics if needed; current verbose identities/flags support inspection but are not all dedicated summary fields.
- [x] Live-check normal-player diagnostics hiding and empty-hex roster dismissal, same-unit reopening, row selection and movement cancellation on the final DLL. Original units retained their HP and moves; the game closed normally. Evidence: `work/test-runs/ui-final-20260927`.
- [ ] Continue broader AI/balance coverage: collateral dispersion, naval/air strategy, sustained city sieges, long campaigns, multiplayer and unrelated-mod compatibility.

Final replay memory: peak private2,423.832MiB, peak committed+reserved3,218.863MiB, minimum free877.012MiB and minimum largest block724.312MiB across176 samples. These values describe one bounded run; no overhead or leak-free claim is made. Evidence: `work/test-runs/turn240-final-20260927/native-summary.json`, `memory.out`, `provenance.json` and `independent-readout.json`.

The temporary [Lua autoplay observer](../work/AUTOPLAY-OBSERVER.md) remains an earlier structural-data tool, not a requirement for the native logger. See the [configuration reference](stacking-configuration.md), [core review](../work/DIAGNOSTICS-CORE-REVIEW.md), [UI checks](../work/DIAGNOSTICS-UI-REGRESSION.md), [memory watcher](../work/MEMORY-WATCH.md) and [crash investigation](../work/CRASH-245-20260927.md) for evidence and limits.

## Military allocation follow-up (2026-09-27)

- [x] Implement the first bounded [military AI allocation pass](military-ai-plan.md#implementation-checkpoint--2026-09-27): shared retention, useful garrison orders, reserve transfers, domain budgets, assembly recovery and native explanations. Campaign calibration and advanced naval/air planning remain open. See `work/MILITARY-AI-IMPLEMENTATION.md` for release evidence.
- [ ] Compare rear-city surplus, operation assembly delays and actual front arrivals against the Danish replay and independent offensive/defensive scenarios before tuning broader policy.
- [x] User confirmed three-turn observer notification expiry working in autoplay through turn 330. Offline age/rebroadcast/normal-play cases also pass; this report does not add an independent live save/reload boundary test.
