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
2. React sends the Supabase access token to FastAPI.
3. FastAPI verifies the access token with Supabase Auth and creates a short-lived Cloudflare R2 presigned PUT URL.
4. React uploads directly to R2.
5. React calls FastAPI to save metadata in the `documents` table.

Run the API:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Apply the database migration in `backend/db/migrations/001_documents_r2.sql`.

The backend needs `SUPABASE_URL` and `SUPABASE_ANON_KEY` or `SUPABASE_SERVICE_ROLE_KEY` to call `{SUPABASE_URL}/auth/v1/user`. R2 credentials only belong in backend environment variables. The frontend uses `VITE_API_BASE_URL` and Supabase public client keys only.
