-- ════════════════════════════════════════════════════════════════
-- v42 — Identifiant stable d'exercice sur l'historique
-- ════════════════════════════════════════════════════════════════
-- L'historique retrouvait un exercice par son NOM : renommer « Curl » en
-- « Curl marteau » coupait le passé, à moins de réécrire toutes ses séries
-- (audit du 03/10, modèle de données). Chaque exercice du programme porte
-- désormais un identifiant (`e_` + 8 caractères, core/exercice_ids.py) qui
-- survit aux renommages ; une série enregistrée le porte aussi, suivi de sa
-- variante : `e_1a2b3c4d` ou `e_1a2b3c4d~Haltères`.
--
-- Colonne facultative : les lignes plus anciennes restent sans identifiant et
-- se lisent par leur nom, comme avant. Rien n'est réécrit par cette migration.
-- Sans elle, l'app lit et écrit comme avant (repli automatique).
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

alter table public.history add column if not exists exercise_id text;

comment on column public.history.exercise_id is
  'Identifiant stable de l''exercice du programme (core/exercice_ids.py), suivi de ~variante. NULL : ligne antérieure à la v42, lue par son nom.';

-- Écrire une série cible aussi les lignes de l'exercice par identifiant (une
-- série faite avant un renommage porte l'ancien nom), toujours sur un compte,
-- une date et une séance : l'index existant (user_id, date…) suffit à ces
-- lectures. Celui-ci sert au rattachement et aux lectures par exercice.
create index if not exists history_user_exercise_id_idx
  on public.history (user_id, exercise_id)
  where exercise_id is not null;
