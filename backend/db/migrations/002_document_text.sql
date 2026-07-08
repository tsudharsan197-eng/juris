create table if not exists document_text (
  document_id uuid primary key references documents(id) on delete cascade,
  user_id uuid not null,
  text_content text not null,
  page_count integer not null,
  language text not null default 'en',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists document_text_user_idx
  on document_text (user_id);
