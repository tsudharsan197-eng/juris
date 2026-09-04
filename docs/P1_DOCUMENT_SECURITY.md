# P1 Document Security

## Implemented Locally

- Shared upload/reprocess quota: five attempts per user per 600-second fixed window, anchored to the first attempt. Atomic Postgres upsert prevents replica/restart bypass. Rejected requests do not extend the window. This is not a sliding-window or global concurrency limit.
- Quota denials: 429 with Retry-After. Missing/unavailable quota storage: 503 with Retry-After. Both stop before R2 upload, OCR, or embedding generation. Reprocess verifies document ownership before consuming quota. Upload quota is checked before file validation/processing, but after multipart parsing; invalid upload attempts can consume quota.
- Upload body limit: 26 MiB including multipart overhead, enforced against actual bytes even without an accurate Content-Length. Starlette closes partial spool files on rejection. Individual files remain limited to 25 MiB.
- Private response headers on API successes and error envelopes. No-store on new R2 objects and on signed GET overrides for existing objects. PDF previews stay inline; other supported file types use attachment disposition. Sanitized ASCII filenames prevent response-header injection.
- Public OpenAI diagnostic removed. No OpenAI prompt, model, document-grounding, or frontend changes.

## Local Verification

HTTP tests cover quota denial before storage, allowed uploads, cross-user denial before signing, reprocess ownership, missing authentication, dependency failure, Retry-After/CORS visibility, no-store headers, safe filenames, and diagnostic removal. Upload-body tests cover declared oversize, chunked oversize, understated length, and partial-file cleanup.

Isolated PostgreSQL-compatible tests apply migration 011 twice and exercise the exact backend query: saturation, stable expiry under denial, independent users, window reset, RLS/grants, and counter cleanup when an account is removed. This is not a multi-replica production load test.

Read-only R2 verification on 2026-09-04 used one existing PDF without saving or printing its contents, filename, or signed URL:

| Check | Observed |
| --- | --- |
| Signed GET | 200 |
| Cache-Control | private, no-store, max-age=0 |
| Content-Type | application/pdf |
| Content-Disposition | inline with filename |
| Same unsigned object request | 400; no file access |
| Tampered signed cache-header override | 403 |
| Objects modified | 0 |

## Deploy Safely

1. Complete the backup/staging gates in `docs/P0_STORAGE_ROLLOUT.md`.
2. Apply pending migration 010, then 011, as the Supabase administration role. Both scripts are transactional/repeatable. Do not reapply 009 for this release. Migration 011 adds one RLS-protected counter table referencing existing `auth.users`; it does not change Auth behavior.
3. Set `DOCUMENT_PROCESSING_REQUEST_LIMIT=5` and `DOCUMENT_PROCESSING_WINDOW_SECONDS=600` or deliberately chosen capacity values. All replicas must use the same settings. The code bounds these to 1-100 requests and 60-86400 seconds.
4. Redeploy Render. Deploying before migration 011 makes upload/reprocess fail closed with 503. Keep the ledger worker availability requirements from P0.
5. In staging, use a non-sensitive fixture to exhaust a test user's quota. Confirm 429, Retry-After, later recovery, and independence from another user. Verify upload, reprocess, download, deletion, and all unchanged AI tools.
6. Confirm production `/debug/openai` returns 404 and newly generated PDF URLs return no-store/inline response headers.

## Remaining Provider Controls

No production migrations, deployment, object metadata rewrite, token rotation, or bucket-setting changes were performed by this task.

- Verify the R2 app credential is limited to the intended bucket and required object operations. Rotate credentials through the secret manager with a tested rollback; do not revoke working credentials blindly.
- Configure connection/request-rate and upload-timeout limits on the actual backend ingress. A Vercel frontend-only rule does not protect a directly reachable Render backend.
- Decide global OCR concurrency and per-account storage quotas from measured capacity. Current limits do not prevent many authenticated accounts from submitting work at once or many slow requests within the byte limit.
- Review public bucket domains, bucket CORS, account access, and access/audit alert delivery with provider administration access. An unsigned request denial is not proof that every alternative public endpoint is disabled.
- No-store protects compliant caches, not intentionally downloaded copies. Old signed URLs retain their existing behavior until expiry, and old object metadata is not rewritten by this patch.

## Commands

```bash
python3 -m py_compile backend/app/main.py backend/app/services/document_security_service.py backend/app/services/upload_limits_middleware.py
backend/.venv/bin/python -m pytest backend/tests -q
npm run build
./scripts/verify-project-memory.sh
P0_SQL_TEST_DEPS=/tmp/juris-p0-sql-validation node backend/tests/document_security_sql_smoke.mjs
```

The optional SQL smoke test uses the same outside-repository PGlite installation documented for P0. No runtime dependency was added. These code changes are not active until migration and redeployment are completed.
