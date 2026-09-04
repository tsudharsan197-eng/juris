from __future__ import annotations

import argparse
import json
from unittest.mock import AsyncMock, Mock

import httpx
import pytest

from app.services.r2_lifecycle_service import ReconciliationReport
from app.services.security_audit_service import (
    REQUIRED_TABLES, SecurityCheck, audit_configuration, audit_database,
    audit_http, audit_reconciliation, security_report, unresolved_provider_checks,
    validate_api_base_url,
)
from scripts.security_check import bounded_inventory, run


@pytest.mark.parametrize("statuses, code, status", [
    (["pass"], 0, "pass"), (["pass", "unknown"], 3, "incomplete"),
    (["pass", "warn"], 3, "incomplete"), (["unknown", "fail"], 2, "fail"),
])
def test_report_never_turns_missing_evidence_green(statuses, code, status):
    report, result = security_report([SecurityCheck(str(i), value, "test") for i, value in enumerate(statuses)])
    assert (result, report["status"]) == (code, status)
    assert report["mode"] == "read-only"
    assert all(item.status == "unknown" for item in unresolved_provider_checks())


def test_empty_report_is_not_success():
    assert security_report([])[1] == 3


@pytest.mark.parametrize("value, expected", [("false", "pass"), ("off", "pass"), ("TRUE", "fail"), ("typo", "fail")])
def test_debug_configuration(value, expected):
    assert audit_configuration({"OCR_DEBUG": value})[0].status == expected


def database(*, missing=False, exposed=False, backlog=0):
    rows = [{"relname": name, "relkind": "r", "relrowsecurity": True, "client_access": exposed, "data_access": False} for name in REQUIRED_TABLES]
    if missing:
        rows = [row for row in rows if row["relname"] not in {"r2_deletion_jobs", "document_processing_limits"}]
    return Mock(
        fetch=AsyncMock(return_value=rows),
        fetchval=AsyncMock(side_effect=[2, 0, 0]),
        fetchrow=AsyncMock(side_effect=[
            {"rolsuper": False, "rolbypassrls": True},
            {"pending": int(backlog > 0), "failed": 0, "stale_processing": 0, "oldest_seconds": backlog},
        ]),
    )


async def test_missing_migrations_are_reported_without_trying_backlog_query():
    db = database(missing=True)
    result = {check.name: check for check in await audit_database(db)}
    assert result["database.required_tables"].status == "fail"
    assert result["storage.deletion_backlog"].status == "unknown"
    assert db.fetchrow.await_count == 1


@pytest.mark.parametrize("age, state", [(0, "pass"), (80, "pass"), (901, "fail")])
async def test_backlog_age_and_client_grants(age, state):
    result = {check.name: check for check in await audit_database(database(exposed=True, backlog=age))}
    assert result["storage.deletion_backlog"].status == state
    assert result["database.client_grants"].status == "fail"
    assert result["database.client_grants"].metrics["data_read_write_relations"] == 0
    assert result["database.backend_role"].status == "warn"


async def test_stale_processing_fails_even_with_new_created_time():
    db = database()
    db.fetchrow.side_effect = [
        {"rolsuper": False, "rolbypassrls": False},
        {"pending": 1, "failed": 0, "stale_processing": 1, "oldest_seconds": 10},
    ]
    result = {check.name: check for check in await audit_database(db)}
    assert result["storage.deletion_backlog"].status == "fail"


def test_reconciliation_redacts_fingerprints_and_reports_orphans():
    report = ReconciliationReport(True, 0, 0, 1, 2, 1, 1, 80, 0, 0, 0, ("private-fingerprint",), None, None)
    result = audit_reconciliation(report)
    assert result.status == "fail"
    assert result.metrics["unknown_orphans"] == 1
    assert "private-fingerprint" not in json.dumps(security_report([result])[0])


@pytest.mark.parametrize("url", ["http://example.com", "https://user:secret@example.com", "https://example.com/?secret=x", "https://example.com/#secret", "not-a-url"])
def test_probe_rejects_insecure_or_credential_urls(url):
    with pytest.raises(ValueError):
        validate_api_base_url(url)


class UnreadBody(httpx.AsyncByteStream):
    async def __aiter__(self):
        pytest.fail("Private response body must not be read")
        yield b""


async def test_http_checks_do_not_read_document_data_or_call_paid_diagnostic():
    visited = []

    def handler(request):
        visited.append(request.url.path)
        assert request.method == "GET"
        assert request.url.path != "/debug/openai"
        if request.url.path == "/openapi.json":
            return httpx.Response(200, json={"paths": {"/api/documents": {}, "/debug/openai": {}}})
        return httpx.Response(200 if request.url.path == "/health" else 401,
                              headers={"Cache-Control": "private, no-store, max-age=0"}, stream=UnreadBody())

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = {check.name: check for check in await audit_http(client, "https://backend.invalid")}
    assert result["http.unauthenticated_documents"].status == "pass"
    assert result["http.invalid_bearer"].status == "pass"
    assert result["http.debug_route_schema"].status == "fail"
    assert len(visited) == 4


@pytest.mark.parametrize("status", [200, 302, 403, 500])
async def test_unexpected_auth_response_fails_without_following_redirects(status):
    calls = []

    def handler(request):
        calls.append(request.url.host)
        return httpx.Response(status, headers={"Location": "https://other.invalid/private"}, stream=UnreadBody()) if request.url.path != "/openapi.json" else httpx.Response(404)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = {check.name: check for check in await audit_http(client, "https://backend.invalid")}
    assert result["http.unauthenticated_documents"].status == "fail"
    assert set(calls) == {"backend.invalid"}


async def test_http_errors_do_not_log_url_or_exception_message():
    def handler(request):
        raise httpx.ConnectError("secret-token-and-document-name")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        results = await audit_http(client, "https://backend.invalid")
    report, code = security_report(results)
    assert code == 3
    assert "secret-token" not in json.dumps(report)


def test_inventory_is_bounded_and_never_truncated_into_success():
    client = Mock()
    client.get_paginator.return_value.paginate.return_value = [{"Contents": [{"Key": "a", "Size": 3}, {"Key": "b", "Size": 4}]}]
    with pytest.raises(ValueError):
        bounded_inventory(client, "bucket", 1)
    assert client.get_paginator.return_value.paginate.call_args.kwargs["PaginationConfig"]["MaxItems"] == 2
    assert len(bounded_inventory(client, "bucket", 2)) == 2
    client.delete_object.assert_not_called()


async def test_missing_database_is_incomplete_and_never_prints_credentials(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    report, code = await run(argparse.Namespace(api_base_url=None, max_objects=100, backlog_max_age=900))
    assert code == 3
    assert any(check["name"] == "database.audit" and check["status"] == "unknown" for check in report["checks"])
