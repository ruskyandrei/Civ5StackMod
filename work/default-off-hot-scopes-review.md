# Default-off hot scopes: source review, DLL94

This is a read-only source audit. No production changes or native timing claim.
Assembly inspection and any source-bound compilation wait for the current quiet
replay to close.

## Larger candidate: split the scalar miss path

`GetCachedStackDanger` returns immediately from an existing scalar hit before
constructing `PacketProbeCall`, `StackDangerPacketQuery` and `leafSample`.
However, `StackDangerPacketQuery` embeds a private `StackDangerPacketBuffer`
containing `int descriptor[512]` and four vectors, even when it borrows the
shared packet buffer. A single VC9 function normally reserves its fixed local
stack frame at entry; its GS cookie covers every return. This can therefore
make an admitted scalar hit pay stack/GS/EH scaffolding for a >2KiB miss-only
object. **This must be confirmed in the actual DLL93/94 object assembly**,
rather than inferred to be expensive from its source layout alone.

The proposed transformation leaves the key query loan and `keySample` in the
original function. After the existing `keySample.Finish()` and miss counter,
it calls a `__declspec(noinline)` helper containing the byte-identical remainder
from `PacketProbeCall` to `return result`. It passes the existing key/reference
inputs, cacheable flag, revision and scene. The helper retains /GS and /EHsc.

Normal and exception destruction order must remain:

1. leaf sample finishes/destroys;
2. packet query destroys/releases its packet loan;
3. packet probe finishes/destroys;
4. caller key sample destroys;
5. caller forecast query destroys/releases the original key loan.

The key query stays borrowed across the helper. Both fixed-danger checks, all
packet/scalar gates, source refresh, capacity/FIFO accounting, callbacks,
outcome attempts, sentinel values and math remain at the original boundaries.
No return object or reference may escape. A noinline boundary is essential to
prevent reintroducing the large packet frame into the hot caller.

Required proof: actual-source old/new hit, scalar miss, packet/outcome paths,
dirty refresh, nested/foreign callback, tiny budgets, allocation-fault and unwind
oracle; exact keys/capacities/counter/FIFO snapshots; emitted assembly for both
the hot caller and miss helper. This must be rebased/coordinated with the separate
resident even-key shortcut, which modifies the same caller.

## Small diagnostic-only candidates

`DestinationKernelProbeFrame` initializes only `state=NULL` when its TLS probe
pointer is null. Its arguments are existing pointers, references and scalar
values; neither `GetUnitDangerForPlot` nor `ScoreStackPositionMembers` computes
world getters solely to pass them to the disabled constructor. The large source
footprint, metadata scan, incarnation hash and clocks are behind `BeginActive`.
Its source field layout is expected to be96 bytes at normal VC9 x86 packing8,
pending actual compiler verification. Its remaining off cost is frame/lifecycle
scaffolding and TLS checks, not those world scans.

`PlanSampleScope` uses an out-of-line constructor and initializes all dormant
fields before checking `eligible`, TLS enabled/depth and part bounds. It can
initialize only `sampled=false` on the off path and assign other private fields
only when selection succeeds: `Finish`/`FinishSampled` short-circuit on sampled.
That change is smaller than the packet-frame split and should not be conflated
with a substantial native win. Existing separate-TU actual-source measurements
in `work/plan-sample-disabled-benchmark/result.json` found0.7–1.2ns added on
the modeled actual DoDamageMath path and1.7–1.8ns on a tiny probe. They are
synthetic, not native CPU shares or a prediction of current turn speed.

The actual strength wrappers already run Context before constructing their
22-word strength key; they do not eagerly build that key when ineligible.
Lookup repeats Context after key preparation. Eliminating that validation would
need a separate pure-key-preparation proof and preserve ownership/epoch/options
transitions; this audit does not authorize weakening it. Likewise, the scalar
projector can refresh native sources and trigger a nested path query, so its
post-projection Context cannot simply be removed.
