# Interactive launcher. All locations come from user input or environment settings.
[CmdletBinding()]
param(
    [ValidateSet('live', 'offline', 'docs')][string]$Mode,
    [string]$ProjectDirectory = $env:PYRITE64_PROJECT,
    [string]$Executable = $env:PYRITE64_EXECUTABLE,
    [string]$BridgeDirectory,
    [ValidateRange(1, 65535)][int]$Port = 8974,
    [switch]$StartEditor,
    [switch]$Setup,
    [switch]$NonInteractive,
    [switch]$ValidateOnly
)
$ErrorActionPreference = 'Stop'
$localDirectory = Join-Path $PSScriptRoot '.pyrite64-mcp'
$settingsFile = Join-Path $localDirectory 'launcher.json'
$pythonExecutable = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'

function Get-UserPath([string]$Value) {
    if (!$Value) { return '' }
    return [IO.Path]::GetFullPath([Environment]::ExpandEnvironmentVariables($Value.Trim().Trim('"')))
}
function Read-Default([string]$Label, [string]$Default) {
    $suffix = if ($Default) { " [$Default]" } else { '' }
    $answer = Read-Host "$Label$suffix"
    if ([string]::IsNullOrWhiteSpace($answer)) { return $Default }
    return $answer.Trim()
}

try {
    $settings = $null
    if (Test-Path -LiteralPath $settingsFile) {
        try { $settings = Get-Content -LiteralPath $settingsFile -Raw | ConvertFrom-Json }
        catch { Write-Warning 'Saved settings could not be read; choose your locations again.' }
    }
    if (!$Mode) {
        if ($NonInteractive) { $Mode = 'docs' }
        else {
            Write-Host "`nPyrite64 MCP - Codex and Claude" -ForegroundColor Cyan
            Write-Host '1. Live editor control'
            Write-Host '2. Offline project editing (close the project in the editor)'
            Write-Host '3. Documentation and source search only'
            $defaultChoice = '1'
            if ($settings.mode -eq 'offline') { $defaultChoice = '2' }
            if ($settings.mode -eq 'docs') { $defaultChoice = '3' }
            $choice = Read-Default 'Choose a mode (1-3)' $defaultChoice
            $Mode = switch ($choice) { '1' { 'live' } '2' { 'offline' } '3' { 'docs' } default { throw 'Choose 1, 2 or 3.' } }
        }
    }
    $Mode = $Mode.ToLowerInvariant()
    if (!$ProjectDirectory) { $ProjectDirectory = $settings.projectDirectory }
    if (!$Executable) { $Executable = $settings.executable }
    if (!$BridgeDirectory) { $BridgeDirectory = Join-Path $localDirectory 'bridge' }
    $BridgeDirectory = Get-UserPath $BridgeDirectory
    if ($Mode -ne 'docs') {
        if (!$NonInteractive) {
            $ProjectDirectory = Read-Default 'Game folder or .p64proj file (paste or drag its path)' $ProjectDirectory
            $Executable = Read-Default 'Pyrite64 executable (optional for offline mode)' $Executable
        }
        if (!$ProjectDirectory) { throw 'Choose a game folder containing a .p64proj file.' }
        $ProjectDirectory = Get-UserPath $ProjectDirectory
        if ([IO.Path]::GetExtension($ProjectDirectory) -eq '.p64proj') {
            if (!(Test-Path -LiteralPath $ProjectDirectory -PathType Leaf)) { throw 'The project file does not exist.' }
            $ProjectDirectory = Split-Path -Parent $ProjectDirectory
        }
        if (!(Test-Path -LiteralPath $ProjectDirectory -PathType Container)) { throw 'The game folder does not exist.' }
        $projectFiles = @(Get-ChildItem -LiteralPath $ProjectDirectory -Filter '*.p64proj' -File)
        if ($projectFiles.Count -ne 1) { throw 'The game folder must contain exactly one .p64proj file.' }
        if ($Executable) {
            $Executable = Get-UserPath $Executable
            if (!(Test-Path -LiteralPath $Executable -PathType Leaf)) { throw 'The editor executable does not exist.' }
        }
        if ($Mode -eq 'live' -and !$Executable) { throw 'Live mode needs the rebuilt Pyrite64 executable.' }
    }
    if ($StartEditor -and $Mode -ne 'live') { throw '-StartEditor requires live mode.' }
    if ($Setup) {
        if (!(Test-Path -LiteralPath $pythonExecutable)) {
            $systemPython = Get-Command py -ErrorAction SilentlyContinue
            $pythonPrefix = @('-3')
            if (!$systemPython) { $systemPython = Get-Command python -ErrorAction SilentlyContinue; $pythonPrefix = @() }
            if (!$systemPython) { throw 'Install Python 3.11 or newer, then run this launcher with -Setup.' }
            & $systemPython.Source @pythonPrefix -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'
            if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or newer is required.' }
            & $systemPython.Source @pythonPrefix -m venv (Join-Path $PSScriptRoot '.venv')
            if ($LASTEXITCODE -ne 0) { throw 'Could not create the virtual environment.' }
        }
        & $pythonExecutable -m pip install 'mcp>=1.26,<2'
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check the network and try -Setup again.' }
    }
    if (!(Test-Path -LiteralPath $pythonExecutable)) { throw 'First-time setup: run ./run-win-pyrite64mcp.ps1 -Setup (requires Python 3.11+).' }
    & $pythonExecutable -c 'import sys, mcp; sys.exit(0 if sys.version_info >= (3, 11) else 1)' 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ and the MCP SDK are required. Run this launcher with -Setup.' }
    if ($ValidateOnly) { Write-Host "Launcher configuration valid: mode=$Mode, port=$Port"; exit 0 }
    $listener = $null
    try {
        $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $Port)
        $listener.Start()
    } catch { throw "Port $Port is unavailable. Stop the existing server or use -Port." }
    finally { if ($listener) { $listener.Stop() } }
    if (!$NonInteractive) {
        New-Item -ItemType Directory -Path $localDirectory -Force | Out-Null
        @{ mode=$Mode; projectDirectory=$ProjectDirectory; executable=$Executable } |
            ConvertTo-Json | Set-Content -LiteralPath $settingsFile -Encoding UTF8
        if ($Mode -eq 'live' -and !$StartEditor) {
            $StartEditor = (Read-Default 'Launch the rebuilt editor with this game now? (y/N)' 'N') -match '^(y|yes)$'
        }
    }
    if ($StartEditor) {
        & (Join-Path $PSScriptRoot 'scripts/start-editor.ps1') -Executable $Executable -ProjectFile $projectFiles[0].FullName -BridgeDirectory $BridgeDirectory
    }
    Write-Host "`nStarting Pyrite64 MCP at http://127.0.0.1:$Port/mcp" -ForegroundColor Green
    Write-Host 'Leave this window open. Press Ctrl+C to stop.'
    if ($Mode -eq 'live') { Write-Host 'The rebuilt editor must use the same bridge directory; use the editor launcher if it needs restarting.' }
    Write-Host "Codex:  codex mcp add pyrite64 --url http://127.0.0.1:$Port/mcp"
    Write-Host "Claude: claude mcp add --transport http pyrite64 http://127.0.0.1:$Port/mcp"
    $arguments = @{ Mode='offline'; Transport='http'; Port=$Port; BridgeDirectory=$BridgeDirectory; ProjectDirectory=''; Executable='' }
    if ($Mode -ne 'docs') {
        $arguments.Mode = $Mode
        $arguments.ProjectDirectory = $ProjectDirectory
        if ($Executable) { $arguments.Executable = $Executable }
    }
    & (Join-Path $PSScriptRoot 'scripts/start-server.ps1') @arguments
    exit $LASTEXITCODE
} catch {
    Write-Host "`nCould not start Pyrite64 MCP: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
