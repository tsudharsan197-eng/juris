from __future__ import annotations

import io
import textwrap
import uuid
from datetime import datetime, timezone

import fitz
import pytest
from fastapi import HTTPException
from PIL import Image, ImageDraw, ImageFont

from app import main
from app.services.document_processing_service import (
    DocumentChunk,
    build_page_aware_chunks,
    page_metadata,
    validate_chunks,
)
from app.services.ocr_service import OCRResult, OCRUnavailableError
from app.services import ocr_service
from app.services.pdf_extraction_service import (
    ExtractionSettings,
    NativePdfInspection,
    PageExtraction,
    PdfExtractionResult,
    extract_hybrid_pdf,
    inspect_native_pdf,
    is_usable_page_text,
    validate_pdf_extraction,
)


LEGAL_TEXT = (
    "MASTER SERVICE AGREEMENT between Meridian Advisory LLC and Northstar Systems. "
    "The client shall pay all invoices within thirty days. The agreement renews for "
    "twelve months unless either party gives written notice before the renewal date."
)


def _digital_pdf(*page_texts: str) -> bytes:
    pdf = fitz.open()
    for text in page_texts:
        page = pdf.new_page(width=612, height=792)
        page.insert_textbox(fitz.Rect(54, 54, 558, 738), text, fontsize=11)
    contents = pdf.tobytes()
    pdf.close()
    return contents


def _scanned_page_png(text: str = LEGAL_TEXT) -> bytes:
    image = Image.new("RGB", (1400, 1800), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=32)
    draw.multiline_text(
        (90, 120),
        "\n".join(textwrap.wrap(text, width=58)),
        fill="black",
        font=font,
        spacing=18,
    )
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    image.close()
    return buffer.getvalue()


def _image_pdf(page_count: int = 1) -> bytes:
    image_bytes = _scanned_page_png()
    pdf = fitz.open()
    for _ in range(page_count):
        page = pdf.new_page(width=612, height=792)
        page.insert_image(page.rect, stream=image_bytes)
    contents = pdf.tobytes()
    pdf.close()
    return contents


def _mixed_pdf() -> bytes:
    image_bytes = _scanned_page_png()
    pdf = fitz.open()
    native = pdf.new_page(width=612, height=792)
    native.insert_textbox(fitz.Rect(54, 54, 558, 738), LEGAL_TEXT, fontsize=11)
    scanned = pdf.new_page(width=612, height=792)
    scanned.insert_image(scanned.rect, stream=image_bytes)
    contents = pdf.tobytes()
    pdf.close()
    return contents


@pytest.fixture
def settings() -> ExtractionSettings:
    return ExtractionSettings(
        dpi=150,
        min_page_characters=80,
        timeout_seconds=30,
        max_pages=10,
        max_image_dimension=1800,
        max_image_pixels=4_000_000,
    )


def test_text_pdf_skips_ocr(settings):
    contents = _digital_pdf(LEGAL_TEXT)
    inspection = inspect_native_pdf(contents, settings)
    assert inspection.unreadable_pages == ()

    def unexpected_ocr(*args, **kwargs):
        raise AssertionError("OCR must not run for a readable native-text page")

    result = extract_hybrid_pdf(contents, inspection, settings, ocr_engine=unexpected_ocr)
    assert result.pages[0].extraction_method == "native"
    assert "Meridian Advisory" in result.pages[0].text


def test_image_only_pdf_triggers_ocr(settings):
    contents = _image_pdf()
    inspection = inspect_native_pdf(contents, settings)
    calls = []

    def fake_ocr(image, **kwargs):
        calls.append((image.size, kwargs["language"]))
        return OCRResult(LEGAL_TEXT, 0.94)

    result = extract_hybrid_pdf(contents, inspection, settings, ocr_engine=fake_ocr)
    validate_pdf_extraction(result)
    assert inspection.unreadable_pages == (1,)
    assert calls and calls[0][1] == "eng"
    assert result.pages[0].extraction_method == "ocr"
    assert result.pages[0].ocr_confidence == pytest.approx(0.94)


def test_low_confidence_ocr_retries_page_orientation(monkeypatch):
    image = Image.new("RGB", (800, 600), "white")
    results = iter(
        [
            OCRResult("unreadable fragments", 0.14),
            OCRResult(LEGAL_TEXT, 0.95),
        ]
    )
    calls = []

    monkeypatch.setattr(ocr_service, "tesseract_available", lambda: True)
    monkeypatch.setattr(ocr_service, "_detect_orientation", lambda value, timeout: (0, 12.0))
    monkeypatch.setattr(
        ocr_service,
        "_recognize_image",
        lambda value, **kwargs: calls.append(value.size) or next(results),
    )

    result = ocr_service.run_tesseract_ocr(
        image,
        language="eng",
        timeout_seconds=30,
        max_dimension=1200,
    )
    image.close()

    assert len(calls) == 2
    assert result.text == LEGAL_TEXT
    assert result.confidence == pytest.approx(0.95)


def test_mixed_pdf_ocrs_only_unreadable_pages(settings):
    contents = _mixed_pdf()
    inspection = inspect_native_pdf(contents, settings)
    ocr_pages = []

    def fake_ocr(image, **kwargs):
        ocr_pages.append(image.size)
        return OCRResult(LEGAL_TEXT, 0.91)

    result = extract_hybrid_pdf(contents, inspection, settings, ocr_engine=fake_ocr)
    assert inspection.unreadable_pages == (2,)
    assert len(ocr_pages) == 1
    assert [page.extraction_method for page in result.pages] == ["native", "ocr"]


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   \n\t ",
        "--- Page 1 ---\n--- Page 2 ---",
        "A" * 200,
        "corrupt " * 80,
    ],
)
def test_separator_empty_and_corrupt_text_fails_validation(text):
    assert not is_usable_page_text(text)


def test_empty_chunks_are_never_accepted_for_embedding():
    pages = (
        PageExtraction(1, "--- Page 1 ---", "native", None, "2026-01-01T00:00:00Z"),
    )
    chunks = build_page_aware_chunks(pages)
    assert chunks == []
    with pytest.raises(ValueError, match="No valid document chunks"):
        validate_chunks(chunks)


def test_page_metadata_and_ocr_source_page_are_preserved():
    result = PdfExtractionResult(
        (
            PageExtraction(1, LEGAL_TEXT, "native", None, "2026-01-01T00:00:00Z"),
            PageExtraction(2, LEGAL_TEXT, "ocr", 0.88, "2026-01-01T00:00:01Z"),
        )
    )
    chunks = build_page_aware_chunks(result.pages)
    metadata = page_metadata(result)
    ocr_chunk = next(chunk for chunk in chunks if chunk.page_start == 2)
    prompt_block = main.chunk_prompt_block(
        {
            "chunk_index": ocr_chunk.chunk_index,
            "chunk_text": ocr_chunk.text,
            "page_start": ocr_chunk.page_start,
            "page_end": ocr_chunk.page_end,
        }
    )

    assert metadata[1]["extraction_method"] == "ocr"
    assert metadata[1]["ocr_confidence"] == pytest.approx(0.88)
    assert ocr_chunk.extraction_method == "ocr"
    assert "Page 2" in prompt_block


def test_document_record_decodes_asyncpg_json_string():
    document_id = uuid.uuid4()
    user_id = uuid.uuid4()
    record = main.document_record(
        {
            "id": document_id,
            "user_id": user_id,
            "title": "Scanned agreement",
            "file_name": "scan.pdf",
            "file_key": "users/test/scan.pdf",
            "file_size": 1024,
            "mime_type": "application/pdf",
            "storage_provider": "cloudflare_r2",
            "status": "processed",
            "processing_error": None,
            "low_confidence_pages": [],
            "extraction_metadata": '{"ocrPages":[1],"chunkCount":1}',
            "created_at": datetime.now(timezone.utc),
        }
    )
    assert record.extraction_metadata == {"ocrPages": [1], "chunkCount": 1}


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _MemoryConnection:
    def __init__(self):
        self.chunks = []

    def transaction(self):
        return _Transaction()

    async def execute(self, query, *args):
        if "delete from document_chunks" in query:
            self.chunks = []

    async def executemany(self, query, rows):
        self.chunks.extend(rows)


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _ChunkPool:
    def __init__(self):
        self.connection = _MemoryConnection()

    def acquire(self):
        return _Acquire(self.connection)


@pytest.mark.asyncio
async def test_reprocessing_replaces_invalid_chunks_and_is_idempotent():
    pool = _ChunkPool()
    pool.connection.chunks = [("old", "--- Page 1 ---")]
    document_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    chunk = DocumentChunk(0, LEGAL_TEXT, 1, 1, "ocr", 0.93)
    embeddings = [[0.01] * main.EMBEDDING_DIMENSIONS]

    await main.save_document_chunks(pool, document_id, user_id, [chunk], embeddings)
    assert len(pool.connection.chunks) == 1
    assert pool.connection.chunks[0][3] == LEGAL_TEXT

    await main.save_document_chunks(pool, document_id, user_id, [chunk], embeddings)
    assert len(pool.connection.chunks) == 1
    assert pool.connection.chunks[0][3] == LEGAL_TEXT


class _ProcessingPool(_ChunkPool):
    def __init__(self):
        super().__init__()
        self.statuses = []

    async def fetchrow(self, query, *args):
        status_value = args[2]
        self.statuses.append(status_value)
        return {
            "id": args[0],
            "user_id": args[1],
            "title": "Scanned agreement",
            "file_name": "scan.pdf",
            "file_key": "private/scan.pdf",
            "file_size": 1024,
            "mime_type": "application/pdf",
            "storage_provider": "cloudflare_r2",
            "status": status_value,
            "processing_error": args[3],
            "low_confidence_pages": args[4],
            "extraction_metadata": {},
            "created_at": None,
        }


@pytest.mark.asyncio
async def test_document_is_not_processed_before_validation(monkeypatch):
    pool = _ProcessingPool()
    document_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    inspection = NativePdfInspection(("",), (1,))
    invalid_result = PdfExtractionResult(
        (PageExtraction(1, "", "unreadable", None, "2026-01-01T00:00:00Z", "ocr_text_not_usable"),)
    )
    monkeypatch.setattr(main, "inspect_native_pdf", lambda *args: inspection)
    monkeypatch.setattr(main, "extract_hybrid_pdf", lambda *args, **kwargs: invalid_result)
    monkeypatch.setattr(main, "generate_embeddings", lambda *args: pytest.fail("embeddings must not run"))

    row = await main.process_pdf_document(
        pool=pool,
        document_id=document_id,
        user_id=user_id,
        contents=b"%PDF-test",
        already_claimed=True,
    )
    assert row["status"] == "needs_review"
    assert "could not read this scan clearly" in row["processing_error"].lower()
    assert "processed" not in pool.statuses
    assert "embedding" not in pool.statuses


@pytest.mark.asyncio
async def test_reprocessing_checks_ownership_before_r2(monkeypatch):
    async def missing_document(*args, **kwargs):
        return None

    monkeypatch.setattr(main, "get_owned_document", missing_document)
    monkeypatch.setattr(
        main,
        "read_r2_document",
        lambda *args, **kwargs: pytest.fail("R2 must not be read before ownership is verified"),
    )

    with pytest.raises(HTTPException) as error:
        await main.reprocess_document(
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            object(),
        )

    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_failed_ocr_produces_clear_review_state(monkeypatch):
    pool = _ProcessingPool()
    document_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    inspection = NativePdfInspection(("",), (1,))
    monkeypatch.setattr(main, "inspect_native_pdf", lambda *args: inspection)

    def fail_ocr(*args, **kwargs):
        raise OCRUnavailableError("binary missing")

    monkeypatch.setattr(main, "extract_hybrid_pdf", fail_ocr)
    row = await main.process_pdf_document(
        pool=pool,
        document_id=document_id,
        user_id=user_id,
        contents=b"%PDF-test",
        already_claimed=True,
    )
    assert row["status"] == "needs_review"
    assert "OCR is not available" in row["processing_error"]


class _MissingDocumentPool:
    async def fetchrow(self, query, *args):
        return None


@pytest.mark.asyncio
async def test_ownership_is_checked_before_reprocessing(monkeypatch):
    monkeypatch.setattr(
        main,
        "read_r2_document",
        lambda *args: pytest.fail("storage must not be accessed before ownership is verified"),
    )
    with pytest.raises(HTTPException) as error:
        await main.reprocess_document(
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            _MissingDocumentPool(),
        )
    assert error.value.status_code == 404
