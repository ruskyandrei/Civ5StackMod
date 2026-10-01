# Allocation-free resident slot-key candidate

Work-only replacement of DLL97's certificate key vectors. It targets the
observed metadata tax rather than adding another cache or reducing search work.
DLL97 was behavior-exact but slower than DLL96: turn25359.156s versus57.359s (root
native report).
It recorded7,224,875 resident hits but8,665,323 certificate captures. Those
captures copied an entire duplicate key, and a qualifying full-key hit could
repeat parent-cell acquisition three times. These counts motivate this candidate;
they do not prove a native saving.

The candidate is pinned to `fbde19541` (DLL97), source
`b41f2160f2d604e8782bd1554977b1788de1e4c8c890443a4e916cf5ce4d6a19`.
Its staged source is
`b14842c07914648ec02f5fd71c71ece175f82978cc4329eb79970033b03e8c51`.

## What changes

The existing indexed slot owns its immutable exact key until its generation or
lifetime is invalidated. The certificate therefore needs only a handle plus its
unit/arrival-damage/canonical tuple. It no longer owns a vector. Capturing after
the existing exact Find is a POD assignment with no allocation, key copy,
post-copy epoch read, capacity charge or exceptional reconciliation scan.

One original parent-cell acquisition initializes a lexical proof in the existing
owned query scratch. Prepare, capture eligibility and publication reuse that
proof rather than repeating binary search/SharesVirtualStackInputs. The proof
still rejects a changed request/view, disabled/nested view, released storage or
revision/scene drift. Private and foreign queries do not touch the owner's scratch.

Two **owner-only** indexed APIs provide the native key data:

- `TryCopyScalarPrefix` validates table, lifetime, generation, scalar shape,
  current fixed words and the already-warmed full-key capacity. It copies only
  the bounded original prefix into the existing128-word scratch.
- `TryMatchScalarSuffix` validates residency again after the original projected
  source reader and final Context, compares the exact fresh suffix and copies
  only the scalar result.

Neither API independently validates thread/Context. Those are supplied by the
actual owned query, lexical proof and retained final original Context. No Slot,
Data pointer, vector reference or key view crosses `AppendStackDamageProjected`.
Every failure preserves outputs. Existing insertion generations/lifetimes,
pending-node restrictions, eviction/wrap rules and C++ object-lifetime contract
remain unchanged.

Fallback still appends each copied prefix word and rotates it before the suffix,
preserving complete keys and original vector-growth/admission capacity. The
entire cached wrapper, UnitDanger, projection, scalar/packet stores and outlined
miss helper are byte-identical to97. Original callback graph, scalar hits/misses,
FIFO/capacities/budgets, policy and search order remain. The parent base-roster
budget no longer includes duplicated certificate vectors; capture/reject/hit and
preparation counters may consequently differ. Legacy result-cache operations
remain actual operations, not simulated counter increments.

## Evidence and limits

Actual-source VC9/x86 oracle: **64,358 checks / 0**. Complete strong Context,
provider, strength module, indexed/scalar/packet/key code, CoW/first-match,
parent/GetNext/UnitDanger and field/city/air/collateral math are extracted from
pinned source. Native combat/world services and tactical plot/stat structures
are deterministic fixtures.

The synthetic trace retains exact original logical cache counters, stored keys,
FIFO/payload/capacity, raw leaf graph and results. Parent-cell acquisition calls
fall12,657→9,173 and certificate key copies1,152→0. New capture succeeds with an
allocator failure still armed, showing that no allocation seam remains. This
is work-count evidence, not an estimate of native seconds.

Tests retain genuine full-hash collisions, constructor bad_alloc/legacy backend,
recycled/evicted slots, Clear, generation/lifetime exhaustion, foreign/nested and
unsupported capability paths, city/order/duplicate/NULL projection cases and a
source refresh after a warm prefix but before final Context. Direct API cases
cover preserved outputs, capacity denial, fixed-word mismatch, suffix mismatch
and post-copy Clear rejection before a recycled/freed slot read.

The parent preparation cell is16 bytes smaller under VC9/x86, saving4,080 fixed
bytes over255 cells plus all formerly retained certificate vector capacity.
IndexedStore/Slot requested sizes remain unchanged from97. No peak-memory/CRT/
RSS claim is made. Native replay and performance remain unmeasured.

## Reproduce/adopt

```text
python -B work/stage-resident-slot-key.py
python -B work/test-resident-slot-key.py --emit-only
python -B work/test-resident-slot-key.py
python -B work/apply-resident-slot-key.py
```

The last command is a dry run: it validates the passing compiled fixture hash,
whole control/candidate hashes and13 unchanged source/header dependencies.
`--apply` applies only that frozen Tactical candidate, preserving the original
BOM/newlines. Root owns adoption/build/game testing.

After adoption:

```text
python -B work/test-resident-slot-key.py --production --emit-only
```

This checks14 entire live source files before emitting. Verify its fixture hash
matches the compiled passing result; it does not substitute current production
as the old oracle. Evidence is in `work/resident-slot-key-regression/result.json`
and `proof.json`; compiled fixture SHA is
`f1a0be9e3fb7b010d35893deca6cb96833df4a8f37a1b91bf03998b932c86b5f`.
The independent source review is
`work/resident-slot-key-independent-review-97.md`.

New reproducibility files: `stage-resident-slot-key.py`, `resident-slot-key-api.cpp`,
`resident-slot-key-helpers.cpp`, `test-resident-slot-key.py`,
`apply-resident-slot-key.py`, and this document. Existing tracked numerical
extraction/service prerequisites remain unchanged.
