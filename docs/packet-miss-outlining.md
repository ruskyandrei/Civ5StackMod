# Separate packet work from scalar danger hits

GetCachedStackDanger used a large packet-query object only after a scalar miss,
but DLL94's compiled function reserved2,272 local bytes and installed its
exception/protection machinery before even the fixed-danger check.

The candidate moves the existing miss tail, byte for byte, into a noinline
helper. The caller retains its original query, key scratch loan, key sampler,
fixed gates, key construction and hit/miss counters. Helper argument evaluation
copies locals and const references only. Cleanup remains leaf sampler, packet
query, packet probe, then caller key sampler and query, including exception
unwinding. No reference gains lifetime across a clearing Context call.

Global /GS and EH compilation stays enabled. With the actual32-byte sampler
member layout, source-bound fixture assembly matches the old2,272-byte frame;
the split caller uses68 bytes and the miss helper2,212. This is static evidence,
not a prediction of native seconds. Additional call overhead applies to misses.
Failure/crash stack locations gain the helper frame; diagnostics should use the
matching new PDB.

The actual-source old/new oracle passes23,563 checks, covering numerical
selectors, collateral and danger, cache/packet behavior, capacities, FIFO,
epochs, callbacks, private/busy/nested/foreign paths, allocation failure and
cleanup traces. Native services are deterministic substitutes; a matched game
replay remains required. Both full Tactical source and twelve unchanged
dependencies are bound in production mode. Whole-source reversal and the
unchanged miss-tail hash are verified. Native benefit is currently unmeasured.
