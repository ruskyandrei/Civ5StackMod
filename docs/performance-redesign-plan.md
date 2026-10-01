# Larger DLL performance redesigns

The current objective is below 30 seconds per late-game turn on a standard game,
then below 20 seconds if practical. It is not achieved. The DLL86 dense-turn253
control takes about74 seconds, of which about47 seconds are inside tactical
planning. DLL87 brings those figures to63.5 seconds and39 seconds. Even halving
the remaining planning would leave roughly44 seconds. Changes outside the
planner also matter.

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

Start with a bounded, opt-in shadow measurement. The original kernels still
drive play. Record equal observed input signatures across different states,
their original results, descriptor cost, invalidations and coverage limits.
Observed signature equality is an opportunity measurement, not certification
of a complete dependency contract. Prove dependencies and directed stale-reuse
tests before activating reuse.

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
eviction-heavy traces are about4x faster, but native whole-turn benefit remains
unmeasured. Query preparation and CRT bookkeeping are outside these allocation
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
