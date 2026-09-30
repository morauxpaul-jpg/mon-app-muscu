-- ════════════════════════════════════════════════════════════════
-- v38 — Les tables ne sont plus accessibles depuis le navigateur
-- ════════════════════════════════════════════════════════════════
-- La politique « profiles: self update » laissait chaque utilisateur
-- modifier TOUTES les colonnes de sa ligne, `tier` compris. Le navigateur
-- garde une session Supabase après la connexion Google : depuis la console,
-- un compte gratuit pouvait faire `update profiles set tier = 'vip'` et
-- passer PRO sans payer (ou remettre son quota coach à zéro, s'offrir un
-- essai via vip_until, modifier les compteurs rangés dans programs).
--
-- Le navigateur n'utilise Supabase QUE pour l'authentification (login.html,
-- bridge.html). Toutes les lectures et écritures de données passent par le
-- serveur Flask avec la clé service_role, qui contourne le RLS. Les règles
-- « self » ne servent donc à rien — sauf à ouvrir cette porte.
--
-- On retire toutes les règles côté client et les droits des rôles anon et
-- authenticated. Le RLS reste activé : sans règle, tout est refusé à ces
-- rôles. service_role n'est pas concerné.
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

drop policy if exists "body_weight_delete_own"   on public.body_weight;
drop policy if exists "body_weight_select_own"   on public.body_weight;
drop policy if exists "body_weight_update_own"   on public.body_weight;
drop policy if exists "body_weight_insert_own"   on public.body_weight;
drop policy if exists "coach_conv_update_own"    on public.coach_conversations;
drop policy if exists "coach_conv_select_own"    on public.coach_conversations;
drop policy if exists "coach_conv_insert_own"    on public.coach_conversations;
drop policy if exists "coach_conv_delete_own"    on public.coach_conversations;
drop policy if exists "history: self update"     on public.history;
drop policy if exists "history: self read"       on public.history;
drop policy if exists "history: self delete"     on public.history;
drop policy if exists "history: self insert"     on public.history;
drop policy if exists "nutrition_update_own"     on public.nutrition;
drop policy if exists "nutrition_delete_own"     on public.nutrition;
drop policy if exists "nutrition_insert_own"     on public.nutrition;
drop policy if exists "nutrition_select_own"     on public.nutrition;
drop policy if exists "onboarding self"          on public.onboarding;
drop policy if exists "profiles: self update"    on public.profiles;
drop policy if exists "profiles: self read"      on public.profiles;
drop policy if exists "profiles: self upsert"    on public.profiles;
drop policy if exists "programs: self read"      on public.programs;
drop policy if exists "programs: self upsert"    on public.programs;
drop policy if exists "programs: self update"    on public.programs;

-- Ceinture et bretelles : plus aucun droit de table pour les rôles client,
-- sur toutes les tables et vues du schéma public (présentes et futures).
revoke all on all tables in schema public from anon, authenticated;
alter default privileges in schema public revoke all on tables from anon, authenticated;

-- Vérification : les deux requêtes doivent renvoyer 0 ligne.
-- select * from pg_policies where schemaname = 'public';
-- select table_name, grantee from information_schema.role_table_grants
--  where table_schema = 'public' and grantee in ('anon', 'authenticated');
