#!/usr/bin/env python3
"""Read-only P2 security checks. Never applies migrations or deletes objects."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import asyncpg
import httpx
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.r2_lifecycle_service import object_records, reconcile_r2_storage
from app.services.security_audit_service import (
    SecurityCheck, audit_configuration, audit_database, audit_http,
    audit_reconciliation, security_report, unresolved_provider_checks, validate_api_base_url,
)


def bounded_inventory(client, bucket: str, maximum: int):
    pages = client.get_paginator("list_objects_v2").paginate(
        Bucket=bucket, PaginationConfig={"MaxItems": maximum + 1, "PageSize": 1000},
    )
    items = []
    for page in pages:
        items.extend(page.get("Contents", []))
        if len(items) > maximum:
            raise ValueError("Inventory limit reached; never report a truncated inventory as healthy.")
    return object_records(items)


async def run(args) -> tuple[dict, int]:
    checks = audit_configuration(os.environ)
    connection = None
    try:
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            raise ValueError("Database configuration absent")
        connection = await asyncpg.connect(database_url, statement_cache_size=0, timeout=10, command_timeout=15)
        async with connection.transaction(readonly=True, isolation="repeatable_read"):
            checks.extend(await audit_database(connection, backlog_max_age_seconds=args.backlog_max_age))
        try:
            # Reuse the app's signed R2 client without starting FastAPI or any workers.
            from app.main import get_r2_client, get_env

            async def inventory():
                return await asyncio.to_thread(bounded_inventory, get_r2_client(), get_env("R2_BUCKET_NAME"), args.max_objects)

            async with connection.transaction(readonly=True, isolation="repeatable_read"):
                report = await reconcile_r2_storage(connection, list_objects=inventory)
            checks.append(audit_reconciliation(report))
        except Exception as exc:
            checks.append(SecurityCheck("storage.reconciliation", "unknown", "Inventory unavailable or bounded limit reached.", {"error_type": type(exc).__name__}))
    except Exception as exc:
        checks.append(SecurityCheck("database.audit", "unknown", "Database audit unavailable; no migration was applied.", {"error_type": type(exc).__name__}))
    finally:
        if connection:
            await connection.close(timeout=5)

    if args.api_base_url:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            checks.extend(await audit_http(client, args.api_base_url))
    else:
        checks.append(SecurityCheck("http.deployment", "unknown", "Pass --api-base-url to check the actual backend deployment."))
    checks.extend(unresolved_provider_checks())
    report, code = security_report(checks)
    report["checked_at"] = datetime.now(timezone.utc).isoformat()
    return report, code


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base-url", type=validate_api_base_url, help="Actual Render/backend base URL, not the frontend.")
    parser.add_argument("--backlog-max-age", type=int, default=900, help="Alert after this many seconds pending (minimum 60).")
    parser.add_argument("--max-objects", type=int, default=10000, help="Inventory bound; exceeding it is unknown, not a pass.")
    args = parser.parse_args()
    if args.backlog_max_age < 60 or not 1 <= args.max_objects <= 100000:
        parser.error("backlog-max-age must be >=60 and max-objects must be 1-100000")
    load_dotenv(BACKEND_ROOT / ".env")
    load_dotenv(BACKEND_ROOT.parent / ".env")
    try:
        report, code = asyncio.run(asyncio.wait_for(run(args), timeout=180))
    except Exception as exc:
        report = {"mode": "read-only", "status": "error", "error_type": type(exc).__name__}
        code = 1
    print(json.dumps(report, indent=2, sort_keys=True))
    raise SystemExit(code)


if __name__ == "__main__":
    main()
