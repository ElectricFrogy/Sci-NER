param([switch]$UseConstraints)

# 1) Activate existing venv
$activate = ".\.venv\Scripts\Activate.ps1"
if (-Not (Test-Path $activate)) {
  Write-Host "[setup] ERROR: missing $activate" -ForegroundColor Red
  exit 1
}
. $activate

# 2) Upgrade packaging tooling (quoted, wheels preferred later)
python -m pip install --upgrade pip setuptools wheel

# 3) Install deps with wheels-first policy; optionally apply constraints
if ($UseConstraints) {
  python -m pip install --only-binary=:all: --prefer-binary -r requirements.txt -c constraints-windows-py311.txt
} else {
  python -m pip install --only-binary=:all: --prefer-binary -r requirements.txt
}

# 4) Try to fetch en_core_web_sm; safe to skip offline
python scripts\install_spacy_model.py

Write-Host "[setup] done"
