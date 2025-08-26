import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from common import load_json, stable_sort_spans, strip_nondeterminism, sha256_bytes

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples" / "chapters.jsonl"

EXTRACTORS = [
    ("quotes", ROOT / "quotes_extract.py"),
    ("entities", ROOT / "ner_extract.py"),
]


def _hash_output(path: Path, key: str) -> str:
    obj = load_json(path)
    stable_sort_spans(obj, key)
    strip_nondeterminism(obj)
    data = json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
    return sha256_bytes(data)


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for key, script in EXTRACTORS:
            out_a = tmp / f"{key}_a.json"
            out_b = tmp / f"{key}_b.json"
            cmd = [sys.executable, str(script), "--in", str(SAMPLES), "--work-slug", "sample"]
            subprocess.run(cmd + ["--out", str(out_a)], check=True)
            subprocess.run(cmd + ["--out", str(out_b)], check=True)
            h1 = _hash_output(out_a, key)
            h2 = _hash_output(out_b, key)
            if h1 != h2:
                print(f"Non-deterministic output for {key}: {h1} != {h2}")
                return 1
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
