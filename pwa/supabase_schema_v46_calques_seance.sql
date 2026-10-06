-- ════════════════════════════════════════════════════════════════
-- v46 — Les calques du jour sortent de programs.data
-- ════════════════════════════════════════════════════════════════
-- Exercices ajoutés à la volée (_extras), brouillon de séance libre
-- (_libre_draft), échanges du jour (_substituts) et ordre des cartes
-- (_seance_order) vivaient dans le blob du programme, indexés par
-- « séance|date ». Chaque geste en séance relisait et réécrivait le
-- programme entier. Ils ont leur table : une ligne par séance et par date,
-- une colonne par calque (core/db_calques.py).
--
-- Au passage, les bilans restés dans le blob (_session_notes, d'avant la
-- v34) rejoignent la table session_notes : la page de séance les relisait,
-- mais l'export des données et le coach, qui ne lisent que la table, ne
-- les voyaient pas.
--
-- Fermée au navigateur comme les autres tables (v38).
--
-- ORDRE : déployer le code d'abord (sans la table, il lit et écrit dans le
-- programme comme avant et redemande la table chaque minute), puis
-- exécuter ce fichier.
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

-- 1. La table.
create table if not exists public.calques_seance (
  user_id     uuid  not null references auth.users(id) on delete cascade,
  seance      text  not null,
  date        date  not null,
  extras      jsonb not null default '[]' check (jsonb_typeof(extras) = 'array'),
  brouillon   jsonb not null default '[]' check (jsonb_typeof(brouillon) = 'array'),
  substituts  jsonb not null default '{}' check (jsonb_typeof(substituts) = 'object'),
  ordre       jsonb not null default '[]' check (jsonb_typeof(ordre) = 'array'),
  updated_at  timestamptz not null default now(),
  primary key (user_id, seance, date)
);

alter table public.calques_seance enable row level security;
revoke all on public.calques_seance from anon, authenticated;
grant select, insert, update, delete on public.calques_seance to service_role;

comment on table public.calques_seance is
  'Calques du jour d''une séance (v46), sortis de programs.data. Une ligne vide n''est pas gardée.';

-- 2. Les calques existants. Clé « séance|date » : la date est après le
--    dernier « | ». Une clé sans date lisible, ou plus vieille que la
--    fenêtre de 84 jours de l'app, n'est pas reprise (la purge l'aurait
--    retirée). Une valeur du mauvais type prend la valeur vide.
with brut as (
  select p.user_id, c.colonne, e.key as cle, e.value as valeur
    from public.programs p
   cross join (values ('extras', '_extras'), ('brouillon', '_libre_draft'),
                      ('substituts', '_substituts'), ('ordre', '_seance_order')) as c(colonne, cle_blob)
   cross join lateral jsonb_each(case when jsonb_typeof(p.data->c.cle_blob) = 'object'
                                      then p.data->c.cle_blob else '{}'::jsonb end) as e
   where exists (select 1 from auth.users u where u.id = p.user_id)
), lu as (
  select user_id, colonne, valeur,
         regexp_replace(cle, '\|[^|]*$', '') as seance,
         substring(cle from '\|(\d{4}-\d{2}-\d{2})$') as jour
    from brut
)
insert into public.calques_seance (user_id, seance, date, extras, brouillon, substituts, ordre)
select user_id, seance, jour::date,
       coalesce(max(valeur::text) filter (where colonne = 'extras'     and jsonb_typeof(valeur) = 'array'),  '[]')::jsonb,
       coalesce(max(valeur::text) filter (where colonne = 'brouillon'  and jsonb_typeof(valeur) = 'array'),  '[]')::jsonb,
       coalesce(max(valeur::text) filter (where colonne = 'substituts' and jsonb_typeof(valeur) = 'object'), '{}')::jsonb,
       coalesce(max(valeur::text) filter (where colonne = 'ordre'      and jsonb_typeof(valeur) = 'array'),  '[]')::jsonb
  from lu
 where jour is not null
   and jour::date >= current_date - 84
 group by user_id, seance, jour
on conflict (user_id, seance, date) do nothing;

-- Une ligne entièrement vide n'est pas gardée (même règle que l'app).
delete from public.calques_seance
 where extras = '[]' and brouillon = '[]' and substituts = '{}' and ordre = '[]';

-- 3. Les bilans restés dans le blob. Tous repris, quel que soit leur âge :
--    ce sont des données de l'utilisateur. Une ligne déjà en table gagne.
insert into public.session_notes (user_id, date, seance, rating, comment, duration_min,
                                  created_at, updated_at)
select p.user_id,
       substring(e.key from '\|(\d{4}-\d{2}-\d{2})$')::date,
       regexp_replace(e.key, '\|[^|]*$', ''),
       case when jsonb_typeof(e.value->'rating') = 'number'
             and (e.value->>'rating')::numeric between 1 and 5
            then (e.value->>'rating')::numeric::smallint end,
       nullif(left(e.value->>'comment', 500), ''),
       case when jsonb_typeof(e.value->'duration_min') = 'number'
             and (e.value->>'duration_min')::numeric between 1 and 600
            then (e.value->>'duration_min')::numeric::smallint end,
       coalesce(case when e.value->>'ts' ~ '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$'
                     then (e.value->>'ts')::timestamp at time zone 'Europe/Paris' end, now()),
       now()
  from public.programs p
 cross join lateral jsonb_each(case when jsonb_typeof(p.data->'_session_notes') = 'object'
                                    then p.data->'_session_notes' else '{}'::jsonb end) as e
 where jsonb_typeof(e.value) = 'object'
   and e.key ~ '\|\d{4}-\d{2}-\d{2}$'
   and exists (select 1 from auth.users u where u.id = p.user_id)
on conflict (user_id, date, seance) do nothing;

-- 4. Le programme ne les porte plus. La version monte : un onglet ouvert
--    avant la migration qui enregistrerait son programme passe par la
--    fusion (verrou optimiste, v32) au lieu de réécrire ces clés.
update public.programs
   set data = data - '_extras' - '_libre_draft' - '_substituts' - '_seance_order' - '_session_notes',
       version = version + 1
 where data ?| array['_extras', '_libre_draft', '_substituts', '_seance_order', '_session_notes'];

-- Vérification : 0 attendu.
-- select count(*) from public.programs
--  where data ?| array['_extras', '_libre_draft', '_substituts', '_seance_order', '_session_notes'];
