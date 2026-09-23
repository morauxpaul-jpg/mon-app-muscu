-- ============================================================
-- Migration v35 — durée de séance
--
-- À exécuter dans Supabase → SQL Editor. Idempotente.
-- Sans elle, l'app fonctionne : la durée est simplement ignorée à
-- l'enregistrement (l'upsert ne pose la colonne que si une durée existe,
-- et PostgREST refuserait la ligne entière — d'où cette migration courte
-- livrée séparément de la v34).
--
-- La durée est mesurée côté client entre la première saisie et « Terminer »,
-- bornée à 8 h, et sert à : afficher « 47 min » dans le bilan, calculer la
-- densité (kg/min) dans les stats, et alimenter le debrief IA.
-- ============================================================

alter table public.session_notes
  add column if not exists duration_min smallint
    check (duration_min is null or (duration_min >= 0 and duration_min <= 480));

comment on column public.session_notes.duration_min is
  'Durée de la séance en minutes (première série → « Terminer »), 0..480.';
