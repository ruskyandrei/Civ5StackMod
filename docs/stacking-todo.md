# Stacking development TODO

## Current checkpoint

Release20260927-093917 (`Release-5.4.6-6-gb7731f6 Clean`) compiled 176 translation units with native VC9 and is deployment-verified. DLL SHA256: `DEA164B78A048141AAF0812AE6D11474989163B6B8F6A9ECBDBD69C818CA7D75`. Deployment `095814-6f88875f` verifies all 2,367 files. Initial live diagnostics validation is complete; the bounded Turn 240 replay and broader AI/memory conclusions remain pending.

## Completed implementation and validation

- [x] Add native DLL diagnostics without an injected Lua observer. The direct top-center Diagnostics button is deployed and visually usable; Off, Summary, Verbose, Close and Escape were tested in game. The original EUI dropdown access problem is resolved. `StackAutoplayObserver` was nil during native validation.
- [x] Add XML defaults for summary/detail/memory intervals, player filtering, row/file limits, histogram overflow bucket and long-plan warnings. Runtime level changes apply only to the loaded session.
- [x] Record per-player/turn structural statistics, wounded/illegal units, stack-size histograms and bounded virtual-memory samples. Verbose records expose unit roles and city/garrison identities. Composition is explicitly separate from a safety forecast.
- [x] Record city-attack gates, recruitment filters/budget drops, chosen assignments and score components, operation messages, and bounded long-history warnings before assignment insertion. Search limits remain 13 units and 6,000 states.
- [x] Add actual-combat before/after logging using saved owner/unit IDs, including primary/secondary/garrison participants, explicit inflicted-versus-received damage labels, and post-resolution positions. Missing-unit records do not automatically assert combat death.
- [x] Add run/build/configuration identifiers and immediately flushed, live-readable rolling files. Off/On retains the loaded session's ring; new sessions have separate prefixes. Fixed workspace, cached settings, recursive locking and TLS status snapshots avoid unbounded diagnostic state.
- [x] Validate logger policy with 36 actual-source VC9 checks and the corrected UI with 43 Lua checks plus the existing roster suite. Confirm no gameplay orders or RNG calls in the diagnostics code. Live logs are in the correct engine Logs directory and readable while the game runs; Off/resume retains the same prefix and opens segment 1.
- [x] Implement the selected AI improvements: stronger protection at visible fog edges, conservative protected siege approaches, city-specific bombard protection preferences, unique-hex blockade estimates, and a bounded alternative exit for a full-stack blocker. All 41 targeted actual-source VC9 checks pass; representative live coverage remains pending.
- [x] Correct the ineffective VC9 danger-vector shrink expression. All 71 actual-source checks and independent review pass. This establishes capacity release, not a measured memory saving or a crash fix.
- [x] Prepare the bounded external memory watcher; 28 offline checks pass. The coordinator also recorded one successful read-only sample of the actual DX11 game. The optional stop path has not been exercised by those checks.

- [x] Compare fresh processes loading `auto_test_1` from Turn 0 through one autoplay turn with logging Off versus Verbose. All captured fields match for 60 units and 30 cities, with no illegal-unit flags. This is one captured-state comparison, not proof of every game-state value or long-run equivalence.
- [x] Verify an actual catapult shot and its native combat trace: 30 assertions pass, primary damage is 34, two secondary victims take 6 each, and all four logged participant IDs/HP before and after agree with the fixture. The pre-fixture native archive has 395 rows; the final 494-row archive includes the fixture and level toggles and is not a second benchmark.

## Remaining validation and extensions

- [ ] Extend off/on equivalence, event-count and save/reload validation to later turns and more event types. The single-turn comparison and one collateral shot do not establish whole-campaign determinism or exhaustive logging coverage.
- [ ] Run the bounded Turn 240 replay without the Lua observer, recording virtual-memory pressure and long-plan warnings. Determine why the failed assignment history reached 2,074 entries. Do not claim that the retention fix prevents the Turn 245 crash.
- [ ] Measure overhead on a large late-game position, including disabled logging, collection time, output cost and the effect of truncation/rotation. Confirm safety-monitor completion/threshold behavior during a controlled test; preserve original saves.
- [ ] Extend decision explanations where needed: the current chosen-plan components are not an exhaustive trace of every protector, concentration penalty, defender or cavalry-interception alternative. The actual catapult trace proves one result path; broader forecast-to-result correlation still needs runtime evidence.
- [ ] Add area/category filters if useful; current filtering is by player. Add explicit city-stack and anti-cavalry aggregate statistics if needed; current verbose identities/flags support inspection but are not all dedicated summary fields.
- [ ] Continue broader AI/balance coverage: collateral dispersion, naval/air strategy, sustained city sieges, long campaigns, multiplayer and unrelated-mod compatibility.

The temporary [Lua autoplay observer](../work/AUTOPLAY-OBSERVER.md) remains an earlier structural-data tool, not a requirement for the native logger. See the [configuration reference](stacking-configuration.md), [core review](../work/DIAGNOSTICS-CORE-REVIEW.md), [UI checks](../work/DIAGNOSTICS-UI-REGRESSION.md), [memory watcher](../work/MEMORY-WATCH.md) and [crash investigation](../work/CRASH-245-20260927.md) for evidence and limits.
