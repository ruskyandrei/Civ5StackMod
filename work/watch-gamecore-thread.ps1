<# Read-only, bounded same-user OS thread sampling. Never suspends/attaches,
calls Lua, changes priority/affinity, or starts an ETW session. ThreadState and
WaitReason are snapshots, not proof of a specific engine timer or lock. #>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateRange(1,2147483647)][int]$GamePid,
    [Parameter(Mandatory=$true)][long]$StartTicks,
    [Parameter(Mandatory=$true)][ValidateRange(1,2147483647)][int]$CoreThreadId,
    [Parameter(Mandatory=$true)][string]$NativeRun,
    [Parameter(Mandatory=$true)][string]$NativeLog,
    [Parameter(Mandatory=$true)][string]$DLLPath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedDLLSHA256,
    [Parameter(Mandatory=$true)][string]$OutputJsonl,
    [string]$StopSignal,
    [ValidateRange(50,1000)][int]$SampleMilliseconds=100,
    [ValidateRange(1,600)][int]$DurationSeconds=180,
    [ValidateRange(1,6001)][int]$MaximumSamples=3000,
    [ValidateRange(65536,16777216)][int]$MaximumBytes=4194304
)
$ErrorActionPreference='Stop'
$projectRoot=[IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent $PSCommandPath)))
$allowed=[IO.Path]::GetFullPath((Join-Path $projectRoot 'work\test-runs'))+'\'
$outputPath=[IO.Path]::GetFullPath($OutputJsonl)
$summaryPath=[IO.Path]::ChangeExtension($outputPath,'.summary.json')
if(-not $outputPath.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase) -or [IO.Path]::GetExtension($outputPath) -ne '.jsonl'){
    throw 'Output must be a new .jsonl beneath project work/test-runs'
}
if(-not (Test-Path -LiteralPath ([IO.Path]::GetDirectoryName($outputPath)) -PathType Container)){
    throw 'Output parent must already exist'
}
if((Test-Path -LiteralPath $outputPath) -or (Test-Path -LiteralPath $summaryPath)){
    throw 'Sampling evidence already exists; never overwrite or resume it'
}
if($StopSignal){
    $StopSignal=[IO.Path]::GetFullPath($StopSignal)
    if(-not $StopSignal.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'Stop signal must be beneath project work/test-runs'}
    if(Test-Path -LiteralPath $StopSignal){throw 'Stop signal already exists'}
}
$runPattern='^Stacking-(?<date>\d{8})T(?<time>\d{6})-(?<ms>\d{3})-p(?<pid>\d+)-r\d+$'
$runMatch=[regex]::Match($NativeRun,$runPattern)
if(-not $runMatch.Success -or [int]$runMatch.Groups['pid'].Value -ne $GamePid){throw 'Native run must identify the exact game PID'}
$nativeUTC=[DateTime]::ParseExact($runMatch.Groups['date'].Value+'T'+$runMatch.Groups['time'].Value+$runMatch.Groups['ms'].Value,
    "yyyyMMdd'T'HHmmssfff",[Globalization.CultureInfo]::InvariantCulture,
    [Globalization.DateTimeStyles]::AssumeUniversal -bor [Globalization.DateTimeStyles]::AdjustToUniversal)
$nativePath=(Resolve-Path -LiteralPath $NativeLog).Path
if(-not $nativePath.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)){throw 'Native evidence must be beneath project work/test-runs'}
$dllFullPath=(Resolve-Path -LiteralPath $DLLPath).Path
$watchClock=[Diagnostics.Stopwatch]::StartNew()
$ownProcess=[Diagnostics.Process]::GetCurrentProcess()
$ownCPUStarted=$ownProcess.TotalProcessorTime.Ticks
$target=$null;$writer=$null;$samples=0;$bytes=0;$pollWall=0.0;$pollCPU=0L
$status='validation';$failure=$null;$binding=$null;$stateCounts=@{};$reasonCounts=@{}
$cpuFirst=$null;$cpuLast=$null;$captureStarted=0.0;$captureFinished=0.0
function Get-ExactTarget {
    param([Diagnostics.Process]$Process)
    $Process.Refresh()
    if($Process.HasExited){return $false}
    if($Process.StartTime.ToUniversalTime().Ticks -ne $StartTicks){throw 'Exact PID start identity changed'}
    return $true
}
function Get-CoreThread {
    param([Diagnostics.Process]$Process)
    $threads=$Process.Threads
    $selected=$null
    foreach($item in $threads){
        if($item.Id -eq $CoreThreadId){$selected=$item}else{$item.Dispose()}
    }
    return $selected
}
function Get-SHA256 {
    param([string]$Path)
    $algorithm=[Security.Cryptography.SHA256]::Create()
    $inputFile=[IO.File]::OpenRead($Path)
    try{return [BitConverter]::ToString($algorithm.ComputeHash($inputFile)).Replace('-','')}
    finally{$inputFile.Dispose();$algorithm.Dispose()}
}
try {
    $reader=New-Object IO.StreamReader($nativePath)
    try{
        $header=$reader.ReadLine()
        if(-not $header.StartsWith('STACKDIAG|SESSION|') -or $header -notmatch ('(?:^|\s)run='+[regex]::Escape($NativeRun)+'(?:\s|$)')){
            throw 'Native header does not match supplied run'
        }
        $threadObserved=$false;$nativeLines=0
        $threadPattern='\|(?:TURN_PHASE|TURN_UPDATE_GAP)\|.*(?:^|\s)thread='+$CoreThreadId+'(?:\s|;|$)'
        while(-not $reader.EndOfStream -and $nativeLines -lt 65536 -and $reader.BaseStream.Position -lt 8388608){
            $line=$reader.ReadLine();++$nativeLines
            if($line -match $threadPattern){$threadObserved=$true;break}
        }
        if(-not $threadObserved){throw 'Core thread was not observed in the supplied native session'}
    }finally{$reader.Dispose()}
    $target=[Diagnostics.Process]::GetProcessById($GamePid)
    if(-not (Get-ExactTarget $target)){throw 'Exact game process has exited'}
    $loaded=@($target.Modules | Where-Object {[String]::Equals($_.FileName,$dllFullPath,[StringComparison]::OrdinalIgnoreCase)})
    if($loaded.Count -ne 1){throw 'Expected DLL path is not loaded once in the exact process'}
    $dllSHA=Get-SHA256 $dllFullPath
    if($dllSHA -ne $ExpectedDLLSHA256.ToUpperInvariant()){throw 'Expected DLL SHA256 does not match loaded path'}
    $core=Get-CoreThread $target
    if($null -eq $core){throw 'Native core thread is not present in the exact process'}
    try{
        $coreStartTicks=$core.StartTime.ToUniversalTime().Ticks
        if($coreStartTicks -gt $nativeUTC.AddSeconds(1).Ticks){throw 'Current thread was created after native session began; possible reused thread ID'}
    }finally{$core.Dispose()}
    $binding=[ordered]@{processPID=$GamePid;processStartUTCTicks=$StartTicks;processName=$target.ProcessName;
        nativeRun=$NativeRun;nativeLog=$nativePath;nativeThread=$CoreThreadId;threadStartUTCTicks=$coreStartTicks;
        loadedDLL=$dllFullPath;loadedDLLSHA256=$dllSHA;helperPID=$PID;sampleMilliseconds=$SampleMilliseconds;
        durationSeconds=$DurationSeconds;maximumSamples=$MaximumSamples;maximumBytes=$MaximumBytes}
    $stream=New-Object IO.FileStream($outputPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::Read)
    $encoding=New-Object Text.UTF8Encoding($false)
    $writer=New-Object IO.StreamWriter($stream,$encoding,65536)
    $captureStarted=$watchClock.Elapsed.TotalMilliseconds
    $status='sampling'
    while($samples -lt $MaximumSamples -and $watchClock.Elapsed.TotalMilliseconds-$captureStarted -lt $DurationSeconds*1000){
        if($StopSignal -and (Test-Path -LiteralPath $StopSignal)){$status='completion_signal';break}
        $pollStart=$watchClock.Elapsed.TotalMilliseconds
        $ownBefore=$ownProcess.TotalProcessorTime.Ticks
        if(-not (Get-ExactTarget $target)){$status='process_exited';break}
        $core=Get-CoreThread $target
        if($null -eq $core){$status='core_thread_exited';break}
        $row=[ordered]@{sample=$samples;utc=[DateTime]::UtcNow.ToString('o');nativeTick32=([long][Environment]::TickCount -band [long]4294967295);
            elapsedMilliseconds=$watchClock.Elapsed.TotalMilliseconds-$captureStarted;thread=$CoreThreadId;
            state=$null;waitReason=$null;cpu100ns=$null;cpuDelta100ns=$null;fieldError=$null}
        try{
            if($core.StartTime.ToUniversalTime().Ticks -ne $coreStartTicks){throw 'Core thread creation identity changed'}
            $stateValue=$core.ThreadState
            $row.state=$stateValue.ToString()
            if($stateValue -eq [Diagnostics.ThreadState]::Wait){$row.waitReason=$core.WaitReason.ToString()}
            $row.cpu100ns=$core.TotalProcessorTime.Ticks
            if($null -eq $cpuFirst){$cpuFirst=$row.cpu100ns}
            if($null -ne $cpuLast){
                if($row.cpu100ns -lt $cpuLast){throw 'Core CPU counter moved backwards'}
                $row.cpuDelta100ns=$row.cpu100ns-$cpuLast
            }
            $cpuLast=$row.cpu100ns
        }finally{$core.Dispose()}
        if($null -ne $row.state){if(-not $stateCounts.ContainsKey($row.state)){$stateCounts[$row.state]=0};++$stateCounts[$row.state]}
        if($null -ne $row.waitReason){if(-not $reasonCounts.ContainsKey($row.waitReason)){$reasonCounts[$row.waitReason]=0};++$reasonCounts[$row.waitReason]}
        $row.pollWallMilliseconds=$watchClock.Elapsed.TotalMilliseconds-$pollStart
        $row.pollCPU100ns=$ownProcess.TotalProcessorTime.Ticks-$ownBefore
        $pollWall+=$row.pollWallMilliseconds;$pollCPU+=$row.pollCPU100ns
        $rendered=$row | ConvertTo-Json -Depth 4 -Compress
        $rowBytes=$encoding.GetByteCount($rendered)+[Environment]::NewLine.Length
        if($bytes+$rowBytes -gt $MaximumBytes){$status='byte_limit';break}
        $writer.WriteLine($rendered);$bytes+=$rowBytes;++$samples
        $nextAt=$captureStarted+$samples*$SampleMilliseconds
        $remaining=[Math]::Min($nextAt,$captureStarted+$DurationSeconds*1000)-$watchClock.Elapsed.TotalMilliseconds
        if($remaining -gt 0){Start-Sleep -Milliseconds ([int][Math]::Ceiling($remaining))}
    }
    if($status -eq 'sampling'){$status=if($samples -ge $MaximumSamples){'sample_limit'}else{'duration_complete'}}
    $binding.loadedDLLSHA256After=Get-SHA256 $dllFullPath
    if($binding.loadedDLLSHA256After -ne $dllSHA){throw 'DLL file identity changed during observation'}
}catch{
    $status='error';$failure=$_.Exception.Message
}finally{
    $captureFinished=$watchClock.Elapsed.TotalMilliseconds
    if($writer){$writer.Dispose()}
    $ownCPUFinished=$ownProcess.TotalProcessorTime.Ticks
    if($target){$target.Dispose()}
    $summary=[ordered]@{status=$status;error=$failure;binding=$binding;samples=$samples;bytes=$bytes;
        setupWallMilliseconds=$captureStarted;captureWallMilliseconds=$captureFinished-$captureStarted;
        helperTotalWallMilliseconds=$watchClock.Elapsed.TotalMilliseconds;helperTotalCPU100ns=$ownCPUFinished-$ownCPUStarted;
        pollWallMilliseconds=$pollWall;pollCPU100ns=$pollCPU;coreCPU100ns=if($null -ne $cpuFirst -and $null -ne $cpuLast){$cpuLast-$cpuFirst}else{$null};
        stateCounts=$stateCounts;waitReasonCounts=$reasonCounts;gameCalls=0;suspensions=0;attachments=0;
        limits='Read-only snapshots at sample timestamps, not exact duration totals. WaitReason is queried only for Wait state. Poll cost excludes serialization/write/sleep; total helper CPU includes them through final flush. Single native-thread creation binding; no engine-call or synchronization-object attribution.'}
    if($binding -or (Test-Path -LiteralPath $outputPath)){
        $summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
    }
    $ownProcess.Dispose()
    $summary | ConvertTo-Json -Depth 3 -Compress
}
if($status -eq 'error'){exit 2}
