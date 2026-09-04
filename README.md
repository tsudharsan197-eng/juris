# Juris.

Premium React landing page and auth-ready frontend for an AI legal intelligence platform.

## Project memory and recovery

AI and maintainer context is versioned with the project:

- [`AGENTS.md`](AGENTS.md) defines the collaboration and memory-maintenance protocol.
- [`MEMORY.md`](MEMORY.md) records the current durable project state.
- [`docs/DECISIONS.md`](docs/DECISIONS.md) records architecture decisions.
- [`docs/PROJECT_RECOVERY.md`](docs/PROJECT_RECOVERY.md) explains Git, data, storage, secret, and deployment recovery.

Run `./scripts/verify-project-memory.sh` to validate the memory baseline. Use `./scripts/create-recovery-bundle.sh /path/to/off-device-backup` for a portable copy of committed Git history.

## Run locally

```bash
npm install
npm run dev
```

## Supabase auth

Copy `.env.example` to `.env` and set:

```bash
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

The auth UI includes create account, sign in, forgot password, and reset password routes. The reset flow is prepared for Supabase recovery redirects to `/reset-password`.

## Secure document uploads

The React app includes `/upload-document` and `/documents`. Uploads use this flow:

1. React validates PDF/DOC/DOCX files up to 25MB.
2. React sends the file to FastAPI as `multipart/form-data` at `/api/documents/upload`.
3. FastAPI verifies the Supabase access token with Supabase Auth.
4. FastAPI creates pending document metadata, then uploads the file to private Cloudflare R2 with server-side credentials.
5. FastAPI marks the metadata uploaded only after R2 succeeds. Failed or uncertain storage attempts record rollback intent before attempting cleanup.

Run the API:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Apply the database migration in `backend/db/migrations/001_documents_r2.sql`.
Apply `backend/db/migrations/002_document_text.sql` to store extracted PDF text, apply `backend/db/migrations/003_document_chunks.sql` to store overlapping text chunks, apply `backend/db/migrations/004_chunk_embeddings.sql` to add pgvector embeddings, then apply `backend/db/migrations/006_openai_embeddings.sql` to support 1536-dimensional OpenAI embeddings. Apply `backend/db/migrations/007_ai_outputs.sql` for generated-analysis caching, `backend/db/migrations/008_juris_compass.sql` for private Compass conversation history, `backend/db/migrations/009_hybrid_ocr_processing.sql` for OCR status, page, confidence, and chunk-source metadata, and `backend/db/migrations/010_r2_lifecycle_security.sql` for the durable R2 deletion ledger plus RLS/grant hardening.

The backend needs `SUPABASE_URL` and `SUPABASE_ANON_KEY` or `SUPABASE_SERVICE_ROLE_KEY` to call `{SUPABASE_URL}/auth/v1/user`. AI uses the OpenAI API with `OPENAI_API_KEY`, `OPENAI_EMBED_MODEL=text-embedding-3-small`, `OPENAI_CHAT_MODEL=gpt-5-mini`, `OPENAI_ANALYSIS_MODEL=gpt-5-mini`, `OPENAI_ANALYSIS_MAX_OUTPUT_TOKENS=8000`, and `OPENAI_COMPASS_MODEL=gpt-5-mini`. Clause Intelligence and Risk Analysis use typed OpenAI structured outputs with bounded retries and page-aware batching for long documents. R2 credentials only belong in backend environment variables. The frontend uses `VITE_API_BASE_URL` and Supabase public client keys only.

Documents embedded with Ollama or any older provider/dimension must be deleted and re-uploaded or reprocessed so their chunks are regenerated with `text-embedding-3-small` 1536-dimensional embeddings.

## R2 lifecycle safety

Document deletion is recorded in `r2_deletion_jobs` before the object is removed. The backend attempts deletion immediately, retries transient failures with exponential backoff capped at one hour, and deletes the database document row only after R2 confirms success. Upload rollback uses the same ledger before removing any object. A pending deletion returns a clear 503 response so the existing UI does not claim that deletion has finished.

While running, the backend polls recorded deletion jobs every minute and reconciles storage shortly after startup and every 24 hours by default. Historical or otherwise unknown R2 objects are fingerprinted and reported, never deleted automatically. An in-process worker cannot run while Render is asleep or stopped; use an always-on worker or an external scheduler invoking the retry command for reliable unattended operation.

```bash
R2_MAINTENANCE_ENABLED=true
R2_MAINTENANCE_STARTUP_DELAY_SECONDS=30
R2_RECONCILE_INTERVAL_SECONDS=86400
R2_DELETION_RETRY_BATCH_SIZE=20
R2_DELETION_RETRY_INTERVAL_SECONDS=60

# Read-only drift report. It prints counts and key fingerprints, not filenames.
python3 backend/scripts/reconcile_r2_storage.py

# Retry only jobs already present in r2_deletion_jobs.
python3 backend/scripts/reconcile_r2_storage.py --retry-recorded-deletions
```

Apply migration `010` as the Supabase `postgres` administration role before deploying the ledger-backed delete path. It is transactional and repeatable, but still requires a backup and staging verification. Do not reapply `009` for this release. Review unknown objects against an authorized database/storage backup before any manual removal. See [`docs/P0_STORAGE_ROLLOUT.md`](docs/P0_STORAGE_ROLLOUT.md) for the remaining production gates and verification commands.

## Document security controls

Apply `backend/db/migrations/011_document_processing_limits.sql` after `010` before deploying the P1 release. Upload and reprocess share a per-user Postgres-backed budget, defaulting to five attempts per ten-minute window. It persists across workers/restarts and fails closed with 503 if the quota table is unavailable. Rejected attempts return 429 with `Retry-After`; they do not extend the current window. Controls are configured through:

```bash
DOCUMENT_PROCESSING_REQUEST_LIMIT=5
DOCUMENT_PROCESSING_WINDOW_SECONDS=600
```

Upload requests have a 26 MiB total multipart ceiling, including chunked requests, in addition to the existing 25 MiB file limit. Partial parser spool files close on limit errors. This does not replace edge-level request-rate, connection, or timeout controls.

API responses and signed downloads use `private, no-store, max-age=0`. Signed response overrides protect existing objects without rewriting them. PDF previews remain inline with a sanitized filename; Word documents use attachment disposition. The five-minute signature lifetime remains unchanged. The temporary public `/debug/openai` endpoint is removed in this release.

See [`docs/P1_DOCUMENT_SECURITY.md`](docs/P1_DOCUMENT_SECURITY.md) for test evidence, deployment order, and remaining provider controls.

## Security operations

Run `backend/.venv/bin/python backend/scripts/security_check.py --api-base-url https://YOUR-BACKEND-HOST` for read-only database permissions, storage drift/backlog, and HTTP checks. Output contains redacted findings; exit 2 means a measured failure, 3 means incomplete evidence, and 1 means an execution error. It never deletes objects, applies migrations, reads document response bodies, or invokes OpenAI. Provider-only controls remain explicitly unverified, not silently passed.

P2 needs no new migration. Pending 010/011 still precede deployment. The Docker image includes the operational scripts and excludes environment files and private artifacts from its build context. The credential-free GitHub regression workflow takes effect after commit/push; it is not a production monitor or backup. See [`docs/P2_SECURITY_OPERATIONS.md`](docs/P2_SECURITY_OPERATIONS.md) for evidence and remaining release gates.

## Hybrid PDF text extraction and OCR

Juris first extracts each PDF page with `pypdf`. Pages with usable native text skip OCR. Empty, marker-only, corrupted, or very short pages are rendered in memory with PyMuPDF and read locally with Tesseract. Mixed PDFs therefore OCR only the unreadable pages. The resulting pages continue through the existing chunk, OpenAI embedding, RAG, summary, intelligence, clause, risk, and compare paths.

Install the Tesseract executable before starting the backend locally:

```bash
# macOS
brew install tesseract

# Debian or Ubuntu
sudo apt-get update
sudo apt-get install -y tesseract-ocr tesseract-ocr-eng

cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest -q
uvicorn app.main:app --reload
```

OCR configuration uses these backend environment variables:

```bash
OCR_ENABLED=true
OCR_DPI=300
OCR_RETRY_DPI=400
OCR_LANGUAGE=eng
OCR_MIN_PAGE_CHARACTERS=80
OCR_TIMEOUT_SECONDS=180
OCR_MAX_PAGES=100
OCR_MAX_IMAGE_DIMENSION=5000
OCR_MAX_IMAGE_PIXELS=25000000
OCR_LOW_CONFIDENCE_THRESHOLD=0.60
OCR_QUALITY_THRESHOLD=72
OCR_MAX_ATTEMPTS_PER_PAGE=12
OCR_DEBUG=false
OCR_DEBUG_DIR=tmp/ocr-debug
```

High-quality pages use one OCR pass. Pages with weak confidence or incomplete visual-text coverage use a bounded set of PSM, orientation, preprocessing, and higher-DPI retries, then retain the strongest legal-text result. `OCR_DEBUG=true` is development-only: it writes rendered/candidate images, local OCR text, and scoring data under `OCR_DEBUG_DIR`; keep it disabled in production and delete artifacts after diagnosis.

Processing statuses move through `checking_text`, optional `ocr_required` and `running_ocr`, `extracting`, `chunking`, and `embedding`. A document becomes `processed` only after validated chunks and embeddings are stored. Low-confidence or visually incomplete scans become `processed_with_warning`; unreadable scans become `needs_review` or `failed`. The authenticated `POST /api/documents/{document_id}/reprocess` endpoint preserves the private R2 object and atomically replaces extracted text, chunks, embeddings, and cached AI outputs. Existing incorrectly processed PDFs must use the Reprocess action on the Documents page before regenerated AI results can use the improved OCR text.

OCR page images are held in memory only, bounded by the upload size, page-count, rendered-pixel, dimension, and timeout limits, and are not sent to an external OCR provider.

### Render deployment

Tesseract is an operating-system package, so deploy the backend with [`backend/Dockerfile`](backend/Dockerfile):

1. In the Render service, set **Language** to **Docker**.
2. If the Render root directory is the repository root, set **Dockerfile Path** to `backend/Dockerfile`. If the root directory is already `backend`, use `./Dockerfile`.
3. Remove the old Python build command. The Docker image installs Python requirements and `tesseract-ocr`/`tesseract-ocr-eng`.
4. Keep the existing backend environment variables and add the OCR variables above.
5. Keep `/health` as the health-check path. The image starts Uvicorn on `0.0.0.0:${PORT:-10000}`.
6. Apply migrations through `backend/db/migrations/011_document_processing_limits.sql` before deploying this release.

## Juris Compass

`/juris-compass` is the standalone, jurisdiction-grounded legal research workspace. It also appears as system 06 in a document workspace for convenient access, but uses the separate `POST /api/juris-compass/chat` flow and never receives a document id, retrieves document chunks, or performs embedding search.

Compass uses OpenAI Responses web search with official legal-source domain filters where available. Answers include checked date, jurisdiction, legal basis, clickable sources, and a permanent legal-information disclaimer. Conversation history is user-owned and separate from document chat.
