# Juris Project Memory

Last verified against the repository: 2026-09-04.

## Product

Juris is an AI-powered legal intelligence platform. Users upload legal documents and work with seven systems:

1. Chat
2. Document Intelligence
3. Executive Summary
4. Clause Intelligence
5. Risk Analysis
6. Juris Compass
7. Compare

Document features must remain grounded in the uploaded document and preserve source/page references. Juris Compass is a separate, jurisdiction-aware legal research experience; it must never receive a document ID or retrieve document chunks.

## Current Stack

- Frontend: React 19, Vite 7, React Router, TypeScript/JSX, Framer Motion, GSAP, Lenis, Lucide icons, Tailwind tooling.
- Backend: FastAPI on Python 3.12.7, Uvicorn, asyncpg.
- Auth/database/vector search: Supabase Auth, Postgres, pgvector.
- Private file storage: Cloudflare R2.
- AI: OpenAI only. Default chat, analysis, and Compass model is `gpt-5-mini`; embeddings use `text-embedding-3-small` with 1536 dimensions.
- Extraction: native `pypdf` text first, then bounded local Tesseract OCR through PyMuPDF/Pillow/OpenCV when needed.
- Hosting: Vercel frontend and Render Docker backend.

There are no active Gemini or Ollama runtime paths. `backend/db/migrations/005_ollama_embeddings.sql` is historical; migration `006_openai_embeddings.sql` replaces the old embedding setup.

## Important Paths

- `src/main.tsx`: providers, routes, and route transitions.
- `src/App.tsx`: landing-page section composition.
- `src/pages/DocumentWorkspace.jsx`: seven-system document workspace and frontend AI state.
- `src/lib/documentsApi.js`: authenticated document API client and request timing logs.
- `src/components/JurisCompass.jsx`, `src/lib/compassApi.js`: Compass UI and separate API client.
- `src/editorial.css`: shared theme tokens and primary visual system.
- `src/workspace-modern.css`: processed-document workspace shell and tool layouts.
- `src/mobile.css`: mobile-only layout behavior.
- `backend/app/main.py`: FastAPI routes, auth/ownership checks, R2, OpenAI, caching, RAG, and orchestration.
- `backend/app/services/ocr_service.py`: OCR strategies, scoring, retries, and debug artifacts.
- `backend/app/services/document_processing_service.py`: extraction-to-chunk processing pipeline.
- `backend/app/services/structured_analysis_service.py`: structured analysis generation/retries.
- `backend/app/services/r2_lifecycle_service.py`: durable R2 deletion jobs, bounded retries, and report-only storage reconciliation.
- `backend/app/services/document_security_service.py`: database-backed upload/reprocess quotas and private-response headers.
- `backend/app/services/upload_limits_middleware.py`: multipart request-body ceiling, including chunked uploads.
- `backend/scripts/reconcile_r2_storage.py`: manual read-only drift report and recorded-job retry command.
- `backend/scripts/security_check.py`: read-only operational audit with redacted findings and nonzero failure/incomplete exits; no deletion or migration.
- `.github/workflows/security-regression.yml`: credential-free regression workflow, active only once committed/pushed.
- `backend/db/migrations/`: ordered Supabase migrations `001` through `011`.
- `backend/tests/`: OCR, processing, and structured-analysis tests.

## Routes

Frontend routes:

- `/`
- `/sign-in`
- `/create-account`
- `/forgot-password`
- `/reset-password`
- `/upload-document`
- `/documents`
- `/documents/:documentId/workspace`
- `/juris-compass`

Primary authenticated backend routes:

- `POST /api/documents/upload`
- `GET /api/documents`
- `GET /api/documents/{document_id}/download-url`
- `POST /api/documents/{document_id}/reprocess`
- `POST /api/documents/{document_id}/ask`
- `POST /api/documents/{document_id}/summary`
- `POST /api/documents/{document_id}/intelligence`
- `POST /api/documents/{document_id}/clauses`
- `POST /api/documents/{document_id}/risk-analysis`
- `POST /api/documents/{document_id}/compare`
- `DELETE /api/documents/{document_id}`
- Compass conversation CRUD under `/api/juris-compass/conversations`
- `POST /api/juris-compass/chat`

## Non-Negotiable Behavior

- Every document route authenticates the Bearer token and verifies ownership.
- Uploads must never be accepted without a valid authenticated session.
- Upload/reprocess share a Postgres-backed per-user budget (default five attempts per ten-minute window). Rate denials return 429 + Retry-After; quota storage failure returns 503. Do not replace this with a process-local counter.
- Private API and signed file responses are no-store. Signed PDF URLs retain inline preview and five-minute expiry. Upload request bodies are capped at 26 MiB including multipart overhead; the file limit remains 25 MiB.
- R2 credentials and `OPENAI_API_KEY` stay backend-only. Never expose or log secrets.
- Chat remains live per question and is not globally cached.
- Generated outputs are cached in `ai_outputs` for summary, document intelligence, clauses, risks, and comparison.
- Cache hashes must change when document content/version changes; compare hashes include both documents.
- Reprocessing replaces stale extracted text, chunks, embeddings, and cached AI outputs.
- Document deletion is ledger-backed: record intent first, confirm R2 deletion, then delete the database row so child text/chunks/cached outputs cascade.
- Unknown R2 objects are never deleted automatically. Reconciliation reports counts, dates, bytes, and truncated SHA-256 key fingerprints until ownership is adjudicated.
- Compare uses bounded context and concise output; do not restore full-document prompts for long documents.
- Preserve structured JSON response schemas and frontend API contracts unless a task explicitly changes them.
- Do not weaken document grounding or let a model invent unsupported legal details.

## OCR Pipeline

- Native text pages skip OCR when usable.
- Scanned or incomplete pages use bounded multi-pass OCR with orientation/preprocessing/PSM candidates and quality scoring.
- Default OCR DPI is 300, with a bounded retry at 400 DPI.
- Preserve page order, clause numbers, names, dates, amounts, percentages, source metadata, and meaningful short lines.
- `OCR_DEBUG=false` by default. Debug artifacts may contain confidential text and must never be enabled or logged in production.
- Existing documents need the Reprocess action before they benefit from OCR improvements.
- Render must use `backend/Dockerfile` because Tesseract is an OS dependency.

## Frontend and Design Invariants

- Preserve the Juris editorial/brutalist identity, uploaded font system, sharp geometry, and semantic accents.
- Shared dark palette is cool ink/graphite, not the old brown/sepia palette.
- Orange/rust is the primary brand action, cobalt is interaction/source, lime is ready/success, and red-orange is risk/destructive.
- Light mode is intentionally designed and must not be treated as a simple inversion.
- Landing-page desktop transitions are considered intentional; avoid changing them unless explicitly requested.
- The document workspace is an application shell: page-level scrolling is locked on desktop, the taskbar is stationary, and only the active content viewport scrolls.
- Long Executive Summary content must reach its true bottom. Chat history scrolls independently while its composer remains available.
- Mobile uses responsive navigation/tool controls and must not squeeze the desktop sidebar into the viewport.
- Respect `prefers-reduced-motion`, keyboard access, visible focus, 44px touch targets, and readable contrast.

## Environment Variables

Frontend public configuration:

- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`
- `VITE_API_BASE_URL`

Backend configuration includes:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY` or `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL`
- R2 credentials/bucket configuration
- `R2_MAINTENANCE_ENABLED`, startup delay, reconciliation interval, and deletion retry batch size
- `DOCUMENT_PROCESSING_REQUEST_LIMIT`, `DOCUMENT_PROCESSING_WINDOW_SECONDS`
- `OPENAI_API_KEY`
- `OPENAI_EMBED_MODEL`
- `OPENAI_CHAT_MODEL`
- `OPENAI_ANALYSIS_MODEL`
- `OPENAI_COMPASS_MODEL`
- OCR settings documented in `README.md`

Never put actual credential values in this file, source control, logs, screenshots, or frontend code.

## Local Commands

Frontend:

```bash
npm install
npm run dev
npm run build
```

Backend:

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Verification:

```bash
python3 -m py_compile backend/app/main.py
cd backend && python -m pytest -q
npm run build
```

Install local Tesseract on macOS with `brew install tesseract` before exercising scanned-PDF tests.

## Database and Deployment

- Apply migrations in numeric order through `011_document_processing_limits.sql`.
- P1 is also local, not deployed. Apply both pending migrations 010 and 011 before deploying. See `docs/P1_DOCUMENT_SECURITY.md` for staged verification and provider-level controls still outstanding.
- P2 adds a read-only schema/permissions, storage/backlog, and optional HTTP checker plus Docker packaging and CI checks; no new migration. See `docs/P2_SECURITY_OPERATIONS.md`. No external monitor, provider hardening, or verified backup/restore has been configured by these phases.
- The 2026-09-04 P2 audit found 0 direct browser read/write grants but residual other privileges on 11 relations and 8 default ACL entries; pending 010 must still be rolled out. The 5 historical R2 orphans remain unchanged. Provider public domains/token scopes and deployed API state are not verified by local HTTP tests.
- P0 lifecycle code is local and not yet deployed; the read-only production check on 2026-09-04 found no deletion ledger. Apply `010` before this release, not `009` again. See `docs/P0_STORAGE_ROLLOUT.md`.
- Deletion retries poll every 60 seconds while the backend is running; storage inventory runs daily. Sleeping/stopped services need an external scheduler or always-on worker. Pending deletion returns 503, never a false success.
- A crash during upload leaves an `uploading` row for investigation. Reconciliation reports these without automatically deleting possibly valid files.
- Do not reapply a migration blindly; first verify whether it is idempotent and whether the target project already contains it.
- Python is pinned to `python-3.12.7` in both runtime files and the Docker image.
- Render health check: `GET /health`.
- The temporary public `GET /debug/openai` endpoint is removed from local code. Confirm 404 after production redeployment; do not recreate an unauthenticated provider diagnostic.

## Current Repository Notes

- Current branch at last verification: `main`.
- `deck_assets/` is untracked presentation-generation material. Do not delete, commit, or treat it as application code without an explicit request.
- `tmp/pdfs/` contains local OCR trace fixtures/artifacts. Do not expose their contents or commit new confidential document artifacts.
- The Figma Slides deck created for Juris is separate from application runtime code.

## Working Method

- At the start of a new AI session, read `AGENTS.md`, this file, `docs/DECISIONS.md`, and relevant current code.
- Read the current implementation before editing; prior conversation context may be stale.
- Keep changes scoped and preserve unrelated user work in a dirty worktree.
- Use existing components, theme tokens, API clients, and service boundaries before adding abstractions.
- For frontend changes, verify in the browser at relevant desktop/mobile sizes and inspect console errors.
- For backend changes, run focused tests plus `py_compile`; broaden tests when shared processing, auth, caching, or API contracts change.
- Update this file only when durable architecture, commands, invariants, routes, or deployment requirements change.
- Record significant decisions in `docs/DECISIONS.md` and follow `docs/PROJECT_RECOVERY.md` for off-device backups and restoration.
