-- ════════════════════════════════════════════════════════════════
-- v44 — Le cardio dans ses propres colonnes
-- ════════════════════════════════════════════════════════════════
-- Une ligne cardio (exercice « CARDIO:Course ») rangeait sa durée dans
-- `reps`, sa distance dans `poids`, et ses calories et sa vitesse en texte
-- dans la remarque (« Cal:360 | Vit:10.5 | RPE:Modéré »). Tout ce qui lit la
-- base directement se trompait : le tonnage de la console admin multipliait
-- des minutes par des kilomètres (audit du 03/10, M15), et aucune requête ne
-- pouvait additionner des calories écrites en texte.
--
-- Après cette migration :
--   duree_min  minutes          distance  km, sauts, rounds… (unité de l'activité)
--   calories   kcal             vitesse   km/h, m/min… (unité de l'activité)
-- et reps = poids = 0 sur toute ligne cardio, ce que la base fait respecter.
-- L'app (core/seance_cardio.py) écrit et lit ce format.
--
-- ORDRE : déployer le code d'abord (il sait écrire sans ces colonnes), puis
-- exécuter ce fichier, puis redémarrer le service web : un processus qui a
-- vu les colonnes absentes continue sans elles jusqu'au redémarrage.
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

-- 1. Les colonnes. NULL sur toute ligne de musculation.
alter table public.history
  add column if not exists duree_min numeric,
  add column if not exists distance  numeric,
  add column if not exists calories  integer,
  add column if not exists vitesse   numeric;

-- 2. Les lignes cardio existantes passent au nouveau format. Calories et
--    vitesse ne quittent la remarque que si ce sont des nombres (une allure
--    « 2:05 » reste en texte).
update public.history h set
  duree_min = h.reps,
  distance = h.poids,
  calories = round(replace(substring(h.remarque from
      '(?i)(?:^|\|)\s*cal:\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:\||$)'), ',', '.')::numeric)::integer,
  vitesse = replace(substring(h.remarque from
      '(?i)(?:^|\|)\s*vit:\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:\||$)'), ',', '.')::numeric,
  remarque = array_to_string(array(
      select trim(u.t)
        from unnest(string_to_array(coalesce(h.remarque, ''), '|')) with ordinality as u(t, i)
       where trim(u.t) <> ''
         and trim(u.t) !~* '^(cal|vit):\s*[0-9]+([.,][0-9]+)?$'
       order by u.i), ' | '),
  reps = 0,
  poids = 0
where h.exercice like 'CARDIO:%'
  and h.duree_min is null;

-- 3. Plus de retour possible à l'ancien format.
do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'history_cardio_colonnes_check') then
    alter table public.history add constraint history_cardio_colonnes_check check (
      case when exercice like 'CARDIO:%'
           then reps = 0 and poids = 0
                and coalesce(duree_min, 0) >= 0 and coalesce(distance, 0) >= 0
                and coalesce(calories, 0) >= 0 and coalesce(vitesse, 0) >= 0
           else duree_min is null and distance is null
                and calories is null and vitesse is null
      end);
  end if;
end $$;

comment on column public.history.duree_min is 'Cardio : durée en minutes (NULL hors cardio).';
comment on column public.history.distance  is 'Cardio : distance dans l''unité de l''activité (NULL hors cardio).';
comment on column public.history.calories  is 'Cardio : kcal (NULL hors cardio).';
comment on column public.history.vitesse   is 'Cardio : vitesse dans l''unité de l''activité (NULL hors cardio).';

-- 4. Dernière séance par compte (cron de relance) : une journée de cardio
--    seul a désormais reps = poids = 0, et ne doit pas disparaître.
create or replace view public.user_last_activity
  with (security_invoker = true) as
select user_id, max(date) as last_date
  from public.history
 where (reps > 0 or poids > 0 or coalesce(duree_min, 0) > 0 or coalesce(distance, 0) > 0)
   and exercice <> 'SESSION'
 group by user_id;

revoke all on public.user_last_activity from anon, authenticated;
grant select on public.user_last_activity to service_role;

-- 5. Console admin : le tonnage ne compte que la musculation (M15).
create or replace view public.admin_history_stats
  with (security_invoker = true) as
select
  count(*)::bigint                                                    as total_rows,
  coalesce(round(sum(coalesce(reps, 0) * coalesce(poids, 0))
                 filter (where exercice not like 'CARDIO:%')), 0)::bigint as total_tonnage,
  count(distinct (user_id, date::text, coalesce(seance, '')))::bigint as total_seances,
  count(distinct user_id) filter (where date::date >= current_date - 7)::bigint  as active_7d,
  count(distinct user_id) filter (where date::date >= current_date - 30)::bigint as active_30d
from public.history;

revoke all on public.admin_history_stats from anon, authenticated;
grant select on public.admin_history_stats to service_role;

-- Vérification : 0 ligne attendue.
-- select id, exercice, reps, poids, duree_min from public.history
--  where exercice like 'CARDIO:%' and (reps <> 0 or poids <> 0 or duree_min is null);
