# DLL97 separated EIP diagnostic readiness

Read-only preparation. **Nothing has been attached, suspended or armed against
the clean DLL97 benchmark.** Do not launch the controller without the root's
explicit authorization for one new, separate diagnostic replay.

## Frozen build identity

Output: `work/msvc-output/Release/20261001-123811`.

- DLL SHA256: `F9D319CB7C2E1DAF3F8C732E870762F080DC62BB3326F726F0E66D2082A3AAB5`
- PDB SHA256: `2656FEC7C62DF485B2AF1959C89CE4BE690F4C8970C485DC2B8BFFD045A1B429`
- Matching RSDS/PDB GUID: `bcea904a-b17a-4a7e-9509-25f8c22572fa`, age1.

The exact disk hashes and PE RSDS/PDB information stream were checked offline;
evidence is `work/eip-d97-preparation-proof.json`. This is not loaded-image proof.
The sampler separately verifies its exact loaded DLL path, disk SHA, loaded PE
timestamp/header and image size during preflight. The captured deployment/load
evidence remains relevant; relocated image bytes are not independently hashed.

## Root-owned launch prerequisites

Use a fresh dedicated run directory beneath `work/test-runs`, with a normal
existing guarded launcher and the reviewed human-source251→255 harness. The
root supplies the fresh exact game PID and .NET UTC creation ticks from the
watcher manifest, then starts the harness. Wait until `harness-events.jsonl`
exists before arming. Initial loading is allowed to have replay Status=preparing;
strict running identity admission happens only after eligible251/252 progress.

The controller needs these files, which must agree:

- `watcher-manifest.json`: game PID/start, expected DLL SHA, service and signal.
- `replay-manifest.json`: running status, same PID/start/SHA, SourceMode=human,
  StartTurn251, StopTurn255, exact service/two guard PID+creation bindings.
- `loaded-dll.json`: same PID/start/SHA and actual loaded DLL path.
- Initial native segment0, named by replay NativeRun, with one consistent
  `TURN_PHASE phase=tactical_ai thread=...` identity before253.
- Healthy exact game/service/two guard held handles, all WAIT_TIMEOUT258; no
  `complete.signal`, stop/failed harness event or existing `eip-*` evidence.

Never reuse the old DLL85 PID, TID, native run or module base. Worker creation can
follow SESSION creation. The sampler qualifies the retained thread against the
first matching native thread row, deriving its UTC from SESSION plus safe
initial-segment tick deltas, with an explicit100ms clock-resolution margin.
After-row creation, malformed/wrapped ambiguity and conflicting tactical TIDs
reject capture. A held thread handle and its creation time prevent ordinary
TID reuse between checks; sub-margin timing is not an exact lifetime proof.

## Controller command template

The root fills the three fresh identity/run values before execution:

```text
python -B work/capture-civ5-eip-at-turn.py --run-dir <fresh diagnostic run directory> --pid <exact watcher game PID> --start-ticks <exact watcher StartTicks> --expected-sha256 F9D319CB7C2E1DAF3F8C732E870762F080DC62BB3326F726F0E66D2082A3AAB5 --maximum-wait-seconds 420
```

If launched as a background PowerShell helper, use Hidden window style and
capture stdio to `capture-controller.stdout.txt`/`.stderr.txt`, outside its
reserved `eip-*` output names. Preserve the helper PID/evidence. Do not overwrite
or restart an earlier controller attempt. The helper automatically performs
one validation-only251/252 preflight, then one capture when harness files first
report active, unpaused observer253. It aborts if253 arrives before preflight or
254/stop is observed before launch. It has no Lua/game API calls.

The sampler command is fixed by the reviewed controller:20Hz, at most512
observations, at most30s, complete.signal stop, default maximum10ms pause.
Cadence includes small external jitter. At20Hz512 observations normally finish
in roughly26s; the wall and sample ceilings are independent. Capture is flat
WOW64 EIP only. Suspension is immediately resumed in mandatory finally, with
no file I/O, module enumeration, symbolization or stack walk while suspended.
Already-suspended threads retain their original suspend count and are not read.

Do not terminate the collector mid-pause. A critical ResumeThread recovery exit3
means preserve evidence and ask the root to stop the exact owned diagnostic run;
no automatic restart/retry. A tracking error after Popen can mean the collector
is still running: retain its exact PID/status and never treat it as no launch.
The420s trigger limit does not forcibly cancel an already running collector.

## Offline interpretation after normal closure

Once the root verifies exact game/service normal closure, symbolize:

```text
python -B work/symbolize-civ5-eip.py <run>/eip-253.jsonl --dll work/msvc-output/Release/20261001-123811/CvGameCore_Expansion2.dll --pdb work/msvc-output/Release/20261001-123811/CvGameCore_Expansion2.pdb --output <run>/eip-symbols253.json
```

This loads matching local DLL/PDB symbols in the helper only, without attaching
to Civ or using network symbol servers. Nearest symbols/displacements require
care with ICF aliases and tiny function bounds. Unresolved addresses stay unknown.
Classify non-gamecore addresses by the captured module ranges separately.

Correlate each sample's nativeTick32 with completed native TURN_PHASE
startTick/endTick intervals on its exact captured thread, using safe uint32
unwrapping and the same run. Keep all nested labels, or report the narrowest
containing label alongside its enclosing phases. Inclusive nested phase counts
must not be summed. Use adjacent-turn recorded intervals too; the253 trigger
alone does not prove every later sample stayed in253. Tick timestamps are
coarse and taken just before suspension; samples near boundaries are ambiguous,
especially under scheduler delays. The native PLAN record gives approximate
search placement rather than a precise sampled instruction ownership interval.

Flat EIP observations are stochastic wall-residency locations, not CPU shares,
call counts or inclusive caller costs. A positive thread CPU delta only means
the thread ran since the previous observation; it cannot assign that entire
interval to the sampled address. Keep zero/unknown CPU deltas, pre-suspended
samples and missing/truncated phase coverage explicit. Never subtract measured
pause overhead from a clean control or call the diagnostic a clean timing pair.

## Lightweight validation performed

Offline DLL/PDB exact hash and RSDS matching passed. Pure native-row/lifetime
qualification tests passed26 checks; mock suspend/context/finally/signal tests
passed14 checks with no owned dummy, real process opens or suspensions. The
existing frozen trigger fixture covers loading→running, pipe-safe TID selection,
identity conflicts, unknown wait states, missed windows and post-Popen evidence
failure; it has not been run against the active clean benchmark. No C++ build,
microbenchmark, controller launch or symbolization was performed.
