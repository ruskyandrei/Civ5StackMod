# Building and testing the stacking DLL locally

This checkout extends Vox Populi Release 5.4.6 in its existing gamecore DLL. Use the native Microsoft Visual C++ 2008 SP1 x86 toolchain already extracted under `work/toolchain`. Earlier Clang experiments produced a DLL that failed to initialize in this installation; they are retained for investigation and are not the tested build route.

## Build

Run from `E:\Projects\Civ5StackMod`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\work\build-vp.ps1 -Check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\work\build-vp.ps1 -Configuration release -Jobs 2
```

These commands set execution policy only for the child PowerShell process; they do not change user or machine policy. The unsigned local scripts need this explicit process-local option on this PC.

The entry point defaults to Debug and six workers; specify Release and two workers as above for the current testing workflow. Use `-Configuration debug` for an unoptimized diagnostic DLL. `-Python` can select another Python 3.10+ executable. The configured default is the local Codex-bundled Python; no Python package is required by the builder.

`work/build-vp-msvc.py` reads the source list, definitions and libraries from `CvGameCoreDLL_Expansion2/VoxPopuli.vcxproj`. It uses the original Firaxis libraries and native VC9 compiler/linker. Current Release flags include `/MD /Z7 /Ox /Zm400`, with whole-program optimization and LTCG disabled. Debug uses `/Od`. The public DLL interface stays x86.

Before a build intended to identify a new Git checkpoint, run the repository's `update_commit_id.bat` from its expected project directory. The builder deliberately does not modify `commit_id.inc`; its exact content is recorded in the result. A `Dirty` version is expected while implementation is uncommitted.

Each build receives a new `work/msvc-output/Release/<timestamp>` or Debug directory. It contains the DLL and matching PDB, per-step logs, compiler commands, source/header/library input hashes and `build-result.json`. Only `status: success` confirms a successful build. The wrapper rejects source inputs changed during compilation. `work/latest-msvc-build-path.txt` points to the latest successful artifact; it does not identify the currently installed DLL.

Prerequisite locations are recorded in the build result and wrapper: native VC9 SP1 tools under `work/toolchain/sdk/admin/vc9`, resource/manifest tools under `admin/win32tools`, VC9 headers/libraries under `sdk/vc9`, and Windows SDK7 headers/libraries under `sdk/windows`. These extracted tools and large build outputs remain local, outside Git.

## Stage and deploy

Close Civ V before deployment. Stage the chosen DLL and its matching PDB explicitly:

```powershell
$python = 'C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python work\stage_vp.py --dll '<build directory>\CvGameCore_Expansion2.dll' --pdb '<build directory>\CvGameCore_Expansion2.pdb'
& $python work\stage_vp.py --verify
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\work\deploy-vp.ps1 -ValidateOnly
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\work\deploy-vp.ps1
```

Staging reconstructs the FullEUI package from project file lists and refreshes checksums only in staged manifests. Deployment validates the prepared package, archives replaced mapped mod/DLC/cache content under `work/backups`, enables test logging, and verifies every installed file hash. It refuses to run while the game is open. It preserves saves, unrelated mods and current graphics preferences. Record `work/last-deployment-path.txt` and the result JSON when associating runtime evidence with a DLL.

The paths are intentionally specific to this PC and the existing verified backup. Read `work/vp-deployment-common.ps1` before adapting the workflow elsewhere. Do not copy another gamecore DLL alongside this one as an additional mod.

## Configure and test

[Stacking configuration](../docs/stacking-configuration.md) describes editable XML rules. Restart and use a fresh disposable game after XML database changes; no DLL rebuild is needed. Keep the XML and enabled mods identical during DLL comparisons.

Manual test helpers in CP's `Core Files/Stacking` are imported files, not automatic UI add-ins. Include them from FireTuner's InGame context only when testing a disposable game. The helper names describe separate tests for mechanics, movement, AI turns, supplemental combat and XML variations. Setup routines may create units/cities, declare war or grant technology, so they do not belong in a campaign save.

Use `StackingAINaturalTests` for saved AI benchmarks. It creates tagged units on existing terrain and persists fixture metadata in those units. Save through the ordinary game menu before arming a turn observer, reload the same save under each DLL and verify exact fixture identity before comparing results. The older terrain-editing stress fixture produced a save that stalled the closed game renderer; the cause remains unresolved. Ordinary unedited and stack-only saves reload successfully. Do not reuse the stalled save as a general compatibility benchmark.

`work/Watch-CivLoad.ps1` provides bounded `-Phase load` and `-Phase ai-turn` guards for disposable tests. It requires the exact PID, process start ticks, renderer and a fresh evidence directory beneath `work/test-runs`; it rechecks executable identity before stopping that process. It stops on the configured time bound or sustained high CPU without log progress. A time-bound cutoff alone is not evidence of a game hang.

Prefer an explicit `-CompletionSignalPath` naming a fresh, unique `*.signal` directly inside `C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog`. This writable location lets the coordinator disarm without an E-drive write approval delay. For example, use different `test-024049-load.signal` and `test-024049-turn.signal` paths for the load and turn guards. Existing signals are rejected. The legacy default signal inside the evidence directory remains supported but is less suitable for this managed environment.

For a load guard, write its completion signal as soon as Continue Your Journey/the loaded game is visibly ready, then confirm `disarmed` in the watchdog log before ordinary play. For the natural AI benchmark, arm the external `-Phase ai-turn` guard before ending the human turn: it snapshots the current Lua.log offset and automatically disarms on a **new** `STACKNAT|HUMAN_RETURN|` marker, including split writes/log rotation. Old return markers cannot disarm a new test. Its explicit writable signal remains an available fallback after verifying completion. Automatic marker detection is specific to StackAINaturalTests; the generic turn monitor or another helper requires the explicit signal. Both completion checks run again immediately before a stop.

Launch any background guard with `Start-Process -WindowStyle Hidden` and child arguments `-NoProfile -ExecutionPolicy Bypass -File <watchdog path> ...`. Redirect stdout and stderr to separate evidence files. **Require the exact PID's `armed` line in the fresh `load-watchdog.log` before the load or End Turn UI action.** An unsigned-script policy failure previously made a background launch exit before arming; neither a returned process object nor `-ValidateOnly` proves an active guard. See the complete [launch and arming-check example](WATCHDOG.md#launch-and-confirm-arming). The execution-policy flag is process-local; do not change OS/global policy. Do not leave a load guard armed during ordinary play. The in-game observer does not advance turns and cannot stop a stalled game thread. Use the external guard plus observed responsiveness/logs, preserve the last progress marker, and stop an actual frozen high-CPU test promptly. After a completed turn, record that result even if a late manual disarm previously caused the process to be stopped afterward. See [natural benchmark procedure](AI-NATURAL-BENCHMARK.md) and [bounded observation](AI-TURN-MONITOR.md).

## Recovery

Re-stage a known successful DLL/PDB pair and deploy it to return to that build while keeping current source. Every deployment archives its predecessor. `work/restore-vp.ps1 -ValidateOnly` describes restoration of the original pre-5.4.6 installation backup, not merely the previous prototype. Restoration also preserves replaced content and does not overwrite saves. Game preferences change only with the explicit `-RestoreGamePreferences` option.

Keep test results tied to exact DLL, XML and save hashes. A successful build, source review or stub regression is not a substitute for a completed in-game test. See [local regression prerequisites](TEST-PREREQUISITES.md) for the Lua dependency, canonical helper inputs, and the historical air-calibration check that still requires a prebuilt native probe.
