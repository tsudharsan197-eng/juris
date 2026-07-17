from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError, RateLimitError
from pydantic import ValidationError
from starlette.requests import Request

from app import main
from app.services import structured_analysis_service as service


def clause_item(**overrides):
    payload = {
        "title": "Term and Renewal",
        "category": "Renewal",
        "plainEnglish": "The agreement renews for another term.",
        "whyItMatters": "A party must act before the renewal date.",
        "riskLevel": "Medium",
        "importantTerms": ["automatic renewal"],
        "obligations": [{"party": "Client", "obligation": "Give notice before renewal."}],
        "rights": [{"party": "Provider", "right": "Renew the agreement."}],
        "restrictions": [],
        "deadlines": ["30 days before renewal"],
        "financialTerms": [],
        "sourceReference": "Chunk 1",
        "confidence": 94,
    }
    payload.update(overrides)
    return service.ClauseItem.model_validate(payload)


def clause_analysis(**overrides):
    payload = {"documentType": "Service Agreement", "clauses": [clause_item()]}
    payload.update(overrides)
    return service.ClauseAnalysis.model_validate(payload)


def risk_item(**overrides):
    payload = {
        "title": "Automatic renewal exposure",
        "category": "Renewal",
        "severity": "Medium",
        "description": "The agreement renews automatically.",
        "whyItMatters": "The client may enter another term unintentionally.",
        "recommendation": "Calendar the notice deadline.",
        "affectedParty": "Client",
        "sourceReference": "Chunk 1",
        "confidence": 92,
    }
    payload.update(overrides)
    return service.RiskItem.model_validate(payload)


def risk_analysis(**overrides):
    payload = {
        "documentType": "Service Agreement",
        "overallRisk": "Medium",
        "summary": "The renewal term needs attention.",
        "risks": [risk_item()],
        "missingProtections": [],
        "unusualTerms": [],
        "financialRisks": [],
        "legalRisks": ["Automatic renewal"],
        "complianceRisks": [],
    }
    payload.update(overrides)
    return service.RiskAnalysis.model_validate(payload)


def fake_response(*, parsed=None, content=None, refusal=None, finish_reason="stop", reasoning_tokens=0):
    message = SimpleNamespace(parsed=parsed, content=content, refusal=refusal)
    choice = SimpleNamespace(message=message, finish_reason=finish_reason)
    usage_details = SimpleNamespace(reasoning_tokens=reasoning_tokens)
    usage = SimpleNamespace(
        prompt_tokens=120,
        completion_tokens=80,
        completion_tokens_details=usage_details,
    )
    return SimpleNamespace(id="chatcmpl-test", choices=[choice], usage=usage)


class FakeCompletions:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeClient:
    def __init__(self, results):
        self.parse_api = FakeCompletions(results)
        self.chat = SimpleNamespace(completions=self.parse_api)


def request_clause(client, *, prompts=None, logs=None):
    logger = logs.append if logs is not None else (lambda _: None)
    return service.request_structured_with_retries(
        client=client,
        model="gpt-5-mini",
        prompts=prompts or ["prompt", "compact prompt", "final prompt"],
        schema=service.ClauseAnalysis,
        feature="clause_intelligence",
        request_id="req-test",
        max_output_tokens=8000,
        timeout_seconds=120,
        logger=logger,
        sleep=lambda _: None,
    )


def test_valid_structured_response_uses_sdk_parsed_object():
    expected = clause_analysis()
    client = FakeClient([fake_response(parsed=expected, content=expected.model_dump_json())])

    actual = request_clause(client)

    assert actual == expected
    assert client.parse_api.calls[0]["response_format"] is service.ClauseAnalysis
    assert client.parse_api.calls[0]["reasoning_effort"] == "low"


def test_parsed_object_is_accepted_without_plain_output_text():
    expected = clause_analysis()
    client = FakeClient([fake_response(parsed=expected, content=None)])

    actual = request_clause(client)

    assert actual.clauses[0].title == "Term and Renewal"


def test_empty_first_response_retries_and_returns_valid_result():
    client = FakeClient(
        [
            fake_response(parsed=None, content=""),
            fake_response(parsed=clause_analysis(), content=None),
        ]
    )

    actual = request_clause(client)

    assert actual.documentType == "Service Agreement"
    assert len(client.parse_api.calls) == 2


def test_malformed_json_retries_then_uses_valid_result():
    client = FakeClient(
        [
            fake_response(parsed=None, content="{not-json"),
            fake_response(parsed=clause_analysis(), content=None),
        ]
    )

    actual = request_clause(client)

    assert actual.clauses
    assert len(client.parse_api.calls) == 2


def test_incomplete_response_retries():
    client = FakeClient(
        [
            fake_response(parsed=None, content="", finish_reason="length", reasoning_tokens=8000),
            fake_response(parsed=clause_analysis(), content=None),
        ]
    )

    actual = request_clause(client)

    assert actual.clauses[0].confidence == 94
    assert len(client.parse_api.calls) == 2


def test_truncated_output_reports_incomplete_after_bounded_retries():
    client = FakeClient([fake_response(finish_reason="length") for _ in range(3)])

    with pytest.raises(service.StructuredAnalysisError) as caught:
        request_clause(client)

    assert caught.value.code == "OpenAIIncompleteResponse"
    assert len(client.parse_api.calls) == 3


def test_refusal_is_not_retried():
    client = FakeClient([fake_response(refusal="Cannot comply")])

    with pytest.raises(service.StructuredAnalysisError) as caught:
        request_clause(client)

    assert caught.value.code == "OpenAIRefusal"
    assert len(client.parse_api.calls) == 1


def test_content_filter_is_not_retried():
    client = FakeClient([fake_response(finish_reason="content_filter")])

    with pytest.raises(service.StructuredAnalysisError) as caught:
        request_clause(client)

    assert caught.value.code == "OpenAIContentFilter"
    assert len(client.parse_api.calls) == 1


def test_provider_502_retries_then_succeeds():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(502, request=request)
    provider_error = APIStatusError("bad gateway", response=response, body={})
    client = FakeClient([provider_error, fake_response(parsed=clause_analysis())])

    actual = request_clause(client)

    assert actual.clauses
    assert len(client.parse_api.calls) == 2


def test_timeout_retries_then_succeeds():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    client = FakeClient([APITimeoutError(request), fake_response(parsed=clause_analysis())])

    actual = request_clause(client)

    assert actual.documentType == "Service Agreement"


def test_rate_limit_retries_then_succeeds():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request)
    rate_limit = RateLimitError("rate limited", response=response, body={})
    client = FakeClient([rate_limit, fake_response(parsed=clause_analysis())])

    actual = request_clause(client)

    assert actual.clauses
    assert len(client.parse_api.calls) == 2


def test_network_error_retries_then_succeeds():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    client = FakeClient(
        [
            APIConnectionError(message="connection failed", request=request),
            fake_response(parsed=clause_analysis()),
        ]
    )

    assert request_clause(client).clauses


def test_permanent_request_error_is_not_retried():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(400, request=request)
    client = FakeClient([APIStatusError("invalid request", response=response, body={})])

    with pytest.raises(service.StructuredAnalysisError) as caught:
        request_clause(client)

    assert caught.value.code == "OpenAIRequestError"
    assert len(client.parse_api.calls) == 1


def test_schema_validation_failure_is_bounded():
    try:
        service.ClauseAnalysis.model_validate({"documentType": "Agreement"})
    except ValidationError as validation_error:
        errors = [validation_error, validation_error, validation_error]
    client = FakeClient(errors)

    with pytest.raises(service.StructuredAnalysisError) as caught:
        request_clause(client)

    assert caught.value.code == "OpenAISchemaValidationError"
    assert len(client.parse_api.calls) == 3


def test_long_document_is_split_into_page_aware_batches():
    rows = [
        {
            "chunk_index": index,
            "chunk_text": f"Section {index}. Termination and payment obligations. " + "word " * 180,
            "page_start": index + 1,
            "page_end": index + 1,
        }
        for index in range(18)
    ]

    batches = service.batch_analysis_chunks(rows, char_budget=3500)

    assert len(batches) > 1
    assert [chunk.chunk_index for batch in batches for chunk in batch] == list(range(18))
    assert all(batch[0].page_start is not None for batch in batches)


@pytest.mark.parametrize("feature", ["clauses", "risks"])
def test_long_document_batches_are_synthesized_with_valid_citations(feature):
    rows = [
        {
            "chunk_index": index,
            "chunk_text": (
                "The agreement renews automatically unless the client gives thirty days notice. "
                + "Payment and termination obligations remain in force. " * 14
            ),
            "page_start": index + 1,
            "page_end": index + 1,
        }
        for index in range(30)
    ]
    batches = service.batch_analysis_chunks(rows)
    assert len(batches) > 1
    cited_indices = [batch[0].chunk_index for batch in batches]
    source_reference = service._source_reference(cited_indices)

    if feature == "clauses":
        batch_results = [
            fake_response(
                parsed=clause_analysis(
                    clauses=[clause_item(sourceReference=f"Chunk {chunk_index}")]
                )
            )
            for chunk_index in cited_indices
        ]
        final_result = clause_analysis(
            clauses=[clause_item(sourceReference=source_reference)]
        )
        client = FakeClient([*batch_results, fake_response(parsed=final_result)])
        result = service.run_clause_analysis(
            client=client,
            model="gpt-5-mini",
            rows=rows,
            request_id="req-test",
            max_output_tokens=8000,
            timeout_seconds=120,
            logger=lambda _: None,
            sleep=lambda _: None,
        )
        assert result["clauses"][0]["sourceReference"] == source_reference
    else:
        batch_results = [
            fake_response(
                parsed=risk_analysis(
                    risks=[risk_item(sourceReference=f"Chunk {chunk_index}")]
                )
            )
            for chunk_index in cited_indices
        ]
        final_result = risk_analysis(
            risks=[risk_item(sourceReference=source_reference)]
        )
        client = FakeClient([*batch_results, fake_response(parsed=final_result)])
        result = service.run_risk_analysis(
            client=client,
            model="gpt-5-mini",
            rows=rows,
            request_id="req-test",
            max_output_tokens=8000,
            timeout_seconds=120,
            logger=lambda _: None,
            sleep=lambda _: None,
        )
        assert result["risks"][0]["sourceReference"] == source_reference

    assert len(client.parse_api.calls) == len(batches) + 1


def test_duplicate_clauses_merge_terms_actions_and_citations():
    first = clause_analysis()
    second = clause_analysis(
        clauses=[
            clause_item(
                confidence=97,
                importantTerms=["notice window"],
                sourceReference="Chunk 2",
            )
        ]
    )

    merged = service.merge_clause_analyses([first, second])

    assert len(merged.clauses) == 1
    assert merged.clauses[0].confidence == 97
    assert merged.clauses[0].sourceReference == "Chunks 1, 2"
    assert set(merged.clauses[0].importantTerms) == {"automatic renewal", "notice window"}


def test_duplicate_risks_merge_severity_and_citations():
    first = risk_analysis()
    second = risk_analysis(
        overallRisk="High",
        risks=[risk_item(severity="High", confidence=98, sourceReference="Chunk 3")],
    )

    merged = service.merge_risk_analyses([first, second])

    assert len(merged.risks) == 1
    assert merged.overallRisk == "High"
    assert merged.risks[0].severity == "High"
    assert merged.risks[0].sourceReference == "Chunks 1, 3"


def test_merged_risks_are_ranked_by_severity_then_confidence():
    analysis = risk_analysis(
        risks=[
            risk_item(title="Low item", severity="Low", confidence=99),
            risk_item(title="High item", severity="High", confidence=70),
            risk_item(title="Medium item", severity="Medium", confidence=95),
        ]
    )

    merged = service.merge_risk_analyses([analysis])

    assert [item.severity for item in merged.risks] == ["High", "Medium", "Low"]


def test_citation_validation_preserves_supported_and_rejects_fabricated_items():
    chunks = service.coerce_analysis_chunks(
        [
            {"chunk_index": 1, "chunk_text": "The agreement renews automatically with thirty days notice."},
            {"chunk_index": 2, "chunk_text": "Payment is due monthly."},
        ]
    )
    analysis = clause_analysis(
        clauses=[
            clause_item(sourceReference="Chunk 1"),
            clause_item(title="Patent assignment", category="Intellectual Property", sourceReference="Chunk 99"),
        ]
    )

    validated = service._validate_clause_citations(
        analysis,
        chunks,
        logger=lambda _: None,
        request_id="req-test",
    )

    assert [item.title for item in validated.clauses] == ["Term and Renewal"]
    assert validated.clauses[0].sourceReference == "Chunk 1"


@pytest.mark.parametrize("extraction_method", ["native", "ocr", "hybrid"])
def test_native_ocr_and_mixed_chunks_follow_the_same_structured_path(extraction_method):
    rows = [
        {
            "chunk_index": 1,
            "chunk_text": "Section 6.2. The agreement renews automatically with thirty days notice.",
            "page_start": 6,
            "page_end": 6,
            "extraction_method": extraction_method,
        }
    ]
    client = FakeClient([fake_response(parsed=clause_analysis())])

    result = service.run_clause_analysis(
        client=client,
        model="gpt-5-mini",
        rows=rows,
        request_id="req-test",
        max_output_tokens=8000,
        timeout_seconds=120,
        logger=lambda _: None,
        sleep=lambda _: None,
    )

    assert result["clauses"][0]["sourceReference"] == "Chunk 1"


def test_valid_no_risk_result_is_not_treated_as_empty():
    no_risk = risk_analysis(
        overallRisk="Low",
        summary="No supported material risks were found.",
        risks=[],
        legalRisks=[],
    )
    client = FakeClient([fake_response(parsed=no_risk)])

    result = service.run_risk_analysis(
        client=client,
        model="gpt-5-mini",
        rows=[{"chunk_index": 1, "chunk_text": "This short agreement contains standard mutual terms."}],
        request_id="req-test",
        max_output_tokens=8000,
        timeout_seconds=120,
        logger=lambda _: None,
        sleep=lambda _: None,
    )

    assert result["risks"] == []
    assert result["overallRisk"] == "Low"


def test_diagnostics_never_log_confidential_prompt_or_output():
    secret = "CONFIDENTIAL-CLIENT-CLAUSE-7391"
    logs = []
    client = FakeClient([fake_response(parsed=clause_analysis(), content=secret)])

    request_clause(client, prompts=[secret], logs=logs)

    rendered = "\n".join(logs)
    assert secret not in rendered
    assert "input_chars=" in rendered
    assert "output_text_length=" in rendered


def request_for(path: str) -> Request:
    return Request({"type": "http", "method": "POST", "path": path, "headers": []})


@pytest.mark.asyncio
async def test_failed_generation_does_not_write_ai_output(monkeypatch):
    saved = []

    async def owned(*_):
        return {"id": "document"}

    async def chunks(*_):
        return [{"chunk_index": 1, "chunk_text": "Termination requires notice."}]

    async def input_hash(*_, **__):
        return "hash"

    async def cache_miss(*_, **__):
        return None

    async def fail(*_, **__):
        raise main.AIProviderError(
            "internal failure",
            error_type="OpenAIEmptyResponse",
            status_code=503,
            diagnostics={"attempt": 3},
        )

    async def save(*_, **kwargs):
        saved.append(kwargs)

    monkeypatch.setattr(main, "get_owned_document", owned)
    monkeypatch.setattr(main, "get_document_chunks_in_order", chunks)
    monkeypatch.setattr(main, "document_feature_input_hash", input_hash)
    monkeypatch.setattr(main, "get_cached_ai_output", cache_miss)
    monkeypatch.setattr(main, "generate_clauses", fail)
    monkeypatch.setattr(main, "save_ai_output", save)

    response = await main.document_clauses(
        request_for("/api/documents/document/clauses"),
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        object(),
    )

    body = json.loads(response.body)
    assert response.status_code == 503
    assert body["error"]["message"] == "Juris could not complete this analysis. Your document is safe. Try again."
    assert body["error"]["details"] == {"code": "ANALYSIS_TEMPORARILY_UNAVAILABLE"}
    assert saved == []


@pytest.mark.asyncio
async def test_previous_cached_success_is_returned_without_regeneration(monkeypatch):
    cached = {"documentType": "Agreement", "clauses": []}

    async def owned(*_):
        return {"id": "document"}

    async def chunks(*_):
        return [{"chunk_index": 1, "chunk_text": "Standard terms."}]

    async def input_hash(*_, **__):
        return "hash"

    async def cache_hit(*_, **__):
        return cached

    async def should_not_generate(*_, **__):
        raise AssertionError("generation must not run on a cache hit")

    monkeypatch.setattr(main, "get_owned_document", owned)
    monkeypatch.setattr(main, "get_document_chunks_in_order", chunks)
    monkeypatch.setattr(main, "document_feature_input_hash", input_hash)
    monkeypatch.setattr(main, "get_cached_ai_output", cache_hit)
    monkeypatch.setattr(main, "generate_clauses", should_not_generate)

    response = await main.document_clauses(
        request_for("/api/documents/document/clauses"),
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
        object(),
    )

    assert response["success"] is True
    assert response["data"]["cached"] is True
