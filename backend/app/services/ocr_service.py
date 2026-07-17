from __future__ import annotations

import json
import math
import os
import re
import shutil
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageOps
from pytesseract import Output


class OCRUnavailableError(RuntimeError):
    """Raised when OCR is requested but Tesseract is not installed."""


class OCRTimeoutError(RuntimeError):
    """Raised when a page exceeds its OCR time budget."""


@dataclass(frozen=True)
class OCRResult:
    text: str
    confidence: float | None
    quality_score: float = 0.0
    preprocessing_variant: str = "unknown"
    psm: int | None = None
    rotation: int = 0
    rotation_confidence: float | None = None
    deskew_angle: float = 0.0
    perspective_corrected: bool = False
    perspective_confidence: float | None = None
    word_count: int = 0
    line_count: int = 0
    block_count: int = 0
    text_box_coverage: float = 0.0
    visual_ink_ratio: float = 0.0
    visual_line_regions: int = 0
    incomplete: bool = False
    attempts: int = 1


@dataclass(frozen=True)
class PageVisualMetrics:
    ink_ratio: float
    line_regions: int


@dataclass(frozen=True)
class OCRAttemptSummary:
    variant: str
    psm: int
    rotation: int
    confidence: float | None
    quality_score: float
    word_count: int
    line_count: int
    block_count: int
    text_box_coverage: float
    incomplete: bool


ORIENTATION_CONFIDENCE_THRESHOLD = 5.0
DEFAULT_QUALITY_THRESHOLD = 72.0
DEFAULT_MAX_ATTEMPTS = 12
LEGAL_KEYWORDS = {
    "agreement",
    "borrower",
    "buyer",
    "client",
    "confidentiality",
    "deposit",
    "employee",
    "employer",
    "governing",
    "landlord",
    "lease",
    "liability",
    "lender",
    "notice",
    "obligation",
    "party",
    "payment",
    "provider",
    "renewal",
    "rent",
    "seller",
    "service",
    "tenant",
    "termination",
}
MONTH_PATTERN = (
    r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
    r"jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
)
DATE_PATTERN = re.compile(
    rf"\b(?:\d{{1,2}}[./-]\d{{1,2}}[./-]\d{{2,4}}|"
    rf"\d{{1,2}}(?:st|nd|rd|th)?\s+{MONTH_PATTERN}[,\s]+\d{{2,4}}|"
    rf"{MONTH_PATTERN}\s+\d{{1,2}}(?:st|nd|rd|th)?[,]?\s+\d{{2,4}})\b",
    re.IGNORECASE,
)
CURRENCY_PATTERN = re.compile(
    r"(?:₹|\$|€|£|\b(?:rs\.?|inr|usd|eur|gbp)\b)\s*[\d,]+(?:\.\d+)?",
    re.IGNORECASE,
)
CLAUSE_PATTERN = re.compile(
    r"(?im)^\s*(?:(?:section|clause|article)\s+)?\d+(?:\.\d+)*(?:\s*[.)-])?\s+\S+"
)
PERCENT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*%")
PARTY_PATTERN = re.compile(
    r"\b(?:landlord|tenant|party|parties|borrower|lender|buyer|seller|"
    r"employer|employee|client|provider|vendor)\b",
    re.IGNORECASE,
)


def tesseract_available() -> bool:
    return shutil.which("tesseract") is not None


def _remaining_seconds(started_at: float, timeout_seconds: float) -> float:
    remaining = timeout_seconds - (time.monotonic() - started_at)
    if remaining <= 0:
        raise OCRTimeoutError("OCR timed out while reading a scanned page.")
    return remaining


def _env_flag(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes", "on"}


def _bounded_image(image: Image.Image, max_dimension: int) -> Image.Image:
    prepared = ImageOps.exif_transpose(image).convert("RGB")
    if max(prepared.size) > max_dimension:
        prepared.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
    return prepared


def _detect_orientation(image: Image.Image, timeout_seconds: float) -> tuple[int, float | None]:
    try:
        osd = pytesseract.image_to_osd(
            image,
            output_type=Output.DICT,
            timeout=max(1.0, min(timeout_seconds, 10.0)),
        )
        rotation = int(osd.get("rotate", 0) or 0) % 360
        confidence = float(osd.get("orientation_conf", 0) or 0)
        return rotation, confidence
    except (pytesseract.TesseractError, RuntimeError, TypeError, ValueError):
        return 0, None


def _apply_rotation(image: Image.Image, rotation: int) -> Image.Image:
    if rotation % 360 == 0:
        return image.copy()
    return image.rotate(-(rotation % 360), expand=True, fillcolor="white")


def _correct_orientation(image: Image.Image, timeout_seconds: float) -> Image.Image:
    rotation, confidence = _detect_orientation(image, timeout_seconds)
    if confidence is None or confidence < ORIENTATION_CONFIDENCE_THRESHOLD:
        rotation = 0
    return _apply_rotation(image, rotation)


def _deskew_with_angle(gray: np.ndarray) -> tuple[np.ndarray, float]:
    _, foreground = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coordinates = np.column_stack(np.where(foreground > 0))
    if coordinates.shape[0] < 100:
        return gray.copy(), 0.0

    angle = cv2.minAreaRect(coordinates)[-1]
    angle = -(90 + angle) if angle < -45 else -angle
    if not math.isfinite(angle) or abs(angle) < 0.15 or abs(angle) > 4.0:
        return gray.copy(), 0.0

    height, width = gray.shape
    center = (width / 2.0, height / 2.0)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    corrected = cv2.warpAffine(
        gray,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return corrected, float(angle)


def _deskew(gray: np.ndarray) -> np.ndarray:
    corrected, _ = _deskew_with_angle(gray)
    return corrected


def _normalize_contrast(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=1.6, tileGridSize=(8, 8))
    return clahe.apply(gray)


def preprocess_for_ocr(image: Image.Image, max_dimension: int) -> Image.Image:
    """Return the conservative grayscale candidate retained for API compatibility."""
    prepared = _bounded_image(image, max_dimension)
    try:
        gray = cv2.cvtColor(np.asarray(prepared), cv2.COLOR_RGB2GRAY)
        normalized = _normalize_contrast(gray)
        return Image.fromarray(normalized)
    finally:
        prepared.close()


def _order_points(points: np.ndarray) -> np.ndarray:
    ordered = np.zeros((4, 2), dtype="float32")
    coordinate_sum = points.sum(axis=1)
    coordinate_difference = np.diff(points, axis=1).reshape(-1)
    ordered[0] = points[np.argmin(coordinate_sum)]
    ordered[2] = points[np.argmax(coordinate_sum)]
    ordered[1] = points[np.argmin(coordinate_difference)]
    ordered[3] = points[np.argmax(coordinate_difference)]
    return ordered


def _perspective_correct(image: Image.Image) -> tuple[Image.Image | None, float | None]:
    rgb = np.asarray(image.convert("RGB"))
    height, width = rgb.shape[:2]
    scale = min(1.0, 1600.0 / max(height, width))
    preview = cv2.resize(rgb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(preview, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 45, 135)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    preview_area = float(preview.shape[0] * preview.shape[1])

    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:12]:
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue

        area_ratio = cv2.contourArea(polygon) / preview_area
        if area_ratio < 0.55 or area_ratio > 0.985:
            continue

        rectangle = cv2.minAreaRect(polygon)
        rectangle_area = max(1.0, rectangle[1][0] * rectangle[1][1])
        rectangularity = min(1.0, cv2.contourArea(polygon) / rectangle_area)
        confidence = 0.68 * rectangularity + 0.32 * min(1.0, area_ratio / 0.80)
        if confidence < 0.72:
            continue

        points = polygon.reshape(4, 2).astype("float32") / scale
        points = _order_points(points)
        top_left, top_right, bottom_right, bottom_left = points
        target_width = int(
            max(np.linalg.norm(bottom_right - bottom_left), np.linalg.norm(top_right - top_left))
        )
        target_height = int(
            max(np.linalg.norm(top_right - bottom_right), np.linalg.norm(top_left - bottom_left))
        )
        if target_width < width * 0.45 or target_height < height * 0.45:
            continue

        destination = np.array(
            [
                [0, 0],
                [target_width - 1, 0],
                [target_width - 1, target_height - 1],
                [0, target_height - 1],
            ],
            dtype="float32",
        )
        matrix = cv2.getPerspectiveTransform(points, destination)
        corrected = cv2.warpPerspective(
            rgb,
            matrix,
            (target_width, target_height),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return Image.fromarray(corrected), round(confidence, 4)

    return None, None


def _visual_metrics(image: Image.Image) -> PageVisualMetrics:
    gray = cv2.cvtColor(np.asarray(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    scale = min(1.0, 1400.0 / max(gray.shape))
    if scale < 1.0:
        gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, foreground = cv2.threshold(
        blurred,
        0,
        255,
        cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU,
    )
    ink_ratio = float(np.count_nonzero(foreground)) / float(foreground.size)

    height, width = foreground.shape
    horizontal_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (max(13, width // 75), max(2, height // 700)),
    )
    grouped = cv2.morphologyEx(foreground, cv2.MORPH_CLOSE, horizontal_kernel)
    contours, _ = cv2.findContours(grouped, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    minimum_width = max(18, int(width * 0.018))
    minimum_height = max(3, int(height * 0.002))
    maximum_height = max(minimum_height + 1, int(height * 0.075))
    line_regions = 0
    for contour in contours:
        x, y, region_width, region_height = cv2.boundingRect(contour)
        del x, y
        if (
            region_width >= minimum_width
            and minimum_height <= region_height <= maximum_height
            and region_width * region_height >= 45
        ):
            line_regions += 1

    return PageVisualMetrics(round(ink_ratio, 5), line_regions)


def _build_preprocessing_variants(
    image: Image.Image,
) -> tuple[dict[str, Image.Image], float, float | None]:
    rgb = np.asarray(image.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    normalized = _normalize_contrast(gray)
    deskewed, deskew_angle = _deskew_with_angle(gray)
    deskewed_normalized = _normalize_contrast(deskewed)

    blurred = cv2.GaussianBlur(normalized, (0, 0), 1.0)
    sharpened = cv2.addWeighted(normalized, 1.22, blurred, -0.22, 0)
    adaptive = cv2.adaptiveThreshold(
        normalized,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        41,
        11,
    )
    background = cv2.GaussianBlur(gray, (0, 0), max(15.0, min(gray.shape) / 35.0))
    shadow_normalized = cv2.divide(gray, np.maximum(background, 1), scale=255)

    variants = {
        "original_rgb": image.copy(),
        "grayscale_normalized": Image.fromarray(normalized),
        "adaptive_threshold": Image.fromarray(adaptive),
        "light_sharpen": Image.fromarray(sharpened),
        "deskewed": Image.fromarray(deskewed_normalized),
        "shadow_normalized": Image.fromarray(shadow_normalized),
    }
    perspective, perspective_confidence = _perspective_correct(image)
    if perspective is not None:
        variants["perspective_corrected"] = perspective
    return variants, deskew_angle, perspective_confidence


def _safe_index(values, index: int, default=0):
    try:
        return values[index]
    except (IndexError, TypeError):
        return default


def _text_and_confidence(data: dict, image_size: tuple[int, int] | None = None) -> OCRResult:
    texts = data.get("text", [])
    lines: dict[tuple[int, int, int, int], list[str]] = {}
    weighted_confidence = 0.0
    confidence_weight = 0
    block_numbers: set[int] = set()
    text_box_area = 0.0

    for index, raw_text in enumerate(texts):
        word = re.sub(r"\s+", " ", str(raw_text or "")).strip()
        if not word:
            continue

        page_number = int(_safe_index(data.get("page_num", []), index, 0) or 0)
        block_number = int(_safe_index(data.get("block_num", []), index, 0) or 0)
        paragraph_number = int(_safe_index(data.get("par_num", []), index, 0) or 0)
        line_number = int(_safe_index(data.get("line_num", []), index, 0) or 0)
        key = (page_number, block_number, paragraph_number, line_number)
        lines.setdefault(key, []).append(word)
        if block_number > 0:
            block_numbers.add(block_number)

        try:
            confidence = float(_safe_index(data.get("conf", []), index, -1))
        except (TypeError, ValueError):
            confidence = -1
        if confidence >= 0:
            weight = max(1, len(word))
            weighted_confidence += confidence * weight
            confidence_weight += weight

        try:
            width = max(0, int(_safe_index(data.get("width", []), index, 0)))
            height = max(0, int(_safe_index(data.get("height", []), index, 0)))
            text_box_area += width * height
        except (TypeError, ValueError):
            pass

    rendered_lines = [" ".join(words).strip() for words in lines.values() if words]
    text = "\n".join(line for line in rendered_lines if line).strip()
    confidence = None
    if confidence_weight:
        confidence = max(0.0, min(1.0, weighted_confidence / confidence_weight / 100.0))

    coverage = 0.0
    if image_size:
        image_area = max(1, image_size[0] * image_size[1])
        coverage = max(0.0, min(1.0, text_box_area / image_area))

    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’._/-]*", text)
    return OCRResult(
        text=text,
        confidence=confidence,
        word_count=len(words),
        line_count=len(rendered_lines),
        block_count=len(block_numbers),
        text_box_coverage=coverage,
    )


def _quality_score(result: OCRResult, visuals: PageVisualMetrics) -> tuple[float, bool]:
    text = result.text
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’._/-]*", text)
    lowered_words = [word.lower().strip(".'’_/-") for word in words]
    meaningful_words = [word for word in lowered_words if len(word) >= 2 or word.isdigit()]
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    plausible_lines = [
        line
        for line in lines
        if len(re.findall(r"[A-Za-z0-9]+", line)) >= 2
        or DATE_PATTERN.search(line)
        or CURRENCY_PATTERN.search(line)
        or CLAUSE_PATTERN.search(line)
        or PARTY_PATTERN.search(line)
    ]

    visible = [character for character in text if not character.isspace()]
    alphanumeric_ratio = (
        sum(character.isalnum() for character in visible) / len(visible) if visible else 0.0
    )
    legal_keyword_count = len(set(lowered_words).intersection(LEGAL_KEYWORDS))
    pattern_count = sum(
        bool(pattern.search(text))
        for pattern in (DATE_PATTERN, CURRENCY_PATTERN, CLAUSE_PATTERN, PERCENT_PATTERN, PARTY_PATTERN)
    )
    single_character_ratio = (
        sum(len(word) == 1 and not word.isdigit() for word in words) / len(words) if words else 1.0
    )
    duplicate_lines = len(lines) - len({re.sub(r"\W+", "", line.lower()) for line in lines})
    repeated_garbage = len(re.findall(r"([^\w\s])\1{3,}|([A-Za-z])\2{5,}", text))
    words_per_line = len(words) / max(1, len(lines))

    dense_page = visuals.line_regions >= 12 or visuals.ink_ratio >= 0.025
    line_recovery = len(plausible_lines) / max(1, visuals.line_regions)
    incomplete = bool(
        not meaningful_words
        or (
            dense_page
            and (
                len(meaningful_words) < max(12, visuals.line_regions * 1.75)
                or len(plausible_lines) < max(3, visuals.line_regions * 0.32)
            )
        )
        or (
            dense_page
            and result.text_box_coverage < 0.003
            and len(meaningful_words) < 35
        )
    )

    score = 0.0
    score += (result.confidence or 0.0) * 30.0
    score += min(1.0, len(meaningful_words) / 180.0) * 20.0
    score += (len(plausible_lines) / max(1, len(lines))) * 8.0
    score += min(1.0, legal_keyword_count / 7.0) * 8.0
    score += min(1.0, pattern_count / 4.0) * 8.0
    score += min(1.0, alphanumeric_ratio / 0.78) * 6.0
    score += min(1.0, line_recovery) * 8.0
    score += min(1.0, result.text_box_coverage / 0.07) * 7.0
    score += min(1.0, result.block_count / 5.0) * 5.0

    if words_per_line < 2.2 and len(words) > 30:
        score -= min(12.0, (2.2 - words_per_line) * 8.0)
    score -= min(10.0, single_character_ratio * 18.0)
    score -= min(8.0, duplicate_lines * 0.8)
    score -= min(10.0, repeated_garbage * 2.0)
    if incomplete:
        score -= 18.0

    return round(max(0.0, min(100.0, score)), 2), incomplete


def _enrich_result(
    result: OCRResult,
    *,
    variant: str,
    psm: int,
    rotation: int,
    rotation_confidence: float | None,
    deskew_angle: float,
    perspective_confidence: float | None,
    visuals: PageVisualMetrics,
) -> OCRResult:
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’._/-]*", result.text)
    lines = [line for line in result.text.splitlines() if line.strip()]
    result = replace(
        result,
        word_count=result.word_count or len(words),
        line_count=result.line_count or len(lines),
    )
    quality_score, incomplete = _quality_score(result, visuals)
    return replace(
        result,
        quality_score=quality_score,
        preprocessing_variant=variant,
        psm=psm,
        rotation=rotation,
        rotation_confidence=rotation_confidence,
        deskew_angle=round(deskew_angle, 3),
        perspective_corrected=variant == "perspective_corrected",
        perspective_confidence=perspective_confidence,
        visual_ink_ratio=visuals.ink_ratio,
        visual_line_regions=visuals.line_regions,
        incomplete=incomplete,
    )


def _ocr_quality(result: OCRResult) -> float:
    if result.quality_score > 0:
        return result.quality_score
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9'’._/-]*", result.text)
    alphanumeric = sum(character.isalnum() for character in result.text)
    visible = sum(not character.isspace() for character in result.text)
    alphanumeric_ratio = alphanumeric / visible if visible else 0.0
    confidence = result.confidence or 0.0
    return confidence * 70.0 + min(len(words), 100) * 0.2 + alphanumeric_ratio * 10.0


def result_needs_retry(result: OCRResult, quality_threshold: float = DEFAULT_QUALITY_THRESHOLD) -> bool:
    if result.quality_score > 0:
        high_confidence_sparse_page = (
            not result.incomplete
            and result.confidence is not None
            and result.confidence >= 0.90
            and result.word_count >= 20
            and result.visual_line_regions < 5
        )
        if high_confidence_sparse_page:
            return False
        return result.incomplete or result.quality_score < quality_threshold
    word_count = len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'’._/-]*", result.text))
    return result.confidence is None or result.confidence < 0.72 or word_count < 20


def choose_better_result(current: OCRResult, candidate: OCRResult) -> OCRResult:
    current_key = (
        not current.incomplete,
        _ocr_quality(current),
        current.confidence or 0.0,
        current.word_count or len(current.text.split()),
    )
    candidate_key = (
        not candidate.incomplete,
        _ocr_quality(candidate),
        candidate.confidence or 0.0,
        candidate.word_count or len(candidate.text.split()),
    )
    return candidate if candidate_key > current_key else current


def _recognize_image(
    image: Image.Image,
    *,
    language: str,
    timeout_seconds: float,
    psm: int = 3,
) -> OCRResult:
    data = pytesseract.image_to_data(
        image,
        lang=language,
        config=f"--oem 1 --psm {psm} -c preserve_interword_spaces=1",
        output_type=Output.DICT,
        timeout=timeout_seconds,
    )
    return _text_and_confidence(data, image_size=image.size)


def _debug_page_dir(debug_label: str | None) -> Path | None:
    if not _env_flag("OCR_DEBUG"):
        return None
    safe_label = re.sub(r"[^A-Za-z0-9._-]+", "-", debug_label or "page").strip("-") or "page"
    root = Path(os.getenv("OCR_DEBUG_DIR", "tmp/ocr-debug"))
    page_dir = root / safe_label
    page_dir.mkdir(parents=True, exist_ok=True)
    return page_dir


def _save_debug_image(page_dir: Path | None, name: str, image: Image.Image) -> None:
    if page_dir is not None:
        image.save(page_dir / f"{name}.png", format="PNG")


def _save_debug_result(
    page_dir: Path | None,
    attempt_number: int,
    result: OCRResult,
) -> None:
    if page_dir is None:
        return
    stem = f"attempt-{attempt_number:02d}-{result.preprocessing_variant}-psm-{result.psm}-r{result.rotation}"
    (page_dir / f"{stem}.txt").write_text(result.text, encoding="utf-8")
    details = asdict(result)
    details.pop("text", None)
    (page_dir / f"{stem}.json").write_text(json.dumps(details, indent=2), encoding="utf-8")


def run_tesseract_ocr(
    image: Image.Image,
    *,
    language: str,
    timeout_seconds: float,
    max_dimension: int,
    max_attempts: int | None = None,
    quality_threshold: float | None = None,
    debug_label: str | None = None,
) -> OCRResult:
    if not tesseract_available():
        raise OCRUnavailableError(
            "Scanned pages require Tesseract OCR, but the Tesseract binary is not installed."
        )

    configured_attempts = max_attempts or int(
        os.getenv("OCR_MAX_ATTEMPTS_PER_PAGE", str(DEFAULT_MAX_ATTEMPTS))
    )
    max_attempts = max(1, min(20, configured_attempts))
    quality_threshold = quality_threshold or float(
        os.getenv("OCR_QUALITY_THRESHOLD", str(DEFAULT_QUALITY_THRESHOLD))
    )
    started_at = time.monotonic()
    source = _bounded_image(image, max_dimension)
    page_dir = _debug_page_dir(debug_label)
    _save_debug_image(page_dir, "original-render", source)

    detected_rotation, rotation_confidence = _detect_orientation(
        source,
        _remaining_seconds(started_at, timeout_seconds),
    )
    applied_rotation = (
        detected_rotation
        if rotation_confidence is not None
        and rotation_confidence >= ORIENTATION_CONFIDENCE_THRESHOLD
        else 0
    )
    oriented = _apply_rotation(source, applied_rotation)
    visuals = _visual_metrics(oriented)
    variants: dict[str, Image.Image] = {"original_rgb": oriented}
    attempts: list[OCRAttemptSummary] = []
    best_result: OCRResult | None = None
    deskew_angle = 0.0
    perspective_confidence = None
    preprocessing_variants_generated = False

    def ensure_preprocessing_variants() -> None:
        nonlocal deskew_angle, perspective_confidence, preprocessing_variants_generated
        if preprocessing_variants_generated:
            return
        generated, deskew_angle, perspective_confidence = _build_preprocessing_variants(oriented)
        for name, variant_image in generated.items():
            if name == "original_rgb":
                variant_image.close()
                continue
            variants[name] = variant_image
            _save_debug_image(page_dir, name, variant_image)
        preprocessing_variants_generated = True

    def recognize(variant: str, psm: int, rotation: int = applied_rotation) -> OCRResult | None:
        nonlocal best_result
        if len(attempts) >= max_attempts:
            return None
        candidate_image = variants[variant]
        try:
            raw_result = _recognize_image(
                candidate_image,
                language=language,
                timeout_seconds=_remaining_seconds(started_at, timeout_seconds),
                psm=psm,
            )
        except pytesseract.TesseractNotFoundError as exc:
            raise OCRUnavailableError(
                "Scanned pages require Tesseract OCR, but the Tesseract binary is not installed."
            ) from exc
        except (RuntimeError, pytesseract.TesseractError):
            return None

        enriched = _enrich_result(
            raw_result,
            variant=variant,
            psm=psm,
            rotation=rotation,
            rotation_confidence=rotation_confidence,
            deskew_angle=deskew_angle,
            perspective_confidence=perspective_confidence,
            visuals=visuals,
        )
        attempts.append(
            OCRAttemptSummary(
                variant=variant,
                psm=psm,
                rotation=rotation,
                confidence=enriched.confidence,
                quality_score=enriched.quality_score,
                word_count=enriched.word_count,
                line_count=enriched.line_count,
                block_count=enriched.block_count,
                text_box_coverage=round(enriched.text_box_coverage, 6),
                incomplete=enriched.incomplete,
            )
        )
        _save_debug_result(page_dir, len(attempts), enriched)
        best_result = enriched if best_result is None else choose_better_result(best_result, enriched)
        return enriched

    try:
        initial = recognize("original_rgb", 3)
        if initial is None:
            raise OCRTimeoutError("OCR timed out while reading a scanned page.")

        if page_dir is not None and not result_needs_retry(initial, quality_threshold):
            # Debug mode records every bounded image candidate without spending
            # extra OCR passes on an already-complete page.
            ensure_preprocessing_variants()

        if result_needs_retry(initial, quality_threshold):
            if applied_rotation == 0 and (
                rotation_confidence is None or rotation_confidence < ORIENTATION_CONFIDENCE_THRESHOLD
            ):
                for angle in (90, 180, 270):
                    rotated_name = f"original_rotated_{angle}"
                    variants[rotated_name] = source.rotate(-angle, expand=True, fillcolor="white")
                    rotated_visuals = _visual_metrics(variants[rotated_name])
                    previous_visuals = visuals
                    visuals = rotated_visuals
                    candidate = recognize(rotated_name, 3, angle)
                    visuals = previous_visuals
                    if candidate is not None and not result_needs_retry(candidate, quality_threshold):
                        break

            if best_result is not None and result_needs_retry(best_result, quality_threshold):
                ensure_preprocessing_variants()

                retry_plan = (
                    ("original_rgb", 4),
                    ("original_rgb", 6),
                    ("original_rgb", 11),
                    ("original_rgb", 12),
                    ("grayscale_normalized", 3),
                    ("light_sharpen", 6),
                    ("deskewed", 4),
                    ("shadow_normalized", 11),
                    ("adaptive_threshold", 6),
                    ("perspective_corrected", 3),
                )
                for variant, psm in retry_plan:
                    if variant not in variants or len(attempts) >= max_attempts:
                        continue
                    candidate = recognize(variant, psm)
                    if candidate is not None and not result_needs_retry(candidate, quality_threshold):
                        break

        if page_dir is not None:
            (page_dir / "scoring.json").write_text(
                json.dumps([asdict(attempt) for attempt in attempts], indent=2),
                encoding="utf-8",
            )
            if best_result is not None:
                (page_dir / "chosen.txt").write_text(best_result.text, encoding="utf-8")
                chosen_details = asdict(best_result)
                chosen_details.pop("text", None)
                chosen_details["attempts"] = len(attempts)
                (page_dir / "chosen.json").write_text(
                    json.dumps(chosen_details, indent=2),
                    encoding="utf-8",
                )

        if best_result is None:
            raise OCRTimeoutError("OCR timed out while reading a scanned page.")
        return replace(best_result, attempts=len(attempts))
    except OCRTimeoutError:
        raise
    except RuntimeError as exc:
        raise OCRTimeoutError("OCR timed out while reading a scanned page.") from exc
    finally:
        closed: set[int] = set()
        for variant_image in variants.values():
            identity = id(variant_image)
            if identity not in closed:
                variant_image.close()
                closed.add(identity)
        source.close()
