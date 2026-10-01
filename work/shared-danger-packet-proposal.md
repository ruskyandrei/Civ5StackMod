# Shared danger packets: reviewed implementation and validation

DLL74 measured 17,182 selected cohort queries at turn253, 8,616 group
admissions, 8,566 repeats and 6,048 first fresh-work visits by a different
member. Existing local outcome batches served 1,257 selected queries. These
are retained, censored observations; they cannot be multiplied by32 to predict
saved leaves or seconds. They justify an experiment, not adoption. Native
result-cache ROI remains unknown.

## One table, preserving the scalar hit path

Replace the existing danger-table value with a small tagged interpretation:
the first field remains the original integer; a vector is empty for scalar
entries and holds `(native unit ID, final danger int)` for packet entries.
Scalar lookup uses its existing exact key/hash/equality and returns that first
integer. No complete packet key, source descriptor, friendly-ledger sort or
packet search runs before an original scalar hit.

After a valid packet build or hit, admit the **actually queried** original even
key and integer as the old scalar wrapper would do. Packet first, queried
scalar last preserves cheap scalar hits with a one-entry budget. Never preseed
never-queried members' old even keys: the old key omits off-roster friendly
injuries, so that would expand stale-cache assumptions. A new member first
passes the complete odd-key lookup; only then may its legacy integer be stored.
Each group entry therefore adds pressure beside its queried scalar entries;
same table and unchanged limits do not guarantee the old hit rate.

After an original miss, only supported native homogeneous combat rosters can
try a complete packet lookup in that **same danger table**. No third result
table is added. Packet entries naturally compete with scalar entries and the
existing defender table under the same entry/payload ceilings and original
larger-pool-first FIFO policy; that competition can still harm performance.

Namespace separation can avoid a new field/branch in the hot scalar hash. The
current scalar wrapper is the only production caller of
`StoreStackDangerForecast`. Its key has four fixed prefix words, the candidate
count and exact ID/wound pairs, then the enemy count and exact ID/wound pairs:
`6 + 2*N + 2*E` words, always even. An independently validated complete packet
encoding uses an odd length, initially `15 + 2*(ordered roster + full nonzero
friendly ledger + ordered unit/city sources + projected nonzero enemy ledger)`.
It includes seven context/roster/protection/city-health words, four versioned fixed-hazard descriptor
words, one friendly count, two source counts and one enemy count. Full vector
equality remains mandatory. Odd/even is an explicit format namespace; no
sentinel unit ID or hash-only match is trusted. Future builder shape changes
must fail the fixture. Unsupported or partially prepared keys never probe.

## Input and output contracts

The complete key includes query owner/team, plot, actual native friendly-city
mode, exact candidate order/duplicate multiplicity, every numerical friendly
injury including off-stack AA, freshly ordered raw unit/city `(owner,ID)`
sources with duplicates, and the original scalar key's newly projected enemy
injuries including negative city IDs, ID0 and owner aliases. The original live
city protection word is retained verbatim, and any present city's actual damage
is an additional explicit field. City damage does not always advance SceneEpoch.
Both values are checked again before packet lookup and after precomputation.
Duplicate raw
injury entries are rejected because first-occurrence GetValue semantics cannot
be replaced with a sorted multiset. Native player lookup must resolve every
roster member to exactly the same object. Mixed owners, differing teams/modes,
nulls, civilians, mixed land/sea domains, nonnative domains, outside queries, missing maps and malformed
keys use the original scalar path.

A **precomputed final int** additionally includes improvement, fog and flat
terrain extraction. Therefore fixed hazard fields must be part of the fresh
source descriptor, not inferred from source IDs alone. Actual terrain/feature
metadata and unit ignore/extra flags remain under the existing locked preview
scene contract. `CvPlot::getTurnDamage` reads terrain/feature data, performs
integer arithmetic and a volcano-type comparison; it has no Lua callback.
An alternative which supports arbitrary mutation must key these individual
per-unit hazard results too; that adds work and is outside this first scope.

On a packet miss, obtain **one actual GetStackDangerOutcome**. Preserve the
current query's returned int and precompute other supported unique roster
members through actual TryGetStackDangerFromOutcome. Packet hits read only the
stored member int, not the injury ledger. Candidate ordering still determines
sequential casualties and city-garrison ties; no score or damage arithmetic is
rewritten. The temporary final ledger can be released after precomputation.

An already computed local outcome batch can supply the same immutable ledger
after its existing TryGet validates owner/team/mode/revision/scene. A ready
local batch must not be rebuilt just to populate a packet. If a computed batch
was released on invalidation/budget failure, return its current value once and
skip packet admission; never rebuild its original mathematical/callback graph.
The existing raw fallback remains exactly once where no outcome was computed.

Before lookup (including after complete packet preparation) and after computation/precomputation, require owned depth1,
unchanged revision/live scene, non-dirty map, exact source/hazard descriptor,
immutable full injury inputs and native identity/mode. Scripted
CanMoveInto events conservatively bypass packet work. CITY_BOMBARD events also
bypass packet work because a dirty refresh in any caller can mutate unrelated
interceptor counters without a scene change; a local wrapper snapshot cannot
prove all such refreshes were observed. CP XML defaults this option to0 and VP
does not enable it. A read-only query of the active runtime debug database
confirmed EVENTS_CITY_BOMBARD=0, EVENTS_CAN_MOVE_INTO=0 and
BALANCE_BOMBARD_RANGE_BUILDINGS=1 for the controlled campaign. CanMoveInto events cover next-turn
melee, HeavyCharge fallback, MoraleBreak fallback and city-blockade paths even
with quick previews. Dirty refresh can invoke city bombard/reach callbacks:
preserve the original projected-enemy-key refresh **before** packet lookup and
only then capture context/source state. Clean outcome/extract mathematics does
not invoke GetBombardRange. City range-damage/strength/belief helpers have no
additional separate Lua callback found by the independent read-only audit.

Custom `DOMAIN_AIR` units without a ranged attack are also excluded as raw
threat sources. Native ground-attack legality can enter
`canEnterTerrain -> canLoad -> CanLoadAt`, including a fallback Lua hook even
when the two broad event options are off. The const descriptor stays pure;
the packet helper scans its ordered unit sources for this unsupported route
and rechecks context/epoch after those native getters. Standard ranged VP
aircraft remain eligible. Numerical stubs alone do not prove arbitrary custom
movement/loading callback behavior.

Failed postchecks return the one original computed query value, discard the
packet and do not repeat side effects. Nested/foreign calls cannot touch owning
scratch, packet records, accounting or counters. All existing forecast clear,
yield, scene reset and outer-scope-release paths clear packet entries too.
The contract does not promise arbitrary live mission/turn mutations solely
from SceneEpoch; several interceptor setters do not individually advance it.

## Retained storage

Charge `key.state.capacity()*sizeof(int)` plus each retained score-vector
capacity times its pair size to the original shared key-payload ceiling. A
temporary build/copy is not a retained allocation and must not be advertised
as peak-RSS bounded. Fixed node/object estimates reflect the added vector
field for danger nodes; allocator memory remains an estimate. Copy capacity
must be measured from the retained node before final admission/accounting.
Oversized payloads cannot evict useful entries before rejection. Erase/clear
must release vector storage and subtract the same charged capacity. New packet
queue insertion rolls back its inserted node on deque allocation failure.
Existing scalar/defender queue exception behavior is inherited; do not claim
universal allocation-failure safety for those original paths.

## Isolated proof and later native gate

The adopted-source fixture compiles actual unchanged scalar, outcome,
extraction, air, city, selector/exchange/collateral and friendly-city/garrison
bodies with deterministic engine services. It compares original and trial
numeric results, direct/collateral/order traces, computation counts, duplicate
ID rejection, ID0/negative-city aliases, off-stack AA, ordered ties/casualties,
mode/owner changes, fixed hazards, dirty refresh, scene/source invalidation,
exceptions, scripts, nesting, foreign threads, scalar/packet collisions,
payload/entry FIFO pressure and complete release. Production key-builder/store
shape assertions pin the parity format. Existing scalar-only hits must cause
zero packet preparation or extra native getter/clock work.

The final whole-wrapper fixture passed 11,784 checks with zero failures against
the pinned DLL77 control, and strict --production mode matched all three
adopted source hashes before compiling their actual bodies. The offline packet
reader passed 100 checks, including version2 separation of shared packet hits
from existing local-batch reuse. Reproduction commands and complete source
prerequisites are in docs/shared-danger-packets.md.

A distinct native candidate still must compare all actions/censuses and
packet/scalar work/pressure versus the unchanged DLL78 numerical control. More
complete keys and larger nodes can cost more than shared leaves save; DLL61
already demonstrated that new cache pressure can outweigh mathematical reuse.
No search-depth, candidate count, behavior, mechanics, XML or entry-budget cut
belongs in this experiment.
