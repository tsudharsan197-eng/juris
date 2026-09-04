#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import asyncpg
from dotenv import load_dotenv


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

load_dotenv(BACKEND_ROOT / ".env")
load_dotenv(REPOSITORY_ROOT / ".env")

from app.main import delete_r2_object, list_r2_objects  # noqa: E402
from app.services.r2_lifecycle_service import (  # noqa: E402
    process_due_deletion_jobs,
    reconcile_r2_storage,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Report drift between document metadata and R2. Unknown objects are never deleted."
        )
    )
    parser.add_argument(
        "--retry-recorded-deletions",
        action="store_true",
        help="Retry only deletion jobs already recorded in r2_deletion_jobs.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Maximum recorded deletion jobs to retry (1-100).",
    )
    parser.add_argument(
        "--fail-on-drift",
        action="store_true",
        help="Exit non-zero when unknown, missing, or incomplete storage state is found.",
    )
    return parser.parse_args()


async def run(args) -> int:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")

    pool = await asyncpg.create_pool(database_url, statement_cache_size=0)
    try:
        retry_result = None
        if args.retry_recorded_deletions:
            retry_result = await process_due_deletion_jobs(
                pool,
                delete_object=delete_r2_object,
                limit=max(1, min(args.batch_size, 100)),
            )

        report = await reconcile_r2_storage(pool, list_objects=list_r2_objects)
        output = {
            "mode": "retry-recorded-deletions" if args.retry_recorded_deletions else "report-only",
            "unknown_objects_deleted": 0,
            "retry": vars(retry_result) if retry_result else None,
            "report": report.as_dict(),
        }
        print(json.dumps(output, indent=2, sort_keys=True))

        has_drift = any(
            (
                report.unknown_orphans,
                report.queued_orphans,
                report.completed_jobs_still_present,
                report.database_rows_missing_objects,
                report.incomplete_uploads,
                report.pending_deletions,
                not report.deletion_ledger_available,
            )
        )
        return 2 if args.fail_on_drift and has_drift else 0
    finally:
        await pool.close()


def main():
    args = parse_args()
    try:
        exit_code = asyncio.run(run(args))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "error": "R2 reconciliation failed.",
                    "error_type": exc.__class__.__name__,
                },
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        raise SystemExit(1) from exc
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
