# Setup

This project targets **Python 3.11**. Create a virtual environment and install
dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
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

## Running Tests

```powershell
python -m pip install -r requirements.txt
python tests/run_all.py
```

On first run the command bootstraps `golden/*.golden.json` from `samples/chapters.jsonl`.

If spaCy and its model are unavailable, force the pure-Python NER path:

```powershell
$env:NER_FORCE_PURE="1"
python tests/run_all.py
Remove-Item Env:\NER_FORCE_PURE
```

Golden comparisons ignore `duration_sec` and any future telemetry fields.

### Testing notes
- The NER extractor continues to work without spaCy/model via a deterministic pure-Python fallback.
- You can force the fallback path during local tests:
  ```powershell
  $env:NER_FORCE_PURE="1"
  python smoke_tests.py
  ```

### Windows (PyCharm) — quick setup with existing `.venv`

1. In PyCharm, ensure **Settings → Project → Python Interpreter** points to `.venv`.
2. Open **PowerShell** at the project root and run:

   ```powershell
   # If scripts are blocked:
   Set-ExecutionPolicy Bypass -Scope Process

   # Install deps with wheels first (avoids MSVC build errors)
   .\scripts\setup_venv.ps1
   # If you still see build attempts, run with constraints:
   .\scripts\setup_venv.ps1 -UseConstraints
   ```

Tips

Prefer `python -m pip` ... (avoid bare `pip` and avoid JetBrains packaging helpers).

Wheels-first flags `--only-binary=:all:` `--prefer-binary` reduce native build issues on Windows.

Run

```bash
# Quotes (deterministic)
python quotes_extract.py --in samples/chapters.jsonl --out quotes.raw.json --work-slug scifi_sample --determinism-check

# NER (uses spaCy if available; else blank('en') or pure-Python fallback, deterministic)
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

### Unified CLI

```bash
# Quotes
python pipeline.py extract quotes --in samples/chapters.jsonl --out quotes.raw.json --work-slug scifi_sample --determinism-check

# Entities
python pipeline.py extract entities --in samples/chapters.jsonl --out entities.raw.json --work-slug scifi_sample --determinism-check

# Stream to stdout (no file)
python pipeline.py extract quotes --in samples/chapters.jsonl --work-slug scifi_sample --stdout

# Dry-run (hashes & counts only)
python pipeline.py dry-run --in samples/chapters.jsonl --work-slug scifi_sample
```

### Unified CLI

```bash
# Quotes
python pipeline.py extract quotes --in samples/chapters.jsonl --out quotes.raw.json --work-slug scifi_sample --determinism-check

# Entities
python pipeline.py extract entities --in samples/chapters.jsonl --out entities.raw.json --work-slug scifi_sample --determinism-check

# Stream to stdout (no file)
python pipeline.py extract quotes --in samples/chapters.jsonl --work-slug scifi_sample --stdout

# Dry-run (hashes & counts only)
python pipeline.py dry-run --in samples/chapters.jsonl --work-slug scifi_sample
```
