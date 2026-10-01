# Comparing native forecast-cache work

`compare-plan-cache-counters.py` compares actual retained `PLAN_PERF` counters
from two exact native runs. It uses `profile-turn-phases.py` for segment
selection, prefix-copy deduplication and clock/run metadata. It writes only the
requested JSON and refuses replacing an input log, including an alias.

```powershell
python -B work/compare-plan-cache-counters.py <baseline-native-folder> <candidate-native-folder> --baseline-run <exact-baseline-run> --candidate-run <exact-candidate-run> --turn 252 --turn 253 --map-width 88 --output <comparison.json>
```

`--turn` is repeatable; omitting it retains every recorded turn. The optional
map width must be verified. Without it, locations are compared by target
coordinates and player, with the plot identity explicitly unverified. Exact
run IDs are mandatory, and an absent run refuses rather than producing an
empty comparison. The helper has no game calls or gameplay/source writes.

Each turn and player/target group reports actual danger hits, misses and
evictions; outcome builds, reuses and bypasses; and shared packet hits,
builds and bypasses. Missing historical packet counters are **unknown**, not
zero. Every metric carries its known and missing row counts. A complete total
or comparison delta is null unless all retained valid rows supply the metric.
Present zero values remain known zeros.

Search counters are summed because they reset per search. Retained-entry and
payload snapshots and per-search retained peaks are summarized with maxima,
not sums. Search phase milliseconds are retained separately and overlap the
existing PLAN timer; these are not total-turn measurements. Diagnostic drops,
invalid rows and partial/conflicting archives are reported beside the counts.
Matching player/plot aggregates do not prove individual search inputs or
search counts are identical.

`outcomeBuilds` changes instrumentation scope across the version boundary:
before79 it counts local-batch builds, while79 also increments it for direct
global packet builds. `packetBuilds` is the subset of direct packet builds
without a supplying local batch. These overlapping fields must not be added,
and their raw comparison delta is not a local-only build reduction or a count
of avoided simulations. `outcomeReuses` retains the existing local-batch reuse
field; `packetHits` is the separate shared-result lookup field.

No stride scaling, estimated saved simulations or predicted time is produced.
Judge packet reuse with scalar work, evictions, retained capacity, native
turn time and the separate action/census equality comparison together.

Validation uses only a small Python fixture:

```powershell
python -B work/test-plan-cache-counters.py
```

The checked native78 preflight retained259 valid rows across turns252 and253,
with no invalid rows or archive warnings. Its packet metrics are all unknown,
as expected for the earlier emitter. `work/plan-cache-counter-baseline78.json`
is a self-comparison to validate baseline reading, not a packet performance
comparison. Generated reports and test results remain ignored artifacts.
