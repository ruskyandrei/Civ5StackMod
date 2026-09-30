param(
    [string]$GameDirectory = "E:\SteamLibrary\steamapps\common\Sid Meier's Civilization V",
    [int]$TimeoutSeconds = 120
)
$ErrorActionPreference = 'Stop'
if (Get-Process CivilizationV,CivilizationV_DX11,CivilizationV_Tablet -ErrorAction SilentlyContinue) {
    throw 'Civ V is already running.'
}
if (-not (Get-Process steam -ErrorAction SilentlyContinue)) { throw 'Start and sign into Steam first.' }
$gameExe = Join-Path $GameDirectory 'CivilizationV_DX11.exe'
if (-not (Test-Path -LiteralPath $gameExe)) { throw 'DX11 executable not found.' }
$appidFile = Join-Path $GameDirectory 'steam_appid.txt'
$createdAppid = -not (Test-Path -LiteralPath $appidFile)
if (-not $createdAppid -and (Get-Content -LiteralPath $appidFile -Raw).Trim() -ne '8930') {
    throw 'Existing steam_appid.txt has an unexpected app ID; it was left untouched.'
}
try {
    # Standard Steam SDK development launch. Keep the file until Steam has
    # initialized; deleting it immediately lets Steam restart the DX9 default.
    if ($createdAppid) { [IO.File]::WriteAllText($appidFile, '8930') }
    $civProcess = Start-Process -FilePath $gameExe -ArgumentList '-DX11' -WorkingDirectory $GameDirectory -WindowStyle Hidden -PassThru
    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        $civProcess.Refresh()
        if ($civProcess.HasExited) { throw 'DX11 exited before its tuner became ready.' }
        $listen = Get-NetTCPConnection -State Listen -LocalPort 4318 -ErrorAction SilentlyContinue |
            Where-Object { $_.OwningProcess -eq $civProcess.Id }
        if ($listen) {
            [pscustomobject]@{ Ready=$true; Id=$civProcess.Id; StartTime=$civProcess.StartTime; Executable=$gameExe } | ConvertTo-Json -Compress
            return
        }
        Start-Sleep -Milliseconds 500
    }
    throw "Tuner was not ready within $TimeoutSeconds seconds; game PID $($civProcess.Id) was left running."
} finally {
    if ($createdAppid -and (Test-Path -LiteralPath $appidFile)) { Remove-Item -LiteralPath $appidFile }
}
