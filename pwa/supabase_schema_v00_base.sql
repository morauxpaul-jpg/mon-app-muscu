-- Migration v00 — socle d'origine, reconstitué le 10/10/2026.
--
-- Les cinq premières tables (profiles, programs, history, onboarding,
-- coach_messages) et la création automatique du profil à l'inscription
-- avaient été faites à la main dans Supabase, avant la v23 : aucun fichier
-- du dépôt ne les créait, donc rien ne permettait de reconstruire une base
-- vide (CI, reprise après sinistre) ni de rejouer les migrations.
--
-- Reconstitué depuis la production (information_schema, pg_constraint,
-- pg_indexes, pg_get_functiondef) : chaque colonne ajoutée ENSUITE par une
-- migration v23 → v48 en a été retirée, pour que l'enchaînement
-- v00, v23, …, v48 redonne la base de production.
--
-- Idempotente (IF NOT EXISTS, OR REPLACE). Inutile en production : tout y
-- est déjà. Rejouée à chaque CI sur un PostgreSQL vide
-- (tests/test_migrations_postgres.py).

create table if not exists public.profiles (
  id              uuid primary key references auth.users(id) on delete cascade,
  created_at      timestamptz not null default now(),
  display_name    text,
  niveau          text,
  objectif        text,
  frequence       integer,
  equipement      text[],
  morphologie     text,
  onboarding_done boolean not null default false,
  prenom          text
);

create table if not exists public.programs (
  user_id    uuid primary key references auth.users(id) on delete cascade,
  data       jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.history (
  id         bigserial primary key,
  user_id    uuid not null references auth.users(id) on delete cascade,
  semaine    integer not null,
  seance     text not null,
  exercice   text not null,
  serie      integer not null,
  reps       integer not null default 0,
  poids      double precision not null default 0,
  remarque   text default ''::text,
  muscle     text default ''::text,
  date       date,
  created_at timestamptz not null default now()
);
create index if not exists history_user_idx on public.history (user_id);
create index if not exists history_user_seance_semaine_idx on public.history (user_id, seance, semaine);

create table if not exists public.onboarding (
  user_id      uuid primary key references auth.users(id) on delete cascade,
  prenom       text,
  age          integer,
  sexe         text,
  niveau       text,
  frequence    integer,
  objectif     text,
  equipement   text,
  completed_at timestamptz default now()
);

create table if not exists public.coach_messages (
  id         bigserial primary key,
  user_id    uuid references auth.users(id) on delete cascade,
  role       text not null check (role = any (array['user'::text, 'assistant'::text])),
  content    text not null,
  created_at timestamptz default now()
);
create index if not exists idx_coach_user on public.coach_messages (user_id, created_at);

alter table public.profiles enable row level security;
alter table public.programs enable row level security;
alter table public.history enable row level security;
alter table public.onboarding enable row level security;
alter table public.coach_messages enable row level security;

-- Un compte neuf reçoit son profil et un programme vide. Le droit d'appeler
-- la fonction directement est retiré par la v48.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path to 'public'
as $function$
  begin
    insert into public.profiles (id, display_name)
    values (new.id, coalesce(new.raw_user_meta_data->>'full_name', new.email))
    on conflict (id) do nothing;
    insert into public.programs (user_id, data)
    values (new.id, '{}'::jsonb)
    on conflict (user_id) do nothing;
    return new;
  end $function$;

create or replace trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
