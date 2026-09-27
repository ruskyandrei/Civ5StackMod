[CmdletBinding()]
param(
    [ValidateSet('release', 'debug')]
    [string]$Configuration = 'debug',

    [ValidateRange(1, 256)]
    [int]$Jobs = 6,

    [string]$Python = 'C:\Users\rusit\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',

    [switch]$Check,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$BuildArguments = @()
)

$ErrorActionPreference = 'Stop'
$wrapper = Join-Path $PSScriptRoot 'build-vp-msvc.py'
if (-not (Test-Path -LiteralPath $wrapper -PathType Leaf)) {
    throw "Build wrapper not found: $wrapper"
}
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
    throw "Python was not found at '$Python'. Supply a Python 3.10+ executable with -Python <path>."
}

$pythonArguments = @('-B', '-u', $wrapper, '--config', $Configuration, '--jobs', [string]$Jobs, '--embedded-compiler-debug')
if ($Configuration -eq 'release') { $pythonArguments += @('--no-ltcg','--pch-memory','400') }
if ($Check) {
    $pythonArguments += '--check'
}
$pythonArguments += $BuildArguments
& $Python @pythonArguments
exit $LASTEXITCODE
