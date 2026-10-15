"""Ce qu'une carte d'exercice rappelle de la fois d'avant.

Retour du 14/10 : « les remarques ne s'affichent pas d'une séance à une
autre ». Elles étaient bien enregistrées (une par série, history.remarque),
mais ne revenaient que dans le tableau replié « Historique et options », et
seulement pour les semaines précédentes : la séance de lundi était
invisible le jeudi. Elles reviennent désormais sous « Dernière fois ».

Même retour : « potentiel onglet réglages de machine ». Une ligne libre par
machine (« siège 4 · goupille 7 »), rangée dans le programme sous une clé
personnelle : elle survit aux changements de programme, sans migration
(core/db_programme.py, PROG_BODY_KEYS).

Module pur : ni Flask ni base. Hors des `seance_*` (plafonnés en taille).
"""
import re
from datetime import date

from core.seance_historique import _norm

JOURS_COURTS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."]
LONGUEUR_MAX = 300

# Ce que la colonne remarque contient sans que l'utilisateur l'ait écrit.
_RPE = re.compile(r"@?\bRPE\s*:?\s*[\d.,]+", re.I)
_BRUIT = ("Import Hevy", "Import Strong", "Import CSV")


def nettoyer_remarque(texte):
    """La remarque telle que l'utilisateur l'a tapée : sans le marqueur
    « SKIP » d'une série passée (la raison, elle, reste), sans les anciens
    jetons « @RPE8 », sans les mentions d'import."""
    t = str(texte or "").strip()
    if t.upper().startswith("SKIP"):
        t = t[4:]
    t = _RPE.sub("", t)
    for bruit in _BRUIT:
        t = t.replace(bruit, "")
    return " ".join(t.split()).strip(" ·-:")


def _jour_court(iso):
    try:
        d = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{JOURS_COURTS[d.weekday()]} {d.day:02d}/{d.month:02d}"


def derniere_remarque(hist, exo_final, seance, date_str):
    """« lun. 06/10 · S3 deux reps aidées » : les remarques de la dernière
    séance, avant `date_str`, où cet exercice en porte une. Cette séance
    d'abord, sinon toutes (un exercice déplacé garde ses notes). Par date et
    non par semaine ; les séries passées comptent : c'est souvent là qu'on
    écrit pourquoi. "" s'il n'y en a pas."""
    def lignes(meme_seance):
        out = []
        for r in hist:
            d = r.get("Date") or ""
            if not d or d >= date_str or _norm(r.get("Exercice")) != _norm(exo_final):
                continue
            if meme_seance and _norm(r.get("Séance")) != _norm(seance):
                continue
            texte = nettoyer_remarque(r.get("Remarque"))
            if texte:
                out.append((d, int(r.get("Série") or 0), texte))
        return out

    trouvees = lignes(True) or lignes(False)
    if not trouvees:
        return ""
    jour = max(d for d, _, _ in trouvees)
    du_jour = sorted(t for t in trouvees if t[0] == jour)
    notes = " · ".join(f"S{s} {texte}" if s else texte for _, s, texte in du_jour)
    return f"{_jour_court(jour)} · {notes}"[:LONGUEUR_MAX]


# ── Réglages de machine ──────────────────────────────────────────
CLE_REGLAGES = "_reglages_machines"
REGLAGES_MAX = 120


def cle_reglages(exo_id, base, variant):
    """Une machine = un exercice dans un équipement : la presse et la poulie
    n'ont pas les mêmes crans. L'identifiant stable survit aux renommages ;
    sans lui (exercice ajouté pour aujourd'hui), le nom."""
    racine = exo_id or ("n:" + _norm(base))
    return racine if not variant or variant == "Standard" else f"{racine}~{variant}"


def reglages_de(prog, cle):
    table = (prog or {}).get(CLE_REGLAGES)
    entree = table.get(cle) if isinstance(table, dict) else None
    return str(entree.get("texte") or "") if isinstance(entree, dict) else ""


def noter_reglages(prog, cle, texte, aujourdhui):
    """Écrit (ou efface, si vide) les réglages d'une machine dans `prog`.
    Rend le texte retenu, borné et sans espaces en trop."""
    texte = " ".join(str(texte or "").split())[:REGLAGES_MAX]
    table = prog.get(CLE_REGLAGES)
    if not isinstance(table, dict):
        table = prog[CLE_REGLAGES] = {}
    if texte:
        table[cle] = {"texte": texte, "maj": aujourdhui}
    else:
        table.pop(cle, None)
    return texte


def completer_cartes(exos_ctx, hist, seance, date_str, prog=None):
    """Ajoute à chaque carte ce qu'elle doit rappeler de la fois d'avant."""
    for ctx in exos_ctx:
        ctx["derniere_remarque"] = derniere_remarque(hist, ctx["exo_final"], seance, date_str)
        ctx["reglages_machine"] = reglages_de(
            prog, cle_reglages(ctx.get("exo_id"), ctx["base"], ctx.get("variant")))
    return exos_ctx
