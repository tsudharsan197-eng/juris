# Juris.

Premium React landing page and auth-ready frontend for an AI legal intelligence platform.

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
4. FastAPI uploads the file to private Cloudflare R2 with server-side credentials.
5. FastAPI saves metadata in the `documents` table.

Run the API:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Apply the database migration in `backend/db/migrations/001_documents_r2.sql`.
Apply `backend/db/migrations/002_document_text.sql` to store extracted PDF text, apply `backend/db/migrations/003_document_chunks.sql` to store overlapping text chunks, apply `backend/db/migrations/004_chunk_embeddings.sql` to add pgvector embeddings, then apply `backend/db/migrations/006_openai_embeddings.sql` to support 1536-dimensional OpenAI embeddings. Apply `backend/db/migrations/007_ai_outputs.sql` for generated-analysis caching, `backend/db/migrations/008_juris_compass.sql` for private Compass conversation history, and `backend/db/migrations/009_hybrid_ocr_processing.sql` for OCR status, page, confidence, and chunk-source metadata.

The backend needs `SUPABASE_URL` and `SUPABASE_ANON_KEY` or `SUPABASE_SERVICE_ROLE_KEY` to call `{SUPABASE_URL}/auth/v1/user`. AI uses the OpenAI API with `OPENAI_API_KEY`, `OPENAI_EMBED_MODEL=text-embedding-3-small`, `OPENAI_CHAT_MODEL=gpt-5-mini`, `OPENAI_ANALYSIS_MODEL=gpt-5-mini`, `OPENAI_ANALYSIS_MAX_OUTPUT_TOKENS=8000`, and `OPENAI_COMPASS_MODEL=gpt-5-mini`. Clause Intelligence and Risk Analysis use typed OpenAI structured outputs with bounded retries and page-aware batching for long documents. R2 credentials only belong in backend environment variables. The frontend uses `VITE_API_BASE_URL` and Supabase public client keys only.

Documents embedded with Ollama or any older provider/dimension must be deleted and re-uploaded or reprocessed so their chunks are regenerated with `text-embedding-3-small` 1536-dimensional embeddings.

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
6. Apply `backend/db/migrations/009_hybrid_ocr_processing.sql` before reprocessing or uploading PDFs with this release.

## Juris Compass

`/juris-compass` is the standalone, jurisdiction-grounded legal research workspace. It also appears as system 06 in a document workspace for convenient access, but uses the separate `POST /api/juris-compass/chat` flow and never receives a document id, retrieves document chunks, or performs embedding search.

Compass uses OpenAI Responses web search with official legal-source domain filters where available. Answers include checked date, jurisdiction, legal basis, clickable sources, and a permanent legal-information disclaimer. Conversation history is user-owned and separate from document chat.
