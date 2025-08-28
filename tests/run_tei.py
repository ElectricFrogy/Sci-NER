import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
ROOT = TEST_DIR.parent
sys.path.append(str(TEST_DIR))
sys.path.append(str(ROOT))

from common import load_json, strip_nondeterminism, try_jsonschema_validate
from utils import iter_chapters, tokenize, token_span_to_char_span, token_sha

SAMPLES = ROOT / "samples" / "chapters.jsonl"
GOLDEN_DIR = ROOT / "golden"
SCHEMA = ROOT / "schemas" / "tei.layer.schema.json"


def _canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _emit_tei(script: Path, out_path: Path, extra_env=None) -> None:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--in",
            str(SAMPLES),
            "--work-slug",
            "sample",
            "--emit-tei",
            str(out_path),
        ],
        check=True,
        env=env,
    )


def _compare(path: Path, golden: str) -> int:
    obj = load_json(path)
    obj.get("annotations", []).sort(key=lambda a: (a["chapter_id"], a["token_span"][0], a["token_span"][1]))
    strip_nondeterminism(obj)
    data = _canonical_bytes(obj)
    with open(GOLDEN_DIR / golden, "rb") as fh:
        if data != fh.read():
            print(f"Mismatch against {golden}")
            return 1
    # round-trip & tokenization checks
    chapters = {cid: text for cid, text in iter_chapters(str(SAMPLES))}
    token_meta = obj.get("tokenization", {}).get("per_chapter", {})
    chapters_seen = {ann["chapter_id"] for ann in obj.get("annotations", [])}
    for cid in chapters_seen:
        meta = token_meta.get(str(cid))
        if not meta or "count" not in meta or "sha" not in meta:
            print(f"Missing token metadata for chapter {cid}")
            return 1
        tokens = tokenize(chapters[cid])
        if len(tokens) != meta["count"] or token_sha(tokens) != meta["sha"]:
            print(f"Token metadata mismatch for chapter {cid}")
            return 1
    for ann in obj.get("annotations", []):
        tokens = tokenize(chapters[ann["chapter_id"]])
        s, e = token_span_to_char_span(tokens, ann["token_span"][0], ann["token_span"][1])
        if chapters[ann["chapter_id"]][s:e] != ann["text"]:
            print("Round-trip text mismatch")
            return 1
    status, msg = try_jsonschema_validate(obj, SCHEMA)
    if status == "skip":
        print(f"SKIP schema: {msg}")
    return 0 if status == "ok" else 1


def main() -> int:
    rc = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        q_tei = tmp / "quotes.tei.json"
        _emit_tei(ROOT / "quotes_extract.py", q_tei)
        rc |= _compare(q_tei, "quotes.tei.golden.json")

        e_tei = tmp / "entities.tei.json"
        _emit_tei(ROOT / "ner_extract.py", e_tei, extra_env={"NER_FORCE_PURE": "1"})
        rc |= _compare(e_tei, "entities.tei.golden.json")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
