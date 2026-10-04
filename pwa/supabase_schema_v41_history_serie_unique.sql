-- ════════════════════════════════════════════════════════════════
-- v41 — Une série = une ligne : index unique sur l'historique
-- ════════════════════════════════════════════════════════════════
-- Deux écritures croisées du même exercice (requête abandonnée par le
-- téléphone puis renvoyée) pouvaient doubler des séries. Un verrou en
-- mémoire les met en file, mais il ne vaut que pour un seul processus
-- (audit du 03/10, I7). L'index le garantit en base, et permet à l'app
-- d'écrire PAR CLÉ (upsert) : une écriture rejouée réécrit les mêmes
-- lignes au lieu d'en ajouter.
--
-- Clé : (user_id, date, seance, exercice, serie). Une ligne sans date n'entre
-- jamais en collision (NULL), comme avant.
--
-- Sécurité : la migration refuse de s'appliquer s'il existe déjà des
-- doublons — elle n'efface rien. Au 04/10/2026 : 1 136 lignes, 0 doublon.
-- Sans elle, l'app écrit comme avant (repli automatique).
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

do $$
declare
  n bigint;
begin
  select count(*) into n from (
    select 1 from public.history
    where date is not null
    group by user_id, date, seance, exercice, serie
    having count(*) > 1
  ) d;
  if n > 0 then
    raise exception 'v41 : % groupe(s) de séries en double — à fusionner avant de créer l''index', n;
  end if;
end $$;

create unique index if not exists history_serie_unique
  on public.history (user_id, date, seance, exercice, serie);

notify pgrst, 'reload schema';
