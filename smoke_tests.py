from utils import normalize_text
from quotes_extract import extract_quote_spans, extract_em_dash_lines
from ner_extract import build_nlp, extract_entities
import os



def test_quotes():
    text = (
        '“Wake,” said HAL 9000.\r\n'
        '— We shouldn’t be here.\r\n'
        '“No,” she said.\n'
        '“But listen...\n'
        'we can still turn back.”\n'
    )
    norm = normalize_text(text)
    qs = extract_quote_spans(norm)
    kinds = [q["kind"] for q in qs]
    assert sum(k == "quote" for k in kinds) >= 2
    ed = extract_em_dash_lines(norm)
    assert len(ed) == 1


def test_ner_fallback():
    raw = "The Spacing Guild\nCouncil met.\nGalactic Empire"
    text = normalize_text(raw)

    # path 1: normal (spaCy may be present or not)
    nlp = build_nlp()
    ents = extract_entities(nlp, text, chapter_id=2)
    texts = {e["text"] for e in ents}
    assert "The Spacing Guild" in texts
    assert "Galactic Empire" in texts

    # path 2: force pure-Python fallback (no spaCy dependency)
    os.environ["NER_FORCE_PURE"] = "1"
    ents2 = extract_entities(nlp, text, chapter_id=2)
    texts2 = {e["text"] for e in ents2}
    assert "The Spacing Guild" in texts2
    assert "Galactic Empire" in texts2
    os.environ.pop("NER_FORCE_PURE", None)


if __name__ == "__main__":
    test_quotes()
    test_ner_fallback()
    print("Smoke tests passed.")


