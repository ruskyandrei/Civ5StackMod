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
    [string]$CompletionSignalPath,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
# These helpers are side-effect-free with respect to the game/process and are
# extracted by Test-WatchCivLoad.ps1 for disposable-file regression tests.
function Resolve-CivCompletionSignalPath([string]$RequestedPath, [string]$DefaultPath) {
    if ([string]::IsNullOrWhiteSpace($RequestedPath)) { return $DefaultPath }
    $allowed = [IO.Path]::GetFullPath('C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog')
    if (-not [IO.Path]::IsPathRooted($RequestedPath)) { throw 'CompletionSignalPath must be absolute.' }
    $resolved = [IO.Path]::GetFullPath($RequestedPath)
    $name = [IO.Path]::GetFileName($resolved)
    if (-not [string]::Equals([IO.Path]::GetDirectoryName($resolved), $allowed, [StringComparison]::OrdinalIgnoreCase) -or
        -not $name.EndsWith('.signal', [StringComparison]::OrdinalIgnoreCase) -or
        $name.IndexOfAny([IO.Path]::GetInvalidFileNameChars()) -ge 0) {
        throw 'CompletionSignalPath must be a direct *.signal file in C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog.'
    }
    return $resolved
}
function Get-CivLuaAnchor([IO.FileStream]$Stream, [long]$Offset) {
    $length = [int][Math]::Min(64, $Offset)
    if ($length -eq 0) { return '' }
    $bytes = New-Object byte[] $length
    $Stream.Position = $Offset - $length
    $read = 0
    while ($read -lt $length) {
        $count = $Stream.Read($bytes, $read, $length - $read)
        if ($count -eq 0) { return '' }
        $read += $count
    }
    return [Convert]::ToBase64String($bytes)
}
function New-CivLuaCompletionCursor([string]$Path) {
    $cursor = @{ Path = $Path; Offset = [long]0; Tail = ''; Anchor = ''; CreationTicks = [long]0 }
    $stream = $null
    try {
        if ([IO.File]::Exists($Path)) {
            $stream = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
            $cursor.Offset = $stream.Length
            $cursor.Anchor = Get-CivLuaAnchor $stream $cursor.Offset
            $cursor.CreationTicks = [IO.File]::GetCreationTimeUtc($Path).Ticks
        }
    } catch [IO.IOException] { throw 'Cannot establish Lua.log arming offset; retry arming instead of accepting old completion markers.' }
    finally { if ($stream) { $stream.Dispose() } }
    # Deliberately do not import an old partial marker into Tail.
    return $cursor
}
function Read-CivLuaCompletion([hashtable]$Cursor) {
    $marker = 'STACKNAT|HUMAN_RETURN|'
    $stream = $null
    try {
        if (-not [IO.File]::Exists($Cursor.Path)) {
            $Cursor.Offset = [long]0; $Cursor.Tail = ''; $Cursor.Anchor = ''; $Cursor.CreationTicks = [long]0
            return $false
        }
        $stream = [IO.File]::Open($Cursor.Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, ([IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete))
        $limit = $stream.Length
        $creationTicks = [IO.File]::GetCreationTimeUtc($Cursor.Path).Ticks
        $offset = [long]$Cursor.Offset
        $tail = [string]$Cursor.Tail
        # Length catches ordinary truncation; the trailing-byte anchor also
        # catches a truncate/rewrite that grows beyond the previous offset.
        $rewritten = $limit -lt $offset -or $creationTicks -ne $Cursor.CreationTicks
        if (-not $rewritten -and $offset -gt 0) {
            $rewritten = (Get-CivLuaAnchor $stream $offset) -cne $Cursor.Anchor
        }
        if ($rewritten) { $offset = 0; $tail = '' }
        $stream.Position = $offset
        $buffer = New-Object byte[] 65536
        $found = $false
        while ($offset -lt $limit) {
            $count = $stream.Read($buffer, 0, [int][Math]::Min($buffer.Length, $limit - $offset))
            if ($count -eq 0) { break }
            $text = $tail + [Text.Encoding]::ASCII.GetString($buffer, 0, $count)
            if ($text.IndexOf($marker, [StringComparison]::Ordinal) -ge 0) { $found = $true }
            $keep = [Math]::Min($marker.Length - 1, $text.Length)
            $tail = $text.Substring($text.Length - $keep)
            $offset += $count
        }
        $anchor = Get-CivLuaAnchor $stream $offset
        $Cursor.Offset = $offset; $Cursor.Tail = $tail
        $Cursor.Anchor = $anchor; $Cursor.CreationTicks = $creationTicks
        return $found
    } catch [IO.IOException] { return $false } # A transient writer/rotation race is retried next poll.
    catch [UnauthorizedAccessException] { return $false }
    finally { if ($stream) { $stream.Dispose() } }
}
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
$disarmFile = Resolve-CivCompletionSignalPath $CompletionSignalPath (Join-Path $runRoot $signalName)
$logFile = Join-Path $runRoot 'load-watchdog.log'
if (Test-Path -LiteralPath $disarmFile) { throw 'Use a fresh completion signal: the selected signal file already exists.' }
New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($disarmFile)) -Force | Out-Null
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
# Snapshot before arming so prior human returns cannot disarm this turn test.
$luaCompletion = if ($Phase -eq 'ai-turn') { New-CivLuaCompletionCursor (Join-Path $profileLogs 'Lua.log') } else { $null }
function Get-CivTestCompletion {
    if (Test-Path -LiteralPath $disarmFile) { return 'completion signal observed' }
    if ($luaCompletion -and (Read-CivLuaCompletion $luaCompletion)) { return 'new Lua HUMAN_RETURN marker observed' }
    return $null
}
$timer = [Diagnostics.Stopwatch]::StartNew()
$lastElapsed = 0.0
$lastCpu = $target.TotalProcessorTime.TotalSeconds
$highFor = 0.0
$lastProgress = 0.0
$token = ProgressToken
Record "armed pid=$GameProcessId max=${MaximumSeconds}s highCpu=${HighCpuCorePercent}% of one core; $Phase test; signal=$disarmFile; automatic Lua disarm=$($Phase -eq 'ai-turn')"
while ($true) {
    Start-Sleep -Seconds 2
    $completion = Get-CivTestCompletion
    if ($completion) { Record "disarmed: $completion"; break }
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
        $completion = Get-CivTestCompletion
        if ($completion) { Record "disarmed before stop: $completion"; break }
        # Recheck PID, start time and exact executable immediately before stopping.
        $current = Get-Process -Id $GameProcessId -ErrorAction SilentlyContinue
        if ($current -and $current.Path -eq $expectedExe -and $current.StartTime.ToUniversalTime().Ticks -eq $ExpectedStartTicks) {
            $reason = if ($stalledHighCpu) { 'sustained high CPU without log progress' } elseif ($Phase -eq 'ai-turn') { 'bounded test time exceeded' } else { 'bounded load time exceeded' }
            Record "stopping only this disposable game test: $reason"
            Stop-Process -Id $GameProcessId -Force
        }
        break
    }
    $lastCpu = $cpu; $lastElapsed = $elapsed
}
