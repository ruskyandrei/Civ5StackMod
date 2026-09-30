# Performance resume checkpoint — 30 September 2026

**Paused at the user's request. The game is closed; no autoplay, tuner service,
campaign heartbeat or performance build remains running.** The three research
agents were interrupted. Core Temp is the user's app and was left open.

## Current tested installation

- Branch: `b-stack-prototype`; last code commit `2cc4911ba`.
- Build/document checkpoint: `21481844d`.
- Installed DLL: `Release-5.4.6-50-g21481844d Clean`.
- Build: `work/msvc-output/Release/20260930-200233`, genuine VC9 x86 Release,
  179 translation units, two workers, 74.516 seconds; successful build.
- DLL SHA256: `2B97CEE47B2D8CF8EDC1377DC9FB2F62CF8860BEFFF65D6A1557387F2E85E4E3`.
- PDB SHA256: `FD471D865DBB0F013B9DE55A8DC3996A2B808888602AD7DDBA289AA3DA83A436`.
- Previous installed content:
  `work/backups/deployment-replaced-20260930-201549-ce16a145`.
- Retained DLL47 control build: `work/msvc-output/Release/20260930-171757`;
  SHA256 `93F10988D3DB148B04AA4A3E996F430BAD4FE4F68DD1031DBEA5EDE57500E0E4`.

The new code removes role-name allocations, mirrors the already-loaded Enabled
setting and shares the movement destination's temporary stack roster. It adds
sampled phase timings around original VP and tactical work. AI decisions,
combat math, XML numbers, search budgets and tactical limits remain unchanged.
Actual-source offline checks passed, followed by the matched runtime comparison.
There are **no partial full-melee-cache production edits**: that investigation
was interrupted before any source changes. Git was clean before this note.
These two new commits were local; no new push was made during performance work.

## Matched runtime result

The preserved observer post240 source was replayed through turn242 under DLL47
and DLL50. The interior turn241 is the comparable complete turn; source and
human-return turns are partial.

| Measurement | DLL47 control | DLL50 candidate |
|---|---:|---:|
| Comparable complete turn241 | 83.109s | 70.469s |
| PLAN search total | 55.523s | 44.466s |
| PLAN calls | 141 | 141 |
| Complete turn minus PLAN total | 27.586s | 26.003s |

The complete turn improved **12.640s / 15.2%** in this one matched test. This is
still well above the sub30s goal. It is not a general late-game performance
guarantee, and there is no candidate repeat yet.

- All **401 ordered retained native semantic records** match: 265 PLAN and
  136 COMBAT_SUMMARY records across the bounded replay. Captures and immediate
  city opportunity branches were not exercised in this position.
- Before: identical 830 units, 81 cities, 23 players and 112 directed war rows.
- After: identical 821 units, 81 cities, 23 players and 112 directed war rows.
  Compared identity/type/position/HP/movement/strength/population fields match.
- Both bounded runs stopped correctly on living human player0 at242 and were
  closed through the normal game API. No additional crash dump was generated.
  The process objects did not expose an exit code, so do not assert exit0.
- CPU/GPU guards stayed below their sustained cutoffs and disarmed on completion.
- Both used Summary diagnostics, quick combat/movement and the same five mods:
  CP151, VP17, EUI compatibility1, Squads1 and Small Resource Icons4.

Evidence:

- Control: `work/test-runs/perf-d47-c47-t241-control`, native
  `Stacking-20260930T190942-006-p39476-r1`.
- Candidate: `work/test-runs/perf-d50-c47-t241-candidate2`, native
  `Stacking-20260930T192611-146-p3144-r1`.
- Candidate `comparison-d47.json`, `finalphase-report241.json` and
  `configuration-proof.json`; both runs contain preserved before/after world
  snapshots, native segments, protocol records, telemetry and normal-exit notes.

**Timing trap:** new TURN_PHASE rows move the first-record turn boundaries.
Use the first non-TURN_PHASE record in each turn for a DLL47 comparison. The
all-row candidate interval is70.203s; that is not the matched70.469s measurement.
The updated `work/profile-turn-phases.py` handles both windows and passes33
offline tests. Phase times are inclusive; use interval unions/subtractions,
never sum overlapping parent, child and PLAN totals.

## What the broader profile found

Tactical search still dominates. Approximate measured nonPLAN costs include
tactical operations5.259s (stack offensive child0.704s), city turns/production
3.347s, homeland2.499s and tactical zone work1.593s. Economy is below1s;
military planning about0.5s and danger refresh about0.33s. Unit-power sorting,
ordinary unit upkeep and recruitment are0 at the coarse tick resolution;
visibility is about0.015s. These last routines are poor first targets here.

Roughly8.3s of the comparable interval is outside the measured phase unions.
This can include engine/callback/scheduling/rendering work; it is not proven
stacking overhead or CPU time. Full diagnostic-off/on controls remain pending.
No row truncation, missing segments, invalid phase bounds or reversed clocks
were found. All141 PLAN records have their preceding PLAN_PERF anchors.

## Next performance work, interrupted before implementation

1. **Complete melee-strength reuse during locked previews.** Current caches
   reuse generic melee modifiers, while original VP maximum attack/defense
   calculations still repeat on every generic hit. Investigate exact wrappers
   around the complete original bodies with separate key kinds. Preserve null
   source-plot semantics, every flag, projected self/opponent injury, city
   identity/HP and both city/opponent attack counters. An attack can have both a
   city and defender; the existing single counter word cannot represent both.
   Preserve bounded storage, scene/epoch/thread/nested guards and original math.
   Agent `/root/replay_harness` was auditing this; no production edits exist.
2. **Shared final damage ledger feasibility.** A stack danger query simulates
   all defenders, then returns one member's injury. Sharing the full result
   across queried members might avoid repeated simulations. Key dependencies
   include exact ordered membership/wounds, off-stack anti-air wounds, enemy
   and negative city-ID wounds, combat owner/team/friendly-city predicates and
   scene lifetime. Apply each member's hazards/city-fall sentinel separately.
   Agent `/root/forecast_hotspots` was reviewing this; no implementation exists.
3. If these are safe and worthwhile, use actual-source behavior/work-count
   fixtures, compile, then run the same bounded post240 comparison and repeat.
   Retain search limits and AI behavior. Examine city production, homeland and
   tactical operation remainders next, according to measured costs.

Read `work/strength-hit-performance-review.md` for detailed keys, guards,
cache-hit costs, candidate ranking and validation requirements. The existing
danger cache already serves about95% of queries at campaign250: do not multiply
all strength hits by stack size or assume every ledger query is a new simulation.
The original VP audit is [separate](legacy-vp-performance-audit.md).

## Preserved campaign and load crash

The long DLL47 campaign stopped at251 rather than its planned350.
`work/test-runs/campaign47-20260930-1735` contains its logs/replay/censuses and
unique manual251 save; SHA256
`2A31D7020FFA5348582DD46442D079308CEDC7880248C1B1623A39FF62BC659B`.
At the final250 census there were six conquest events on five city plots,
five current major-owned conquests and four major holdings retained20+turns.
There were no captures before200. AI count/cohesion, supply/production,
reinforcement, city healing/balance and voluntary-war follow-ups are recorded
in [the separate conquest note](decisive-war-campaign47-followups.md).

The first post250 control load crashed at19:56:52 BST under **DLL47**, before
any new DLL deployment or replay preparation. Fault: closed
`CivilizationV_DX11.exe`, RVA0x0037C6DA/raw-file offset0x0037BADA, access violation
through a non-null pointer. No gamecore frame was recovered; unavailable EXE
symbols prevent a reliable engine function identification. Low sub2GB free
space is recorded, but the dump does not prove out-of-memory or exclude a mod
interaction. Do not repeatedly retry it or claim the new optimizations caused it.

Dump/logs/review:
`work/test-runs/perf-d47-c47-t251-control2/load-crash-evidence`,
`crash-review.md`, `crash-review.json`, `fault-disassembly.txt`.

The working late-battle source is:
`work/test-runs/campaign47-20260930-1735/autosaves-at-stop/auto/AutoSave_Post_0240 AD-1650.Civ5Save`;
SHA256 `2EAF79F3A2C90CBAF46AEAFB393FBD0832A3E07AD53244C8B80C3B561D5BD87C`.
The separate historical `auto_275.Civ5Save` remains a known-load fallback, but
belongs to a different campaign and must not be mixed into this comparison.

## Practical resume safeguards

- No live game/service needs recovery. Start fresh only after the user resumes.
- Use one persistent `tools/civ5_tuner.py serve` connection per game-process
  lifetime; never reconnect it while the same game is running. No FireTuner or
  computer use is needed for the tested workflow.
- Back up engine autosave slots; arm exact-PID/start-time CPU and memory/GPU
  guards before loading. `work/start-short-performance-test.ps1` is a local
  ignored convenience wrapper; verify its guards actually arm.
- Full deployment clears the mod cache. Re-enable the **exact expected five
  mods** before activation, using the game's documented `Modding.EnableMod`
  API. Both failed setup attempts were preserved and stopped before activation.
  Do not accept an empty or different activation set as a valid comparison.
- The installed XML file has a different byte hash from the control because
  comments and the placement of three existing rows changed during earlier
  source cleanup. All231 parsed table/row records and values are identical;
  `configuration-proof.json` records this. Do not change XML for the next test.
- `work/run-behavior-replay.py` supports240→242, source SHA, expected DLL SHA,
  expected mods JSON, exact process identity and bounded human return. Existing
  output directories are rejected; use fresh evidence directories. Never
  repeat a mutation after an ambiguous timeout.
- Preparation must preserve paused observer8 and stop its restored counter with
  `Game.SetAIAutoPlay(0,-1)`. Manual251 has a human slot; it is not this fixture.
- Use `work/compare-behavior-performance-replays.py` for sorted nonzero
  before/after censuses and ordered native decisions; the older PERF_UNIT
  comparator cannot validate this harness's JSON snapshots.
- Shut the game and service down after each bounded test. Preserve logs even
  on failure. Do not restart a long campaign or resume AI/balance changes until
  late-game performance is addressed.
