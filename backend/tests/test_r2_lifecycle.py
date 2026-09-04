from __future__ import annotations

import uuid
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import main
from app.services import r2_lifecycle_service as lifecycle


def document_row(document_id: str, user_id: str, file_key: str, *, status: str):
    return {
        "id": uuid.UUID(document_id),
        "user_id": uuid.UUID(user_id),
        "title": "Agreement",
        "file_name": "agreement.doc",
        "file_key": file_key,
        "file_size": 128,
        "mime_type": "application/msword",
        "storage_provider": "cloudflare_r2",
        "status": status,
        "processing_error": None,
        "low_confidence_pages": [],
        "extraction_metadata": {},
        "created_at": datetime.now(timezone.utc),
    }


class FakeUpload:
    filename = "agreement.doc"
    content_type = "application/msword"

    async def read(self, _limit):
        return b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + (b"x" * 120)


class ReconciliationPool:
    def __init__(self, documents, deletion_jobs):
        self.documents = documents
        self.deletion_jobs = deletion_jobs

    async def fetch(self, query, *_args):
        if "from documents" in query:
            return self.documents
        if "from r2_deletion_jobs" in query:
            return self.deletion_jobs
        raise AssertionError(query)


class UndefinedTableError(Exception):
    sqlstate = "42P01"


@pytest.mark.asyncio
async def test_reconciliation_reports_unknown_objects_without_deleting_them():
    listed = False

    async def list_objects():
        nonlocal listed
        listed = True
        return [
            lifecycle.R2ObjectRecord("known", 100),
            lifecycle.R2ObjectRecord("queued", 200),
            lifecycle.R2ObjectRecord("unknown", 300),
        ]

    report = await lifecycle.reconcile_r2_storage(
        ReconciliationPool(
            documents=[{"file_key": "known"}],
            deletion_jobs=[{"file_key": "queued", "status": "failed"}],
        ),
        list_objects=list_objects,
    )

    assert listed is True
    assert report.deletion_ledger_available is True
    assert report.matched_objects == 1
    assert report.queued_orphans == 1
    assert report.unknown_orphans == 1
    assert report.unknown_orphan_bytes == 300
    assert report.unknown_orphan_fingerprints == (
        lifecycle.storage_key_fingerprint("unknown"),
    )


@pytest.mark.asyncio
async def test_reconciliation_remains_read_only_before_migration():
    class Pool:
        calls = 0

        async def fetch(self, query, *_args):
            self.calls += 1
            if "from r2_deletion_jobs" in query:
                raise UndefinedTableError()
            return [{"file_key": "known"}]

    async def list_objects():
        return [lifecycle.R2ObjectRecord("known", 100)]

    report = await lifecycle.reconcile_r2_storage(Pool(), list_objects=list_objects)
    assert report.deletion_ledger_available is False
    assert report.matched_objects == 1
    assert report.unknown_orphans == 0


class Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class Connection:
    def __init__(self):
        self.executed = []

    def transaction(self):
        return Transaction()

    async def execute(self, query, *args):
        self.executed.append((query, args))
        return "UPDATE 1" if "update r2_deletion_jobs" in query else "DELETE 1"


class Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class DeletionPool:
    def __init__(self):
        self.connection = Connection()
        self.executed = []

    def acquire(self):
        return Acquire(self.connection)

    async def execute(self, query, *args):
        self.executed.append((query, args))


def deletion_job(file_key="users/private/document.pdf"):
    return {
        "id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "file_key": file_key,
        "reason": "user_delete",
        "status": "processing",
        "attempt_count": 1,
    }


@pytest.mark.asyncio
async def test_successful_deletion_completes_job_and_document_in_one_transaction():
    pool = DeletionPool()
    deleted = []
    job = deletion_job()

    async def delete_object(file_key):
        deleted.append(file_key)

    assert await lifecycle.execute_deletion_job(pool, job, delete_object=delete_object) is True
    assert deleted == [job["file_key"]]
    assert len(pool.connection.executed) == 2
    assert "status = 'completed'" in pool.connection.executed[0][0]
    assert "delete from documents" in pool.connection.executed[1][0]


@pytest.mark.asyncio
async def test_failed_deletion_is_retried_without_leaking_storage_key():
    pool = DeletionPool()
    job = deletion_job()

    async def delete_object(_file_key):
        raise TimeoutError(f"timeout deleting {job['file_key']}")

    assert await lifecycle.execute_deletion_job(pool, job, delete_object=delete_object) is False
    assert len(pool.executed) == 1
    query, args = pool.executed[0]
    assert "status = 'failed'" in query
    assert job["file_key"] not in args[1]
    assert args[1] == "TimeoutError"
    assert args[3] == job["attempt_count"]


@pytest.mark.asyncio
async def test_upload_commits_metadata_before_r2(monkeypatch):
    events = []
    document_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())

    async def save_metadata(**kwargs):
        events.append(("metadata", kwargs["status_value"]))
        return document_row(document_id, user_id, kwargs["file_key"], status="uploading")

    async def update_status(_pool, _document_id, _user_id, status_value, **_kwargs):
        events.append(("status", status_value))
        file_key = main.user_file_key(user_id, _document_id, "agreement.doc")
        return document_row(_document_id, user_id, file_key, status=status_value)

    class R2:
        def put_object(self, **_kwargs):
            events.append(("r2", "put"))

    monkeypatch.setattr(main.uuid, "uuid4", lambda: uuid.UUID(document_id))
    monkeypatch.setattr(main, "save_document_metadata", save_metadata)
    monkeypatch.setattr(main, "update_document_status", update_status)
    monkeypatch.setattr(main, "get_r2_client", lambda: R2())
    monkeypatch.setattr(main, "get_env", lambda _name: "bucket")

    result = await main.upload_document(FakeUpload(), user_id, object())
    assert result.status == "uploaded"
    assert events == [
        ("metadata", "uploading"),
        ("r2", "put"),
        ("status", "uploaded"),
    ]


@pytest.mark.asyncio
async def test_failed_upload_attempts_idempotent_r2_compensation(monkeypatch):
    document_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    deleted = []

    async def save_metadata(**kwargs):
        return document_row(document_id, user_id, kwargs["file_key"], status="uploading")

    class Pool:
        def __init__(self):
            self.queries = []

        async def execute(self, query, *args):
            self.queries.append((query, args))

    class R2:
        def put_object(self, **_kwargs):
            raise TimeoutError("connection outcome unknown")

    async def delete_object(file_key):
        deleted.append(file_key)

    async def enqueue(_pool, **kwargs):
        assert not deleted
        return {"id": uuid.uuid4(), "file_key": kwargs["file_key"]}

    async def process(_pool, _job_id, *, delete_object):
        await delete_object("private")
        await _pool.execute("delete from documents")
        return True

    pool = Pool()
    monkeypatch.setattr(main.uuid, "uuid4", lambda: uuid.UUID(document_id))
    monkeypatch.setattr(main, "save_document_metadata", save_metadata)
    monkeypatch.setattr(main, "get_r2_client", lambda: R2())
    monkeypatch.setattr(main, "get_env", lambda _name: "bucket")
    monkeypatch.setattr(main, "delete_r2_object", delete_object)
    monkeypatch.setattr(main, "enqueue_deletion_job", enqueue)
    monkeypatch.setattr(main, "process_deletion_job_by_id", process)

    with pytest.raises(HTTPException) as error:
        await main.upload_document(FakeUpload(), user_id, pool)

    assert error.value.status_code == 500
    assert len(deleted) == 1
    assert any("delete from documents" in query for query, _args in pool.queries)


@pytest.mark.asyncio
async def test_delete_checks_ownership_before_scheduling(monkeypatch):
    class Pool:
        async def fetchrow(self, _query, *_args):
            return None

    async def forbidden_enqueue(*_args, **_kwargs):
        pytest.fail("deletion must not be scheduled before ownership is verified")

    monkeypatch.setattr(main, "enqueue_deletion_job", forbidden_enqueue)
    with pytest.raises(HTTPException) as error:
        await main.delete_document(str(uuid.uuid4()), str(uuid.uuid4()), Pool())
    assert error.value.status_code == 404


def test_security_migration_hardens_recovery_schema():
    migration = (
        Path(__file__).resolve().parents[1]
        / "db"
        / "migrations"
        / "010_r2_lifecycle_security.sql"
    ).read_text()
    assert "create table if not exists public.r2_deletion_jobs" in migration
    assert "enable row level security" in migration
    assert "revoke all privileges" in migration
    assert "with check ((select auth.uid()) = user_id)" in migration
    assert "as restrictive" in migration
    assert "alter default privileges for role postgres\n" in migration


@pytest.mark.asyncio
async def test_duplicate_delete_preserves_worker_lease_and_backoff():
    class Pool:
        async def fetchrow(self, query, *args):
            conflict = query.split("on conflict")[1].split("returning")[0]
            assert "status =" not in conflict
            assert "updated_at =" not in conflict
            assert "next_attempt_at =" not in conflict
            assert "document_id = excluded.document_id" in conflict
            assert "user_id = excluded.user_id" in conflict
            return {"id": uuid.uuid4(), "status": "processing"}

    result = await lifecycle.enqueue_deletion_job(
        Pool(), document_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()),
        file_key="private", reason="user_delete",
    )
    assert result["status"] == "processing"


@pytest.mark.asyncio
async def test_expired_worker_cannot_finalize_a_newer_attempt():
    pool = DeletionPool()

    async def stale_update(query, *args):
        pool.connection.executed.append((query, args))
        assert "attempt_count = $2" in query
        return "UPDATE 0"

    pool.connection.execute = stale_update

    async def delete_object(_key):
        pass

    assert not await lifecycle.execute_deletion_job(pool, deletion_job(), delete_object=delete_object)
    assert len(pool.connection.executed) == 1


@pytest.mark.asyncio
async def test_database_finalization_failure_retains_retry(monkeypatch):
    pool = DeletionPool()

    async def fail_completion(*args):
        raise ConnectionError("private database detail")

    async def delete_object(_key):
        pass

    monkeypatch.setattr(lifecycle, "_complete_deletion_job", fail_completion)
    assert not await lifecycle.execute_deletion_job(pool, deletion_job(), delete_object=delete_object)
    assert pool.executed[0][1][1] == "ConnectionError"


@pytest.mark.asyncio
async def test_worker_claims_one_job_at_a_time_and_respects_batch_limit(monkeypatch):
    events = []

    async def claim(_pool, *, limit):
        assert limit == 1
        events.append("claim")
        return [deletion_job()]

    async def execute(_pool, _job, **kwargs):
        events.append("execute")
        return True

    monkeypatch.setattr(lifecycle, "claim_due_deletion_jobs", claim)
    monkeypatch.setattr(lifecycle, "execute_deletion_job", execute)
    result = await lifecycle.process_due_deletion_jobs(object(), delete_object=None, limit=3)
    assert events == ["claim", "execute"] * 3
    assert result == lifecycle.DeletionBatchResult(3, 3, 0)


@pytest.mark.asyncio
async def test_missing_ledger_is_not_silently_reported_as_success():
    class Pool:
        async def fetch(self, *args):
            raise UndefinedTableError()

    with pytest.raises(UndefinedTableError):
        await lifecycle.process_due_deletion_jobs(Pool(), delete_object=None)


@pytest.mark.asyncio
async def test_cleanup_failure_records_intent_without_removing_metadata(monkeypatch):
    pool = DeletionPool()
    recorded = []

    async def fail_delete(_key):
        raise TimeoutError()

    async def enqueue(_pool, **kwargs):
        recorded.append(kwargs)
        return {"id": uuid.uuid4()}

    async def process(*args, **kwargs):
        assert recorded
        return False

    monkeypatch.setattr(main, "delete_r2_object", fail_delete)
    monkeypatch.setattr(main, "enqueue_deletion_job", enqueue)
    monkeypatch.setattr(main, "process_deletion_job_by_id", process)
    result = await main.compensate_uncommitted_upload(
        pool, document_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()),
        file_key="private", storage_attempted=True,
    )
    assert result is False
    assert recorded[0]["reason"] == "upload_rollback"
    assert not any("delete from documents" in query for query, _ in pool.executed)


@pytest.mark.asyncio
async def test_metadata_failure_never_attempts_storage_upload(monkeypatch):
    async def fail_metadata(**kwargs):
        raise ConnectionError()

    monkeypatch.setattr(main, "save_document_metadata", fail_metadata)
    monkeypatch.setattr(main, "get_r2_client", lambda: pytest.fail("No metadata: no R2 upload"))
    with pytest.raises(HTTPException) as error:
        await main.upload_document(FakeUpload(), str(uuid.uuid4()), DeletionPool())
    assert error.value.status_code == 500


@pytest.mark.asyncio
@pytest.mark.parametrize("outcome", [True, False, None, ConnectionError()])
async def test_delete_only_reports_success_after_finalization(monkeypatch, outcome):
    class Pool:
        async def fetchrow(self, *args):
            return {"file_key": "private", "status": "processed"}

    async def enqueue(*args, **kwargs):
        return {"id": uuid.uuid4()}

    async def process(*args, **kwargs):
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(main, "enqueue_deletion_job", enqueue)
    monkeypatch.setattr(main, "process_deletion_job_by_id", process)
    if outcome is True:
        assert await main.delete_document(str(uuid.uuid4()), str(uuid.uuid4()), Pool()) == {"ok": True}
    else:
        with pytest.raises(HTTPException) as error:
            await main.delete_document(str(uuid.uuid4()), str(uuid.uuid4()), Pool())
        assert error.value.status_code == 503
        assert "not complete yet" in error.value.detail


@pytest.mark.asyncio
async def test_upload_in_progress_cannot_be_deleted(monkeypatch):
    class Pool:
        async def fetchrow(self, *args):
            return {"file_key": "private", "status": "uploading"}

    async def enqueue(*args, **kwargs):
        pytest.fail("An active upload must not be deleted")

    monkeypatch.setattr(main, "enqueue_deletion_job", enqueue)
    with pytest.raises(HTTPException) as error:
        await main.delete_document(str(uuid.uuid4()), str(uuid.uuid4()), Pool())
    assert error.value.status_code == 409


@pytest.mark.asyncio
async def test_maintenance_polls_retries_separately_from_daily_inventory(monkeypatch):
    cycles = []
    sleeps = []
    clock = iter([0, 1, 61])

    async def sleep(seconds):
        sleeps.append(seconds)
        if len(sleeps) == 3:
            raise asyncio.CancelledError()

    async def cycle(pool, *, reconcile):
        cycles.append(reconcile)

    monkeypatch.setattr(main.asyncio, "sleep", sleep)
    monkeypatch.setattr(main, "time", SimpleNamespace(monotonic=lambda: next(clock)))
    monkeypatch.setattr(main, "run_r2_maintenance_cycle", cycle)
    with pytest.raises(asyncio.CancelledError):
        await main.r2_maintenance_loop(object())
    assert cycles == [True, False]
    assert sleeps[1:] == [main.R2_DELETION_RETRY_INTERVAL_SECONDS] * 2


@pytest.mark.asyncio
async def test_rollback_does_not_touch_r2_when_ledger_is_unavailable(monkeypatch):
    pool = DeletionPool()

    async def unavailable(*args, **kwargs):
        raise UndefinedTableError()

    async def forbidden_delete(*args, **kwargs):
        pytest.fail("Rollback must first be recorded")

    monkeypatch.setattr(main, "enqueue_deletion_job", unavailable)
    monkeypatch.setattr(main, "delete_r2_object", forbidden_delete)
    assert not await main.compensate_uncommitted_upload(
        pool, document_id=str(uuid.uuid4()), user_id=str(uuid.uuid4()),
        file_key="private", storage_attempted=True,
    )
    assert not any("delete from documents" in query for query, _ in pool.executed)


@pytest.mark.asyncio
async def test_lifecycle_routes_reject_missing_auth_before_storage(monkeypatch):
    import httpx

    monkeypatch.setattr(main, "get_r2_client", lambda: pytest.fail("Unauthenticated R2 access"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        response = await client.delete(f"/api/documents/{uuid.uuid4()}")
        assert response.status_code == 401
        response = await client.post('/api/documents/upload', files={"file": ("test.pdf", b"%PDF-test", "application/pdf")})
        assert response.status_code == 401
