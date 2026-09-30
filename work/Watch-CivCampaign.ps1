[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][int]$GameProcessId,
 [Parameter(Mandatory=$true)][long]$ExpectedStartTicks,
 [Parameter(Mandatory=$true)][string]$RunDirectory,
 [Parameter(Mandatory=$true)][string]$CompletionSignalPath,
 [ValidateRange(5,60)][int]$SampleSeconds=15,
 [ValidateRange(60,1800)][int]$NoProgressSeconds=480,
 [ValidateRange(60,95)][int]$GpuTemperatureLimit=85,
 [ValidateRange(1,43200)][int]$MaximumSeconds=28800,
 [switch]$ValidateOnly
)
$ErrorActionPreference='Stop'
$allowedRoot=[IO.Path]::GetFullPath('E:\Projects\Civ5StackMod\work\test-runs').TrimEnd('\')+'\'
$runPath=[IO.Path]::GetFullPath($RunDirectory)
if(-not [IO.Path]::IsPathRooted($RunDirectory) -or -not $runPath.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase)){throw 'Run directory must be under work/test-runs.'}
$signalPath=[IO.Path]::GetFullPath($CompletionSignalPath)
if(-not $signalPath.StartsWith($allowedRoot,[StringComparison]::OrdinalIgnoreCase) -or -not $signalPath.EndsWith('.signal')){throw 'Completion signal must be a .signal below work/test-runs.'}
if(Test-Path -LiteralPath $signalPath){throw 'Choose a fresh completion signal.'}
$nativeText=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'Watch-CivMemory.ps1'))
$match=[regex]::Match($nativeText,'(?s)\$nativeSource=@"\r?\n(.*?)\r?\n"@')
if(-not $match.Success){throw 'Native process verifier unavailable.'}
if(-not ('CivMemoryWatch.Native' -as [type])){Add-Type -TypeDefinition $match.Groups[1].Value}
$initial=[CivMemoryWatch.Native]::Read($GameProcessId,$ExpectedStartTicks,$false)
if($ValidateOnly){$initial|ConvertTo-Json -Compress;return}
[void][IO.Directory]::CreateDirectory($runPath)
$evidence=Join-Path $runPath 'campaign-health.jsonl'
if(Test-Path -LiteralPath $evidence){throw 'Health evidence already exists; use a fresh run directory.'}
$gameLogs='C:\Users\rusit\Documents\My Games\Sid Meier''s Civilization 5\Logs'
$smi='C:\Windows\System32\nvidia-smi.exe'
function Write-Event($event){$line=$event|ConvertTo-Json -Depth 5 -Compress;[IO.File]::AppendAllText($evidence,$line+[Environment]::NewLine,[Text.Encoding]::UTF8);Write-Output $line}
function Get-ProgressFingerprint {
 $parts=New-Object 'System.Collections.Generic.List[string]'
 foreach($file in Get-ChildItem -LiteralPath $gameLogs -Filter '*.log' -File){
  if($file.Name -notmatch '^(Stacking-|StackingNative|Lua|AIOperationsLog|TacticalAILog)'){continue}
  $stream=$null
  try{
   $stream=[IO.File]::Open($file.FullName,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)
   $length=$stream.Length
   if($length -gt 0){
    $bytes=New-Object byte[] ([int][Math]::Min(256,$length))
    [void]$stream.Seek(-$bytes.Length,[IO.SeekOrigin]::End)
    $read=$stream.Read($bytes,0,$bytes.Length)
    $parts.Add($file.Name+':'+$length+':'+[Convert]::ToBase64String($bytes,0,$read))
   }
  }catch [IO.IOException]{}finally{if($stream){$stream.Dispose()}}
 }
 return [string]::Join('|',$parts)
}
function Copy-NativeSegments {
 $archive=Join-Path $runPath 'native-segments'
 foreach($file in Get-ChildItem -LiteralPath $gameLogs -Filter "Stacking-*-p$GameProcessId-*.log" -File){
  if($file.CreationTimeUtc.Ticks -lt $ExpectedStartTicks){continue}
  $inputStream=$null;$outputStream=$null
  try{
   $inputStream=[IO.File]::Open($file.FullName,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite -bor [IO.FileShare]::Delete)
   $length=$inputStream.Length
   if($length -lt 20){continue}
   $headerBytes=New-Object byte[] ([int][Math]::Min(512,$length));$read=$inputStream.Read($headerBytes,0,$headerBytes.Length)
   $header=[Text.Encoding]::UTF8.GetString($headerBytes,0,$read)
   $segment=[regex]::Match($header,'^STACKDIAG\|SESSION\|schema=\d+ run=([a-zA-Z0-9-]+) segment=(\d+) ')
   if(-not $segment.Success){continue}
   [void][IO.Directory]::CreateDirectory($archive)
   $dest=Join-Path $archive ($segment.Groups[1].Value+'-segment-'+([long]$segment.Groups[2].Value).ToString('D6')+'.log')
   $outputStream=[IO.File]::Open($dest,[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::Write,[IO.FileShare]::Read)
   $offset=$outputStream.Length
   if($length -lt $offset){Write-Event @{event='segment_shrank';source=$file.Name;segment=$segment.Groups[2].Value};continue}
   [void]$inputStream.Seek($offset,[IO.SeekOrigin]::Begin);[void]$outputStream.Seek($offset,[IO.SeekOrigin]::Begin)
   $buffer=New-Object byte[] 65536
   while($offset -lt $length){
    $read=$inputStream.Read($buffer,0,[int][Math]::Min($buffer.Length,$length-$offset))
    if($read -eq 0){break};$outputStream.Write($buffer,0,$read);$offset+=$read
   }
  }catch [IO.IOException]{Write-Event @{event='segment_observation_error';source=$file.Name;message=$_.Exception.Message}}
  finally{if($inputStream){$inputStream.Dispose()};if($outputStream){$outputStream.Dispose()}}
 }
}
$timer=[Diagnostics.Stopwatch]::StartNew();$previous=$initial;$lastSample=0.0;$lastProgress=0.0;$fingerprint=Get-ProgressFingerprint
$hotSamples=0;$memorySamples=0
Write-Event @{event='armed';utc=[DateTime]::UtcNow.ToString('o');pid=$GameProcessId;startTicks=$ExpectedStartTicks;gpuLimit=$GpuTemperatureLimit;noProgressSeconds=$NoProgressSeconds;maximumSeconds=$MaximumSeconds;cpuTemperature='Unavailable in process telemetry; observe Core Temp separately.'}
while($true){
 if(Test-Path -LiteralPath $signalPath){Copy-NativeSegments;Write-Event @{event='disarmed';reason='completion_signal';utc=[DateTime]::UtcNow.ToString('o')};break}
 if($timer.Elapsed.TotalSeconds -ge $MaximumSeconds){Copy-NativeSegments;Write-Event @{event='disarmed';reason='monitor_duration';utc=[DateTime]::UtcNow.ToString('o')};break}
 try{$sample=[CivMemoryWatch.Native]::Read($GameProcessId,$ExpectedStartTicks,$false)}catch{
  $process=Get-Process -Id $GameProcessId -ErrorAction SilentlyContinue
  if(-not $process){Copy-NativeSegments;Write-Event @{event='game_exited';utc=[DateTime]::UtcNow.ToString('o')};break}
  Write-Event @{event='observation_error';utc=[DateTime]::UtcNow.ToString('o');message=$_.Exception.Message}
  Start-Sleep -Seconds $SampleSeconds;continue
 }
 $now=$timer.Elapsed.TotalSeconds;$elapsed=$now-$lastSample
 $cpu=if($elapsed -gt 0){100.0*($sample.Cpu100ns-$previous.Cpu100ns)/10000000.0/$elapsed}else{0.0}
 $nextFingerprint=Get-ProgressFingerprint
 if($nextFingerprint -ne $fingerprint){$lastProgress=$now;$fingerprint=$nextFingerprint}
 Copy-NativeSegments
 $temperature=$null;$gpuUse=$null;$power=$null
 if(Test-Path -LiteralPath $smi){
  $gpu= & $smi --query-gpu=temperature.gpu,utilization.gpu,power.draw --format=csv,noheader,nounits 2>$null
  if($LASTEXITCODE -eq 0 -and $gpu){$values=($gpu|Select-Object -First 1).Split(',');$temperature=[int]$values[0].Trim();$gpuUse=[int]$values[1].Trim();$power=$values[2].Trim()}
 }
 $hotSamples=if($null -ne $temperature -and $temperature -ge $GpuTemperatureLimit){$hotSamples+1}else{0}
 $lowMemory=$sample.PrivateBytes -ge 3.6GB -or $sample.FreeBytes -lt 128MB -or $sample.LargestFreeBytes -lt 2MB
 $memorySamples=if($lowMemory){$memorySamples+1}else{0}
 Write-Event @{event='sample';utc=$sample.Utc;cpuCorePercent=[Math]::Round($cpu,1);gpuTemperature=$temperature;gpuUse=$gpuUse;gpuWatts=$power;privateBytes=$sample.PrivateBytes;freeBytes=$sample.FreeBytes;largestFreeBytes=$sample.LargestFreeBytes;progressIdleSeconds=[Math]::Round($now-$lastProgress,1)}
 $reason=if($hotSamples -ge 3){'sustained_gpu_temperature'}elseif($memorySamples -ge 3){'sustained_low_address_space'}elseif($now-$lastProgress -ge $NoProgressSeconds){'suspected_stall_no_log_progress'}else{$null}
 if($reason -and -not (Test-Path -LiteralPath $signalPath)){
  [CivMemoryWatch.Native]::StopExact($GameProcessId,$ExpectedStartTicks)
  Write-Event @{event='stopped';utc=[DateTime]::UtcNow.ToString('o');reason=$reason;note='No-log-progress cutoff requires subsequent investigation; alone it does not prove a game hang.'};break
 }
 $previous=$sample;$lastSample=$now
 Start-Sleep -Seconds $SampleSeconds
}
