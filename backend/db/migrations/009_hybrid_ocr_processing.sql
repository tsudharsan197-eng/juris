alter table documents
  add column if not exists processing_error text,
  add column if not exists low_confidence_pages integer[] not null default '{}'::integer[],
  add column if not exists extraction_metadata jsonb not null default '{}'::jsonb,
  add column if not exists updated_at timestamptz not null default now();

update documents
set updated_at = created_at
where updated_at is null;

alter table document_text
  add column if not exists page_metadata jsonb not null default '[]'::jsonb;

alter table document_chunks
  add column if not exists page_start integer,
  add column if not exists page_end integer,
  add column if not exists extraction_method text,
  add column if not exists ocr_confidence real;

create index if not exists document_chunks_document_page_idx
  on document_chunks (document_id, page_start, chunk_index);
