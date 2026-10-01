# Work-only shared danger outcome opportunity probe

The staged five-file patch is measurement only. It never changes an AI result,
assignment, stack capacity, search budget, gameplay cache, RNG state or source
map. The stage script rebuilds against current production and reverse-strips
every diagnostic annotation to require exact equality with that production.
The immutable enemy-damage fragment introduced in DLL72 remains untouched.

The existing `Game.SetStackingTacticalSampling(bool)` runtime switch gates this
probe alongside sampled timings. Sampling off creates no metadata scope. A
scalar danger hit returns before the probe constructor. An active outer PLAN
owns one fixed POD metadata block, allocated with `nothrow`, released on scope
exit, and never shared with gameplay caches. No new XML option is required.

## What is observed

Only original cacheable scalar misses are eligible. A cheap deterministic
prefilter hashes the already-built scalar key excluding member ID and that
member's wound prefix, salted by PLAN serial and forecast revision/scene. The
two low bits must be zero. Selected queries build a complete metadata key, then
require three low bits of its deterministic hash to be zero. Both hashes are
only selection aids; retained groups compare every complete key word.

The complete key contains owner, team, plot index, native friendly-city result,
the ordered roster's owner/ID pairs including duplicates, every numerical
nonzero friendly injury (including off-stack interceptors), ordered unit and
city source owner/ID pairs, and the original key's freshly projected enemy
injuries. City source duplicates and negative enemy city IDs are retained.
Malformed duplicate stored injury IDs, null or nonnative queried units,
outside queries, mixed owners, unresolved native identity, singleton rosters,
more than 32 distinct roster members, oversized keys, and unavailable/dirty
source maps are excluded. Explicit stored zero injuries equal missing entries
numerically; they can change the logical output-storage estimate.

Source observation is const and never refreshes a map. The source reader uses
remaining-capacity subtraction checks before writing. Entry and completion
checks require original TLS identity, sampler serial/epoch, forecast depth,
revision, cached scene and live strength scene. Completion rereads the ordered
raw sources to reject reordering or rebuilds which occurred without a scene
change. A busy sentinel suppresses nested pending observers without overwriting
their shared scratch. Scripted movement events disable scope admission.

This is the existing locked, synchronous, callback-free native preview
contract. It is not a claim that scene epochs cover arbitrary live mission,
interceptor counter, XML, UI or asynchronous game mutations. A toggle/reset
changes the sampler epoch and suppresses stale rows.

## Bounds and definitions

There are 128 diagnostic FIFO slots, each with at most 512 exact integer key
words, two bounded shared scratch buffers, and fixed counters. The actual
native x86 `sizeof(PacketProbeState)` is measured by the fixture; a hard check
rejects sizes above 3 MiB. Friendly/enemy ledger validation accepts at most 128
stored raw pairs. No per-query metadata allocation occurs after scope creation.
Metadata eviction does not evict or admit any gameplay result.

One `PLAN_PACKET_PROBE` record is emitted per still-valid outer PLAN through the
existing performance category and row budget. It reports original scalar
misses, prefiltered and selected cohort queries, retained group admissions,
same-member repeats, first new cross-member repeats, fresh-work query classes,
raw scalar calls, outcome-builder attempts, field/city groups, bounds/fallbacks,
evictions/clears and metadata key bytes. `sameMember` means that member was
already seen in this retained group; `crossMember` means its first observation
after a different member. Subsequent visits to that now-seen member count as
same-member. FIFO clears restart membership history.

`freshQueries` counts selected queries which called the original raw scalar
method or incremented the existing outcome-builder counter. It counts queries,
not successful simulations. An attempted batch may fail before a raw fallback,
so `outcomeBuildAttempts` and `rawCalls` remain separate. A query served by an
existing local outcome batch counts as `batchReuseQueries`; it must not be
called an avoidable original leaf. `freshCrossMemberQueries` counts the first
fresh-work visit by a new member after earlier fresh work in the retained group.

`outputUpperBytes` is the first admitted group's logical pair-storage upper
estimate: the union of stored friendly injury IDs and distinct roster IDs,
multiplied by the pair size. It does not measure final ledger capacity, inline
container cost, nodes, future global residency or allocation policy. Stored
zeros can make this estimate differ across otherwise equal numerical groups.
No duplicate danger simulation is performed to estimate storage.

All overlap is censored by both sampling filters, metadata bounds, unsupported
inputs, FIFO eviction and scene clears. Do not multiply observed repeats by
32 to predict saved leaves or seconds. The probe may itself cost time when
enabled, particularly the prefiltered full-key construction and source copies.
Native off/on equivalence and overhead measurements are required before using
the results to justify any result-cache redesign.

## Validation / reproduction

The stage generator is pinned to DLL73 commit
`ddab3d93397871f5fb41e99169b06cecffadddfd`, read with `git show`. It therefore
regenerates the original-to-probe patch after adoption without double patching
the current tree. It writes only `work/packet-probe-candidate/`. All five
candidate and original source hashes are recorded, with a strict diagnostic
reverse-strip equality proof. UTF-8 BOM handling and Windows line endings are
normalized consistently; no original comments or math are removed.

Run the fixture with `--production` after the probe has been adopted. Before
compiling, it requires every current production file to equal the staged
candidate exactly. It then compiles actual adopted observer/token/reader bodies
alongside the pinned original scalar wrapper and current cache/FIFO/batch/key/
immutable-fragment code. Without `--production`, the current tree must equal
the pinned original instead and it compiles staged bodies.

These four helper inputs must be tracked together:

- `work/stage-packet-probe.py`
- `work/packet-probe-tactical-fragment.cpp`
- `work/test-packet-probe.py`
- `work/packet-probe-fixture-services.h`

The fixture additionally reads these existing tracked source files:

- `CvDangerPlots.h/.cpp`
- `CvStackingDiagnostics.h/.cpp`
- `CvTacticalAI.cpp`
- `CvUnit.h`, `CvUnitCombat.cpp`, `CvPlot.cpp`
- `CvStackingRules.h/.cpp`

These files are all under `CvGameCoreDLL_Expansion2/`. The frozen DLL73 commit
must be present in the Git history. No previously generated ignored C++ fixture
is required. `test-stack-danger-packets.py`, its prototype header and the old
zero-AoE generated scaffold are not dependencies of this probe fixture.

The numerical service header contains only deterministic engine substitutes.
The actual container and contents declarations, field/city/air forecast bodies,
selector/exchange/collateral bodies and native friendly-city/garrison bodies are
extracted afresh. Original math bodies must equal their DLL73 originals. The
fake typed setting service binds all 24 names to the actual production enum
ordinals and uses the existing numerical string-service toggles/fallbacks;
this fixture does not retest XML loading. Its results are not evidence about
native damage arithmetic, profiler overhead or saved end-turn time.

Use the bundled Python and existing genuine VC9/Windows SDK fixture toolchain:

```powershell
$packetPython = 'C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $packetPython -B work/stage-packet-probe.py
& $packetPython -B work/test-packet-probe.py --production
```

The expected local compiler/headers/libraries are the existing
`work/toolchain/sdk/admin/vc9/Program Files/Microsoft Visual Studio 9.0/`,
`work/toolchain/sdk/vc9/` and `work/toolchain/sdk/windows/` paths. The bounded
single-worker regression writes `work/packet-probe-regression/test.cpp`,
`compile.log` and `result.json`. Both helpers leave production files untouched.

Current adopted-code binding passed **314 checks, 0 failures**. Fixed metadata
is **269,568 bytes**; maximum-width numeric fields produce a **1,238-byte**
summary message, below the existing 3,072-byte message buffer. The result JSON
records all five actual source hashes, unchanged original math-body hashes and
the exact 24 typed names. No native packet-overlap or speed result exists yet.
