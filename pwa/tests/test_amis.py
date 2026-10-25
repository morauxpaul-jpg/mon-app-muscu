"""Amis (v52) : demandes, fil des séances terminées, encouragements.

Choix du propriétaire (25/10) : « Amis + séances visibles », visibles des
amis ACCEPTÉS seulement, gratuit pour tous. Ce qui est tenu ici :

* demander, accepter, refuser, annuler, retirer — et seul celui à qui une
  demande est adressée peut l'accepter ;
* un non-ami ne voit rien, une demande en attente non plus, un ami qui a
  masqué ses séances non plus (sans que l'amitié tombe) ;
* rien de privé ne sort : poids du corps, photos, nutrition, coach, notes
  et commentaires de séance ;
* un encouragement par personne et par séance, compté pour l'auteur ;
* la suppression du compte efface amitiés, fil et encouragements ;
* une base sans la v52 : la page le dit, la fin de séance marche.
"""
import time

import pytest

import core.db as core_db
from conftest import CSRF
from core.dates import continuous_week, logical_today_paris

AUJ = logical_today_paris()
PAUL, MARC, INCONNU = "u-paul-0001", "u-marc-0002", "u-autre-0003"
SECRETS = ("SECRET-COMMENTAIRE", "SECRET-NUTRITION", "SECRET-COACH", "SECRET-MEMOIRE", "93,7", "93.7")


def _compte(fake, uid, prenom, code):
    fake.table("profiles").insert({"id": uid, "tier": "free", "prenom": prenom,
                                   "referral_code": code, "poids_kg": 93.7,
                                   "coach_memory": "SECRET-MEMOIRE"}).execute()
    fake.table("onboarding").insert({"user_id": uid, "completed_at": "2026-01-01"}).execute()
    fake.table("programs").insert({"user_id": uid, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push"}, "_settings": {}}}).execute()


def _connecter(uid):
    import app as appmod
    appmod.app.config["TESTING"] = True
    c = appmod.app.test_client()
    with c.session_transaction() as s:
        s.update(user_id=uid, email=f"{uid}@example.com", fournisseurs=["google"], onboarded=True,
                 is_vip=False, is_vip_full=False, is_vip_ts=time.time(), auth_check_ts=time.time(),
                 _csrf=CSRF)
    return c


@pytest.fixture()
def deux(fake_db):
    _compte(fake_db, PAUL, "Paul", "paulcode")
    _compte(fake_db, MARC, "Marc", "marccode")
    _compte(fake_db, INCONNU, "Zoé", "zoezoezo")
    return _connecter(PAUL), _connecter(MARC)


def _post(c, url, **champs):
    return c.post(url, data={"_csrf": CSRF, **champs})


def _amities(fake):
    return fake.tables.get("amities", [])


def _devenir_amis(paul, marc):
    _post(marc, "/amis/demande", code="paulcode")
    demande = core_db.amities_de(PAUL)[0]
    assert _post(paul, "/amis/accepter", id=demande["id"]).status_code == 302
    return demande["id"]


def _seance(fake, client, uid, seance="Push", poids=60.0, commentaire="SECRET-COMMENTAIRE"):
    """Une séance terminée par la vraie route, avec un commentaire et une note."""
    for n in (1, 2):
        fake.table("history").insert({
            "user_id": uid, "semaine": continuous_week(AUJ), "seance": seance,
            "exercice": "Développé couché", "serie": n, "reps": 8, "poids": poids,
            "remarque": "SECRET-COMMENTAIRE", "muscle": "Pecs", "date": AUJ.isoformat()}).execute()
    core_db.vider_cache()
    r = _post(client, "/seance/finish", mode="prefaite", seance_name=seance, date=AUJ.isoformat(),
              rating="2", comment=commentaire, duration_min="47")
    assert r.status_code == 302
    return core_db.session_id_for(uid, AUJ.isoformat(), seance)


def _fil(client):
    return client.get("/amis").get_data(as_text=True)


# ── Le calcul ────────────────────────────────────────────────────


def test_le_code_se_lit_tape_ou_dans_un_lien_colle():
    from core import amis as calc
    assert calc.lire_code("ABCD2345") == "abcd2345"
    assert calc.lire_code(" abcd 2345 ") == "abcd2345"
    assert calc.lire_code("https://muscu.app/?ref=AbCd2345&ami=1") == "abcd2345"
    assert calc.lire_code("abcd") == "" and calc.lire_code("<script>") == "" and calc.lire_code(None) == ""


def test_le_nom_affiche_n_est_jamais_l_e_mail():
    from core import amis as calc
    assert calc.nom_affiche({"prenom": "  Marc  ", "display_name": "marc@gmail.com"}) == "Marc"
    assert calc.nom_affiche({}) == "Un ami"


def test_la_ligne_du_fil_ne_garde_que_le_permis():
    from core import amis as calc
    faits = {"volume": 960.4, "records": [{"exo": "Squat", "poids": 100}], "comment": "x",
             "rating": 2, "rpe_moyen": 9, "exos": {"Squat": {}}}
    ligne = calc.ligne_fil("sid", "2026-10-25", "Push", faits, 47)
    assert set(ligne) == {"session_id", "date", "seance", "duree_min", "tonnage", "records"}
    assert ligne["tonnage"] == 960 and ligne["duree_min"] == 47
    assert ligne["records"] == [{"exo": "Squat", "poids": 100.0}]


# ── Demander, accepter, refuser, annuler, retirer ────────────────


def test_une_demande_attend_l_accord_de_l_autre(deux):
    paul, marc = deux
    r = _post(marc, "/amis/demande", code="PAULCODE")
    assert r.status_code == 302 and "m=envoyee" in r.headers["Location"]
    assert "Marc" in _fil(paul) and "Demandes reçues" in _fil(paul)
    assert "En attente de réponse" in _fil(marc)
    demande = _amities(core_db.current_client())[0]
    assert demande["etat"] == "en_attente" and demande["demandeur"] == MARC

    # Celui qui demande ne peut pas accepter à la place de l'autre.
    _post(marc, "/amis/accepter", id=demande["id"])
    assert _amities(core_db.current_client())[0]["etat"] == "en_attente"
    _post(paul, "/amis/accepter", id=demande["id"])
    ligne = _amities(core_db.current_client())[0]
    assert ligne["etat"] == "acceptee" and ligne["acceptee_le"]
    assert "Mes amis · 1" in _fil(paul) and "Mes amis · 1" in _fil(marc)


def test_refuser_et_annuler_effacent_la_demande(deux):
    paul, marc = deux
    _post(marc, "/amis/demande", code="paulcode")
    demande = _amities(core_db.current_client())[0]
    _post(marc, "/amis/refuser", id=demande["id"])          # pas à lui de refuser
    assert len(_amities(core_db.current_client())) == 1
    _post(paul, "/amis/refuser", id=demande["id"])
    assert _amities(core_db.current_client()) == []

    _post(marc, "/amis/demande", code="paulcode")
    demande = _amities(core_db.current_client())[0]
    _post(paul, "/amis/annuler", id=demande["id"])          # ni à lui d'annuler
    assert len(_amities(core_db.current_client())) == 1
    _post(marc, "/amis/annuler", id=demande["id"])
    assert _amities(core_db.current_client()) == []


def test_deux_demandes_croisees_font_une_amitie(deux):
    paul, marc = deux
    _post(marc, "/amis/demande", code="paulcode")
    r = _post(paul, "/amis/demande", code="marccode")
    assert "m=acceptee" in r.headers["Location"]
    lignes = _amities(core_db.current_client())
    assert len(lignes) == 1 and lignes[0]["etat"] == "acceptee"


def test_la_paire_est_unique_dans_les_deux_sens(deux):
    """Deux demandes simultanées : la seconde insertion échoue (index unique
    sur la paire), `demander` relit et accepte celle de l'autre."""
    fake = core_db.current_client()
    fake.table("amities").insert({"demandeur": MARC, "destinataire": PAUL, "etat": "en_attente"}).execute()
    with pytest.raises(Exception, match="23505"):
        fake.table("amities").insert({"demandeur": PAUL, "destinataire": MARC, "etat": "en_attente"}).execute()


def test_codes_refuses(deux):
    paul, _marc = deux
    assert "m=inconnu" in _post(paul, "/amis/demande", code="zzzzzzzz").headers["Location"]
    assert "m=inconnu" in _post(paul, "/amis/demande", code="pas un code").headers["Location"]
    assert "m=soi_meme" in _post(paul, "/amis/demande", code="paulcode").headers["Location"]
    assert _amities(core_db.current_client()) == []


def test_retirer_un_ami_vaut_des_deux_cotes_tout_de_suite(deux):
    paul, marc = deux
    amitie = _devenir_amis(paul, marc)
    _seance(core_db.current_client(), marc, MARC)
    _seance(core_db.current_client(), paul, PAUL, seance="Legs")
    assert "PUSH" in _fil(paul).upper() and "LEGS" in _fil(marc).upper()

    _post(paul, "/amis/retirer", id=amitie)                 # Paul avait accepté : il peut retirer
    assert _amities(core_db.current_client()) == []
    assert f's-{core_db.session_id_for(MARC, AUJ.isoformat(), "Push")}' not in _fil(paul)
    assert f's-{core_db.session_id_for(PAUL, AUJ.isoformat(), "Legs")}' not in _fil(marc)


def test_le_demandeur_peut_aussi_retirer(deux):
    paul, marc = deux
    amitie = _devenir_amis(paul, marc)
    _post(marc, "/amis/retirer", id=amitie)
    assert _amities(core_db.current_client()) == []


# ── Qui voit quoi ────────────────────────────────────────────────


def test_un_non_ami_ne_voit_rien(deux):
    paul, marc = deux
    sid = _seance(core_db.current_client(), marc, MARC)
    assert f"s-{sid}" not in _fil(paul)
    # Une demande en attente ne suffit pas.
    _post(paul, "/amis/demande", code="marccode")
    assert f"s-{sid}" not in _fil(paul)
    assert core_db.visibles_par(PAUL) == []
    # Ni la page, ni l'encouragement : 404 comme une séance qui n'existe pas.
    assert _post(paul, "/amis/encourager", compte=MARC, session=sid).status_code == 404
    assert core_db.current_client().tables.get("encouragements", []) == []


def test_un_ami_accepte_voit_la_seance_terminee(deux):
    paul, marc = deux
    _devenir_amis(paul, marc)
    sid = _seance(core_db.current_client(), marc, MARC, poids=60.0)
    html = _fil(paul)
    assert f"s-{sid}" in html
    carte = html[html.index(f"s-{sid}"):]
    carte = carte[:carte.index("</article>")]
    assert "Marc" in carte and "Push" in carte and "47</b> min" in carte
    assert "960</b> kg" in carte and "Développé couché · 60 kg" in carte   # 2 × 8 × 60, premier record


def test_masquer_ses_seances_cache_tout_sans_retirer_l_ami(deux):
    paul, marc = deux
    _devenir_amis(paul, marc)
    sid = _seance(core_db.current_client(), marc, MARC)
    assert _post(marc, "/amis/masquer", masquer="1").status_code == 302
    assert "Montrer mes séances" in _fil(marc)
    assert f"s-{sid}" not in _fil(paul)
    assert _post(paul, "/amis/encourager", compte=MARC, session=sid).status_code == 404
    assert _amities(core_db.current_client())[0]["etat"] == "acceptee"
    assert f"s-{sid}" in _fil(marc)                           # lui voit toujours les siennes
    _post(marc, "/amis/masquer", masquer="0")
    assert f"s-{sid}" in _fil(paul)


def test_rien_de_prive_ne_sort(deux):
    paul, marc = deux
    _devenir_amis(paul, marc)
    fake = core_db.current_client()
    fake.table("body_weight").insert({"user_id": MARC, "date": AUJ.isoformat(), "poids_kg": 93.7}).execute()
    fake.table("nutrition").insert({"user_id": MARC, "date": AUJ.isoformat(), "meal_type": "diner",
                                    "calories": 900, "protein": 50, "carbs": 80, "fat": 30,
                                    "note": "SECRET-NUTRITION"}).execute()
    fake.table("coach_messages").insert({"user_id": MARC, "role": "user", "content": "SECRET-COACH"}).execute()
    fake.table("photos_corps").insert({"user_id": MARC, "date": AUJ.isoformat(), "angle": "face",
                                       "chemin": f"{MARC}/x.jpg", "miniature": f"{MARC}/x_m.jpg",
                                       "octets": 10}).execute()
    sid = _seance(fake, marc, MARC)
    html = _fil(paul)
    assert f"s-{sid}" in html
    for secret in SECRETS + (f"{MARC}/x.jpg", "/progres/photos/", "marc@example.com"):
        assert secret not in html, secret
    # Le fil ne garde que le permis : pas de note, pas de commentaire.
    ligne = fake.tables["fil_seances"][0]
    assert set(ligne) <= {"id", "user_id", "session_id", "date", "seance", "duree_min",
                          "tonnage", "records", "created_at"}
    assert "SECRET" not in repr(ligne) and "rating" not in ligne and "comment" not in ligne


def test_le_compteur_d_encouragements_n_est_que_pour_l_auteur(deux):
    paul, marc = deux
    _devenir_amis(paul, marc)
    sid = _seance(core_db.current_client(), marc, MARC)
    assert "Pas encore d&#39;encouragement" in _fil(marc) or "Pas encore d'encouragement" in _fil(marc)
    r = _post(paul, "/amis/encourager", compte=MARC, session=sid)
    assert r.status_code == 302 and r.headers["Location"].endswith(f"#s-{sid}")
    # Un seul par personne et par séance.
    _post(paul, "/amis/encourager", compte=MARC, session=sid)
    assert len(core_db.current_client().tables["encouragements"]) == 1
    assert "<b>1</b> encouragement" in _fil(marc)
    carte = _fil(paul)[_fil(paul).index(f"s-{sid}"):]
    assert "Encouragé" in carte[:carte.index("</article>")]
    assert "encouragement" not in carte[:carte.index("</article>")]   # Paul ne voit pas le compteur
    # Sa propre séance ne s'encourage pas.
    assert _post(marc, "/amis/encourager", compte=MARC, session=sid).status_code == 404


def test_une_seance_effacee_sort_du_fil(deux):
    paul, marc = deux
    _devenir_amis(paul, marc)
    sid = _seance(core_db.current_client(), marc, MARC)
    _post(paul, "/amis/encourager", compte=MARC, session=sid)
    _post(marc, "/seance/reset-session", seance_name="Push", date=AUJ.isoformat(), mode="prefaite")
    assert f"s-{sid}" not in _fil(paul)
    assert core_db.current_client().tables["encouragements"] == []


def test_terminer_deux_fois_ne_double_pas(deux):
    _paul, marc = deux
    _seance(core_db.current_client(), marc, MARC)
    _post(marc, "/seance/finish", mode="prefaite", seance_name="Push", date=AUJ.isoformat())
    assert len(core_db.current_client().tables["fil_seances"]) == 1


def test_une_seance_vide_n_entre_pas_dans_le_fil(deux):
    _paul, marc = deux
    _post(marc, "/seance/finish", mode="prefaite", seance_name="Push", date=AUJ.isoformat())
    assert core_db.current_client().tables.get("fil_seances", []) == []


# ── Lien d'ami et inscription ────────────────────────────────────


def test_le_lien_d_ami_passe_par_le_parrainage(client, fake_db):
    r = client.get("/?ref=paulcode&ami=1")
    cookies = r.headers.getlist("Set-Cookie")
    assert any(c.startswith("pending_ref=paulcode") for c in cookies)
    assert any(c.startswith("pending_ami=paulcode") for c in cookies)
    # Le lien de parrainage seul n'envoie pas de demande d'ami.
    assert not any(c.startswith("pending_ami") for c in client.get("/?ref=paulcode").headers.getlist("Set-Cookie"))


def test_deja_connecte_le_lien_propose_la_demande(deux):
    paul, marc = deux
    r = marc.get("/?ref=paulcode&ami=1")
    assert r.status_code == 302 and "/amis?code=paulcode" in r.headers["Location"]
    html = marc.get("/amis?code=paulcode").get_data(as_text=True)
    assert "Envoyer une demande à Paul" in html
    assert _amities(core_db.current_client()) == []           # rien n'est envoyé sans le geste


def test_l_inscription_par_un_lien_d_ami_envoie_la_demande(fake_db):
    _compte(fake_db, PAUL, "Paul", "paulcode")
    nouveau = _connecter(MARC)
    with nouveau.session_transaction() as s:
        s["onboarded"] = False
    nouveau.set_cookie("pending_ami", "paulcode")
    nouveau.set_cookie("pending_ref", "paulcode")
    r = nouveau.post("/onboarding/submit", data={
        "_csrf": CSRF, "prenom": "Marc", "age": "30", "sexe": "homme", "poids_kg": "72.5",
        "taille_cm": "178", "niveau": "débutant", "frequence": "3", "objectif": "prise de masse",
        "equipement": "salle", "programme_id": "", "equipment_details": "[]"})
    assert r.status_code == 302 and "/amis" in r.headers["Location"]
    lignes = _amities(fake_db)
    assert len(lignes) == 1 and lignes[0]["demandeur"] == MARC and lignes[0]["destinataire"] == PAUL
    assert lignes[0]["etat"] == "en_attente"                  # Paul accepte ou non


def test_un_compte_deja_inscrit_arrive_sur_l_invitation_apres_connexion(deux):
    _paul, marc = deux
    marc.set_cookie("pending_ami", "paulcode")
    r = marc.get("/accueil", headers={"Sec-Fetch-Mode": "navigate"})
    assert r.status_code == 302 and r.headers["Location"].endswith("/amis")
    r = marc.get("/amis", headers={"Sec-Fetch-Mode": "navigate"})
    assert "Envoyer une demande à Paul" in r.get_data(as_text=True)
    assert any(c.startswith("pending_ami=;") for c in r.headers.getlist("Set-Cookie"))


# ── Compte, données, base en retard ──────────────────────────────


def test_la_suppression_du_compte_nettoie_amis_fil_et_encouragements(deux, monkeypatch):
    paul, marc = deux
    _devenir_amis(paul, marc)
    sid_marc = _seance(core_db.current_client(), marc, MARC)
    sid_paul = _seance(core_db.current_client(), paul, PAUL, seance="Legs")
    _post(paul, "/amis/encourager", compte=MARC, session=sid_marc)
    _post(marc, "/amis/encourager", compte=PAUL, session=sid_paul)
    _post(_connecter(INCONNU), "/amis/demande", code="marccode")
    from core import stripe_client
    monkeypatch.setattr(stripe_client, "resilier_avant_suppression", lambda *_a: None)
    monkeypatch.setattr(stripe_client, "client", lambda: None)

    assert _post(marc, "/gestion/delete-account", confirm="yes").status_code == 302
    fake = core_db.current_client()
    assert [a for a in _amities(fake) if MARC in (a["demandeur"], a["destinataire"])] == []
    assert [e for e in fake.tables["encouragements"] if MARC in (e["auteur"], e["destinataire"])] == []
    assert [f for f in fake.tables["fil_seances"] if f["user_id"] == MARC] == []
    assert [f["user_id"] for f in fake.tables["fil_seances"]] == [PAUL]   # l'autre garde les siens


def test_la_remise_a_zero_vide_le_fil(deux):
    _paul, marc = deux
    _seance(core_db.current_client(), marc, MARC)
    _post(marc, "/gestion/reset-total", confirm="yes")
    assert core_db.current_client().tables["fil_seances"] == []


def test_l_export_contient_les_amis_sans_les_identifiants_des_autres(deux):
    import json
    paul, marc = deux
    _devenir_amis(paul, marc)
    _seance(core_db.current_client(), marc, MARC)
    donnees = json.loads(marc.get("/gestion/export").get_data(as_text=True))
    assert [a["nom"] for a in donnees["amis"]["amis"]] == ["Paul"]
    assert donnees["amis"]["fil_seances"][0]["seance"] == "Push"
    assert PAUL not in json.dumps(donnees["amis"])
    _post(marc, "/amis/masquer", masquer="1")
    donnees = json.loads(marc.get("/gestion/export").get_data(as_text=True))
    assert donnees["profil"]["seances_masquees"] is True


def test_sans_la_v52_la_page_attend_et_la_seance_se_termine(deux):
    paul, marc = deux
    fake = core_db.current_client()

    def refuser_tables(table, _vrai=fake.table):
        if table in ("amities", "fil_seances", "encouragements"):
            raise Exception("{'code': '42P01', 'message': 'relation \"public.%s\" does not exist'}" % table)
        return _vrai(table)
    fake.table = refuser_tables
    assert "Les amis arrivent bientôt" in _fil(paul)
    _seance(fake, marc, MARC)                                  # 302 : la fin de séance marche
    from core import schema
    assert "amities" in schema.etat()["absentes"] or "fil_seances" in schema.etat()["absentes"]


def test_le_controle_du_schema_connait_les_tables_v52():
    from core.schema import ATTENDU
    assert {"amities", "fil_seances", "encouragements"} <= set(ATTENDU)
    assert "seances_masquees" in ATTENDU["profiles"]


def test_les_demandes_sont_limitees(deux):
    from core.limiter import limiter
    paul, _marc = deux
    codes = [_post(paul, "/amis/demande", code="zzzzzzzz").status_code for _ in range(21)]
    assert codes[:20] == [302] * 20 and codes[20] == 429


def test_les_encouragements_sont_limites(deux):
    paul, _marc = deux
    codes = [_post(paul, "/amis/encourager", compte=MARC, session="x").status_code for _ in range(61)]
    assert codes[-1] == 429 and 429 not in codes[:60]


def test_un_identifiant_de_seance_mal_forme_est_refuse_sans_requete(deux):
    paul, marc = deux
    _devenir_amis(paul, marc)
    assert _post(paul, "/amis/encourager", compte=MARC, session="pas-un-uuid").status_code == 404


def test_la_page_est_ouverte_aux_comptes_gratuits(deux):
    paul, _marc = deux
    r = paul.get("/amis")
    assert r.status_code == 200 and "Ajouter un ami" in r.get_data(as_text=True)
    assert "PAULCODE" in r.get_data(as_text=True)


def test_la_limite_compte_par_compte_et_pas_par_adresse(deux):
    """En salle, plusieurs personnes partagent la même adresse IP : la
    limite d'un compte ne doit pas bloquer le voisin."""
    paul, marc = deux
    assert [_post(paul, "/amis/demande", code="zzzzzzzz").status_code for _ in range(21)][-1] == 429
    assert _post(marc, "/amis/demande", code="zzzzzzzz").status_code == 302
