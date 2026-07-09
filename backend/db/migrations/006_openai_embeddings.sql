create extension if not exists vector;

drop index if exists document_chunks_embedding_idx;
drop index if exists document_chunks_embedding_ollama_idx;
drop index if exists document_chunks_embedding_openai_idx;

alter table document_chunks
  add column if not exists embedding vector(1536),
  add column if not exists embedding_provider text,
  add column if not exists embedding_model text,
  add column if not exists embedding_dimensions integer;

alter table document_chunks
  alter column embedding type vector(1536)
  using case
    when embedding_dimensions = 1536 then embedding::vector(1536)
    else null
  end;

update document_chunks
set
  embedding_provider = 'openai',
  embedding_model = 'text-embedding-3-small',
  embedding_dimensions = 1536
where embedding is not null;

create index if not exists document_chunks_embedding_openai_idx
  on document_chunks
  using ivfflat ((embedding::vector(1536)) vector_cosine_ops)
  with (lists = 100)
  where embedding is not null
    and embedding_provider = 'openai'
    and embedding_model = 'text-embedding-3-small'
    and embedding_dimensions = 1536;
