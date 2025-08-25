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
