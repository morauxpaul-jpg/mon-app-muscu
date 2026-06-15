-- v31 — Opt-in newsletter e-mail (consentement RGPD pour les annonces produit).
-- Le consentement est recueilli dans l'app (Gestion) ; la liste s'exporte
-- ensuite vers un outil d'emailing (Brevo) côté admin.
--
-- newsletter_opt_in     : l'utilisateur accepte de recevoir les nouveautés
-- newsletter_opt_in_at  : date du consentement (preuve RGPD ; null si retiré)
-- newsletter_email      : e-mail au moment du consentement (évite un appel à
--                         l'API auth pour l'export ; = e-mail du compte Google)

alter table public.profiles
  add column if not exists newsletter_opt_in    boolean not null default false,
  add column if not exists newsletter_opt_in_at timestamptz,
  add column if not exists newsletter_email      text;
