# Setup

This project targets **Python 3.11**. Create a virtual environment and install
dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If `spaCy` or the `en_core_web_sm` model are missing, the NER extractor falls
back to a deterministic capitalized-span heuristic.

# Quick run commands

```bash
# Quotes (deterministic)
python quotes_extract.py --in samples/chapters.jsonl --out quotes.raw.json --work-slug scifi_sample --determinism-check

# NER (deterministic)
python ner_extract.py --in samples/chapters.jsonl --out entities.raw.json --work-slug scifi_sample --determinism-check

# Smoke tests
python smoke_tests.py
```

## Setup on Windows with existing .venv
```powershell
# From PowerShell in project root:
.\scripts\setup_venv.ps1
# Or, if you want to force constraints (to avoid builds):
.\scripts\setup_venv.ps1 -UseConstraints
```

## Run
```powershell
python quotes_extract.py --in samples/chapters.jsonl --out quotes.raw.json --work-slug scifi_sample --determinism-check
python ner_extract.py    --in samples/chapters.jsonl --out entities.raw.json --work-slug scifi_sample --determinism-check
python smoke_tests.py
```
