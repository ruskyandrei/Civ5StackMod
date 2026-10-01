# Shared stack danger result packets

The tactical forecast cache can reuse one completed stack-danger simulation
across different queried members of the same supported stack. It retains the
existing scalar lookup first and uses the existing danger table, entry limit,
payload limit and FIFO policy. It adds no gameplay setting, search limit or
combat arithmetic. Native performance remains a measurement question: larger
keys and output vectors also consume cache capacity.

## Lookup and lifetime

An ordinary scalar hit returns the first integer in the cached value before
constructing a packet key, reading its source descriptor or sorting its full
friendly injury ledger. An ordinary miss can query a packet entry only for a
native combat roster with the same owner, team, domain and friendly-city mode.
Nulls, unresolved identities, malformed duplicate injury IDs, mixed domains,
outside queries and singleton rosters use the original scalar path.

Scalar keys have `6+2*N` words and packet keys have `15+2*N` words. Even and odd
lengths form explicit separate namespaces; full vector equality is still
required. The packet key includes ordered roster IDs with duplicate
multiplicity, owner/team/city mode, all numerical friendly injuries including
off-stack interceptors, the original projected enemy injuries and freshly
ordered raw unit/city owner-ID sources. It also retains the original city
protection value, actual city damage and improvement/fog/flat-damage fields.
No wound rounding or unordered roster representation is used.

On a packet miss, one actual outcome simulation supplies the final injury
ledger. The original extraction calculates an integer for each supported
unique roster member. Packet hits read that precomputed integer. An already
computed local outcome batch is used without another simulation. A computed
result invalidated during the call is returned once and never admitted or
recomputed.

After a valid packet build or hit, the actually queried scalar key is admitted
last, preserving inexpensive future scalar hits even with a one-entry budget.
Unqueried scalar keys are never preseeded. Packet and scalar entries therefore
compete in the same table; the previous scalar hit rate is not guaranteed.
Retained output-vector capacity is charged with retained key capacity, while
the fixed node estimate includes the additional vector object. This is a
retained-cache bound, not a bound on temporary allocations or process RSS.

Context, revision, live scene, dirty state, fresh ordered sources, city damage
and protection are checked after key preparation and after computation.
Nested and foreign calls retain the original fallback. Scope exit and existing
cache clear paths release packet entries and scratch. The contract requires
the existing locked synchronous preview scene; epoch checks alone do not
promise reuse across arbitrary live missions or interceptor-counter changes.

New packet work is disabled when CAN_MOVE_INTO or CITY_BOMBARD script events
are enabled. It also rejects custom air melee threat sources, whose terrain
legality can invoke a loading Lua hook. The original refresh and scalar path
remain available. The controlled campaign's runtime database was read-only
verified with EVENTS_CAN_MOVE_INTO=0, EVENTS_CITY_BOMBARD=0 and
BALANCE_BOMBARD_RANGE_BUILDINGS=1.

## Evidence and diagnostics

The adopted-source regression passed **11,784 checks, zero failures**. It
compiles the complete original DLL77 and current cache wrappers, storage,
scratch, keys, FIFO and accounting, with actual unchanged danger/outcome,
extraction, city/air and defender-selection bodies. Deterministic services
stand in for the engine; this is not a complete native engine or arbitrary
Lua callback proof. It covers result equivalence, ordered duplicates and
aliases, off-stack AA, hazards, city health, invalidation during preparation
and computation, scripted fallbacks, nesting, foreign threads and new packet
store allocation failure. Legacy scalar allocation-failure behavior is not
claimed improved.

A separate native type gate uses the actual PlayerTypes enum and
CvPlayerAI::getPlayer declaration. Seven checks pass; its pre-fix control,
which omits the raw source owner's enum cast, must fail VC9 compilation with
C2664. This catches the type distinction intentionally substituted by the
larger mathematical fixture's engine services.

Strict `--production` mode checks all three adopted whole-file hashes before
compiling current code. Every control body is taken from frozen DLL77 commit
`cf8f842e2733841255a1d5bc741e4d95a387299b`; it cannot silently compare the
candidate against itself. Hashes normalize UTF-8 BOM and platform newlines.
The current source names, hashes, fixture hash and result are recorded in
`work/shared-packet-native-regression/result.json`.

Existing once-per-search `PLAN_PERF` reports `packetHits`, `packetBuilds` and
`packetBypasses`. `packetBuilds` counts outcome builds performed for packet
resolution, not queries served by an existing local batch. Probe version2 adds
`packetResultReuseQueries` so selected shared-result hits are distinct from
`batchReuseQueries`. Its reader also supports version1. Counts are censored
observations and cannot be multiplied by the diagnostic stride to predict
saved time. The formatter check verifies 36 arguments for 36 fields and a
worst numeric message of 1,046 bytes below the existing 3,072-byte bound.

The existing `outcomeBuilds` field includes direct packet builds from79 onward;
earlier versions counted local-batch builds only. `packetBuilds` is a subset,
so these counters must not be added or compared as identical local-only work.
The comparison helper reports their raw observed fields with that version
boundary explicit.

## Reproduction

Run from the repository root. The retained staging helpers reconstruct the
reviewed candidate from frozen DLL77; they do not apply patches, build the DLL
or start the game. The fixture requires the locally prepared 32-bit VC9 SDK
under `work/toolchain/sdk`, Python, and the frozen control commit in Git.

Required source prerequisites are:

- `work/shared-packet-storage-stage.py`
- `work/shared-packet-query-buffer.cpp`
- `work/shared-packet-native-helpers.cpp`
- `work/stack-danger-cache-descriptor.cpp`
- `work/stage-shared-danger-packet.py`
- `work/test-shared-packet-native-stage.py`
- `work/test-shared-packet-native-types.py`
- `work/test-shared-danger-packet.py`
- `work/shared-danger-packet-experiment.h`
- `work/test-packet-probe.py`
- `work/packet-probe-fixture-services.h`

The whole-wrapper fixture uses only the pure source-extraction portion of the
earlier mathematical generator. It reads these source prerequisites directly;
no old generated `test.cpp`, previous numerical result, old probe manifest or
pre-existing candidate directory is required. The historical isolated model
script is not the adopted-source test and should not be run against a later
cache implementation without revisiting its own pinned assertions.

```powershell
python -B work/shared-packet-storage-stage.py
python -B work/stage-shared-danger-packet.py
python -B work/test-shared-packet-native-stage.py --production
python -B work/test-shared-packet-native-types.py
python -B work/test-packet-probe-profile.py
```

Use the same native fixture command without `--production` to compile the
staged candidate before adoption. `--emit-only` writes its generated C++
without compiling. The fixture writes only ignored generated/test artifacts
under `work/shared-packet-native-regression`; the staging scripts write only
their ignored output folders. An adopted checkout must match the exact
reviewed three-file candidate, or `--production` refuses before compilation.

For a new native run, compare retained actions and all unit/city censuses with
the unchanged numerical control. Inspect packet reuse, scalar misses,
evictions, retained bytes and full turn time together. An offline equality
proof or a high packet hit count alone does not establish an end-to-end gain.
