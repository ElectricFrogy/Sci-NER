import json
import hashlib
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_json(path: os.PathLike) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-8-sig") as fh:
            return json.load(fh)


def stable_sort_spans(obj: Dict[str, Any], key_name: str) -> None:
    spans = obj.get(key_name)
    if isinstance(spans, list):
        spans.sort(key=lambda s: (s.get("chapter_id"), s.get("start"), s.get("end")))


def _strip(obj: Any) -> None:
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            if k == "duration_sec" or k.startswith("telemetry"):
                obj.pop(k)
            else:
                _strip(obj[k])
    elif isinstance(obj, list):
        for item in obj:
            _strip(item)


def strip_nondeterminism(obj: Dict[str, Any]) -> None:
    _strip(obj)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def try_jsonschema_validate(obj: Dict[str, Any], schema_path: os.PathLike) -> Tuple[str, str]:
    path = Path(schema_path)
    if not path.exists():
        return "skip", f"missing schema: {path}"
    try:
        import jsonschema  # type: ignore
    except Exception:
        return "skip", "jsonschema not installed"
    with open(path, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
    import jsonschema
    jsonschema.validate(obj, schema)
    return "ok", f"validated {path.name}"
