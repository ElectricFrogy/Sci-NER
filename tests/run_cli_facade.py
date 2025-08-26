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

def _canonical_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _run_cli_to_stdout(args, extra_env=None):
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    cp = subprocess.run(args, capture_output=True, check=True, env=env)
    tmp = Path(tempfile.gettempdir()) / "cli_stdout.json"
    with open(tmp, "wb") as fh:
        fh.write(cp.stdout)
    return tmp

def _compare(output_path: Path, golden_name: str, key: str | None = None, tei: bool = False) -> int:
    obj = load_json(output_path)
    if tei:
        obj.get("annotations", []).sort(key=lambda a: (a.get("chapter_id"), a.get("token_span", [0,0])[0], a.get("token_span", [0,0])[1]))
    elif key:
        stable_sort_spans(obj, key)
    strip_nondeterminism(obj)
    data = _canonical_bytes(obj)
    with open(GOLDEN_DIR / golden_name, "rb") as fh:
        golden = fh.read()
    if data != golden:
        print(f"Mismatch against {golden_name}")
        return 1
    return 0

def main() -> int:
    rc = 0
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        q_tei = tmp / "q.tei.json"
        q_off = tmp / "q.json"
        subprocess.run([
            sys.executable,
            str(ROOT / "pipeline.py"),
            "extract",
            "quotes",
            "--in",
            str(SAMPLES),
            "--work-slug",
            "sample",
            "--emit-tei",
            str(q_tei),
            "--export-offsets",
            str(q_off),
            "--determinism-check",
        ], check=True)
        rc |= _compare(q_off, "quotes.golden.json", "quotes")
        rc |= _compare(q_tei, "quotes.tei.golden.json", tei=True)

        e_tei = tmp / "e.tei.json"
        e_off = tmp / "e.json"
        subprocess.run([
            sys.executable,
            str(ROOT / "pipeline.py"),
            "extract",
            "entities",
            "--in",
            str(SAMPLES),
            "--work-slug",
            "sample",
            "--emit-tei",
            str(e_tei),
            "--export-offsets",
            str(e_off),
            "--determinism-check",
        ], check=True, env={**os.environ, "NER_FORCE_PURE": "1"})
        rc |= _compare(e_off, "entities.golden.json", "entities")
        rc |= _compare(e_tei, "entities.tei.golden.json", tei=True)

        q_stdout = _run_cli_to_stdout([
            sys.executable,
            str(ROOT / "pipeline.py"),
            "extract",
            "quotes",
            "--in",
            str(SAMPLES),
            "--work-slug",
            "sample",
            "--stdout",
            "--determinism-check",
        ])
        rc |= _compare(q_stdout, "quotes.tei.golden.json", tei=True)

        e_stdout = _run_cli_to_stdout([
            sys.executable,
            str(ROOT / "pipeline.py"),
            "extract",
            "entities",
            "--in",
            str(SAMPLES),
            "--work-slug",
            "sample",
            "--stdout",
            "--determinism-check",
        ], extra_env={"NER_FORCE_PURE": "1"})
        rc |= _compare(e_stdout, "entities.tei.golden.json", tei=True)

        q_off2 = tmp / "q2.json"
        subprocess.run([
            sys.executable,
            str(ROOT / "pipeline.py"),
            "export",
            "offsets",
            "--tei",
            str(q_tei),
            "--out",
            str(q_off2),
            "--in",
            str(SAMPLES),
        ], check=True)
        rc |= _compare(q_off2, "quotes.golden.json", "quotes")

        e_off2 = tmp / "e2.json"
        subprocess.run([
            sys.executable,
            str(ROOT / "pipeline.py"),
            "export",
            "offsets",
            "--tei",
            str(e_tei),
            "--out",
            str(e_off2),
            "--in",
            str(SAMPLES),
        ], check=True)
        rc |= _compare(e_off2, "entities.golden.json", "entities")

        proc = subprocess.run([
            sys.executable,
            str(ROOT / "pipeline.py"),
            "dry-run",
            "--in",
            str(SAMPLES),
            "--work-slug",
            "sample",
        ], check=True, stdout=subprocess.PIPE)
        drobj = json.loads(proc.stdout.decode("utf-8"))
        required = {"work_slug", "pipeline_version", "normalization_version", "text_hash", "counts"}
        if not required.issubset(drobj.keys()):
            print("Missing keys in dry-run output")
            rc |= 1
    return rc

if __name__ == "__main__":
    raise SystemExit(main())
