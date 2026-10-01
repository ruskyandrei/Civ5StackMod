[CmdletBinding()]
param([Parameter(Mandatory=$true)][string]$RunName,
 [Parameter(Mandatory=$true)][string]$ExpectedDLLSHA,
 [ValidateRange(60,43200)][int]$MaximumSeconds=14400)
# Launch Civ V for a vanilla-VP benchmark: CPU temperature guard and tuner service only.
# (Watch-CivCampaign's no-progress cutoff watches stacking log names, so it is not used.)
$ErrorActionPreference='Stop'
$root='E:\Projects\Civ5StackMod'
$python='C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$pwsh='C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe'
if($RunName -notmatch '^[a-zA-Z0-9-]+$'){throw 'Use a simple unique run name.'}
$run=Join-Path $root ('work\test-runs\'+$RunName)
if(Test-Path -LiteralPath $run){throw 'Run directory already exists.'}
if(Test-Path -LiteralPath (Join-Path $root 'work\tuner-session.json')){throw 'A tuner service is already recorded.'}
if(Get-Process CivilizationV,CivilizationV_DX11,CivilizationV_Tablet -ErrorAction SilentlyContinue){throw 'Game already running.'}
$dll="C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5\MODS\(1) Community Patch\CvGameCore_Expansion2.dll"
if((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -ne $ExpectedDLLSHA){throw 'Installed DLL differs from expected test.'}
[void][IO.Directory]::CreateDirectory($run)
$launch=& $pwsh -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'tools\launch-civ5.ps1')
if($LASTEXITCODE -ne 0){throw 'Launcher failed.'}
$launchData=$launch|ConvertFrom-Json
$game=Get-Process -Id $launchData.Id
$ticks=$game.StartTime.ToUniversalTime().Ticks
$signal=Join-Path $run 'complete.signal'
$common=@('-NoProfile','-ExecutionPolicy','Bypass','-File')
$cpu=Start-Process -FilePath $pwsh -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $run 'cpu-guard.stdout') -RedirectStandardError (Join-Path $run 'cpu-guard.stderr') -ArgumentList ($common+@((Join-Path $root 'work\Watch-CivCpuTemp.ps1'),'-GameProcessId',$game.Id,'-ExpectedStartTicks',$ticks,'-RunDirectory',$run,'-CompletionSignalPath',$signal,'-MaximumSeconds',$MaximumSeconds))
$service=Start-Process -FilePath $python -WorkingDirectory $root -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $run 'tuner-service.stdout') -RedirectStandardError (Join-Path $run 'tuner-service.stderr') -ArgumentList @('-B','-u',(Join-Path $root 'tools\civ5_tuner.py'),'serve')
$identity=@{Game=$game.Id;StartTicks=$ticks;CpuWatcher=$cpu.Id;Service=$service.Id;Signal=$signal;ExpectedDLLSHA=$ExpectedDLLSHA}
$identity|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $run 'watcher-manifest.json') -Encoding utf8
$deadline=[DateTime]::UtcNow.AddSeconds(45)
while(-not(Test-Path -LiteralPath (Join-Path $root 'work\tuner-session.json'))){
 if($service.HasExited -or [DateTime]::UtcNow -ge $deadline){throw 'Persistent service did not initialize; no reconnect attempted.'}
 Start-Sleep -Milliseconds 250
}
$identity|ConvertTo-Json -Compress
