param(
 [Parameter(Mandatory=$true)][ValidateSet('baseline','main','sea-enabled','no-flanking','no-collateral','no-stacking','no-ai','defaults-restored')][string]$Profile,
 [int]$GameProcessId=0,
 [switch]$ValidateOnly
)
$ErrorActionPreference='Stop'
$taskRoot=[IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$profileRoot="C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5"
$stageRoot=Join-Path $taskRoot 'work\staging\vp-5.4.6-full-eui'
$expectedDLL='CC8F233774E4608EA3891471FA10E551DED25CBBE566393EF9A76F976B5621CC'
$prepared=Get-Content -LiteralPath (Join-Path $taskRoot 'work\xml-variation\manifest.json') -Raw | ConvertFrom-Json
$xmlRows=@()
$archiveSources=@()
foreach($kind in @('cp','vp')) {
 $entry=$prepared.files.$kind
 $expected=if($Profile -in @('baseline','defaults-restored')){$entry.baseline}else{$entry.profiles.$Profile}
 if(-not $expected){throw 'Missing expected XML profile hash'}
 $relative=[string]$entry.relative
 $paths=@{canonical=(Join-Path $taskRoot $relative);staged=(Join-Path $stageRoot ('user-data\MODS\'+$relative));installed=(Join-Path $profileRoot ('MODS\'+$relative))}
 foreach($location in @('canonical','staged','installed')) {
  $path=$paths[$location];$hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
  if($hash -ne $expected){throw "Wrong $kind XML at $location for profile $Profile"}
  $name="$location.$kind.xml";$archiveSources+=@{Path=$path;Name=$name}
  $xmlRows+=[PSCustomObject]@{Kind=$kind;Location=$location;Path=$path;SHA256=$hash;Expected=$expected}
 }
}
$dllPath=Join-Path $profileRoot 'MODS\(1) Community Patch\CvGameCore_Expansion2.dll'
if((Get-FileHash -LiteralPath $dllPath -Algorithm SHA256).Hash -ne $expectedDLL){throw 'Comparison DLL changed'}
$moduleProof=$null
if($GameProcessId -gt 0) {
 $game=Get-Process -Id $GameProcessId -ErrorAction Stop
 $exeRoot="E:\SteamLibrary\steamapps\common\Sid Meier's Civilization V"
 if($game.Path -notin @((Join-Path $exeRoot 'CivilizationV.exe'),(Join-Path $exeRoot 'CivilizationV_DX11.exe'))){throw 'Unexpected process executable'}
 $mods=@($game.Modules | Where-Object {$_.ModuleName -eq 'CvGameCore_Expansion2.dll'})
 if($mods.Count -ne 1 -or $mods[0].FileName -ne $dllPath){throw 'Expected installed CP DLL is not loaded'}
 $moduleProof=[PSCustomObject]@{PID=$game.Id;Executable=$game.Path;StartUTC=$game.StartTime.ToUniversalTime().ToString('o');ModulePath=$mods[0].FileName;BaseAddress=$mods[0].BaseAddress.ToInt64();Size=$mods[0].ModuleMemorySize;FileSHA256=$expectedDLL;Method='Read-only process module enumeration and on-disk module hash'}
}
if($ValidateOnly){[PSCustomObject]@{Status='validated_only_no_files_written';Profile=$Profile;XML=$xmlRows;DLL_SHA256=$expectedDLL;ModuleProof=$moduleProof}|ConvertTo-Json -Depth 7;return}
if($GameProcessId -le 0){throw 'Pass the exact running test PID to archive its loaded-module proof before closing'}
$stamp=[DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss')+'-'+[Guid]::NewGuid().ToString('N').Substring(0,8)
$out=Join-Path $taskRoot ('work\test-runs\xml-variation\'+$Profile+'-'+$stamp)
if(Test-Path -LiteralPath $out){throw 'Refusing to overwrite an archive'}
New-Item -ItemType Directory -Path $out | Out-Null
foreach($name in @('Lua.log','CustomMods.log','GameCore.log','Database.log')) {
 $path=Join-Path $profileRoot ('Logs\'+$name)
 if(Test-Path -LiteralPath $path){$archiveSources+=@{Path=$path;Name=$name}}
}
foreach($file in Get-ChildItem -LiteralPath (Join-Path $profileRoot 'MODS\(1) Community Patch\Core Files\Stacking') -Filter 'Stacking*.lua' -File){$archiveSources+=@{Path=$file.FullName;Name=('helper-'+$file.Name)}}
foreach($name in @('StackPanel.lua','StackPanel.xml')){$archiveSources+=@{Path=(Join-Path $profileRoot ('MODS\(3a) VP - EUI Compatibility Files\LUA\'+$name));Name=$name}}
$archiveSources+=@{Path=(Join-Path $stageRoot 'deploy-manifest.json');Name='stage-manifest.json'}
$files=@()
foreach($row in $archiveSources) {
 $dest=Join-Path $out $row.Name
 Copy-Item -LiteralPath $row.Path -Destination $dest
 $files+=[PSCustomObject]@{File=$row.Name;Source=$row.Path;Bytes=(Get-Item -LiteralPath $dest).Length;SHA256=(Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash}
}
$luaPath=Join-Path $out 'Lua.log'
if(Test-Path -LiteralPath $luaPath){@(Get-Content -LiteralPath $luaPath | Where-Object {$_ -match 'STACK(XML|TEST|MOVE|UI10)|Runtime Error|XML.*(true|false)'}) | Set-Content -LiteralPath (Join-Path $out 'XML-UI.filtered.log') -Encoding UTF8}
[PSCustomObject]@{Status='evidence_archived_not_an_automatic_test_pass';Profile=$Profile;RecordedUTC=[DateTime]::UtcNow.ToString('o');DLL_SHA256=$expectedDLL;XML=$xmlRows;ModuleProof=$moduleProof;Files=$files;Limits='Snapshot before close; add screenshots and explicit pass/fail scenario readout. Profile/hash equality alone does not prove runtime behavior.'}|ConvertTo-Json -Depth 8|Set-Content -LiteralPath (Join-Path $out 'archive.json') -Encoding UTF8
@"
# XML run evidence: $Profile

Exact canonical/staged/installed XML profile hashes and unchanged030606 DLL were checked. The loaded CP module is recorded for PID$GameProcessId. Full logs, filtered diagnostic lines and exact installed manual/UI helpers are preserved.

This archive does not assign mechanic passes automatically. Add scenario outcomes, preserved fixture failures, screenshots for rendered UI claims, and unrun cases. Do not combine assertion counts from independent runs. Close normally only after this archive succeeds; preserve any additional post-close CSV/log flush separately before the next launch.
"@ | Set-Content -LiteralPath (Join-Path $out 'README.md') -Encoding UTF8
[PSCustomObject]@{Status='archived';Profile=$Profile;Path=$out;Files=$files.Count;DLL_SHA256=$expectedDLL}|ConvertTo-Json
