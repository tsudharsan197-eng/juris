create table if not exists document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  user_id uuid not null,
  chunk_index integer not null,
  chunk_text text not null,
  created_at timestamptz not null default now()
);

create index if not exists document_chunks_document_idx
  on document_chunks (document_id);

create index if not exists document_chunks_user_idx
  on document_chunks (user_id);

create unique index if not exists document_chunks_document_chunk_idx
  on document_chunks (document_id, chunk_index);
