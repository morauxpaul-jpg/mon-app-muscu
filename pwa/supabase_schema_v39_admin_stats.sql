-- ════════════════════════════════════════════════════════════════
-- v39 — Les chiffres de la console admin calculés par la base
-- ════════════════════════════════════════════════════════════════
-- /admin relisait TOUT l'historique de TOUS les comptes (paginé par 1 000
-- lignes) pour afficher cinq nombres. Le coût grandissait avec chaque série
-- enregistrée par chaque utilisateur (audit du 30/09, M6). Une vue agrège
-- côté PostgreSQL : une ligne, cinq colonnes.
--
-- Lisible par le serveur seulement (service_role) : security_invoker, et
-- aucun droit pour anon / authenticated (cf. v38).
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent. Sans elle, l'app
-- retombe sur l'ancien calcul (plus lent, même résultat).

create or replace view public.admin_history_stats
  with (security_invoker = true) as
select
  count(*)::bigint                                                    as total_rows,
  coalesce(round(sum(coalesce(reps, 0) * coalesce(poids, 0))), 0)::bigint as total_tonnage,
  count(distinct (user_id, date::text, coalesce(seance, '')))::bigint as total_seances,
  count(distinct user_id) filter (where date::date >= current_date - 7)::bigint  as active_7d,
  count(distinct user_id) filter (where date::date >= current_date - 30)::bigint as active_30d
from public.history;

revoke all on public.admin_history_stats from anon, authenticated;
grant select on public.admin_history_stats to service_role;
