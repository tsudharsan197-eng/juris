from __future__ import annotations

import io
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable

import fitz
from PIL import Image
from pypdf import PdfReader

from .ocr_service import (
    OCRResult,
    choose_better_result,
    result_needs_retry,
    run_tesseract_ocr,
)


PAGE_MARKER_RE = re.compile(r"(?im)^\s*-{2,}\s*page\s+\d+\s*-{2,}\s*$")
WORD_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'._/-]*")
LEGAL_SIGNAL_RE = re.compile(
    r"(?im)(?:"
    r"\b(?:landlord|tenant|party|parties|buyer|seller|borrower|lender|client|provider|"
    r"employer|employee|agreement|lease|rent|deposit|notice|termination|liability|"
    r"witness|signature|signed)\b|"
    r"(?:₹|\$|€|£|\b(?:rs\.?|inr|usd|eur|gbp)\b)\s*[\d,]+(?:\.\d+)?|"
    r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|"
    r"^\s*(?:(?:section|clause|article)\s+)?\d+(?:\.\d+)*(?:\s*[.)-])?\s+\S+|"
    r"\b\d+(?:\.\d+)?\s*%"
    r")"
)


class DocumentExtractionError(RuntimeError):
    """Base exception for safe, user-facing extraction failures."""


class DocumentValidationError(DocumentExtractionError):
    """Raised when extracted content is not useful enough for Juris."""


class DocumentPageLimitError(DocumentExtractionError):
    """Raised before rendering PDFs that exceed the configured page limit."""


@dataclass(frozen=True)
class ExtractionSettings:
    enabled: bool = True
    dpi: int = 300
    retry_dpi: int = 400
    language: str = "eng"
    min_page_characters: int = 80
    timeout_seconds: int = 180
    max_pages: int = 100
    max_image_dimension: int = 5000
    max_image_pixels: int = 25_000_000
    low_confidence_threshold: float = 0.60
    quality_threshold: float = 72.0
    max_attempts_per_page: int = 12
    debug: bool = False

    @classmethod
    def from_env(cls) -> "ExtractionSettings":
        return cls(
            enabled=os.getenv("OCR_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"},
            dpi=max(150, min(400, int(os.getenv("OCR_DPI", "300")))),
            retry_dpi=max(200, min(400, int(os.getenv("OCR_RETRY_DPI", "400")))),
            language=os.getenv("OCR_LANGUAGE", "eng").strip() or "eng",
            min_page_characters=max(20, int(os.getenv("OCR_MIN_PAGE_CHARACTERS", "80"))),
            timeout_seconds=max(15, int(os.getenv("OCR_TIMEOUT_SECONDS", "180"))),
            max_pages=max(1, int(os.getenv("OCR_MAX_PAGES", "100"))),
            max_image_dimension=max(1500, int(os.getenv("OCR_MAX_IMAGE_DIMENSION", "5000"))),
            max_image_pixels=max(2_000_000, int(os.getenv("OCR_MAX_IMAGE_PIXELS", "25000000"))),
            low_confidence_threshold=max(
                0.0,
                min(1.0, float(os.getenv("OCR_LOW_CONFIDENCE_THRESHOLD", "0.60"))),
            ),
            quality_threshold=max(
                40.0,
                min(95.0, float(os.getenv("OCR_QUALITY_THRESHOLD", "72"))),
            ),
            max_attempts_per_page=max(
                1,
                min(20, int(os.getenv("OCR_MAX_ATTEMPTS_PER_PAGE", "12"))),
            ),
            debug=os.getenv("OCR_DEBUG", "false").strip().lower() in {"1", "true", "yes", "on"},
        )


@dataclass(frozen=True)
class NativePdfInspection:
    page_texts: tuple[str, ...]
    unreadable_pages: tuple[int, ...]

    @property
    def page_count(self) -> int:
        return len(self.page_texts)


@dataclass(frozen=True)
class PageExtraction:
    page_number: int
    text: str
    extraction_method: str
    ocr_confidence: float | None
    processed_at: str
    warning: str | None = None
    ocr_strategy: str | None = None
    ocr_psm: int | None = None
    ocr_quality_score: float | None = None
    ocr_rotation: int | None = None
    ocr_rotation_confidence: float | None = None
    ocr_attempts: int | None = None
    ocr_word_count: int | None = None
    ocr_line_count: int | None = None
    ocr_block_count: int | None = None
    ocr_text_box_coverage: float | None = None
    ocr_visual_line_regions: int | None = None

    @property
    def is_usable(self) -> bool:
        return self.extraction_method in {"native", "ocr"} and bool(self.text)


@dataclass(frozen=True)
class PdfExtractionResult:
    pages: tuple[PageExtraction, ...]

    @property
    def page_count(self) -> int:
        return len(self.pages)

    @property
    def ocr_pages(self) -> list[int]:
        return [page.page_number for page in self.pages if page.extraction_method == "ocr"]

    @property
    def failed_pages(self) -> list[int]:
        return [page.page_number for page in self.pages if not page.is_usable]

    @property
    def low_confidence_pages(self) -> list[int]:
        return [
            page.page_number
            for page in self.pages
            if page.extraction_method == "ocr"
            and page.warning in {"low_ocr_confidence", "incomplete_ocr"}
        ]

    @property
    def review_pages(self) -> list[int]:
        return sorted(set(self.low_confidence_pages + self.failed_pages))

    @property
    def text_content(self) -> str:
        return "\n\n".join(
            f"--- Page {page.page_number} ---\n{page.text}"
            for page in self.pages
            if page.is_usable
        ).strip()


OCRCallable = Callable[..., OCRResult]


def normalize_page_text(text: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = (
        normalized.replace("\x00", " ")
        .replace("\u200b", "")
        .replace("\ufeff", "")
        .replace("\f", "\n")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    normalized = PAGE_MARKER_RE.sub("", normalized)
    normalized = "\n".join(re.sub(r"[\t ]+", " ", line).strip() for line in normalized.splitlines())
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def meaningful_character_count(text: str | None) -> int:
    return sum(character.isalnum() for character in normalize_page_text(text))


def has_legal_signal(text: str | None) -> bool:
    return bool(LEGAL_SIGNAL_RE.search(normalize_page_text(text)))


def is_usable_page_text(text: str | None, min_characters: int = 80) -> bool:
    normalized = normalize_page_text(text)
    if not normalized:
        return False

    non_space = [character for character in normalized if not character.isspace()]
    if not non_space:
        return False

    meaningful = sum(character.isalnum() for character in non_space)
    if meaningful / len(non_space) < 0.35:
        return False

    words = [word.lower() for word in WORD_RE.findall(normalized)]
    standard_page = meaningful >= min_characters and len(words) >= 8
    sparse_legal_page = meaningful >= 12 and len(words) >= 2 and has_legal_signal(normalized)
    if not standard_page and not sparse_legal_page:
        return False
    if re.search(r"(.)\1{24,}", normalized):
        return False

    if len(words) >= 20:
        unique_ratio = len(set(words)) / len(words)
        dominant_ratio = max(words.count(word) for word in set(words)) / len(words)
        if unique_ratio < 0.08 or dominant_ratio > 0.65:
            return False
    return True


def page_needs_ocr(text: str | None, min_characters: int = 80) -> bool:
    return not is_usable_page_text(text, min_characters=min_characters)


def inspect_native_pdf(contents: bytes, settings: ExtractionSettings) -> NativePdfInspection:
    try:
        reader = PdfReader(io.BytesIO(contents))
    except Exception as exc:
        raise DocumentExtractionError("The PDF could not be opened for text extraction.") from exc

    page_count = len(reader.pages)
    if page_count == 0:
        raise DocumentValidationError("The PDF contains no pages.")
    if page_count > settings.max_pages:
        raise DocumentPageLimitError(
            f"This PDF has {page_count} pages. Juris currently supports up to {settings.max_pages} pages per upload."
        )

    page_texts: list[str] = []
    unreadable_pages: list[int] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            native_text = normalize_page_text(page.extract_text() or "")
        except Exception:
            native_text = ""
        page_texts.append(native_text)
        if page_needs_ocr(native_text, settings.min_page_characters):
            unreadable_pages.append(index)

    return NativePdfInspection(tuple(page_texts), tuple(unreadable_pages))


def _render_page(
    page: fitz.Page,
    settings: ExtractionSettings,
    *,
    dpi: int | None = None,
) -> Image.Image:
    scale = (dpi or settings.dpi) / 72.0
    target_width = max(1.0, page.rect.width * scale)
    target_height = max(1.0, page.rect.height * scale)
    dimension_scale = min(
        1.0,
        settings.max_image_dimension / target_width,
        settings.max_image_dimension / target_height,
    )
    pixel_scale = min(1.0, (settings.max_image_pixels / (target_width * target_height)) ** 0.5)
    scale *= min(dimension_scale, pixel_scale)

    pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB, alpha=False)
    try:
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    finally:
        pixmap = None


def extract_hybrid_pdf(
    contents: bytes,
    inspection: NativePdfInspection,
    settings: ExtractionSettings,
    *,
    ocr_engine: OCRCallable = run_tesseract_ocr,
    debug_label: str | None = None,
) -> PdfExtractionResult:
    started_at = time.monotonic()
    pages: list[PageExtraction] = []
    pdf = None

    if inspection.unreadable_pages and settings.enabled:
        try:
            pdf = fitz.open(stream=contents, filetype="pdf")
        except Exception as exc:
            raise DocumentExtractionError("The PDF could not be rendered for text recognition.") from exc

    try:
        for page_number, native_text in enumerate(inspection.page_texts, start=1):
            processed_at = datetime.now(timezone.utc).isoformat()
            if page_number not in inspection.unreadable_pages:
                pages.append(
                    PageExtraction(page_number, native_text, "native", None, processed_at)
                )
                continue

            if not settings.enabled:
                pages.append(
                    PageExtraction(
                        page_number,
                        "",
                        "unreadable",
                        None,
                        processed_at,
                        "ocr_disabled",
                    )
                )
                continue

            remaining = settings.timeout_seconds - (time.monotonic() - started_at)
            if remaining <= 0:
                raise DocumentExtractionError("Text recognition timed out before all scanned pages were read.")

            page_started_at = time.monotonic()
            image = _render_page(pdf[page_number - 1], settings, dpi=settings.dpi)
            try:
                ocr_result = ocr_engine(
                    image,
                    language=settings.language,
                    timeout_seconds=remaining,
                    max_dimension=settings.max_image_dimension,
                    max_attempts=settings.max_attempts_per_page,
                    quality_threshold=settings.quality_threshold,
                    debug_label=(
                        f"{debug_label}-page-{page_number}-dpi-{settings.dpi}"
                        if debug_label
                        else f"page-{page_number}-dpi-{settings.dpi}"
                    ),
                )
            finally:
                image.close()

            remaining = settings.timeout_seconds - (time.monotonic() - started_at)
            if (
                result_needs_retry(ocr_result, settings.quality_threshold)
                and settings.retry_dpi > settings.dpi
                and remaining > 5
            ):
                retry_image = _render_page(
                    pdf[page_number - 1],
                    settings,
                    dpi=settings.retry_dpi,
                )
                try:
                    retry_result = ocr_engine(
                        retry_image,
                        language=settings.language,
                        timeout_seconds=remaining,
                        max_dimension=settings.max_image_dimension,
                        max_attempts=settings.max_attempts_per_page,
                        quality_threshold=settings.quality_threshold,
                        debug_label=(
                            f"{debug_label}-page-{page_number}-dpi-{settings.retry_dpi}"
                            if debug_label
                            else f"page-{page_number}-dpi-{settings.retry_dpi}"
                        ),
                    )
                finally:
                    retry_image.close()
                ocr_result = choose_better_result(ocr_result, retry_result)

            page_duration_ms = round((time.monotonic() - page_started_at) * 1000)
            print(
                f"[ocr:page] page={page_number} strategy={ocr_result.preprocessing_variant} "
                f"psm={ocr_result.psm} rotation={ocr_result.rotation} "
                f"rotation_confidence={ocr_result.rotation_confidence} "
                f"quality={ocr_result.quality_score} confidence={ocr_result.confidence} "
                f"words={ocr_result.word_count} lines={ocr_result.line_count} "
                f"visual_line_regions={ocr_result.visual_line_regions} "
                f"coverage={round(ocr_result.text_box_coverage, 5)} "
                f"attempts={ocr_result.attempts} incomplete={ocr_result.incomplete} "
                f"duration_ms={page_duration_ms}"
            )

            ocr_text = normalize_page_text(ocr_result.text)
            if not is_usable_page_text(ocr_text, settings.min_page_characters):
                pages.append(
                    PageExtraction(
                        page_number,
                        "",
                        "unreadable",
                        ocr_result.confidence,
                        processed_at,
                        "ocr_text_not_usable",
                        ocr_strategy=ocr_result.preprocessing_variant,
                        ocr_psm=ocr_result.psm,
                        ocr_quality_score=ocr_result.quality_score,
                        ocr_rotation=ocr_result.rotation,
                        ocr_rotation_confidence=ocr_result.rotation_confidence,
                        ocr_attempts=ocr_result.attempts,
                        ocr_word_count=ocr_result.word_count,
                        ocr_line_count=ocr_result.line_count,
                        ocr_block_count=ocr_result.block_count,
                        ocr_text_box_coverage=ocr_result.text_box_coverage,
                        ocr_visual_line_regions=ocr_result.visual_line_regions,
                    )
                )
                continue

            if ocr_result.incomplete or (
                ocr_result.quality_score > 0
                and ocr_result.quality_score < settings.quality_threshold
            ):
                warning = "incomplete_ocr"
            elif (
                ocr_result.confidence is not None
                and ocr_result.confidence < settings.low_confidence_threshold
            ):
                warning = "low_ocr_confidence"
            else:
                warning = None
            pages.append(
                PageExtraction(
                    page_number,
                    ocr_text,
                    "ocr",
                    ocr_result.confidence,
                    processed_at,
                    warning,
                    ocr_strategy=ocr_result.preprocessing_variant,
                    ocr_psm=ocr_result.psm,
                    ocr_quality_score=ocr_result.quality_score,
                    ocr_rotation=ocr_result.rotation,
                    ocr_rotation_confidence=ocr_result.rotation_confidence,
                    ocr_attempts=ocr_result.attempts,
                    ocr_word_count=ocr_result.word_count,
                    ocr_line_count=ocr_result.line_count,
                    ocr_block_count=ocr_result.block_count,
                    ocr_text_box_coverage=ocr_result.text_box_coverage,
                    ocr_visual_line_regions=ocr_result.visual_line_regions,
                )
            )
    finally:
        if pdf is not None:
            pdf.close()

    return PdfExtractionResult(tuple(pages))


def validate_pdf_extraction(result: PdfExtractionResult, minimum_document_characters: int = 80) -> None:
    usable_pages = [page for page in result.pages if page.is_usable]
    total_meaningful_characters = sum(meaningful_character_count(page.text) for page in usable_pages)
    if not usable_pages or total_meaningful_characters < minimum_document_characters:
        raise DocumentValidationError(
            "We could not read this scan clearly. Retry text recognition or replace the file."
        )
    if not normalize_page_text(result.text_content):
        raise DocumentValidationError("No usable document text was extracted.")
