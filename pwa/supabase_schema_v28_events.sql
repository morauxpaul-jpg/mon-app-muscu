-- Migration v28 — Analytics produit (events de conversion / funnel)
-- À exécuter dans Supabase → SQL Editor → New query → Run.
--
-- Table d'events auto-hébergée : alimente le funnel de conversion de la console
-- admin (/admin/funnel). Pas de tiers (PostHog/Mixpanel) → pas de bannière de
-- consentement, données chez nous. Écrite côté serveur en service_role.
-- Idempotent : ré-exécutable sans risque.

create table if not exists public.events (
  id         bigint generated always as identity primary key,
  user_id    uuid,                         -- nullable (events anonymes éventuels)
  event      text not null,                -- ex: onboarding_completed, workout_finished…
  props      jsonb not null default '{}'::jsonb,
  tier       text,                         -- 'free' / 'vip' au moment de l'event
  created_at timestamptz not null default now()
);

-- Filtrage par type d'event + fenêtre temporelle (requêtes du funnel).
create index if not exists events_event_idx   on public.events (event);
create index if not exists events_created_idx  on public.events (created_at);
create index if not exists events_user_idx     on public.events (user_id);

-- Accès réservé au backend (service_role). RLS activé sans policy = aucun
-- accès via la clé anon (le client ne lit/écrit jamais cette table directement).
alter table public.events enable row level security;
