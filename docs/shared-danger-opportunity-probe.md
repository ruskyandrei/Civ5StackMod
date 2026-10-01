# Observing repeated stack danger simulations

The existing tactical-sampling toggle now enables one bounded metadata observer
per outer search. Ordinary Summary logging with tactical sampling off allocates
no probe state. Scalar danger hits return before probing. The observer never
supplies a result or changes gameplay cache admission, search limits, XML rules
or randomness.

Selected scalar misses are grouped using complete owner/team/plot, ordered
membership, numerical friendly wounds, fresh ordered threat sources and
projected enemy wounds. Hashes choose cohorts; every stored key word decides
equality. Source reads are const and never refresh a dirty danger map. Ownership,
thread/session/epoch, source-content and reentrancy guards reject invalid
observations. Independent metadata FIFO eviction cannot evict gameplay results.

`PLAN_PACKET_PROBE` distinguishes raw danger calls, existing batch reuse,
outcome-build attempts, same-member repeats and first cross-member repeats.
Counts are censored by sampling, bounds and eviction. They are observed
opportunities, not counts of saved simulations multiplied by a sampling stride.
Output-storage figures estimate the union of stored IDs; they are not vector
capacity or RSS measurements. Native evidence is still required before adopting
broader outcome caching.

The current production fixture passes314 x86 VC9 checks and binds all five
affected files to the diagnostic-only delta from DLL73. It compiles the actual
scalar/cache/batch/key graph, selectors, exchange, collateral and source reader
with deterministic engine services. Original results and cache/FIFO/build
counters agree, including disabled, nested, foreign, reset, source alias/order,
malformed, bounds, collision, invalidation and exception cases. Current typed
setting aliases are checked against source. The metadata block is269,568 bytes;
the maximum formatted detail is1,238 bytes within the3,072-byte buffer.

Run `work/stage-packet-probe.py`, then
`work/test-packet-probe.py --production`; no generated scaffold is required.
Detailed definitions, commands and limits are in `work/packet-probe-design.md`.
