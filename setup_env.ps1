<#
setup_env.ps1
Creates a Python 3.8 virtual environment (venv38) and installs requirements.
Usage: Open PowerShell as your normal user and run:
    .\setup_env.ps1

Notes:
- This script will use `py -3.8` if available. If not, it will attempt `python`.
- It will NOT attempt to install `pyrfc` automatically unless an NW RFC SDK path is provided via env var NWRFCSDK_DIR.
  Installing `pyrfc` usually requires the SAP NW RFC SDK and matching Python ABI.
#>

Write-Host "== Setup script for virtualenv and requirements ==" -ForegroundColor Cyan

$ErrorActionPreference = 'Stop'

# Allow passing explicit Python executable path via env var or first script arg
$paramPythonExe = $args[0]
$pythonExe = $env:PYTHON_EXE
if (-not $pythonExe -and $paramPythonExe) { $pythonExe = $paramPythonExe }

# Helper to check version for a given python executable path/command
function Get-PythonVersionString([string]$exe) {
    try {
        $out = & $exe -c "import sys; print(sys.version)" 2>$null
        return $out -as [string]
    } catch {
        return $null
    }
}

Write-Host "Detecting Python 3.8..." -ForegroundColor Yellow

# 1) If user provided explicit path or env var, test it
if ($pythonExe) {
    $ver = Get-PythonVersionString $pythonExe
    if ($ver -and $ver -match '^3\.8') {
        Write-Host "Using Python executable from PYTHON_EXE/env/arg: $pythonExe" -ForegroundColor Green
    } else {
        Write-Host "Provided PYTHON_EXE does not look like Python 3.8: $pythonExe" -ForegroundColor Yellow
        $pythonExe = $null
    }
}

# 2) Try py launcher (preferred) and extract actual executable path
if (-not $pythonExe) {
    try {
        $pyPath = & py -3.8 -c "import sys; print(sys.executable)" 2>$null
        if ($pyPath) { $pyPath = $pyPath.Trim(); $ver = Get-PythonVersionString $pyPath; if ($ver -and $ver -match '^3\.8') { $pythonExe = $pyPath; Write-Host "Found Python 3.8 via py launcher: $pythonExe" -ForegroundColor Green } }
    } catch {
        # ignore
    }
}

# 3) Try 'python' command if it is Python 3.8
if (-not $pythonExe) {
    try {
        $ver = Get-PythonVersionString 'python'
        if ($ver -and $ver -match '^3\.8') { $pythonExe = 'python'; Write-Host "Found Python 3.8 via 'python' on PATH" -ForegroundColor Green }
    } catch {
        # ignore
    }
}

# 4) Check common install locations
if (-not $pythonExe) {
    $common = @(
        Join-Path $env:LOCALAPPDATA "Programs\Python\Python38\python.exe",
        "C:\Program Files\Python38\python.exe",
        "C:\Program Files (x86)\Python38\python.exe"
    )
    foreach ($p in $common) {
        if (Test-Path $p) {
            $ver = Get-PythonVersionString $p
            if ($ver -and $ver -match '^3\.8') { $pythonExe = $p; Write-Host "Found Python 3.8 at $p" -ForegroundColor Green; break }
        }
    }
}

# 5) Last resort: search LOCALAPPDATA Programs for Python
if (-not $pythonExe) {
    try {
        $found = Get-ChildItem -Path (Join-Path $env:LOCALAPPDATA 'Programs') -Recurse -Filter python.exe -ErrorAction SilentlyContinue | Select-Object -First 8 -ExpandProperty FullName
        foreach ($f in $found) {
            $ver = Get-PythonVersionString $f
            if ($ver -and $ver -match '^3\.8') { $pythonExe = $f; Write-Host "Located Python 3.8 at $f" -ForegroundColor Green; break }
        }
    } catch {
        # ignore
    }
}

if (-not $pythonExe) {
    Write-Host "Python 3.8 not found. Please install Python 3.8 or set the PYTHON_EXE environment variable to the python.exe path." -ForegroundColor Red
    Write-Host "Example: $env:PYTHON_EXE='C:\\Users\\you\\AppData\\Local\\Programs\\Python\\Python38\\python.exe' ; .\\setup_env.ps1" -ForegroundColor Cyan
    exit 1
}

$venvPath = Join-Path (Get-Location) 'venv38'
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment at $venvPath using $pythonExe..." -ForegroundColor Yellow
    & $pythonExe -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to create venv with $pythonExe" -ForegroundColor Red
        exit 2
    }
} else {
    Write-Host "Virtual environment already exists: $venvPath" -ForegroundColor Green
}

$venvPython = Join-Path $venvPath 'Scripts\python.exe'
if (-not (Test-Path $venvPython)) {
    Write-Host "Cannot find venv python at $venvPython" -ForegroundColor Red
    exit 3
}

Write-Host "Upgrading pip in venv..." -ForegroundColor Yellow
& $venvPython -m pip install --upgrade pip setuptools wheel

# Install requirements.txt (if exists)
$req = Join-Path (Get-Location) 'requirements.txt'
if (Test-Path $req) {
    Write-Host "Installing packages from requirements.txt..." -ForegroundColor Yellow
    & $venvPython -m pip install -r $req
} else {
    Write-Host "requirements.txt not found, skipping pip install -r requirements.txt" -ForegroundColor Yellow
}

# pyrfc note: attempt auto-install only if NWRFCSDK_DIR provided
if ($env:NWRFCSDK_DIR) {
    Write-Host "Detected NWRFCSDK_DIR environment variable: $env:NWRFCSDK_DIR" -ForegroundColor Green
    Write-Host "Attempting to install pyrfc (may still fail if ABI mismatch)" -ForegroundColor Yellow
    & $venvPython -m pip install pyrfc
    if ($LASTEXITCODE -ne 0) {
        Write-Host "pyrfc install failed. Please ensure NW RFC SDK is installed and accessible." -ForegroundColor Red
    }
} else {
    Write-Host "Note: pyrfc not installed automatically. If you need pyrfc, install SAP NW RFC SDK and then run:" -ForegroundColor Cyan
    Write-Host "    $venvPath\\Scripts\\activate.ps1" -ForegroundColor Cyan
    Write-Host "    pip install pyrfc" -ForegroundColor Cyan
}

Write-Host "\nSetup complete." -ForegroundColor Green
Write-Host "To activate the virtual environment in your current PowerShell session run:" -ForegroundColor Cyan
Write-Host "    Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process -Force" -ForegroundColor Cyan
Write-Host "    . $venvPath\\Scripts\\Activate.ps1" -ForegroundColor Cyan
Write-Host "Then you can start the gateway or Streamlit:" -ForegroundColor Cyan
Write-Host "    python sap_gateway.py" -ForegroundColor Cyan
Write-Host "    python -m streamlit run app.py --server.port 8501" -ForegroundColor Cyan
