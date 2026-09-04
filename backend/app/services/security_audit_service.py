from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Mapping
from urllib.parse import urlsplit

import httpx

from .r2_lifecycle_service import ReconciliationReport


REQUIRED_TABLES = (
    "documents", "document_text", "document_chunks", "ai_outputs",
    "juris_compass_conversations", "juris_compass_messages",
    "r2_deletion_jobs", "document_processing_limits",
)

# Inspect effective privileges, including inherited/PUBLIC and column grants.
RELATIONS_SQL = """
select c.relname, c.relkind, c.relrowsecurity,
  exists (
    select 1 from pg_roles r
    where r.rolname in ('anon', 'authenticated') and (
      has_table_privilege(r.oid, c.oid, 'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER')
      or has_any_column_privilege(r.oid, c.oid, 'SELECT,INSERT,UPDATE,REFERENCES')
    )
  ) as client_access,
  exists (
    select 1 from pg_roles r
    where r.rolname in ('anon', 'authenticated') and (
      has_table_privilege(r.oid, c.oid, 'SELECT,INSERT,UPDATE,DELETE')
      or has_any_column_privilege(r.oid, c.oid, 'SELECT,INSERT,UPDATE')
    )
  ) as data_access
from pg_class c join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public' and c.relkind in ('r', 'p', 'v', 'm', 'f')
"""

DEFINERS_SQL = """
select count(*)::integer from pg_proc p
join pg_namespace n on n.oid = p.pronamespace
where n.nspname = 'public' and p.prosecdef
  and p.prorettype not in ('trigger'::regtype, 'event_trigger'::regtype)
  and exists (select 1 from pg_roles r
    where r.rolname in ('anon', 'authenticated')
      and has_function_privilege(r.oid, p.oid, 'EXECUTE'))
  and not exists (select 1 from pg_depend d
    where d.classid = 'pg_proc'::regclass and d.objid = p.oid and d.deptype = 'e')
"""

DEFAULT_GRANTS_SQL = """
select count(*)::integer
from pg_default_acl d cross join lateral aclexplode(d.defaclacl) a
where d.defaclrole = 'postgres'::regrole and d.defaclobjtype in ('r', 'S')
  and (d.defaclnamespace = 0 or d.defaclnamespace = 'public'::regnamespace)
  and (a.grantee = 0 or exists (select 1 from pg_roles r
    where r.rolname in ('anon', 'authenticated')
      and pg_has_role(r.oid, a.grantee, 'USAGE')))
"""

BACKLOG_SQL = """
select count(*)::integer as pending,
  count(*) filter (where status = 'failed')::integer as failed,
  count(*) filter (where status = 'processing'
    and updated_at < now() - interval '15 minutes')::integer as stale_processing,
  coalesce(max(extract(epoch from now() - created_at)), 0)::double precision as oldest_seconds
from public.r2_deletion_jobs where status <> 'completed'
"""


@dataclass(frozen=True)
class SecurityCheck:
    name: str
    status: str
    detail: str
    metrics: dict = field(default_factory=dict)


def checked(name: str, ok: bool, detail: str, **metrics) -> SecurityCheck:
    return SecurityCheck(name, "pass" if ok else "fail", detail, metrics)


def audit_configuration(env: Mapping[str, str]) -> list[SecurityCheck]:
    debug_disabled = env.get("OCR_DEBUG", "false").strip().lower() in {"0", "false", "no", "off"}
    return [checked(
        "local_config.ocr_debug", debug_disabled,
        "OCR debug artifacts must be disabled in production; this checks this process only.",
    )]


async def audit_database(connection, *, backlog_max_age_seconds: int = 900) -> list[SecurityCheck]:
    rows = await connection.fetch(RELATIONS_SQL)
    present = {row["relname"] for row in rows}
    missing = sorted(set(REQUIRED_TABLES) - present)
    results = [checked(
        "database.required_tables", not missing,
        "Required tables must exist; migration files on disk do not prove deployment.",
        missing_tables=missing,
    )]
    role_count = await connection.fetchval("select count(*) from pg_roles where rolname in ('anon', 'authenticated')")
    results.append(checked("database.api_roles", role_count == 2, "Both Supabase API roles must be inspectable."))
    results.append(checked(
        "database.rls", all(row["relrowsecurity"] for row in rows if row["relkind"] in {"r", "p"}),
        "Public tables must enable RLS.",
        unprotected_tables=sum(not row["relrowsecurity"] for row in rows if row["relkind"] in {"r", "p"}),
    ))
    results.append(checked(
        "database.client_grants", not any(row["client_access"] for row in rows),
        "Juris document data uses backend ownership checks, not direct client table/view access.",
        granted_relations=sum(bool(row["client_access"]) for row in rows),
        data_read_write_relations=sum(bool(row["data_access"]) for row in rows),
    ))
    definers = await connection.fetchval(DEFINERS_SQL)
    results.append(checked(
        "database.security_definers", definers == 0,
        "Review client-callable non-extension SECURITY DEFINER functions; excludes trigger-only functions, which need separate trigger review.",
        callable_functions=definers,
    ))
    default_grants = await connection.fetchval(DEFAULT_GRANTS_SQL)
    results.append(checked(
        "database.default_grants", default_grants == 0,
        "New postgres-owned tables/sequences must not inherit browser-role grants.",
        grants=default_grants,
    ))
    role = await connection.fetchrow("select rolsuper, rolbypassrls from pg_roles where rolname = current_user")
    results.append(SecurityCheck(
        "database.backend_role", "warn" if role["rolsuper"] or role["rolbypassrls"] else "pass",
        "A bypass-RLS backend role requires tested application ownership checks; review least privilege separately.",
        dict(role),
    ))
    if "r2_deletion_jobs" in present:
        backlog = dict(await connection.fetchrow(BACKLOG_SQL))
        results.append(checked(
            "storage.deletion_backlog",
            backlog["oldest_seconds"] <= backlog_max_age_seconds and backlog["stale_processing"] == 0,
            "Old pending or stale processing jobs require worker/log investigation, not manual object deletion.",
            **backlog,
        ))
    else:
        results.append(SecurityCheck("storage.deletion_backlog", "unknown", "Migration 010 is required to inspect deletion jobs."))
    return results


def audit_reconciliation(report: ReconciliationReport) -> SecurityCheck:
    # Counts only: even key fingerprints are unnecessary for external monitoring.
    metrics = {key: value for key, value in report.as_dict().items() if isinstance(value, (bool, int))}
    drift = any((
        not report.deletion_ledger_available, report.incomplete_uploads,
        report.unknown_orphans, report.queued_orphans, report.completed_jobs_still_present,
        report.database_rows_missing_objects,
    ))
    return checked("storage.reconciliation", not drift, "Read-only inventory; unknown objects are never removed.", **metrics)


def validate_api_base_url(value: str) -> str:
    parsed = urlsplit(value)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or (parsed.scheme != "https" and not (local and parsed.scheme == "http"))):
        raise ValueError("Use an HTTPS backend base URL without credentials, query, or fragment; HTTP is loopback-only.")
    return value.rstrip("/")


async def audit_http(client: httpx.AsyncClient, base_url: str) -> list[SecurityCheck]:
    base = validate_api_base_url(base_url)
    results = []
    for name, path, headers, expected in (
        ("health", "/health", {}, 200),
        ("unauthenticated_documents", "/api/documents", {}, 401),
        ("invalid_bearer", "/api/documents", {"Authorization": "Bearer invalid-security-probe"}, 401),
    ):
        try:
            # Do not read response bodies: an auth regression could return private data.
            async with client.stream("GET", base + path, headers=headers, follow_redirects=False) as response:
                private = path.startswith("/api/")
                cache = {part.strip().lower() for part in response.headers.get("cache-control", "").split(",")}
                results.append(checked(
                    "http." + name,
                    response.status_code == expected and (not private or {"private", "no-store"} <= cache),
                    "Expected HTTP status and private no-store API headers; redirects are not followed.",
                    status_code=response.status_code,
                    private_no_store={"private", "no-store"} <= cache if private else None,
                ))
        except httpx.HTTPError as exc:
            results.append(SecurityCheck("http." + name, "unknown", "HTTP probe unavailable.", {"error_type": type(exc).__name__}))
    try:
        # Never call the legacy diagnostic: old deployments make paid OpenAI requests.
        async with client.stream("GET", base + "/openapi.json", follow_redirects=False) as response:
            if response.status_code != 200:
                results.append(SecurityCheck("http.debug_route_schema", "unknown", "OpenAPI unavailable; diagnostic removal cannot be checked through schema."))
            else:
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 1024 * 1024:
                        raise ValueError("Schema limit exceeded")
                paths = json.loads(data)["paths"]
                if not isinstance(paths, dict):
                    raise ValueError("Invalid schema")
                results.append(checked(
                    "http.debug_route_schema", not any(path.rstrip("/") == "/debug/openai" for path in paths),
                    "Diagnostic absent from advertised schema only; hidden routes require deployed-code review.",
                ))
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        results.append(SecurityCheck("http.debug_route_schema", "unknown", "Schema could not be verified.", {"error_type": type(exc).__name__}))
    return results


def unresolved_provider_checks() -> list[SecurityCheck]:
    return [SecurityCheck(name, "unknown", detail) for name, detail in (
        ("provider.r2_public_access", "Verify r2.dev, custom domains, Workers routes, and CORS in Cloudflare administration."),
        ("provider.credentials", "Verify bucket-scoped token permissions, rotation, and secret-manager recovery."),
        ("provider.ingress_capacity", "Verify backend ingress limits, global OCR capacity, and account storage quotas."),
        ("provider.backup_restore", "Verify independent encrypted database/object backups and a successful restore drill."),
        ("provider.monitor_delivery", "Verify an external runner, alert delivery, and missing-run detection; local execution is not monitoring."),
    )]


def security_report(checks: list[SecurityCheck]) -> tuple[dict, int]:
    failed = any(check.status == "fail" for check in checks)
    incomplete = not checks or any(check.status in {"unknown", "warn"} for check in checks)
    status = "fail" if failed else "incomplete" if incomplete else "pass"
    return {"mode": "read-only", "status": status, "checks": [asdict(check) for check in checks]}, 2 if failed else 3 if incomplete else 0
