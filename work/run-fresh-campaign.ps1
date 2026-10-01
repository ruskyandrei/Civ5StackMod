[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RunName,
 [Parameter(Mandatory=$true)][string]$ExpectedDLLSHA,
 [Parameter(Mandatory=$true)][string]$SavePrefix,
 [Parameter(Mandatory=$true)][string]$SourceCommit,
 [int]$TargetTurn=270,
 [int]$MaximumSeconds=14400)
# Fresh same-map campaign (campaign102's T000 source, map and roster) with the
# installed DLL: launch with guards, restore the benchmark mods, start autoplay
# from turn 0, then poll with the campaign monitor until the target turn, when
# it stops autoplay and writes a unique final save. Run in the background.
$ErrorActionPreference='Stop'
$root='E:\Projects\Civ5StackMod'
$python='C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pwsh='C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
Set-Location $root
$run=Join-Path $root ('work\test-runs\'+$RunName)
$launchLog=Join-Path $env:TEMP ('civ5-launch-'+$RunName+'.log')
# Not -Wait: that waits for every descendant, including the guards/service.
$p=Start-Process -FilePath $pwsh -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput $launchLog `
 -ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $root 'work\start-short-performance-test.ps1'),'-RunName',$RunName,'-ExpectedDLLSHA',$ExpectedDLLSHA,'-MaximumSeconds',$MaximumSeconds)
$p.WaitForExit()
if($p.ExitCode -ne 0){throw "Launch failed; see $launchLog"}
$mods=Join-Path $root 'work\test-runs\c102-t269-source\expected-mods.json'
& $python -B -u (Join-Path $root 'work\ensure-benchmark-mods.py') --run-dir $run --expected-mods-json $mods
if($LASTEXITCODE -ne 0){throw 'Benchmark mods could not be verified.'}
& $python -B -u (Join-Path $root 'work\start-fresh-campaign.py') --run-dir $run --dll-sha $ExpectedDLLSHA --save-prefix $SavePrefix `
 --source-commit $SourceCommit --target-turn $TargetTurn
if($LASTEXITCODE -ne 0){throw 'Campaign start failed.'}
& $python -B -u (Join-Path $root 'work\monitor-live-campaign.py') --run-dir $run --poll-seconds 60
exit $LASTEXITCODE
