# Performance work paused — 1 October 2026

The user requested a break after repeated dense-turn results near60 seconds.
The active <30-second goal is paused and unmet. No remaining DLL candidate has
demonstrated a further10–20-second reduction. Do not resume tests automatically.

## Retained baseline

Production gamecore source is restored exactly to commit `4cd0a4cfe` (DLL96).
This retains the earlier checked-getter formatting improvements, indexed forecast
storage, bounded diagnostics, parent roster preparation and packet-miss outlining.
No AI search budgets, cache budgets, combat formulas or gameplay XML are reduced.

Same saved game, standard view, Summary diagnostics, profiler off:

| Build | Turn252 | Dense turn253 | Planning on253 |
|---|---:|---:|---:|
|96, retained|31.266s|57.359s|32.827s|
|97, resident certificates|32.469s|59.156s|34.595s|
|99, certificates without duplicate key vectors|32.391s|60.250s|34.484s|

These are individual controlled replay measurements, not statistically established
general turn times. All699 retained decisions/combat/capture events, both nonempty
world censuses and34 legacy cache fields match across these runs. Builds97/99
also have identical five new counters and physical forecast estimates. Both
resident variants are removed; their source, oracles and evidence remain saved.

Installed96 DLL SHA256:
`4CBBEB119EBE22CFA8561E09EF018BA46FCF70213E184CA6B0EC83074C2B1B2F`.
PDB SHA256:
`92CA92F421D40E73B71270EF03374D216C12B5E68C218D676251F0D7BD743F5A`.
Archived build: `work/msvc-output/Release/20261001-121718`.
Source Tactical normalized SHA256:
`b0975783336b020a92d856d1da46e28907ed5e176277316b188f28da7afd6e0a`.
Restoration verified2368 installed files at12:22:26UTC; replacement backup is
`work/backups/deployment-replaced-20261001-132154-ca6bc770`.
Graphics and saves are unchanged. The ordinary deployment resets mod selection;
reselect the five campaign mods when returning to play, or use the existing
fresh-main-menu benchmark helper during a later authorized test.

## What could still be substantial

The strongest remaining architectural direction is preparing an immutable battle
snapshot and reusing exact destination/stack numerical outcomes across virtual
children. This could eliminate repeated work rather than merely speed each lookup.
It is not implemented or supported by a measured savings estimate. Live object
lifetimes, source ordering, callbacks, dirty refresh, city garrison selection,
projected wounds, collateral ties, nested queries and allocation failure must be
proved before relying on it. A scene epoch alone does not cover every native setter.

The dense96 planning envelope is about33 seconds; most of the remaining24–25
seconds is outside planning, including roughly8 seconds between engine update
entries. That gap records little same-thread CPU, but cannot be safely bypassed
without understanding engine update hooks, timers, network/pause behavior and
turn slices. Existing phase envelopes overlap; they must not be summed twice.

One separated97 instruction sample identifies strength-key/hash/context and folded
pointer-table lookups, including a portion of the heavy search. It is a partial
flat wall-residency sample, not a CPU-share or whole-turn saving estimate.
The target-distance floods measured only~0.2 seconds on the heavy turn and are
not a promising large-gain redesign in this evidence.

## Unfinished smaller experiment

Actual VC9 assembly shows an88-byte returned-key copy and184-byte local frame in
four strength-cache wrappers. A private output-reference builder is staged only,
uncompiled and unapplied. It needs a source-bound numerical/key/exception oracle,
candidate assembly and native timing. Its dependency binding currently pins99
Tactical source and must explicitly rebase to the restored96 baseline.
See `work/strength-key-output-reference-pending.md`. No speedup is claimed.

## Evidence and shutdown

Final99 replay completed normally at12:13:09UTC (13:13 UK time): game3600 and
service656 exited, session file removed, CPU and memory guards disarmed on
completion. No game/controller/compiler is retained. No save was overwritten.
Detailed results: `docs/performance-progress-20260930.md` and the corresponding
`work/test-runs/perf-d96-*`, `perf-d97-*`, `perf-d99-*` folders.
Runtime evidence and the overnight journal are local; tracked documents and
reproduction tools preserve the development checkpoint. No push is requested.
