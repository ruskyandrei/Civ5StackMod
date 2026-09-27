# Shared path checks and file handling for the VP deployment/restore scripts.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:ProjectRoot = [IO.Path]::GetFullPath('E:\Projects\Civ5StackMod')
$script:WorkRoot = Join-Path $script:ProjectRoot 'work'
$script:StageRoot = Join-Path $script:WorkRoot 'staging\vp-5.4.6-full-eui'
$script:UserDataRoot = "C:\Users\rusit\Documents\My Games\Sid Meier's Civilization 5"
$script:GameRoot = "E:\SteamLibrary\steamapps\common\Sid Meier's Civilization V"
$script:ModNames = @('(1) Community Patch','(2) Vox Populi','(3a) VP - EUI Compatibility Files','(4a) Squads for VP','(5) Modpack Maker for VP')
$script:LoggingFlags = @('ValidateGameDatabase','LoggingEnabled','MessageLog','AILog','AIPerfLog','BuilderAILog','PlayerAndCityAILogSplit')

function Get-CanonicalPath([string]$Path) {
    if (-not [IO.Path]::IsPathRooted($Path)) { throw "Absolute path required: $Path" }
    return [IO.Path]::GetFullPath($Path).TrimEnd('\','/')
}
function Assert-SamePath([string]$Actual, [string]$Expected) {
    if (-not [string]::Equals((Get-CanonicalPath $Actual), (Get-CanonicalPath $Expected), [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unexpected path '$Actual'; only '$Expected' is allowed."
    }
}
function Assert-UnderPath([string]$Path, [string]$Root) {
    $full = Get-CanonicalPath $Path
    $parent = (Get-CanonicalPath $Root) + '\'
    if (-not $full.StartsWith($parent, [StringComparison]::OrdinalIgnoreCase)) { throw "Path escapes expected parent: $Path" }
    return $full
}
function Resolve-SafeRelative([string]$Root, [string]$Relative) {
    if ([IO.Path]::IsPathRooted($Relative) -or $Relative -match '(^|[\\/])\.\.?([\\/]|$)') { throw "Unsafe relative path: $Relative" }
    return Assert-UnderPath (Join-Path $Root ($Relative.Replace('/','\'))) $Root
}
function Assert-NoReparsePoints([string]$Path, [switch]$Tree) {
    $current = Get-CanonicalPath $Path
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            $item = Get-Item -LiteralPath $current -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point refused: $current" }
        }
        $parent = [IO.Path]::GetDirectoryName($current)
        if (-not $parent -or $parent -eq $current) { break }
        $current = $parent
    }
    if ($Tree -and (Test-Path -LiteralPath $Path -PathType Container)) {
        foreach ($item in Get-ChildItem -LiteralPath $Path -Recurse -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Reparse point refused: $($item.FullName)" }
        }
    }
}
function Assert-GameStopped {
    $running = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^Civilization(V|5)(_|$)' })
    if ($running.Count) { throw "Close Civilization V before continuing. Running process IDs: $($running.Id -join ', ')" }
}
function Get-ExpectedMappings {
    $result = @()
    foreach ($name in $script:ModNames) {
        $result += [pscustomobject]@{ source_relative="user-data/MODS/$name"; destination=(Join-Path $script:UserDataRoot "MODS\$name"); kind='directory'; backup_relative="MODS/$name" }
    }
    foreach ($name in @('UI_bc1','VPUI')) {
        $result += [pscustomobject]@{ source_relative="game/Assets/DLC/$name"; destination=(Join-Path $script:GameRoot "Assets\DLC\$name"); kind='directory'; backup_relative="DLC/$name" }
    }
    $result += [pscustomobject]@{source_relative='user-data/Text/VPUI_tips_en_us.xml';destination=(Join-Path $script:UserDataRoot 'Text\VPUI_tips_en_us.xml');kind='file';backup_relative='UserData/Text/VPUI_tips_en_us.xml'}
    $result += [pscustomobject]@{source_relative='game/Assets/DLC/Expansion2/Expansion2.Civ5Pkg';destination=(Join-Path $script:GameRoot 'Assets\DLC\Expansion2\Expansion2.Civ5Pkg');kind='file';backup_relative='Expansion2/Expansion2.Civ5Pkg'}
    $result += [pscustomobject]@{source_relative='game/Assets/DLC/Expansion2/Sounds/XML/MinorCivSounds_VoxPopuli.xml';destination=(Join-Path $script:GameRoot 'Assets\DLC\Expansion2\Sounds\XML\MinorCivSounds_VoxPopuli.xml');kind='file';backup_relative='Expansion2/Sounds/XML/MinorCivSounds_VoxPopuli.xml'}
    return $result
}
function Get-ExpectedBackupEntries {
    $entries = @()
    foreach ($mapping in Get-ExpectedMappings) {
        $entries += [pscustomobject]@{ Source=$mapping.destination; Relative=$mapping.backup_relative; Kind=$mapping.kind; ArchiveRelative=$mapping.source_relative; Restore=$true }
    }
    foreach ($name in @('config.ini','GraphicsSettingsDX11.ini','UserSettings.ini')) {
        $entries += [pscustomobject]@{Source=(Join-Path $script:UserDataRoot $name);Relative="UserData/$name";Kind='file';ArchiveRelative="user-data/$name";Restore=$true}
    }
    $entries += [pscustomobject]@{Source=(Join-Path $script:UserDataRoot 'cache');Relative='UserData/cache';Kind='directory';ArchiveRelative='user-data/cache';Restore=$true}
    $entries += [pscustomobject]@{Source=(Join-Path $script:UserDataRoot 'Saves\single\auto');Relative='UserData/Saves/single/auto';Kind='directory';ArchiveRelative='user-data/Saves/single/auto';Restore=$false}
    return $entries
}
function Get-InitialBackup {
    $pathFile = Join-Path $script:WorkRoot 'backup-path.txt'
    $path = Get-CanonicalPath ([IO.File]::ReadAllText($pathFile).Trim())
    $null = Assert-UnderPath $path (Join-Path $script:WorkRoot 'backups')
    if ([IO.Path]::GetFileName($path) -notlike 'before-vp-5.4.6-*') { throw 'Initial backup directory name was not recognized.' }
    Assert-NoReparsePoints $path -Tree
    $manifestPath = Join-Path $path 'manifest.json'
    $manifest = @(Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json)
    $expected = @(Get-ExpectedBackupEntries)
    if ($manifest.Count -ne $expected.Count) { throw 'Initial backup manifest has unexpected entry count.' }
    $resolved = @()
    foreach ($entry in $expected) {
        $matches = @($manifest | Where-Object { [string]::Equals($_.Source, $entry.Source, [StringComparison]::OrdinalIgnoreCase) })
        if ($matches.Count -ne 1) { throw "Missing or duplicate backup entry: $($entry.Source)" }
        $actual = $matches[0]
        $expectedBackup = Resolve-SafeRelative $path $entry.Relative
        Assert-SamePath $actual.Backup $expectedBackup
        if ($actual.Existed -isnot [bool]) { throw "Invalid Existed flag: $($entry.Source)" }
        if ($actual.Existed) {
            $type = if ($entry.Kind -eq 'directory') { 'Container' } else { 'Leaf' }
            if (-not (Test-Path -LiteralPath $expectedBackup -PathType $type)) { throw "Missing initial backup: $expectedBackup" }
        }
        Assert-NoReparsePoints $entry.Source -Tree
        $resolved += [pscustomobject]@{Source=$entry.Source;Backup=$expectedBackup;Existed=$actual.Existed;Kind=$entry.Kind;ArchiveRelative=$entry.ArchiveRelative;Restore=$entry.Restore}
    }
    return [pscustomobject]@{Root=$path;Manifest=$manifestPath;Entries=$resolved}
}
function Get-StageFileDestination([string]$Relative, [object[]]$Mappings) {
    $matches = @($Mappings | Where-Object {
        $Relative -eq $_.source_relative -or ($_.kind -eq 'directory' -and $Relative.StartsWith($_.source_relative+'/', [StringComparison]::OrdinalIgnoreCase))
    })
    if ($matches.Count -ne 1) { throw "Payload file is not covered by one exact mapping: $Relative" }
    $mapping = $matches[0]
    if ($mapping.kind -eq 'file') { return Get-CanonicalPath $mapping.destination }
    $suffix = $Relative.Substring($mapping.source_relative.Length + 1)
    return Resolve-SafeRelative $mapping.destination $suffix
}
function Get-ValidatedStage {
    Assert-SamePath $PSScriptRoot $script:WorkRoot
    Assert-NoReparsePoints $script:StageRoot -Tree
    $path = Join-Path $script:StageRoot 'deploy-manifest.json'
    $manifest = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    if ($manifest.schema -ne 1 -or $manifest.version -ne '5.4.6' -or $manifest.component -ne 'FullEUI') { throw 'Wrong staging manifest version/component.' }
    if ($manifest.source_commit -notmatch '^[A-Fa-f0-9]{40}$') { throw 'Invalid staging source commit.' }
    # Local implementation checkpoints must retain the verified upstream release.
    & git -C $script:ProjectRoot merge-base --is-ancestor dcb33a654cd9e8efb038a0733b4025e19cbcd8ba $manifest.source_commit
    if ($LASTEXITCODE -ne 0) { throw 'Staged source is not a descendant of the verified VP 5.4.6 release.' }
    & git -C $script:ProjectRoot merge-base --is-ancestor $manifest.source_commit HEAD
    if ($LASTEXITCODE -ne 0) { throw 'Staged source is not part of the current project history.' }
    Assert-SamePath $manifest.stage_root $script:StageRoot
    $expected = @(Get-ExpectedMappings)
    if (@($manifest.mappings).Count -ne $expected.Count) { throw 'Staging mappings count mismatch.' }
    foreach ($mapping in $expected) {
        $matches = @($manifest.mappings | Where-Object { $_.source_relative -eq $mapping.source_relative })
        if ($matches.Count -ne 1 -or $matches[0].kind -ne $mapping.kind) { throw "Unexpected staging mapping: $($mapping.source_relative)" }
        Assert-SamePath $matches[0].destination $mapping.destination
        $source = Resolve-SafeRelative $script:StageRoot $mapping.source_relative
        $type = if ($mapping.kind -eq 'directory') { 'Container' } else { 'Leaf' }
        if (-not (Test-Path -LiteralPath $source -PathType $type)) { throw "Missing staged path: $source" }
        Assert-NoReparsePoints $mapping.destination -Tree
    }
    $seen = @{}
    $files = @()
    foreach ($file in $manifest.files) {
        $source = Resolve-SafeRelative $script:StageRoot $file.staged_path
        if ($seen.ContainsKey($source)) { throw "Duplicate staged file: $source" }
        $seen[$source] = $true
        if ($file.sha256 -notmatch '^[A-Fa-f0-9]{64}$') { throw "Invalid SHA256 entry: $source" }
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Missing staged file: $source" }
        if ((Get-Item -LiteralPath $source).Length -ne $file.bytes) { throw "Staged file size mismatch: $source" }
        if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -ne $file.sha256) { throw "Staged SHA256 mismatch: $source" }
        $destination = Get-StageFileDestination $file.staged_path $expected
        $files += [pscustomobject]@{Source=$source;Destination=$destination;Relative=$file.staged_path;SHA256=$file.sha256;Bytes=$file.bytes;Provenance=$file.source}
    }
    foreach ($name in @('user-data','game')) {
        foreach ($file in Get-ChildItem -LiteralPath (Join-Path $script:StageRoot $name) -Recurse -File -Force) {
            if (-not $seen.ContainsKey($file.FullName)) { throw "Unlisted extra staged file: $($file.FullName)" }
        }
    }
    $dll = @($files | Where-Object Relative -eq 'user-data/MODS/(1) Community Patch/CvGameCore_Expansion2.dll')
    $pdb = @($files | Where-Object Relative -eq 'user-data/MODS/(1) Community Patch/CvGameCore_Expansion2.pdb')
    if ($dll.Count -ne 1 -or $pdb.Count -ne 1) { throw 'Stage the locally built DLL and matching PDB before deployment: stage_vp.py --dll <DLL> --pdb <PDB>.' }
    Assert-SamePath ([IO.Path]::GetDirectoryName($dll[0].Provenance)) ([IO.Path]::GetDirectoryName($pdb[0].Provenance))
    $null = Assert-UnderPath $dll[0].Provenance $script:ProjectRoot
    if ($dll[0].Provenance -like '*\(1) Community Patch\*') { throw 'Staging still uses the upstream packaged DLL, not the local build.' }
    if ($manifest.dll.sha256 -ne $dll[0].SHA256) { throw 'DLL provenance metadata mismatch.' }
    [xml]$modinfo = Get-Content -LiteralPath (Join-Path $script:StageRoot 'user-data\MODS\(1) Community Patch\(1) Community Patch (v 151).modinfo') -Raw
    $dllNode = @($modinfo.Mod.Files.File | Where-Object InnerText -eq 'CvGameCore_Expansion2.dll')
    if ($dllNode.Count -ne 1 -or $dllNode[0].md5 -ne (Get-FileHash -LiteralPath $dll[0].Source -Algorithm MD5).Hash) { throw 'Staged DLL modinfo MD5 is wrong.' }
    return [pscustomobject]@{Manifest=$manifest;ManifestPath=$path;Mappings=$expected;Files=$files;DLL=$dll[0];PDB=$pdb[0]}
}
function Write-JsonFile([string]$Path, $Data) {
    [IO.File]::WriteAllText($Path, ($Data | ConvertTo-Json -Depth 20), (New-Object Text.UTF8Encoding($false)))
}
function New-RunArchive([string]$Prefix) {
    $parent = Join-Path $script:WorkRoot 'backups'
    $path = Join-Path $parent ($Prefix+'-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+[guid]::NewGuid().ToString('N').Substring(0,8))
    $null = Assert-UnderPath $path $parent
    Assert-NoReparsePoints $parent
    if (Test-Path -LiteralPath $path) { throw "Archive already exists: $path" }
    $null = New-Item -ItemType Directory -Path $path
    $script:RunArchive = $path
    $script:Journal = New-Object System.Collections.Generic.List[object]
    Add-Journal 'created' $path ''
    return $path
}
function Add-Journal([string]$Action, [string]$Source, [string]$Destination) {
    $script:Journal.Add([pscustomobject]@{TimeUTC=[DateTime]::UtcNow.ToString('o');Action=$Action;Source=$Source;Destination=$Destination})
    Write-JsonFile (Join-Path $script:RunArchive 'journal.json') @($script:Journal.ToArray())
}
function Move-KnownPathToArchive([string]$Source, [string]$Relative, [string[]]$AllowedTargets) {
    $full = Get-CanonicalPath $Source
    if (-not ($AllowedTargets | Where-Object { [string]::Equals((Get-CanonicalPath $_),$full,[StringComparison]::OrdinalIgnoreCase) })) { throw "Refusing unlisted move source: $Source" }
    $destination = Resolve-SafeRelative $script:RunArchive ('replaced/'+$Relative)
    Assert-NoReparsePoints $full -Tree
    Assert-NoReparsePoints $destination
    if (-not (Test-Path -LiteralPath $full)) { Add-Journal 'was_absent' $full $destination; return }
    if (Test-Path -LiteralPath $destination) { throw "Move target already exists: $destination" }
    $null = New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($destination)) -Force
    $item = Get-Item -LiteralPath $full -Force
    Add-Journal 'move_started' $full $destination
    if (-not $item.PSIsContainer -or [IO.Path]::GetPathRoot($full) -eq [IO.Path]::GetPathRoot($destination)) {
        Move-Item -LiteralPath $full -Destination $destination -ErrorAction Stop
    } else {
        # PowerShell cannot move a whole directory across volumes. Move its files
        # with native Move-Item, then remove only empty directories, never recursively.
        $directories = @(Get-ChildItem -LiteralPath $full -Directory -Recurse -Force)
        $fileList = @(Get-ChildItem -LiteralPath $full -File -Recurse -Force)
        $null = New-Item -ItemType Directory -Path $destination
        foreach ($directory in $directories) {
            $null = Assert-UnderPath $directory.FullName $full
            $suffix = $directory.FullName.Substring($full.Length+1)
            $target = Resolve-SafeRelative $destination $suffix
            $null = New-Item -ItemType Directory -Path $target -Force
        }
        foreach ($file in $fileList) {
            $null = Assert-UnderPath $file.FullName $full
            $suffix = $file.FullName.Substring($full.Length+1)
            $target = Resolve-SafeRelative $destination $suffix
            Move-Item -LiteralPath $file.FullName -Destination $target -ErrorAction Stop
        }
        foreach ($directory in ($directories | Sort-Object { $_.FullName.Length } -Descending)) {
            $null = Assert-UnderPath $directory.FullName $full
            # false guarantees a concurrently added file prevents deletion.
            [IO.Directory]::Delete($directory.FullName, $false)
        }
        Assert-SamePath $full $Source
        [IO.Directory]::Delete($full, $false)
    }
    Add-Journal 'move_completed' $full $destination
}
function Copy-ValidatedPath([string]$Source, [string]$Destination, [string]$Kind, [string[]]$AllowedTargets) {
    if (-not ($AllowedTargets | Where-Object { [string]::Equals((Get-CanonicalPath $_),(Get-CanonicalPath $Destination),[StringComparison]::OrdinalIgnoreCase) })) { throw "Refusing unlisted copy target: $Destination" }
    Assert-NoReparsePoints $Source -Tree
    Assert-NoReparsePoints $Destination
    if (Test-Path -LiteralPath $Destination) { throw "Copy target must be absent: $Destination" }
    $null = New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($Destination)) -Force
    if ($Kind -eq 'directory') { Copy-Item -LiteralPath $Source -Destination $Destination -Recurse -Force -ErrorAction Stop }
    else { Copy-Item -LiteralPath $Source -Destination $Destination -Force -ErrorAction Stop }
    Add-Journal 'copy_completed' $Source $Destination
}
function Get-FileInventory([string]$Path, [string]$Kind) {
    if ($Kind -eq 'file') { return ,([pscustomobject]@{Relative='';SHA256=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash}) }
    $full = Get-CanonicalPath $Path
    $result = @()
    foreach ($file in Get-ChildItem -LiteralPath $full -File -Recurse -Force) {
        $result += [pscustomobject]@{Relative=$file.FullName.Substring($full.Length+1);SHA256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash}
    }
    return $result
}
function Assert-Inventory([string]$Path, [string]$Kind, [object[]]$Inventory) {
    $actual = @(Get-FileInventory $Path $Kind)
    if ($actual.Count -ne $Inventory.Count) { throw "File count differs after copy: $Path" }
    $lookup = @{}
    foreach ($file in $actual) { $lookup[$file.Relative] = $file.SHA256 }
    foreach ($file in $Inventory) {
        if (-not $lookup.ContainsKey($file.Relative) -or $lookup[$file.Relative] -ne $file.SHA256) { throw "Copied file hash differs: $Path\$($file.Relative)" }
    }
}
function Get-ConfigEdit {
    $path = Join-Path $script:UserDataRoot 'config.ini'
    $bytes = [IO.File]::ReadAllBytes($path)
    $offset = 0
    $encoding = New-Object Text.UTF8Encoding($false, $true)
    $preamble = [byte[]]@()
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 239 -and $bytes[1] -eq 187 -and $bytes[2] -eq 191) { $offset=3; $preamble=[byte[]]@(239,187,191) }
    elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 255 -and $bytes[1] -eq 254) { $offset=2; $encoding=[Text.Encoding]::Unicode; $preamble=[byte[]]@(255,254) }
    elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 254 -and $bytes[1] -eq 255) { $offset=2; $encoding=[Text.Encoding]::BigEndianUnicode; $preamble=[byte[]]@(254,255) }
    try { $text = $encoding.GetString($bytes,$offset,$bytes.Length-$offset) }
    catch { $encoding=[Text.Encoding]::GetEncoding(1252); $text=$encoding.GetString($bytes); $preamble=[byte[]]@() }
    foreach ($flag in $script:LoggingFlags) {
        $pattern = '(?m)^('+[regex]::Escape($flag)+'[ \t]*=[ \t]*)[01]([ \t]*\r?)$'
        if ([regex]::Matches($text,$pattern).Count -ne 1) { throw "Expected exactly one boolean config setting: $flag" }
        $text = [regex]::Replace($text,$pattern,'${1}1${2}')
    }
    $newBytes = [byte[]]($preamble + $encoding.GetBytes($text))
    return [pscustomobject]@{Path=$path;OriginalSHA256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash;Bytes=$newBytes}
}
