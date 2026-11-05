-- Miora evidence library
-- Run once in Supabase SQL Editor. Resources are shared reference material;
-- only authenticated users can read them. Writes are restricted to service-role/admin workflows.
create extension if not exists pgcrypto;

create table if not exists public.knowledge_resources (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  source_name text not null,
  source_url text not null,
  resource_type text not null default 'guideline',
  topic_tags text[] not null default '{}',
  content text not null,
  reviewed_at timestamptz,
  review_status text not null default 'pending'
    check (review_status in ('pending', 'approved', 'rejected')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

alter table public.knowledge_resources enable row level security;

drop policy if exists "Authenticated users read approved knowledge" on public.knowledge_resources;
create policy "Authenticated users read approved knowledge"
  on public.knowledge_resources for select
  to authenticated
  using (review_status = 'approved');

-- No client insert/update/delete policies: content ingestion and review must
-- happen through a trusted admin process, never from an ordinary app account.

create index if not exists knowledge_resources_review_status_idx
  on public.knowledge_resources (review_status);
create index if not exists knowledge_resources_topic_tags_idx
  on public.knowledge_resources using gin (topic_tags);
