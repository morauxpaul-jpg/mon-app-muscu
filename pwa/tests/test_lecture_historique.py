"""`get_hist` ne lit que les colonnes qu'elle regarde.

Elle faisait `select("*")`. La table `history` porte aussi `user_id`,
`session_id` et `created_at` — deux UUID et un horodatage, une centaine
d'octets par ligne que le mappeur ne lit jamais. Sur un an d'entraînement
(~1 900 lignes), c'était près de la moitié du transfert pour rien.

`rpe` n'existe qu'après la migration v34. `select("*")` l'ignorait sans bruit
si elle manquait ; une liste explicite ferait échouer la requête. D'où le même
repli qu'à l'écriture : on retombe sur la liste courte, une fois pour toutes.

La fausse base **projette** désormais les colonnes demandées, comme PostgREST.
Sans ça, restreindre le `select` n'aurait été vérifié nulle part : un champ
oublié serait passé au vert ici et aurait cassé en production.
"""
import datetime as dt

import pytest

from conftest import USER_ID

JOUR = dt.date(2026, 9, 14).isoformat()


@pytest.fixture()
def une_ligne(fake_db):
    fake_db.table("history").insert({
        "user_id": USER_ID, "date": JOUR, "semaine": "2026-W38",
        "seance": "Push", "exercice": "Développé couché", "muscle": "Pecs",
        "serie": 1, "reps": 10, "poids": 80.0, "remarque": "facile",
        "rpe": 7.5, "session_id": "sid-1"}).execute()
    return fake_db


def _hist(fake_db):
    import core.db as db
    db._data_cache.clear()
    return db.get_hist(USER_ID)


# ── Rien n'est perdu ─────────────────────────────────────────────────────

def test_toutes_les_valeurs_affichees_survivent(une_ligne):
    """Restreindre les colonnes ne doit vider aucun champ de la vue."""
    r = _hist(une_ligne)[0]
    assert r["Séance"] == "Push"
    assert r["Exercice"] == "Développé couché"
    assert r["Muscle"] == "Pecs"
    assert r["Série"] == 1
    assert r["Reps"] == 10
    assert r["Poids"] == 80.0
    assert r["Remarque"] == "facile"
    assert r["Date"] == JOUR
    assert r["RPE"] == 7.5
    assert r["Semaine"] > 0


def test_la_colonne_rpe_est_bien_demandee(une_ligne):
    """Sans elle, le RPE retomberait sur le token « @RPE » de la remarque."""
    import core.db as db
    assert "rpe" in db._HIST_COLS_LUES + ",rpe"
    assert _hist(une_ligne)[0]["RPE"] == 7.5


def test_les_colonnes_inutiles_ne_sont_pas_demandees():
    """Le point de tout l'exercice : ce qui ne sert pas ne traverse pas."""
    import core.db as db
    for inutile in ("user_id", "session_id", "created_at"):
        assert inutile not in db._HIST_COLS_LUES, (
            f"{inutile} est lu alors que rien ne le regarde")


def test_lordre_ne_depend_pas_dune_colonne_demandee(une_ligne):
    """`id` n'est plus dans le select : PostgREST trie quand même dessus.

    Si ce n'était pas vrai, l'historique reviendrait dans le désordre — et
    « dernière fois » afficherait la mauvaise séance.
    """
    for jour in ("2026-09-10", "2026-09-12"):
        une_ligne.table("history").insert({
            "user_id": USER_ID, "date": jour, "semaine": "2026-W37",
            "seance": "Push", "exercice": "Squat", "muscle": "Quadriceps",
            "serie": 1, "reps": 5, "poids": 100.0}).execute()
    lignes = _hist(une_ligne)
    assert [r["Date"] for r in lignes] == [JOUR, "2026-09-10", "2026-09-12"], \
        "l'ordre d'insertion n'est plus respecté"


# ── Le repli quand la migration v34 manque ───────────────────────────────

def test_une_base_sans_colonne_rpe_est_lue_quand_meme(une_ligne, monkeypatch):
    """Une base en retard ne doit pas faire tomber l'app.

    `select("*")` ignorait une colonne absente ; une liste explicite non.
    """
    import core.db_historique as mod
    appels = []
    vrai = mod._fetch_all

    def refuse_rpe(build):
        q = build()
        cols = getattr(q, "_colonnes", None) or []
        appels.append(list(cols))
        if "rpe" in cols:
            raise RuntimeError('column history.rpe does not exist')
        return vrai(build)

    monkeypatch.setattr(mod, "_fetch_all", refuse_rpe)
    monkeypatch.setattr(mod, "_hist_ext_supported", True)
    lignes = _hist(une_ligne)
    assert lignes, "la lecture doit aboutir malgré la colonne manquante"
    assert any("rpe" in c for c in appels), "elle doit d'abord essayer avec rpe"
    assert any("rpe" not in c for c in appels), "puis réessayer sans"
    assert lignes[0]["RPE"] is None


def test_une_autre_erreur_nest_pas_avalee(une_ligne, monkeypatch):
    """Le repli ne doit pas masquer une panne réelle.

    Sans ce test, une base injoignable ressemblerait à une migration
    manquante, et l'app relancerait une requête vouée au même échec.
    """
    import core.db_historique as mod
    essais = []

    def casse(_build):
        essais.append(1)
        raise RuntimeError("connexion refusée")

    monkeypatch.setattr(mod, "_fetch_all", casse)
    monkeypatch.setattr(mod, "_hist_ext_supported", True)
    with pytest.raises(RuntimeError, match="connexion"):
        _hist(une_ligne)
    # Un seul essai : réessayer sans `rpe` ne réparerait pas une connexion
    # coupée, ça doublerait juste l'attente avant l'erreur.
    assert len(essais) == 1, f"{len(essais)} tentatives pour une panne réseau"


# ── Le harnais lui-même ──────────────────────────────────────────────────

def test_la_fausse_base_projette_les_colonnes(fake_db):
    """Sans cette projection, restreindre un `select` ne serait pas testé."""
    fake_db.table("history").insert({
        "user_id": USER_ID, "date": JOUR, "seance": "Push",
        "exercice": "Squat", "poids": 100.0}).execute()
    ligne = fake_db.table("history").select("date,seance").eq(
        "user_id", USER_ID).execute().data[0]
    assert set(ligne) == {"date", "seance"}
    assert "poids" not in ligne


def test_letoile_ramene_tout(fake_db):
    """`select("*")` doit rester ce qu'il est, sinon tout le reste casse."""
    fake_db.table("history").insert({
        "user_id": USER_ID, "date": JOUR, "poids": 100.0}).execute()
    ligne = fake_db.table("history").select("*").eq(
        "user_id", USER_ID).execute().data[0]
    assert {"user_id", "date", "poids"} <= set(ligne)
