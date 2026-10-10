"""Ce que coûte une « Série faite » pendant une vraie séance.

En production, le 04/10, l'enregistrement d'une série prenait 1,4 à 2,9 s
côté serveur (audit du 06/10, I-2). Chaque appel à la base coûte 45 à 135 ms
(Railway aux Pays-Bas, Supabase en Irlande). Or le cache ne gardait les
données que 60 s : un repos entre deux séries dépasse presque toujours la
minute, donc chaque série relisait l'historique, le programme, l'état du
compte et le profil — 7 appels par série, plus l'API auth toutes les 2 min.

Ces tests rejouent une séance à l'horloge réelle : des repos de 2 et 3 min.
"""
import collections
import datetime as dt
import json
import time

import pytest

from conftest import CSRF, USER_ID

EXO_ID = "e_1a2b3c4d"


@pytest.fixture()
def seance(fake_db, logged_in, monkeypatch):
    """Un compte gratuit au milieu d'une séance, une horloge qu'on avance, et
    le compte des appels à la base (table:opération)."""
    import conftest
    from core.dates import logical_today_paris
    auj = logical_today_paris()
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 4, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}}}).execute()
    for i in range(60):
        fake_db.table("history").insert({
            "user_id": USER_ID, "date": (auj - dt.timedelta(days=i // 4 + 1)).isoformat(),
            "seance": "Push", "exercice": "Développé couché", "serie": i % 4 + 1,
            "reps": 8, "poids": 80.0, "remarque": "", "muscle": "Pecs", "semaine": 1}).execute()

    appels = []
    vrai = conftest.FakeQuery.execute

    def compte(self):
        appels.append(f"{self._table}:{self._op}")
        return vrai(self)

    monkeypatch.setattr(conftest.FakeQuery, "execute", compte)
    reel, decalage = time.time, [0.0]
    monkeypatch.setattr(time, "time", lambda: reel() + decalage[0])

    def serie(n, repos_s):
        decalage[0] += repos_s
        appels.clear()
        r = logged_in.post("/seance/save-exo", data={
            "_csrf": CSRF, "seance_name": "Push", "exo_base": "Développé couché",
            "variant": "Standard", "muscle": "Pecs", "date": auj.isoformat(),
            "mode": "prefaite", "name": "Push", "partiel": "1", "exo_id": EXO_ID,
            "sets_json": json.dumps([{"reps": 8, "poids": 82.5}] * n)},
            headers={"Accept": "application/json", "X-CSRFToken": CSRF})
        assert r.status_code == 200 and r.get_json()["ok"]
        return collections.Counter(appels)

    logged_in.get(f"/seance?mode=prefaite&name=Push&date={auj}")   # la page ouverte
    return serie


def test_apres_un_repos_la_serie_ne_relit_ni_historique_ni_programme(seance):
    seance(1, 0)
    for n, repos in ((2, 120), (3, 180), (4, 150)):
        c = seance(n, repos)
        assert c["programs:select"] == 0, c
        assert c["etat_compte:select"] == 0, c
        assert c["history:select"] == 1, c          # les identifiants du jour, une fois
        assert c["history:upsert"] == 1, c
        assert sum(c.values()) <= 3, c              # + au plus la relecture du profil


def test_les_series_du_jour_se_retrouvent_en_une_requete(seance):
    """Par nom ET par identifiant (exercice renommé) : une requête, pas deux."""
    c = seance(1, 0)
    assert c["history:select"] == 1, c


def test_au_dela_de_dix_minutes_tout_est_relu(seance):
    """La durée borne ce qui a pu changer HORS de l'app (éditeur SQL)."""
    seance(1, 0)
    c = seance(2, 11 * 60)
    assert c["programs:select"] == 1 and c["history:select"] == 2, c


def test_le_cache_reste_bien_plus_court_que_les_numeros_de_generation():
    """Un numéro de génération expiré revient à 0 : une entrée plus vieille que
    lui pourrait redevenir valide. Le cache doit expirer bien avant."""
    from core import db_base, partage
    assert db_base._TTL * 4 <= partage.GENERATION_TTL
    assert db_base._PROFILE_TTL <= db_base._TTL


def test_un_passage_pro_se_voit_malgre_le_cache_long(fake_db, logged_in, monkeypatch):
    """Le profil reste 10 min en cache, mais un passage PRO (webhook Stripe,
    admin) passe par _profile_upsert, qui invalide : la revérification
    suivante d'un compte gratuit (15 s) le voit."""
    import core.db as core_db
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    reel, decalage = time.time, [0.0]
    monkeypatch.setattr(time, "time", lambda: reel() + decalage[0])
    with logged_in.session_transaction() as s:
        s["is_vip_ts"] = 0
    assert "Passe en PRO" in logged_in.get("/plus").get_data(as_text=True)
    core_db.set_user_tier(USER_ID, "vip")
    decalage[0] += 20                                  # > FREE_RECHECK_TTL
    assert "Passe en PRO" not in logged_in.get("/plus").get_data(as_text=True)


def test_lexistence_du_compte_nest_plus_verifiee_a_chaque_serie(fake_db, logged_in, monkeypatch):
    """L'API auth était appelée toutes les 2 min : presque à chaque série."""
    import app as appmod
    import core.db as core_db
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    appels = []
    vrai = core_db.auth_user_exists
    monkeypatch.setattr(core_db, "auth_user_exists", lambda uid: appels.append(uid) or vrai(uid))
    reel, decalage = time.time, [0.0]
    monkeypatch.setattr(time, "time", lambda: reel() + decalage[0])
    with logged_in.session_transaction() as s:
        s["is_vip_ts"] = 0
    logged_in.get("/accueil")
    assert len(appels) == 1
    for _ in range(3):                                 # trois repos de 3 min
        decalage[0] += 180
        logged_in.get("/accueil")
    assert len(appels) == 1
    decalage[0] += appmod.AUTH_CHECK_TTL
    logged_in.get("/accueil")
    assert len(appels) == 2
