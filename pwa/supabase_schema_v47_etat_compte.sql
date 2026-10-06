-- ════════════════════════════════════════════════════════════════
-- v47 — L'état du compte sort de programs.data
-- ════════════════════════════════════════════════════════════════
-- Badges (_badges), record de série (_streak_record), défis
-- (_challenges_done, _challenges_won), « upsell vu » (_upsell_seen), quota
-- de debrief gratuit (_debrief_free), semaine allégée (_decharge_semaine,
-- _decharge_ignoree), plats de la semaine (_meal_plan) et cibles nutrition
-- perso (_nutrition) ne sont pas le programme. Une ligne par compte, une
-- colonne typée par donnée (core/db_etat.py).
--
-- Au passage, le « reset soft » est supprimé : son archive (_archive,
-- _legacy_volume) est retirée des programmes. Aucun compte ne s'en servait
-- au 06/10.
--
-- Fermée au navigateur comme les autres tables (v38).
--
-- ORDRE : déployer le code d'abord (sans la table, il garde tout dans le
-- programme et redemande la table chaque minute), puis exécuter ce fichier.
-- Les étapes sont idempotentes : rejouées ou coupées, elles ne doublent ni
-- ne perdent rien.
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

-- 1. La table.
create table if not exists public.etat_compte (
  user_id           uuid primary key references auth.users(id) on delete cascade,
  badges            jsonb   not null default '[]' check (jsonb_typeof(badges) = 'array'),
  record_serie      integer not null default 0 check (record_serie >= 0),
  defis_faits       jsonb   not null default '[]' check (jsonb_typeof(defis_faits) = 'array'),
  defis_gagnes      integer not null default 0 check (defis_gagnes >= 0),
  upsell_vu         boolean not null default false,
  debrief_gratuit   jsonb   not null default '{}' check (jsonb_typeof(debrief_gratuit) = 'object'),
  decharge_semaine  integer,
  decharge_ignoree  integer,
  plats_semaine     jsonb   check (plats_semaine is null or jsonb_typeof(plats_semaine) = 'object'),
  nutrition_perso   jsonb   check (nutrition_perso is null or jsonb_typeof(nutrition_perso) = 'object'),
  updated_at        timestamptz not null default now()
);

alter table public.etat_compte enable row level security;
revoke all on public.etat_compte from anon, authenticated;
grant select, insert, update, delete on public.etat_compte to service_role;

comment on table public.etat_compte is
  'État du compte (v47), sorti de programs.data : badges, défis, plats, cibles nutrition perso, compteurs.';

-- 2. L'état existant. Une valeur du mauvais type prend la valeur vide.
insert into public.etat_compte (user_id, badges, record_serie, defis_faits, defis_gagnes, upsell_vu,
                                debrief_gratuit, decharge_semaine, decharge_ignoree,
                                plats_semaine, nutrition_perso)
select p.user_id,
       case when jsonb_typeof(d->'_badges') = 'array' then d->'_badges' else '[]' end,
       case when jsonb_typeof(d->'_streak_record') = 'number' and (d->>'_streak_record')::numeric >= 0
            then trunc((d->>'_streak_record')::numeric)::integer else 0 end,
       case when jsonb_typeof(d->'_challenges_done') = 'array' then d->'_challenges_done' else '[]' end,
       case when jsonb_typeof(d->'_challenges_won') = 'number' and (d->>'_challenges_won')::numeric >= 0
            then trunc((d->>'_challenges_won')::numeric)::integer else 0 end,
       coalesce(case when jsonb_typeof(d->'_upsell_seen') = 'boolean' then (d->>'_upsell_seen')::boolean end, false),
       case when jsonb_typeof(d->'_debrief_free') = 'object' then d->'_debrief_free' else '{}' end,
       case when jsonb_typeof(d->'_decharge_semaine') = 'number' then trunc((d->>'_decharge_semaine')::numeric)::integer end,
       case when jsonb_typeof(d->'_decharge_ignoree') = 'number' then trunc((d->>'_decharge_ignoree')::numeric)::integer end,
       case when jsonb_typeof(d->'_meal_plan') = 'object' then d->'_meal_plan' end,
       case when jsonb_typeof(d->'_nutrition') = 'object' then d->'_nutrition' end
  from public.programs p
 cross join lateral (select p.data as d) x
 where d ?| array['_badges', '_streak_record', '_challenges_done', '_challenges_won', '_upsell_seen',
                  '_debrief_free', '_decharge_semaine', '_decharge_ignoree', '_meal_plan', '_nutrition']
   and exists (select 1 from auth.users u where u.id = p.user_id)
on conflict (user_id) do nothing;

-- 3. Le programme ne les porte plus, ni l'archive du reset soft. La version
--    monte : un onglet ouvert avant la migration passe par la fusion
--    (verrou optimiste, v32) au lieu de réécrire ces clés.
update public.programs
   set data = data - '_badges' - '_streak_record' - '_challenges_done' - '_challenges_won'
                   - '_upsell_seen' - '_debrief_free' - '_decharge_semaine' - '_decharge_ignoree'
                   - '_meal_plan' - '_nutrition' - '_archive' - '_legacy_volume',
       version = version + 1
 where data ?| array['_badges', '_streak_record', '_challenges_done', '_challenges_won', '_upsell_seen',
                     '_debrief_free', '_decharge_semaine', '_decharge_ignoree', '_meal_plan', '_nutrition',
                     '_archive', '_legacy_volume'];

-- Vérification : 0 attendu.
-- select count(*) from public.programs
--  where data ?| array['_badges', '_streak_record', '_challenges_done', '_challenges_won',
--                      '_upsell_seen', '_debrief_free', '_decharge_semaine', '_decharge_ignoree',
--                      '_meal_plan', '_nutrition', '_archive', '_legacy_volume'];
