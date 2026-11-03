"""Notifications push entre amis (choix du 03/11) : demande reçue, invitation
à un défi, ami qui vous dépasse, encouragement.

Ce qui est tenu ici :
* chaque événement prévient la bonne personne, et elle seule ;
* « t'a dépassé » : seulement si la séance fait passer devant, une fois par
  jour et par défi ; un encouragement, une notification par séance ;
* actives par défaut pour qui a un abonnement push, coupées par le réglage
  « Notifications des amis » ; rien sans abonnement ; un abonnement mort est
  effacé ; une panne d'envoi ne fait jamais échouer la route ;
* sans la v54, les réglages se lisent et s'écrivent sans la colonne.
"""
import datetime as dt

import pytest

import core.db as core_db
from core import push_amis
from core.dates import logical_today_paris
from test_amis import INCONNU, MARC, PAUL, _compte, _connecter, _devenir_amis, _post, _seance
from test_defis import _lancer

AUJ = logical_today_paris()


@pytest.fixture()
def envois(monkeypatch):
    """Les notifications parties : [(compte, titre, corps, url)]. L'envoi est
    rendu synchrone (en production il part en tâche de fond)."""
    from core import push

    class Envois(list):
        par_endpoint: dict
    parties = Envois()
    par_endpoint = {}

    def faux_envoi(sub, payload, ttl=0, urgence=""):
        parties.append((par_endpoint[sub["endpoint"]], payload["title"], payload["body"], payload["url"]))
        return "ok"
    monkeypatch.setattr(push, "send_push", faux_envoi)
    monkeypatch.setattr(push_amis, "_en_fond", lambda travail: travail())
    parties.par_endpoint = par_endpoint
    return parties


@pytest.fixture()
def trois(fake_db, envois):
    for uid, prenom, code in ((PAUL, "Paul", "paulcode"), (MARC, "Marc", "marccode"),
                              (INCONNU, "Zoé", "zoezoezo")):
        _compte(fake_db, uid, prenom, code)
        _abonner(fake_db, envois, uid)
    return _connecter(PAUL), _connecter(MARC), _connecter(INCONNU)


def _abonner(fake, envois, uid):
    endpoint = f"https://push.example/{uid}"
    envois.par_endpoint[endpoint] = uid
    fake.table("push_subscriptions").insert({"user_id": uid, "endpoint": endpoint,
                                             "p256dh": "p", "auth": "a"}).execute()


def _pour(envois, uid):
    return [(t, c, u) for qui, t, c, u in envois if qui == uid]


def _amis(a, b, code_b, uid_a):
    """`a` (compte uid_a) demande `b` ; b accepte."""
    _post(a, "/amis/demande", code=code_b)
    demande = next(x for x in core_db.amities_de(uid_a) if x["etat"] == "en_attente")
    _post(b, "/amis/accepter", id=demande["id"])


# ── Les quatre événements ────────────────────────────────────────


def test_une_demande_d_ami_previent_celui_qui_la_recoit(trois, envois):
    paul, marc, _zoe = trois
    _post(marc, "/amis/demande", code="paulcode")
    assert _pour(envois, PAUL) == [("Demande d'ami", "Marc veut devenir ton ami.", "/amis")]
    assert _pour(envois, MARC) == []
    _post(paul, "/amis/demande", code="zzzzzzzz")                  # code inconnu : personne
    _post(marc, "/amis/demande", code="paulcode")                  # déjà envoyée : rien de plus
    assert len(envois) == 1


def test_une_invitation_a_un_defi_previent_les_invites(trois, envois):
    paul, marc, zoe = trois
    _devenir_amis(paul, marc)
    _amis(zoe, paul, "paulcode", INCONNU)
    envois.clear()
    _lancer(paul, MARC, type_="volume", semaines="2", depart="demain")
    assert _pour(envois, MARC) == [("Nouveau défi", "Paul te lance un défi Volume sur 2 semaines.",
                                    "/amis#defis")]
    assert _pour(envois, PAUL) == [] and _pour(envois, INCONNU) == []
    # « Inviter d'autres amis » : seulement le nouvel invité.
    (d,) = core_db.current_client().tables["defis"]
    _post(paul, "/amis/defis/inviter", defi=d["id"], amis=INCONNU)
    assert _pour(envois, INCONNU) == [("Nouveau défi", "Paul te lance un défi Volume sur 2 semaines.",
                                       "/amis#defis")]
    assert len(_pour(envois, MARC)) == 1
    # Un non-ami refusé : aucun défi, aucune notification.
    envois.clear()
    _lancer(marc, INCONNU)
    assert envois == []


def test_un_ami_qui_te_depasse_te_previent_une_fois_par_jour(trois, envois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    _lancer(paul, MARC, type_="regularite", depart="aujourdhui")
    (d,) = core_db.current_client().tables["defis"]
    _post(marc, "/amis/defis/accepter", defi=d["id"])
    envois.clear()
    _seance(core_db.current_client(), marc, MARC)                  # 0 = 0 avant, 1 > 0 après
    assert _pour(envois, PAUL) == [("Tu t'es fait dépasser", "Marc t'a dépassé au défi Régularité.",
                                    "/amis#defis")]
    assert _pour(envois, MARC) == []
    # Une seconde séance le même jour : déjà prévenu aujourd'hui pour ce défi.
    _seance(core_db.current_client(), marc, MARC, seance="Legs")
    assert len(_pour(envois, PAUL)) == 1
    # Marc a 2 séances. Paul en fait 1, puis 2 (égalité) : pas encore ; à 3,
    # il passe devant et Marc est prévenu à son tour.
    _seance(core_db.current_client(), paul, PAUL)
    _seance(core_db.current_client(), paul, PAUL, seance="Legs")
    assert _pour(envois, MARC) == []
    _seance(core_db.current_client(), paul, PAUL, seance="Pull")
    assert _pour(envois, MARC) == [("Tu t'es fait dépasser", "Paul t'a dépassé au défi Régularité.",
                                    "/amis#defis")]


def test_le_calcul_du_depassement():
    defi = {"id": 1, "type": "volume", "debut": str(AUJ - dt.timedelta(days=2)), "semaines": 1,
            "fin": str(AUJ + dt.timedelta(days=4))}
    parts = [{"user_id": u, "etat": "acceptee"} for u in ("moi", "a", "b", "c")] \
        + [{"user_id": "d", "etat": "invite"}]

    def l(uid, kg, seance="Push", jour=0):
        return {"user_id": uid, "date": str(AUJ - dt.timedelta(days=jour)), "seance": seance,
                "exercice": "Squat", "reps": 1, "poids": kg}
    lignes = {"moi": [l("moi", 100, jour=1), l("moi", 100)],          # 100 avant, 200 après
              "a": [l("a", 150)],                                     # dépassé
              "b": [l("b", 100)],                                     # égalité avant : dépassé
              "c": [l("c", 50)],                                      # déjà derrière : rien
              "d": [l("d", 120)]}                                     # pas accepté : rien
    assert push_amis.depasses(defi, parts, lignes, "moi", AUJ.isoformat(), "Push", AUJ) == ["a", "b"]
    lignes["a"] = [l("a", 200)]                                       # égalité après : pas dépassé
    assert push_amis.depasses(defi, parts, lignes, "moi", AUJ.isoformat(), "Push", AUJ) == ["b"]
    # Une séance qui ne compte pas dans ce défi ne dépasse personne.
    assert push_amis.depasses(defi, parts, lignes, "moi", AUJ.isoformat(), "Autre", AUJ) == []


def test_un_encouragement_previent_une_fois_par_seance(trois, envois):
    paul, marc, zoe = trois
    _devenir_amis(paul, marc)
    _amis(zoe, marc, "marccode", INCONNU)
    sid = _seance(core_db.current_client(), marc, MARC)
    envois.clear()
    _post(paul, "/amis/encourager", compte=MARC, session=sid)
    assert _pour(envois, MARC) == [("Encouragement", "Paul t'a encouragé pour ta séance.", "/amis")]
    _post(zoe, "/amis/encourager", compte=MARC, session=sid)          # second encouragement, même séance
    assert len(_pour(envois, MARC)) == 1
    assert len(core_db.current_client().tables["encouragements"]) == 2   # compté quand même


# ── Le réglage, l'abonnement, les pannes ─────────────────────────


def test_le_reglage_coupe_les_notifications_des_amis(trois, envois, logged_in):
    paul, marc, _zoe = trois
    page = paul.get("/gestion").get_data(as_text=True)
    assert 'name="notifs_amis" checked' in page                      # actif par défaut
    _post(paul, "/gestion/settings", auto_rest_timer="on")           # interrupteur décoché
    assert core_db.lire_reglages(PAUL)["notifs_amis"] is False
    assert 'name="notifs_amis" checked' not in paul.get("/gestion").get_data(as_text=True)
    _post(marc, "/amis/demande", code="paulcode")
    assert envois == []
    _post(paul, "/gestion/settings", notifs_amis="on")
    _post(marc, "/amis/annuler", id=core_db.amities_de(MARC)[0]["id"])
    _post(marc, "/amis/demande", code="paulcode")
    assert len(_pour(envois, PAUL)) == 1


def test_rien_sans_abonnement_et_un_abonnement_mort_est_efface(fake_db, envois, monkeypatch):
    from core import push
    _compte(fake_db, PAUL, "Paul", "paulcode")
    _compte(fake_db, MARC, "Marc", "marccode")
    _post(_connecter(MARC), "/amis/demande", code="paulcode")        # Paul n'a pas d'abonnement
    assert envois == []
    _abonner(fake_db, envois, PAUL)
    monkeypatch.setattr(push, "send_push", lambda *a, **k: "expired")
    _post(_connecter(MARC), "/amis/annuler", id=core_db.amities_de(MARC)[0]["id"])
    _post(_connecter(MARC), "/amis/demande", code="paulcode")
    assert fake_db.tables["push_subscriptions"] == []


def test_une_panne_d_envoi_ne_fait_pas_echouer_la_route(trois, monkeypatch):
    from core import push
    _paul, marc, _zoe = trois

    def panne(*_a, **_k):
        raise RuntimeError("service de push indisponible")
    monkeypatch.setattr(push, "send_push", panne)
    r = _post(marc, "/amis/demande", code="paulcode")
    assert r.status_code == 302 and "m=envoyee" in r.headers["Location"]


def test_l_envoi_ne_bloque_pas_la_route(trois, monkeypatch):
    """En production, la route rend la main avant l'envoi."""
    _paul, marc, _zoe = trois
    en_attente = []
    monkeypatch.setattr(push_amis, "_en_fond", en_attente.append)
    assert _post(marc, "/amis/demande", code="paulcode").status_code == 302
    assert len(en_attente) == 1


def test_sans_la_v54_les_reglages_marchent_sans_la_colonne(fake_db, logged_in, monkeypatch):
    from conftest import CSRF, USER_ID
    from core import schema
    colonnes = tuple(c for c in schema.ATTENDU["reglages"] if c != "notifs_amis")
    monkeypatch.setitem(schema.ATTENDU, "reglages", colonnes)       # la fausse base refuse la colonne
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {"_settings": {}}}).execute()
    fake_db.table("reglages").insert({"user_id": USER_ID, "reminder_hour": 7, "auto_rest_timer": True,
                                      "auto_prefill_weight": True, "show_rpe": True,
                                      "show_overload_hint": True, "notifications": True,
                                      "recap_hebdo": True}).execute()
    assert core_db.lire_reglages(USER_ID)["reminder_hour"] == 7      # la ligne sert toujours
    assert core_db.lire_reglages(USER_ID)["notifs_amis"] is True     # défaut
    r = logged_in.post("/gestion/settings", data={"_csrf": CSRF, "reminder_hour": "9",
                                                  "notifications": "on"})
    assert r.status_code in (200, 302)
    assert fake_db.tables["reglages"][0]["reminder_hour"] == 9
    assert "notifs_amis" in schema.etat()["absentes"].get("reglages", [])
