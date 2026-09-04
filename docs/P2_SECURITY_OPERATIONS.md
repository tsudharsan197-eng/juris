# P2 Security Operations

## Scope and Status

P2 adds read-only operational checks, a credential-free regression workflow, and safer Docker build packaging. It does not claim that provider hardening, production backups, alert delivery, OCR concurrency, or account storage quotas have been completed.

No new database migration is needed for P2. Pending P0/P1 migrations 010 and 011 are still required before their backend deployment. Do not reapply 009. No production schema, credentials, objects, bucket settings, or deployments were changed.

## Read-Only Check

From the repository root, with backend dependencies installed:

```bash
backend/.venv/bin/python backend/scripts/security_check.py
backend/.venv/bin/python backend/scripts/security_check.py --api-base-url https://YOUR-BACKEND-HOST
```

The URL must be the actual backend, not the Vercel frontend. HTTPS is required except for loopback development. Credentials, query strings, and fragments in the URL are rejected. Existing environment values take precedence over local `backend/.env` and root `.env`. No new environment variable is required.

The Docker image now includes both operational scripts. After redeployment, the equivalent command inside the container is `python scripts/security_check.py --api-base-url https://YOUR-BACKEND-HOST`. The image continues running as the existing non-root user. Environment files, private PDFs, logs, and local debug folders are excluded from the backend build context.

Checks include:

- Required tables, RLS, effective browser-role privileges (including column-only and inherited/PUBLIC grants), and future postgres-owned table/sequence grants.
- Client-callable, non-extension SECURITY DEFINER functions. Trigger-only functions are excluded from direct-call findings; their trigger bodies/search paths still need a separate review.
- Backend bypass-RLS role warning. The command does not replace ownership tests or silently change the production database role.
- Pending deletion age and stale processing leases. Default alert age is 900 seconds; use `--backlog-max-age` to choose a deliberate operational threshold. A newly queued job is not automatically considered stuck.
- Read-only R2 reconciliation, including missing objects, unknown orphans, incomplete uploads, and resurrected completed deletions. Inventory defaults to 10,000 objects; `--max-objects` can increase this up to 100,000. Exceeding the bound returns unknown, never a healthy truncated inventory.
- Local OCR debug configuration. This does not inspect Render environment variables remotely.
- Backend health, unauthenticated and invalid-token denial, and private no-store API headers. Response bodies are not read, and redirects are not followed.
- Legacy debug route discovery through a bounded OpenAPI response only. The script never invokes `/debug/openai`, which can create billable OpenAI calls on old deployments. An absent schema entry does not prove hidden routes are absent; review deployed code as well.

SQL runs in read-only transactions. The checker performs no INSERT/UPDATE/DELETE, migration, upload, download of private document content, deletion retry, or OpenAI generation. Reconciliation necessarily reads private object keys in memory but emits only aggregate counts, not keys, filenames, fingerprints, source text, URLs, credentials, or raw exception messages.

The database and R2 cannot share a snapshot. Concurrent uploads/deletes can create transient drift; recheck and investigate before remediation. Database commands time out after 15 seconds; HTTP probes after 10 seconds; the async audit has a 180-second deadline. R2 uses the existing bounded SDK retries/timeouts. Cancellation waits for any already-running SDK thread to return; use a runner-level deadline as well. This is not an unbounded inventory or a hard real-time process kill.

## Exit Codes and Monitoring

| Code | Meaning |
| --- | --- |
| 0 | All supplied checks passed |
| 1 | Audit execution failed or timed out |
| 2 | One or more measured checks failed |
| 3 | Evidence is incomplete or warnings require review |

Provider-only checks are explicitly unknown, so this complete CLI intentionally cannot return an all-clear until those checks are implemented/verified. Do not silence them to obtain a green release. Consume individual `checks[].name/status` values when monitoring a known issue; preserve the unresolved findings in the release review.

No recurring production monitor or external notification destination was configured. A local script invocation and a GitHub regression run are not uptime monitoring. Before enabling a protected external runner, choose its owner, interval, secret store, notification destination, and missing-run deadline. It needs read-only database/R2 inventory access, not a new public diagnostic endpoint. Verify delivery using a non-sensitive failure fixture and monitor the absence of expected runs.

## Live Evidence: 2026-09-04

| Observation | Result |
| --- | --- |
| Missing required tables | `r2_deletion_jobs`, `document_processing_limits` |
| Existing public tables without RLS | 0 |
| Relations with browser SELECT/INSERT/UPDATE/DELETE or equivalent column access | 0 |
| Relations retaining other browser privileges | 11; full revocation is part of pending 010 |
| Relevant default ACL entries granting future access | 8; pending 010 addresses table/sequence defaults |
| Directly callable non-extension SECURITY DEFINER functions | 0 after excluding trigger-only functions |
| Backend bypass-RLS role | Present; application ownership remains mandatory |
| Documents / R2 objects | 5 / 10 |
| Missing referenced objects | 0 |
| Unknown orphan objects | 5, totaling 3,435,637 bytes; unchanged and not deleted |
| Final audit exit code | 2, correctly reporting unresolved findings |

HTTP verification used a temporary local backend on port 8012, with maintenance explicitly disabled: health 200, missing/invalid auth 401 with private no-store headers, and no debug route in OpenAPI. It did not verify the currently deployed Render API. The configured frontend API URL was localhost; provider administration tools were unavailable in this task.

## Regression Workflow

`.github/workflows/security-regression.yml` runs on push, pull request, and manual dispatch once committed/pushed. It uses read-only repository permissions, immutable action SHAs, no persisted checkout credential, no production secrets, no deployment step, and no scheduled production probes.

It runs backend tests, compilation, three disposable SQL suites, frontend build, Docker packaging verification, and project-memory hygiene. The SQL suites use PGlite 0.5.8 installed outside application dependencies. They verify query semantics, not multi-replica production load or a full Supabase restoration.

Local verification: 132 backend tests, compilation, frontend build, all three SQL suites, workflow YAML parsing, and memory checks. Existing FastAPI/PyMuPDF deprecation warnings remain. Docker execution and the actual GitHub-hosted workflow were not run locally; CI includes the image build and command check.

## Remaining Release Gates

1. Complete encrypted database/object backup and staging checks from the P0 runbook. Verify restore, not just backup creation.
2. Apply 010 then 011; deploy the tested backend; rerun this command against the real backend URL.
3. Review historical orphans against an authorized recovery copy. No automatic purge.
4. Verify all R2 public surfaces: r2.dev, custom domains, and Workers. Review CORS and exact bucket token scopes. Do not grant administration permissions to the application token merely to run an audit.
5. Verify backend ingress rate/connection/time limits, then size global OCR capacity and per-account storage quotas from measured load. P1's per-user budget does not provide these controls.
6. Establish external monitoring and alert delivery; review privileged trigger functions and backend role separation without breaking Auth/account creation.

References: [Supabase RLS and grants](https://supabase.com/docs/guides/database/postgres/row-level-security), [Cloudflare public bucket surfaces](https://developers.cloudflare.com/r2/buckets/public-buckets/), [GitHub Actions security](https://docs.github.com/en/actions/reference/security/secure-use).
