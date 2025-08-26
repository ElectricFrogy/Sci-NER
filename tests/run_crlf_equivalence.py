import subprocess
import sys
import tempfile
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent
sys.path.append(str(BASE))
sys.path.append(str(BASE.parent))
from common import load_json, stable_sort_spans, strip_nondeterminism
from utils import iter_chapters

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / "samples" / "chapters.jsonl"


def make_crlf_variant(src: Path, dst: Path) -> None:
    text = src.read_text(encoding="utf-8")
    dst.write_text(text.replace("\n", "\r\n"), encoding="utf-8", newline="")


def main() -> int:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        crlf_path = tmp / "chapters_crlf.jsonl"
        make_crlf_variant(SAMPLES, crlf_path)

        runs = [
            ("lf", SAMPLES),
            ("crlf", crlf_path),
        ]
        outputs = {}
        chapters_text = {}
        for tag, in_path in runs:
            q_out = tmp / f"quotes_{tag}.json"
            e_out = tmp / f"entities_{tag}.json"
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "quotes_extract.py"),
                    "--in",
                    str(in_path),
                    "--work-slug",
                    "sample",
                    "--export-offsets",
                    str(q_out),
                ],
                check=True,
            )
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "ner_extract.py"),
                    "--in",
                    str(in_path),
                    "--work-slug",
                    "sample",
                    "--export-offsets",
                    str(e_out),
                ],
                check=True,
                env={**os.environ, "NER_FORCE_PURE": "1"},
            )
            q_obj = load_json(q_out)
            e_obj = load_json(e_out)
            stable_sort_spans(q_obj, "quotes")
            stable_sort_spans(e_obj, "entities")
            strip_nondeterminism(q_obj)
            strip_nondeterminism(e_obj)
            outputs[tag] = {"quotes": q_obj, "entities": e_obj}
            chapters_text[tag] = {cid: text for cid, text in iter_chapters(in_path)}

        lf = outputs["lf"]
        cr = outputs["crlf"]
        if lf["quotes"]["text_hash"] != cr["quotes"]["text_hash"]:
            print("text_hash mismatch for quotes")
            return 1
        if lf["entities"]["text_hash"] != cr["entities"]["text_hash"]:
            print("text_hash mismatch for entities")
            return 1

        # sample spans
        for tag in ("lf", "crlf"):
            texts = chapters_text[tag]
            for key in ("quotes", "entities"):
                spans = outputs[tag][key].get(key, [])[:3]
                for sp in spans:
                    chapter_text = texts[sp["chapter_id"]]
                    if chapter_text[sp["start"]:sp["end"]] != sp["text"]:
                        print(f"Span text mismatch in {key} {tag}")
                        return 1
        return 0

if __name__ == "__main__":
    raise SystemExit(main())
