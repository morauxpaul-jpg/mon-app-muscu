-- v33 — Suivi du poids corporel dans le temps.
--
-- Une pesée par jour et par user (upsert sur (user_id, date)). La dernière
-- pesée est recopiée dans profiles.poids_kg pour que le TDEE de la
-- nutrition et le badge « Costaud » suivent le poids réel au lieu de celui
-- saisi à l'onboarding.

CREATE TABLE IF NOT EXISTS public.body_weight (
  id         bigserial PRIMARY KEY,
  user_id    uuid NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  date       date NOT NULL,
  poids_kg   numeric(5,1) NOT NULL CHECK (poids_kg > 0 AND poids_kg < 500),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, date)
);

CREATE INDEX IF NOT EXISTS body_weight_user_date_idx
  ON public.body_weight (user_id, date);

ALTER TABLE public.body_weight ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "body_weight_select_own" ON public.body_weight;
CREATE POLICY "body_weight_select_own" ON public.body_weight
  FOR SELECT USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "body_weight_insert_own" ON public.body_weight;
CREATE POLICY "body_weight_insert_own" ON public.body_weight
  FOR INSERT WITH CHECK (auth.uid() = user_id);

DROP POLICY IF EXISTS "body_weight_update_own" ON public.body_weight;
CREATE POLICY "body_weight_update_own" ON public.body_weight
  FOR UPDATE USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "body_weight_delete_own" ON public.body_weight;
CREATE POLICY "body_weight_delete_own" ON public.body_weight
  FOR DELETE USING (auth.uid() = user_id);
