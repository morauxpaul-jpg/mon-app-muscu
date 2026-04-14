-- ═════════════════════════════════════════════════════════════════════
-- Muscu PRO — Migration v24 (Coach IA + Tier system)
-- À exécuter dans SQL Editor de Supabase. Idempotent (IF NOT EXISTS).
-- ═════════════════════════════════════════════════════════════════════

-- 1) Tier — free / vip (paywall préparé, non activé)
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS tier text NOT NULL DEFAULT 'free';

-- 2) Compteur de messages Coach IA (rate limit 20/jour côté serveur)
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS coach_quota_date  date,
  ADD COLUMN IF NOT EXISTS coach_quota_count integer NOT NULL DEFAULT 0;
