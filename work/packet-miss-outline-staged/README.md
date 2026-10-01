# Scalar miss cold-outline prototype

Work only, pinned to DLL94 `3601cc10c`. Production source is untouched.
Generate with `work/prepare-packet-miss-outline.py`; run the source-bound VC9
fixture with `work/test-packet-miss-outline.py`. `--production` binds the whole
candidate Tactical source and twelve unchanged math/safety/diagnostic files.
`--emit-only` prepares the fixture without compilation.

The actual DLL94 `CvTacticalAI.obj` reserves **2,272 local stack bytes** and sets
up GS/EH at `GetCachedStackDanger` entry, before fixed-danger or scalar-hit
checks. Its miss-only `StackDangerPacketQuery` contains 2,124 bytes, including
the 2,116-byte private packet buffer and its 512-int descriptor. Even shared
packet borrowers have that private local object in the function's stack layout.

The prototype keeps the original key query, key sample, complete hit path,
miss counter and original loans in the caller. It moves the byte-identical
remainder, from PacketProbeCall to return, into a `__declspec(noinline)` helper.
The helper receives the same key/roster/ledger references and immutable
cacheable/revision/scene values. No math, cache key, capacity, admission/FIFO,
policy, query count, source refresh or callback gate is changed. The stager
reverses the whole delta exactly and pins the moved-tail hash.

Normal and exception cleanup stays leafSample→packetQuery→packetProbe in the
callee, then keySample→key query in the caller. The key scratch loan remains
held throughout the miss helper. Explicit Finish calls remain at the same
boundaries and remain idempotent. /GS and /EHsc are retained in both functions.

The actual-source fixture passed **23,563 checks, zero failures**. It compiles
the pinned Context/provider/strength module, actual scalar/packet/backend and
selected danger/selector/collateral math against deterministic engine services.
It exercises random cities/air/land/alias/HP/fortification states, tiny shared
budgets, explicit outcome batches, hits/misses, private/nested/foreign calls,
epoch callbacks, exceptions and allocation faults. Keys, FIFO contents,
capacities, selected work counters and Context counts match. Fixture-only
destructor markers verify the exact old/new hit, miss and unwind sequences;
they do not appear in the candidate patch. The inactive parent-preparation
release service is explicitly substituted because direct scalar calls do not
activate that separate preparation view.

With the actual 32-byte PlanSampleScope member layout retained and constructor
calls kept out of line, the fixture's old caller frame is also **2,272 bytes**.
The split caller is **68 bytes**, and the cold helper is **2,212 bytes**. Both
retain GS/EH checks. `assembly-proof.json` identifies the exact native and
fixture objects, hashes, decorated symbols and annotated disassemblies.
These are static assembly results; there is **no native speed claim**. The
helper's extra call applies only to scalar misses and may offset some of the
hit-path gain. A matched native replay remains necessary.

Rebase this mechanical tail split after the separately developed resident-key
shortcut. That shortcut owns the hit/key prefix; this prototype keeps that
prefix unchanged.
