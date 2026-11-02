"""Séance créée par le coach : reprise après une pause, courte, légère (02/11).

Choix du propriétaire : ouvert comme le coach (PRO et essai), la séance
entre dans le programme hors planning, et une reprise allège les charges
selon la durée de la pause. Ce qui est tenu ici :

* le facteur de reprise, palier par palier, et l'arrondi des charges ;
* la charge habituelle : la plus lourde des 3 dernières séances de
  l'exercice, au même matériel, séries de travail seulement ;
* l'IA ne reçoit ni ne donne aucune charge : elles sont calculées par le
  serveur, à l'aperçu et de nouveau à l'ajout ;
* la séance du programme pré-remplit les charges allégées la première
  fois, puis la progression ordinaire reprend ;
* accès, quota, refus et réponse illisible.
"""
import datetime as dt
import json
import re
import sys
import time
import types

import pytest

import core.db as core_db
from conftest import CSRF, USER_ID, prog_lu
from core import coach_seance as calc
from core.dates import continuous_week, logical_today_paris
from core.seance_contexte import _build_exo_context

AUJ = logical_today_paris()
J = dt.timedelta(days=1)


def _r(date, exo="Développé couché (Barre)", poids=80.0, reps=8, seance="Push", **autres):
    return {"Date": str(date), "Séance": seance, "Exercice": exo, "Poids": poids, "Reps": reps,
            "Série": 1, "Remarque": "", "Muscle": "Pecs", **autres}


# ── Le calcul ────────────────────────────────────────────────────


@pytest.mark.parametrize("jours, attendu", [
    (0, .90), (13, .90), (14, .85), (27, .85), (28, .75), (55, .75), (56, .65), (119, .65),
    (120, .55), (400, .55)])
def test_le_facteur_de_reprise_suit_la_pause(jours, attendu):
    assert calc.facteur("reprise", jours) == attendu


def test_les_autres_seances_et_l_absence_d_historique():
    assert calc.facteur("legere", 3) == .80 and calc.facteur("legere", None) == .80
    assert calc.facteur("courte", 200) == 1.0 and calc.facteur("libre", 200) == 1.0
    assert calc.facteur("reprise", None) == 1.0          # rien pour comparer : pas d'allègement


def test_l_arrondi_des_charges():
    assert calc.arrondi(80 * .75) == 60.0 and calc.arrondi(72.5 * .65) == 47.5
    assert calc.arrondi(17.4) == 17.0 and calc.arrondi(12 * .55) == 7.0      # 1 kg sous 20 kg


def test_la_pause_se_compte_depuis_la_derniere_seance_faite():
    assert calc.jours_de_pause([], AUJ) is None
    hist = [_r(AUJ - 40 * J), _r(AUJ - 60 * J), _r(AUJ - 5 * J, reps=0, poids=0)]   # série vide : pas faite
    assert calc.jours_de_pause(hist, AUJ) == 40
    hist.append(_r(AUJ - 3 * J, exo="CARDIO:Course", poids=5, reps=30))            # le cardio compte
    assert calc.jours_de_pause(hist, AUJ) == 3


def test_la_charge_habituelle_est_la_plus_lourde_des_trois_dernieres_seances():
    hist = [_r(AUJ - 90 * J, poids=100),                          # 4e séance en arrière : ignorée
            _r(AUJ - 60 * J, poids=82.5, reps=5),
            _r(AUJ - 50 * J, poids=80), _r(AUJ - 50 * J, poids=40, Type="echauffement"),
            _r(AUJ - 45 * J, poids=77.5),
            _r(AUJ - 45 * J, exo="Développé couché (Haltères)", poids=90),       # autre matériel
            _r(AUJ, poids=120)]                                   # aujourd'hui : pas une référence
    assert calc.charge_habituelle(hist, "Développé couché (Barre)", AUJ) == {
        "poids": 82.5, "reps": 5, "date": str(AUJ - 60 * J)}
    assert calc.charge_habituelle(hist, "Squat", AUJ) is None


def test_les_conseils_de_reprise():
    hist = [_r(AUJ - 40 * J, poids=80),
            _r(AUJ - 40 * J, exo="Tractions", poids=0, reps=10)]
    exos = [{"name": "Développé couché", "materiel": "Barre"}, {"name": "Tractions", "materiel": None},
            {"name": "Squat", "materiel": None}]
    c = calc.conseils(exos, hist, "reprise", calc.facteur("reprise", 40), AUJ)
    assert c["Développé couché"]["poids"] == 60.0
    assert c["Développé couché"]["libelle"] == ("Reprise : 60 kg, −25 % de tes 80 kg habituels. "
                                                "Garde 2 à 3 reps en réserve.")
    assert c["Tractions"] == {"poids": None, "reps": 7, "habituel": 10,
                              "libelle": "Reprise : 7 reps, −25 % de tes 10 habituelles. "
                                         "Garde 2 à 3 reps en réserve."}
    assert "Squat" not in c                                       # jamais fait : la carte donne une méthode
    assert calc.conseils(exos, hist, "courte", 1.0, AUJ) == {}
    legere = calc.conseils(exos, hist, "legere", calc.FACTEUR_LEGERE, AUJ)
    assert legere["Développé couché"]["libelle"].startswith("Séance légère : 65 kg, −20 %")


def test_la_reponse_de_l_ia_est_lue_et_bornee():
    raw = "```json\n" + json.dumps({"nom": "  Reprise   haut  ", "notes": "Doucement.", "exercices": [
        {"name": "Développé couché (Barre)", "sets": 9, "reps": "8-10", "rest_seconds": 999, "muscle": "pecs"},
        {"name": "Développé couché (Haltères)", "sets": 3},             # même mouvement : doublon
        {"name": "_cache", "sets": 3}, "pas un exercice",
        {"name": "Planche", "sets": 0, "rest_seconds": 5, "muscle": "Inconnu", "poids": 200},
        {"name": "Squat", "materiel": "Haltères"}, {"name": "Rowing", "materiel": "Fusée"}]}) + "\n```"
    p = calc.lire_reponse(raw)
    assert p["nom"] == "Reprise haut" and p["notes"] == "Doucement."
    assert p["exercices"] == [
        {"name": "Développé couché", "materiel": "Barre", "sets": 5, "reps": "8-10",
         "rest_seconds": 180, "muscle": "Pecs"},
        {"name": "Planche", "materiel": None, "sets": 3, "reps": "", "rest_seconds": 45, "muscle": "Autre"},
        {"name": "Squat", "materiel": "Haltères", "sets": 3, "reps": "", "rest_seconds": 90, "muscle": "Autre"},
        {"name": "Rowing", "materiel": None, "sets": 3, "reps": "", "rest_seconds": 90, "muscle": "Autre"}]
    assert calc.lire_reponse(p)["exercices"] == p["exercices"]          # relue à l'ajout : identique
    for faux in ("pas du json", "{}", '{"exercices": []}', '{"exercices": [{"name": ""}]}'):
        with pytest.raises(ValueError):
            calc.lire_reponse(faux)


def test_l_ia_ne_recoit_aucune_charge():
    hist = [_r(AUJ - 40 * J, poids=87.5), _r(AUJ - 41 * J, exo="Squat", poids=143)]
    prompt = calc.consigne_ia("reprise", 45, "épaule fragile", calc.exercices_habituels(hist, AUJ), 40,
                              {"niveau": "Intermédiaire"})
    assert "Développé couché (Barre)" in prompt and "Squat" in prompt and "épaule fragile" in prompt
    assert "il y a 40 jours" in prompt and "REPRISE" in prompt
    assert "87" not in prompt and "143" not in prompt


def test_les_conseils_valent_tant_que_la_seance_n_a_pas_ete_faite():
    prog = {calc.CLE_PROGRAMME: {"Reprise": {"conseils": {"Développé couché": {"poids": 60.0}}}}}
    assert calc.conseils_actifs(prog, "Reprise", [], AUJ.isoformat()) == {"Développé couché": {"poids": 60.0}}
    # Des séries saisies aujourd'hui : c'est la séance en cours, les conseils restent.
    assert calc.conseils_actifs(prog, "Reprise", [_r(AUJ, seance="Reprise")], AUJ.isoformat())
    # Faite un autre jour : la progression ordinaire reprend.
    assert calc.conseils_actifs(prog, "Reprise", [_r(AUJ - J, seance="Reprise")], AUJ.isoformat()) == {}
    assert calc.conseils_actifs(prog, "Push", [], AUJ.isoformat()) == {}
    assert calc.conseils_actifs({}, "Reprise", [], AUJ.isoformat()) == {}


def test_la_carte_pre_remplit_chaque_serie_avec_la_charge_conseillee():
    hist = [dict(_r("2026-08-01", poids=80), Série=1, Semaine=1)]
    exo = {"name": "Développé couché", "sets": 3, "muscle": "Pecs", "reps": "8-10", "materiel": "Barre"}
    conseil = {"poids": 60.0, "reps": None, "habituel": 80.0, "libelle": "Reprise : 60 kg"}
    carte = _build_exo_context(hist, exo, "Reprise", 50, "2026-09-21", conseil=conseil)
    assert carte["exo_final"] == "Développé couché (Barre)"
    assert [s["poids"] for s in carte["sets"]] == [60.0, 60.0, 60.0]        # pas seulement la 1re
    assert carte["suggestion"]["label"] == "Reprise : 60 kg" and carte["suggestion"]["why"] == "coach"
    sans = _build_exo_context(hist, exo, "Reprise", 50, "2026-09-21")
    assert sans["sets"][0]["poids"] == 80.0


# ── Les routes ───────────────────────────────────────────────────


REPONSE_IA = {"nom": "Reprise", "notes": "On reprend en douceur.", "exercices": [
    {"name": "Développé couché (Barre)", "sets": 3, "reps": "8-10", "rest_seconds": 120, "muscle": "Pecs",
     "poids": 120},                                                       # une charge de l'IA : ignorée
    {"name": "Tractions", "sets": 3, "reps": "6-8", "rest_seconds": 120, "muscle": "Dos"},
    {"name": "Gainage", "sets": 2, "reps": "30 s", "rest_seconds": 60, "muscle": "Abdos"}]}


@pytest.fixture()
def ia(monkeypatch):
    """Une fausse API Anthropic : garde les prompts, rend `reponse`."""
    from core import taches_ia
    etat = {"prompts": [], "reponse": json.dumps(REPONSE_IA), "stop": "end_turn"}

    class Client:
        def __init__(self, **_k):
            self.messages = types.SimpleNamespace(create=self._create)

        def _create(self, **k):
            etat["prompts"].append(k["messages"][-1]["content"])
            return types.SimpleNamespace(content=[types.SimpleNamespace(text=etat["reponse"])],
                                         stop_reason=etat["stop"], usage=None)

    monkeypatch.setitem(sys.modules, "anthropic", types.SimpleNamespace(Anthropic=Client))
    monkeypatch.setattr("routes.coach_seance._env", lambda *_a, **_k: "cle-de-test")
    monkeypatch.setattr(taches_ia, "ATTENTE_REQUETE", 5.0)
    return etat


@pytest.fixture()
def compte(fake_db, logged_in):
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs", "materiel": "Barre"}],
        "_planning": {"Lundi": "Push"}, "_settings": {}}}).execute()
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip", "prenom": "Paul"}).execute()
    pause = AUJ - 40 * J
    for n, (exo, poids, reps) in enumerate([("Développé couché (Barre)", 80, 8), ("Tractions", 0, 10)]):
        fake_db.table("history").insert({
            "user_id": USER_ID, "semaine": continuous_week(pause), "seance": "Push", "exercice": exo,
            "serie": 1, "reps": reps, "poids": poids, "remarque": "", "muscle": "Pecs",
            "date": pause.isoformat()}).execute()
    core_db.vider_cache()
    return logged_in


def _json(texte):
    return json.dumps(texte)[1:-1]


def _creer(client, **params):
    r = client.post("/coach/seance", json={"type": "reprise", "duree": 45, **params},
                    headers={"X-CSRFToken": CSRF})
    for _ in range(50):
        if r.status_code != 202:
            break
        time.sleep(0.1)
        r = client.get(f"/coach/seance/tache/{r.get_json()['tache']}")
    return r


def test_creer_une_reprise_donne_des_charges_calculees_par_le_serveur(compte, ia):
    page = compte.get("/coach/seance").get_data(as_text=True)
    assert "Ta dernière séance date de 40 jours" in page and "−25 %" in page
    r = _creer(compte, demande="épaule fragile")
    assert r.status_code == 200, r.get_json()
    d = r.get_json()
    assert d["pause"] == 40 and d["facteur"] == .75
    assert [l["conseil"] for l in d["lignes"]] == [
        "Reprise : 60 kg, −25 % de tes 80 kg habituels. Garde 2 à 3 reps en réserve.",
        "Reprise : 7 reps, −25 % de tes 10 habituelles. Garde 2 à 3 reps en réserve.",
        ""]                                                        # gainage : jamais fait
    (prompt,) = ia["prompts"]
    assert "épaule fragile" in prompt and "Développé couché (Barre)" in prompt
    assert not re.search(r"\b80\b", prompt)                       # « 180 s » de repos, pas les 80 kg


def test_ajouter_met_la_seance_au_programme_hors_planning(compte, ia):
    d = _creer(compte).get_json()
    trafique = dict(d["proposition"])
    trafique["conseils"] = {"Développé couché": {"poids": 500}}    # rien du navigateur n'est cru
    r = compte.post("/coach/seance/ajouter", json={"type": "reprise", "proposition": trafique},
                    headers={"X-CSRFToken": CSRF})
    assert r.status_code == 200 and r.get_json()["nom"] == "Reprise"
    assert r.get_json()["lien"] == "/seance?mode=prefaite&name=Reprise"
    prog = prog_lu()
    assert [e["name"] for e in prog["Reprise"]] == ["Développé couché", "Tractions", "Gainage"]
    assert prog["Reprise"][0]["materiel"] == "Barre" and prog["Reprise"][0]["reps"] == "8-10"
    assert prog["_planning"] == {"Lundi": "Push"}                 # planning intact
    fiche = prog[calc.CLE_PROGRAMME]["Reprise"]
    assert fiche["facteur"] == .75 and fiche["pause_jours"] == 40 and fiche["type"] == "reprise"
    assert fiche["conseils"]["Développé couché"]["poids"] == 60.0
    # Une seconde : jamais une séance écrasée.
    compte.post("/coach/seance/ajouter", json={"type": "reprise", "proposition": d["proposition"]},
                headers={"X-CSRFToken": CSRF})
    assert "Reprise 2" in prog_lu() and len(prog_lu()["Reprise"]) == 3


def test_la_seance_pre_remplit_les_charges_allegees_la_premiere_fois(compte, ia):
    d = _creer(compte).get_json()
    compte.post("/coach/seance/ajouter", json={"type": "reprise", "proposition": d["proposition"]},
                headers={"X-CSRFToken": CSRF})
    html = compte.get(f"/seance?mode=prefaite&name=Reprise&date={AUJ.isoformat()}").get_data(as_text=True)
    # Les cartes reçoivent leurs données en JSON (accents échappés).
    assert _json("Reprise : 60 kg, −25 % de tes 80 kg habituels") in html
    assert _json("Reprise : 7 reps, −25 % de tes 10 habituelles") in html
    assert html.count('"poids": 60.0, "remarque": "", "reps": null') == 3    # les 3 séries pré-remplies
    # Faite une première fois (hier) : la progression ordinaire reprend.
    fake = core_db.current_client()
    fake.table("history").insert({
        "user_id": USER_ID, "semaine": continuous_week(AUJ - J), "seance": "Reprise",
        "exercice": "Développé couché (Barre)", "serie": 1, "reps": 10, "poids": 60, "remarque": "",
        "muscle": "Pecs", "date": (AUJ - J).isoformat()}).execute()
    core_db.vider_cache()
    html = compte.get(f"/seance?mode=prefaite&name=Reprise&date={AUJ.isoformat()}").get_data(as_text=True)
    assert _json("−25 % de tes") not in html


def test_reservee_au_coach_pro_et_essai(fake_db, client, ia):
    with client.session_transaction() as s:
        s.update(user_id=USER_ID, email="t@example.com", fournisseurs=["google"], onboarded=True,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time(), auth_check_ts=time.time(),
                 _csrf=CSRF)
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {"_settings": {}}}).execute()
    assert "PRO" in client.get("/coach/seance").get_data(as_text=True)
    assert client.post("/coach/seance", json={}, headers={"X-CSRFToken": CSRF}).status_code == 403
    assert client.post("/coach/seance/ajouter", json={}, headers={"X-CSRFToken": CSRF}).status_code == 403
    assert ia["prompts"] == []
    with client.session_transaction() as s:
        s["is_vip"] = True                                         # essai PRO en cours
    page = client.get("/coach/seance")
    assert page.status_code == 200 and "Créer la séance" in page.get_data(as_text=True)


def test_le_quota_du_jour(compte, ia, monkeypatch):
    monkeypatch.setattr("routes.coach_seance.compter", lambda *_a: 5)
    r = compte.post("/coach/seance", json={"type": "reprise"}, headers={"X-CSRFToken": CSRF})
    assert r.status_code == 429 and ia["prompts"] == []
    assert "Limite du jour atteinte" in compte.get("/coach/seance").get_data(as_text=True)


def test_un_refus_ou_une_reponse_illisible_ne_cree_rien(compte, ia):
    ia["stop"] = "refusal"
    assert _creer(compte).status_code == 422
    ia["stop"], ia["reponse"] = "end_turn", "Désolé, je ne peux pas."
    assert _creer(compte).status_code == 502
    evenements = [e["event"] for e in core_db.current_client().tables.get("events", [])]
    assert "coach_seance_creee" not in evenements                  # quota intact
    assert "_seances_coach" not in prog_lu()


def test_une_seance_illisible_n_est_pas_ajoutee(compte):
    r = compte.post("/coach/seance/ajouter", json={"proposition": {"exercices": "rien"}},
                    headers={"X-CSRFToken": CSRF})
    assert r.status_code == 400 and "_seances_coach" not in prog_lu()


def test_les_liens_vers_la_page(compte):
    assert 'href="/coach/seance"' in compte.get("/plus").get_data(as_text=True)
    assert 'href="/coach/seance"' in compte.get("/coach").get_data(as_text=True)
