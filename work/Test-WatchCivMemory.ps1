$ErrorActionPreference='Stop'
$path=Join-Path $PSScriptRoot 'Watch-CivMemory.ps1'
$tokens=$null;$errors=$null;$ast=[Management.Automation.Language.Parser]::ParseFile($path,[ref]$tokens,[ref]$errors)
if($errors.Count){throw ($errors|Out-String)}
$names=@('Resolve-CivMemoryRunDirectory','Resolve-CivMemorySignal','Get-CivMemoryLimitReason')
$ast.FindAll({param($node)$node -is [Management.Automation.Language.FunctionDefinitionAst] -and $names -contains $node.Name},$true)|ForEach-Object {Invoke-Expression $_.Extent.Text}
$script:checks=0
function Check($ok,$name){$script:checks++;if(-not $ok){throw "FAIL $name"}}
function Reject($block,$name){$bad=$false;try{&$block|Out-Null}catch{$bad=$true};Check $bad $name}
$s=@{PrivateBytes=1GB;CommittedBytes=2GB;ReservedBytes=0;FreeBytes=1GB;LargestFreeBytes=64MB}
Check ($null -eq (Get-CivMemoryLimitReason $s 0 180)) 'safe baseline'
$s.PrivateBytes=[long](3.1GB);Check ((Get-CivMemoryLimitReason $s 0 180)-eq 'private_bytes_3.1GiB') 'private boundary'
$s.PrivateBytes--;Check ($null -eq (Get-CivMemoryLimitReason $s 0 180)) 'private just below'
$s.CommittedBytes=3GB;$s.ReservedBytes=512MB;Check ((Get-CivMemoryLimitReason $s 0 180)-eq 'commit_plus_reserve_3.5GiB') 'virtual boundary'
$s.ReservedBytes--;Check ($null -eq (Get-CivMemoryLimitReason $s 0 180)) 'virtual below'
$s.CommittedBytes=2GB;$s.ReservedBytes=0;$s.FreeBytes=256MB;Check ($null -eq (Get-CivMemoryLimitReason $s 0 180)) 'free equal safe'
$s.FreeBytes--;Check ((Get-CivMemoryLimitReason $s 0 180)-eq 'free_below_256MiB') 'free below'
$s.FreeBytes=1GB;$s.LargestFreeBytes=16MB;Check ($null -eq (Get-CivMemoryLimitReason $s 0 180)) 'largest equal safe'
$s.LargestFreeBytes--;Check ((Get-CivMemoryLimitReason $s 0 180)-eq 'largest_free_below_16MiB') 'largest below'
$s.LargestFreeBytes=64MB;Check ((Get-CivMemoryLimitReason $s 180 180)-eq 'maximum_duration') 'time boundary'
Check ($null -eq (Get-CivMemoryLimitReason $s 179.99 180)) 'before deadline'
Check ((Resolve-CivMemoryRunDirectory 'E:\Projects\Civ5StackMod\work\test-runs\memory-test') -like '*memory-test') 'valid output'
Reject {Resolve-CivMemoryRunDirectory 'E:\Projects\Civ5StackMod\work\test-runs-evil\x'} 'prefix sibling'
Reject {Resolve-CivMemoryRunDirectory 'E:\Projects\Civ5StackMod\work\test-runs\..\escape'} 'traversal'
Reject {Resolve-CivMemoryRunDirectory 'relative'} 'relative output'
Check ((Resolve-CivMemorySignal 'C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\memory-done.signal') -like '*memory-done.signal') 'valid signal'
Reject {Resolve-CivMemorySignal 'C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\nested\a.signal'} 'nested signal'
Reject {Resolve-CivMemorySignal 'C:\Users\rusit\Documents\Codex\Civ5StackMod-watchdog\bad.txt'} 'signal extension'
Check ($null -eq (Resolve-CivMemorySignal '')) 'signal optional'
$text=[IO.File]::ReadAllText($path)
$match=[regex]::Match($text,'(?s)\$nativeSource=@"\r?\n(.*?)\r?\n"@')
Check $match.Success 'native source extract'
Add-Type -TypeDefinition $match.Groups[1].Value
Check ([Runtime.InteropServices.Marshal]::SizeOf([type][CivMemoryWatch.Native+MBI64])-eq48) 'MBI64 native size'
Check ([Runtime.InteropServices.Marshal]::OffsetOf([type][CivMemoryWatch.Native+MBI64],'RegionSize').ToInt32()-eq24) 'RegionSize offset'
Check ([Runtime.InteropServices.Marshal]::OffsetOf([type][CivMemoryWatch.Native+MBI64],'State').ToInt32()-eq32) 'State offset'
# Reads only this test PowerShell's identity, never a game process. No stop method called.
Reject {[CivMemoryWatch.Native]::Read($PID,0,$true)} 'wrong creation and executable rejected'
$own=[Diagnostics.Process]::GetCurrentProcess()
Reject {[CivMemoryWatch.Native]::Read($PID,$own.StartTime.ToUniversalTime().Ticks,$true)} 'correct creation but non-game path rejected'
Check ($text.Contains('if ($StopOnLimit)')) 'stop requires explicit switch'
Check ($text.Contains('Open(pid,0x0410)')) 'read-only sampling rights'
Check ($text.Contains('Open(pid,0x0411);try{Verify(h,pid,ticks);Check(TerminateProcess')) 'termination verifies same held handle'
$result=@{checks=$checks;failures=0;sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash;scope='Pure thresholds/path tests, C# compile/layout, read-only identity rejection on this PowerShell process. No game sampled or stopped; native process stop never executed.'}
$out=Join-Path $PSScriptRoot 'memory-watch-regression';[void][IO.Directory]::CreateDirectory($out)
$result|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $out 'result.json') -Encoding UTF8
$result|ConvertTo-Json
