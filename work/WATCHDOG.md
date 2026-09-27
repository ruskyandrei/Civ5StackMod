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

## Launch and confirm arming

Always launch the watcher with `powershell.exe -NoProfile -ExecutionPolicy Bypass -File`. The execution-policy option applies only to that child PowerShell process; it does not change user, machine or registry policy. A background launch without it exited before arming under this PC's unsigned-script policy during the Release024049 load check. `Start-Process` returning a process is not evidence that the guard armed.

Use a fresh evidence directory, redirect both output streams, and require the exact PID's `armed` line in `load-watchdog.log` **before clicking Load/Continue or End Turn**. The following example uses the known disposable game's PID; replace it and select the appropriate renderer/phase. It does not launch the game or request a turn.

```powershell
$gameProcessId = 12345 # Replace with the exact just-launched disposable game PID.
$game = Get-Process -Id $gameProcessId -ErrorAction Stop
$phase = 'load' # Use 'ai-turn' for the natural benchmark's normal UI End Turn.
$runName = [DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-fff') + '-' + $phase
$runRoot = Join-Path 'E:\Projects\Civ5StackMod\work\test-runs' $runName
$signal = Join-Path 'C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog' ($runName + '.signal')
New-Item -ItemType Directory -Path $runRoot -ErrorAction Stop | Out-Null
$stdout = Join-Path $runRoot 'watchdog-stdout.log'
$stderr = Join-Path $runRoot 'watchdog-stderr.log'
$watchLog = Join-Path $runRoot 'load-watchdog.log'
$arguments = @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
    '"E:\Projects\Civ5StackMod\work\Watch-CivLoad.ps1"',
    '-GameProcessId', $gameProcessId,
    '-ExpectedStartTicks', $game.StartTime.ToUniversalTime().Ticks,
    '-RunDirectory', ('"{0}"' -f $runRoot),
    '-Graphics', 'DX9', '-Phase', $phase,
    '-CompletionSignalPath', ('"{0}"' -f $signal)
)
$watchdog = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments `
    -WindowStyle Hidden -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
$deadline = [DateTime]::UtcNow.AddSeconds(10)
$armed = $false
while ([DateTime]::UtcNow -lt $deadline) {
    $watchdog.Refresh()
    if ($watchdog.HasExited) { throw "Watchdog exited before arming; inspect $stdout and $stderr" }
    if (Test-Path -LiteralPath $watchLog) {
        $armed = [bool](Select-String -LiteralPath $watchLog -SimpleMatch " armed pid=$gameProcessId ")
        if ($armed) { break }
    }
    Start-Sleep -Milliseconds 100
}
if (-not $armed) { throw "Watchdog did not confirm arming; do not start the test. Inspect $stdout and $stderr" }
Get-Content -LiteralPath $watchLog -Tail 1
# Only now perform the intended normal UI load or End Turn.
```

An arming failure means stop before the UI action and inspect the redirected errors; do not infer that an invisible background guard is running. `-ValidateOnly` checks process identity and exits without arming, so its success is not a substitute for the `armed` log. Invoke it with the same process-local `-NoProfile -ExecutionPolicy Bypass -File` prefix. After success, confirm `disarmed` in the log; the natural AI guard has been observed automatically disarming on its new human-return marker. No process-stop test is implied by that completion observation.

## Focused verification

`work/Test-WatchCivLoad.ps1` extracts the actual reader and path-validator function definitions with the PowerShell parser and exercises them against disposable UTF-8 log files. It does **not** execute the watchdog body, query any process or stop anything. Coverage includes all marker split points, old and partial pre-arm markers, chunk boundaries, missing/rotated files, shorter/same-length/longer rewrites, transient file locks, constrained signal paths and preservation of identity/stall checks.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File 'E:\Projects\Civ5StackMod\work\Test-WatchCivLoad.ps1'
```

Default results and retained disposable fixtures are in `C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog-regression`. The checked checkpoint result is also copied to `work/watchdog-regression/result.json`. A successful fixture run validates log/control logic, not a live process-stop test. No game control is used by these checks.
