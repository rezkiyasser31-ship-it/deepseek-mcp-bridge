# install_bridge.ps1
Write-Host "============================================="
Write-Host "  DeepSeek Harness <-> Claude Bridge Installer"
Write-Host "============================================="
Write-Host ""

# 1. Discover best Python executable
$pythonExe = $null
if (Test-Path "C:\Program Files\Python312\python.exe") {
    $pythonExe = "C:\Program Files\Python312\python.exe"
} else {
    try {
        $cmd = Get-Command python -ErrorAction Stop
        $pythonExe = $cmd.Source
    } catch {
        Write-Host "[-] Python is not installed or not in PATH."
        Write-Host "Please install Python from python.org or Microsoft Store."
        Exit
    }
}

$pythonVersion = & $pythonExe --version 2>&1
Write-Host "[+] Using Python executable: $pythonExe ($pythonVersion)"

# 2. Install dependencies
Write-Host "[*] Checking and installing dependencies (mcp, pyyaml)..."
& $pythonExe -m pip install mcp pyyaml --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[-] Warning: pip returned non-zero exit code. Will proceed if modules already present."
}

# 3. Locate paths
$scriptPath = $MyInvocation.MyCommand.Path
$bridgeDir = Split-Path -Parent $scriptPath
$serverPath = Join-Path $bridgeDir "server.py"

# 4. Find all Claude Desktop config paths
$candidatePaths = [System.Collections.Generic.List[string]]@(
    "$env:APPDATA\Claude\claude_desktop_config.json",
    "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json",
    "$env:LOCALAPPDATA\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude-3p\claude_desktop_config.json"
)

# Also detect Claude-Data directory used when Claude runs with custom user-data-dir
$claudeDataDir = "$env:LOCALAPPDATA\Claude-Data"
if (Test-Path $claudeDataDir) {
    Get-ChildItem -Path $claudeDataDir -Filter "claude_desktop_config.json" -Recurse | ForEach-Object {
        $candidatePaths.Add($_.FullName)
    }
}

# Also detect Claude Multi-Account native profiles
$multiProfiles = Join-Path (Split-Path -Parent $env:USERPROFILE) "$env:USERNAME\.claude_multi\native_profiles"
if (Test-Path $multiProfiles) {
    Get-ChildItem -Path $multiProfiles -Filter "claude_desktop_config.json" -Recurse | ForEach-Object {
        $candidatePaths.Add($_.FullName)
    }
}

# 5. Safely update JSON using Python (safe against BOM and multi-account wiping)
Write-Host "[*] Registering DeepSeek bridge in Claude Desktop configs..."

foreach ($configPath in $candidatePaths) {
    $configDir = Split-Path -Parent $configPath
    if (-not (Test-Path -Path $configDir)) {
        New-Item -ItemType Directory -Force -Path $configDir | Out-Null
    }

    $pythonScript = @"
import json
import os
import sys

config_path = r'$configPath'
server_path = r'$serverPath'
python_exe = r'$pythonExe'

config = {}
if os.path.exists(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8-sig') as f:
            content = f.read().strip()
            if content:
                config = json.loads(content)
    except Exception as e:
        print(f'[-] Warning parsing existing config {config_path}: {e}')

if 'mcpServers' not in config:
    config['mcpServers'] = {}

config['mcpServers']['deepseek'] = {
    'command': python_exe,
    'args': [server_path]
}

with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2)

print(f'[+] Successfully merged DeepSeek bridge into {config_path}!')
"@

    $tempScript = Join-Path $env:TEMP "patch_claude_deepseek.py"
    Set-Content -Path $tempScript -Value $pythonScript -Encoding UTF8
    & $pythonExe $tempScript
    Remove-Item $tempScript -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "[SUCCESS] DeepSeek Harness Bridge registered successfully!"
Write-Host "Active tools for Claude Desktop:"
Write-Host "  - delegate_to_deepseek"
Write-Host "  - send_feedback_to_deepseek"
Write-Host "  - inspect_deepseek_session"
Write-Host "  - cancel_deepseek_session"
Write-Host ""
Write-Host "NEXT STEP: Restart Claude Desktop, open your browser to http://127.0.0.1:3080, and enjoy the live link!"
