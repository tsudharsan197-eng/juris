create extension if not exists "pgcrypto";

create table if not exists documents (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  title text not null,
  file_name text not null,
  file_key text not null unique,
  file_size bigint not null,
  mime_type text not null,
  storage_provider text not null default 'cloudflare_r2',
  status text not null default 'uploaded',
  created_at timestamptz not null default now()
);

create index if not exists documents_user_created_idx
  on documents (user_id, created_at desc);

alter table documents
  add column if not exists file_key text,
  add column if not exists storage_provider text default 'cloudflare_r2',
  add column if not exists mime_type text,
  add column if not exists file_size bigint,
  add column if not exists status text default 'uploaded';
