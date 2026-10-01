# Local batches before shared packet entries

This ignored experiment is staged from frozen DLL79 commit `e0d85052b`.
DLL80 changes only the strength-key hash, so its TacticalAI input is the same.
No core source, game setting, entry ceiling, payload ceiling, FIFO rule or
numerical body is edited by these staging/fixture commands.

Policy A skips global packet preparation, lookup and admission whenever the
caller supplies an already-ready local outcome batch. The existing scalar-hit
prefix still runs first. On a miss, the unchanged local TryGet validates its
lexical inputs, owner/team/mode, scene and dirty state; a stale or unsuitable
batch follows its existing rebuild/fallback rules. Merely reading ready does
not promise that the batch is valid.

Policy B also avoids seeding a global packet after a cold local batch computes.
It retains the one computed queried result and original queried scalar entry,
with the existing strong post-computation checks. A released or invalidated
result is returned once without replaying its math/callbacks. A cold batch can
still use an already-existing global packet first. Nonbatch queries retain
DLL79's full shared-result path.

The omission is bounded: a ready lexical batch already supplies the nearby
member results without global table nodes. Skipping unqueried precomputation
calls only omits the original callback-free outcome extractor (numeric injury
reads and live fog/improvement/terrain damage); no combat arithmetic is
changed. The local batch's existing immutable-input/synchronous-scene contract
remains required. This variant does not claim to repair arbitrary live
mutation or broaden cache validity.

## Offline proof

`work/packet-batch-pressure-regression/result.json` records **14,546 checks,
zero failures**. The fixture compiles complete actual original77, actual79 and
both staged wrapper/cache/batch variants with the unchanged actual forecast
and extraction graph under deterministic engine services. It retains the
previous whole-wrapper alias, callback, ownership, invalidation, exception,
FIFO and capacity tests. Added batch tests verify:

- already-ready calls use zero packet metadata or odd node admission;
- a cold batch can use an existing global packet without another simulation;
- a stale scene rebuilds exactly once and rebinds the ready batch to that scene;
- dirty refresh, scripted movement and mismatched lexical references retain
  the original one-computation fallback;
- live no-epoch fog damage is still read by the original extractor;
- each actually performed strike graph matches one original leaf trace;
- scalar results and measured retained-capacity/FIFO ceilings stay correct.

Twenty independent immutable local batches, five member queries each, give:

| Fixed entry ceiling |79 evictions |A evictions |B evictions |79 descriptor calls |A |B |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
|2 |158 |118 |98 |560 |120 |100 |
|5 |115 |115 |95 |520 |120 |100 |
|8 |112 |112 |92 |520 |120 |100 |

All variants perform20 original strike sequences in each loop. B admits no
odd packet nodes from those local builders. These are explicit small fixture
workloads, not estimates of native turn time or representative native cache
hit rates. Native usefulness remains unproven.

## Reproduction and adoption boundary

The prerequisites in `docs/shared-danger-packets.md` remain required, including
the historical extraction source and deterministic services. Regenerate the
reviewed79 staging input before the new stage; generated numerical C++ is not
an input:

```powershell
python -B work/shared-packet-storage-stage.py
python -B work/stage-shared-danger-packet.py
python -B work/stage-packet-batch-pressure.py
python -B work/test-packet-batch-pressure.py
```

`--emit-only` on the fixture writes generated C++ without compiling. It uses
one VC9 compiler worker and never applies a patch or builds the full DLL.
The output contains both policies and their exact SHA256 hashes. Policy B is
`work/packet-batch-pressure-candidate/ready-and-local-no-seed.patch`.
The stage source and numerical inputs are pinned in Git; the fixture does not
silently take an adopted candidate as its original control. As with the
previous isolated fixture, native engine services and Lua are substituted;
the reviewed native callback/type boundaries are documented separately.

After adoption, run `python -B work/test-packet-batch-pressure.py --production`.
This first checks all three current TacticalAI/DangerPlots file hashes against
the reviewed B candidate, then compiles the actual current B body. Original79
and77 controls remain pinned in Git. A mismatched or partially adopted checkout
refuses before compilation; the earlier79 fixture's stage remains historical.

Any adoption still needs a distinct native run with exact action/census
comparison and actual per-search hits, misses, packet activity, evictions,
retained bytes and full turn timing. Smaller pressure in these fixture loops
alone does not justify a performance claim.
