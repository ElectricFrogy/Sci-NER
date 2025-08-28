param(
  [switch]$UseConstraints
)

# 1) Activate existing venv
$activate = ".\.venv\Scripts\Activate.ps1"
if (-Not (Test-Path $activate)) {
  Write-Host "[setup] ERROR: missing $activate" -ForegroundColor Red
  exit 1
}
. $activate
$venvPython = (Get-Command python).Source

# Choose constraints if requested
$constraints = $null
if ($UseConstraints) {
  $pyVer = & $venvPython -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
  if ($pyVer -eq '3.11') {
    $constraints = 'constraints-windows-py311.txt'
  } elseif ($pyVer -eq '3.13') {
    $constraints = 'constraints-windows-py313.txt'
  } else {
    Write-Error "Unsupported Python version: $pyVer. Use 3.11 or 3.13 on Windows."
    exit 1
  }
}

# Upgrade tooling
& $venvPython -m pip install -U pip setuptools wheel

# Install deps with wheels-first policy
if ($constraints) {
  & $venvPython -m pip install -r requirements.txt -c $constraints --only-binary=:all: --prefer-binary
} else {
  & $venvPython -m pip install -r requirements.txt --only-binary=:all: --prefer-binary
}

# Optional: attempt model download (do not fail if it can't)
try {
  & $venvPython scripts\install_spacy_model.py
} catch {
  Write-Host "Skipping spaCy model download (optional)."
}

Write-Host "[setup] done"
