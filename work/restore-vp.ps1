<#
Restore the original pre-5.4.6 backup without deleting replacement content.
The current contents are moved to a fresh rollback archive before restoration.
Restores the ten VP mappings, initial config.ini, and initial cache if present.
Preserves current graphics/UserSettings unless -RestoreGamePreferences is explicit.
Does not restore or overwrite autosaves or any other saves; backup stays accessible.
Use -ValidateOnly for a read-only preflight. Requires the game to be closed.
#>
[CmdletBinding()]
param([switch]$ValidateOnly, [switch]$RestoreGamePreferences)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'vp-deployment-common.ps1')
Assert-SamePath $PSScriptRoot $script:WorkRoot
Assert-GameStopped
$initial = Get-InitialBackup
$entries = @($initial.Entries | Where-Object { $_.Restore -and ($RestoreGamePreferences -or ([IO.Path]::GetFileName($_.Source) -notin @('GraphicsSettingsDX11.ini','UserSettings.ini'))) })
$allowedTargets = @($entries | ForEach-Object Source)
$inventories = @{}
foreach ($entry in $entries) {
    if ($entry.Existed) { $inventories[$entry.Source] = @(Get-FileInventory $entry.Backup $entry.Kind) }
}
$autosaveBackup = @($initial.Entries | Where-Object { -not $_.Restore })[0].Backup
$preflight = [pscustomobject]@{InitialBackup=$initial.Root;RestoredPaths=$entries.Count;ExistingOriginalPaths=@($entries|Where-Object Existed).Count;SavesWillBeOverwritten=$false;GamePreferencesWillBeRestored=[bool]$RestoreGamePreferences;AutosaveBackup=$autosaveBackup}
if ($ValidateOnly) { $preflight | ConvertTo-Json -Depth 5; return }
Assert-GameStopped
$archive = New-RunArchive 'rollback-replaced'
Write-JsonFile (Join-Path $archive 'preflight.json') $preflight
Copy-Item -LiteralPath $initial.Manifest -Destination (Join-Path $archive 'initial-backup-manifest.json')
try {
    $restored = @()
    foreach ($entry in $entries) {
        Assert-GameStopped
        Move-KnownPathToArchive $entry.Source $entry.ArchiveRelative $allowedTargets
        if ($entry.Existed) {
            Copy-ValidatedPath $entry.Backup $entry.Source $entry.Kind $allowedTargets
            Assert-Inventory $entry.Source $entry.Kind $inventories[$entry.Source]
            $restored += [pscustomobject]@{Path=$entry.Source;State='restored_and_hash_verified';Files=$inventories[$entry.Source].Count}
        } else {
            if (Test-Path -LiteralPath $entry.Source) { throw "Originally absent path unexpectedly exists: $($entry.Source)" }
            $restored += [pscustomobject]@{Path=$entry.Source;State='originally_absent_current_content_archived';Files=0}
        }
    }
    Write-JsonFile (Join-Path $archive 'restored-paths.json') $restored
    $report = [pscustomobject]@{Status='restored_and_hash_verified';TimeUTC=[DateTime]::UtcNow.ToString('o');OriginalBackup=$initial.Root;ReplacementArchive=$archive;PathsRestored=$entries.Count;SavesTouched=$false;GamePreferencesRestored=[bool]$RestoreGamePreferences;AutosaveBackupAvailable=$autosaveBackup}
    Write-JsonFile (Join-Path $archive 'result.json') $report
    [IO.File]::WriteAllText((Join-Path $script:WorkRoot 'last-restore-path.txt'), $archive, (New-Object Text.UTF8Encoding($false)))
    Add-Journal 'completed' $initial.Root $archive
    $report | ConvertTo-Json -Depth 5
} catch {
    Add-Journal 'failed' $_.Exception.Message $archive
    Write-Error "Restore stopped. Initial backup remains untouched at $($initial.Root), and replaced content is in $archive. Inspect journal.json. Error: $($_.Exception.Message)"
    throw
}
