"""Extract named entities from chapters.jsonl into entities.raw.json."""
import argparse
import re
from typing import List, Dict

import spacy
from spacy.pipeline import EntityRuler
from spacy.lang.en.stop_words import STOP_WORDS

from utils import (
    set_seed,
    iter_chapters,
    compute_text_hashes,
    ensure_sorted,
    write_json,
    normalize_text,
)

TECH_PATTERNS = [
  {"label":"TECH","pattern":[{"LOWER":"ftl"}],"id":"ruler"},
  {"label":"TECH","pattern":"warp drive","id":"ruler"},
  {"label":"TECH","pattern":"hyperspace","id":"ruler"},
  {"label":"PRODUCT","pattern":"HAL 9000","id":"ruler"},
  {"label":"SUBSTANCE","pattern":"spice","id":"ruler"},
  {"label":"OCCUPATION","pattern":"mentat","id":"ruler"},
  {"label":"TECH","pattern":"ansible","id":"ruler"},
  {"label":"EVENT","pattern":"jump","id":"ruler"},
  {"label":"TECH","pattern":"terraforming","id":"ruler"},
  {"label":"ORG","pattern":"spacing guild","id":"ruler"},
  {"label":"ORG","pattern":"galactic empire","id":"ruler"},
]

def build_nlp():
    nlp = spacy.load("en_core_web_sm")
    nlp.max_length = 10 ** 7
    ruler = nlp.add_pipe("entity_ruler", before="ner")
    ruler.add_patterns(TECH_PATTERNS)
    return nlp

def extract_entities(nlp, text: str, chapter_id: int) -> List[Dict]:
    doc = nlp(text)
    spans: List[Dict] = []
    for ent in doc.ents:
        source = "ruler" if ent.ent_id_ == "ruler" else "spacy"
        spans.append({
            "chapter_id": chapter_id,
            "start": ent.start_char,
            "end": ent.end_char,
            "text": ent.text,
            "label": ent.label_,
            "source": source,
        })
    covered = set()
    for ent in doc.ents:
        covered.update(range(ent.start, ent.end))
    i = 0
    while i < len(doc):
        if i in covered:
            i += 1
            continue
        token = doc[i]
        if token.text[0].isupper() and token.text.lower() not in STOP_WORDS:
            start = i
            j = i + 1
            while j < len(doc):
                t = doc[j]
                if j in covered or not t.text[0].isupper() or t.text.lower() in STOP_WORDS:
                    break
                j += 1
            if j - start >= 2:
                span = doc[start:j]
                spans.append({
                    "chapter_id": chapter_id,
                    "start": span.start_char,
                    "end": span.end_char,
                    "text": span.text,
                    "label": "ORG",
                    "source": "capitalized_fallback",
                })
                covered.update(range(start, j))
                i = j
                continue
        i += 1
    return spans

def run(in_path: str, out_path: str, work_slug: str, dry_run: bool=False):
    set_seed()
    nlp = build_nlp()
    chapters = list(iter_chapters(in_path))
    hashes = compute_text_hashes(chapters)
    entities: List[Dict] = []
    for cid, text in chapters:
        entities.extend(extract_entities(nlp, text, cid))
    ensure_sorted(entities)
    result = {
        "work_slug": work_slug,
        "pipeline_version": "0.1.0",
        "text_hash": hashes,
        "entities": entities,
    }
    if dry_run:
        counts = {}
        for e in entities:
            counts[e["chapter_id"]] = counts.get(e["chapter_id"],0)+1
        print("Entity counts per chapter:")
        for cid in sorted(counts):
            print(f"  {cid}: {counts[cid]}")
        longest = sorted(entities, key=lambda s: s["end"] - s["start"], reverse=True)[:5]
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
    nlp = build_nlp()
    ents = extract_entities(nlp, norm, 1)
    assert any(e["text"] == "HAL 9000" and e["label"] == "PRODUCT" and e["source"] == "ruler" for e in ents)
    assert all("she" not in e["text"].lower() for e in ents)
    print("ner_extract tests passed")

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
