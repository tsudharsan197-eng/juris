create extension if not exists vector;

drop index if exists document_chunks_embedding_idx;
drop index if exists document_chunks_embedding_ollama_idx;

alter table document_chunks
  add column if not exists embedding vector(768),
  add column if not exists embedding_provider text,
  add column if not exists embedding_model text,
  add column if not exists embedding_dimensions integer;

alter table document_chunks
  alter column embedding type vector(768)
  using case
    when embedding_dimensions = 768 then embedding::vector(768)
    else null
  end;

update document_chunks
set
  embedding_provider = 'ollama',
  embedding_model = 'nomic-embed-text',
  embedding_dimensions = 768
where embedding is not null;

create index if not exists document_chunks_embedding_ollama_idx
  on document_chunks
  using ivfflat ((embedding::vector(768)) vector_cosine_ops)
  with (lists = 100)
  where embedding is not null
    and embedding_provider = 'ollama'
    and embedding_model = 'nomic-embed-text'
    and embedding_dimensions = 768;
