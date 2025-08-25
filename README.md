# Quick run commands

## Quotes (deterministic)
python quotes_extract.py --in samples/chapters.jsonl --out quotes.raw.json --work-slug scifi_sample --determinism-check

## NER (deterministic)
python ner_extract.py --in samples/chapters.jsonl --out entities.raw.json --work-slug scifi_sample --determinism-check

## Smoke tests (no deps)
python smoke_tests.py
