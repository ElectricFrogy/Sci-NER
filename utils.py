"""Shared utilities for text normalization, hashing, IO, and determinism."""
import json
import hashlib
import random
import unicodedata
from typing import Iterable, Tuple, Dict, List, Any

try:  # numpy is optional in some environments
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - fall back if numpy missing
    np = None

FIXED_SEED = 1337
# === Normalization contract (version your normalization policy) ===
NORMALIZATION_VERSION = "nfc-crlf2lf-v1"

def set_seed() -> None:
    """Seed random number generators for determinism."""
    random.seed(FIXED_SEED)
    if np is not None:
        np.random.seed(FIXED_SEED)
    try:  # optional dependency
        import torch
        torch.manual_seed(FIXED_SEED)
    except Exception:
        pass

def normalize_text(text: str) -> str:
    """Apply canonical normalization to input text."""
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = unicodedata.normalize("NFC", text)
    return text

def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def iter_chapters(path: str) -> Iterable[Tuple[int, str]]:
    """Yield (chapter_id, normalized_text) from a JSONL file."""
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            cid = int(obj["chapter_id"])
            text = normalize_text(obj["text"])
            yield cid, text

def compute_text_hashes(chapters: List[Tuple[int, str]]) -> Dict[str, Dict[str, str]]:
    per = {str(cid): sha256_hex(text) for cid, text in chapters}
    corpus_concat = "\n".join(text for cid, text in sorted(chapters, key=lambda x: x[0]))
    return {"per_chapter": per, "full_corpus": sha256_hex(corpus_concat)}

TOK_VERSION = "tok-v1"

def tokenize(normalized_text: str) -> List[Dict[str, int | str]]:
    """Deterministic whitespace/punctuation tokenizer.

    - Contiguous letters/digits form a token.
    - Each punctuation mark is a standalone token (including em-dash).
    - Whitespace boundaries are dropped.
    - Returns 0-based half-open character offsets.
    """
    tokens: List[Dict[str, int | str]] = []
    i = 0
    n = len(normalized_text)
    while i < n:
        ch = normalized_text[i]
        if ch.isspace():
            i += 1
            continue
        start = i
        if ch.isalnum():
            while i < n and normalized_text[i].isalnum():
                i += 1
            tokens.append({"text": normalized_text[start:i], "start": start, "end": i})
        else:
            tokens.append({"text": ch, "start": start, "end": start + 1})
            i += 1
    return tokens

def token_sha(tokens: List[Dict[str, int | str]]) -> str:
    return sha256_hex("\n".join(str(t["text"]) for t in tokens))

def char_span_to_token_span(tokens: List[Dict[str, int]], start: int, end: int) -> Tuple[int, int]:
    """Map character offsets to token index span.

    If ``start`` or ``end`` fall inside a token, expand to include that token.
    ``end`` is half-open.
    """
    if start < 0 or end > (tokens[-1]["end"] if tokens else 0):
        raise ValueError("char span outside tokenized text")
    t_start = 0
    while t_start < len(tokens) and tokens[t_start]["end"] <= start:
        t_start += 1
    t_end = t_start
    while t_end < len(tokens) and tokens[t_end]["start"] < end:
        t_end += 1
    return t_start, t_end

def token_span_to_char_span(tokens: List[Dict[str, int]], t_start: int, t_end: int) -> Tuple[int, int]:
    if not (0 <= t_start <= t_end <= len(tokens)):
        raise ValueError("token span out of range")
    if t_start == t_end:
        return 0, 0
    start = tokens[t_start]["start"]
    end = tokens[t_end - 1]["end"]
    return start, end

def build_tei_layer_header(
    work_slug: str,
    pipeline_version: str,
    normalization_version: str,
    text_hash: Dict[str, Dict[str, str]],
    layer_name: str,
    token_meta_per_chapter: Dict[int, Dict[str, str | int]],
) -> Dict[str, Any]:
    return {
        "work_slug": work_slug,
        "pipeline_version": pipeline_version,
        "normalization_version": normalization_version,
        "text_hash": text_hash,
        "tokenization": {
            "algo": TOK_VERSION,
            "version": TOK_VERSION,
            "per_chapter": {str(k): v for k, v in token_meta_per_chapter.items()},
        },
        "layer": layer_name,
    }

def write_tei(path: str, header_dict: Dict[str, Any], annotations_list: List[Dict[str, Any]]) -> None:
    obj = dict(header_dict)
    obj["annotations"] = annotations_list
    write_json(path, obj)

def ensure_sorted(spans: List[Dict]) -> None:
    spans.sort(key=lambda s: (s["chapter_id"], s["start"], s["end"]))

def write_json(path: str, data: Dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=False)


def validate_quote_span(span: Dict) -> None:
    assert isinstance(span.get("chapter_id"), int)
    s, e = span.get("start"), span.get("end")
    assert isinstance(s, int) and isinstance(e, int) and 0 <= s < e
    assert isinstance(span.get("text"), str)
    assert span.get("kind") in {"quote", "em_dash_dialogue", "blockquote_guess"}
    # optional: open/close can be None or str
    oc = span.get("open_char")
    cc = span.get("close_char")
    assert (oc is None or isinstance(oc, str)) and (cc is None or isinstance(cc, str))


def validate_entity_span(span: Dict) -> None:
    assert isinstance(span.get("chapter_id"), int)
    s, e = span.get("start"), span.get("end")
    assert isinstance(s, int) and isinstance(e, int) and 0 <= s < e
    assert isinstance(span.get("text"), str)
    assert isinstance(span.get("label"), str)
    assert span.get("source") in {"spacy", "ruler", "capitalized_fallback"}


def deterministic_file_hash(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()

# === DEDUPE HELPERS (append near end of utils.py) ===
from typing import List, Dict, Tuple

def _span_key(span: Dict) -> Tuple[int, int, str]:
    # key insensitive to 'source'; prefer to keep one span per (start,end,text)
    return (span["start"], span["end"], span["text"])

def dedupe_spans(spans: List[Dict]) -> List[Dict]:
    """Deterministic de-duplication by (start,end,text).
    If duplicates exist with different 'source', keep non-fallback over fallback (prefer 'spacy'/'ruler').
    Preserve original order among distinct keys.
    """
    best_by_key = {}
    order = []
    for s in spans:
        k = _span_key(s)
        if k not in best_by_key:
            best_by_key[k] = s
            order.append(k)
        else:
            cur = best_by_key[k]
            # prefer non-fallback if available
            cur_is_fallback = cur.get("source") == "capitalized_fallback"
            new_is_fallback = s.get("source") == "capitalized_fallback"
            if cur_is_fallback and not new_is_fallback:
                best_by_key[k] = s
            # else keep existing deterministically
    return [best_by_key[k] for k in order]

# === Stable identifiers & writing helpers ===
import hashlib, json, os, time
from typing import Dict, List, Tuple, Optional, Any

def _sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def make_record_id(
    chapter_id: int,
    start: int,
    end: int,
    kind_or_label: str,
    text: str,
    pipeline_version: str,
    normalization_version: str,
) -> str:
    """
    Stable ID over the normalized text space and span metadata.
    IMPORTANT: text must be from the normalized chapter string at [start:end].
    """
    payload = "\n".join([
        f"cid={chapter_id}",
        f"s={start}",
        f"e={end}",
        f"k={kind_or_label}",
        f"txt={text}",
        f"pver={pipeline_version}",
        f"nver={normalization_version}",
    ])
    return _sha256_hex(payload)

def write_json_with_normmeta(path: str, obj: Dict, normalization_version: str) -> None:
    obj = dict(obj)  # shallow copy
    obj.setdefault("normalization_version", normalization_version)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

def append_jsonl(path: str, rec: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

def emit_manifest(path: str, manifest: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

