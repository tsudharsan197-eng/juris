# P0 Storage Rollout

## Status

The lifecycle changes are implemented locally. Production has not been migrated or redeployed by this task. This is not a completed backup deployment.

Read-only reconciliation on 2026-09-04 found:

- Five document rows, all with matching R2 objects.
- Ten total R2 objects; five unknown objects totaling 3,435,637 bytes.
- No document rows missing their source objects and no incomplete upload rows.
- No `r2_deletion_jobs` table yet.
- Zero objects deleted by the audit.

Unknown objects remain report-only. A missing database row alone does not establish that an object may be destroyed. Resolve ownership, intended retention, and backup availability before explicitly authorizing any cleanup. Do not store private filenames or document contents in Git.

## Release Order

1. Verify a restorable, encrypted database backup and a separate R2 recovery copy. Git is not a data backup.
2. Apply `backend/db/migrations/010_r2_lifecycle_security.sql` in staging as `postgres`. It runs in a transaction, creates the deletion ledger, enables RLS, revokes client table grants, and protects future-table defaults. It does not alter Auth schemas or remove document data. Default-privilege changes apply to future objects created by `postgres`; other DDL roles require their own defaults.
3. Test authenticated upload, download, delete, failure/retry, and cross-user denial in staging. Repeat migration 010 there to confirm deployment compatibility. Do not reapply migration 009 for this change.
4. Apply 010 to the confirmed production project, then deploy the backend. Deploying first makes deletes fail closed with 503 because the ledger is unavailable.
5. Keep an always-on backend/worker, or configure an external scheduler to invoke `--retry-recorded-deletions`. The in-process worker polls every 60 seconds only while the service runs. Batch size is 20; retries use 30-second exponential backoff capped at one hour; full inventory runs daily.
6. Run the read-only report again. Review missing objects, incomplete uploads, pending deletions, and unknown objects. Alert on `[r2:maintenance:error]`, `[r2:upload:rollback_pending]`, and drift in the report. Alert delivery is not configured by this patch.

The application reports deletion success only after R2 deletion and transactional database finalization. A pending delete keeps the existing row visible and returns 503 with a retry message. Existing signed download URLs may remain usable until object removal or their five-minute expiry.

A crash during upload may leave an `uploading` row. These rows block concurrent delete/reprocess and appear in reconciliation; inspect the object and logs before an administrator resolves them. Unknown objects and completed-ledger objects that unexpectedly reappear are not automatically erased. No distributed transaction can eliminate all ambiguous storage outcomes.

## Verification Commands

From the repository root with backend dependencies installed:

```bash
python3 -m py_compile backend/app/main.py backend/app/services/r2_lifecycle_service.py
backend/.venv/bin/python -m pytest backend/tests -q
npm run build
./scripts/verify-project-memory.sh
backend/.venv/bin/python backend/scripts/reconcile_r2_storage.py --fail-on-drift
```

The final command is read-only and exits 2 on drift or a missing ledger. It logs no file contents or full object keys. The following command mutates only jobs already recorded by an authorized deletion/rollback:

```bash
backend/.venv/bin/python backend/scripts/reconcile_r2_storage.py --retry-recorded-deletions
```

An optional isolated PostgreSQL-compatible SQL smoke test requires no production credentials. Install its test-only package outside the repository; this does not add an application dependency:

```bash
npm install --prefix /tmp/juris-p0-sql-validation --no-audit --no-fund @electric-sql/pglite@0.5.8
P0_SQL_TEST_DEPS=/tmp/juris-p0-sql-validation node backend/tests/r2_sql_smoke.mjs
```

The smoke test applies the exact migration twice and checks data retention, RLS/grants, future-table privacy, legacy-policy isolation, parameterized queue SQL, active leases, and retry backoff. It does not replace staging tests on Supabase or multi-worker load testing.

## Rollback

Keep migration 010 in place if the application release is rolled back. Do not drop the ledger, disable RLS, or restore client grants. Disable the in-process worker with `R2_MAINTENANCE_ENABLED=false` if investigation is needed, understanding that automatic retries will pause. Review pending jobs before resuming. Source-object recovery requires the independent storage backup.
