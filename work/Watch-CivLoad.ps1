[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][int]$GameProcessId,
    [Parameter(Mandatory=$true)][long]$ExpectedStartTicks,
    [Parameter(Mandatory=$true)][string]$RunDirectory,
    [ValidateRange(10,180)][int]$MaximumSeconds = 75,
    [ValidateRange(1,60)][int]$HighCpuSeconds = 15,
    [ValidateRange(1,60)][int]$NoProgressSeconds = 20,
    [ValidateRange(50,2000)][int]$HighCpuCorePercent = 300,
    [ValidateSet('DX9','DX11')][string]$Graphics = 'DX9',
    [ValidateSet('load','ai-turn')][string]$Phase = 'load',
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$expectedExe = "E:\SteamLibrary\steamapps\common\Sid Meier's Civilization V\CivilizationV.exe"
if ($Graphics -eq 'DX11') { $expectedExe = $expectedExe.Replace('CivilizationV.exe','CivilizationV_DX11.exe') }
$projectRoot = [IO.Path]::GetFullPath('E:\Projects\Civ5StackMod\work\test-runs')
$runRoot = [IO.Path]::GetFullPath($RunDirectory)
if (-not $runRoot.StartsWith($projectRoot + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Watchdog output must be in a named test-runs subdirectory.' }
$target = Get-Process -Id $GameProcessId -ErrorAction SilentlyContinue
if (-not $target) { Write-Output 'Test process already exited.'; return }
if ($target.Path -ne $expectedExe -or $target.StartTime.ToUniversalTime().Ticks -ne $ExpectedStartTicks) { throw 'Process identity does not match the explicitly named Civ V test; refusing to monitor or stop it.' }
if ($ValidateOnly) { Write-Output 'Validated exact Civ V process identity; no process change.'; return }
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$signalName = if ($Phase -eq 'load') { 'load-complete.signal' } else { 'turn-complete.signal' }
$disarmFile = Join-Path $runRoot $signalName
$logFile = Join-Path $runRoot 'load-watchdog.log'
if (Test-Path -LiteralPath $disarmFile) { throw 'Use a fresh run directory: completion signal already exists.' }
$profileLogs = "C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\Logs"
$watchedFiles = @((Join-Path $profileLogs 'Lua.log'),(Join-Path $profileLogs 'CustomMods.log'))
function ProgressToken {
    $items = foreach ($path in $watchedFiles) {
        $item = Get-Item -LiteralPath $path -ErrorAction SilentlyContinue
        if ($item) { '{0}:{1}' -f $item.Length,$item.LastWriteTimeUtc.Ticks } else { 'missing' }
    }
    return ($items -join '|')
}
function Record([string]$message) {
    $line = '{0:o} {1}' -f [DateTime]::UtcNow,$message
    Add-Content -LiteralPath $logFile -Value $line
    Write-Output $line
}
$timer = [Diagnostics.Stopwatch]::StartNew()
$lastElapsed = 0.0
$lastCpu = $target.TotalProcessorTime.TotalSeconds
$highFor = 0.0
$lastProgress = 0.0
$token = ProgressToken
Record "armed pid=$GameProcessId max=${MaximumSeconds}s highCpu=${HighCpuCorePercent}% of one core; $Phase test, disarm on successful completion"
while ($true) {
    Start-Sleep -Seconds 2
    if (Test-Path -LiteralPath $disarmFile) { Record 'disarmed: test completion observed'; break }
    $target = Get-Process -Id $GameProcessId -ErrorAction SilentlyContinue
    if (-not $target) { Record 'test process exited'; break }
    if ($target.Path -ne $expectedExe -or $target.StartTime.ToUniversalTime().Ticks -ne $ExpectedStartTicks) { Record 'identity changed; no stop performed'; break }
    $elapsed = $timer.Elapsed.TotalSeconds
    $span = $elapsed - $lastElapsed
    $cpu = $target.TotalProcessorTime.TotalSeconds
    $percent = [Math]::Max(0,100 * ($cpu - $lastCpu) / [Math]::Max(0.01,$span))
    if ($percent -ge $HighCpuCorePercent) { $highFor += $span } else { $highFor = 0 }
    $newToken = ProgressToken
    if ($newToken -ne $token) { $lastProgress = $elapsed; $token = $newToken }
    Record ('elapsed={0:F1}s cpu={1:F0}% highFor={2:F1}s logIdle={3:F1}s privateMiB={4:F0}' -f $elapsed,$percent,$highFor,($elapsed-$lastProgress),($target.PrivateMemorySize64/1MB))
    $stalledHighCpu = $highFor -ge $HighCpuSeconds -and ($elapsed-$lastProgress) -ge $NoProgressSeconds
    if ($stalledHighCpu -or $elapsed -ge $MaximumSeconds) {
        if (Test-Path -LiteralPath $disarmFile) { Record 'disarmed before stop'; break }
        # Recheck PID, start time and exact executable immediately before stopping.
        $current = Get-Process -Id $GameProcessId -ErrorAction SilentlyContinue
        if ($current -and $current.Path -eq $expectedExe -and $current.StartTime.ToUniversalTime().Ticks -eq $ExpectedStartTicks) {
            $reason = if ($stalledHighCpu) { 'sustained high CPU without log progress' } else { 'bounded load time exceeded' }
            Record "stopping only this disposable game test: $reason"
            Stop-Process -Id $GameProcessId -Force
        }
        break
    }
    $lastCpu = $cpu; $lastElapsed = $elapsed
}
