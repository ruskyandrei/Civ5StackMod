# Full-word strength-cache hash

The indexed strength cache now mixes its22 integer key words through four
independent unsigned lanes and a final avalanche. This shortens the dependency
chain of the previous hash. Full88-byte equality still decides identity;
collisions cannot merge values. Ownership, epochs, nesting, FIFO, entry limits,
allocations and statistics are unchanged. Hashes are neither serialized nor
used to rank tactical choices. Integer overflow is intentional modulo32 bits.

The proposed algorithm passed434,703 actual-module checks, including the timed
fixture's extra assertions. The adopted `--no-benchmark` fixture passed434,679
checks. Both compare actual old/new modules, including collisions, signed
extremes, all704 individual input-bit changes, FIFO, invalidation, foreign
threads and allocation failures. `work/test-strength-hash-experiment.py
--variant multiply1 --production --no-benchmark` verifies the complete adopted
file and public header before compiling with VC9 x86.

Isolated synthetic tests measured about30% less pure-hash time and6–10% less
cache time in mixed resident/churn traces. One repeating512-key trace took
about2.5% longer. These profiles are synthetic rather than captured game keys;
they do not predict turn-time savings. A separate native replay must compare
recorded actions, nonempty world censuses, cache pressure and complete turn
windows. Reproduction helpers retain the rejected slower two-multiply variant
for comparison. No gameplay or search-limit change is involved.
