from __future__ import annotations

import io
import math
import re
import uuid

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from app import main
from app.services import ocr_service
from app.services.document_processing_service import (
    build_page_aware_chunks,
    validate_chunk_coverage,
)
from app.services.ocr_service import OCRResult, PageVisualMetrics
from app.services.pdf_extraction_service import (
    PageExtraction,
    has_legal_signal,
    is_usable_page_text,
    normalize_page_text,
)


COMPLETE_LEGAL_TEXT = "\n".join(
    [
        "RENTAL AGREEMENT",
        "This Agreement is between T. Karunakaran, Landlord, and Akash Sivadas Menon, Tenant.",
        "The lease starts on 1 August 2024 and ends on 30 June 2025.",
        "1. RENT AND DEPOSIT",
        "The Tenant shall pay monthly rent of Rs. 11,000 on or before day 5.",
        "The refundable security deposit is Rs. 44,000.",
        "4. TERMINATION",
        "Either party may terminate this lease by giving two months written notice.",
    ]
    * 4
)


def _font(size: int = 26):
    try:
        return ImageFont.truetype("DejaVuSans.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def _legal_scan(*, shadow: bool = False) -> Image.Image:
    width, height = 1500, 1900
    if shadow:
        gradient = Image.new("L", (width, height))
        pixels = gradient.load()
        for y in range(height):
            for x in range(width):
                pixels[x, y] = int(245 - 65 * (x / width) + 12 * math.sin(y / 180))
        image = Image.merge("RGB", (gradient, gradient, gradient))
        gradient.close()
    else:
        image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.multiline_text((70, 70), COMPLETE_LEGAL_TEXT, fill="#171717", font=_font(), spacing=11)
    return image


def test_high_quality_page_uses_one_ocr_pass(monkeypatch):
    image = Image.new("RGB", (900, 1200), "white")
    calls = []
    monkeypatch.setattr(ocr_service, "tesseract_available", lambda: True)
    monkeypatch.setattr(ocr_service, "_detect_orientation", lambda *_: (0, 12.0))
    monkeypatch.setattr(
        ocr_service,
        "_recognize_image",
        lambda value, **kwargs: calls.append(kwargs["psm"]) or OCRResult(COMPLETE_LEGAL_TEXT, 0.96),
    )

    result = ocr_service.run_tesseract_ocr(
        image,
        language="eng",
        timeout_seconds=30,
        max_dimension=1600,
    )
    image.close()

    assert calls == [3]
    assert result.attempts == 1
    assert result.preprocessing_variant == "original_rgb"


def test_low_quality_page_evaluates_requested_psm_modes(monkeypatch):
    image = Image.new("RGB", (900, 1200), "white")
    calls = []
    monkeypatch.setattr(ocr_service, "tesseract_available", lambda: True)
    monkeypatch.setattr(ocr_service, "_detect_orientation", lambda *_: (0, 12.0))
    monkeypatch.setattr(
        ocr_service,
        "_recognize_image",
        lambda value, **kwargs: calls.append(kwargs["psm"]) or OCRResult("x x x", 0.12),
    )

    result = ocr_service.run_tesseract_ocr(
        image,
        language="eng",
        timeout_seconds=30,
        max_dimension=1600,
        max_attempts=5,
    )
    image.close()

    assert calls == [3, 4, 6, 11, 12]
    assert result.attempts == 5


def test_dense_page_with_two_lines_is_incomplete_even_at_high_confidence():
    partial = OCRResult(
        "TERMINATION NOTICE\n" + "word " * 34,
        0.93,
        word_count=36,
        line_count=2,
        block_count=1,
        text_box_coverage=0.006,
    )
    enriched = ocr_service._enrich_result(
        partial,
        variant="original_rgb",
        psm=3,
        rotation=0,
        rotation_confidence=9.0,
        deskew_angle=0.0,
        perspective_confidence=None,
        visuals=PageVisualMetrics(ink_ratio=0.08, line_regions=48),
    )
    assert enriched.incomplete is True
    assert ocr_service.result_needs_retry(enriched)


def test_preprocessing_variants_keep_original_and_offer_bounded_recovery_images():
    image = _legal_scan(shadow=True)
    variants, deskew_angle, perspective_confidence = ocr_service._build_preprocessing_variants(image)
    try:
        assert {
            "original_rgb",
            "grayscale_normalized",
            "adaptive_threshold",
            "light_sharpen",
            "deskewed",
            "shadow_normalized",
        }.issubset(variants)
        assert variants["original_rgb"].mode == "RGB"
        assert variants["original_rgb"].size == image.size
        assert variants["adaptive_threshold"].mode == "L"
        assert abs(deskew_angle) <= 4.0
        assert perspective_confidence is None or 0.0 <= perspective_confidence <= 1.0
    finally:
        for variant in variants.values():
            variant.close()
        image.close()


def test_mildly_skewed_text_is_detected_without_extreme_rotation():
    image = Image.new("L", (1200, 900), "white")
    draw = ImageDraw.Draw(image)
    font = _font(24)
    for row in range(12):
        draw.text((90, 80 + row * 55), "Clause 6.2 termination notice and payment obligations", fill="black", font=font)
    skewed = image.rotate(2.0, resample=Image.Resampling.BICUBIC, fillcolor="white")
    corrected, angle = ocr_service._deskew_with_angle(np.asarray(skewed))
    image.close()
    skewed.close()

    assert corrected.shape == (900, 1200)
    assert 0.15 <= abs(angle) <= 4.0


def test_preprocessing_preserves_content_at_page_edges():
    image = Image.new("RGB", (900, 1200), "white")
    draw = ImageDraw.Draw(image)
    draw.text((4, 4), "SECTION 1", fill="black", font=_font(22))
    draw.text((4, 1165), "SIGNED 21-Jan-2025", fill="black", font=_font(22))
    variants, _, _ = ocr_service._build_preprocessing_variants(image)
    try:
        assert variants["original_rgb"].size == image.size
        assert variants["grayscale_normalized"].size == image.size
        assert variants["light_sharpen"].size == image.size
    finally:
        for variant in variants.values():
            variant.close()
        image.close()


def test_debug_mode_saves_candidates_scoring_and_chosen_text(monkeypatch, tmp_path):
    image = Image.new("RGB", (900, 1200), "white")
    monkeypatch.setenv("OCR_DEBUG", "true")
    monkeypatch.setenv("OCR_DEBUG_DIR", str(tmp_path))
    monkeypatch.setattr(ocr_service, "tesseract_available", lambda: True)
    monkeypatch.setattr(ocr_service, "_detect_orientation", lambda *_: (0, 12.0))
    monkeypatch.setattr(
        ocr_service,
        "_recognize_image",
        lambda *args, **kwargs: OCRResult(COMPLETE_LEGAL_TEXT, 0.96),
    )
    ocr_service.run_tesseract_ocr(
        image,
        language="eng",
        timeout_seconds=30,
        max_dimension=1600,
        debug_label="test-page",
    )
    image.close()

    page_dir = tmp_path / "test-page"
    assert (page_dir / "original-render.png").exists()
    assert (page_dir / "grayscale_normalized.png").exists()
    assert (page_dir / "adaptive_threshold.png").exists()
    assert (page_dir / "chosen.txt").exists()
    assert (page_dir / "chosen.json").exists()
    assert (page_dir / "scoring.json").exists()


def test_confident_four_corner_page_can_be_perspective_corrected():
    image = Image.new("RGB", (1200, 900), "#303238")
    draw = ImageDraw.Draw(image)
    corners = [(170, 90), (1070, 145), (1000, 820), (100, 760)]
    draw.polygon(corners, fill="white", outline="black", width=8)
    for y in range(220, 700, 70):
        draw.line((220, y, 930, y + 25), fill="black", width=6)

    corrected, confidence = ocr_service._perspective_correct(image)
    image.close()
    assert corrected is not None
    assert confidence is not None and confidence >= 0.72
    assert corrected.width > 700 and corrected.height > 500
    corrected.close()


def test_normalization_preserves_names_dates_amounts_and_clause_numbers():
    source = (
        "SECTION 6.2 / TERM-AND-RENEWAL\r\n"
        "T. Karunakaran: ₹44,000.50 (INR)\r\n"
        "Notice: 30 days; 21-Jan-2025; 12.5%\r\n"
        "LANDLORD\r\nTENANT"
    )
    normalized = normalize_page_text(source)
    assert "SECTION 6.2" in normalized
    assert "T. Karunakaran" in normalized
    assert "₹44,000.50" in normalized
    assert "21-Jan-2025" in normalized
    assert "12.5%" in normalized
    assert "LANDLORD\nTENANT" in normalized
    assert has_legal_signal(normalized)


@pytest.mark.parametrize(
    "text",
    [
        "LANDLORD\nT. KARUNAKARAN\nWITNESS 1",
        "SECURITY DEPOSIT\nRs. 44,000",
        "SECTION 6.2\n30 DAY NOTICE",
        "SIGNED: 21-Jan-2025",
    ],
)
def test_sparse_legal_labels_are_not_dropped(text):
    assert is_usable_page_text(text, min_characters=80)


def test_chunking_preserves_page_lines_boundaries_and_representative_text():
    sections = []
    for index in range(1, 80):
        sections.append(
            f"{index}. Clause {index}\nThe Tenant shall preserve obligation marker-{index} and pay Rs. {index},000."
        )
    page_text = "\n\n".join(sections)
    page = PageExtraction(1, page_text, "ocr", 0.93, "2026-01-01T00:00:00Z")
    chunks = build_page_aware_chunks([page], chunk_size=700, overlap=120)
    validate_chunk_coverage([page], chunks)

    assert len(chunks) > 5
    assert all(chunk.page_start == chunk.page_end == 1 for chunk in chunks)
    assert any("marker-1" in chunk.text for chunk in chunks)
    assert any("marker-40" in chunk.text for chunk in chunks)
    assert any("marker-79" in chunk.text for chunk in chunks)
    for chunk in chunks[1:]:
        prefix_index = page_text.find(chunk.text[:45])
        assert prefix_index >= 0
        assert prefix_index == 0 or page_text[prefix_index - 1].isspace()


def test_multiple_pages_keep_beginning_middle_and_end_in_separate_source_chunks():
    pages = []
    for page_number in range(1, 4):
        body = " ".join(
            [
                f"PAGE-{page_number}-BEGIN",
                *(f"Clause {index} payment obligation notice" for index in range(80)),
                f"PAGE-{page_number}-END",
            ]
        )
        pages.append(
            PageExtraction(page_number, body, "ocr", 0.91, "2026-01-01T00:00:00Z")
        )
    chunks = build_page_aware_chunks(pages, chunk_size=650, overlap=100)
    validate_chunk_coverage(pages, chunks)

    for page_number in range(1, 4):
        page_chunks = [chunk.text for chunk in chunks if chunk.page_start == page_number]
        combined = " ".join(page_chunks)
        assert f"PAGE-{page_number}-BEGIN" in combined
        assert f"PAGE-{page_number}-END" in combined


@pytest.mark.skipif(not ocr_service.tesseract_available(), reason="Tesseract is not installed")
def test_real_ocr_recovers_names_amounts_dates_and_numbered_clauses():
    image = _legal_scan(shadow=True)
    result = ocr_service.run_tesseract_ocr(
        image,
        language="eng",
        timeout_seconds=45,
        max_dimension=2200,
        max_attempts=8,
    )
    image.close()

    compact = re.sub(r"\s+", " ", result.text).lower()
    assert "karunakaran" in compact
    assert "akash sivadas menon" in compact
    assert re.search(r"44[,.]?000", compact)
    assert "30 june 2025" in compact
    assert "terminate this lease" in compact
    assert result.confidence is not None and result.confidence > 0.65


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _ResetConnection:
    def __init__(self):
        self.queries = []

    def transaction(self):
        return _Transaction()

    async def execute(self, query, *args):
        self.queries.append(" ".join(query.split()))


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _ResetPool:
    def __init__(self):
        self.connection = _ResetConnection()

    def acquire(self):
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_reprocessing_invalidates_stale_text_chunks_and_ai_outputs():
    pool = _ResetPool()
    await main.reset_document_processing_data(pool, str(uuid.uuid4()), str(uuid.uuid4()))
    statements = "\n".join(pool.connection.queries)
    assert "delete from document_chunks" in statements
    assert "delete from document_text" in statements
    assert "delete from ai_outputs" in statements


@pytest.mark.asyncio
async def test_retrieved_ocr_text_reaches_grounded_rag_prompt(monkeypatch):
    document_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    captured = {}
    row = {
        "id": uuid.uuid4(),
        "chunk_index": 7,
        "chunk_text": "The refundable security deposit is Rs. 44,000.",
        "page_start": 2,
        "page_end": 2,
        "extraction_method": "ocr",
        "ocr_confidence": 0.94,
        "distance": 0.12,
    }

    async def owned(*args, **kwargs):
        return {"id": document_id}

    async def embeddings(*args, **kwargs):
        return [[0.01] * main.EMBEDDING_DIMENSIONS]

    async def count(*args, **kwargs):
        return 1

    async def search(*args, **kwargs):
        assert kwargs["limit"] == 3
        return [row]

    async def answer(prompt):
        captured["prompt"] = prompt
        return "The refundable security deposit is Rs. 44,000. [Chunk 7]"

    monkeypatch.setattr(main, "get_owned_document", owned)
    monkeypatch.setattr(main, "generate_embeddings", embeddings)
    monkeypatch.setattr(main, "count_retrievable_document_chunks", count)
    monkeypatch.setattr(main, "search_document_chunks", search)
    monkeypatch.setattr(main, "generate_answer", answer)

    response = await main.ask_document(
        document_id,
        main.AskDocumentRequest(question="What is the security deposit?"),
        user_id,
        object(),
    )
    assert "Rs. 44,000" in captured["prompt"]
    assert response.sources[0].page_number == 2
    assert response.sources[0].extraction_method == "ocr"
