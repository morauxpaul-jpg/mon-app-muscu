-- ============================================================
-- Migration v36 — mémoire du coach
--
-- À exécuter dans Supabase → SQL Editor. Idempotente.
--
-- Sans mémoire, chaque conversation repartait de zéro : il fallait redire à
-- chaque fois qu'on a mal à l'épaule droite, qu'on s'entraîne le matin, ou
-- qu'on ne supporte pas le squat barre.
--
-- La note est courte (700 caractères max), mise à jour par le coach lui-même
-- après quelques échanges, et injectée dans toutes les conversations
-- suivantes. Sans cette colonne l'app fonctionne : la mémoire est simplement
-- vide et l'écriture échoue en silence (loggée en warning).
-- ============================================================

alter table public.profiles
  add column if not exists coach_memory text;

comment on column public.profiles.coach_memory is
  'Note du coach sur l''utilisateur (blessures, contraintes, préférences), '
  'régénérée après quelques échanges. 700 caractères max côté applicatif.';
