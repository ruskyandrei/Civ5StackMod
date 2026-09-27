[CmdletBinding()]
param([string]$WatchdogPath = 'E:\Projects\Civ5StackMod\work\Watch-CivLoad.ps1', [string]$ResultDirectory = 'C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog-regression')
$ErrorActionPreference='Stop'
$tokens=$null; $parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($WatchdogPath,[ref]$tokens,[ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
$wanted=@('Resolve-CivCompletionSignalPath','Get-CivLuaAnchor','New-CivLuaCompletionCursor','Read-CivLuaCompletion')
$functions=$ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] -and $wanted -contains $node.Name},$true)
if ($functions.Count -ne $wanted.Count) { throw 'Missing reader/path-validation functions.' }
# Define only those actual source functions. Never execute watchdog process logic.
foreach ($function in $functions) { Invoke-Expression $function.Extent.Text }
New-Item -ItemType Directory -Path $ResultDirectory -Force | Out-Null
$fixture=Join-Path $ResultDirectory ('fixture-'+[Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $fixture | Out-Null
$log=Join-Path $fixture 'Lua.log'; $marker='STACKNAT|HUMAN_RETURN|'
$script:checks=0; $script:failures=0; $script:outcomes=New-Object Collections.Generic.List[string]
function Check([string]$Name,[object]$Actual,[object]$Expected) {
 $script:checks++
 if ($Actual -ne $Expected) { $script:failures++;$script:outcomes.Add("FAIL $Name actual=$Actual expected=$Expected") }
}
function WriteLog([string]$Text) { [IO.File]::WriteAllText($log,$Text,[Text.Encoding]::UTF8) }
function AppendLog([string]$Text) { [IO.File]::AppendAllText($log,$Text,[Text.Encoding]::UTF8) }
WriteLog ($marker+'old');$cursor=New-CivLuaCompletionCursor $log
Check 'existing completion ignored' (Read-CivLuaCompletion $cursor) $false
AppendLog "`nordinary message";Check 'old marker remains ignored after append' (Read-CivLuaCompletion $cursor) $false
AppendLog ("`n"+$marker+'turn=2');Check 'new completion found' (Read-CivLuaCompletion $cursor) $true
Check 'marker not replayed' (Read-CivLuaCompletion $cursor) $false
for ($split=1;$split -lt $marker.Length;$split++) {
 WriteLog ''; $cursor=New-CivLuaCompletionCursor $log
 AppendLog $marker.Substring(0,$split);Check "split $split prefix" (Read-CivLuaCompletion $cursor) $false
 AppendLog $marker.Substring($split);Check "split $split completion" (Read-CivLuaCompletion $cursor) $true
 Check "split $split no repeat" (Read-CivLuaCompletion $cursor) $false
}
WriteLog 'STACKNAT|HUMAN_';$cursor=New-CivLuaCompletionCursor $log
AppendLog 'RETURN|';Check 'pre-arm partial marker cannot complete later' (Read-CivLuaCompletion $cursor) $false
WriteLog ''; $cursor=New-CivLuaCompletionCursor $log
AppendLog 'STACKNAT|HUMAN_';Check 'pending partial before truncation' (Read-CivLuaCompletion $cursor) $false
WriteLog 'RETURN|';Check 'truncation clears old partial' (Read-CivLuaCompletion $cursor) $false
AppendLog $marker;Check 'completion after truncation' (Read-CivLuaCompletion $cursor) $true
WriteLog ('x'*256);$cursor=New-CivLuaCompletionCursor $log
WriteLog ($marker+('y'*512));Check 'rewrite beyond previous offset detected' (Read-CivLuaCompletion $cursor) $true
WriteLog ('x'*256);$cursor=New-CivLuaCompletionCursor $log
WriteLog ($marker+('y'*(256-$marker.Length)));Check 'same-length rewrite detected' (Read-CivLuaCompletion $cursor) $true
WriteLog ''; $cursor=New-CivLuaCompletionCursor $log
AppendLog (('z'*65530)+$marker);Check 'marker crosses internal chunk boundary' (Read-CivLuaCompletion $cursor) $true
Check 'offset catches entire append' $cursor.Offset ([IO.FileInfo]$log).Length
WriteLog $marker;$cursor=New-CivLuaCompletionCursor $log
[IO.File]::Delete($log);Check 'missing rotated log does not complete' (Read-CivLuaCompletion $cursor) $false
WriteLog $marker;Check 'recreated log completion found' (Read-CivLuaCompletion $cursor) $true
[IO.File]::Delete($log);$cursor=New-CivLuaCompletionCursor $log
WriteLog $marker;Check 'log created after arming' (Read-CivLuaCompletion $cursor) $true
WriteLog ''; $cursor=New-CivLuaCompletionCursor $log
$locked=[IO.File]::Open($log,[IO.FileMode]::Open,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
try { Check 'temporary writer lock defers read' (Read-CivLuaCompletion $cursor) $false } finally { $locked.Dispose() }
AppendLog $marker;Check 'reader retries after writer lock' (Read-CivLuaCompletion $cursor) $true
$default='E:\Projects\Civ5StackMod\work\test-runs\sample\turn-complete.signal'
Check 'default project signal preserved' (Resolve-CivCompletionSignalPath '' $default) $default
$allowed='C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\fast.signal'
Check 'direct workspace signal accepted' (Resolve-CivCompletionSignalPath $allowed $default) $allowed
Check 'case-insensitive extension allowed' (Resolve-CivCompletionSignalPath $allowed.Replace('fast.signal','FAST.SIGNAL') $default) $allowed.Replace('fast.signal','FAST.SIGNAL')
foreach ($bad in @('relative.signal','E:\Projects\Civ5StackMod\escape.signal','C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\sub\nested.signal','C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\..\escape.signal','C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\bad.txt','C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog-other\bad.signal','C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\bad*.signal','C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\bad.signal:stream')) {
 $rejected=$false;try { [void](Resolve-CivCompletionSignalPath $bad $default) } catch { $rejected=$true }
 Check "reject $bad" $rejected $true
}
$source=[IO.File]::ReadAllText($WatchdogPath)
Check 'AI timeout diagnostic' $source.Contains("'bounded test time exceeded'") $true
Check 'load timeout diagnostic retained' $source.Contains("'bounded load time exceeded'") $true
Check 'stop still requires exact executable' $source.Contains('$current.Path -eq $expectedExe') $true
Check 'stop still requires exact start ticks' $source.Contains('$current.StartTime.ToUniversalTime().Ticks -eq $ExpectedStartTicks') $true
Check 'high CPU and no-progress still conjunctive' $source.Contains('$highFor -ge $HighCpuSeconds -and ($elapsed-$lastProgress) -ge $NoProgressSeconds') $true
$result=[ordered]@{checks=$script:checks;failures=$script:failures;source_sha256=(Get-FileHash -LiteralPath $WatchdogPath -Algorithm SHA256).Hash;scope='Actual source reader/path functions extracted with PowerShell AST; disposable logs only; no Get-Process or Stop-Process execution';fixture_directory=$fixture;errors=@($script:outcomes)}
$result | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $ResultDirectory 'result.json') -Encoding UTF8
Write-Output "watchdog reader regression: $script:checks checks, $script:failures failures"
$script:outcomes | Write-Output
if ($script:failures) { exit 1 }
