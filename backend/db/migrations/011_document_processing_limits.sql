begin;

-- Stores counters only, never tokens, IP addresses, filenames or document text.
-- Deleting an account also removes its quota counter.
create table if not exists public.document_processing_limits (
  user_id uuid primary key references auth.users(id) on delete cascade,
  request_count integer not null check (request_count >= 1),
  expires_at timestamptz not null
);

alter table public.document_processing_limits enable row level security;
revoke all privileges on table public.document_processing_limits from anon, authenticated, public;

commit;
