import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

STAGES = [
    ("golden", ROOT / "run_golden.py"),
    ("crlf", ROOT / "run_crlf_equivalence.py"),
    ("determinism", ROOT / "run_determinism.py"),
    ("schema", ROOT / "run_schema.py"),
    ("cli_facade", ROOT / "run_cli_facade.py"),
]


def main() -> int:
    for name, script in STAGES:
        proc = subprocess.run([sys.executable, str(script)])
        if proc.returncode != 0:
            print(f"FAIL {name}")
            return proc.returncode
        print(f"PASS {name}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
