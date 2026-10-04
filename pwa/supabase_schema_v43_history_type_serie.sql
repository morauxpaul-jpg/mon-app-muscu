-- ════════════════════════════════════════════════════════════════
-- v43 — Séries d'échauffement enregistrées à part
-- ════════════════════════════════════════════════════════════════
-- Une série d'échauffement compte dans ce qu'on a soulevé, pas dans le
-- travail : notée comme une série normale, elle faussait la suggestion de
-- charge, les séries par muscle et les records en répétitions (retour du
-- 04/10). Elle porte désormais type_serie = 'echauffement' ; l'app l'exclut
-- des records, suggestions, séries par muscle et du volume de travail, et
-- l'affiche à part dans la séance (« +200 échauff. »).
--
-- Colonne facultative : NULL = série de travail, comme toutes les lignes
-- existantes. Rien n'est réécrit. Sans elle, l'app ne propose pas la case.
--
-- À exécuter dans l'éditeur SQL de Supabase. Idempotent.

alter table public.history add column if not exists type_serie text;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'history_type_serie_check') then
    alter table public.history
      add constraint history_type_serie_check check (type_serie is null or type_serie = 'echauffement');
  end if;
end $$;

comment on column public.history.type_serie is
  'NULL = série de travail ; ''echauffement'' = hors records, suggestions, séries par muscle et volume de travail.';
