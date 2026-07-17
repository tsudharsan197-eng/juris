from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz
import pytesseract
from pytesseract import Output

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.ocr_service import _text_and_confidence, preprocess_for_ocr
from app.services.pdf_extraction_service import ExtractionSettings, _render_page


SOURCE = ROOT / "tmp/pdfs/ocr-baseline-rental.pdf"
OUTPUT = ROOT / "tmp/pdfs/ocr-baseline-trace"
PSMS = (3, 4, 6, 11, 12)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    settings = ExtractionSettings()
    pdf = fitz.open(SOURCE)
    summaries: list[dict] = []
    try:
        for page_number, page in enumerate(pdf, start=1):
            rendered = _render_page(page, settings)
            processed = preprocess_for_ocr(rendered, settings.max_image_dimension)
            rendered.save(OUTPUT / f"page-{page_number}-original.png")
            processed.save(OUTPUT / f"page-{page_number}-current-preprocessed.png")

            for variant, image in (("original", rendered), ("current", processed)):
                for psm in PSMS:
                    data = pytesseract.image_to_data(
                        image,
                        lang=settings.language,
                        config=f"--oem 1 --psm {psm} -c preserve_interword_spaces=1",
                        output_type=Output.DICT,
                        timeout=90,
                    )
                    result = _text_and_confidence(data)
                    path = OUTPUT / f"page-{page_number}-{variant}-psm-{psm}.txt"
                    path.write_text(result.text, encoding="utf-8")
                    summaries.append(
                        {
                            "page": page_number,
                            "variant": variant,
                            "psm": psm,
                            "characters": len(result.text),
                            "words": len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", result.text)),
                            "lines": len([line for line in result.text.splitlines() if line.strip()]),
                            "confidence": round(result.confidence or 0.0, 4),
                        }
                    )
            rendered.close()
            processed.close()
    finally:
        pdf.close()

    (OUTPUT / "summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    for page_number in range(1, len(pdf) + 1):
        page_rows = [row for row in summaries if row["page"] == page_number]
        best = max(page_rows, key=lambda row: (row["words"], row["confidence"]))
        print(json.dumps(best))


if __name__ == "__main__":
    main()
