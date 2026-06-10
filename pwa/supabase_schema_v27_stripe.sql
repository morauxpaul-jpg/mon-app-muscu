-- Migration v27 — Stripe (abonnements Premium)
-- À exécuter dans Supabase → SQL Editor → New query → Run.
--
-- Ajoute la colonne qui mémorise l'identifiant client Stripe sur le profil.
-- Sert au portail client (gérer/annuler) et au mapping customer→user lors des
-- webhooks d'annulation. Idempotent : ré-exécutable sans risque.

alter table public.profiles
  add column if not exists stripe_customer_id text;

-- Recherche rapide par customer Stripe (webhook annulation).
create index if not exists profiles_stripe_customer_idx
  on public.profiles (stripe_customer_id);
