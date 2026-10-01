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

## DLL60 native sampling control and next exact optimization

The quiet Standard-map replay pair completed251→255 with the same manual
source, original dedicated-thread configuration and full logging. Sampling
off/on retained identical699 planning/combat/capture records and all world
censuses. Interior turn252 took39.031/39.099s and253 took84.422/84.782s;
PLAN totals were13.275/13.316s and56.073/56.252s. Both games quit normally.
These are one paired observation, not a statistical overhead bound.

The samples identify repeated stack-danger defender comparisons as a substantial
remaining search envelope. Inclusive sample estimates overlap and sparse parent
samples can overestimate whole plans; they must not be added as CPU shares.
The prepared optimization reuses the existing exact selector memo for owned
danger previews, retaining the original final quick/next-turn strike and injury
sequence. It conservatively bypasses scripted movement events, mixed owners and
ambiguous identities. No scoring, mechanics, search limits or storage budgets
change. Relevant actual-source regressions passed1,149,421 checks. Native timing
and identical-save action comparison are the next validation step.
