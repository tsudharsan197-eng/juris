from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.pdf_extraction_service import (
    ExtractionSettings,
    extract_hybrid_pdf,
    inspect_native_pdf,
)


def main() -> None:
    source = ROOT / "tmp/pdfs/ocr-baseline-rental.pdf"
    output = ROOT / "tmp/pdfs/ocr-after"
    output.mkdir(parents=True, exist_ok=True)
    contents = source.read_bytes()
    settings = ExtractionSettings(timeout_seconds=240)
    inspection = inspect_native_pdf(contents, settings)
    result = extract_hybrid_pdf(
        contents,
        inspection,
        settings,
        debug_label="failing-rental",
    )
    metadata = []
    for page in result.pages:
        (output / f"page-{page.page_number}.txt").write_text(page.text, encoding="utf-8")
        details = asdict(page)
        details.pop("text", None)
        details["characters"] = len(page.text)
        metadata.append(details)
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
