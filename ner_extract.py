"""Extract named entities from chapters.jsonl into entities.raw.json."""
import argparse
import os
import re
from typing import List, Dict, Optional, Tuple

try:  # spaCy is optional
    import spacy
except Exception:  # pragma: no cover - runtime dependency
    spacy = None  # type: ignore

from utils import (
    set_seed,
    iter_chapters,
    compute_text_hashes,
    ensure_sorted,
    write_json,
    normalize_text,
    validate_entity_span,
    deterministic_file_hash,
    dedupe_spans,
)

_LIGHT_MIDDLES = {"of", "the", "and"}            # allowed internal connectors
_LEADING_DETS  = {"the", "a", "an"}              # allow as leading determiner
_HEADING_DENY  = {"Chapter", "Prologue", "Epilogue"}  # optional heading denylist
_MAX_TOKENS    = 6                                # cap span length to reduce over-merges

def _cap_spans_in_segment(seg: str, base: int, chapter_id: int) -> List[Dict]:
    """
    Find capitalized multi-token spans in a *single-line* segment.
    - Allow an optional leading determiner (The/A/An) without counting it toward core length.
    - Allow internal 'of/the/and'.
    - Require ≥2 core capitalized tokens.
    - Stop at punctuation or end-of-line.
    - Cap length to _MAX_TOKENS to avoid over-greedy merges.
    """
    spans: List[Dict] = []
    toks = list(re.finditer(r"[A-Za-z]+|\S", seg))
    i = 0
    while i < len(toks):
        tok = toks[i].group(0)
        s = base + toks[i].start()
        e = base + toks[i].end()

        # optional leading determiner
        leading_det = tok.lower() in _LEADING_DETS and tok.istitle()
        if leading_det and i + 1 < len(toks):
            nxt = toks[i+1].group(0)
            nxt_is_cap = nxt[:1].isupper() and nxt.isalpha()
            if nxt_is_cap:
                # start from determiner but core starts at next token
                used: List[Tuple[str,int,int]] = [(tok, s, e)]
                j = i + 1
                core_count = 0
            else:
                leading_det = False  # treat as normal token below

        if not leading_det:
            if not (tok[:1].isupper() and tok.isalpha()):
                i += 1
                continue
            used = [(tok, s, e)]
            j = i + 1
            core_count = 1

        # aggregate up to MAX_TOKENS
        while j < len(toks) and len(used) < _MAX_TOKENS:
            t2 = toks[j].group(0)
            if t2 in {".", "!", "?", "\n"}:
                break
            # allow capitals or light middles
            if (t2[:1].isupper() and t2.isalpha()) or (t2.lower() in _LIGHT_MIDDLES):
                used.append((t2, base + toks[j].start(), base + toks[j].end()))
                if (t2[:1].isupper() and t2.isalpha()) and (t2 not in _HEADING_DENY):
                    core_count += 1
                j += 1
                continue
            break

        # if we had a leading determiner, ensure there are at least 2 capitalized cores after it
        min_core = 2 if leading_det else 2
        # Count core again more explicitly (capitals excluding middles)
        cores = [t for t,_,__ in used if (t[:1].isupper() and t.isalpha()) and (t.lower() not in _LIGHT_MIDDLES)]
        if leading_det:
            # exclude the determiner itself from the core count
            if cores and cores[0].lower() in _LEADING_DETS:
                cores = cores[1:]

        if len(cores) >= min_core:
            span_start, span_end = used[0][1], used[-1][2]
            txt = seg[(span_start - base):(span_end - base)]
            # light label heuristic
            low = txt.lower()
            if any(w in low for w in ("empire","guild","company","council","ministry","federation","conglomerate")):
                label = "ORG"
            elif any(w in low for w in ("system","sector","quadrant","nebula","alpha","beta","orion")):
                label = "LOC"
            else:
                label = "ORG"
            spans.append({
                "chapter_id": chapter_id,
                "start": span_start,
                "end": span_end,
                "text": txt,
                "label": label,
                "source": "capitalized_fallback",
            })
            i = j
        else:
            i += 1

    return spans

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

def ensure_spacy_model() -> Optional["spacy.language.Language"]:
    """Return a loaded spaCy model or a blank pipeline.

    If spaCy or the model is unavailable, return ``None``.
    """
    if spacy is None:
        return None
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        nlp = spacy.blank("en")
        nlp.add_pipe("sentencizer")
    nlp.max_length = 10 ** 7
    return nlp


def build_nlp():
    nlp = ensure_spacy_model()
    if nlp is None:
        return None
    if "ner" in nlp.pipe_names:
        ruler = nlp.add_pipe("entity_ruler", before="ner")
    else:
        ruler = nlp.add_pipe("entity_ruler")
    ruler.add_patterns(TECH_PATTERNS)
    return nlp

def _cap_fallback_on_text(text: str, chapter_id: int) -> List[Dict]:
    spans: List[Dict] = []
    idx = 0
    for line in text.splitlines():
        start = text.find(line, idx)
        if start < 0:
            start = idx
        if line.strip() in _HEADING_DENY:
            idx = start + len(line) + 1
            continue
        spans.extend(_cap_spans_in_segment(line, start, chapter_id))
        idx = start + len(line) + 1  # skip newline
    return spans

def extract_entities(nlp, text: str, chapter_id: int) -> List[Dict]:
    if os.getenv("NER_FORCE_PURE") == "1":
        nlp = None
    spans: List[Dict] = []
    if nlp is not None:
        doc = nlp(text)
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
        # line-aware fallback bounded by sentences
        for sent in getattr(doc, "sents", [doc[:]]):
            sent_text = text[sent.start_char:sent.end_char]
            offset = sent.start_char
            for line in sent_text.splitlines():
                line_start = text.find(line, offset, sent.end_char)
                if line_start == -1:
                    line_start = offset
                if line.strip() in _HEADING_DENY:
                    offset = line_start + len(line) + 1
                    continue
                spans.extend(_cap_spans_in_segment(line, line_start, chapter_id))
                offset = line_start + len(line) + 1
    else:
        spans.extend(_cap_fallback_on_text(text, chapter_id))
    spans = dedupe_spans(spans)
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
    if nlp is None:
        print("spaCy unavailable; basic tests skipped")
        return
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
