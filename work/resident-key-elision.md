# Resident even-key preparation shortcut (work-only)

This candidate replaces repeated preparation and lookup of an **already-resident
original scalar key**. It does not create another result cache, recompute a fresh
danger value, skip a policy callback, change a search limit, or preseed unqueried
members. Native performance has not been measured.

The first emitted stage is pinned to DLL93 `e38b19798`. The composed stage is
pinned to `4cd0a4cfe`, including the target-distance timer and the unchanged
`ResolveStackDangerForecastMiss` outline. Both reverse mechanically to their
entire control Tactical file. The composed candidate is
`b41f2160f2d604e8782bd1554977b1788de1e4c8c890443a4e916cf5ce4d6a19`.

## Admission and equality proof

Only `GetUnitDangerForPlot` arrivals inside the original parent preparation view
can register a request. The request names the actual output roster and friendly
wound objects, queried unit, destination, arrival damage, and parent/explicit
EFD-only child. The existing preparation witness proves the same ordered base
roster and first-match friendly wounds. The arrival overwrite/dedup logic stays
unchanged. Generic scalar, full-stack, solo/protector, private, nested and foreign
queries cannot inherit this request. Active tactical sampling forces the
original full-key path so diagnostic key visits remain comparable.

A certificate is captured only during an existing full-key indexed scalar hit;
there is no additional table lookup. It stores that original key and a residence
token, never its result. Generic/full/solo hits do not capture a token. One
certificate is kept per already-touched parent preparation cell.

Original even danger keys have the following exact words:

1. queried unit ID, destination index, queried friendly wounds, city protection;
2. member count and each exact `(unit ID, friendly wounds)` pair, in original
   canonical/noncanonical order;
3. projected enemy pair count and each original numerical pair.

The first four words and canonical setting are read fresh at their original
pre-projection seam. The parent view plus exact unit/arrival tuple certifies the
previous member prefix. The **original** `AppendStackDamageProjected` still runs
once, including its source refresh, negative city IDs, aliases, zero treatment,
and NULL-source full-ledger fallback. The original post-key Context/revision/
scene check runs before any residence-token read. Exact suffix equality and the
still-valid token then imply that the omitted full-key lookup would find the
same immutable resident scalar.

This is equality with the original cache lookup, not a claim that this key
captures every dependency of a freshly computed leaf. Source hazards/order or
live fields omitted by the original scalar key are not given new semantics.
No new source descriptor or refresh callback is introduced.

If suffix equality/residency fails, the copied prefix is appended word-by-word
and rotated before the suffix. The original complete key, vector growth sequence
and admission capacity are restored without a second refresh or leaf simulation.
Original packet/scalar stores, larger-pool FIFO decisions, entry limits, payload
budget, candidate order and search policy remain. Successful shortcuts increment
the existing scalar-hit counter because they return the same live resident hit.

## Lifetime, exceptions and memory

Each indexed slot gains a uint32 published-insertion generation. It is zero
until QueuePush and after QueuePop/erase; pending packets cannot certify. Clear,
Release and reinitialization advance a table lifetime. Residence reads check
identity, enabled state, lifetime, bounds and generation before slot access and
copy only the scalar integer. Generation/lifetime exhaustion disables
certification without adding forecast clears or changing admission/results.
Tokens cannot survive destruction/reconstruction of the owning C++ table object;
production `gIndexed` is a process-lifetime static object.

Private/nested/foreign calls retain the original buffers and checks. A source
refresh/invalidation cannot destroy the fixed copied fallback prefix. Optional
certificate copy failure or post-copy invalidation drops the certificate and
returns the existing hit once. It does not call the leaf again. An exceptional
or invalidation path reconciles optional measured capacities; normal calls do
not scan all cells.

The stock CRT vector allocator is part of the same callback-free native contract
as the existing shared parent roster copies. A normal `bad_alloc` is supported.
A synthetic allocator hook that destroys the owner scope and lets a new owner
reclaim its static cell *during vector assignment* is outside this contract;
the fixture does not claim arbitrary allocator-driven ownership reentry is safe.
Original engine callbacks occur at the retained projection/leaf seams, rather
than inside that metadata copy. Post-copy checks still reject ordinary scene,
view and slot-lifetime drift without recomputing the already-returnable scalar.

Actual VC9/x86 representation changes:

- Slot: 168 to 172 bytes, or +24,004 bytes for 6,001 allocated slots.
- IndexedStore object: +12 bytes.
- Parent preparation cell: +44 bytes, or +11,220 fixed bytes for 255 cells.
- A single fixed 128-word prefix scratch plus small ownership fields; requests
  are lexical stack objects.

Certificate vector capacity is charged to the **existing parent optional
payload budget** alongside roster/damage vectors. New base construction discards
certificate payload first if needed, then uses the original base-budget fallback.
All optional payload is released at outer search teardown. These figures measure
requested representation storage, not CRT overhead, peak process memory or RSS.
The 128-word prefix limit bounds only this optional shortcut; larger keys use
the original evaluator.

## Evidence and counters

The composed actual-source oracle currently passes **64,347 checks / 0**.
It compiles the complete strong Context/provider and strength module, indexed
backend, scalar/packet/key code, actual CoW/first-match/GetNextPosition/parent
preparation/UnitDanger bodies and actual field/city/air/collateral math.
Engine/unit combat services and tactical plot/stat structures are deterministic
fixtures. Native engine integration and speed still require the parent-run replay.

The trace returns 6,852 resident hits, avoids 6,852 full-key table lookups and
7,616 candidate-prefix serializations. The latter also includes suffix-mismatch
fallbacks that reconstruct the proven prefix. Results, raw leaf/callback counts,
retained keys, FIFO order, capacity, payload and original logical cache counters
match. Optional payload peaked at 408 bytes in this trace. No synthetic work
count is converted to seconds or scaled to a native turn.

A targeted warm-certificate case dirties the actual projected-source getter
after its original loan/prefix seam: the final Context rejects the token, returns
one leaf result and admits nothing. Strict adopted-source emission binds14 full
files and is byte-identical to the compiled passing fixture.

Targeted fixture supplements add genuine complete-hash collision keys (using
the original recurrence), real constructor bad_alloc and terminal lifetime wrap.
They pass in the final 64,347-check oracle; the production candidate is unchanged.
The independent residence-API oracle previously passed 22,559 checks / 0,
including pending packets, duplicate insertion, recycled slots, Clear/Release/
Init, both wrap boundaries and the explicit C++ object-lifetime limitation.

Five counters are added to the existing single PLAN_PERF row:

- `residentHits`: successfully validated resident scalar shortcuts.
- `residentCaptures`: optional certificates published from existing full-key hits.
- `residentRejects`: eligible cold/mismatched/unresident preparations or prepared
  suffix fallback; excludes unsupported calls that never enter the shortcut.
- `prepBuildAttempts`: original parent base-roster build attempts.
- `prepReuseAttempts`: warm parent cell copy attempts, including later copy failure.

The format has 47 conversions/arguments and a conservative 1,336-byte maximum,
below the requested 2,048-byte bound. Existing scalar/packet/strength counters
remain actual operations. Physical forecast memory estimates intentionally grow.

## Reproduce

No generated scaffold is required. The stage regenerates the pinned residence
class via `resident-scalar-handles-stage.py --pinned`. This mode only emits the
immutable historical component; the default component mode still requires its
whole live DLL91 control. Numerical services are regenerated from tracked
`test-immediate-forecast-borrow.py`, `test-packet-probe.py` and
`packet-probe-fixture-services.h`, bound to the selected control's full source.

```text
python -B work/stage-resident-key-elision.py --control 4cd0a4cfe --output work/resident-key-elision-outline-staged
python -B work/test-resident-key-elision.py --control 4cd0a4cfe --emit-only
python -B work/test-resident-key-elision.py --control 4cd0a4cfe
```

After applying the reviewed candidate, add `--production` to the last command.
It requires the entire live Tactical file to equal the emitted candidate and
all 13 other source/header dependencies to equal the pinned control; otherwise
it fails before compiling. It never substitutes current production as the old
oracle. `--production --emit-only` provides a cheap strict binding check.

New reproducibility files are `stage-resident-key-elision.py`,
`resident-key-elision-fragment.cpp`, `resident-key-elision-helpers.cpp`,
`resident-scalar-handles-stage.py`, `test-resident-key-elision.py` and this file.
The existing three tracked numerical dependencies above remain prerequisites.
All manifests, emitted full sources, compile output and result evidence are
written under `work/resident-key-elision[-outline]-staged` and the corresponding
`-regression` directory.
