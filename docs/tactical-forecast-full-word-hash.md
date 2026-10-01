# Rejected variable-length tactical forecast hash trial

DLL83 preserved all699 recorded decisions and the before/after censuses, but
the controlled turns took36.125s/72.953s versus35.891s/72.625s for DLL82.
The PLAN sums were10.886s/45.224s. This pair establishes no game-level benefit.
The original forecast hash is restored in the following build; the stage,
tests and synthetic timing evidence are retained as an experiment.

The danger and defender forecast tables still compare every integer and the
vector length for equality. Their FIFO order, payload accounting, scene
checks, scratch ownership, admission and search limits are unchanged.

For keys longer than eight words, four independent unsigned32-bit mixing
lanes replace the serial hash recurrence. The vector length and every word
participate, followed by an avalanche. Shorter keys retain the original
recurrence. Hashes select buckets; they never establish state equivalence.

The whole Tactical source reverses exactly to DLL82 after replacing only the
hash. The VC9 differential fixture compares the actual wrappers, original
combat math and shared cache storage; its danger-table traces also force all
keys to collide. The same exact key/hasher is shared by the defender table. It
covers signed/high-bit values and lengths0–512, FIFO retention and limits.
The initial work-only run passed54,298 checks with no failures. A separate
production-bound run passed54,274 checks without timing again. It binds the
entire adopted Tactical source and unchanged whole Unit/Combat/Danger/Plot/Rules
inputs to DLL82. Its `production-result.json` is separate from the preserved
initial benchmark `result.json`.

Synthetic mixed danger-like keys improved full-cache traces by roughly3–9%;
longer packet-like keys improved more. Short-key traces were flat to a small
regression. These distributions were constructed, not captured from Civ V;
they establish neither end-turn savings nor representative key frequencies.

Selected medians from four alternating VC9 x86 runs:

| Synthetic600k cache operations | Original | Candidate |
| --- | ---: | ---: |
|8-word keys,512 hot keys |18.689ms |19.259ms |
|8–28-word keys,512 hot keys |23.162ms |21.915ms |
|8–28-word keys,6000 hot keys |60.289ms |58.699ms |
|19–511-word keys,512 hot keys |151.540ms |96.450ms |
|19–511-word keys,6000 hot keys |736.494ms |516.239ms |

The6000-key long-vector workload exceeds the unchanged2MiB payload ceiling
and becomes almost entirely misses, unlike the high-hit native scalar path.
The8-word pure hash also measured5.423→5.829ms per1M calls: unchanged values
do not eliminate the small selection-branch cost. Fixture traces time actual
container/ownership/store/eviction/equality bodies but exclude native key
building and most engine services. These medians cannot predict full turn time.

Use a matched, sampling-off replay to assess actual benefit and retain the
original numerical calculations and recorded decisions.

Reproduction is in `work/stage-tactical-key-hash.py` and
`work/test-tactical-key-hash.py`; staging and regression artifacts live under
`work/tactical-key-hash-stage` and `work/tactical-key-hash-regression`.
The historical packet fixture prerequisites in `shared-danger-packets.md`,
the locally prepared VC9 SDK and frozen82 Git source are required. No old
generated C++ is an input. After adoption, reproduce the strict proof without
repeating the benchmark:

```powershell
python -B work/shared-packet-storage-stage.py
python -B work/stage-shared-danger-packet.py
python -B work/stage-tactical-key-hash.py
python -B work/test-tactical-key-hash.py --production --no-benchmark
```

Staging/fixtures never apply core patches, build the DLL or start the game.
Future numerical-source migrations require explicit fixture review; they
must not silently bypass whole-file binding assertions.
