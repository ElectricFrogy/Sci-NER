param([switch]$UseConstraints)

$activate = ".\.venv\Scripts\Activate.ps1"
if (-Not (Test-Path $activate)) {
  Write-Host "[setup] ERROR: missing $activate" -ForegroundColor Red
  exit 1
}
. $activate

Write-Host "[setup] upgrading pip/setuptools/wheel"
python -m pip install --upgrade pip setuptools wheel

Write-Host "[setup] installing requirements (prefer wheels)"
if ($UseConstraints) {
  python -m pip install --only-binary=:all: --prefer-binary -r requirements.txt -c constraints-windows-py311.txt
} else {
  python -m pip install --only-binary=:all: --prefer-binary -r requirements.txt
}

Write-Host "[setup] attempting spaCy model install (safe if offline)"
python scripts/install_spacy_model.py

Write-Host "[setup] done"
