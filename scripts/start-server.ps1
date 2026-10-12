param(
    [string]$ProjectDirectory = $env:PYRITE64_PROJECT,
    [ValidateSet('offline', 'live')][string]$Mode = 'offline',
    [ValidateSet('http', 'stdio')][string]$Transport = 'http',
    [string]$Executable = $env:PYRITE64_EXECUTABLE,
    [string]$AresExecutable = $env:PYRITE64_ARES,
    [string]$BridgeDirectory,
    [int]$Port = 8974
)
$ErrorActionPreference = 'Stop'
$repoDirectory = Split-Path -Parent $PSScriptRoot
$pythonExecutable = Join-Path $repoDirectory '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $pythonExecutable)) {
    throw 'Create .venv and install the package first; see README.md.'
}
if (!$BridgeDirectory) { $BridgeDirectory = Join-Path $repoDirectory '.pyrite64-mcp/bridge' }
$env:PYTHONPATH = Join-Path $repoDirectory 'src'
$serverArguments = @('-m', 'pyrite64_mcp.server', '--transport', $Transport.ToLowerInvariant(), '--port', "$Port", '--mode', $Mode.ToLowerInvariant(), '--bridge-dir', $BridgeDirectory)
if ($ProjectDirectory) { $serverArguments += @('--project', $ProjectDirectory) }
if ($Executable) { $serverArguments += @('--executable', $Executable) }
if ($AresExecutable) { $serverArguments += @('--ares', $AresExecutable) }
& $pythonExecutable @serverArguments
exit $LASTEXITCODE
