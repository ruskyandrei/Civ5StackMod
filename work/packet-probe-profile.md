# Offline packet probe reader

`profile-packet-probes.py` reads one exact native session through the canonical
`profile-turn-phases.py` segment loader. Copied shorter segments are ignored;
conflicting copies, gaps, incomplete tails and malformed records are reported.
Different native runs are never combined. The only write is the requested JSON.

```powershell
python -B work/profile-packet-probes.py <native-folder> --run <exact-run-id> --turn 253 --map-width 88 --output <report.json>
```

`--turn`, `--player` and `--map-width` are optional. Map width must come from a
verified map; the reader never infers it. `--run` and `--output` are required.
Exit 2 means invalid diagnostic rows were included in the report. An unknown
run fails explicitly. A valid run with no probe records succeeds but reports
that overlap is **unknown**, not zero.

PROBE and SAMPLE rows join only on exact turn, player, plot, thread and serial.
Duplicate identities are rejected. Legacy PLAN/PERF rows lack thread/serial;
only the immediately preceding PLAN/PERF and its matching preceding partner
are considered. Even when target coordinates match, this remains an adjacent
candidate association. It never borrows an earlier target from another search.

The report includes selected-query/work-class counts, fresh cross-member first
visits, local-batch reuse, raw calls and build attempts, field versus friendly
city group admissions, fixed metadata/payload bounds, FIFO evictions and clears,
unmatched SAMPLE/PROBE records, row drops and archive coverage. Current FIFO
occupancy is unknown after a clear because cumulative admissions alone cannot
recover it. Peaks are maxima across plans, not sums. Query/repeat counts are
not split between field and city because the native emitter does not do so.

Fractions describe only retained selected observations. No counts are
multiplied by the sampling stride. No saved leaves, CPU shares or seconds are
predicted. A `freshQueries` observation may attempt a batch and fall back to raw
danger; attempts may fail. Existing local-batch reuse is already optimized.
Logical output-storage proxy bytes are not actual vector capacity or future
result-cache memory. Bounds, row drops, finite metadata FIFO, scene clears and
sampling censor overlap; especially valuable large groups can be missing.

Tracked prerequisites: `profile-packet-probes.py`, `profile-plan-samples.py` and
`profile-turn-phases.py`. Validation is Python only:

```powershell
python -B work/test-packet-probe-profile.py
```

Its synthetic tests cover schema/count equations, native byte bounds, exact
and mismatched identities, legacy candidate qualifications, filters, absence,
duplicate/conflicting segments, row drops, CLI writes and invalid-row exit 2.
Results are written to `work/packet-probe-profile-fixture-result.json`.
