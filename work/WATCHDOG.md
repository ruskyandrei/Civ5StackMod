# Civ V test watchdog

`work/Watch-CivLoad.ps1` monitors only the explicitly supplied Civ V PID, exact executable and UTC process-start ticks. The same identity is checked again immediately before a timeout stop. The sustained-high-CPU **and** no-log-progress rule is unchanged. The independent maximum-duration limit still applies.

For `-Phase ai-turn`, the watchdog snapshots `Lua.log` at arming and automatically disarms when new text contains `STACKNAT|HUMAN_RETURN|`. Arm this external watchdog **before** clicking normal UI End Turn. Existing markers and partial markers written before arming are ignored. The reader retains a short tail across polls, reads bounded chunks, handles file absence/rotation and truncation, and checks a trailing-byte anchor for rewrites that grow beyond the old offset. A transient file-sharing error is retried. It checks completion before evaluating a timeout and again before the final process-identity check.

Automatic Lua completion applies only to the `ai-turn` phase. For ordinary loads, signal completion as soon as Continue Your Journey appears. To avoid waiting for permission to write an E: signal, supply a unique direct file path under:

`C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\<run-name>.signal`

Example argument added to the normal watchdog launch:

```powershell
-CompletionSignalPath 'C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\run-20260927-load.signal'
```

When that load succeeds, disarm through the default writable workspace:

```powershell
New-Item -ItemType File -Path 'C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\run-20260927-load.signal' | Out-Null
```

Only direct `.signal` files in that exact directory are accepted; nested directories, sibling directories, traversal outside it, other extensions and wildcard/stream names are rejected. The directory is created after validating the target process. Choose a fresh name: an existing completion signal prevents arming. Omit the option to retain the previous `RunDirectory\load-complete.signal` or `RunDirectory\turn-complete.signal` convention. The log remains `RunDirectory\load-watchdog.log`. Background watchdog launches must use `Start-Process -WindowStyle Hidden`.

AI-turn timeout diagnostics say **bounded test time exceeded**; load diagnostics retain **bounded load time exceeded**. The watcher requires the natural benchmark's `HUMAN_RETURN` marker for automatic completion; other turn helpers should supply an explicit completion signal.

## Focused verification

`work/Test-WatchCivLoad.ps1` extracts the actual reader and path-validator function definitions with the PowerShell parser and exercises them against disposable UTF-8 log files. It does **not** execute the watchdog body, query any process or stop anything. Coverage includes all marker split points, old and partial pre-arm markers, chunk boundaries, missing/rotated files, shorter/same-length/longer rewrites, transient file locks, constrained signal paths and preservation of identity/stall checks.

```powershell
& 'E:\Projects\Civ5StackMod\work\Test-WatchCivLoad.ps1'
```

Default results and retained disposable fixtures are in `C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog-regression`. The checked checkpoint result is also copied to `work/watchdog-regression/result.json`. A successful fixture run validates log/control logic, not a live process-stop test. No game control is used by these checks.
