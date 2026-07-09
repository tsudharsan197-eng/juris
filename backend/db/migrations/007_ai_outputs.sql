create table if not exists ai_outputs (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references documents(id) on delete cascade,
  user_id uuid not null,
  feature text not null,
  input_hash text not null,
  output_json jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'ai_outputs_document_feature_hash_key'
  ) then
    alter table ai_outputs
      add constraint ai_outputs_document_feature_hash_key
      unique (document_id, feature, input_hash);
  end if;
end $$;

create index if not exists ai_outputs_user_feature_idx
  on ai_outputs (user_id, feature, updated_at desc);

create index if not exists ai_outputs_document_idx
  on ai_outputs (document_id);
