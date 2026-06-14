-- Migration v29 — Parrainage + VIP à durée limitée
-- À exécuter dans Supabase → SQL Editor → New query → Run.
--
-- Ajoute au profil :
--   referral_code : code de parrainage unique de l'utilisateur (lien d'invit).
--   referred_by   : id du parrain (posé UNE fois à l'onboarding du filleul).
--   vip_until     : VIP à durée limitée (parrainage, promo, geste co). Le statut
--                   VIP effectif = (tier = 'vip') OU (vip_until > now()).
-- Idempotent : ré-exécutable sans risque.

alter table public.profiles
  add column if not exists referral_code text,
  add column if not exists referred_by   text,
  add column if not exists vip_until      timestamptz;

-- Unicité + recherche rapide d'un parrain par code (résolution du lien ?ref=).
create unique index if not exists profiles_referral_code_key
  on public.profiles (referral_code)
  where referral_code is not null;

-- Comptage des filleuls d'un parrain.
create index if not exists profiles_referred_by_idx
  on public.profiles (referred_by);
