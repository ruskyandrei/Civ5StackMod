# Tactical hot-path sampling

This diagnostic measures selected calls inside a tactical planning search. It changes no scoring, damage calculation, candidate order, search budget, or AI decision. It is independent of the existing top-level turn/CPU phase timers.

## Enable and control it

Sampling defaults **off**, even with Summary or Verbose diagnostics enabled. The XML setting is in `(1) Community Patch/Database Changes/StackingConfig.xml`:

```xml
<Row Name="DiagnosticsTacticalSampling" Value="0" />
```

Set it to 1 for an XML default, or use the session-only Lua override:

```lua
Game.SetStackingDiagnosticsLevel(1)       -- Summary
Game.SetStackingTacticalSampling(true)    -- Returns the effective boolean
Game.GetStackingTacticalSampling()        -- Returns boolean
Game.SetStackingTacticalSampling(false)   -- Turn sampling off independently
```

The setter requires a Lua boolean; numbers/strings fail before changing state. Native counterparts are `CvStackingDiagnostics::SetTacticalSamplingEnabled(bool)` and `GetTacticalSamplingEnabled()`.

The override resets to XML on `CvStackingDiagnostics::Reset()` (including load/reset). Toggling sampling invalidates in-flight samples through its own epoch; it leaves the existing phase-timer generation, diagnostic level and gameplay state unchanged. Actual collection also requires Summary or Verbose, performance category bit16, the configured player filter and the selected `DiagnosticsPerformanceInterval` turn. Enabling the flag alone does not override those gates.

The replay harness supports `--tactical-sampling preserve|off|on`; `preserve` is the default. Use an off/on pair with the **same DLL, save, mods, settings and engine configuration**, then verify native semantic records and nonempty world snapshots match. Prefer interior observer turns: a return to human control adjacent to a timing boundary can affect that window. The flag is paused/read back before continuing and retained in the replay proof metadata. No UI button is added.

## Recorded evidence

One `PLAN_SAMPLE` row is emitted per eligible outer search, including an early return or exception unwind. The row uses a fixed part order:

| Part | Inclusive measured envelope |
| --- | --- |
| `combatMove` | Combat movement scorer |
| `turnEnd` | Combat turn-end scorer |
| `stackScore` | Stack preference scorer |
| `unitDanger` | Tactical unit-danger query, including membership/key/leaf work |
| `dangerKey` | Scalar stack-danger key construction and lookup |
| `dangerLeaf` | Scalar-miss/outcome-resolution; includes local outcome reuse, excludes cache admission |
| `preferred` | Preferred-assignment enumeration for one unit |
| `moveUpdate` | Lazy tactical move-plot update |
| `nextAssignments` | Branch generation and its nested enumeration/scoring |
| `citySimulation` | Simulated city attack |
| `unitSimulation` | Simulated unit attack |
| `damageMath` | Deterministic `DoDamageMath` call |
| `randomDamageMath` | Random-enabled `DoDamageMath` call (without skipping its original RNG work) |

`calls`, `selected`, `samples`, `ticks`, and `maxTicks` are CSV arrays in that order. Counts cover calls eligible for the outer owning session. Cadence version2 samples `nextAssignments` once per64 calls, `preferred` and `dangerLeaf` once per256, and the other ten parts once per4096. Each row records all13 `strides` and `phases`. The existing outer TLS serial rotates the deterministic target phase without a game RNG draw. Original version1 rows retain the4096 schedule and remain readable. Selected calls with failed clocks or an invalidated lifetime can have no completed sample. A method with calls but no completed sample has **unknown cost**, not zero cost.

`qpcFrequency` converts raw ticks to seconds. `qpcFrequencyCalls=1`, `qpcReads`, and `clockFailures` describe the clock work. `thread`, TLS-local `serial`, and `targetPlot` identify the owning search; serial alone is not globally unique. The fixed13-part counters fit384-byte buffers and cadence metadata fits96-byte buffers. The worst64-bit version2 formatting fixture produces a2184-byte row within the existing3072-byte message limit. Existing row/file limits still apply, so inspect truncation and archive quality.

These are **inclusive same-thread wall samples**, not CPU counters or exclusive attribution. Do not add parent/child estimates: movement scoring includes unit danger, key timing includes lookup, and branch generation includes scorer calls. A selected outer scope can include a nested search's wall time even though nested counters are suppressed. Systematic samples can alias work patterns; small sample counts are especially uncertain. Raw counters are authoritative; scaled duration estimates are approximate.

## Offline analysis

```text
python -B work/profile-plan-samples.py <native-folder> --run <exact-run-id> --turn 252 --map-width 88 --output <report.json>
```

`--turn`, `--player`, and `--map-width` are optional. The exact run and output are required. Map width is never guessed: without it, adjacent PLAN target associations remain unverified. Even a target-verified adjacent PLAN is a qualified candidate association because existing PLAN rows carry no shared serial/thread identity. The report exposes raw counts, missing/incomplete sample coverage and nonadditive estimates.

## Safety and validation

Counters live in fixed POD TLS storage. Foreign threads cannot consume an owning search's state; original TLS-address identity is checked before an imported object can change depth or samples, even with colliding serial/epoch values. Nested search sessions suppress their own counters. Reset and toggle epochs prevent stale emission. Inactive leaf probes use no clocks, settings reads, locks, logging, allocation or owner-thread API reads. The diagnostic gate and frequency calibration happen once per eligible outer plan.

`work/test-plan-sampled-timing.py` compiles the actual state/session/scope, category mapping, Reset/SetLevel hooks and strict Lua bodies with deterministic engine/clock/log services. It also reverse-strips only marked diagnostic additions and compares all 8 affected production files against pinned DLL58 source. Gameplay extraction fixtures omit those marked probes through `work/plan_sample_fixture.py`; they still compile their complete original math/scoring bodies. Run the sampler fixture independently so that exclusion does not conceal diagnostic defects.

That original fixture's uniform4096 and whole-source guards document the historical DLL60 proof. Current cadence validation uses `work/prepare-plan-sample-cadence.py` to regenerate the isolated frozen60 proposal, then `work/test-plan-sample-cadence.py` to require an exact normalized match to the current production Diagnostics files and compile their complete sampler/reset/toggle/Lua paths. Its89 checks cover64/256/4096 schedules, phase rotation, filters, off/thread/nested/lifetime safety and bounded formatting. `work/test-profile-plan-samples-cadence.py` checks the production parser's95 original/new-cadence cases, including the actual emitted native fixture row. Deliberate gameplay changes outside Diagnostics must not be hidden behind a whole-source reverse-strip claim.

`work/benchmark-plan-sampling-disabled.py` requires the sampler fixture's emitted scaffold first. Its sampler ctor/dtor compile in a separate translation unit from the probes. Bounded VC9 x86 measurements observed about 1.7–1.8ns extra per tiny inactive probe and 0.7–1.2ns per inactive probe around the actual damage-math body, with identical results. These synthetic measurements are not a native turn-time result. An off/on native replay remains required to assess enabled sampling/logging overhead and choose the next optimization from measured evidence.
