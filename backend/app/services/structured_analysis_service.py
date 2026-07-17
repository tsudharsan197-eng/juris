from __future__ import annotations

import json
import math
import random
import re
import time
from dataclasses import dataclass
from typing import Callable, Iterable, Literal, Mapping, Sequence, TypeVar

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
    OpenAI,
    OpenAIError,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError


RiskLevel = Literal["Low", "Medium", "High"]
SchemaT = TypeVar("SchemaT", bound=BaseModel)

ANALYSIS_BATCH_CHAR_BUDGET = 22_000
ANALYSIS_SYNTHESIS_CHAR_BUDGET = 36_000
ANALYSIS_MAX_ATTEMPTS = 3


class StrictAnalysisModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClauseObligation(StrictAnalysisModel):
    party: str
    obligation: str


class ClauseRight(StrictAnalysisModel):
    party: str
    right: str


class ClauseItem(StrictAnalysisModel):
    title: str
    category: str
    plainEnglish: str
    whyItMatters: str
    riskLevel: RiskLevel
    importantTerms: list[str]
    obligations: list[ClauseObligation]
    rights: list[ClauseRight]
    restrictions: list[str]
    deadlines: list[str]
    financialTerms: list[str]
    sourceReference: str
    confidence: int = Field(ge=0, le=100)


class ClauseAnalysis(StrictAnalysisModel):
    documentType: str
    clauses: list[ClauseItem]


class RiskItem(StrictAnalysisModel):
    title: str
    category: str
    severity: RiskLevel
    description: str
    whyItMatters: str
    recommendation: str
    affectedParty: str
    sourceReference: str
    confidence: int = Field(ge=0, le=100)


class RiskAnalysis(StrictAnalysisModel):
    documentType: str
    overallRisk: RiskLevel
    summary: str
    risks: list[RiskItem]
    missingProtections: list[str]
    unusualTerms: list[str]
    financialRisks: list[str]
    legalRisks: list[str]
    complianceRisks: list[str]


class StructuredAnalysisError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        retryable: bool,
        status_code: int = 503,
        diagnostics: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        self.status_code = status_code
        self.diagnostics = diagnostics or {}


@dataclass(frozen=True)
class AnalysisChunk:
    chunk_index: int
    chunk_text: str
    page_start: int | None = None
    page_end: int | None = None
    extraction_method: str | None = None


def _row_value(row, key: str, default=None):
    if isinstance(row, Mapping):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, TypeError, IndexError):
        return getattr(row, key, default)


def coerce_analysis_chunks(rows: Iterable) -> list[AnalysisChunk]:
    chunks = []
    for position, row in enumerate(rows):
        text = str(_row_value(row, "chunk_text", "") or "").strip()
        if not text:
            continue
        raw_index = _row_value(row, "chunk_index", position)
        try:
            chunk_index = int(raw_index)
        except (TypeError, ValueError):
            chunk_index = position
        chunks.append(
            AnalysisChunk(
                chunk_index=chunk_index,
                chunk_text=text,
                page_start=_optional_int(_row_value(row, "page_start")),
                page_end=_optional_int(_row_value(row, "page_end")),
                extraction_method=str(_row_value(row, "extraction_method", "") or "") or None,
            )
        )
    return chunks


def _optional_int(value) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def format_analysis_chunk(chunk: AnalysisChunk) -> str:
    label = f"Chunk {chunk.chunk_index}"
    if chunk.page_start is not None:
        page_end = chunk.page_end or chunk.page_start
        page_label = str(chunk.page_start) if page_end == chunk.page_start else f"{chunk.page_start}-{page_end}"
        label = f"{label} / Page {page_label}"
    return f"[{label}]\n{chunk.chunk_text}"


def batch_analysis_chunks(
    rows: Iterable,
    *,
    char_budget: int = ANALYSIS_BATCH_CHAR_BUDGET,
) -> list[list[AnalysisChunk]]:
    chunks = coerce_analysis_chunks(rows)
    if not chunks:
        return []

    batches: list[list[AnalysisChunk]] = []
    current: list[AnalysisChunk] = []
    current_chars = 0
    for chunk in chunks:
        chunk_chars = len(format_analysis_chunk(chunk)) + 2
        if current and current_chars + chunk_chars > char_budget:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(chunk)
        current_chars += chunk_chars
    if current:
        batches.append(current)
    return batches


def build_clause_prompt(chunks: Sequence[AnalysisChunk], *, compact: bool = False) -> str:
    rules = (
        "Use only the supplied chunks. Extract only supported clauses. Every clause must cite at least one "
        "actual chunk as 'Chunk N' or 'Chunks N, M'. Do not invent clauses or assume a document type. "
        "Use Low, Medium, or High for riskLevel and an integer 0-100 for confidence. Return the schema only."
        if compact
        else """First identify the document type, then extract the important clauses appropriate to that type.
Use only the supplied document chunks. Do not invent clauses or assume this is a lease.
Explain each supported clause in plain English and state why it matters.
Include its important terms, party-specific obligations and rights, restrictions, deadlines, and financial terms.
Use an empty array when a field is not applicable.
Use Low, Medium, or High for riskLevel and an integer from 0 to 100 for confidence.
Every clause must cite at least one supplied chunk using exactly "Chunk N" or "Chunks N, M".
Return only the supplied structured schema."""
    )
    document = "\n\n".join(format_analysis_chunk(chunk) for chunk in chunks)
    return f"""You are a careful legal document analyst for Juris.

{rules}

DOCUMENT CHUNKS
{document}""".strip()


def build_risk_prompt(chunks: Sequence[AnalysisChunk], *, compact: bool = False) -> str:
    rules = (
        "Use only the supplied chunks. Report only supported legal, financial, operational, or compliance "
        "risks. Every risk must cite an actual chunk as 'Chunk N' or 'Chunks N, M'. Do not invent risks. "
        "A no-risk result must use an empty risks array. Return the schema only."
        if compact
        else """First identify the document type, then analyze legal, financial, operational, and compliance risks appropriate to it.
Use only the supplied document chunks. Never invent a risk or report generic risks unsupported by the text.
Explain each risk in plain English, why it matters, who it affects, and a practical recommendation.
Use Low, Medium, or High for severity and overallRisk, and an integer from 0 to 100 for confidence.
Every risk must cite at least one supplied chunk using exactly "Chunk N" or "Chunks N, M".
If no supported risks exist, return an empty risks array and say so in summary.
Return only the supplied structured schema."""
    )
    document = "\n\n".join(format_analysis_chunk(chunk) for chunk in chunks)
    return f"""You are a careful legal document risk analyst for Juris.

{rules}

DOCUMENT CHUNKS
{document}""".strip()


def _estimate_tokens(prompt: str, schema: type[BaseModel]) -> int:
    schema_chars = len(json.dumps(schema.model_json_schema(), separators=(",", ":")))
    return math.ceil((len(prompt) + schema_chars) / 4)


def _usage_value(usage, name: str):
    return getattr(usage, name, None) if usage is not None else None


def _response_diagnostics(response) -> dict:
    choices = list(getattr(response, "choices", None) or [])
    choice = choices[0] if choices else None
    message = getattr(choice, "message", None)
    usage = getattr(response, "usage", None)
    details = getattr(usage, "completion_tokens_details", None)
    finish_reason = getattr(choice, "finish_reason", None)
    return {
        "response_id": getattr(response, "id", None),
        "response_object_type": type(response).__name__,
        "response_status": "completed" if finish_reason == "stop" else "incomplete",
        "completion_status": finish_reason,
        "incomplete_reason": finish_reason if finish_reason not in (None, "stop") else None,
        "refusal_present": bool(getattr(message, "refusal", None)),
        "output_item_types": [type(message).__name__] if message is not None else [],
        "output_text_length": len((getattr(message, "content", None) or "").strip()),
        "parsed_object_present": getattr(message, "parsed", None) is not None,
        "usage_input_tokens": _usage_value(usage, "prompt_tokens"),
        "usage_output_tokens": _usage_value(usage, "completion_tokens"),
        "usage_reasoning_tokens": getattr(details, "reasoning_tokens", None),
    }


def _diagnostic_line(event: str, diagnostics: dict) -> str:
    fields = " ".join(f"{key}={value}" for key, value in diagnostics.items())
    return f"[openai:structured:{event}] {fields}"


def _provider_error(exc: OpenAIError) -> StructuredAnalysisError:
    if isinstance(exc, APITimeoutError):
        return StructuredAnalysisError(
            "OpenAI analysis request timed out.",
            code="OpenAITimeout",
            retryable=True,
            status_code=504,
        )
    if isinstance(exc, APIConnectionError):
        return StructuredAnalysisError(
            "OpenAI analysis connection failed.",
            code="OpenAITransportError",
            retryable=True,
        )
    if isinstance(exc, APIStatusError):
        provider_status = int(getattr(exc, "status_code", 0) or 0)
        if provider_status == 429:
            code = "OpenAIRateLimit"
            retryable = True
        elif provider_status >= 500:
            code = "OpenAIProviderError"
            retryable = True
        else:
            code = "OpenAIRequestError"
            retryable = False
        return StructuredAnalysisError(
            "OpenAI rejected the structured analysis request.",
            code=code,
            retryable=retryable,
            diagnostics={"provider_status": provider_status},
        )
    return StructuredAnalysisError(
        "OpenAI structured analysis failed.",
        code="OpenAIProviderError",
        retryable=True,
    )


def _request_structured_once(
    *,
    client: OpenAI,
    model: str,
    prompt: str,
    schema: type[SchemaT],
    feature: str,
    request_id: str,
    max_output_tokens: int,
    timeout_seconds: int,
    attempt: int,
    logger: Callable[[str], None],
) -> SchemaT:
    started_at = time.perf_counter()
    request_diagnostics = {
        "request_id": request_id,
        "feature": feature,
        "model": model,
        "api": "chat.completions.parse",
        "input_chars": len(prompt),
        "estimated_input_tokens": _estimate_tokens(prompt, schema),
        "max_output_tokens": max_output_tokens,
        "attempt": attempt,
    }
    logger(_diagnostic_line("request", request_diagnostics))

    try:
        response = client.chat.completions.parse(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format=schema,
            max_completion_tokens=max_output_tokens,
            reasoning_effort="low",
            timeout=timeout_seconds,
        )
    except LengthFinishReasonError as exc:
        completion = getattr(exc, "completion", None)
        diagnostics = _response_diagnostics(completion) if completion is not None else {}
        diagnostics.update(
            {
                "request_id": request_id,
                "feature": feature,
                "model": model,
                "attempt": attempt,
                "latency_ms": round((time.perf_counter() - started_at) * 1000),
            }
        )
        logger(_diagnostic_line("incomplete", diagnostics))
        raise StructuredAnalysisError(
            "OpenAI structured analysis reached its output limit.",
            code="OpenAIIncompleteResponse",
            retryable=True,
            diagnostics=diagnostics,
        ) from exc
    except ContentFilterFinishReasonError as exc:
        diagnostics = {
            "request_id": request_id,
            "feature": feature,
            "model": model,
            "attempt": attempt,
            "completion_status": "content_filter",
            "latency_ms": round((time.perf_counter() - started_at) * 1000),
        }
        logger(_diagnostic_line("content_filter", diagnostics))
        raise StructuredAnalysisError(
            "OpenAI filtered the structured analysis response.",
            code="OpenAIContentFilter",
            retryable=False,
            diagnostics=diagnostics,
        ) from exc
    except ValidationError as exc:
        diagnostics = {
            "request_id": request_id,
            "feature": feature,
            "model": model,
            "attempt": attempt,
            "validation_error_count": len(exc.errors(include_input=False)),
            "latency_ms": round((time.perf_counter() - started_at) * 1000),
        }
        logger(_diagnostic_line("schema_error", diagnostics))
        raise StructuredAnalysisError(
            "OpenAI response did not match the required schema.",
            code="OpenAISchemaValidationError",
            retryable=True,
            diagnostics=diagnostics,
        ) from exc
    except OpenAIError as exc:
        mapped = _provider_error(exc)
        mapped.diagnostics.update(
            {
                "request_id": request_id,
                "feature": feature,
                "model": model,
                "attempt": attempt,
                "provider_error_type": type(exc).__name__,
                "latency_ms": round((time.perf_counter() - started_at) * 1000),
            }
        )
        logger(_diagnostic_line("provider_error", mapped.diagnostics))
        raise mapped from exc

    diagnostics = _response_diagnostics(response)
    diagnostics.update(
        {
            "request_id": request_id,
            "feature": feature,
            "model": model,
            "attempt": attempt,
            "latency_ms": round((time.perf_counter() - started_at) * 1000),
        }
    )
    logger(_diagnostic_line("response", diagnostics))

    choices = list(getattr(response, "choices", None) or [])
    if not choices:
        raise StructuredAnalysisError(
            "OpenAI returned no completion choices.",
            code="OpenAIEmptyResponse",
            retryable=True,
            diagnostics=diagnostics,
        )

    choice = choices[0]
    message = choice.message
    if getattr(message, "refusal", None):
        raise StructuredAnalysisError(
            "OpenAI refused the structured analysis request.",
            code="OpenAIRefusal",
            retryable=False,
            diagnostics=diagnostics,
        )
    if choice.finish_reason == "content_filter":
        raise StructuredAnalysisError(
            "OpenAI filtered the structured analysis response.",
            code="OpenAIContentFilter",
            retryable=False,
            diagnostics=diagnostics,
        )
    if choice.finish_reason not in (None, "stop"):
        raise StructuredAnalysisError(
            "OpenAI returned an incomplete structured analysis response.",
            code="OpenAIIncompleteResponse",
            retryable=True,
            diagnostics=diagnostics,
        )

    parsed = getattr(message, "parsed", None)
    if parsed is not None:
        try:
            return parsed if isinstance(parsed, schema) else schema.model_validate(parsed)
        except ValidationError as exc:
            diagnostics["validation_error_count"] = len(exc.errors(include_input=False))
            raise StructuredAnalysisError(
                "OpenAI parsed output did not match the required schema.",
                code="OpenAISchemaValidationError",
                retryable=True,
                diagnostics=diagnostics,
            ) from exc

    plain_text = (getattr(message, "content", None) or "").strip()
    if plain_text:
        try:
            return schema.model_validate_json(plain_text)
        except ValidationError as exc:
            diagnostics["validation_error_count"] = len(exc.errors(include_input=False))
            raise StructuredAnalysisError(
                "OpenAI output did not match the required schema.",
                code="OpenAISchemaValidationError",
                retryable=True,
                diagnostics=diagnostics,
            ) from exc

    raise StructuredAnalysisError(
        "OpenAI completed without parsed or plain output.",
        code="OpenAIEmptyResponse",
        retryable=True,
        diagnostics=diagnostics,
    )


def request_structured_with_retries(
    *,
    client: OpenAI,
    model: str,
    prompts: Sequence[str],
    schema: type[SchemaT],
    feature: str,
    request_id: str,
    max_output_tokens: int,
    timeout_seconds: int,
    logger: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
) -> SchemaT:
    last_error: StructuredAnalysisError | None = None
    attempts = min(ANALYSIS_MAX_ATTEMPTS, max(1, len(prompts)))
    for attempt in range(1, attempts + 1):
        try:
            return _request_structured_once(
                client=client,
                model=model,
                prompt=prompts[attempt - 1],
                schema=schema,
                feature=feature,
                request_id=request_id,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
                attempt=attempt,
                logger=logger,
            )
        except StructuredAnalysisError as exc:
            last_error = exc
            if not exc.retryable or attempt >= attempts:
                raise
            delay = min(2.0, 0.35 * (2 ** (attempt - 1))) + random.uniform(0.0, 0.15)
            logger(
                _diagnostic_line(
                    "retry",
                    {
                        "request_id": request_id,
                        "feature": feature,
                        "model": model,
                        "attempt": attempt,
                        "next_attempt": attempt + 1,
                        "reason": exc.code,
                        "backoff_ms": round(delay * 1000),
                    },
                )
            )
            sleep(delay)
    if last_error is not None:
        raise last_error
    raise StructuredAnalysisError(
        "OpenAI structured analysis did not run.",
        code="OpenAIProviderError",
        retryable=False,
    )


def _reference_indices(value: str) -> list[int]:
    references = []
    for match in re.finditer(r"\bChunks?\s+([0-9][0-9,\s]*)", value or "", flags=re.IGNORECASE):
        references.extend(int(number) for number in re.findall(r"\d+", match.group(1)))
    return list(dict.fromkeys(references))


def _source_reference(indices: Iterable[int]) -> str:
    unique = sorted(set(indices))
    if len(unique) == 1:
        return f"Chunk {unique[0]}"
    return f"Chunks {', '.join(str(index) for index in unique)}"


_EVIDENCE_STOP_WORDS = {
    "about",
    "after",
    "against",
    "agreement",
    "clause",
    "document",
    "legal",
    "other",
    "party",
    "terms",
    "this",
    "with",
}


def _evidence_terms(*values: str) -> set[str]:
    terms = set()
    for value in values:
        for token in re.findall(r"[a-z0-9]+", (value or "").lower()):
            if len(token) >= 4 and token not in _EVIDENCE_STOP_WORDS:
                terms.add(token[:7])
    return terms


def _has_evidence(item: ClauseItem | RiskItem, chunk_text: str) -> bool:
    if isinstance(item, ClauseItem):
        extra = " ".join(item.importantTerms)
        terms = _evidence_terms(item.title, item.category, extra)
    else:
        terms = _evidence_terms(item.title, item.category, item.description)
    if not terms:
        return True
    normalized_chunk = re.sub(r"[^a-z0-9]+", " ", chunk_text.lower())
    return any(term in normalized_chunk for term in terms)


def _validate_clause_citations(
    analysis: ClauseAnalysis,
    chunks: Sequence[AnalysisChunk],
    *,
    logger: Callable[[str], None],
    request_id: str,
) -> ClauseAnalysis:
    chunk_map = {chunk.chunk_index: chunk.chunk_text for chunk in chunks}
    accepted = []
    rejected = 0
    for item in analysis.clauses:
        valid_indices = [index for index in _reference_indices(item.sourceReference) if index in chunk_map]
        evidence = "\n".join(chunk_map[index] for index in valid_indices)
        if not valid_indices or not _has_evidence(item, evidence):
            rejected += 1
            continue
        accepted.append(item.model_copy(update={"sourceReference": _source_reference(valid_indices)}))
    if rejected:
        logger(
            _diagnostic_line(
                "citation_validation",
                {
                    "request_id": request_id,
                    "feature": "clause_intelligence",
                    "accepted": len(accepted),
                    "rejected": rejected,
                },
            )
        )
    return ClauseAnalysis(documentType=analysis.documentType, clauses=accepted)


def _validate_risk_citations(
    analysis: RiskAnalysis,
    chunks: Sequence[AnalysisChunk],
    *,
    logger: Callable[[str], None],
    request_id: str,
) -> RiskAnalysis:
    chunk_map = {chunk.chunk_index: chunk.chunk_text for chunk in chunks}
    accepted = []
    rejected = 0
    for item in analysis.risks:
        valid_indices = [index for index in _reference_indices(item.sourceReference) if index in chunk_map]
        evidence = "\n".join(chunk_map[index] for index in valid_indices)
        if not valid_indices or not _has_evidence(item, evidence):
            rejected += 1
            continue
        accepted.append(item.model_copy(update={"sourceReference": _source_reference(valid_indices)}))
    if rejected:
        logger(
            _diagnostic_line(
                "citation_validation",
                {
                    "request_id": request_id,
                    "feature": "risk_analysis",
                    "accepted": len(accepted),
                    "rejected": rejected,
                },
            )
        )
    ranked = sorted(
        accepted,
        key=lambda item: (_RISK_RANK[item.severity], item.confidence),
        reverse=True,
    )
    return analysis.model_copy(update={"risks": ranked})


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        normalized = re.sub(r"\s+", " ", str(value or "")).strip()
        key = normalized.casefold()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def _item_key(title: str, category: str, source_reference: str) -> str:
    key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    if key:
        return key
    return re.sub(r"[^a-z0-9]+", " ", f"{category} {source_reference}".lower()).strip()


def merge_clause_analyses(analyses: Sequence[ClauseAnalysis]) -> ClauseAnalysis:
    merged: dict[str, ClauseItem] = {}
    for analysis in analyses:
        for item in analysis.clauses:
            key = _item_key(item.title, item.category, item.sourceReference)
            existing = merged.get(key)
            if existing is None:
                merged[key] = item
                continue
            preferred, other = (item, existing) if item.confidence > existing.confidence else (existing, item)
            source_indices = _reference_indices(preferred.sourceReference) + _reference_indices(other.sourceReference)
            data = preferred.model_dump()
            for field in ("importantTerms", "restrictions", "deadlines", "financialTerms"):
                data[field] = _dedupe_strings([*getattr(preferred, field), *getattr(other, field)])
            for field, action_key in (("obligations", "obligation"), ("rights", "right")):
                actions = [entry.model_dump() for entry in [*getattr(preferred, field), *getattr(other, field)]]
                seen_actions = set()
                data[field] = []
                for action in actions:
                    action_id = (str(action.get("party", "")).casefold(), str(action.get(action_key, "")).casefold())
                    if action_id not in seen_actions:
                        seen_actions.add(action_id)
                        data[field].append(action)
            data["sourceReference"] = _source_reference(source_indices)
            data["confidence"] = max(existing.confidence, item.confidence)
            merged[key] = ClauseItem.model_validate(data)
    document_type = next((item.documentType for item in analyses if item.documentType.strip()), "Not specified")
    return ClauseAnalysis(documentType=document_type, clauses=list(merged.values()))


_RISK_RANK = {"Low": 1, "Medium": 2, "High": 3}


def merge_risk_analyses(analyses: Sequence[RiskAnalysis]) -> RiskAnalysis:
    merged: dict[str, RiskItem] = {}
    for analysis in analyses:
        for item in analysis.risks:
            key = _item_key(item.title, item.category, item.sourceReference)
            existing = merged.get(key)
            if existing is None:
                merged[key] = item
                continue
            item_score = (_RISK_RANK[item.severity], item.confidence)
            existing_score = (_RISK_RANK[existing.severity], existing.confidence)
            preferred, other = (item, existing) if item_score > existing_score else (existing, item)
            data = preferred.model_dump()
            data["sourceReference"] = _source_reference(
                _reference_indices(preferred.sourceReference) + _reference_indices(other.sourceReference)
            )
            data["confidence"] = max(existing.confidence, item.confidence)
            merged[key] = RiskItem.model_validate(data)

    highest_risk = max(
        (analysis.overallRisk for analysis in analyses),
        key=lambda level: _RISK_RANK[level],
        default="Low",
    )
    summary = max((analysis.summary for analysis in analyses), key=len, default="No supported risks found.")
    document_type = next((item.documentType for item in analyses if item.documentType.strip()), "Not specified")
    return RiskAnalysis(
        documentType=document_type,
        overallRisk=highest_risk,
        summary=summary,
        risks=sorted(
            merged.values(),
            key=lambda item: (_RISK_RANK[item.severity], item.confidence),
            reverse=True,
        ),
        missingProtections=_dedupe_strings(value for item in analyses for value in item.missingProtections),
        unusualTerms=_dedupe_strings(value for item in analyses for value in item.unusualTerms),
        financialRisks=_dedupe_strings(value for item in analyses for value in item.financialRisks),
        legalRisks=_dedupe_strings(value for item in analyses for value in item.legalRisks),
        complianceRisks=_dedupe_strings(value for item in analyses for value in item.complianceRisks),
    )


def _analysis_prompts(prompt_builder, chunks: Sequence[AnalysisChunk]) -> list[str]:
    full = prompt_builder(chunks, compact=False)
    compact = prompt_builder(chunks, compact=True)
    final_retry = f"{compact}\n\nKeep every string concise. Return a complete schema object and no prose."
    return [full, compact, final_retry]


def _synthesis_prompt(feature: str, payload: BaseModel) -> str:
    candidate_json = payload.model_dump_json()
    noun = "clauses" if feature == "clause_intelligence" else "risks"
    return f"""Consolidate these validated batch-level {noun} into one final result.
Do not add a clause, risk, fact, party, amount, deadline, or source reference absent from the candidates.
Merge duplicates, keep the clearest concise wording, retain all valid chunk references, and return only the schema.

VALIDATED CANDIDATES
{candidate_json}""".strip()


def run_clause_analysis(
    *,
    client: OpenAI,
    model: str,
    rows: Iterable,
    request_id: str,
    max_output_tokens: int,
    timeout_seconds: int,
    logger: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    all_chunks = coerce_analysis_chunks(rows)
    batches = batch_analysis_chunks(all_chunks)
    logger(
        _diagnostic_line(
            "pipeline",
            {
                "request_id": request_id,
                "feature": "clause_intelligence",
                "chunk_count": len(all_chunks),
                "batch_count": len(batches),
                "document_chars": sum(len(chunk.chunk_text) for chunk in all_chunks),
            },
        )
    )
    analyses = []
    for batch_number, batch in enumerate(batches, start=1):
        analysis = request_structured_with_retries(
            client=client,
            model=model,
            prompts=_analysis_prompts(build_clause_prompt, batch),
            schema=ClauseAnalysis,
            feature=f"clause_intelligence.batch_{batch_number}",
            request_id=request_id,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            logger=logger,
            sleep=sleep,
        )
        analyses.append(_validate_clause_citations(analysis, batch, logger=logger, request_id=request_id))

    merged = merge_clause_analyses(analyses)
    if len(analyses) > 1:
        synthesis = _synthesis_prompt("clause_intelligence", merged)
        if len(synthesis) <= ANALYSIS_SYNTHESIS_CHAR_BUDGET:
            try:
                merged = request_structured_with_retries(
                    client=client,
                    model=model,
                    prompts=[synthesis, synthesis, synthesis],
                    schema=ClauseAnalysis,
                    feature="clause_intelligence.synthesis",
                    request_id=request_id,
                    max_output_tokens=max_output_tokens,
                    timeout_seconds=timeout_seconds,
                    logger=logger,
                    sleep=sleep,
                )
            except StructuredAnalysisError as exc:
                logger(
                    _diagnostic_line(
                        "synthesis_fallback",
                        {"request_id": request_id, "feature": "clause_intelligence", "reason": exc.code},
                    )
                )
        else:
            logger(
                _diagnostic_line(
                    "synthesis_fallback",
                    {
                        "request_id": request_id,
                        "feature": "clause_intelligence",
                        "reason": "candidate_budget",
                        "candidate_chars": len(synthesis),
                    },
                )
            )
    merged = _validate_clause_citations(merged, all_chunks, logger=logger, request_id=request_id)
    return merged.model_dump()


def run_risk_analysis(
    *,
    client: OpenAI,
    model: str,
    rows: Iterable,
    request_id: str,
    max_output_tokens: int,
    timeout_seconds: int,
    logger: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    all_chunks = coerce_analysis_chunks(rows)
    batches = batch_analysis_chunks(all_chunks)
    logger(
        _diagnostic_line(
            "pipeline",
            {
                "request_id": request_id,
                "feature": "risk_analysis",
                "chunk_count": len(all_chunks),
                "batch_count": len(batches),
                "document_chars": sum(len(chunk.chunk_text) for chunk in all_chunks),
            },
        )
    )
    analyses = []
    for batch_number, batch in enumerate(batches, start=1):
        analysis = request_structured_with_retries(
            client=client,
            model=model,
            prompts=_analysis_prompts(build_risk_prompt, batch),
            schema=RiskAnalysis,
            feature=f"risk_analysis.batch_{batch_number}",
            request_id=request_id,
            max_output_tokens=max_output_tokens,
            timeout_seconds=timeout_seconds,
            logger=logger,
            sleep=sleep,
        )
        analyses.append(_validate_risk_citations(analysis, batch, logger=logger, request_id=request_id))

    merged = merge_risk_analyses(analyses)
    if len(analyses) > 1:
        synthesis = _synthesis_prompt("risk_analysis", merged)
        if len(synthesis) <= ANALYSIS_SYNTHESIS_CHAR_BUDGET:
            try:
                merged = request_structured_with_retries(
                    client=client,
                    model=model,
                    prompts=[synthesis, synthesis, synthesis],
                    schema=RiskAnalysis,
                    feature="risk_analysis.synthesis",
                    request_id=request_id,
                    max_output_tokens=max_output_tokens,
                    timeout_seconds=timeout_seconds,
                    logger=logger,
                    sleep=sleep,
                )
            except StructuredAnalysisError as exc:
                logger(
                    _diagnostic_line(
                        "synthesis_fallback",
                        {"request_id": request_id, "feature": "risk_analysis", "reason": exc.code},
                    )
                )
        else:
            logger(
                _diagnostic_line(
                    "synthesis_fallback",
                    {
                        "request_id": request_id,
                        "feature": "risk_analysis",
                        "reason": "candidate_budget",
                        "candidate_chars": len(synthesis),
                    },
                )
            )
    merged = _validate_risk_citations(merged, all_chunks, logger=logger, request_id=request_id)
    return merged.model_dump()
