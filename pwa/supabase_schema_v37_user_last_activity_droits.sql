-- ════════════════════════════════════════════════════════════════
-- v37 — La vue `user_last_activity` n'est lisible que par le serveur
-- ════════════════════════════════════════════════════════════════
-- Audit du 30/09 (I19). La v34 affirmait « les vues héritent des droits de
-- l'appelant » : c'est faux par défaut en PostgreSQL. Une vue s'exécute
-- avec les droits de son PROPRIÉTAIRE, donc sans le RLS de `history` — et
-- Supabase accorde par défaut SELECT aux rôles `anon` et `authenticated`
-- sur ce qui est créé dans `public`. Avec la clé anon (publique, dans la
-- page de connexion), n'importe qui pouvait lire l'identifiant et la date
-- de dernière séance de tous les comptes.
--
-- Seul le cron de relance la lit (core/db_push.py), avec service_role.
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

-- 1. La vue applique désormais le RLS de celui qui l'interroge
--    (PostgreSQL 15+, la version de Supabase).
alter view public.user_last_activity set (security_invoker = true);

-- 2. Et les rôles côté client n'y ont plus accès du tout.
revoke all on public.user_last_activity from anon, authenticated;
grant select on public.user_last_activity to service_role;

comment on view public.user_last_activity is
  'Dernière séance par utilisateur, pour le cron de relance. service_role uniquement (v37).';

-- Vérification : doit ne lister que service_role (et le propriétaire).
-- select grantee, privilege_type from information_schema.role_table_grants
--  where table_name = 'user_last_activity';
