-- ════════════════════════════════════════════════════════════════
-- v51 — Les réglages des machines sortent de programs.data
-- ════════════════════════════════════════════════════════════════
-- « Siège 4 · goupille 7 » (_reglages_machines, une entrée par machine) est
-- une donnée personnelle, pas le programme : elle rejoint l'état du compte
-- (v47, core/db_etat.py), colonne `reglages_machines` (audit du 18/10, m7).
--
-- ORDRE — deux temps, à ne pas inverser :
--   1. AVANT le déploiement du code : la colonne, vide. L'ancien code ne la
--      lit ni ne l'écrit (il nomme ses colonnes) : sans effet sur lui. Le
--      nouveau code, lui, prendrait une colonne absente pour une table
--      absente et repasserait tout l'état du compte sur le programme.
--   2. APRÈS le déploiement : les réglages existants rangés dans la colonne,
--      puis retirés du programme. Avant le déploiement, l'ancien code les
--      chercherait dans le programme et ne les trouverait plus.
-- Entre les deux, le nouveau code lit le programme tant que la colonne est
-- vide (NULL) et range les réglages à la première sauvegarde : rien ne se
-- perd, quel que soit le temps écoulé.
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

-- ── 1. AVANT le déploiement ─────────────────────────────────────
alter table public.etat_compte
  add column if not exists reglages_machines jsonb
  check (reglages_machines is null or jsonb_typeof(reglages_machines) = 'object');

comment on column public.etat_compte.reglages_machines is
  'Réglages des machines (v51), sortis de programs.data : clé machine → {texte, maj}.';

-- ── 2. APRÈS le déploiement ─────────────────────────────────────
-- Une colonne déjà remplie (le nouveau code a déjà rangé ce compte) n'est
-- pas écrasée par le reste du programme.
insert into public.etat_compte (user_id, reglages_machines)
select p.user_id, p.data->'_reglages_machines'
  from public.programs p
 where jsonb_typeof(p.data->'_reglages_machines') = 'object'
   and exists (select 1 from auth.users u where u.id = p.user_id)
on conflict (user_id) do update
   set reglages_machines = excluded.reglages_machines, updated_at = now()
 where public.etat_compte.reglages_machines is null;

-- La version monte : un onglet ouvert avant passe par la fusion (verrou
-- optimiste, v32) au lieu de réécrire la clé.
update public.programs
   set data = data - '_reglages_machines', version = version + 1
 where data ? '_reglages_machines'
   and exists (select 1 from public.etat_compte e
                where e.user_id = programs.user_id and e.reglages_machines is not null);

-- Vérification : 0 attendu.
-- select count(*) from public.programs where data ? '_reglages_machines';
