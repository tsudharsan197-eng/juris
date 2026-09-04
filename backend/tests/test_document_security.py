from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from fastapi import HTTPException, UploadFile

from app import main
from app.services.document_security_service import (
    PRIVATE_CACHE_CONTROL,
    ProcessingBudget,
    consume_processing_budget,
)


USER_ID = str(uuid.uuid4())
DOCUMENT_ID = str(uuid.uuid4())


@pytest.fixture
def signed_in():
    pool = Mock()
    previous = main.app.dependency_overrides.copy()
    main.app.dependency_overrides[main.current_user_id] = lambda: USER_ID
    main.app.dependency_overrides[main.get_db_pool] = lambda: pool
    yield pool
    main.app.dependency_overrides.clear()
    main.app.dependency_overrides.update(previous)


def client():
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test")


@pytest.mark.asyncio
async def test_quota_is_one_atomic_database_operation():
    pool = Mock(fetchrow=AsyncMock(return_value={"allowed": False, "retry_after": 123}))
    budget = await consume_processing_budget(pool, user_id=USER_ID, limit=5, window_seconds=600)
    assert budget == ProcessingBudget(False, 123)
    sql, owner, limit, window = pool.fetchrow.call_args.args
    assert "on conflict (user_id) do update" in sql
    assert "else document_processing_limits.expires_at" in sql
    assert (owner, limit, window) == (uuid.UUID(USER_ID), 5, 600.0)


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome, expected_status, retry", [
    (ProcessingBudget(False, 47), 429, "47"),
    (ConnectionError("private connection details"), 503, "60"),
])
async def test_denied_upload_stops_before_storage_and_preserves_retry_headers(
    monkeypatch, signed_in, outcome, expected_status, retry,
):
    quota = AsyncMock(side_effect=outcome) if isinstance(outcome, Exception) else AsyncMock(return_value=outcome)
    monkeypatch.setattr(main, "consume_processing_budget", quota)
    storage = Mock(side_effect=AssertionError("R2 must not run"))
    metadata = AsyncMock(side_effect=AssertionError("Metadata must not be written"))
    monkeypatch.setattr(main, "get_r2_client", storage)
    monkeypatch.setattr(main, "save_document_metadata", metadata)
    async with client() as http:
        response = await http.post("/api/documents/upload", files={"file": ("test.pdf", b"%PDF-test", "application/pdf")}, headers={"Origin": "http://localhost:5173"})
    assert response.status_code == expected_status
    assert response.headers["Retry-After"] == retry
    assert "retry-after" in response.headers["access-control-expose-headers"].lower()
    assert response.headers["Cache-Control"] == PRIVATE_CACHE_CONTROL
    assert "private connection details" not in response.text
    assert quota.call_args.kwargs["user_id"] == USER_ID
    storage.assert_not_called()
    metadata.assert_not_called()


@pytest.mark.asyncio
async def test_allowed_upload_writes_private_object_metadata(monkeypatch, signed_in):
    row = {
        "id": DOCUMENT_ID, "user_id": USER_ID, "title": "Agreement",
        "file_name": "agreement.pdf", "file_key": "private/test.pdf", "file_size": 9,
        "mime_type": "application/pdf", "storage_provider": "cloudflare_r2",
        "status": "processed", "processing_error": None, "low_confidence_pages": [],
        "extraction_metadata": {}, "created_at": datetime.now(timezone.utc),
    }
    quota = AsyncMock(return_value=ProcessingBudget(True, 600))
    r2 = Mock()
    monkeypatch.setattr(main, "consume_processing_budget", quota)
    monkeypatch.setattr(main, "save_document_metadata", AsyncMock(return_value=row))
    monkeypatch.setattr(main, "update_document_status", AsyncMock(return_value=row))
    monkeypatch.setattr(main, "process_pdf_document", AsyncMock(return_value=row))
    monkeypatch.setattr(main, "get_r2_client", lambda: r2)
    monkeypatch.setattr(main, "get_env", lambda name: "bucket")
    async with client() as http:
        response = await http.post("/api/documents/upload", files={"file": ("agreement.pdf", b"%PDF-test", "application/pdf")})
    assert response.status_code == 200
    assert quota.await_count == 1
    assert r2.put_object.call_args.kwargs["CacheControl"] == PRIVATE_CACHE_CONTROL
    assert r2.put_object.call_args.kwargs["ContentDisposition"] == 'inline; filename="agreement.pdf"'
    assert response.headers["Cache-Control"] == PRIVATE_CACHE_CONTROL


@pytest.mark.asyncio
async def test_reprocess_limit_precedes_processing_and_r2(monkeypatch, signed_in):
    monkeypatch.setattr(main, "get_owned_document", AsyncMock(return_value={"mime_type": "application/pdf"}))
    monkeypatch.setattr(main, "consume_processing_budget", AsyncMock(return_value=ProcessingBudget(False, 120)))
    claim = AsyncMock(side_effect=AssertionError("OCR claim must not run"))
    monkeypatch.setattr(main, "claim_document_processing", claim)
    async with client() as http:
        response = await http.post(f"/api/documents/{DOCUMENT_ID}/reprocess")
    assert response.status_code == 429
    assert response.headers["Retry-After"] == "120"
    claim.assert_not_called()


@pytest.mark.asyncio
async def test_reprocess_ownership_precedes_quota(monkeypatch, signed_in):
    monkeypatch.setattr(main, "get_owned_document", AsyncMock(return_value=None))
    quota = AsyncMock(side_effect=AssertionError("Quota must not be touched for another owner's document"))
    monkeypatch.setattr(main, "consume_processing_budget", quota)
    async with client() as http:
        response = await http.post(f"/api/documents/{DOCUMENT_ID}/reprocess")
    assert response.status_code == 404
    quota.assert_not_called()


@pytest.mark.asyncio
async def test_unauthenticated_requests_do_not_consume_quota(monkeypatch):
    quota = AsyncMock(side_effect=AssertionError("No quota without verified identity"))
    monkeypatch.setattr(main, "consume_processing_budget", quota)
    async with client() as http:
        response = await http.post("/api/documents/upload", files={"file": ("test.pdf", b"%PDF-test", "application/pdf")})
    assert response.status_code == 401
    assert response.headers["Cache-Control"] == PRIVATE_CACHE_CONTROL
    quota.assert_not_called()


@pytest.mark.asyncio
async def test_download_signs_private_headers_for_existing_objects(monkeypatch, signed_in):
    signed_in.fetchrow = AsyncMock(return_value={"file_key": "legacy/key", "file_name": "report.pdf", "mime_type": "application/pdf"})
    r2 = Mock()
    r2.generate_presigned_url.return_value = "https://storage.invalid/signed"
    monkeypatch.setattr(main, "get_r2_client", lambda: r2)
    monkeypatch.setattr(main, "get_env", lambda name: "bucket")
    async with client() as http:
        response = await http.get(f"/api/documents/{DOCUMENT_ID}/download-url")
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == PRIVATE_CACHE_CONTROL
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    kwargs = r2.generate_presigned_url.call_args.kwargs
    assert kwargs["ExpiresIn"] == 300
    assert kwargs["Params"]["ResponseCacheControl"] == PRIVATE_CACHE_CONTROL
    assert kwargs["Params"]["ResponseContentDisposition"] == 'inline; filename="report.pdf"'
    assert kwargs["Params"]["ResponseContentType"] == "application/pdf"
    assert signed_in.fetchrow.call_args.args[1:] == (uuid.UUID(DOCUMENT_ID), uuid.UUID(USER_ID))


@pytest.mark.asyncio
async def test_download_requires_ownership_before_signing(monkeypatch):
    pool = Mock(fetchrow=AsyncMock(return_value=None))
    r2 = Mock(side_effect=AssertionError("Must not mint someone else's URL"))
    monkeypatch.setattr(main, "get_r2_client", r2)
    with pytest.raises(HTTPException) as exc:
        await main.download_url(DOCUMENT_ID, USER_ID, pool)
    assert exc.value.status_code == 404
    r2.assert_not_called()


@pytest.mark.parametrize("name", ['../../report.pdf', 'evil"\r\nX-Test: bad.pdf', 'a\\b.pdf', 'name;extra.pdf'])
def test_disposition_cannot_inject_headers(name):
    header = main.document_disposition(name, "application/pdf")
    assert header.startswith('inline; filename="')
    assert header.count('"') == 2
    assert "\r" not in header and "\n" not in header
    assert header.count(';') == 1


def test_word_documents_are_attachments():
    assert main.document_disposition("report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document").startswith("attachment;")


@pytest.mark.asyncio
async def test_public_openai_diagnostic_is_removed(monkeypatch):
    monkeypatch.setattr(main, "get_openai_client", lambda: pytest.fail("No public diagnostic AI calls"))
    async with client() as http:
        response = await http.get("/debug/openai")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_declared_oversized_upload_rejected_before_parsing(monkeypatch):
    quota = AsyncMock(side_effect=AssertionError("Must reject before quota dependency"))
    monkeypatch.setattr(main, "consume_processing_budget", quota)
    async with client() as http:
        response = await http.post("/api/documents/upload", content=b"", headers={"Content-Length": str(27 * 1024 * 1024)})
    assert response.status_code == 413
    assert response.headers["Cache-Control"] == PRIVATE_CACHE_CONTROL
    quota.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("declared_length", [None, "1"])
async def test_chunked_upload_limit_closes_partial_spool_files(monkeypatch, declared_length):
    from fastapi import FastAPI, File
    from starlette import formparsers
    from app.services.upload_limits_middleware import UploadBodyLimitMiddleware

    test_app = FastAPI()
    test_app.add_middleware(UploadBodyLimitMiddleware, max_bytes=512)

    @test_app.post('/api/documents/upload')
    async def upload(file: UploadFile = File(...)):
        pytest.fail("Oversized body must not reach the handler")

    opened = []
    original = formparsers.SpooledTemporaryFile

    def tracked_file(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", tracked_file)

    async def content():
        yield b'--boundary\r\nContent-Disposition: form-data; name="file"; filename="x.pdf"\r\nContent-Type: application/pdf\r\n\r\n%PDF-test'
        yield b'x' * 1024
        yield b'\r\n--boundary--\r\n'

    headers = {"Content-Type": "multipart/form-data; boundary=boundary"}
    if declared_length:
        headers["Content-Length"] = declared_length
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=test_app), base_url="http://test") as http:
        response = await http.post('/api/documents/upload', content=content(), headers=headers)
    assert response.status_code == 413
    assert opened and all(file.closed for file in opened)
