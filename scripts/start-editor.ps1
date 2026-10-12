param(
    [Parameter(Mandatory)][string]$Executable,
    [Parameter(Mandatory)][string]$ProjectFile,
    [string]$BridgeDirectory
)
$ErrorActionPreference = 'Stop'
$repoDirectory = Split-Path -Parent $PSScriptRoot
if (!$BridgeDirectory) { $BridgeDirectory = Join-Path $repoDirectory '.pyrite64-mcp/bridge' }
$env:PYRITE64_MCP_BRIDGE_DIR = [System.IO.Path]::GetFullPath($BridgeDirectory)
$resolvedExecutable = (Resolve-Path -LiteralPath $Executable).Path
$resolvedProject = (Resolve-Path -LiteralPath $ProjectFile).Path
# This launcher intentionally opens the interactive editor for the user.
Start-Process -FilePath $resolvedExecutable -WorkingDirectory (Split-Path $resolvedExecutable) -ArgumentList ('"' + $resolvedProject + '"')
