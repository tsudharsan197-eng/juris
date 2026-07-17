from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

from .pdf_extraction_service import (
    PageExtraction,
    PdfExtractionResult,
    has_legal_signal,
    meaningful_character_count,
    normalize_page_text,
)


@dataclass(frozen=True)
class DocumentChunk:
    chunk_index: int
    text: str
    page_start: int
    page_end: int
    extraction_method: str
    ocr_confidence: float | None


def is_valid_chunk_text(text: str | None) -> bool:
    normalized = normalize_page_text(text)
    meaningful = meaningful_character_count(normalized)
    if meaningful < 10:
        return False
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'._/-]*", normalized)
    return len(words) >= 3 or (len(words) >= 2 and has_legal_signal(normalized))


def _preferred_chunk_end(text: str, start: int, chunk_size: int) -> int:
    maximum_end = min(start + chunk_size, len(text))
    if maximum_end >= len(text):
        return len(text)

    window = text[start:maximum_end]
    minimum_boundary = max(1, int(chunk_size * 0.58))
    for separator in ("\n\n", "\n", ". ", "; ", ": ", " "):
        boundary = window.rfind(separator, minimum_boundary)
        if boundary >= minimum_boundary:
            return start + boundary + len(separator)
    return maximum_end


def _overlap_start(text: str, start: int, end: int, overlap: int) -> int:
    target = max(start + 1, end - overlap)
    while target > start + 1 and not text[target - 1].isspace():
        target -= 1
    while target < end and text[target].isspace():
        target += 1
    return target if target > start else min(end, start + 1)


def build_page_aware_chunks(
    pages: tuple[PageExtraction, ...] | list[PageExtraction],
    *,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    for page in pages:
        if not page.is_usable:
            continue
        normalized = normalize_page_text(page.text)
        start = 0
        while start < len(normalized):
            end = _preferred_chunk_end(normalized, start, chunk_size)
            chunk_text = normalized[start:end].strip()
            if is_valid_chunk_text(chunk_text):
                chunks.append(
                    DocumentChunk(
                        chunk_index=len(chunks),
                        text=chunk_text,
                        page_start=page.page_number,
                        page_end=page.page_number,
                        extraction_method=page.extraction_method,
                        ocr_confidence=page.ocr_confidence,
                    )
                )
            if end == len(normalized):
                break
            start = _overlap_start(normalized, start, end, overlap)
    return chunks


def validate_chunks(chunks: list[DocumentChunk]) -> None:
    if not chunks:
        raise ValueError("No valid document chunks were created from the extracted text.")
    if any(not is_valid_chunk_text(chunk.text) for chunk in chunks):
        raise ValueError("Invalid or marker-only text was found in the document chunks.")


def validate_chunk_coverage(
    pages: tuple[PageExtraction, ...] | list[PageExtraction],
    chunks: list[DocumentChunk],
) -> None:
    chunks_by_page: dict[int, list[str]] = {}
    for chunk in chunks:
        chunks_by_page.setdefault(chunk.page_start, []).append(chunk.text)

    for page in pages:
        if not page.is_usable:
            continue
        page_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'._/-]*", page.text.lower())
        if not page_words:
            continue
        joined_chunks = " ".join(chunks_by_page.get(page.page_number, [])).lower()
        joined_words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'._/-]*", joined_chunks)
        joined_text = " ".join(joined_words)
        sample_size = min(5, len(page_words))
        sample_starts = {
            0,
            max(0, len(page_words) // 2 - sample_size // 2),
            max(0, len(page_words) - sample_size),
        }
        for sample_start in sample_starts:
            sample = " ".join(page_words[sample_start : sample_start + sample_size])
            if sample and sample not in joined_text:
                raise ValueError(
                    f"Document chunking lost representative text from page {page.page_number}."
                )


def validate_embeddings(embeddings: list[list[float]], expected_count: int, dimensions: int) -> None:
    if expected_count <= 0 or len(embeddings) != expected_count:
        raise ValueError("Embedding generation did not return one vector for every valid chunk.")
    for embedding in embeddings:
        if len(embedding) != dimensions or any(not math.isfinite(value) for value in embedding):
            raise ValueError("Embedding generation returned an invalid vector.")


def page_metadata(result: PdfExtractionResult) -> list[dict]:
    return [asdict(page) for page in result.pages]


def extraction_metadata(result: PdfExtractionResult, chunk_count: int) -> dict:
    native_pages = [page.page_number for page in result.pages if page.extraction_method == "native"]
    return {
        "pageCount": result.page_count,
        "nativePages": native_pages,
        "ocrPages": result.ocr_pages,
        "lowConfidencePages": result.low_confidence_pages,
        "reviewPages": result.review_pages,
        "unreadablePages": result.failed_pages,
        "chunkCount": chunk_count,
        "ocrStrategies": {
            str(page.page_number): {
                "variant": page.ocr_strategy,
                "psm": page.ocr_psm,
                "qualityScore": page.ocr_quality_score,
                "confidence": page.ocr_confidence,
                "attempts": page.ocr_attempts,
                "rotation": page.ocr_rotation,
            }
            for page in result.pages
            if page.extraction_method == "ocr"
        },
    }
