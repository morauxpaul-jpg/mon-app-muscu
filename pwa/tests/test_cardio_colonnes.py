"""Le cardio dans ses propres colonnes (v44).

Une ligne cardio stockait sa durée dans `reps`, sa distance dans `poids`, et
ses calories et sa vitesse en texte dans la remarque (« Cal:360 | Vit:10.5 »).
Tout ce qui lit la base sans passer par l'app se trompait : la console admin
additionnait des minutes × kilomètres au tonnage (M15), et une requête SQL ne
pouvait pas sommer des calories écrites en texte. L'audit nommait ce format
comme la dernière dette du modèle de données.

Désormais : `duree_min`, `distance`, `calories`, `vitesse`, et `reps = poids
= 0` pour une ligne cardio. La conversion se fait à un seul endroit, à la
frontière avec la base (`core/db_historique.py`) ; l'app continue de lire
Reps/Poids/Remarque pour le cardio comme avant, ce qui garde intacts les
dizaines d'endroits qui l'affichent.
"""
import datetime as dt
from pathlib import Path

import pytest

from conftest import USER_ID, CSRF
from test_cardio_mesures import compte, JOUR  # noqa: F401  (fixture)

import core.db as db
import core.db_historique as dh

PWA = Path(__file__).resolve().parents[1]
SQL = (PWA / "supabase_schema_v44_cardio_colonnes.sql")


def _cardio(fake):
    return [r for r in fake.tables.get("history", [])
            if str(r.get("exercice") or "").startswith("CARDIO:")]


def _footing(client, **extra):
    data = {"activite": "Course", "date": JOUR, "duree_min": "30",
            "distance_km": "5", "vitesse": "", "calories": "320", "rpe": "Modéré"}
    data.update(extra)
    return client.post("/cardio/save", data=data, headers={"X-CSRFToken": CSRF},
                       follow_redirects=True)


# ── Écriture ─────────────────────────────────────────────────────────────

def test_la_page_cardio_ecrit_les_colonnes_dediees(compte, logged_in):
    _footing(logged_in)
    (ligne,) = _cardio(compte)
    assert ligne["duree_min"] == 30
    assert ligne["distance"] == 5.0
    assert ligne["calories"] == 320
    assert ligne["vitesse"] == 10.0
    # plus rien de détourné
    assert ligne["reps"] == 0 and ligne["poids"] == 0
    assert "Cal:" not in ligne["remarque"] and "Vit:" not in ligne["remarque"]
    assert "RPE:Modéré" in ligne["remarque"]


def test_le_cardio_dune_seance_muscu_aussi(compte, logged_in):
    logged_in.post("/seance/add-cardio", data={
        "mode": "prefaite", "name": "Push", "seance_name": "Push", "date": JOUR,
        "activite": "Rameur", "duree_min": "12", "distance_km": "2.5",
        "vitesse": "", "calories": "90", "_csrf": CSRF,
    }, headers={"X-CSRFToken": CSRF})
    (ligne,) = _cardio(compte)
    assert (ligne["duree_min"], ligne["distance"], ligne["calories"]) == (12, 2.5, 90)
    assert ligne["reps"] == 0 and ligne["poids"] == 0


def test_une_allure_non_numerique_reste_dans_la_remarque():
    """« Vit:2:05 » (allure du rameur saisie à la main) n'est pas un nombre :
    on ne le perd pas, on le laisse où il était."""
    p = dh._row_to_supabase(USER_ID, {
        "Date": JOUR, "Séance": "Cardio", "Exercice": "CARDIO:Rameur", "Série": 1,
        "Reps": 10, "Poids": 2, "Remarque": "Cal:80 | Vit:2:05 | note"})
    assert p["vitesse"] is None and "Vit:2:05" in p["remarque"]
    assert p["calories"] == 80


def test_une_ligne_de_musculation_ne_porte_aucune_colonne_cardio():
    p = dh._row_to_supabase(USER_ID, {
        "Date": JOUR, "Séance": "Push", "Exercice": "Squat", "Série": 1,
        "Reps": 5, "Poids": 100, "Remarque": "Cal:3"})
    assert (p["reps"], p["poids"], p["remarque"]) == (5, 100.0, "Cal:3")
    assert all(p[c] is None for c in ("duree_min", "distance", "calories", "vitesse"))


# ── Lecture : l'app voit le cardio comme avant ───────────────────────────

def test_lapp_relit_le_cardio_comme_avant(compte, logged_in):
    _footing(logged_in)
    (r,) = [r for r in db.get_hist(USER_ID) if r["Exercice"] == "CARDIO:Course"]
    assert (r["Reps"], r["Poids"]) == (30, 5.0)
    assert "Cal:320" in r["Remarque"] and "Vit:10" in r["Remarque"]
    assert (r["Duree"], r["Distance"], r["Calories"], r["Vitesse"]) == (30, 5.0, 320, 10.0)


def test_une_ancienne_ligne_se_lit_toujours(compte):
    """Avant la migration (ou une ligne qu'elle n'a pas touchée) : le format
    d'origine se lit à l'identique."""
    compte.table("history").insert({
        "user_id": USER_ID, "date": JOUR, "semaine": 38, "seance": "Cardio Course",
        "exercice": "CARDIO:Course", "serie": 1, "reps": 40, "poids": 8.0,
        "remarque": "Cal:500 | Vit:12 | RPE:Dur", "muscle": "Cardio"}).execute()
    (r,) = db.get_hist(USER_ID)
    assert (r["Reps"], r["Poids"], r["Duree"], r["Distance"]) == (40, 8.0, 40, 8.0)
    assert (r["Calories"], r["Vitesse"]) == (500, 12.0)
    assert r["Remarque"] == "Cal:500 | Vit:12 | RPE:Dur"


def test_la_seance_affiche_le_cardio_enregistre(compte, logged_in):
    logged_in.post("/seance/add-cardio", data={
        "mode": "prefaite", "name": "Push", "seance_name": "Push", "date": JOUR,
        "activite": "Rameur", "duree_min": "12", "distance_km": "2.5",
        "vitesse": "", "calories": "90", "_csrf": CSRF,
    }, headers={"X-CSRFToken": CSRF})
    from core.seance_cardio import _build_cardio_done
    (bloc,) = _build_cardio_done(db.get_hist(USER_ID), "Push", JOUR)
    assert (bloc["duree"], bloc["distance"], bloc["calories"]) == (12, 2.5, 90)


def test_les_statistiques_cardio_comptent_les_kilometres(compte, logged_in):
    _footing(logged_in)
    from core.cardio_activites import sum_cardio_km
    from core.hist import is_cardio
    assert sum_cardio_km([r for r in db.get_hist(USER_ID) if is_cardio(r)]) == 5.0
    assert logged_in.get("/progres").status_code == 200


# ── Base en retard : sans la v44, écriture à l'ancienne ──────────────────

def test_sans_la_v44_lecriture_garde_lancien_format(compte, logged_in, monkeypatch):
    from conftest import FakeQuery
    vraie_exec = FakeQuery.execute

    def refuse(self):
        charge = getattr(self, "_payload", None)
        lignes = charge if isinstance(charge, list) else [charge] if isinstance(charge, dict) else []
        sel = str(getattr(self, "_colonnes", "") or "")
        if "duree_min" in sel or any("duree_min" in (l or {}) for l in lignes):
            raise Exception("column history.duree_min does not exist")
        return vraie_exec(self)
    monkeypatch.setattr(FakeQuery, "execute", refuse)
    monkeypatch.setitem(dh._COLONNES, "cardio", True)

    _footing(logged_in)
    assert dh._COLONNES["cardio"] is False
    (ligne,) = _cardio(compte)
    assert (ligne["reps"], ligne["poids"]) == (30, 5.0)
    assert "Cal:320" in ligne["remarque"] and "Vit:10" in ligne["remarque"]
    (r,) = [r for r in db.get_hist(USER_ID) if r["Exercice"] == "CARDIO:Course"]
    assert (r["Reps"], r["Poids"], r["Calories"]) == (30, 5.0, 320)


def test_apres_la_v44_un_processus_en_retard_se_rattrape(compte, logged_in, monkeypatch):
    """Code déployé, colonnes vues absentes, puis migration appliquée : la
    contrainte refuse l'ancien format. L'écriture repasse au nouveau au lieu
    d'échouer jusqu'au redémarrage."""
    from conftest import FakeQuery
    vraie_exec = FakeQuery.execute

    def contrainte(self):
        charge = getattr(self, "_payload", None)
        lignes = charge if isinstance(charge, list) else [charge] if isinstance(charge, dict) else []
        if any(str(l.get("exercice", "")).startswith("CARDIO:") and l.get("reps")
               for l in lignes if l):
            raise Exception('new row for relation "history" violates check constraint '
                            '"history_cardio_colonnes_check"')
        return vraie_exec(self)
    monkeypatch.setattr(FakeQuery, "execute", contrainte)
    monkeypatch.setitem(dh._COLONNES, "cardio", False)

    _footing(logged_in)
    assert dh._COLONNES["cardio"] is True
    (ligne,) = _cardio(compte)
    assert (ligne["reps"], ligne["duree_min"], ligne["calories"]) == (0, 30, 320)


def test_la_migration_et_lapp_lisent_pareil_les_lignes_reelles():
    """Formes relevées en production le 05/10 (25 lignes cardio) : ce que
    l'app lisait avant est ce qu'elle lit après conversion."""
    from core.seance_cardio import _parse_cardio_remarque, depuis_colonnes, vers_colonnes
    formes = [
        (45, 1200, "Cal:390 | RPE:Modéré"), (0, 0, ""),
        (10, 0, "Cal:64 | RPE:Modéré | 420 marches vitesse 4"),
        (10, 420, "Cal:129 | RPE:Modéré | Vitesse 4"),
        (15, 1.25, "Cal:144 | Incl:7% | Vit:5 | RPE:Facile"),
        (10, 2.47, "Cal:115 | Vit:14.82"), (12, 2.5, "Cal:80 | Vit:2:05 | note"),
    ]
    for reps, poids, rem in formes:
        lu = depuis_colonnes({"exercice": "CARDIO:X", **vers_colonnes(reps, poids, rem)})
        assert (lu["reps"], lu["poids"]) == (reps, float(poids))
        assert _parse_cardio_remarque(lu["remarque"]) == _parse_cardio_remarque(rem), rem


# ── Ce qui lit la base sans passer par l'app ─────────────────────────────

def _cardio_seul(fake, jour):
    fake.table("history").insert({
        "user_id": USER_ID, "date": jour, "semaine": 1, "seance": "Cardio Course",
        "exercice": "CARDIO:Course", "serie": 1, "reps": 0, "poids": 0,
        "duree_min": 30, "distance": 5, "calories": 300, "vitesse": 10,
        "remarque": "", "muscle": "Cardio"}).execute()


def test_un_jour_de_cardio_seul_compte_comme_entraine(fake_db):
    """Sinon le rappel de séance part le soir d'un footing."""
    _cardio_seul(fake_db, JOUR)
    assert db.users_trained_on(JOUR) == {USER_ID}


def test_la_derniere_activite_voit_le_cardio(fake_db):
    """Repli du cron de relance (vue absente) : un coureur n'est pas inactif."""
    _cardio_seul(fake_db, JOUR)
    assert db._last_activity_by_user() == {USER_ID: JOUR}


def test_le_recap_compte_une_semaine_de_cardio():
    from core import recap
    lignes = [{"date": "2026-09-22", "seance": "Cardio Course",
               "exercice": "CARDIO:Course", "reps": 0, "poids": 0, "duree_min": 30}]
    assert recap._faites(lignes) == 1


# ── La migration ─────────────────────────────────────────────────────────

def test_la_migration_cree_remplit_et_verrouille():
    sql = SQL.read_text(encoding="utf-8").lower()
    for col in ("duree_min", "distance", "calories", "vitesse"):
        assert f"add column if not exists {col}" in sql
    # les lignes existantes passent au nouveau format…
    assert "duree_min = h.reps" in sql and "distance = h.poids" in sql
    # …et la base refuse le retour de l'ancien
    assert "history_cardio_colonnes_check" in sql
    # les deux vues qui lisaient reps/poids
    assert "create or replace view public.user_last_activity" in sql
    assert "create or replace view public.admin_history_stats" in sql
    assert sql.count("security_invoker = true") >= 2
    assert "revoke all on public.user_last_activity from anon, authenticated" in sql
    assert "revoke all on public.admin_history_stats from anon, authenticated" in sql
