"""
Extract dialogue quotes from chapters.jsonl into quotes.raw.json.
"""
import argparse
import re
import time
from collections import defaultdict
from typing import List, Dict, Optional, Tuple, Any

from utils import (
    set_seed,
    iter_chapters,
    compute_text_hashes,
    ensure_sorted,
    write_json_with_normmeta,
    normalize_text,
    validate_quote_span,
    deterministic_file_hash,
    NORMALIZATION_VERSION,
    make_record_id,
    emit_manifest,
    append_jsonl,
    tokenize,
    token_sha,
    char_span_to_token_span,
    token_span_to_char_span,
    build_tei_layer_header,
    write_tei,
)

PIPELINE_VERSION = "0.1.0"

def extract_quote_spans(text: str) -> Tuple[List[Dict], Optional[int]]:
    """
    Robust pairing:
      - smart/straight quotes: “ ” and "
      - nested single quotes allowed inside
      - stitches across paragraphs; avoids common heading/title false positives
    """
    spans: List[Dict] = []
    openers = {'"', '“'}
    closers = {'"', '”'}
    i, n = 0, len(text)
    open_pos = None
    open_char = None

    while i < n:
        ch = text[i]
        if ch in openers:
            # Avoid short heading patterns like: “Chapter 1”
            look = text[i+1:i+8]
            if re.match(r'^\s*(chapter|prologue|epilogue|\d+)\b', look.strip().lower() or ""):
                i += 1
            else:
                if open_pos is None:
                    open_pos, open_char = i, ch
                # else keep first open until a proper closer
        elif ch in closers and open_pos is not None:
            end = i + 1
            spans.append({
                "start": open_pos,
                "end": end,
                "text": text[open_pos:end],
                "kind": "quote",
                "open_char": open_char,
                "close_char": ch,
            })
            open_pos, open_char = None, None
        i += 1
    # We do not emit unterminated quotes to avoid drift.
    return spans, open_pos


def extract_em_dash_lines(text: str) -> List[Dict]:
    pattern = re.compile(r"(?m)^(?:—|-)\s+[^\n]+$")
    out: List[Dict] = []
    for m in pattern.finditer(text):
        start, end = m.span()
        out.append({
            "start": start,
            "end": end,
            "text": text[start:end],
            "kind": "em_dash_dialogue",
            "open_char": None,
            "close_char": None,
        })
    return out

def run(
    in_path: str,
    work_slug: str,
    *,
    emit_tei: Optional[str] = None,
    export_offsets: Optional[str] = None,
    dry_run: bool = False,
    **kwargs,
) -> None:
    t0 = time.perf_counter()
    warns: List[Dict] = []
    chapter_counts: Dict[int, Dict[str, int]] = {}
    set_seed()
    chapters = list(iter_chapters(in_path))
    text_hash = compute_text_hashes(chapters)
    quotes: List[Dict] = []
    tei_annotations: List[Dict] = []
    tokens_by_cid: Dict[int, List[Dict]] = {}
    token_meta: Dict[int, Dict[str, Any]] = {}

    for cid, text in chapters:
        tokens = tokenize(text)
        tokens_by_cid[cid] = tokens
        token_meta[cid] = {"count": len(tokens), "sha": token_sha(tokens)}
        q_spans, open_pos = extract_quote_spans(text)
        spans = q_spans + extract_em_dash_lines(text)
        for span in spans:
            span["chapter_id"] = cid
            span["record_id"] = make_record_id(
                chapter_id=cid,
                start=span["start"],
                end=span["end"],
                kind_or_label=span.get("kind", "quote"),
                text=span["text"],
                pipeline_version=PIPELINE_VERSION,
                normalization_version=NORMALIZATION_VERSION,
            )
            quotes.append(span)
            t_start, t_end = char_span_to_token_span(tokens, span["start"], span["end"])
            payload = {
                "open_char": span.get("open_char"),
                "close_char": span.get("close_char"),
            }
            tei_annotations.append(
                {
                    "chapter_id": cid,
                    "token_span": [t_start, t_end],
                    "text": span["text"],
                    "tag": span.get("kind", "quote"),
                    "source": span.get("source", "regex"),
                    "payload": payload,
                    "record_id": span["record_id"],
                }
            )
        chapter_counts[cid] = {"quotes": len(spans)}
        if open_pos is not None:
            warns.append(
                {
                    "kind": "unmatched_quote_opener",
                    "chapter_id": cid,
                    "position": int(open_pos),
                    "note": "Opening quote without closing delimiter; dropped span.",
                }
            )

    ensure_sorted(quotes)
    tei_annotations.sort(key=lambda a: (a["chapter_id"], a["token_span"][0], a["token_span"][1]))
    for q in quotes:
        validate_quote_span(q)

    if dry_run:
        counts = defaultdict(int)
        for q in quotes:
            counts[q["chapter_id"]] += 1
        print("Quote counts per chapter:")
        for cid in sorted(counts):
            print(f"  {cid}: {counts[cid]}")
        longest = sorted(quotes, key=lambda s: s["end"] - s["start"], reverse=True)[:5]
        print("Top 5 longest spans:")
        for span in longest:
            print(span)
        return

    if emit_tei:
        header = build_tei_layer_header(
            work_slug,
            PIPELINE_VERSION,
            NORMALIZATION_VERSION,
            text_hash,
            "quotes",
            token_meta,
        )
        write_tei(emit_tei, header, tei_annotations)

    if export_offsets:
        legacy: List[Dict] = []
        for ann in tei_annotations:
            cid = ann["chapter_id"]
            start, end = token_span_to_char_span(
                tokens_by_cid[cid], ann["token_span"][0], ann["token_span"][1]
            )
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
        ensure_sorted(legacy)
        result = {
            "work_slug": work_slug,
            "pipeline_version": PIPELINE_VERSION,
            "text_hash": text_hash,
            "quotes": legacy,
        }
        write_json_with_normmeta(export_offsets, result, NORMALIZATION_VERSION)

    t1 = time.perf_counter()
    manifest = {
        "work_slug": work_slug,
        "pipeline_version": PIPELINE_VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "nlp_mode": "regex",
        "duration_sec": round(t1 - t0, 6),
        "counts": {
            "total_quotes": len(quotes),
            "by_chapter": chapter_counts,
        },
        "text_hash": text_hash,
    }
    if kwargs.get("emit_manifest"):
        emit_manifest(kwargs["emit_manifest"], manifest)
    if kwargs.get("warns"):
        for w in warns:
            append_jsonl(kwargs["warns"], w)

def _run_tests():
    text = (
        "“Wake,” said HAL 9000.\r\n"
        "— We shouldn’t be here.\r\n"
        "“No,” she said.\n"
        "“But listen...\n"
        "we can still turn back.”\n"
    )
    norm = normalize_text(text)
    quotes, _ = extract_quote_spans(norm)
    dashes = extract_em_dash_lines(norm)
    assert len(quotes) == 3, quotes
    assert len(dashes) == 1, dashes
    print("quotes_extract tests passed")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--work-slug", required=True)
    ap.add_argument("--emit-tei")
    ap.add_argument("--export-offsets")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--determinism-check", action="store_true", help="Run pipeline twice and assert identical output hash")
    ap.add_argument("--emit-manifest", default=None, help="Path for pipeline.run.json (optional)")
    ap.add_argument("--warns", default=None, help="Path for errors.warn.jsonl (optional)")
    args = ap.parse_args()
    if args.test:
        _run_tests()
        return
    run(
        args.in_path,
        args.work_slug,
        emit_tei=args.emit_tei,
        export_offsets=args.export_offsets,
        dry_run=args.dry_run,
        emit_manifest=args.emit_manifest,
        warns=args.warns,
    )
    target = args.emit_tei or args.export_offsets
    if args.determinism_check and not args.dry_run and target:
        h1 = deterministic_file_hash(target)
        run(
            args.in_path,
            args.work_slug,
            emit_tei=args.emit_tei,
            export_offsets=args.export_offsets,
            dry_run=False,
            emit_manifest=args.emit_manifest,
            warns=args.warns,
        )
        h2 = deterministic_file_hash(target)
        assert h1 == h2, f"Non-deterministic output: {h1} != {h2}"

if __name__ == "__main__":
    main()
