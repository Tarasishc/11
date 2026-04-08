-- ENUMS
do $$ begin
  create type counterparty_type as enum ('buyer', 'supplier');
exception when duplicate_object then null; end $$;

do $$ begin
  create type document_type as enum ('invoice', 'waybill', 'contract');
exception when duplicate_object then null; end $$;

-- PROFILES
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text,
  ipn text,
  address text,
  bank_name text,
  bank_account text,
  bank_mfo text,
  webhook_url text,
  terms_accepted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- COUNTERPARTIES
create table if not exists public.counterparties (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  type counterparty_type not null,
  name text not null,
  tax_id text,
  address text,
  bank_name text,
  bank_account text,
  bank_mfo text,
  created_at timestamptz not null default now()
);
create index if not exists counterparties_user_id_idx on public.counterparties(user_id);

-- DOCUMENTS HISTORY
create table if not exists public.documents_history (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  counterparty_id uuid references public.counterparties(id) on delete set null,
  counterparty_name text not null, -- денормалізовано: щоб історія лишалася читабельною після видалення контрагента
  document_type document_type not null,
  total_amount numeric(14,2) not null default 0,
  google_doc_url text not null,
  created_at timestamptz not null default now()
);
create index if not exists documents_history_user_id_idx on public.documents_history(user_id);
create index if not exists documents_history_created_at_idx on public.documents_history(created_at desc);

-- TRIGGER: створити порожній profile при реєстрації
create or replace function public.handle_new_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id) values (new.id) on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- TRIGGER: updated_at для profiles
create or replace function public.handle_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_updated_at on public.profiles;
create trigger profiles_updated_at
  before update on public.profiles
  for each row execute function public.handle_updated_at();

-- RLS
alter table public.profiles enable row level security;
alter table public.counterparties enable row level security;
alter table public.documents_history enable row level security;

-- profiles policies
create policy "profiles_select_own" on public.profiles for select using (auth.uid() = id);
create policy "profiles_insert_own" on public.profiles for insert with check (auth.uid() = id);
create policy "profiles_update_own" on public.profiles for update using (auth.uid() = id) with check (auth.uid() = id);

-- counterparties policies
create policy "counterparties_select_own" on public.counterparties for select using (auth.uid() = user_id);
create policy "counterparties_insert_own" on public.counterparties for insert with check (auth.uid() = user_id);
create policy "counterparties_update_own" on public.counterparties for update using (auth.uid() = user_id) with check (auth.uid() = user_id);
create policy "counterparties_delete_own" on public.counterparties for delete using (auth.uid() = user_id);

-- documents_history policies (тільки select + insert)
create policy "documents_history_select_own" on public.documents_history for select using (auth.uid() = user_id);
create policy "documents_history_insert_own" on public.documents_history for insert with check (auth.uid() = user_id);
