import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))
from common import load_json, stable_sort_spans, strip_nondeterminism

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples" / "chapters.jsonl"
GOLDEN_DIR = ROOT / "golden"

EXTRACTORS = [
    ("quotes", ROOT / "quotes_extract.py", "quotes.golden.json"),
    ("entities", ROOT / "ner_extract.py", "entities.golden.json"),
]

def _canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def main() -> int:
    rc = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        for key, script, golden_name in EXTRACTORS:
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
                "--determinism-check",
            ]
            env = os.environ.copy()
            if key == "entities":
                env["NER_FORCE_PURE"] = "1"
            subprocess.run(cmd, check=True, env=env)
            obj = load_json(out_path)
            stable_sort_spans(obj, key)
            strip_nondeterminism(obj)
            data_bytes = _canonical_bytes(obj)

            gpath = GOLDEN_DIR / golden_name
            if not gpath.exists() or load_json(gpath) == {}:
                gpath.parent.mkdir(parents=True, exist_ok=True)
                with open(gpath, "wb") as fh:
                    fh.write(data_bytes)
                print(f"Bootstrapped golden {gpath}")
                continue
            with open(gpath, "rb") as fh:
                golden_bytes = fh.read()
            if data_bytes != golden_bytes:
                gobj = json.loads(golden_bytes)
                pobj = json.loads(data_bytes)
                if len(pobj.get(key, [])) != len(gobj.get(key, [])):
                    print(
                        f"Mismatch in {key} count: {len(pobj.get(key, []))} != {len(gobj.get(key, []))}"
                    )
                else:
                    for s1, s2 in zip(pobj.get(key, []), gobj.get(key, [])):
                        if s1 != s2:
                            diff_key = next((k for k in s1 if s1.get(k) != s2.get(k)), "?")
                            print(
                                f"First diff in {key} at record_id {s1.get('record_id')} field {diff_key}"
                            )
                            break
                rc = 1
    return rc

if __name__ == "__main__":
    raise SystemExit(main())
