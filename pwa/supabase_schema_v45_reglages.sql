-- ════════════════════════════════════════════════════════════════
-- v45 — Les réglages sortent de programs.data
-- ════════════════════════════════════════════════════════════════
-- Les réglages vivaient dans programs.data->'_settings', au milieu du
-- programme : non typés, sans défaut en base, et le cron des rappels
-- relisait le blob entier de chaque abonné pour connaître son heure. Ils
-- ont leur table : une ligne par compte, une colonne par réglage. Pas de
-- ligne = valeurs par défaut (les mêmes que core/db_reglages.py).
--
-- Quatre anciens réglages ne sont PAS repris : auto_collapse, show_1rm,
-- theme_animations et show_previous_weeks. Rien dans l'app ne les lisait.
--
-- Fermée au navigateur comme les autres tables (v38) : RLS actif, aucune
-- règle, aucun droit pour anon / authenticated. Le serveur passe par
-- service_role.
--
-- ORDRE : déployer le code d'abord (sans la table, il lit et écrit dans le
-- programme comme avant ; il redemande la table chaque minute), puis
-- exécuter ce fichier.
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

-- 1. La table.
create table if not exists public.reglages (
  user_id             uuid primary key references auth.users(id) on delete cascade,
  auto_rest_timer     boolean  not null default true,
  auto_prefill_weight boolean  not null default true,
  show_rpe            boolean  not null default true,
  show_overload_hint  boolean  not null default true,
  notifications       boolean  not null default false,
  reminder_hour       smallint not null default 18
                      check (reminder_hour = 0 or reminder_hour between 6 and 22),
  recap_hebdo         boolean  not null default true,
  updated_at          timestamptz not null default now()
);

alter table public.reglages enable row level security;
revoke all on public.reglages from anon, authenticated;
grant select, insert, update, delete on public.reglages to service_role;

comment on table public.reglages is
  'Réglages par compte (v45), sortis de programs.data->''_settings''. Pas de ligne = défauts.';

-- 2. Les réglages existants. Une valeur du mauvais type est ignorée (elle
--    prend le défaut) plutôt que de faire échouer la migration ; l'heure
--    est bornée comme dans core/reminders.py (0 = aucun rappel, sinon 6-22).
insert into public.reglages (user_id, auto_rest_timer, auto_prefill_weight, show_rpe,
                             show_overload_hint, notifications, reminder_hour, recap_hebdo)
select p.user_id,
       case when jsonb_typeof(s->'auto_rest_timer')     = 'boolean' then (s->>'auto_rest_timer')::boolean     else true  end,
       case when jsonb_typeof(s->'auto_prefill_weight') = 'boolean' then (s->>'auto_prefill_weight')::boolean else true  end,
       case when jsonb_typeof(s->'show_rpe')            = 'boolean' then (s->>'show_rpe')::boolean            else true  end,
       case when jsonb_typeof(s->'show_overload_hint')  = 'boolean' then (s->>'show_overload_hint')::boolean  else true  end,
       case when jsonb_typeof(s->'notifications')       = 'boolean' then (s->>'notifications')::boolean       else false end,
       case when jsonb_typeof(s->'reminder_hour') = 'number'
            then case when (s->>'reminder_hour')::numeric = 0 then 0
                      else least(22, greatest(6, trunc((s->>'reminder_hour')::numeric)))::smallint end
            else 18 end,
       case when jsonb_typeof(s->'recap_hebdo')         = 'boolean' then (s->>'recap_hebdo')::boolean         else true  end
  from public.programs p
 cross join lateral (select p.data->'_settings' as s) r
 where jsonb_typeof(r.s) = 'object'
   and exists (select 1 from auth.users u where u.id = p.user_id)
on conflict (user_id) do nothing;

-- 3. Le programme ne les porte plus. La version monte : un onglet ouvert
--    avant la migration qui enregistrerait son programme passe par la
--    fusion (verrou optimiste, v32) au lieu de réécrire la clé.
update public.programs
   set data = data - '_settings',
       version = version + 1
 where data ? '_settings';

-- Vérification : autant de lignes que de comptes qui avaient des réglages,
-- et plus aucun programme qui en porte.
-- select count(*) from public.reglages;
-- select count(*) from public.programs where data ? '_settings';
