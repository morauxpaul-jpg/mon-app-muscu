-- Migration v48 — durcissement après l'audit du 06/10/2026.
-- À exécuter dans Supabase → SQL Editor (ou par le connecteur), une fois.
-- Idempotente : ré-exécutable sans effet de plus.
--
-- 1. handle_new_user() est la fonction du déclencheur qui crée le profil et le
--    programme d'un compte neuf (on_auth_user_created). Supabase la signalait
--    (get_advisors, lints 0028 et 0029) : SECURITY DEFINER et exécutable par
--    `anon` et `authenticated` via /rest/v1/rpc/handle_new_user. Un appel
--    direct échoue (fonction de déclencheur), mais rien ne justifie ce droit.
--    PostgreSQL ne vérifie EXECUTE qu'à la création du déclencheur, pas quand il
--    se déclenche : l'inscription n'est pas touchée (rejoué en local, voir le
--    rapport d'audit).
--
-- 2. `_profiles` et `_active_profile` restaient dans 9 programmes : la
--    fonction « profils d'entraînement » a été retirée le 01/10 et aucun code
--    ne les lit plus. La version du programme est incrémentée, pour qu'un
--    onglet resté ouvert ne réécrive pas l'ancien contenu (verrou optimiste).

revoke execute on function public.handle_new_user() from public, anon, authenticated;

update public.programs
   set data = data - '_profiles' - '_active_profile',
       version = coalesce(version, 1) + 1
 where data ?| array['_profiles', '_active_profile'];

-- Vérifications (doivent rendre false, false, 0) :
-- select has_function_privilege('anon', 'public.handle_new_user()', 'execute'),
--        has_function_privilege('authenticated', 'public.handle_new_user()', 'execute'),
--        (select count(*) from public.programs where data ?| array['_profiles', '_active_profile']);
