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

def _compare(output_path: Path, golden_name: str, key: str) -> int:
    obj = load_json(output_path)
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
        q_out = tmp / "q.json"
        subprocess.run([
            sys.executable,
            str(ROOT / "pipeline.py"),
            "extract",
            "quotes",
            "--in",
            str(SAMPLES),
            "--out",
            str(q_out),
            "--work-slug",
            "sample",
            "--determinism-check",
        ], check=True)
        rc |= _compare(q_out, "quotes.golden.json", "quotes")

        e_out = tmp / "e.json"
        subprocess.run([
            sys.executable,
            str(ROOT / "pipeline.py"),
            "extract",
            "entities",
            "--in",
            str(SAMPLES),
            "--out",
            str(e_out),
            "--work-slug",
            "sample",
            "--determinism-check",
        ], check=True, env={**os.environ, "NER_FORCE_PURE": "1"})
        rc |= _compare(e_out, "entities.golden.json", "entities")

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
        rc |= _compare(q_stdout, "quotes.golden.json", "quotes")

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
        rc |= _compare(e_stdout, "entities.golden.json", "entities")

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
