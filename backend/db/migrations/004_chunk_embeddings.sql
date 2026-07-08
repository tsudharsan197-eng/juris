create extension if not exists vector;

drop index if exists document_chunks_embedding_idx;

alter table document_chunks
  add column if not exists embedding vector(768);

do $$
begin
  if exists (
    select 1
    from pg_attribute
    where attrelid = 'document_chunks'::regclass
      and attname = 'embedding'
      and not attisdropped
      and format_type(atttypid, atttypmod) <> 'vector(768)'
  ) then
    alter table document_chunks
      alter column embedding type vector(768)
      using null;
  end if;
end $$;

create index if not exists document_chunks_embedding_idx
  on document_chunks
  using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);
