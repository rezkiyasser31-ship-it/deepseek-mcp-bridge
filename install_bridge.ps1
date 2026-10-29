# install_bridge.ps1
# Industry-standard PowerShell installer for DeepSeek Harness MCP Bridge

Write-Host "============================================="
Write-Host "  DeepSeek Harness <-> Claude Bridge Installer"
Write-Host "============================================="
Write-Host ""

# 1. Discover Python dynamically across the system
$pythonExe = $null

# Check standard PATH first
try {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $pythonExe = $cmd.Source
    }
} catch {}

# Fallback to py launcher
if (-not $pythonExe) {
    try {
        $cmd = Get-Command py -ErrorAction SilentlyContinue
        if ($cmd) {
            $pythonExe = $cmd.Source
        }
    } catch {}
}

# Fallback to common Windows installation directories
if (-not $pythonExe) {
    $commonPaths = @(
        "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe",
        "$env:ProgramFiles\Python*\python.exe",
        "C:\Python*\python.exe"
    )
    foreach ($pat in $commonPaths) {
        $found = Get-Item $pat -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $pythonExe = $found.FullName
            break
        }
    }
}

if (-not $pythonExe) {
    Write-Host "[-] Error: Python is not installed or not in PATH." -ForegroundColor Red
    Write-Host "    Please install Python 3.10+ from python.org or via winget: winget install Python.Python.3.12"
    Exit 1
}

$pythonVersion = & $pythonExe --version 2>&1
Write-Host "[+] Discovered Python: $pythonExe ($pythonVersion)"

# 2. Install dependencies dynamically from requirements.txt
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$reqFile = Join-Path $scriptDir "requirements.txt"
$installPy = Join-Path $scriptDir "install.py"

Write-Host "[*] Checking and installing dependencies..."
if (Test-Path $reqFile) {
    & $pythonExe -m pip install -r $reqFile --quiet
} else {
    & $pythonExe -m pip install mcp pyyaml --quiet
}

# 3. Run cross-platform installer
Write-Host "[*] Running configuration installer..."
& $pythonExe $installPy

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[SUCCESS] Installation finished successfully!" -ForegroundColor Green
} else {
    Write-Host "[-] Installer exited with code $LASTEXITCODE" -ForegroundColor Yellow
}
