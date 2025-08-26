import argparse
import json
import os
import sys
import tempfile
import contextlib
import io
from typing import Any, Callable, Dict, List

from quotes_extract import run as run_quotes
from ner_extract import run as run_entities
from utils import (
    compute_text_hashes,
    iter_chapters,
    NORMALIZATION_VERSION,
    deterministic_file_hash,
    tokenize,
    token_sha,
    token_span_to_char_span,
    ensure_sorted,
    write_json_with_normmeta,
)

PIPELINE_VERSION = "0.1.0"


def _emit_stdout_path(path: str) -> None:
    with open(path, "rb") as fh:
        data = fh.read()
    sys.stdout.buffer.write(data)
    if not data.endswith(b"\n"):
        sys.stdout.buffer.write(b"\n")


def _run_extract(run_func: Callable[..., Any], args: argparse.Namespace) -> None:
    tei_path = args.emit_tei
    if args.stdout and not tei_path:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tei_path = tmp.name
        tmp.close()
    run_func(
        args.in_path,
        args.work_slug,
        emit_tei=tei_path,
        export_offsets=args.export_offsets,
        dry_run=False,
        emit_manifest=args.emit_manifest,
        warns=args.warns,
    )
    target = tei_path or args.export_offsets
    if args.determinism_check and target:
        h1 = deterministic_file_hash(target)
        run_func(
            args.in_path,
            args.work_slug,
            emit_tei=tei_path,
            export_offsets=args.export_offsets,
            dry_run=False,
            emit_manifest=args.emit_manifest,
            warns=args.warns,
        )
        h2 = deterministic_file_hash(target)
        if h1 != h2:
            raise RuntimeError(f"Non-deterministic output: {h1} != {h2}")
    if args.stdout and tei_path:
        _emit_stdout_path(tei_path)
        os.unlink(tei_path)


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
        run_quotes(args.in_path, args.work_slug, dry_run=True)
    e_buf = io.StringIO()
    with contextlib.redirect_stdout(e_buf):
        run_entities(args.in_path, args.work_slug, dry_run=True)
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


def _cmd_export_offsets(args: argparse.Namespace) -> None:
    with open(args.tei, "r", encoding="utf-8") as fh:
        tei = json.load(fh)
    layer = tei.get("layer")
    chapters = {cid: text for cid, text in iter_chapters(args.in_path)}
    token_meta = tei.get("tokenization", {}).get("per_chapter", {})
    legacy: List[Dict[str, Any]] = []
    for ann in tei.get("annotations", []):
        cid = ann["chapter_id"]
        tokens = tokenize(chapters[cid])
        meta = token_meta.get(str(cid))
        if meta and token_sha(tokens) != meta.get("sha"):
            raise RuntimeError(f"Token SHA mismatch for chapter {cid}")
        start, end = token_span_to_char_span(tokens, ann["token_span"][0], ann["token_span"][1])
        if layer == "quotes":
            legacy.append(
                {
                    "chapter_id": cid,
                    "start": start,
                    "end": end,
                    "text": ann["text"],
                    "kind": ann["tag"],
                    "open_char": ann.get("payload", {}).get("open_char"),
                    "close_char": ann.get("payload", {}).get("close_char"),
                    "record_id": ann["record_id"],
                }
            )
        else:
            legacy.append(
                {
                    "chapter_id": cid,
                    "start": start,
                    "end": end,
                    "text": ann["text"],
                    "label": ann["tag"],
                    "source": ann["source"],
                    "record_id": ann["record_id"],
                }
            )
    ensure_sorted(legacy)
    out_obj = {
        "work_slug": tei["work_slug"],
        "pipeline_version": tei["pipeline_version"],
        "text_hash": tei["text_hash"],
        layer: legacy,
    }
    write_json_with_normmeta(args.out, out_obj, tei.get("normalization_version", NORMALIZATION_VERSION))


def main(argv: Any = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract")
    ext_sub = extract.add_subparsers(dest="which", required=True)
    common = [
        ("--in", dict(dest="in_path", required=True)),
        ("--work-slug", dict(required=True)),
        ("--emit-tei", dict(dest="emit_tei")),
        ("--export-offsets", dict(dest="export_offsets")),
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

    export = sub.add_parser("export")
    exp_sub = export.add_subparsers(dest="which", required=True)
    off_parser = exp_sub.add_parser("offsets")
    off_parser.add_argument("--tei", required=True)
    off_parser.add_argument("--out", required=True)
    off_parser.add_argument("--in", dest="in_path", required=True)

    dry_run = sub.add_parser("dry-run")
    dry_run.add_argument("--in", dest="in_path", required=True)
    dry_run.add_argument("--work-slug", required=True)

    args = parser.parse_args(argv)

    try:
        if args.command == "extract":
            if not (args.emit_tei or args.export_offsets or args.stdout):
                raise SystemExit("no output specified")
            run_func = run_quotes if args.which == "quotes" else run_entities
            _run_extract(run_func, args)
        elif args.command == "dry-run":
            _cmd_dry_run(args)
        elif args.command == "export" and args.which == "offsets":
            _cmd_export_offsets(args)
        else:
            parser.print_help()
            return 1
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
