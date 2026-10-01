# Contiguous storage for combat-strength forecasts

The search-scoped strength cache now keeps nodes in a contiguous vector with
integer bucket links and an insertion-order ring. It stores the same22-word
keys and integer results. Hashes select buckets; complete key equality still
decides hits. Duplicate insertion does not update results or FIFO order. Entry
limits, statistics, ownership/depth checks, invalidation and post-computation
admission checks retain their original behavior.

Indices survive vector growth, so neither bucket links nor FIFO state depends
on addresses. Eviction unlinks the oldest slot and reuses that slot; clearing
resets nodes, bucket heads and ring position. Scope destruction releases both
allocations in the32-bit process. An allocation failure during constructor
setup releases ownership and payload before rethrowing, avoiding an incomplete
scope retaining the owning-thread claim.

The current production fixture passes433,070 checks with x86 VC9. It binds the
complete representation-only source transform and unchanged public header,
keys/hash/equality/context functions. It exercises collisions, foreign/nested
contexts, invalidation, duplicate FIFO behavior, capacities through65,536,
eviction/link integrity, statistics, complete release and injected constructor
allocation failure followed by reopening. Production binding deliberately runs
without a timing benchmark.

Historical synthetic lookup tests improved, but omit unit getter/key-building
cost and are not native predictions. At default capacity16,384 the prototype's
retained payload is about1.835MB, transient growth about2.687MB, before allocator
overhead; worst allowed growth is about10.748MB. Clearing bucket heads can also
cost more than the old representation for tiny caches invalidated frequently.
Native timing, memory and unchanged action/census checks decide adoption.

Reproduce with `work/prepare-strength-index-container.py`, then
`work/test-strength-index-container-prototype.py --production --no-benchmark`.
