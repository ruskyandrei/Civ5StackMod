# Decisive-war implementation — 30 September 2026

Status: the first pass was deployed as DLL29 and exercised in a fresh Standard/Pangaea/Standard campaign. The user stopped that campaign at turn 275 because of slow turn processing. Follow-up capture, assembly and performance fixes pass deterministic source checks; their native build and live comparison are pending. These checks do not establish better conquest rates or real pathfinder behavior.

## Assault coordination

An objective caches one healthy force/route/damage assessment per turn. It distinguishes true land siege from ordinary ranged units, accepts a real naval battery for a coastal target, reserves a particular surviving capturer, and evaluates city damage after estimated healing. Hidden cities retain normal VP scouting; visible enemy occupants are not globally enumerated. Force size scales with current stacking capacity and known fortifications, with small weak-city opportunities preserved.

Gathering chooses a reachable native-domain staging plot using existing danger forecasts and a singleton defender, so a friendly screen cannot hide the enemy attack footprint. Army positioning and loose forces after tactical handoff use the same decision. Committed loose units have their own objective movement pass instead of relying on a city zone remaining offensive. Safe shots already available and defensive/retreat actions remain eligible. Healthy units with excessive arrival spread cannot start the wave. Actual city captures that are executable and surviving bypass gathering.

Summary `ASSAULT_PLAN` records phase (0 gather, 1 commit, 2 reassess), ready/desired roles, inbound units, city damage/healing, staging, capture identity/ETA and path work. Reasons are 0 acceptable, 1 missing timely capture, 2 missing siege role, 3 insufficient damage, 4 insufficient core, 5 no safe stage, 6 excessive arrival spread and 7 abandoned-target cooldown. The ready count is a forecast of healthy reachable attackers, not executed participation.

The campaign follow-up adds reason 8 for an objective limit: an unassessed second domain cannot make an incomplete assault ready. Generic tactical city attack candidates and execution use the actual city's assembly policy, including when the search is aimed at another target. Capture choices remain eligible; preparatory ranged fire must use a safe firing position. A blocked ring-two endpoint now triggers bounded alternative legal firing routes, sharing the existing assault path budget.

Movement and first arrivals refresh commitments. Safe assembly holds survive the previous five-turn stationary cutoff, including after an operation has handed its units off. Gathering becomes reassessment after six turns by default. An assembling objective with no actual movement, useful force growth, production progress or new lowest city HP for 24 turns is abandoned, releases its units and receives a retry cooldown. Rotating candidate capturers alone do not restart the missing-capture siege timer.

Campaign 01 identified Egypt's Abernethy siege: ranged attacks left the city at one HP on turns 219–234 while capturer 6310 stayed at ETA one with no arrival progress. The follow-up removes the ETA-one exemption from the distant-capturer timeout and distinguishes forecasts from actual adjacency. A fast capturer can now use an exact legal route to attack in the current turn, with retaliation evaluated from the final approach. A specifically recorded assembly hold may be released for that surviving capture; arbitrary processed units cannot be reused. The recruitment health threshold no longer excludes a wounded adjacent unit that can survive the actual capture.

These fixes pass deterministic source checks but are not yet deployed or verified by a fresh campaign. The DLL29 campaign ran unchanged until the user's turn-275 stop; its save and native logs are preserved for comparisons. It is not a completed 300-turn run.

Each tactical search still has the existing 13-unit/6,000-state bounds. Larger groups can use three successive searches by default, re-reading live unit IDs and the changed board, with a per-player extra-batch allowance. Positioning also re-resolves participants after combat rather than retaining deleted unit pointers. A reserved capturer receives a final legality/survival/damage check after ranged softening before issuing a capture order.

## Recruitment and production

The support target is at least 12 combat units, with four reserves and a maximum of 32 credited units per objective/domain. Desired ready forces and true siege requirements scale separately with stacking capacity and target defenses. Role-specific production continues during approach and after tactical handoff, including when formation slots are already occupied.

Normal city production retains VP's economy, supply, resource and training checks. An objective bonus supplements the global unit ratios for a concrete missing role. Each producing city owns one support claim; existing VP formation promises are credited by their actual queued role and are never given a duplicate support claim. Actual completion replaces its pending credit with a unit commitment. Preparation objectives can receive these reserves before a voluntary declaration; staged committed reserves outside a full formation count toward opening readiness. A known fortified target requires a staged true siege battery before the voluntary opening.

Staffing counts are cached per objective/turn rather than re-scanning the army for every buildable unit. Summary records actual queue claims, completion identities and cancellation reasons. Training stagnation and changed queues cancel claims; peace, capture and invalid targets cancel demand.

`StackingFormations.sql`, loaded after `StackingConfig.xml`, adds optional combat slots to the small/basic/bigger land attack templates. Defaults add three/four/five true siege slots and the same number of front-line slots, making the total formations 15/18/21 slots. Added siege slots allow only the siege role as their substitute. Existing required early slots remain unchanged so absent siege technology does not block initial recruitment. Assault readiness separately prevents ordinary archers from satisfying a fortified target's siege requirement.

## City defense and bombardment

One designated garrison contributes passive city strength and ordinary damage absorption. Extra melee occupants do not multiply that benefit; ranged occupants each supply defensive firepower. The role policy prefers a useful garrison and ranged-heavy defense, normally retaining at most one melee occupant, with an emergency exception for a city in danger of falling. Rear cities retain economical coverage and release offensive commitments when an adequate replacement exists.

Missing ordinary ranged defense can generate transfer and local production priority even when melee strength is already sufficient. Siege weapons do not silently fill that ordinary ranged quota. Current marginal values are configurable approximations, not a complete counterattack/rotation scheduler; campaigns must verify actual defensive firing and released front-line strength.

`DisableCityRangedAttacks=1` disables cities' own shots in attack eligibility and danger forecasts. Unit ranged attacks remain enabled. Set it to 0 for the VP city-bombardment behavior.

## XML controls and validation

Edit `(1) Community Patch/Database Changes/StackingConfig.xml` and restart the game. `AIAssault*` controls core/siege counts, capacity scaling, weak-city thresholds, health/strength/damage margins, arrival cohesion, staging, gathering/abandonment, work budgets, batching and diagnostic cadence. `AIAssaultSmall/Basic/BiggerExtra*Slots` controls the formation additions (0–8 of each role). `AICapture*` controls persistence, progress, retries and survival eligibility. `AIOffensiveProduction*` controls pending builds, completion/stall horizons, siege reserves and priorities. `AICityRoleDefense*`, `AICityMaximumMeleeDefenders`, `AICityThreatenedMinimumRanged`, `AICityRangedSharePercent` and related value/priority settings control city role allocation. Every newly introduced numerical policy is registered in the rules and XML.

Offline evidence includes real offensive-module, city-allocation, bounded coordinator, city-bombardment/danger, collateral/production and formation-SQL checks. Route, combat and city services in policy fixtures are deterministic substitutes. Intermediate builds compile all 178 translation units using genuine VC9 x86 Release tools; they are not deployment evidence.

## Turn-processing follow-up

Native timestamps place turn 272 at approximately 123 seconds, with 98 seconds in tactical tree searches. PLAN timing covers the search loop rather than all preparation. Logged formatting/write/flush and snapshot timings were much smaller, but their tick counters are coarse and do not prove zero diagnostics overhead. The system CPU profiler could not start because Windows refused the profiling policy; no policy or security settings were changed.

The follow-up adds Summary PLAN_PERF records for setup, search and finalization, plus exact-state cache hits, misses, evictions and retained payload. The existing diagnostics interval and category filters control these records. Search bounds, attack rules and scoring remain intact for this performance work.

The defender selector skips outcome comparisons when there is exactly one eligible defender and that defender passes the existing flank filter. The actual hit still uses the normal combat calculation. A comparison against the preserved DLL29 source passes 40,001 deterministic states, covering melee, ranged, air, flanking, anti-cavalry, simulated wounds, invalid candidates and legacy toggles. This proves selector agreement under the test services, not a full-game speedup. Saved-position timing with diagnostics on/off and before/after the optimized build is still required.

The campaign watcher verifies the exact DX11 PID and creation time, samples process CPU/address space and GPU temperature/load, stops sustained thermal/address-space problems or suspected no-progress runs, and incrementally preserves native rolling segments. CPU temperature is not supplied by process telemetry and needs Core Temp observation. A no-log-progress cutoff alone is not proof of a hang. Existing saves and logs were preserved before testing; completed campaigns must reach at least turn 300, and abnormal stopped runs must be identified as incomplete.

The next performance change caches exact generic melee modifiers and ranged strengths within each locked tactical preview. Combat bodies remain byte-identical to the pre-cache commit; the new wrapper is bypassed outside preview, on foreign UI threads and during nested searches. Dirty danger state and UI yields invalidate the scene. XML `AITacticalStrengthCacheEntries` defaults to 16384 and accepts 0 (disabled) through 65536. Native Summary PLAN_PERF exposes cache hits, misses, bounded entries, evictions and invalidations. The actual cache/key/wrapper fixture passes 96,071 VC9 x86 checks, with deterministic engine services; full-game correctness and timing still require a saved-position replay.

The user stopped the long campaign at turn 275 and requested performance work. The sole-defender optimization alone did not establish a speedup: the intended full resumed turns 276 and 277 took roughly 163 and 77 seconds. No matched same-save DLL29 control has been run, and the sub-30-second target remains unverified. Further tests should be short, use an alive human return player for bounded autoplay, and exclude loading/resumed partial turns. Returning autoplay to NO_PLAYER keeps the observer running after the counter reaches zero.
