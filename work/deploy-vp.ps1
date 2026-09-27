<#
Deploy staged VP 5.4.6 FullEUI after verifying hashes and the initial backup.
Must run with the game closed and adequate permissions for both installation roots.
All replaced content is moved to a new project archive; no recursive deletes occur.
Use -ValidateOnly for a read-only preflight. This script never touches saves.
#>
[CmdletBinding()]
param([switch]$ValidateOnly)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'vp-deployment-common.ps1')
Assert-SamePath $PSScriptRoot $script:WorkRoot
Assert-GameStopped
$initial = Get-InitialBackup
$stage = Get-ValidatedStage
$configEdit = Get-ConfigEdit
$protectedSettings = @{}
foreach ($name in @('GraphicsSettingsDX11.ini','UserSettings.ini')) {
    $path = Join-Path $script:UserDataRoot $name
    if (Test-Path -LiteralPath $path -PathType Leaf) { $protectedSettings[$path]=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
}
$allowedTargets = @($stage.Mappings | ForEach-Object destination)
$cachePath = Join-Path $script:UserDataRoot 'cache'
$allowedTargets += $cachePath
$allowedTargets += $configEdit.Path
Assert-NoReparsePoints $cachePath -Tree
$preflight = [pscustomobject]@{Stage=$script:StageRoot;InitialBackup=$initial.Root;Files=$stage.Files.Count;Mappings=$stage.Mappings.Count;DLL=$stage.DLL.SHA256;PDB=$stage.PDB.SHA256;LoggingFlags=$script:LoggingFlags}
if ($ValidateOnly) { $preflight | ConvertTo-Json -Depth 5; return }
Assert-GameStopped
$archive = New-RunArchive 'deployment-replaced'
Write-JsonFile (Join-Path $archive 'preflight.json') $preflight
Copy-Item -LiteralPath $stage.ManifestPath -Destination (Join-Path $archive 'stage-manifest.json')
Copy-Item -LiteralPath $initial.Manifest -Destination (Join-Path $archive 'initial-backup-manifest.json')
try {
    foreach ($mapping in $stage.Mappings) {
        Assert-GameStopped
        $source = Resolve-SafeRelative $script:StageRoot $mapping.source_relative
        Move-KnownPathToArchive $mapping.destination $mapping.source_relative $allowedTargets
        Copy-ValidatedPath $source $mapping.destination $mapping.kind $allowedTargets
    }
    # Cache is reproducible. Preserve it in the archive so it can be inspected.
    Move-KnownPathToArchive $cachePath 'user-data/cache' $allowedTargets
    # Preserve the immediate pre-deployment config as well as the initial backup.
    if ((Get-FileHash -LiteralPath $configEdit.Path -Algorithm SHA256).Hash -ne $configEdit.OriginalSHA256) { throw 'config.ini changed during deployment; refusing to overwrite it.' }
    $configBackup = Resolve-SafeRelative $archive 'replaced/user-data/config.ini'
    $null = New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($configBackup)) -Force
    Copy-Item -LiteralPath $configEdit.Path -Destination $configBackup -ErrorAction Stop
    Add-Journal 'config_backup' $configEdit.Path $configBackup
    [IO.File]::WriteAllBytes($configEdit.Path, $configEdit.Bytes)
    Add-Journal 'enabled_test_logging' $configEdit.Path ($script:LoggingFlags -join ',')
    Assert-GameStopped
    $installedRecords = @()
    foreach ($file in $stage.Files) {
        Assert-NoReparsePoints $file.Destination
        if (-not (Test-Path -LiteralPath $file.Destination -PathType Leaf)) { throw "Installed file missing: $($file.Destination)" }
        $hash = (Get-FileHash -LiteralPath $file.Destination -Algorithm SHA256).Hash
        if ($hash -ne $file.SHA256) { throw "Installed SHA256 mismatch: $($file.Destination)" }
        $installedRecords += [pscustomobject]@{Path=$file.Destination;SHA256=$hash;Bytes=(Get-Item -LiteralPath $file.Destination).Length}
    }
    # Check for stale files as well as matching expected hashes in the seven folders.
    foreach ($mapping in $stage.Mappings | Where-Object kind -eq 'directory') {
        $wanted = @($stage.Files | Where-Object { $_.Relative.StartsWith($mapping.source_relative+'/',[StringComparison]::OrdinalIgnoreCase) })
        $actual = @(Get-ChildItem -LiteralPath $mapping.destination -File -Recurse -Force)
        if ($wanted.Count -ne $actual.Count) { throw "Unexpected installed file count: $($mapping.destination)" }
    }
    foreach ($path in $protectedSettings.Keys) {
        if ((Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $protectedSettings[$path]) { throw "Protected settings changed unexpectedly: $path" }
    }
    $configText = [IO.File]::ReadAllText($configEdit.Path)
    foreach ($flag in $script:LoggingFlags) {
        if (-not [regex]::IsMatch($configText, '(?m)^'+[regex]::Escape($flag)+'[ \t]*=[ \t]*1[ \t]*\r?$')) { throw "Logging setting verification failed: $flag" }
    }
    Write-JsonFile (Join-Path $archive 'installed-files.json') $installedRecords
    $report = [pscustomobject]@{Status='deployed_and_hash_verified';TimeUTC=[DateTime]::UtcNow.ToString('o');Version='5.4.6';Files=$installedRecords.Count;DLL_SHA256=$stage.DLL.SHA256;PDB_SHA256=$stage.PDB.SHA256;ReplacementArchive=$archive;InitialBackup=$initial.Root;GraphicsSettingsUnchanged=$true;SavesTouched=$false;KnownUpstreamMissingActions=$stage.Manifest.known_upstream_missing_actions_preserved}
    Write-JsonFile (Join-Path $archive 'result.json') $report
    [IO.File]::WriteAllText((Join-Path $script:WorkRoot 'last-deployment-path.txt'), $archive, (New-Object Text.UTF8Encoding($false)))
    Add-Journal 'completed' $script:StageRoot $archive
    $report | ConvertTo-Json -Depth 6
} catch {
    Add-Journal 'failed' $_.Exception.Message $archive
    Write-Error "Deployment stopped. Current and replaced files are preserved; initial backup remains at $($initial.Root). Inspect $archive\journal.json and use restore-vp.ps1 to restore the baseline. Error: $($_.Exception.Message)"
    throw
}
