"""Shared utilities for text normalization, hashing, IO, and determinism."""
import json
import hashlib
import random
import unicodedata
from typing import Iterable, Tuple, Dict, List

try:  # numpy is optional in some environments
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover - fall back if numpy missing
    np = None

FIXED_SEED = 1337

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

def ensure_sorted(spans: List[Dict]) -> None:
    spans.sort(key=lambda s: (s["chapter_id"], s["start"], s["end"]))

def write_json(path: str, data: Dict) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=False)
