# Variable-length tactical forecast hashes

The danger and defender forecast tables still compare every integer and the
vector length for equality. Their FIFO order, payload accounting, scene
checks, scratch ownership, admission and search limits are unchanged.

For keys longer than eight words, four independent unsigned32-bit mixing
lanes replace the serial hash recurrence. The vector length and every word
participate, followed by an avalanche. Shorter keys retain the original
recurrence. Hashes select buckets; they never establish state equivalence.

The whole Tactical source reverses exactly to DLL82 after replacing only the
hash. The VC9 differential fixture compares the actual wrappers, original
combat math and both tables under ordinary and forced-collision hashing. It
covers signed/high-bit values and lengths0–512, FIFO retention and limits.
The initial work-only run passed54,298 checks with no failures. A separate
production-bound run must bind the adopted source before native testing.

Synthetic mixed danger-like keys improved full-cache traces by roughly3–9%;
longer packet-like keys improved more. Short-key traces were flat to a small
regression. These distributions were constructed, not captured from Civ V;
they establish neither end-turn savings nor representative key frequencies.
Use a matched, sampling-off replay to assess actual benefit and retain the
original numerical calculations and recorded decisions.

Reproduction is in `work/stage-tactical-key-hash.py` and
`work/test-tactical-key-hash.py`; staging and regression artifacts live under
`work/tactical-key-hash-stage` and `work/tactical-key-hash-regression`.
