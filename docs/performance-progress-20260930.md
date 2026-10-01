# Resumed late-game performance work — 30 September 2026

Target: complete turns250+ below30 seconds while preserving useful AI behavior.
The previous matched post240 test improved full241 from83.109s to70.469s under
DLL50 with matching recorded outcomes. That remains above the goal.

## Direct late-game control

The preserved manual251 save loads successfully under DLL50. An explicit new
`--source-mode human` test path validates the paused human return-player state,
then enters observer autoplay. VP deliberately chooses diplomacy/production/
research/policies during that slot transition. Compare only identical saved
source and preparation across builds; this is a normalized replay branch,
not proof of identity with the original uninterrupted campaign.

- Source: `work/test-runs/campaign47-20260930-1735/Stack DLL47 Campaign Manual Stop T251 20260930-1735.Civ5Save`.
- SHA256: `2A31D7020FFA5348582DD46442D079308CEDC7880248C1B1623A39FF62BC659B`.
- Control folder: `work/test-runs/perf-d50-manual251-control`.
- Native run: `Stacking-20260930T200459-934-p39284-r1`.
- DLL50 SHA256: `2B97CEE47B2D8CF8EDC1377DC9FB2F62CF8860BEFFF65D6A1557387F2E85E4E3`.
- Bounded251→253, human return0; complete comparable turn252 is **95.938s**,
  with **67.526s PLAN** over125 searches and28.412s outside PLAN's recorded sum.
- Final census:850 units,81 cities. Source save hash remains unchanged.
- Loaded and stopped correctly, then closed through the normal API. Process
  exit code was unavailable; no claim of exit0. CPU/GPU guards stayed below
  sustained cutoffs. A new candidate comparison is required before claiming
  any additional speedup.

Phase analysis now also includes adjacent-turn phase records whose time bounds
overlap the chosen legacy-comparable window. In this252 control,391ms of253
preparation was previously outside the selected-turn-only accounting. All
recorded phase unions leave10.124s unattributed; this is wall-clock time and may
include engine scheduling/callback/rendering. It is not proof of pure CPU work.

## First candidate prepared

Complete maximum melee attack/defense strengths are memoized inside the
existing locked preview scope, while retaining the original math bodies.
Keys include raw NULL-plot semantics, both city/opponent attack counters,
projected wounds, embark flags and same-promotion attack history. Scripted
movement-event paths in HeavyCharge and nonquick city blockade bypass full
attack reuse. Existing cache capacity and gameplay/search limits are unchanged.
Separate full-attack/full-defense hit/miss counters expose additional cache
pressure rather than hiding it.

Offline actual-source full-body comparison:140,042 checks passed; existing
generic/ranged/cache checks:96,078 passed. Engine services are deterministic
substitutes, so native outcome and timing comparisons remain necessary.

Compact `PLAN_EXEC_FAIL` and `PLAN_RETRY` Summary diagnostics were added to
explain rejected orders. The latter logs bounded ordered IDs and basic-state
signatures; equality does not establish complete tactical scene identity and
does not drive gameplay.89 actual-source diagnostic checks and16 batch checks
pass. Retry limits and the discovered legacy A_USE_POWER behavior are unchanged
pending runtime evidence.

In the252 control, Arabia's operations repeatedly search target25:25. Several
5–7s attempts have matching work counts and no intervening COMBAT record.
Two earlier attempts do execute ranged hits, so those are changed-state
replans. The new failure diagnostics are needed to identify the repeated
failures; Summary counts alone do not justify deleting retries.

## DLL52 native result and the next correctness fix

`c2de0e55f` built as `Release-5.4.6-52-gc2de0e55f Clean` in
`work/msvc-output/Release/20260930-212752` (179 translation units,75.015s).
DLL SHA256: `8B0440069823C61A54CB15AE65031A0E1868982C8DE136E22602757600E5350A`.

Matched manual251→253 run: `work/test-runs/perf-d52-manual251-candidate`,
native `Stacking-20260930T203510-790-p37228-r1`. Full252 fell from95.938s to
**77.594s**, with PLAN67.526s→49.908s over the same125 searches. All274 retained
semantic records match (199 PLAN,75 COMBAT_SUMMARY), with identical847-unit
before and850-unit after censuses,81 cities and23 players. No capture branch
was exercised. Normal API shutdown succeeded; no new dump. The game is closed.

The full cache removed most generic-only hits but raised shared-cache evictions
from755,940 to1,921,686 in252. Ranged misses increased2,172,185→2,489,429; complete
attack/defense hits were6,125,306/15,827,936. This is a measured tradeoff, not
evidence that cache capacity should be changed blindly.

New execution diagnostics identify the expensive repeated-plan cause. All eight
Arabia25:25 attempts fail `city_attack_gate`, for ranged units6976/7095 trying
to fire from2138 into city2225. Repeated attempts have equal ordered basic unit
signatures; preceding idempotent mission orders do exist, so this is not a claim
that no calls occurred. Both city-attack scorer gate returns use `SetScore(0,0,0)`.
`IsAcceptable()` rejects only the impossible sentinel, and virtual assignment
application still applies the retained damage payload. A denied attack can
therefore influence a plan and then fail execution repeatedly.

The next candidate changes those two denial returns to `SetImpossible()`,
preserving `AllowCityAttack` policy and search/retry limits. This is an intended
correctness change, so subsequent actions/outcomes may differ; exact old-plan
equivalence is no longer the acceptance test for that fix. Validate denied
actions cannot enter virtual plans, preserve allowed/capture paths, then inspect
runtime failures and complete-turn times. Ledger production remains on hold
until this simpler fix is measured.

The source fix and39 actual-source checks are ready: the old control admits
50 points of phantom city damage; rejected fixed actions cannot enter the
candidate list or advance the virtual city state. Allowed/capture/unit-combat
paths retain their outputs. Native evidence identifies target2225 as Utrecht
(Netherlands); the eight Arabia plans cost35.335s total, including valid earlier
orders before failure. This is not a claim that all35.335s can be eliminated.
See `work/test-runs/perf-d52-manual251-candidate/denied-city-attack-review.json`.

## DLL53: denied-city attack fix measured

`6f383711c` built as `Release-5.4.6-53-g6f383711c Clean`, in
`work/msvc-output/Release/20260930-214752`. Installed DLL SHA256:
`F6B4A2F0E6E3063B99BBB666A760271ABF57EDAB3AD5E269E55EC37AB03FAF9C`.
The matched manual251 replay is `work/test-runs/perf-d53-manual251-citygate`.
The measured252 window fell from77.594s to **48.234s**, PLAN49.908s to15.293s,
with125 to116 searches. The 30-second target is not yet met.

The Utrecht plans cost35.335s before and2.270s after the fix. Across turn252,
city-attack-gate execution failures fell16 to0, total retries22 to4, and retries
with unchanged ordered basic unit state13 to0. Remaining retries involved actual
movement/combat/visibility changes. The fix deliberately changes actions: two
additional field-combat records occurred; no city capture was exercised. Utrecht
remained Dutch,82 damage of534HP after253. Final census850 units and81 cities;
normal API quit completed, no new crash dump. This is not a conquest result.

All recorded phase intervals cover33.516s of that48.234s window;14.716s remain
outside those scopes. Roughly9.721s lies between major-player turn processing and
the first actual unit-AI pass. These are wall-clock gaps, not yet evidence of CPU
work, intentional delays or renderer cost. Next instrumentation measures the
pre-AI script hook/busy guard and thread CPU time with bounded aggregate rows.

### Benchmark boundary correction

The earlier manual251-to253 runs used an identical bounded autoplay setup, but
the ending boundary includes return-to-human processing: `CvGame::doTurn`
decrements autoplay before incrementing the game turn. Their95.938/77.594/48.234s
windows are useful matched samples, not proven steady observer-turn timings.
The next control/candidate runs use251-to254 and measure252-to253 while autoplay
remains active at both boundaries. Exclude the final return-adjacent interval.
Retain the same immutable source, normalization, options and diagnostics.

Exact optimization candidates now being integrated separately from the city-gate
fix: caller-local full danger outcomes behind the existing scalar cache, and a
genuine VC9/x86 acquire read replacing redundant Interlocked read-modify-writes.
Both retain cache invalidation/ownership checks and search/entry budgets. Their
isolated tests do not establish a whole-game performance gain.

## Further candidates

- Caller-local reuse of complete stack damage outcomes behind the existing
  scalar cache. An isolated exact-source split prototype passed288,016 checks
  with numerical services substituted; field/city/air/collateral loop order,
  off-stack AA wounds, raw-ID aliases, city-fall sentinels and hazards are
  covered. Production integration is held until the first candidate is tested.
- If full strength keys cause eviction pressure, project only proven equivalent
  injury modifiers/thresholds in the key, keeping original math and bounds.
- Diagnose actual execution failures before changing retry behavior.
- Measure the pre-unit-AI Lua hook/busy guard and engine dispatch gaps with
  aggregate timing; do not create per-poll logging or assume a fixed delay.
- City production, homeland and operation execution are secondary measured
  costs. Unit sorting/visibility were tiny in241. Legacy compiler LTCG is
  disabled because of earlier linker hangs; avoid treating toolchain changes
  as a proven improvement.

All new work remains local unless explicitly pushed. Preserve both the original
DLL47 and DLL50 controls, saved inputs, normal-exit records and crash evidence.

## Steady-observer control before the outcome-cache candidate

`perf-d53-steady251-control` completed manual251-to254 and quit normally;
native run `Stacking-20260930T211159-845-p16080-r1`. Interior252-to253 is
**45.031s**, PLAN14.757s over116 searches, with17421ms in measured phase
work outside PLAN and about12.9s outside selected-turn phase scopes. This
confirms that returning to a human did not explain most of the earlier48s.

The following253-to254 interval is132.188s, PLAN99.943s over139 searches.
It includes the final return transition, but that cannot explain the99.943s
of measured search. Multiple large Arabia plans around Utrecht dominate;
actual movement/combat changes and a city capture occur during the retries.
Preserve this harder case for correctness and performance comparisons instead
of presenting252 as a general late-game result. Detailed retry analysis is
in progress; do not simply suppress retries after real state changes.

The next candidate leaves search, score, actor and cache-entry limits unchanged.
It reuses complete damage outcomes locally in protector/source-leaving queries,
retains the original scalar fallback, and uses the documented genuine VC9/x86
acquire-read semantics for owner/epoch reads while retaining atomic writes.
Sampled entry-hook/busy timing and absolute same-thread CPU counters distinguish
script/lock waits from work between existing phases. Offline numerical/thread
fixtures establish bounded equivalence, not measured native speed gains.

## DLL54 outcome-cache and CPU instrumentation result

Clean commit0273c8e3e built54 in `work/msvc-output/Release/20260930-222029`
(79.953s,179TUs). DLL SHA256 FAC046D16E8D71B1286D868D8A7A616DD1DAAAB811FD7FF325BF14414724593F;
PDB88A0D4CC7D77A0C8021610E7E46176138B8CA2F3E9F6E6814E4C9495691FC343.
Run `perf-d54-steady251-candidate`, native `Stacking-20260930T212613-631-p22664-r1`,
completed251-to254, normal API quit and service stop, no new crash.

All506 compared semantic records match53, including329 plans,176 combats and
one city capture. Before847 and after840 unit rows,81 cities,23 players and
90-to102 directed war rows also match exactly. Turn252 measured42.922s,
PLAN14.799s; turn253 measured142.000s,PLAN104.543s. Compared with45.031/14.757
and132.188/99.943, this pair does **not** establish a tactical speed improvement.
Do not report the isolated cache microbenchmark as a whole-turn gain.

Outcome reuse is active but rare on252:3869 builds,6434 reuses,0 bypasses,
peak retained payload288B, versus193667 scalar misses and6762339 hits. Its
future retention should depend on broader/isolated measurements, not test counts.

The added CPU endpoints localize the252 gap: all-bound phase coverage32.753s,
uncovered10.169s, only359ms of measurable same-thread CPU in those gaps.
Large gaps before unit-AI entry for players1/7/4/6 were1813/1375/906/906ms
with unchanged GameCore CPU counters. Entry instrumentation recorded23 calls,
zero busy returns and zero hook/guard coarse milliseconds. This turn does not
implicate that pre-AI Lua callback. Other threads can be working while GameCore
waits; renderer, engine dispatch and lock causes remain hypotheses.

Next controlled presentation experiment uses recorded explicit standard and
strategic modes on this same54 build, with unchanged gameplay/diagnostics and
exact semantic/census comparisons. Earlier runs did not record actual view mode,
so they are not sufficient proof of a standard-vs-strategic causal comparison.
Separately,253 execution analysis found garrison-victim identity checks and
post-city-capture stale defender pointers worth fixing under dedicated tests;
valid damage-roll/movement divergence must continue to cause replanning.

## Presentation and legacy logging controls (DLL54)

Explicit standard-view/full-legacy-log control:
`perf-d54-standard-full-logging`, native `Stacking-20260930T213726-727-p36392-r1`.
T25246.703s/PLAN15.183s; T253128.797s. Raw252 phase CPU31.203s and
unscoped wall13.392s with343.75ms of same-thread gap CPU. Hook/busy checks
remain23 calls,0 busy returns and0 coarse milliseconds.

The first strategic setup (`perf-d54-strategic-full-logging`) failed before
continuation: EUI's deferred active-player handler restored standard view after
the immediate preparation toggle. Verified251/observer8/counter3/paused8, quit
normally; no autoplay time accepted. The harness now applies explicit view in
a separate late InGame command after census/slot events, verifies it separately,
and retains initial and final preparation proof. No ambiguous mutation retry.

Successful strategic retry: `perf-d54-strategic-full-logging2`, native
`Stacking-20260930T215134-377-p10560-r1`. T25243.750s/PLAN14.194s;
T253128.313s/PLAN95.295s. All506 semantic events and all census rows match
standard control, including the city capture. Gap12.139s still contains only
312.5ms same-thread CPU; strategic view did not eliminate the waits. The small
single-pair total difference is not a general renderer speedup claim.

Legacy logs disabled in a fresh standard-view process: only AILog, AIPerfLog,
BuilderAILog changed1-to0, preserving LoggingEnabled/MessageLog and native Summary.
`perf-d54-standard-native-logging`, native `Stacking-20260930T220122-917-p32108-r1`,
T25244.797s/PLAN14.685s, T253130.265s/PLAN95.956s. All506 events and censuses
again match. This is a small measured contribution, not the main bottleneck.
`work/engine-logging-profile.py` backed up and restored original config bytes;
restoration22:05UTC hash04b4aaa0a9360cadbb8ef0da277441a11af95dd50bfa8334d3bc179b29b627f3.
All game/service processes from these experiments are closed; no new crash dump.

Next56 candidate is exact full-strength wound-key canonicalization plus bounded
update/activation timing, preserving54 gameplay for native equivalence testing.
A separate explicit primary victim owner/ID tactical fix is prepared under
`work/primary-identity-production.patch`, deliberately held until after the cache
comparison. It avoids the more intrusive discarded projected-damage HP gate.
Do not claim these pending changes are installed or native-validated yet.

## DLL56 exact cache result and dispatch localization

Workflow controls were saved separately in4bfc9812d. Source commitf412182f4
built `Release-5.4.6-56-gf412182f4 Clean` in
`work/msvc-output/Release/20260930-231318` (80.875s,179TUs).
DLL SHA30060AE35E0A90BC7533205CB15D733C4A92F5821F851DC4E8AE3D0901AC7F94;
PDB050F3D75CAADA12025FC9DCAE96C0B859C2EBF77F9BA30CD9D37006B5CB40F9B.

`perf-d56-standard-full-logging`, native
`Stacking-20260930T221954-848-p32136-r1`, completed and quit normally.
All506 semantic events and before/after census rows match recorded54 standard
control, including Utrecht capture. T25246.250s/PLAN14.013s; T253126.328s/
PLAN91.064s. This is a modest search improvement; the30-second target is unmet.
T253 strength evictions declined8,393,930 to5,743,198 compared with the earlier
54 candidate with the same event sequence. Full defense misses2,461,680 to828,749;
full attack misses767,667 to565,897. Remaining ranged misses5,685,222 motivate
separate proof work, not changing the cache budget.

The new bounded update markers localize23 T252 activation windows totaling14.405s:
all14.405s occurs between consecutive CvDllGame::Update calls, with unchanged
GameCore CPU counters. Each has two wrapper spans and one dispatch interval;
activation tail, update body/head and begin/end Lua hooks round to0ms. No nested
scopes or reconciliation remainder. This does not identify a particular external
wait: wrapper-constructor GameCoreLock acquisition occurs before Update itself.
A narrowly scoped constructor acquisition counter is prepared for the next build.

The next build also applies the separately reviewed explicit-primary-victim
executor fix. That intentionally changes some actions, so do not require its
native sequence to match56 blindly. Validate the corrected victim/capture checks,
legitimate roll/visibility restarts, source/preparation proof and actual timing.
The tactical patch adds8 bytes per ephemeral assignment and changes no save
format, combat math, search limits or army requirements. The original projected
HP-consistency-gate prototype remains excluded.

## DLL57 combat-victim correction

Commitdea6f2eae built57 in `work/msvc-output/Release/20260930-233436`
(74.140s). DLL8EDD72FC79390888BEC3347CF4992A2BA53388C8408AF3CFF47CB0807C7AB70F;
PDBD3C273E885B31E3FAB7F0F6EC66A5B49898E27AF3529697DA52C46C91F97E926.
`perf-d57-standard-full-logging`, native
`Stacking-20260930T224217-405-p38320-r1`, completed and quit normally.
Source/preparation/before census match56; subsequent actions intentionally differ.
T25246.125s/PLAN14.014s; T253100.922s/PLAN65.404s. Goal<30s remains unmet.

The third Utrecht garrison-killing shot now continues its plan instead of
reporting a false surviving-defender result. Two earlier predicted kills still
leave the expected, correctly matched garrison alive, so they still replan.
Utrecht capture by8125 (combat125) passes its postcondition; the following
visibility restart is intentional. Further forecast-versus-rolled-damage analysis
is separate from the corrected identity/stale-pointer checks.

Constructor instrumentation records44 of44 acquisitions at0 coarse milliseconds
inside the23 T252 pending windows. Their14.472s dispatch wait remains outside the
measured acquire as well as Update/tail/hooks. This rules out that constructor
path as the multi-second cause in this sample, not every engine synchronization
path. A bounded read-only OS thread-state sampler is being prepared; no suspend,
attach, priority change or game call is needed for that first observation.

Next58 is exact ranged-strength projected-key canonicalization, with original
ranged body unchanged. It uses the ranged ceiling-half predicate, effective
support-fire base and ignored-argument shortcuts, and preserves scripted city
blockade callbacks by bypassing cache when movement events are enabled. Offline
actual-source and related regressions8,360,158 checks passed; native equivalence
against57 and speed remain to be measured. No search or cache capacity increase.

## DLL58 ranged cache and next engine wait test

Commit b977a7a0b built Release-5.4.6-58-gb977a7a0b Clean in
work/msvc-output/Release/20260930-234959 (72.796s, 179 TUs).
DLL E53BEC3BECF4B3C2E5633632000370D5AA7B93C543AE8A3AD4F0FB5D39EE4797.
perf-d58-standard-full-logging completed and quit normally; native
Stacking-20260930T230011-989-p22880-r1. All 508 retained semantic events
(333 PLAN, 174 COMBAT_SUMMARY, one CITY_CAPTURE) and before/after censuses
match DLL57 exactly. T252 44.625s / PLAN14.017s; T253 96.140s / PLAN60.123s.
The return-adjacent T253 window is heavier; T252 is the steady observer window.
Neither meets the requested <30s target.

T253 ranged strength misses declined 3,721,776 to 636,315; total strength
cache evictions 3,376,480 to 54,191. About 63.2 million strength queries and
21.2 million danger hits remain. T252 PLAN timing is effectively unchanged.
The exact reuse is validated for this replay, not a universal speed guarantee.

A separate DLL58 run, perf-d58-thread-state-diagnostic, now records bounded
same-user OS thread-state snapshots. It includes observer-helper overhead and
must not be mixed with quiet performance control measurements. No attach,
suspend, Lua, affinity/priority change, or ETW recording is used by that helper.
Current normal config hash remains 04B4AAA0A9360CADBB8EF0DA277441A11AF95DD50BFA8334D3BC179B29B627F3;
GameCoreThreadingUsesJobManager is still 0. A backed-up one-setting test is
being prepared only after understanding the observed dispatch gaps.

The dedicated-thread OS diagnostic has now completed and quit normally. Its
508 retained events/censuses match quiet58. Across63 pending windows totaling
27.056s,232 sample points fell inside;228 were Wait/Suspended,4 Running at
boundaries. Excluding sampling/boundary uncertainty gives211/211 Suspended.
No inside sample was Ready or ExecutionDelay. This supports actual GameCore
suspension between updates, not the identity of the suspending caller/policy.
See perf-d58-thread-state-diagnostic/thread-gap-findings.md and correlation JSON.

A container-only VC9 prototype passed433,010 differential checks with identical
entry caps, FIFO evictions, full-key equality, values and stats. Synthetic hit
loops are1.8x faster, but at the observed63.2M strength hits this suggests only
about2.2s cache-only saving; peak requested allocation rises1.75→2.69MB during
vector growth. It remains an ignored experiment, not production code. A sampled
native scorer/danger profile is a better next step than assuming this removes
the remaining60-second tactical search cost.

## DLL58 job-manager comparison (configuration restored)

One exact byte changed GameCoreThreadingUsesJobManager0→1, with
EnableGameCoreThreading1 and every other config byte unchanged. Applied SHA
93525313A52F9C11C29C58069329C6AE9CAB902EFB399CEA3FF071A2F11F3CEE.
The profile backup is work/test-runs/job-manager-profile-d58. Quiet run
perf-d58-job-manager, native Stacking-20260930T231633-829-p39792-r1,
completed254 and quit normally; all508 events and censuses match quiet58.
T25238.453s/PLAN13.031s; T25384.985s/PLAN55.409s. Compare quiet dedicated-thread
58:44.625/14.017 and96.140/60.123. Both search and outside-search time differ,
so one pair does not isolate scheduler benefit from CPU/run variation.

Original config bytes were restored after game39792/service shutdown; SHA
04B4AAA0A9360CADBB8EF0DA277441A11AF95DD50BFA8334D3BC179B29B627F3.
No permanent engine setting change has been retained. Thread distribution and
same-thread timing coverage must be reviewed before attributing the change.
Next diagnostic build samples tactical scorer/danger costs with fixed per-PLAN
counters and bounded timing; it does not alter search limits or scoring.

## Quiet-window continuation and opt-in tactical samples

The second job-manager replay was stopped by the CPU temperature guard during
T253 after three samples of97,98,97 C. Concurrent read-only process counters
observed one Brave process using11–14 CPU cores. This run is incomplete and
cannot validate the setting's performance. Its evidence remains in
perf-d58-job-manager-repeat/guard-stop-review.json and guard-stop-evidence.
No new crash file appeared; the newest dump remains the DLL47 September30
19:56:52 crash. The persistent service was stopped and original config bytes
restored. The user subsequently closed Brave and provided an eight-hour quiet
window. Keep the engine setting at its original0 until a clean comparison.

The source candidate now adds default-off tactical sampling with a strict Lua
boolean toggle and XML DiagnosticsTacticalSampling0. It records one bounded
PLAN_SAMPLE row per eligible search. The sampled methods are inclusive wall
measurements; they overlap and are not CPU-share or additive phase totals.
See docs/tactical-sampling-diagnostics.md and work/plan-sample-profiler.md.
Relevant actual-source/Lua/config regressions766,624 checks passed. All eight
production files restore byte-for-byte to DLL58 after only marked diagnostic
additions are stripped. One old siege fixture retains a documented preexisting
stale scaffold compile failure. Separate-object inactive probe measurements are
approximately1–2ns per call; enabled native overhead remains unmeasured.

The replay harness records strict sampling control proof and a read-only game
setup census (map dimensions/world type/speed/alive major count). The comparator
reports only view_and_tactical_sampling_controls_equal, explicitly excluding
engine threading/configuration/logging equality. Next quiet off/on replay pair
uses the same candidate DLL/config/save and251→255 so252 and253 are both interior
observer turns. Required goal remains verified<30s per standard late-game turn,
then an attempt at<20s; neither is proven by the current results.

## DLL60 native control and rejected DLL61 cache experiment

The quiet Standard-map replay pair completed251→255 with the same manual
source, original dedicated-thread configuration and full logging. Sampling
off/on retained identical699 planning/combat/capture records and all world
censuses. Interior turn252 took39.031/39.099s and253 took84.422/84.782s;
PLAN totals were13.275/13.316s and56.073/56.252s. Both games quit normally.
These are one paired observation, not a statistical overhead bound.

DLL61 (`edafcd48d`) extended the exact defender memo into field-danger
previews. Its1,149,421 regression checks passed and its native replay preserved
all699 ordered records and nonempty before/after censuses. Nevertheless it
regressed turn252 to39.454s and253 to92.984s (PLAN13.843/64.374s).
For253, danger misses increased1,155,413→1,417,639 and danger evictions
461,651→896,745. Defender reuse saved existing strength lookups but added
1,848,516 defender misses and1,395,679 defender evictions in the same bounded
forecast pool. Increased cache pressure and preparation outweighed reuse.

The entire trial was reverted in490ee12c4, without rewriting history or changing
search/storage limits. It remains reproducible from its commit and
`work/test-runs/perf-d61-defender-off-251-255`, including the exact comparison,
guard logs, normal-exit proof and `defender-trial-counters.json`. The installed
DLL61 is inactive while the next separately measured build is prepared.

The next candidates remove zero-AoE ledger scans and per-branch plot-score tree
allocations. Both must preserve scores, candidate ordering and full search
budgets; numerical and native behavior comparisons remain required. Goal
<30s after250 remains unmet, and no broad late-game timing claim is warranted.

## DLL64 empty-ledger work and DLL65 score-container trial

DLL64 (`fb45e447e`) combines the separately committed default-off diagnostic
cadence revision with the two zero-AoE forecast guards. Its quiet sampling-off
251→255 replay completed and quit normally. All699 native semantic records
and before/after player/unit/city/war censuses match DLL60. Interior252 took
38.781s (PLAN13.238s);253 took84.031s (PLAN55.497s). The small difference from
60 is within ordinary run variation; the verified removed fixture work does
not establish a substantial native speed gain. Source/run evidence is in
`perf-d64-zero-aoe-off-251-255` and `docs/zero-aoe-danger-forecasts.md`.

DLL60's253 CPU profile covers73.625s of same-thread CPU inside fully contained
native phase unions, with8.374s of uncovered elapsed gaps and0.344s of measured
CPU across unambiguous same-thread gap endpoints. Inclusive nested scopes must
not be added. This supports continuing to reduce computation as well as studying
engine scheduling; eliminating uncovered waits alone cannot meet30s here.

The next separately validated trial replaces only the protected plot-score
map with sorted contiguous `(int,short)` records. Current-production VC9
regressions pass49,687 checks and strict source-delta guards. Scores, integer
iteration order, short conversions, CoW borrowing and search policies are
unchanged. Allocation counts decrease in isolated repeated-copy fixtures;
native timing/RSS and retained action comparison remain to be measured.
See `docs/flat-tactical-plot-scores.md`. Broad nested CoW retention is deferred
because actor/plot caps do not tightly bound retained history and nested vectors.

## DLL65 native results and rejected DLL66 history trial

DLL65 OFF completed the same251→255 replay with all699 ordered records and
nonempty before/after world censuses equal to64/60. Turn252 took38.016s
(PLAN12.718s);253 took81.938s (PLAN54.071s). Its sampling-ON control retained
the same records/censuses and took38.172s/82.437s (PLAN12.772s/54.151s).
Both games closed normally. This modest single-pair improvement does not yet
meet the30s goal or establish performance on other maps and late turns.

The denser ON profiler parsed116/143 plans without schema errors. Turn253's
known-plan estimates include next assignments51.24s, preferred assignments
47.34s, danger leaves26.80s and key preparation6.52s. These are overlapping
inclusive estimates with unsampled work; subtracting parent and child estimates
does not produce exclusive time. Damage-math instrumentation also has a
meaningful floor. Computation inside tactical search remains the main target.

DLL66 (`a44557171`) reused shared history prefixes only in the protected main
search. Its111,472 actual-source regression checks passed; all699 native
records/censuses again matched65. Native252 took38.250s (PLAN12.784s),253
82.640s (PLAN54.567s), providing no measured improvement. It was reverted in
`8aac77ca7` rather than retaining added complexity. The failed trial remains
available in its commit and `perf-d66-shared-history-off-251-255` evidence.

The next candidate mirrors24 hot XML settings into value/presence arrays,
preserving string lookup and reentrant loader behavior. Its3,985 production
checks and24,075 reentrant probes passed. Synthetic savings are modest;
native performance and699-event/census comparison remain required.

## DLL69 native lookup result and automatic benchmark shutdown

DLL69 (`9c4b9915e`) completed251→255 with sampling OFF, the same Standard
source/config/mods and all699 ordered native records plus nonempty censuses
equal to65OFF. Interior252 took37.407s (PLAN12.029s),253 took79.218s
(PLAN51.146s), versus38.016s/81.938s for65. This is a useful single paired
observation; it still falls short of30s and needs broader late-game validation.
Evidence is in `perf-d69-hot-settings-off-251-255/comparison-d65.json` and its
phase reports. The original save remains unchanged.

The separate workflow commit `d99b16dfc` passed its first native automatic-exit
test: bounded human return at255, complete censuses/native archive/offline
analyses, one acknowledged normal quit, confirmed exact game exit, one service
stop, confirmed service exit and absent session file. No forced termination,
reconnect or retry occurred; `normal-exit.json` records each stage. The game and
service were both closed by02:42:56 UTC. These exit proofs are separate from
the comparator's recorded semantic agreement.

## DLL71 legacy resource result

The separately committed full-movement duplicate-check removal (`f43546572`)
and sparse unit-resource metadata (`ee180b91d`) completed the same OFF replay.
All699 native records and nonempty before/after censuses match69. Interior252
took37.454s (PLAN11.902s),253 took78.703s (PLAN50.828s), versus37.407s/79.218s
under69. This pair provides at most a small gain within run variation; the
substantial fixture work reduction is not evidence of a large native speedup.
Both game/service closed normally at02:56:06 UTC. Evidence is in
`perf-d71-sparse-resources-off-251-255`.

A separate roster fixture ran during save loading and ended at02:52:37;
bounded autoplay continued at02:52:50.758. It did not overlap the retained
252/253 timing intervals. That roster experiment has not passed its runtime
fixture and is unapplied; its timeout is not a Civ V crash.

## DLL73 combined forecast representation result

The immutable enemy fragment (`84269fd7b`,29,938 production checks) and
contiguous strength-cache representation (`ddab3d933`,433,070 production checks)
completed the same OFF replay. All699 native semantic records and nonempty
censuses match71. Interior252 took36.500s (PLAN11.371s),253 took74.656s
(PLAN47.002s), versus37.454s/78.703s for71. This paired result supports retaining
the combined changes; it does not attribute the saving to either one alone or
establish the30s goal. `perf-d73-index-enemy-off-251-255` preserves comparison,
native phases, guard logs and acknowledged normal game/service shutdown at
03:06:37 UTC.

The next diagnostic-only trial measures complete-key overlap among scalar
danger misses, separately from existing local outcome reuse. Its opt-in,
bounded metadata cohorts will be used to decide whether broader packet reuse
has enough native opportunity to justify another representation change.

## DLL74 diagnostic replay and observed overlap

Diagnostic-only DLL74 (`f194cff95`) completed251→255 with tactical sampling ON.
The deliberate cross-sampling comparison retains all699 native actions and
nonempty censuses from73OFF. Interior252 took36.719s (PLAN11.487s),253
75.250s (PLAN47.279s). This measures the combined profiler/probe run, not an
optimization or statistical bound on instrumentation overhead. Exact game and
service shutdown completed at03:27:07 UTC.

All116/143 probe rows match sampled timing identities at252/253; no invalid
rows, missing samples, source-unavailable observations or invalidated queries
were reported. Turn253 retained17,182 cohort queries,8,616 admitted groups,
8,566 repeats and15,925 queries doing fresh work. Of those fresh-work visits,
7,321 repeated an earlier fresh query and6,048 introduced a different member;
1,257 cohort queries already used the local batch. Metadata FIFO evicted149
groups and cleared290 times. Its deterministic selection and bounds censor
these counts: do not multiply them into saved simulations or seconds. The
observed overlap supports testing wider shared outcomes using the existing
forecast pool, rather than adding another competing result table.

Evidence: `perf-d74-packet-probe-on-251-255/packet252.json`, `packet253.json`,
phase reports and `comparison-d73.json`. The offline reader separately checks
coverage, field/city admissions, bounds, duplicates and exact identity. New
probe rows are excluded from historical turn-boundary anchors; all-event
boundaries still include them. Goal below30s remains unmet.

## DLL77 roster and previous-score result

Previous-score reuse (`9be3018e5`,72,260 production checks) and enemy-roster CoW
(`cf8f842e2`,154,342 production checks) completed the same OFF replay. All699
native records and nonempty before/after censuses match73OFF. Interior252 took
36.266s (PLAN11.044s),253 took73.797s (PLAN46.153s), versus36.500s/74.656s for73.
This is a modest combined gain in one paired run; no individual attribution or
general late-game performance conclusion is justified. The game/service both
closed normally at03:47:43 UTC. Configuration and graphics flags retain the
original04B4AAA0A9360CADBB8EF0DA277441A11AF95DD50BFA8334D3BC179B29B627F3 hash.

The next shared-outcome experiment remains work-only. It must preserve the
cheap original scalar hits, keep packet/scalar entries under the same existing
pool budget, preserve required source refreshes and validate city protection,
actual city HP, raw ordered sources/hazards and scene state. Event-enabled
city bombard paths conservatively bypass expanded reuse. Native timing remains
unknown. Existing CP/VP source defaults city bombard events off; runtime option
verification was unavailable while deployment cleared the database cache.
The regenerated runtime database was checked read-only at04:12 UTC: both
`EVENTS_CITY_BOMBARD` and `EVENTS_CAN_MOVE_INTO` are0; the separate
`BALANCE_BOMBARD_RANGE_BUILDINGS` option is1. The proposed optimization still
bypasses event-enabled configurations rather than assuming these defaults.

Evidence: `perf-d77-rosters-prev-off-251-255/comparison-d73.json`, phase reports,
guard logs and normal-exit proof. Best current controlled pair remains
36.266s/73.797s, so the goal is still active and unmet.

## DLL77 quiet engine threading retest

`perf-d77-job-manager-251-255` completed with only
`GameCoreThreadingUsesJobManager` changed0→1. All699 records and nonempty
censuses match77OFF. Interior252 took35.875s (PLAN10.925s);253 took73.218s
(PLAN45.802s). The subsecond changes do not establish a worthwhile general
improvement. The exact game/service closed normally at04:19:20 UTC; the
original config hash04B4AAA0... was restored. Unlike the earlier interrupted
trial, no heat guard or Brave contention affected this run. Source, DLL,
graphics, sampling and logging were held fixed.

The next separate trial removes out-of-line `PlanSampleScope` completion calls
when its existing `sampled` flag is false. It retains the selected completion
body and constructor, with89 actual-source lifecycle/cadence checks passing.
Native ROI is pending; it does not alter gameplay or reduce search limits.

## DLL78 inline completion result

`b0092e54d` completed the OFF251→255 replay with all699 native actions and
nonempty censuses matching77. Interior252 took35.906s (PLAN10.895s),253
73.969s (PLAN46.077s), compared with36.266s/73.797s for77OFF. This pair shows
no clear overall wall-time improvement: the fast turn improves slightly and
the slower turn regresses slightly. The narrow inline gate remains correct,
with89 actual-source lifecycle/cadence checks and fewer unselected completion
calls, but no meaningful general performance gain is claimed.

The exact game/service closed normally at04:29:06 UTC; configuration retains
the original04B4AAA0... hash. Build66.281s under
`work/msvc-output/Release/20261001-052115`; DLL
B045482865CB7F1F6CA2F5B8256C9516862AF532AF4C1DBEB6381D8C2882F41A.
Evidence: `perf-d78-inline-finish-off-251-255/comparison-d77.json`, phase reports
and normal-exit proof. The target remains unmet; the slower controlled turn
still takes about74seconds.

## DLL79 shared-packet native result

The corrected `e0d85052b` build completed251→255 with all699 recorded actions
and nonempty censuses matching78. Interior252 took35.953s (PLAN10.941s),253
72.891s (PLAN45.266s), versus35.906s/73.969s for78. The slower turn saves
about1.1s in this pair; repeatable or general benefit is not established.

At253,197,339 shared-result hits coexist with105,176 additional scalar misses
and333,928 additional evictions. Local-batch reuses decrease41,734→28,187.
The same table peaks at6000 entries, with maximum payload623,952bytes versus
623,624. Sharing is real, but added cache pressure limits its gain. Per-search
counter sums and coarse search timings are not independent exclusive CPU
measurements. `outcomeBuilds` now includes direct packet builds; it cannot be
compared as a local-only build counter across79. Missing old packet counters
remain unknown in the reader.

Full build initially caught the source-owner integer→`PlayerTypes` conversion;
the explicit cast corrected it. A separate7-check fixture uses the actual enum
and player accessor signature and rejects the pre-fix helper. The amended local
commit retains11,784 production-bound numerical/storage checks and100 parser
checks. Corrected full build66.062s, DLL
3269ABF3379207808138F0B22B4BF19909B07DF9341CFF61AF1C95F9A290F056,
under `work/msvc-output/Release/20261001-054342`. The exact game/service closed
normally at04:52:32 UTC; no crash or safety cutoff occurred.

Evidence: `perf-d79-shared-packets-off-251-255/comparison-d78.json`, phase reports,
`cache-comparison-d78.json`/`.md`, and normal-exit proof. The next compiler trial
keeps this source and all controls fixed while enabling the Release project's
existing whole-program/link-time optimization through the direct builder.
It has a bounded process/temperature monitor and must pass the same native
comparison before acceptance. Target below30s remains unmet.

## Bounded same79 compiler experiment

The GL/LTCG trial compiled its source/PCH and reached linking under
`work/msvc-output/Release/20261001-055519`. The linker accumulated4.766s of CPU
and about204MB private memory, then made no log/CPU progress. The monitor
stopped the verified owned launcher/linker at04:57:46 UTC after120s without
progress (146.609s total). There is no complete candidate DLL/PDB or native
performance result. No shared PDB service was stopped and no retry was made.
The process inventory confirms no remaining cl/link/game processes. The later
read-only thread diagnostic found the linker already exited and records that
refusal rather than inventing a wait cause.

Evidence: `build-d79-ltcg-trial/monitor-result.json`, `build-monitor.jsonl` and
builder logs. The earlier Zi hypothesis did not explain or resolve this Z7
attempt. Normal tested79 remains installed; the next separate source candidate
changes only strength-cache hashing while retaining full-key equality/FIFO and
all guards. Native ROI is pending.

## DLL80 full-word hash native result

`dc71d1955` completed the same OFF251→255 replay and matched all699 recorded
actions and nonempty censuses from79. Interior252 took35.750s (PLAN10.886s),
253 took72.750s (PLAN44.987s), versus35.953s/72.891s for79. These are small
improvements in one pair; the isolated30% hash improvement does not translate
into a large whole-turn win. The normal compiler/controls remain unchanged.

Build65.906s under `work/msvc-output/Release/20261001-060242`; DLL
3A7B4EA2F72F104753D39ED4ADE9B8ABB1D866D3356AC937BCB4DEE955C71E09.
The exact game/service closed normally at05:11:34 UTC. Evidence:
`perf-d80-strength-hash-off-251-255/comparison-d79.json`, phase reports and
normal-exit proof. Best controlled pair is now35.750s/72.750s, still above
the30s goal. Next work-only candidates reduce packet seeding where a local
batch already provides reuse, and add opt-in raw path-danger measurements.

## DLL81 local-batch admission result

`3297d2b3c` completed OFF251→255 with all699 actions and nonempty censuses
matching80. Interior252 took35.906s (PLAN10.799s),253 took72.094s (PLAN44.534s),
versus35.750s/72.750s for80. The slower turn improves0.656s in this pair while
the faster turn regresses0.156s; neither establishes a general compute win.

Turn253 scalar misses fall1,260,589→1,250,832 and evictions795,579→766,095.
Local-batch reuses increase28,187→46,564, while packet hits decrease197,339→
176,378. The same6000-entry pool peaks at623,960bytes. Summed search time
falls253ms, with244ms less yield time inside it; most of this particular search
timer difference is therefore waiting rather than demonstrated saved compute.
The intended pressure reduction is modestly visible.

Build66.343s, DLL39958D4B783B9BF127308DB8D5457277FF9A0B601A20A7ECE9E149111D274E21,
under `work/msvc-output/Release/20261001-061940`. Exact game/service closure was
05:28:32 UTC. Evidence: `perf-d81-local-batch-off-251-255/comparison-d80.json`,
phase reports, `cache-comparison-d80.json` and normal-exit proof. Target below30s
remains unmet. The next diagnostic-only candidate measures raw path danger
and clear-terrain checks under the existing opt-in tactical sampler.

## DLL82 path profiler replay

The default-off raw path profiler passed its production-bound checks and was
built as DLL82 (`6f4688d81`). Its OFF replay matched DLL81's699 ordered PLAN,
combat and capture records and both censuses. Interior turns252/253 took
35.891s/72.625s, versus35.906s/72.094s for81; this pair does not establish a
speed improvement or a statistical overhead bound.

The ON replay reached255 and closed normally with matching final censuses.
Its native archive was contiguous0–3, but optional path samples exhausted the
4096-row per-turn diagnostic budget at252/253. Explicit `TRUNCATED` and dropped
counts explain missing later-player records (PLAN303 rather than455,
COMBAT211 rather than243). Thus full native behavior equivalence is not
established by this ON run. Its legacy event windows were36.000s/72.485s;
phase and PLAN coverage is censored. These figures do not turn missing work
into zero or show a performance improvement. A bounded, sparser sampler and
repeat replay are required before interpreting the new samples broadly.

Evidence is in `work/test-runs/perf-d82-path-profile-{off,on}-251-255`, including
exact normal-exit manifests, comparisons and phase reports. Existing XML,
search limits, candidate order and gameplay calculations were unchanged.
The <30s goal remains unmet.

## DLL83 hash trial rejected

DLL83 (`a1a6b88a1`) matched all699 ordered records and both censuses against
82OFF. Exact normal game/service closure occurred at06:23:21UTC. Interior
252 took36.125s (PLAN10.886s),253 took72.953s (PLAN45.224s), compared with
35.891s/72.625s for82OFF. Despite synthetic long-key gains, this controlled
pair shows no turn-time benefit. The original forecast hash is restored;
fixtures and the measured experiment are retained for review. No numerical,
FIFO, capacity or search change was needed for the trial or restoration.

The next build reduces optional path sampling to one in128 queries and caps
its row attempts at128 per native-run turn. The cap's coverage bias is
explicit in records and the reader, including previous-turn denied counts.
110 adopted source and50 parser/anchor checks passed. This diagnostic bound
preserves path behavior and leaves the original gameplay/search limits intact.

## DLL84 sparse sampler validation

DLL84 (`24b0428c4`) restores the original forecast hash and bounds optional
path rows. OFF252/253 took36.047s/72.469s (PLAN10.821s/44.775s), matching82's
699 ordered records and both censuses. ON took35.953s/72.844s
(PLAN10.889s/45.327s), again matching all699 records and both censuses with the
intentional sampling difference allowed. No `TRUNCATED` row was present;
256 selected252/253 PATH rows parsed without errors. The row cap censors path
coverage deliberately, including early-completion bias and prior-turn denied
counts. It does not suppress the later-player semantic records seen missing
in82's original high-volume sample. These are individual replay pairs, not
an overhead confidence interval or a new speed gain.

The ON run was intended for an external EIP diagnostic as well, but a
pipe-boundary error in thread selection missed the253 window. Corrected
validation-only confirmed the exact process, native thread, module and SHA;
no Civ V thread was suspended, so there is no EIP hotspot result to claim.
Normal game/service closure occurred at06:46:32UTC. Evidence stays under
`work/test-runs/perf-d84-bounded-path-on-eip-251-255`.

## DLL85 callback safeguard and DLL86 immediate-validation replay

DLL85 (`c92e941cf`) passed186,114 production-bound capability and combat checks.
Its OFF replay matched84's699 ordered decisions and both censuses.252/253
were36.406s/74.016s (PLAN11.158s/46.413s), versus36.047s/72.469s for84.
All455 old/new hit and miss counter rows matched exactly: the additional
1.55s slow-turn cost did not correspond to lost cache reuse. Proof metrics
recorded1,188 scan attempts, flagsOR0, validation bypasses0, one suspension,
and291 searches with admitted hits. Attempts alone are not published proofs.

85ON also matched all699 records/censuses, at36.469s/74.469s. Its one automatic
turn253 EIP capture completed512 observations with32.6814ms total measured
pause and0.9576ms maximum; collectorCPU203.125ms. This was an instrumented
run, not a clean speed control. The flat sample is approximate location data,
not CPU shares. PDB folding aliases lookup functions, so city-labelled map
samples cannot be assigned exclusively to city containers. Compatibility
module observations are retained, but the user now requires DLL-focused work;
no registry or compatibility setting was changed.

DLL86 (`ef274591d`) removes two immediately duplicate validations, with11,547
strict production checks. It matched85's699 records/censuses.252/253 took
37.093s/74.297s (PLAN11.450s/46.698s); this pair establishes no speed gain.
The <30s target remains unmet. The next investigation prioritizes larger exact
state/evaluation and storage redesigns, with shadow numerical/assignment
oracles, fallback for unknown dependencies and substantial native benefit as
an integration requirement. No actor/search/cache limits are reduced.

## DLL87 cold checked-failure formatting

DLL87 (`2bdba7c05`) passed192,028 production-bound actual-source checks across
four assertion configurations with /GS retained. Seven fixture getter/map
bodies lose successful formatting-related cookie/EH frames; cold helpers and
formatters retain protection. Original checks and numeric bodies remain.
Failure stack location and plain-string argument temporary lifetimes have the
documented differences in `cold-checked-failure-formatting.md`.

The OFF251→255 replay matched all699 ordered PLAN/combat/capture records and
both nonempty world censuses against86. Interior252 took32.313s (PLAN9.665s),
253 took63.484s (PLAN39.010s), versus37.093s/74.297s (11.450s/46.698s). This
first pair improves wall time4.780s/10.813s, about13–15%; it is not a confidence
interval or a broad late-game guarantee. The <30s goal remains unmet. Roughly
24.5s still lies outside estimated PLAN on253, so the larger redesign remains
necessary. Gameplay/search/XML/configuration limits were unchanged.
All455 corresponding recorded six-pair cache hit/miss and callback-proof
counter rows also match; this does not cover every unrecorded cache operation.

Build88.937s under `work/msvc-output/Release/20261001-085618`;
DLL26535C3B9C4A36EAAF611035AAD57CC791BF224C12D0CB70B2AEC1D7E97BACCF,
PDBE7E5193E9BE4A63E67A0F17A38555B6F233347E12FF083C88603AD58AE4A0086.
Deployment backup `deployment-replaced-20261001-085918-b8332d31`. The outer
PowerShell command stalled draining launcher output before any mod/replay
dispatch; its exact wrapper alone was stopped after identity verification.
The existing game/service/guards remained intact, with no reconnect or retry.
The same service then restored the five benchmark mods and ran the replay.
No timing interval includes the launcher stall. Exact normal game/service
closure was08:09:01UTC, with no forced game termination.

Evidence: `work/test-runs/perf-d87-cold-format-off-251-255`, native
`Stacking-20261001T080600-728-p39624-r1`, `comparison-d86.json`, phase reports,
`wrapper-interruption.json` and `normal-exit.json`. Next are work-only exact
indexed-store and bounded incremental-kernel shadow prototypes; see
`performance-redesign-plan.md` for contracts and adoption thresholds.
