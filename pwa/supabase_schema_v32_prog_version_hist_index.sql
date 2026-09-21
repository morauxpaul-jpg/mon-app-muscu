-- v32 — Verrou optimiste sur programs + index sur history.
--
-- 1) programs.version : compteur incrémenté à chaque écriture. Le backend
--    fait `update ... where user_id = ? and version = <version lue>` ; si
--    aucune ligne n'est touchée, c'est qu'un autre worker a écrit entre-temps
--    (cache mémoire 60 s par process) → relecture + fusion par clé au lieu
--    d'écraser silencieusement le blob JSON (cf. core/db.py save_prog).
--
-- 2) history(user_id, id) : toutes les pages lisent
--    `select * from history where user_id = ? order by id` ; sans index c'est
--    un scan complet de la table à chaque requête.
--
-- À exécuter AVANT de déployer le code qui lit `version` (select("*") tolère
-- l'absence de la colonne, mais le verrou ne s'active qu'une fois la colonne
-- présente).

alter table public.programs
  add column if not exists version integer not null default 1;

create index if not exists history_user_id_idx
  on public.history (user_id, id);
