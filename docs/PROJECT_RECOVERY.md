# Juris Project Recovery Runbook

Git protects the application source and its versioned project memory. It does not, by itself, back up production data, private R2 objects, deployment configuration, or secrets.

## Recovery Inventory

| Asset | System of record | Recovery requirement |
| --- | --- | --- |
| Source code, migrations, tests, AI memory | GitHub `origin` | Commit and push important checkpoints |
| Architecture decisions | `docs/DECISIONS.md` in Git | Update with the related code change |
| Current AI handoff context | `MEMORY.md` in Git | Keep current and free of secrets |
| Supabase schema | `backend/db/migrations/` in Git | Apply migrations in numeric order to a fresh project |
| Supabase production data/auth/vector rows | Supabase | Enable provider backups or make encrypted, access-controlled exports |
| Uploaded legal documents | Private Cloudflare R2 | Maintain an encrypted, access-controlled off-site copy and test object restore independently of the live bucket |
| Deployment settings | Vercel and Render | Record non-secret names/requirements; export or document configuration separately |
| Credentials and API keys | Secret manager/password manager | Never store values in Git or recovery docs |
| Local OCR traces and private test PDFs | Local development storage | Treat as sensitive and disposable unless intentionally encrypted and archived |

## Normal Checkpoint Workflow

1. Inspect the worktree with `git status --short`.
2. Run the verification appropriate to the change.
3. Update `MEMORY.md` if durable project facts changed.
4. Add an ADR when a significant architecture or security decision changed.
5. Stage only intentional paths.
6. Commit with a descriptive message.
7. Push the branch to `origin`; an unpushed commit is not an off-device backup.
8. For important releases, create and push an annotated tag after verification.

Example:

```bash
git add src backend MEMORY.md docs
git commit -m "Describe the durable change"
git push origin HEAD
git tag -a checkpoint-YYYY-MM-DD -m "Verified Juris recovery checkpoint"
git push origin checkpoint-YYYY-MM-DD
```

Do not copy that `git add` command blindly when private or generated files are present. Prefer explicit paths.

## Portable Git Bundle

Create a complete portable copy of committed Git history on a different disk or a trusted encrypted/cloud-synced folder:

```bash
./scripts/create-recovery-bundle.sh /path/to/off-device-backup
```

The script creates a `.bundle` plus a SHA-256 checksum. It does not include uncommitted or untracked files. Keeping the bundle on the same disk as the repository does not protect against disk loss.

Restore from a bundle:

```bash
git clone /path/to/juris-YYYYMMDD-HHMMSS.bundle Juris-restored
cd Juris-restored
git remote set-url origin https://github.com/tsudharsan197-eng/juris.git
```

## Full Disaster Recovery

1. Clone GitHub or the newest verified Git bundle.
2. Read `AGENTS.md`, `MEMORY.md`, and `docs/DECISIONS.md` before changing code.
3. Restore secret values from the approved secret manager into local, Vercel, Render, Supabase, and R2 environments.
4. Provision Supabase and apply migrations in numeric order through `011_document_processing_limits.sql`. Restore production data only from an encrypted authorized backup.
5. Restore or reconnect the private R2 bucket and verify object ownership/key conventions.
6. Deploy the frontend to Vercel and the backend using `backend/Dockerfile` on Render.
7. Verify `/health`, authentication, upload, OCR/reprocess, each document AI tool, Juris Compass, download, and deletion.
8. Run `./scripts/verify-project-memory.sh`, backend tests, and the frontend build.

## Recovery Testing

- Test cloning from GitHub periodically.
- Verify a recovery bundle after creation; do not assume an unread bundle is a backup.
- Test database restore procedures in a non-production project.
- Test R2 export and restore with a non-sensitive object. The deletion ledger and reconciliation report protect consistency; they do not recover deleted bytes.
- Review who can access GitHub, Supabase, R2, Vercel, Render, and secret stores.
- Confirm `/debug/openai` returns 404 after deploying the P1 release. The local route has been removed.
