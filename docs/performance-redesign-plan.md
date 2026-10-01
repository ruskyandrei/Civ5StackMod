# Larger DLL performance redesigns

The current objective is below 30 seconds per late-game turn on a standard game,
then below 20 seconds if practical. It is not achieved. The quiet DLL88
dense-turn253 replay takes57.5 seconds, of which about33 seconds are inside
tactical planning, down from DLL86's74/47 seconds. About24.5 seconds remains
outside estimated planning. Changes outside the planner also matter.

These timings describe one saved campaign, not all late-game performance. The
source investigations use DLL86 as a pinned control. DLL87's first matched
test of legacy checked-accessor overhead improves32.313s/63.484s versus
37.093s/74.297s for interior252/253, preserving all retained events/censuses.
The goal remains unmet. Game settings, AI/search limits and gameplay data remain
unchanged.

## 1. Incremental evaluation of hypothetical battle states

Today each child position reevaluates all available actors and their reachable
candidates. A child often changes only one actor, its source and destination,
and a few projected wounds. Rebuilding the rest can be unnecessary work.

The proposed evaluator separates immutable battle data from projected state.
It reuses a pure destination-danger/stack-scoring kernel only when its exact
dependencies remain equal. Source-protector penalties stay separate: moving a
protector can change departure penalties without changing many destinations.
Policy calls, candidate generation, stable sorting, arithmetic and assignment
materialization retain their original order.

DLL91's bounded, opt-in shadow measurement completed with the original kernels
driving play. All699 retained semantic records and both world censuses match its
OFF control. Across retained complete observations,91.7% of unit-danger and
82.8% of stack-score evaluations repeat recorded inputs/results, with no observed
mismatch. Most stack observations take a cheap zero-key path; these percentages
are not expensive-work fractions or predicted speed gains. On253, per-row count
bounds establish repeated footprints for84.8–94.7% of nonzero-key unit frames
and64.5–99.7% of nonzero-key stack frames. Misses and elapsed time are not
stratified by repeat class. There is no stride extrapolation.

The first implementation shares a sparse lexical parent view of ordered unit
rosters and first-match health data across candidate evaluations, with exact
enemy-damage overlays for preview children. It keeps existing key serialization
and original numerical evaluation initially. Later certified reuse must account
for arrival versus queried actor, full versus solo rosters, cache scratch loans,
capacity admission, source refresh and table/slot lifetimes. Observer identity
tokens do not certify these dependencies. Directed stale-reuse tests and an
actual-source oracle precede activating any such path.

Projected enemy wounds can affect distant destinations. Interceptors and raw
unit-ID aliases, city HP/protection, garrison order, live HP versus projected HP,
visibility changes and callback suspension all need explicit handling. Unknown
or changed contexts use the original evaluator. No candidate is dropped.

If conservative reuse is substantial, replace repeated copy-on-write detaches
with compact child delta records over the immutable snapshot. Preserve ordered
memberships, first-match lookups, damage-ledger aliases and recycled-position
lifetimes. Measure copied bytes and allocation work before this deeper rewrite.

A later option is parallel evaluation of independent pure candidate kernels.
Workers would consume immutable plain data and produce isolated results; the
owning thread would materialize them in the original enumeration and tie order.
Live engine getters, callbacks, policy calls, assignment storage and existing
global preview caches must stay on their original thread. Simply dispatching
today's scorer to several threads is unsafe. Measure the eligible fraction,
batching overhead and extra memory before building this extension.

## 2. Indexed forecast storage

The measured turn253 has about21.1 million danger-cache hits,1.25 million misses
and766,000 evictions. Its pool reaches6,000 entries and623,960 logical payload
bytes. The current VC9 hash table allocates linked nodes and copies owned vector
keys; eviction hashes and searches for a key already identified by the FIFO.

A prototype uses contiguous stable slots, hash-chain/FIFO integer handles,
inline owned words and exact overflow storage. It can remove node allocations,
intermediate key copies and the eviction lookup. Long keys retain an exact
fallback; inline capacity is not a key-size restriction.

The first work-only actual-source storage oracle passed690,287 checks. It
preserves full key equality,
danger/defender namespaces, source-capacity preflight versus copied-size charges,
packet pending admission, duplicate behavior and both FIFO victim policies.
Hashes remain bucket selectors only. Allocation failure and scene invalidation
must not leave stale references or extra evictions.

An optimized VC9 allocation trace records four owned key copies for a scalar
admission and three key/output copies for a packet. An18-word scalar drops from
seven allocations to none in the indexed prototype; a64-word scalar drops from
seven to one, and a51-word/five-member packet from nine to one. Initial synthetic
eviction-heavy traces are about4x faster. The complete quiet native88 replay
improves the heavy turn63.484→57.531 seconds, about9.4%, and planning
39.010→33.023 seconds; the lighter turn improves32.313→31.828 seconds.
All699 retained semantic records, both censuses and455 recorded cache-counter
rows match87. These individual measurements do not establish a general late-game
guarantee. Query preparation and CRT bookkeeping are outside the allocation
measurements.

Physical allocated memory is distinct from the original logical payload budget.
Reserved unused inline slots, overflow, buckets and pending allocations all
count toward physical peaks. A32-bit game cannot afford an unbounded new cache.
Upfront allocation failure selects the original backend for the entire search,
after releasing partial indexed arrays; no backend switches mid-search.
An arena alternative needs a measured fragmentation/compaction policy; it is
rejected if ordinary churn repeatedly copies the resident pool.

## 3. Immutable ordered threat-source views

A validated battle snapshot can also resolve ordered native unit/city sources
once instead of repeatedly looking them up in every simulated threat pass.
This requires native identity, source order, lifetime and callback/dirty-scene
proofs. Projected damage still stays dynamic. This is a component of the first
redesign, not permission to remove live legality checks or assume every setter
advances a scene epoch.

## 4. Broad legacy overhead

The DLL87 candidate moves checked-failure string formatting into cold helpers.
Successful getters retain their checks without the old formatter-related frames;
global stack protection stays enabled. Its first matched replay improves wall
time about13–15% while retaining recorded behavior. See
`cold-checked-failure-formatting.md` for diagnostic
stack and failure-side temporary-lifetime differences.

Further legacy work should use measured operations, city-production, homeland
and currently unattributed intervals. Flat instruction samples with folded PDB
aliases do not identify a particular object container or prove whole-turn cost.
DLL-only work does not include changing compatibility or registry settings.

The quiet88r2/91OFF253 phase review accounts for most time outside planning:
16.3–16.6 seconds lies in measured phase bounds, with about7.8 seconds between
engine update entries. Very little same-thread CPU is recorded in that dispatch
gap; this does not prove the whole process was idle. Processing the next AI
immediately would change update-hook, timer, network, pause and turn-slice order,
so there is no justified local batching shortcut yet.

Measured non-PLAN envelopes include tactical work7.4–7.5 seconds, other player
scopes6.5–6.7 seconds and homeland2.2 seconds. City doTurn alone is about2.9
seconds. Envelopes overlap child timings; use interval unions. A promising
legacy tactical seam is repeated land/naval distance-field flooding before
every attack attempt, outside the planner and setup timers. Its own elapsed
cost still needs measurement. Reuse needs exact topology, revealed-state,
permissions and capability proof, plus the shared pathfinder's internal-state
contract. Resource and city-state consistency validation is structurally
improvable but bounded by a92/77ms enclosing interval in these replays; defer it.
The detailed source review is `work/off-plan-cost-review-88-91.md`.

## Adoption and validation

1. Compare actual old/new numerical kernels or storage operations, including
   directed invalidation, ordering, collision, capacity and failure cases.
2. Keep measurements bounded and disabled by default. Label censored coverage.
   Instrumented runs cannot serve as clean performance controls.
3. Use matched profiler-off replays of the same immutable save and configuration.
   Compare all retained planning/combat/capture records, nonempty world censuses,
   search outcomes, memory, CPU and complete turn windows.
4. Repeat meaningful gains on another dense era/campaign, then attempt a full
   350-plus-turn campaign. A single fast turn does not meet the objective.

Prioritize a redesign with roughly25% whole-turn gain or at least2x the dominant
planner in matched testing. These are substantial-adoption thresholds, not
predictions. Keep cache traffic counters honest when exact kernel reuse omits
old lookups; capacities and eviction policies remain unchanged.
