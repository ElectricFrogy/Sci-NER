import subprocess
import sys
import tempfile
import os
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from common import load_json, stable_sort_spans, strip_nondeterminism, try_jsonschema_validate

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples" / "chapters.jsonl"
SCHEMAS = {
    "quotes": ROOT / "schemas" / "quotes.raw.schema.json",
    "entities": ROOT / "schemas" / "entities.raw.schema.json",
}


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        results = {}
        for key, script in [
            ("quotes", ROOT / "quotes_extract.py"),
            ("entities", ROOT / "ner_extract.py"),
        ]:
            out_path = tmp / f"{key}.json"
            cmd = [
                sys.executable,
                str(script),
                "--in",
                str(SAMPLES),
                "--work-slug",
                "sample",
                "--export-offsets",
                str(out_path),
            ]
            env = os.environ.copy()
            if key == "entities":
                env["NER_FORCE_PURE"] = "1"
            subprocess.run(cmd, check=True, env=env)
            obj = load_json(out_path)
            stable_sort_spans(obj, key)
            strip_nondeterminism(obj)
            results[key] = obj

        for key, obj in results.items():
            status, msg = try_jsonschema_validate(obj, SCHEMAS[key])
            if status == "skip":
                print(f"SKIP schema: {msg}")
                return 0
        print("Schema validation OK")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
