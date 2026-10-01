# Indexed owned tactical forecasts

The candidate replaces VC9 node-based tactical forecast storage with stable
indexed slots, bucket chains and FIFO handles. Keys and packet outputs are owned
by each slot. Up to32 combined integer words fit inline; larger payloads use an
exact heap allocation. This inline size is not a key limit or an AI search limit.

The two namespaces, full key equality and existing hash remain unchanged. Both
FIFO queues keep insertion order and the original queue-size victim selection.
Scalar/defender preflight still charges the input vector's capacity before its
duplicate check. Retained accounting uses copied-size charges, as the actual VC9
vector copy constructor does. Packet pending insertion, shared entry/payload
ceilings, duplicate behavior and bypass/eviction counters retain their old rules.

Slots are stable during a search. A packet's unqueued pending slot cannot be
selected by FIFO eviction. Scalar, pointer and packet-member lookup helpers copy
their result before caller context validation can clear storage. Scene changes,
suspension, nesting and foreign ownership retain the original guards and clears.

The outer constructor selects one backend for its entire lifetime. If initial
indexed allocation throws `std::bad_alloc`, partial arrays are released and the
original storage helpers serve the search. No backend switches during a search.
The outer destructor releases indexed arrays and original containers. Unsupported
contexts and nested searches retain the original behavior.

At the normal6000-entry ceiling,6001 slots of168 bytes plus16384 bucket heads
reserve1,073,704 bytes before overflow. The extra slot permits original packet
pending admission. Actual physical memory also includes overflow, pending
allocations, fallback container buffers and allocator overhead. The unchanged
624,000-byte logical payload budget is not a physical memory estimate. Existing
estimated-memory diagnostics now account for the reserved representation;
`PLAN_PERF` records `forecastBackend` and `forecastEstimatedBytes` in the existing
row, without adding rows. The formatter has42 conversions/arguments and a tested
1199-byte maximum against its2048-byte buffer.

The whole staged/live source-bound oracle passed723,127 checks with zero failures.
It compares actual original and replacement admission, eviction, packet, Scope
and backend lookup helpers. Cases include tiny budgets, full collisions, input
capacity greater than size, duplicate/member order, zero scalars, null defenders,
source lifetime, resets, nested/foreign/scene contexts and constructor allocation
failure. Deterministic context/unit services are explicit; these tests do not
establish native speed or every engine path. FIFO failure injection exercises a
logical boundary, not identical real allocation-failure probabilities.

An optimized VC9 trace shows four owned key copies for scalar admission and
three key/output copies for packet admission. An18-word scalar uses seven
allocations/380 requested bytes in the original versus zero in the indexed
store; a64-word scalar uses seven/1116 versus one/256; a51-word/five-member
packet uses nine/824 versus one/244. These exclude query preparation and CRT
bookkeeping. Initial synthetic eviction-heavy traces run about4x faster. Their
cleanup measurement assertion was corrected after finding that empty original
containers retain newly allocated default buffers; the functional oracle passes.
The subsequent quiet complete replay preserves699 ordered events, both world
censuses and all455 recorded cache/proof counter rows. Interior252/253 take
31.828s/57.531s versus32.313s/63.484s for87; heavy-turn planning falls
39.010s→33.023s. This first pair supports a useful9.4% heavy-turn reduction,
with a much smaller light-turn gain. It does not establish a general guarantee
or meet the below30s objective.

The first native trial was stopped at254 by the sustained CPU temperature guard
while the user also had Blender work running. Its retained252/253 windows and
606-event prefix match original behavior, with unchanged recorded hit/miss
counters. There is no final census or verified normal stop, so native adoption
were unconfirmed in that interrupted run. The later quiet repeat supplies the
bounded evidence described above; see `performance-progress-20260930.md`.

Reproduction uses `work/prepare-indexed-forecast-store.py`,
`work/apply-indexed-forecast-store.py` and `work/test-indexed-forecast-store.py`.
Run the fixture with `--stage-production --no-benchmark` before application and
`--production --no-benchmark` afterward. Complete source binding and reverse
restoration qualify the change; generated output and the first timing evidence
remain in `work/indexed-forecast-store-staged`. The control is DLL86's unchanged
tactical source, also present in DLL87. Normal native comparisons use DLL87's
measured checked-accessor improvement as their baseline.
