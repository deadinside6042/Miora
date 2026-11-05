-- Miora persistent profile and memory
-- Run once in the Supabase SQL Editor.

create table if not exists public.user_profiles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  preferred_name text,
  memory_summary text not null default '',
  updated_at timestamptz not null default now(),
  constraint user_profiles_preferred_name_length check (char_length(coalesce(preferred_name, '')) <= 80),
  constraint user_profiles_memory_length check (char_length(memory_summary) <= 6000)
);

alter table public.user_profiles enable row level security;

drop policy if exists "Users can read their own Miora profile" on public.user_profiles;
create policy "Users can read their own Miora profile"
on public.user_profiles for select to authenticated
using (auth.uid() = user_id);

drop policy if exists "Users can insert their own Miora profile" on public.user_profiles;
create policy "Users can insert their own Miora profile"
on public.user_profiles for insert to authenticated
with check (auth.uid() = user_id);

drop policy if exists "Users can update their own Miora profile" on public.user_profiles;
create policy "Users can update their own Miora profile"
on public.user_profiles for update to authenticated
using (auth.uid() = user_id)
with check (auth.uid() = user_id);

create index if not exists messages_user_conversation_created_idx
on public.messages (user_id, conversation_id, created_at);
