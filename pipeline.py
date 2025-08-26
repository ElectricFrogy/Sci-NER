import argparse
import json
import os
import sys
import tempfile
import contextlib
import io
from typing import Any, Callable, Dict

from quotes_extract import run as run_quotes
from ner_extract import run as run_entities
from utils import (
    compute_text_hashes,
    iter_chapters,
    NORMALIZATION_VERSION,
    deterministic_file_hash,
)

PIPELINE_VERSION = "0.1.0"


def _emit_stdout_path(path: str) -> None:
    with open(path, "rb") as fh:
        data = fh.read()
    sys.stdout.buffer.write(data)
    if not data.endswith(b"\n"):
        sys.stdout.buffer.write(b"\n")


def _run_extract(run_func: Callable[..., Any], args: argparse.Namespace) -> None:
    if args.stdout or not args.out_path:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        out_path = tmp.name
        tmp.close()
    else:
        out_path = args.out_path
    run_func(
        args.in_path,
        out_path,
        args.work_slug,
        dry_run=False,
        emit_manifest=args.emit_manifest,
        warns=args.warns,
    )
    if args.determinism_check:
        h1 = deterministic_file_hash(out_path)
        run_func(
            args.in_path,
            out_path,
            args.work_slug,
            dry_run=False,
            emit_manifest=args.emit_manifest,
            warns=args.warns,
        )
        h2 = deterministic_file_hash(out_path)
        if h1 != h2:
            raise RuntimeError(f"Non-deterministic output: {h1} != {h2}")
    if args.stdout:
        _emit_stdout_path(out_path)
        os.unlink(out_path)


def _parse_counts(output: str, header: str) -> int:
    total = 0
    lines = output.splitlines()
    parsing = False
    for line in lines:
        if line.startswith(header):
            parsing = True
            continue
        if parsing:
            if not line.startswith("  "):
                break
            try:
                total += int(line.split(":", 1)[1].strip())
            except Exception:
                pass
    return total


def _cmd_dry_run(args: argparse.Namespace) -> None:
    chapters = list(iter_chapters(args.in_path))
    text_hash = compute_text_hashes(chapters)
    q_buf = io.StringIO()
    with contextlib.redirect_stdout(q_buf):
        run_quotes(args.in_path, "", args.work_slug, dry_run=True)
    e_buf = io.StringIO()
    with contextlib.redirect_stdout(e_buf):
        run_entities(args.in_path, "", args.work_slug, dry_run=True)
    counts = {
        "quotes": _parse_counts(q_buf.getvalue(), "Quote counts per chapter:"),
        "entities": _parse_counts(e_buf.getvalue(), "Entity counts per chapter:"),
    }
    result: Dict[str, Any] = {
        "work_slug": args.work_slug,
        "pipeline_version": PIPELINE_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "text_hash": text_hash,
        "counts": counts,
    }
    json.dump(result, sys.stdout, ensure_ascii=False)
    sys.stdout.write("\n")


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract")
    ext_sub = extract.add_subparsers(dest="which", required=True)
    common = [
        ("--in", dict(dest="in_path", required=True)),
        ("--work-slug", dict(required=True)),
        ("--out", dict(dest="out_path")),
        ("--emit-manifest", dict(default=None)),
        ("--warns", dict(default=None)),
        ("--determinism-check", dict(action="store_true")),
        ("--stdout", dict(action="store_true")),
    ]

    q_parser = ext_sub.add_parser("quotes")
    for arg, kwargs in common:
        q_parser.add_argument(arg, **kwargs)

    e_parser = ext_sub.add_parser("entities")
    for arg, kwargs in common:
        e_parser.add_argument(arg, **kwargs)

    dry_run = sub.add_parser("dry-run")
    dry_run.add_argument("--in", dest="in_path", required=True)
    dry_run.add_argument("--work-slug", required=True)

    args = parser.parse_args(argv)

    try:
        if args.command == "extract":
            if args.stdout:
                pass
            elif not args.out_path:
                raise SystemExit("--out required unless --stdout is set")
            run_func = run_quotes if args.which == "quotes" else run_entities
            _run_extract(run_func, args)
        elif args.command == "dry-run":
            _cmd_dry_run(args)
        else:
            parser.print_help()
            return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
