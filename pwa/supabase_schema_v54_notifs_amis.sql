-- ════════════════════════════════════════════════════════════════
-- v54 — Réglage « Notifications des amis »
-- ════════════════════════════════════════════════════════════════
-- Choix du propriétaire (03/11/2026) : prévenir par notification push d'une
-- demande d'ami reçue, d'une invitation à un défi, d'un ami qui vous dépasse
-- dans un défi en cours et d'un encouragement reçu. Actives par défaut pour
-- qui a déjà accepté les notifications ; un interrupteur dans Réglages les
-- coupe (core/push_amis.py).
--
-- Une colonne de plus dans `reglages` (v45), vraie par défaut, comme le récap
-- du dimanche. Pas de ligne = valeurs par défaut : rien à recopier.
--
-- Sans cette colonne, l'app marche comme avant : les réglages se lisent et
-- s'écrivent sans elle (core/db_reglages.py), les notifications des amis
-- partent selon la valeur par défaut, et /admin signale la colonne manquante.
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

alter table public.reglages
  add column if not exists notifs_amis boolean not null default true;

comment on column public.reglages.notifs_amis is
  'Notifications des amis (v54) : demande reçue, invitation à un défi, dépassé dans un défi, encouragement.';

-- PostgREST garde le schéma en cache : sans ce rechargement, la colonne reste
-- invisible à l'API pendant quelques minutes.
notify pgrst, 'reload schema';

-- Vérification :
-- select column_name, data_type, is_nullable, column_default from information_schema.columns
--  where table_name = 'reglages' and column_name = 'notifs_amis';
