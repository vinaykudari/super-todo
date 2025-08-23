-- Enable helpful extension for updated_at
create extension if not exists moddatetime schema extensions;

-- Enum for item state
do $$
begin
  if not exists (select 1 from pg_type where typname = 'item_state') then
    create type item_state as enum ('pending', 'processing', 'completed');
  end if;
end$$;

-- Items table
create table if not exists public.items (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  description text,
  state item_state not null default 'pending',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Keep updated_at fresh
drop trigger if exists handle_updated_at on public.items;
create trigger handle_updated_at
before update on public.items
for each row execute procedure extensions.moddatetime (updated_at);

-- Attachments table
create table if not exists public.attachments (
  id uuid primary key default gen_random_uuid(),
  item_id uuid not null references public.items(id) on delete cascade,
  name text not null,
  path text not null,           -- storage path inside the bucket
  url text not null,            -- public or signed URL
  mime_type text,
  size_bytes integer,
  created_at timestamptz not null default now()
);

create index if not exists idx_attachments_item_id on public.attachments(item_id);

-- RLS is ON by default in Supabase; using SERVICE ROLE key bypasses policies.
-- If you later want to use anon key from a frontend, add granular RLS policies.