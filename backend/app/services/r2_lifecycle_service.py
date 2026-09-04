from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Awaitable, Callable, Iterable, Mapping


DeletionCallback = Callable[[str], Awaitable[None]]
ObjectLister = Callable[[], Awaitable[list["R2ObjectRecord"]]]


@dataclass(frozen=True)
class R2ObjectRecord:
    key: str
    size: int
    last_modified: datetime | None = None


@dataclass(frozen=True)
class DeletionBatchResult:
    claimed: int
    completed: int
    failed: int


@dataclass(frozen=True)
class ReconciliationReport:
    deletion_ledger_available: bool
    incomplete_uploads: int
    pending_deletions: int
    database_documents: int
    r2_objects: int
    matched_objects: int
    unknown_orphans: int
    unknown_orphan_bytes: int
    queued_orphans: int
    completed_jobs_still_present: int
    database_rows_missing_objects: int
    unknown_orphan_fingerprints: tuple[str, ...]
    oldest_unknown_orphan: datetime | None
    newest_unknown_orphan: datetime | None

    def as_dict(self) -> dict:
        result = asdict(self)
        result["oldest_unknown_orphan"] = (
            self.oldest_unknown_orphan.isoformat() if self.oldest_unknown_orphan else None
        )
        result["newest_unknown_orphan"] = (
            self.newest_unknown_orphan.isoformat() if self.newest_unknown_orphan else None
        )
        result["unknown_orphan_fingerprints"] = list(self.unknown_orphan_fingerprints)
        return result


def storage_key_fingerprint(file_key: str) -> str:
    return hashlib.sha256(file_key.encode("utf-8")).hexdigest()[:16]


def _uuid(value) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _is_undefined_table_error(exc: Exception) -> bool:
    return getattr(exc, "sqlstate", None) == "42P01"


async def enqueue_deletion_job(
    pool,
    *,
    document_id: str,
    user_id: str,
    file_key: str,
    reason: str,
):
    return await pool.fetchrow(
        """
        insert into r2_deletion_jobs (
          document_id, user_id, file_key, reason, status, next_attempt_at,
          created_at, updated_at
        )
        values ($1, $2, $3, $4, 'pending', now(), now(), now())
        on conflict (file_key) do update set
          file_key = r2_deletion_jobs.file_key
        where r2_deletion_jobs.document_id = excluded.document_id
          and r2_deletion_jobs.user_id = excluded.user_id
        returning id, document_id, user_id, file_key, reason, status,
          attempt_count, next_attempt_at, last_error, created_at, updated_at,
          completed_at
        """,
        _uuid(document_id),
        _uuid(user_id),
        file_key,
        reason,
    )


async def claim_deletion_job(pool, job_id: str, *, stale_after_seconds: int = 900):
    return await pool.fetchrow(
        """
        update r2_deletion_jobs
        set status = 'processing', attempt_count = attempt_count + 1, updated_at = now()
        where id = $1
          and (
            (status in ('pending', 'failed') and next_attempt_at <= now())
            or (status = 'processing' and updated_at < now() - make_interval(secs => $2::double precision))
          )
        returning id, document_id, user_id, file_key, reason, status,
          attempt_count, next_attempt_at, last_error, created_at, updated_at,
          completed_at
        """,
        _uuid(job_id),
        float(max(60, stale_after_seconds)),
    )


async def claim_due_deletion_jobs(
    pool,
    *,
    limit: int = 20,
    stale_after_seconds: int = 900,
):
    return await pool.fetch(
        """
        with candidates as (
          select id
          from r2_deletion_jobs
          where (
            status in ('pending', 'failed') and next_attempt_at <= now()
          ) or (
            status = 'processing'
            and updated_at < now() - make_interval(secs => $2::double precision)
          )
          order by created_at asc
          for update skip locked
          limit $1
        )
        update r2_deletion_jobs as jobs
        set status = 'processing', attempt_count = attempt_count + 1, updated_at = now()
        from candidates
        where jobs.id = candidates.id
        returning jobs.id, jobs.document_id, jobs.user_id, jobs.file_key,
          jobs.reason, jobs.status, jobs.attempt_count, jobs.next_attempt_at,
          jobs.last_error, jobs.created_at, jobs.updated_at, jobs.completed_at
        """,
        max(1, min(int(limit), 100)),
        float(max(60, stale_after_seconds)),
    )


async def _complete_deletion_job(pool, job: Mapping):
    async with pool.acquire() as connection:
        async with connection.transaction():
            updated = await connection.execute(
                """
                update r2_deletion_jobs
                set status = 'completed', last_error = null,
                  completed_at = now(), updated_at = now()
                where id = $1 and status = 'processing' and attempt_count = $2
                """,
                _uuid(job["id"]),
                job["attempt_count"],
            )
            if updated != 'UPDATE 1':
                return False
            await connection.execute(
                """
                delete from documents
                where id = $1 and user_id = $2 and file_key = $3
                """,
                _uuid(job["document_id"]),
                _uuid(job["user_id"]),
                job["file_key"],
            )
    return True


async def _fail_deletion_job(pool, job: Mapping, exc: Exception):
    attempt_count = max(1, int(job.get("attempt_count", 1)))
    retry_seconds = min(3600, 30 * (2 ** min(attempt_count - 1, 7)))
    # Provider exception messages can contain request URLs and private keys.
    message = exc.__class__.__name__
    await pool.execute(
        """
        update r2_deletion_jobs
        set status = 'failed', last_error = $2,
          next_attempt_at = now() + make_interval(secs => $3::double precision),
          updated_at = now()
        where id = $1 and status = 'processing' and attempt_count = $4
        """,
        _uuid(job["id"]),
        message,
        float(retry_seconds),
        attempt_count,
    )


async def execute_deletion_job(
    pool,
    job: Mapping,
    *,
    delete_object: DeletionCallback,
) -> bool:
    try:
        await delete_object(str(job["file_key"]))
        completed = await _complete_deletion_job(pool, job)
    except Exception as exc:
        await _fail_deletion_job(pool, job, exc)
        print(
            "[r2:delete:retry] "
            f"job_id={job['id']} key_fingerprint={storage_key_fingerprint(str(job['file_key']))} "
            f"attempt={job.get('attempt_count', 1)} error_type={exc.__class__.__name__}"
        )
        return False

    if not completed:
        return False
    print(
        "[r2:delete:complete] "
        f"job_id={job['id']} key_fingerprint={storage_key_fingerprint(str(job['file_key']))} "
        f"attempt={job.get('attempt_count', 1)}"
    )
    return True


async def process_deletion_job_by_id(
    pool,
    job_id: str,
    *,
    delete_object: DeletionCallback,
) -> bool | None:
    job = await claim_deletion_job(pool, job_id)
    if not job:
        return None
    return await execute_deletion_job(pool, job, delete_object=delete_object)


async def process_due_deletion_jobs(
    pool,
    *,
    delete_object: DeletionCallback,
    limit: int = 20,
) -> DeletionBatchResult:
    claimed = 0
    completed = 0
    failed = 0
    # Claim immediately before execution so queued jobs do not expire while
    # waiting behind slow R2 requests in the same batch.
    for _ in range(max(1, min(int(limit), 100))):
        jobs = await claim_due_deletion_jobs(pool, limit=1)
        if not jobs:
            break
        claimed += 1
        if await execute_deletion_job(pool, jobs[0], delete_object=delete_object):
            completed += 1
        else:
            failed += 1
    return DeletionBatchResult(claimed=claimed, completed=completed, failed=failed)


async def reconcile_r2_storage(
    pool,
    *,
    list_objects: ObjectLister,
    fingerprint_limit: int = 25,
) -> ReconciliationReport:
    document_rows = await pool.fetch("select file_key, status from documents")
    deletion_ledger_available = True
    try:
        deletion_rows = await pool.fetch("select file_key, status from r2_deletion_jobs")
    except Exception as exc:
        if not _is_undefined_table_error(exc):
            raise
        deletion_ledger_available = False
        deletion_rows = []
    objects = await list_objects()

    database_keys = {str(row["file_key"]) for row in document_rows}
    object_by_key = {item.key: item for item in objects}
    object_keys = set(object_by_key)
    active_job_keys = {
        str(row["file_key"])
        for row in deletion_rows
        if row["status"] in {"pending", "processing", "failed"}
    }
    completed_job_keys = {
        str(row["file_key"])
        for row in deletion_rows
        if row["status"] == "completed"
    }

    orphan_keys = object_keys - database_keys
    queued_orphan_keys = orphan_keys & active_job_keys
    completed_but_present_keys = orphan_keys & completed_job_keys
    unknown_orphan_keys = orphan_keys - active_job_keys - completed_job_keys
    missing_object_keys = database_keys - object_keys

    unknown_objects = [object_by_key[key] for key in unknown_orphan_keys]
    unknown_dates = sorted(
        item.last_modified for item in unknown_objects if item.last_modified is not None
    )
    fingerprints = tuple(
        sorted(storage_key_fingerprint(key) for key in unknown_orphan_keys)[:fingerprint_limit]
    )

    return ReconciliationReport(
        deletion_ledger_available=deletion_ledger_available,
        incomplete_uploads=sum(row.get("status") == "uploading" for row in document_rows),
        pending_deletions=len(active_job_keys),
        database_documents=len(database_keys),
        r2_objects=len(object_keys),
        matched_objects=len(database_keys & object_keys),
        unknown_orphans=len(unknown_orphan_keys),
        unknown_orphan_bytes=sum(item.size for item in unknown_objects),
        queued_orphans=len(queued_orphan_keys),
        completed_jobs_still_present=len(completed_but_present_keys),
        database_rows_missing_objects=len(missing_object_keys),
        unknown_orphan_fingerprints=fingerprints,
        oldest_unknown_orphan=unknown_dates[0] if unknown_dates else None,
        newest_unknown_orphan=unknown_dates[-1] if unknown_dates else None,
    )


def object_records(items: Iterable[Mapping]) -> list[R2ObjectRecord]:
    return [
        R2ObjectRecord(
            key=str(item["Key"]),
            size=int(item.get("Size", 0)),
            last_modified=item.get("LastModified"),
        )
        for item in items
    ]
