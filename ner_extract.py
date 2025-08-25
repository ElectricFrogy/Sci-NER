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
    validate_entity_span,
    deterministic_file_hash,
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


def _good_cap_token(t):
    return t.text[:1].isupper() and t.is_alpha and t.text.lower() not in STOP_WORDS


_LIGHT_MIDDLES = {"of", "the", "and"}


def _label_guess(txt: str) -> str:
    low = txt.lower()
    if any(w in low for w in ("empire", "guild", "company", "ministry", "consortium", "council")):
        return "ORG"
    if any(w in low for w in ("system", "sector", "quadrant", "nebula", "alpha", "beta", "orion")):
        return "LOC"
    return "ORG"


def extract_capitalized_fallback(doc, chapter_id: int) -> List[Dict]:
    covered = set()
    for ent in doc.ents:
        covered.update(range(ent.start, ent.end))
    spans = []
    for sent in doc.sents:
        i = sent.start
        while i < sent.end:
            tok = doc[i]
            if i in covered or not _good_cap_token(tok):
                i += 1
                continue
            start = i
            j = i + 1
            while j < sent.end:
                t = doc[j]
                if j in covered or t.text == "\n":
                    break
                if _good_cap_token(t) or t.text.lower() in _LIGHT_MIDDLES:
                    j += 1
                else:
                    break
            core = [t for t in doc[start:j] if t.text.lower() not in _LIGHT_MIDDLES]
            if len(core) >= 2:
                span = doc[start:j]
                txt = span.text
                label = _label_guess(txt)
                spans.append({
                    "chapter_id": chapter_id,
                    "start": span.start_char,
                    "end": span.end_char,
                    "text": txt,
                    "label": label,
                    "source": "capitalized_fallback",
                })
                covered.update(range(start, j))
                i = j
            else:
                i += 1
    return spans

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
    fallback_spans = extract_capitalized_fallback(doc, chapter_id)
    spans.extend(fallback_spans)
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
    for e in entities:
        validate_entity_span(e)
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
