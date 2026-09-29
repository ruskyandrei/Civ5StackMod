# Offensive AI follow-up — 2026-09-29

This pass targets the observed declaration/handoff discontinuity, repeated route failures, reinforcement gaps and uncapturable sieges. It also implements city-HP-dependent fortification protection and the requested stack roster position.

The exact behavior, controls and boundaries are documented in [stacking configuration](stacking-configuration.md#offensive-continuity-and-damaged-fortifications-2026-09-29) and the current [todo checkpoint](stacking-todo.md). No game was launched. No performance, conquest-rate or strategic-effectiveness improvement is asserted without an autoplay comparison.

## Offline validation

- Native VC9 actual-source offensive policy regression: route retries/repair, readiness, target ownership and handoff, naval water waypoints, incoming/training caps, capture feasibility and unknown budgets, moving stalls, XML disabling and cache reset.
- Native actual-source fortification/collateral and production reservation regression: siege/ranged-ship/bomber damage at full/half/zero HP, virtual prior damage, cap ordering, collateral HP floor, garrison absorption, building changes/healing, unique production promises, optional slots and cancellation.
- Existing allocation, no-op/endpoint/siege, bounded forecast cache, air/interception, production placement, observer expiry and native diagnostics regressions.
- Lua 5.1 roster, diagnostics and new measured-preview layout checks; parser covers the new native categories. These simulate UI services, so pixel placement still requires visual inspection.

Machine-readable evidence and each test's output: `work/test-runs/offensive-todo-offline/checks.json` and sibling logs. The fixtures use deterministic engine stubs; they do not test the real game's pathfinder, deployment loading or campaign efficacy.

## In-game test sequence once the user prepares the game

1. Confirm the new DLL version, load a disposable fresh modded game and enable Summary diagnostics. Preserve the user's existing saves.
2. Inspect two- and large-unit rosters, combat preview appearing/resizing/disappearing, collapsed/expanded roster, scrolling, empty-hex dismissal and ordinary/observer diagnostics visibility.
3. Test a full/half/nearly destroyed fortified city with siege, ranged ship and bomber attacks. Compare preview, native combat participants and actual HP; protection uses HP before the hit and collateral retains its 50% victim floor.
4. Exercise an army at a closed border, a blocked centroid route, a naval city operation and the across-water Edirne layout. Check readiness, capture path diagnostics, persistent target demand and actual formation joins, not just arrival notices.
5. Save/reload; validate no illegal stacks, crash or repeat-order loop. Then a fresh autoplay with Summary logging and selected Verbose windows around voluntary wars and sustained sieges. Compare route failure frequency, moving idle age, support arrivals/joins, capture feasibility and conquests against the archived campaign.

## Release prepared for in-game validation

- Source commit: `e8923d9f98cd5fac1ad377d52843b74a271a9a30`.
- Embedded DLL version: `Release-5.4.6-16-ge8923d9f9 Clean`.
- Native VC9 x86 Release: 178 translation units, two workers, 106.703 seconds. Build directory: `work/msvc-output/Release/20260929-213046`.
- DLL SHA256: `D217C8A7719149176B22C172F72ABD551110ADA1D2FEF2B620D8FE55AB0B54AE`.
- Matching PDB SHA256: `3ACDA06C1B57AFE0A4ADA65A8797753ED1DD8648AA9AFB1B8E56D8DB1DBA155C`.
- 506 source inputs match the build manifest; all 2367 deployed files are hash-verified.
- Previous installation archive: `E:/Projects/Civ5StackMod/work/backups/deployment-replaced-20260929-213422-af85d5f0`.
- All 50 pre-deployment saves retain their hashes. Graphics settings were verified unchanged. No game launch or runtime validation took place.
- All 15 offline suites pass, including 89 offensive policy checks, 40 collateral/production integration checks, 135 existing allocation checks, 55 diagnostics UI checks, nine new geometry checks and 17 parser cases. Existing combat/production/cache/observer suites also passed; their detailed counts and limitations remain in the captured logs.

Final evidence: `work/test-runs/offensive-todo-offline/release.json`, `checks.json` and individual logs. Source and documentation commits use the user's Git identity; nothing was pushed or published.
