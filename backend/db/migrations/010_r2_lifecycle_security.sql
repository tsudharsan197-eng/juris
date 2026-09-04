begin;

create extension if not exists "pgcrypto";

create table if not exists public.r2_deletion_jobs (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null,
  user_id uuid not null,
  file_key text not null unique,
  reason text not null check (
    reason in ('user_delete', 'upload_rollback', 'reconciliation')
  ),
  status text not null default 'pending' check (
    status in ('pending', 'processing', 'failed', 'completed')
  ),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  next_attempt_at timestamptz not null default now(),
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create index if not exists r2_deletion_jobs_due_idx
  on public.r2_deletion_jobs (next_attempt_at, created_at)
  where status in ('pending', 'failed');

create index if not exists r2_deletion_jobs_user_created_idx
  on public.r2_deletion_jobs (user_id, created_at desc);

-- These tables are accessed by the trusted FastAPI database role, not by the
-- browser-facing Supabase Data API. RLS and revoked grants provide two layers
-- of protection if the schema is restored into a new project.
do $security$
declare
  table_name text;
begin
  foreach table_name in array array[
    'documents',
    'document_text',
    'document_chunks',
    'ai_outputs',
    'juris_compass_conversations',
    'juris_compass_messages',
    'r2_deletion_jobs',
    'profiles',
    'chat_history',
    'clauses',
    'risks',
    'summaries'
  ]
  loop
    if to_regclass(format('public.%I', table_name)) is not null then
      execute format('alter table public.%I enable row level security', table_name);
      execute format(
        'revoke all privileges on table public.%I from anon, authenticated, public',
        table_name
      );
    end if;
  end loop;
end
$security$;

-- Explicit ownership policies keep documents secure if direct client access is
-- deliberately granted in the future. Current browser clients have no table
-- grants, so all document data continues to flow through FastAPI ownership checks.
drop policy if exists documents_owner_select on public.documents;
drop policy if exists documents_owner_insert on public.documents;
drop policy if exists documents_owner_update on public.documents;
drop policy if exists documents_owner_delete on public.documents;
drop policy if exists documents_owner_guard on public.documents;

-- Restrictive policies are ANDed with legacy permissive policies. A restored
-- permissive policy must not bypass the owner check if grants change later.
create policy documents_owner_guard
  on public.documents as restrictive
  for all
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy documents_owner_select
  on public.documents
  for select
  to authenticated
  using ((select auth.uid()) = user_id);

create policy documents_owner_insert
  on public.documents
  for insert
  to authenticated
  with check ((select auth.uid()) = user_id);

create policy documents_owner_update
  on public.documents
  for update
  to authenticated
  using ((select auth.uid()) = user_id)
  with check ((select auth.uid()) = user_id);

create policy documents_owner_delete
  on public.documents
  for delete
  to authenticated
  using ((select auth.uid()) = user_id);

-- Supabase commonly grants new public-schema objects to API roles by default.
-- Keep future tables and sequences private unless a later migration opts in.
alter default privileges for role postgres
  revoke all privileges on tables from anon, authenticated, public;

alter default privileges for role postgres
  revoke all privileges on sequences from anon, authenticated, public;

alter default privileges for role postgres in schema public
  revoke all privileges on tables from anon, authenticated, public;

alter default privileges for role postgres in schema public
  revoke all privileges on sequences from anon, authenticated, public;

commit;
