<#
Installs the Civ V Stack Mod (Vox Populi with unit stacking, EUI version).

Replaces any existing Vox Populi installation. Everything that is replaced is
first moved to a backup folder next to your Civ V user data, so nothing is
deleted. Saves are not touched.

  Install.cmd                         normal installation
  Install.ps1 -DryRun                 show what would happen, change nothing
  Install.ps1 -GameDirectory "D:\Games\Sid Meier's Civilization V"
  Install.ps1 -UserDirectory "D:\Documents\My Games\Sid Meier's Civilization 5"
#>
[CmdletBinding()]
param([string]$GameDirectory, [string]$UserDirectory, [switch]$DryRun)
$ErrorActionPreference = 'Stop'
$package = $PSScriptRoot
$userPayload = Join-Path $package 'UserData'
$gamePayload = Join-Path $package 'Game'
if (-not (Test-Path -LiteralPath (Join-Path $userPayload 'MODS\(1) Community Patch\CvGameCore_Expansion2.dll'))) {
    throw 'Package files are missing. Extract the whole zip before running the installer.'
}
if (Get-Process CivilizationV, CivilizationV_DX11, CivilizationV_Tablet -ErrorAction SilentlyContinue) {
    throw 'Close Civilization V before installing.'
}

# Asks for a folder until it contains $marker; returns $null when cancelled or no dialog can be shown.
function Select-Folder([string]$Description, [string]$Marker) {
    if (-not [Environment]::UserInteractive) { return $null }
    try { Add-Type -AssemblyName System.Windows.Forms } catch { return $null }
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = $Description
    $dialog.ShowNewFolderButton = $false
    while ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) {
        if (Test-Path -LiteralPath (Join-Path $dialog.SelectedPath $Marker)) { return $dialog.SelectedPath }
        $null = [System.Windows.Forms.MessageBox]::Show("That folder does not contain $Marker. Choose another folder, or Cancel to stop.", 'Civ V Stack Mod')
    }
    return $null
}

$userGiven = [bool]$UserDirectory
if (-not $UserDirectory) {
    $UserDirectory = Join-Path ([Environment]::GetFolderPath('MyDocuments')) "My Games\Sid Meier's Civilization 5"
}
if (-not (Test-Path -LiteralPath (Join-Path $UserDirectory 'config.ini'))) {
    $picked = if (-not $userGiven) { Select-Folder "Select your Civ V user data folder (Documents\My Games\Sid Meier's Civilization 5). It contains config.ini." 'config.ini' }
    if (-not $picked) {
        throw "Civ V user data was not found at '$UserDirectory'. Start the game once, or pass -UserDirectory with the folder that contains config.ini."
    }
    $UserDirectory = $picked
}

if (-not $GameDirectory) {
    foreach ($key in 'HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 8930',
                     'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Steam App 8930') {
        $value = (Get-ItemProperty -LiteralPath $key -ErrorAction SilentlyContinue).InstallLocation
        if ($value -and (Test-Path -LiteralPath $value)) { $GameDirectory = $value; break }
    }
}
if (-not $GameDirectory) {
    Write-Host 'The Civ V installation was not found automatically; choose its folder in the dialog.'
    $GameDirectory = Select-Folder 'Select the Civilization V game folder. It contains CivilizationV.exe.' 'CivilizationV.exe'
}
if (-not $GameDirectory -or -not (Test-Path -LiteralPath (Join-Path $GameDirectory 'CivilizationV.exe'))) {
    throw 'The Civ V installation was not found. Pass -GameDirectory with the folder that contains CivilizationV.exe.'
}
if (-not (Test-Path -LiteralPath (Join-Path $GameDirectory 'Assets\DLC\Expansion2'))) {
    throw 'Brave New World (Expansion2) is required and was not found in the game folder.'
}

$backup = Join-Path $UserDirectory ('StackMod-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$mods = '(1) Community Patch', '(2) Vox Populi', '(3a) VP - EUI Compatibility Files', '(3b) 43 Civs Community Patch',
        '(4a) Squads for VP', '(5) Modpack Maker for VP', '(2) Community Balance Patch', '(2) Community Balance Overhaul',
        '(3) CSD for VP', '(3) CSD for CBP'
# Existing path -> where it goes inside the backup folder.
$replace = [ordered]@{}
foreach ($name in $mods) { $replace[(Join-Path $UserDirectory "MODS\$name")] = "UserData\MODS\$name" }
$replace[(Join-Path $UserDirectory 'Text\VPUI_tips_en_us.xml')] = 'UserData\Text\VPUI_tips_en_us.xml'
$replace[(Join-Path $UserDirectory 'cache')] = 'UserData\cache'
$replace[(Join-Path $GameDirectory 'Assets\DLC\UI_bc1')] = 'Game\Assets\DLC\UI_bc1'
$replace[(Join-Path $GameDirectory 'Assets\DLC\VPUI')] = 'Game\Assets\DLC\VPUI'
$replace[(Join-Path $GameDirectory 'Assets\DLC\Expansion2\Expansion2.Civ5Pkg')] = 'Game\Assets\DLC\Expansion2\Expansion2.Civ5Pkg'
$replace[(Join-Path $GameDirectory 'Assets\DLC\Expansion2\Sounds\XML\MinorCivSounds_VoxPopuli.xml')] = 'Game\Assets\DLC\Expansion2\Sounds\XML\MinorCivSounds_VoxPopuli.xml'

Write-Host "User data : $UserDirectory"
Write-Host "Game      : $GameDirectory"
Write-Host "Backup    : $backup"
if ($DryRun) { Write-Host 'Dry run: nothing will be changed.' }

try {
    foreach ($source in $replace.Keys) {
        if (-not (Test-Path -LiteralPath $source)) { continue }
        $target = Join-Path $backup $replace[$source]
        Write-Host "  backup  $source"
        if ($DryRun) { continue }
        $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target)
        if ([IO.Path]::GetPathRoot($source) -eq [IO.Path]::GetPathRoot($target)) {
            Move-Item -LiteralPath $source -Destination $target
        } else {
            Copy-Item -LiteralPath $source -Destination $target -Recurse
            Remove-Item -LiteralPath $source -Recurse -Force
        }
    }
    foreach ($pair in @(@($userPayload, $UserDirectory), @($gamePayload, $GameDirectory))) {
        Write-Host "  install $($pair[1])"
        if ($DryRun) { continue }
        Copy-Item -Path (Join-Path $pair[0] '*') -Destination $pair[1] -Recurse -Force
    }
} catch [UnauthorizedAccessException] {
    throw "Access denied: $($_.Exception.Message) If the game is under Program Files, right-click Install.cmd and choose 'Run as administrator'. Files already moved are in $backup."
}

if ($DryRun) { Write-Host 'Dry run finished.'; return }
Write-Host ''
Write-Host 'Installed. Start Civ V, open MODS, enable these four and click Next:'
Write-Host '  (1) Community Patch, (2) Vox Populi, (3a) VP - EUI Compatibility Files, (4a) Squads for VP'
Write-Host "Replaced files are kept in: $backup"
