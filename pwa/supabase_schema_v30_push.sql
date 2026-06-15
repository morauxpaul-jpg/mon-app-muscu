-- Migration v30 — Push web (relance des inactifs)
-- À exécuter dans Supabase → SQL Editor → New query → Run.
--
-- Stocke les abonnements push (un par appareil/navigateur). Le backend envoie
-- les notifications via pywebpush + clés VAPID (env Railway).
-- Idempotent : ré-exécutable sans risque.

create table if not exists public.push_subscriptions (
  id         bigint generated always as identity primary key,
  user_id    uuid not null,
  endpoint   text not null unique,        -- identifiant unique de l'abonnement
  p256dh     text not null,               -- clé publique du client (chiffrement)
  auth       text not null,               -- secret d'auth du client
  created_at timestamptz not null default now()
);

create index if not exists push_subscriptions_user_idx
  on public.push_subscriptions (user_id);

-- Backend uniquement (service_role). RLS sans policy = pas d'accès via anon.
alter table public.push_subscriptions enable row level security;
