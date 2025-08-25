"""
Extract dialogue quotes from chapters.jsonl into quotes.raw.json.
"""
import argparse
import re
from collections import defaultdict
from typing import List, Dict

from utils import (
    set_seed,
    iter_chapters,
    compute_text_hashes,
    ensure_sorted,
    write_json,
    normalize_text,
    validate_quote_span,
    deterministic_file_hash,
)

def extract_quote_spans(text: str) -> List[Dict]:
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
    return spans


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

def run(in_path: str, out_path: str, work_slug: str, dry_run: bool = False):
    set_seed()
    chapters = list(iter_chapters(in_path))
    hashes = compute_text_hashes(chapters)
    quotes: List[Dict] = []
    for cid, text in chapters:
        spans = extract_quote_spans(text) + extract_em_dash_lines(text)
        for span in spans:
            span["chapter_id"] = cid
        quotes.extend(spans)
    ensure_sorted(quotes)
    for q in quotes:
        validate_quote_span(q)
    result = {
        "work_slug": work_slug,
        "pipeline_version": "0.1.0",
        "text_hash": hashes,
        "quotes": quotes,
    }
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
    else:
        write_json(out_path, result)

def _run_tests():
    text = (
        "“Wake,” said HAL 9000.\r\n"
        "— We shouldn’t be here.\r\n"
        "“No,” she said.\n"
        "“But listen...\n"
        "we can still turn back.”\n"
    )
    norm = normalize_text(text)
    quotes = extract_quote_spans(norm)
    dashes = extract_em_dash_lines(norm)
    assert len(quotes) == 3, quotes
    assert len(dashes) == 1, dashes
    print("quotes_extract tests passed")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", required=True)
    ap.add_argument("--out", dest="out_path", required=True)
    ap.add_argument("--work-slug", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--determinism-check", action="store_true", help="Run pipeline twice and assert identical output hash")
    args = ap.parse_args()
    if args.test:
        _run_tests()
        return
    run(args.in_path, args.out_path, args.work_slug, args.dry_run)
    if args.determinism_check and not args.dry_run:
        h1 = deterministic_file_hash(args.out_path)
        run(args.in_path, args.out_path, args.work_slug, dry_run=False)
        h2 = deterministic_file_hash(args.out_path)
        assert h1 == h2, f"Non-deterministic output: {h1} != {h2}"

if __name__ == "__main__":
    main()
