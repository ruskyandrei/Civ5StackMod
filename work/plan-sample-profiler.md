The offline PLAN sampler profiler is `work/profile-plan-samples.py`. It reads
complete rows from one exact native session and writes a JSON report. It never
connects to Civ V, changes the game, or combines different native sessions.

```powershell
python -B work/profile-plan-samples.py <native-folder> `
  --run <exact-native-run> --turn 252 --map-width 88 `
  --output <run-folder>/plan-samples252.json
```

`--turn`, `--player`, and `--map-width` are optional. The map width must come
from a verified map/source snapshot. It is not inferred from a candidate PLAN.
The directory, exact run, and output path are required. Exit status 2 means one
or more complete sampler rows were rejected as invalid; valid rows still appear
in the report. An archive with no sampler rows produces an explicit empty
report, since sampling can be disabled or filtered by interval/player.

The parser uses the canonical segment loader from `profile-turn-phases.py`.
Copies and rolling aliases of a segment are counted once. Short copies must be
prefixes of the retained complete copy. Conflicts, missing segments, incomplete
tails, and clock reversals remain visible in archive quality. Incomplete native
lines are skipped. Explicit `[message truncated]` records are rejected even if
their numeric fields happen to remain parseable.

The fixed 13 parts are combatMove, turnEnd, stackScore, unitDanger, dangerKey,
dangerLeaf, preferred, moveUpdate, nextAssignments, citySimulation,
unitSimulation, damageMath, and randomDamageMath. The five arrays must have
exactly this length/order. The parser checks unsigned integer bounds, the 4096
selection schedule, samples <= selected <= calls, QPC frequency/read accounting,
and tick totals. Duplicate emitted sample identities are excluded rather than
silently counted twice. Identical serial numbers on different threads are valid.

Each part has raw call/selection/sample counts, sample coverage, sampled wall
milliseconds, maximum sample wall milliseconds, and an approximate extrapolation
`sampled_wall_ms * calls / completed_samples`. The report exposes unknown cost
when a called part has no completed sample. Group totals preserve the known-plan
estimate separately from a full total; one uncovered called plan makes the full
total unknown. Frequencies are converted per row before aggregation.

All measurements are inclusive same-thread wall QPC spans. They are not CPU
measurements. Parent and child parts overlap and must not be summed. Selection
is periodic rather than random, so it may alias periodic work; estimates with
fewer than 30 completed samples have an explicit caution. Nested searches or
callbacks may contribute wall time to a selected outer scope while their own
counters are suppressed. `dangerLeaf` measures scalar-miss/outcome resolution,
including reuse of a resolved outcome, and excludes cache admission; it is not
a pure leaf-computation measure.

The native sampler row has targetPlot/thread/serial, while existing PLAN rows
have x:y coordinates and no thread/serial. Only an immediately preceding
same-turn, same-player PLAN or PLAN_PERF is offered as a candidate. Without a
verified supplied map width or explicit PLAN targetPlot, its target is
unverified. With verified target coordinates but missing PLAN identity fields,
it remains a qualified candidate; the report never claims exact identity from
adjacency alone. Future rows with matching explicit target/thread/serial can be
marked as identity and target verified.

Run the lightweight synthetic regression with:

```powershell
python -B work/test-profile-plan-samples.py
```

The initial regression passes 66 checks, including invalid arrays/frequency,
clock accounting, truncation, incomplete scopes, zero samples, overlapping
parts, frequency conversion, duplicate segments and identities, qualified
target matching, and turn/player filters. It writes
`work/plan-sample-profile-fixture-result.json` and does not compile or launch
anything.
