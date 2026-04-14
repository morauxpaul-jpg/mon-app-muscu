-- ═════════════════════════════════════════════════════════════════════
-- Muscu PRO — Migration v23 (Cardio + Nutrition)
-- À exécuter dans SQL Editor de Supabase. Idempotent (IF NOT EXISTS).
-- ═════════════════════════════════════════════════════════════════════

-- 1) Profil — colonnes nutritionnelles
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS poids_kg          numeric,
  ADD COLUMN IF NOT EXISTS taille_cm         numeric,
  ADD COLUMN IF NOT EXISTS age               integer,
  ADD COLUMN IF NOT EXISTS sexe              text,         -- 'H' ou 'F'
  ADD COLUMN IF NOT EXISTS activite          text,         -- sedentaire|leger|actif|tres_actif|athlete
  ADD COLUMN IF NOT EXISTS objectif_nutrition text,        -- masse|maintien|seche
  ADD COLUMN IF NOT EXISTS tdee              integer,      -- kcal/jour calculé
  ADD COLUMN IF NOT EXISTS calories_cible    integer;      -- objectif kcal selon objectif

-- 2) Table nutrition — un repas logué par ligne
CREATE TABLE IF NOT EXISTS public.nutrition (
  id         bigserial PRIMARY KEY,
  user_id    uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  date       date NOT NULL,
  meal_type  text NOT NULL CHECK (meal_type IN ('petit_dej','dejeuner','diner','collation')),
  calories   integer NOT NULL DEFAULT 0 CHECK (calories >= 0),
  protein    integer NOT NULL DEFAULT 0 CHECK (protein  >= 0),
  carbs      integer NOT NULL DEFAULT 0 CHECK (carbs    >= 0),
  fat        integer NOT NULL DEFAULT 0 CHECK (fat      >= 0),
  note       text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS nutrition_user_date_idx
  ON public.nutrition (user_id, date);

-- 3) RLS — chaque user ne voit et ne modifie que ses propres lignes.
--    Le backend Flask utilise `service_role` (bypass RLS) et filtre par
--    user_id explicitement, mais on active RLS par défense en profondeur.
ALTER TABLE public.nutrition ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "nutrition_select_own" ON public.nutrition;
CREATE POLICY "nutrition_select_own" ON public.nutrition
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "nutrition_insert_own" ON public.nutrition;
CREATE POLICY "nutrition_insert_own" ON public.nutrition
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "nutrition_update_own" ON public.nutrition;
CREATE POLICY "nutrition_update_own" ON public.nutrition
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "nutrition_delete_own" ON public.nutrition;
CREATE POLICY "nutrition_delete_own" ON public.nutrition
  FOR DELETE USING (auth.uid() = user_id);

-- ═════════════════════════════════════════════════════════════════════
-- Pas de nouvelle table pour le cardio : les séances cardio sont
-- stockées dans la table `history` existante avec la convention :
--   exercice = 'CARDIO:Type'  (ex. 'CARDIO:Course')
--   reps     = durée en minutes (integer)
--   poids    = distance en km (numeric, 0 si non applicable)
--   remarque = 'FC:145 | Cal:350 | RPE:Modéré'
--   muscle   = 'Cardio'
-- ═════════════════════════════════════════════════════════════════════
