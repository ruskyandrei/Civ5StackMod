# Optional LTCG build monitor

`monitor-ltcg-build.py` is an ignored, optional direct-builder wrapper. Its default only validates prerequisites and writes a fresh evidence plan. It does not launch a compiler, game or tool service, and does not alter priority, affinity, toolchain, project, DLL or game settings. Root must explicitly add `--build` for an authorized full trial.

```powershell
$python = 'C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $python -B work/monitor-ltcg-build.py --run-dir work/test-runs/ltcg-candidate-79-preparation
```

An eventual build command uses a different fresh run directory and adds `--build`. `--mode baseline` adds the original `--no-ltcg`; default mode retains GL/LTCG. Both keep the current `/Z7 /Zm400 /MD /Ox /fp:precise` route. Jobs default2. No action has been run for this wrapper beyond pure fixtures and read-only native API checks.

The monitor refuses preexisting Civ V processes or a compiler/linker at the configured tool paths before preparation and again immediately before launching. It does not race a native benchmark or another matching build. Do not run fixture compiles in parallel with the optional full trial.

Each admitted tool must be a current descendant of a retained, exact live parent, at the configured cl/link/rc/mt image path, with a valid creation timestamp at or after its parent. Admission recursively discovers `/MP` workers. Records retain original process handles; final termination verifies PID, creation time, image and liveness against that handle, so PID reuse cannot redirect a stop. It never uses name-based `Stop-Process`, `taskkill /T`, or termination of shared `mspdbsrv` services. Unknown descendants receive no termination authority.

On a limit it stops the exact launcher first, stopping progression to another build phase, then known verified compiler/tools from deepest child to parent. It rechecks the tool tree at stop. Process discovery is sampled, so a very short-lived or newly spawned unobserved child can escape admission; the monitor does not claim atomic job-object containment. Such a child is never killed through a guessed stale parent identity. A main build that cannot be verified produces a failure report rather than granting stop authority over an unrelated process.

The JSONL records raw per-process kernel/user/total CPU100ns, creation/exit100ns, private/working-set and available peak counters, file-size/mtime progress, monitor CPU time and read-only Core Temp data. Temperature uses the same documented `CoreTempMappingObjectEx` offsets as the existing CPU guard; it never starts Core Temp. Unavailable or malformed data is explicit and resets the consecutive-high counter. Polls default2 seconds. Process starts/ends between polls can be missed; available peak counters describe each observed process, not a total optimizer-memory upper bound.

Defaults are900 seconds total,600 seconds after first observed link process,120 seconds without output or at least50ms process CPU progress,3.2GiB private bytes for any observed owned process, and three consecutive readings at or above95C. These are configurable operational stop limits, not expected build costs. The link timer has up to one poll of start uncertainty and continues until the builder exits; use the builder's `commands.json` for final exact phase duration. CPU progress prevents a quiet but active optimizer from being labeled idle.

Evidence stays in a fresh directory beneath `work/test-runs`: `monitor-plan.json`, `builder-output.log`, `build-monitor.jsonl`, and `monitor-result.json`. A normal zero exit does not by itself accept a DLL: the existing builder's successful `build-result.json`, source hashes, exact GL/LTCG flags and matching DLL/PDB remain required. This helper performs no staging, deployment, benchmark or settings changes.

`test-ltcg-build-monitor.py` passed50 pure checks using a fake process backend: recursive ownership, wrong-parent/old-child/image/PID/creation/liveness mismatches, vanished handles, same-handle stop policy, shared-service exclusion, limits and Core Temp Celsius/Fahrenheit/delta/bad payloads. The actual Win32 identity/memory/snapshot APIs and Core Temp mapping were read-only checked on the checker process. No live child termination or full build has been tested, so root should review the first trial evidence before relying on it unattended.
