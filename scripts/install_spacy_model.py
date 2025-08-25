import sys, time

def main():
    try:
        import spacy
    except Exception:
        print("[model] spaCy not available; skipping model download")
        return 0

    try:
        spacy.load("en_core_web_sm")
        print("[model] en_core_web_sm already installed")
        return 0
    except Exception:
        pass

    try:
        from spacy.cli import download
    except Exception:
        print("[model] spacy.cli.download unavailable; skipping")
        return 0

    for attempt in range(3):
        try:
            print(f"[model] downloading en_core_web_sm (attempt {attempt+1}/3)")
            download("en_core_web_sm")
            spacy.load("en_core_web_sm")
            print("[model] en_core_web_sm installed")
            return 0
        except Exception as e:
            print(f"[model] download failed: {e}")
            time.sleep(2)

    print("[model] giving up; runtime will fall back deterministically")
    return 0

if __name__ == "__main__":
    sys.exit(main())
