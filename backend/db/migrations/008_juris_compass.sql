create extension if not exists "pgcrypto";

create table if not exists juris_compass_conversations (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null,
  title text not null default 'New legal research',
  jurisdiction text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists juris_compass_messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null references juris_compass_conversations(id) on delete cascade,
  user_id uuid not null,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  response_json jsonb,
  created_at timestamptz not null default now()
);

create index if not exists juris_compass_conversations_user_updated_idx
  on juris_compass_conversations (user_id, updated_at desc);

create index if not exists juris_compass_messages_conversation_created_idx
  on juris_compass_messages (conversation_id, created_at asc);

create index if not exists juris_compass_messages_user_idx
  on juris_compass_messages (user_id);
