-- ============================================================================
-- Muscu PRO — Migration v25 : système Free / VIP
-- ============================================================================
-- Objectif : formaliser le tier VIP (PRO) sur la table `profiles`.
--
-- Contexte : la colonne `tier` existait déjà (text, valeurs 'free' / 'vip').
-- Cette migration garantit qu'elle est bien présente, indexée et par défaut
-- à 'free' pour tout nouveau profil.
--
-- Fonctionnalités gatées côté application (voir README / code) :
--   * Coach IA            → /coach                (VIP requis)
--   * Export programme    → /programme/export     (VIP requis)
--   * Import programme    → /programme/import     (VIP requis)
--   * Stats avancées      → Hall of Fame, 1RM, body map (VIP requis)
--   * Programmes          → 2 max en Free, illimité en VIP
--
-- Idempotent : peut être rejoué sans risque.
-- ============================================================================

-- 1) Colonne tier (garde-fou, déjà existante normalement)
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS tier text NOT NULL DEFAULT 'free';

-- 2) Contrainte de valeur : uniquement 'free' ou 'vip'
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'profiles_tier_check'
    ) THEN
        ALTER TABLE public.profiles
            ADD CONSTRAINT profiles_tier_check
            CHECK (tier IN ('free', 'vip'));
    END IF;
END $$;

-- 3) Index pour filtrer les VIP rapidement (admin, stats)
CREATE INDEX IF NOT EXISTS profiles_tier_idx
    ON public.profiles (tier)
    WHERE tier = 'vip';

-- 4) Normalisation : tout tier NULL / vide → 'free'
UPDATE public.profiles
   SET tier = 'free'
 WHERE tier IS NULL OR btrim(tier) = '';

-- 5) Normalisation : minuscules
UPDATE public.profiles
   SET tier = lower(btrim(tier))
 WHERE tier <> lower(btrim(tier));

-- ============================================================================
-- Fin migration v25
-- ============================================================================
