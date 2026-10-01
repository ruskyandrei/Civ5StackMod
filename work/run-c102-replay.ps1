[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RunName,
 [Parameter(Mandatory=$true)][string]$ExpectedDLLSHA,
 [int]$StartTurn=269,[int]$StopTurn=273,
 [string]$Save='work\test-runs\c102-t269-source\C102 Observer T269.Civ5Save',
 [string]$SaveSHA='ED7C2FA92C0CE0441397D0C53CA36BE2343532F0EA8E6417BE28068F2BA539AD',
 [string]$ViewMode='standard',
 [int]$MaximumSeconds=2400,
 [switch]$SkipLaunch)
# Launch a fresh game with guards and the persistent service, then run one bounded
# observer-source replay of the campaign102 save and quit normally afterwards.
# The launcher's output goes to a file: guards/service inherit its handles, so
# capturing it through a pipe would never complete.
$ErrorActionPreference='Stop'
$root='E:\Projects\Civ5StackMod'
$python='C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pwsh='C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
Set-Location $root
$run=Join-Path $root ('work\test-runs\'+$RunName)
if(-not $SkipLaunch){
 $launchLog=Join-Path $env:TEMP ('civ5-launch-'+$RunName+'.log')
 # Not -Wait: that waits for every descendant, including the guards/service.
 $p=Start-Process -FilePath $pwsh -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $launchLog `
  -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $root 'work\start-short-performance-test.ps1'),'-RunName',$RunName,'-ExpectedDLLSHA',$ExpectedDLLSHA,'-MaximumSeconds',$MaximumSeconds)
 $p.WaitForExit()
 if($p.ExitCode -ne 0){throw "Launch failed; see $launchLog"}
}
$identity=Get-Content -LiteralPath (Join-Path $run 'watcher-manifest.json') -Raw|ConvertFrom-Json
$mods=Join-Path $root 'work\test-runs\c102-t269-source\expected-mods.json'
if(-not $SkipLaunch){
 # Deployment clears the enabled-mod list; restore it at the fresh main menu.
 & $python -B -u (Join-Path $root 'work\ensure-benchmark-mods.py') --run-dir $run --expected-mods-json $mods
 if($LASTEXITCODE -ne 0){throw 'Benchmark mods could not be verified.'}
}
& $python -B -u (Join-Path $root 'work\run-behavior-replay.py') --run-dir $run --save (Join-Path $root $Save) --save-sha $SaveSHA `
 --start-turn $StartTurn --stop-turn $StopTurn --return-player 0 --source-mode observer --view-mode $ViewMode --tactical-sampling off `
 --watch-city Rabat --game-pid $identity.Game --start-ticks $identity.StartTicks --expected-dll-sha $ExpectedDLLSHA `
 --expected-mods-json (Join-Path $root 'work\test-runs\c102-t269-source\expected-mods.json') --maximum-seconds $MaximumSeconds --quit-after-complete
exit $LASTEXITCODE
