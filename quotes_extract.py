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
)

quote_open = {'"', '“'}
quote_close = {'"', '”'}

def extract_quote_spans(text: str) -> List[Dict]:
    spans: List[Dict] = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch in quote_open:
            open_char = ch
            start = i
            i += 1
            while i < n and text[i] not in quote_close:
                i += 1
            if i < n:
                close_char = text[i]
                end = i + 1
                spans.append({
                    "start": start,
                    "end": end,
                    "text": text[start:end],
                    "kind": "quote",
                    "open_char": open_char,
                    "close_char": close_char,
                })
                i = end
                continue
            else:
                break
        i += 1
    return spans

def extract_em_dash_lines(text: str) -> List[Dict]:
    pattern = re.compile(r"(?m)^(?:—|-)\s+[A-Z0-9“\"].+")
    spans: List[Dict] = []
    for m in pattern.finditer(text):
        start, end = m.span()
        spans.append({
            "start": start,
            "end": end,
            "text": text[start:end],
            "kind": "em_dash_dialogue",
            "open_char": None,
            "close_char": None,
        })
    return spans

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
    args = ap.parse_args()
    if args.test:
        _run_tests()
        return
    run(args.in_path, args.out_path, args.work_slug, args.dry_run)

if __name__ == "__main__":
    main()
