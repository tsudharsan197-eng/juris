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
Apply `backend/db/migrations/002_document_text.sql` to store extracted PDF text, apply `backend/db/migrations/003_document_chunks.sql` to store overlapping text chunks, apply `backend/db/migrations/004_chunk_embeddings.sql` to add pgvector embeddings, then apply `backend/db/migrations/006_openai_embeddings.sql` to support 1536-dimensional OpenAI embeddings. PDF uploads are processed with `pypdf`; successful extraction, chunking, and embedding sets `documents.status` to `processed`, and extraction failures set it to `extraction_failed`.

The backend needs `SUPABASE_URL` and `SUPABASE_ANON_KEY` or `SUPABASE_SERVICE_ROLE_KEY` to call `{SUPABASE_URL}/auth/v1/user`. AI uses the OpenAI API with `OPENAI_API_KEY`, `OPENAI_EMBED_MODEL=text-embedding-3-small`, `OPENAI_CHAT_MODEL=gpt-5-mini`, and `OPENAI_ANALYSIS_MODEL=gpt-5-mini`. R2 credentials only belong in backend environment variables. The frontend uses `VITE_API_BASE_URL` and Supabase public client keys only.

Documents embedded with Ollama or any older provider/dimension must be deleted and re-uploaded or reprocessed so their chunks are regenerated with `text-embedding-3-small` 1536-dimensional embeddings.
