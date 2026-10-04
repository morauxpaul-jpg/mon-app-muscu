-- ════════════════════════════════════════════════════════════════
-- v40 — Un repas détaillé aliment par aliment
-- ════════════════════════════════════════════════════════════════
-- Chaque aliment du panier « Aliments » devient une ligne de `nutrition`
-- (audit du 03/10, nutrition). Deux colonnes facultatives :
--
--   grams  quantité mangée, en grammes — pour corriger « 150 g de riz »
--          après coup sans tout ressaisir ;
--   food   valeurs pour 100 g {n, k, p, c, f, brand?, code?, u?} — pour
--          recalculer les macros et proposer les aliments récents.
--
-- Les repas saisis en bloc (saisie rapide, plats de la semaine) les
-- laissent vides. Sans cette migration l'app écrit sans elles : le repas
-- est noté, seules la correction de quantité et les « récents » manquent.
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

alter table public.nutrition add column if not exists grams numeric(7, 1);
alter table public.nutrition add column if not exists food jsonb;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'nutrition_grams_check') then
    alter table public.nutrition
      add constraint nutrition_grams_check check (grams is null or (grams > 0 and grams <= 3000));
  end if;
end $$;

-- Les « récents » lisent les 60 derniers jours d'un utilisateur, du plus
-- récent au plus ancien : l'index (user_id, date) existant suffit.

-- PostgREST garde le schéma en cache : sans ce rechargement, les nouvelles
-- colonnes restent invisibles à l'API pendant quelques minutes.
notify pgrst, 'reload schema';
