"""Défis entre amis (v53) : lancer, inviter, accepter, refuser, classer.

Choix du propriétaire (26/10) : « Défis entre amis », gratuit pour tous.
Ce qui est tenu ici :

* trois types calculés depuis l'historique (régularité, volume,
  progression sur un exercice), trois durées, le score jamais stocké ;
* la référence de la progression : la meilleure charge des 28 jours avant
  le début ; sans elle, classé à part et jamais gagnant ;
* les égalités (rang partagé, gagnants ensemble), la fin du défi et son
  résultat dans le fil ;
* on n'invite que ses amis acceptés ; un non-participant ne voit rien ;
  un participant qui n'est plus l'ami du créateur sort du défi ;
* un ami aux séances masquées reste classé, sans aucun détail ;
* la suppression du compte, l'export, la base sans la v53, les limites.
"""
import datetime as dt
import json

import pytest

import core.db as core_db
from core import defis as calc
from core.dates import continuous_week, logical_today_paris
from test_amis import INCONNU, MARC, PAUL, _compte, _connecter, _devenir_amis, _post, _seance

AUJ = logical_today_paris()
J = dt.timedelta(days=1)


@pytest.fixture()
def trois(fake_db):
    _compte(fake_db, PAUL, "Paul", "paulcode")
    _compte(fake_db, MARC, "Marc", "marccode")
    _compte(fake_db, INCONNU, "Zoé", "zoezoezo")
    return _connecter(PAUL), _connecter(MARC), _connecter(INCONNU)


def _defis(fake=None):
    return (fake or core_db.current_client()).tables.get("defis", [])


def _participants(fake=None):
    return (fake or core_db.current_client()).tables.get("defis_participants", [])


def _lancer(client, *amis, type_="regularite", semaines="2", depart="aujourdhui", **autres):
    return client.post("/amis/defis/lancer", data={"_csrf": "test-csrf-token", "type": type_,
                                                   "semaines": semaines, "depart": depart,
                                                   "amis": list(amis), **autres})


def _page(client):
    return client.get("/amis").get_data(as_text=True)


def _carte(html, defi_id):
    debut = html.index(f'id="defi-{defi_id}"')
    return html[debut:html.index("</article>", debut)]


def _ligne(uid, date, exo="Développé couché", reps=8, poids=60.0, seance="Push", **autres):
    return {"user_id": uid, "date": str(date), "seance": seance, "exercice": exo,
            "reps": reps, "poids": poids, **autres}


def _defi(type_="regularite", debut=AUJ, semaines=1, exercice=None):
    return {"id": 1, "createur": PAUL, "type": type_, "exercice": exercice, "semaines": semaines,
            "debut": str(debut), "fin": str(debut + dt.timedelta(days=7 * semaines - 1))}


def _inserer_defi(fake, debut, semaines=1, type_="regularite", invites=(), acceptes=(MARC,),
                  createur=PAUL, exercice=None):
    """Un défi posé directement en base, daté à volonté (fin passée, début passé)."""
    d = fake.table("defis").insert({
        "createur": createur, "type": type_, "exercice": exercice, "semaines": semaines,
        "debut": str(debut), "fin": str(debut + dt.timedelta(days=7 * semaines - 1))}).execute().data[0]
    for uid in (createur, *acceptes):
        fake.table("defis_participants").insert({"defi_id": d["id"], "user_id": uid, "etat": "acceptee",
                                                 "repondu_le": "2026-01-01T00:00:00+00:00"}).execute()
    for uid in invites:
        fake.table("defis_participants").insert({"defi_id": d["id"], "user_id": uid, "etat": "invite",
                                                 "repondu_le": None}).execute()
    return d["id"]


def _serie(fake, uid, date, poids=60.0, reps=8, seance="Push", exo="Développé couché", n=1):
    fake.table("history").insert({
        "user_id": uid, "semaine": continuous_week(date), "seance": seance, "exercice": exo,
        "serie": n, "reps": reps, "poids": poids, "remarque": "", "muscle": "Pecs",
        "date": date.isoformat()}).execute()
    core_db.vider_cache()


# ── Le calcul ────────────────────────────────────────────────────


def test_les_bornes_suivent_la_duree_et_le_depart():
    lundi = dt.date(2026, 10, 26)
    assert calc.bornes("aujourdhui", 1, lundi) == (lundi, dt.date(2026, 11, 1))
    assert calc.bornes("demain", 2, lundi) == (dt.date(2026, 10, 27), dt.date(2026, 11, 9))
    # « Lundi prochain » un lundi : le suivant, pas aujourd'hui.
    assert calc.bornes("lundi", 4, lundi) == (dt.date(2026, 11, 2), dt.date(2026, 11, 29))
    assert calc.bornes("lundi", 1, dt.date(2026, 11, 1))[0] == dt.date(2026, 11, 2)


def test_la_regularite_compte_les_seances_du_defi_cardio_compris():
    d = _defi("regularite", debut=AUJ - 3 * J)
    lignes = [_ligne(PAUL, AUJ - 4 * J),                                  # avant le début
              _ligne(PAUL, AUJ - 3 * J), _ligne(PAUL, AUJ - 3 * J),       # une séance, deux séries
              _ligne(PAUL, AUJ - 3 * J, seance="Push · 2"),              # seconde passe le même jour
              _ligne(PAUL, AUJ - J, exo="CARDIO:Course", reps=0, poids=0, duree_min=30, seance="Cardio"),
              _ligne(PAUL, AUJ, exo="SESSION", reps=0, poids=0, seance="Legs")]   # marqueur : rien
    s = calc.score(d, lignes, AUJ)
    assert s["valeur"] == 3 and s["texte"] == "3 séances"


def test_le_volume_ne_compte_ni_cardio_ni_echauffement():
    d = _defi("volume", debut=AUJ - 2 * J)
    lignes = [_ligne(PAUL, AUJ - 2 * J, reps=10, poids=100),                     # 1 000
              _ligne(PAUL, AUJ - J, reps=5, poids=40, type_serie="echauffement"),
              _ligne(PAUL, AUJ - J, exo="CARDIO:Vélo", reps=20, poids=12),
              _ligne(PAUL, AUJ - J, exo="Pompes", reps=20, poids=0),
              _ligne(PAUL, AUJ - 3 * J, reps=10, poids=100)]                     # avant le début
    s = calc.score(d, lignes, AUJ)
    assert s["valeur"] == 1000 and s["texte"] == "1 000 kg" and s["seances"] == 2


def test_la_progression_part_des_28_jours_avant_le_debut():
    debut = AUJ - 2 * J
    d = _defi("progression", debut=debut, exercice="Développé couché")
    lignes = [_ligne(PAUL, debut - 29 * J, poids=200),          # hors référence : trop tôt
              _ligne(PAUL, debut - 28 * J, poids=80),           # premier jour de la référence
              _ligne(PAUL, debut - J, poids=75, reps=3),
              _ligne(PAUL, debut, exo="Développé couché (Barre)", poids=85, reps=1),   # matériel : même mouvement
              _ligne(PAUL, debut, exo="Développé incliné", poids=120)]                  # autre exercice
    s = calc.score(d, lignes, AUJ)
    assert s["valeur"] == 6.2 and s["texte"] == "+6,2 %"          # (85 − 80) / 80 = 6,25 → 6,2


def test_la_progression_sans_reference_est_classee_a_part():
    debut = AUJ - J
    d = _defi("progression", debut=debut, exercice="Squat")
    sans = calc.score(d, [_ligne(PAUL, debut, exo="Squat", poids=100)], AUJ)
    assert sans == {"valeur": None, "texte": "Pas de référence", "seances": 1}
    # Au poids du corps (0 kg) : pas de charge de référence non plus.
    assert calc.score(d, [_ligne(PAUL, debut - J, exo="Squat", poids=0, reps=20)], AUJ)["valeur"] is None
    # Une référence, mais l'exercice pas encore refait.
    pas_encore = calc.score(d, [_ligne(PAUL, debut - 5 * J, exo="Squat", poids=100)], AUJ)
    assert pas_encore["valeur"] is None and pas_encore["texte"] == "Pas encore fait"
    # Une baisse se dit avec le signe moins.
    baisse = calc.score(d, [_ligne(PAUL, debut - 5 * J, exo="Squat", poids=100),
                            _ligne(PAUL, debut, exo="Squat", poids=95)], AUJ)
    assert baisse["valeur"] == -5.0 and baisse["texte"] == "−5 %"


def test_les_egalites_partagent_le_rang_et_la_victoire():
    d = _defi("regularite", debut=AUJ - 7 * J)
    d["fin"] = str(AUJ - J)
    lignes = {PAUL: [_ligne(PAUL, AUJ - 6 * J), _ligne(PAUL, AUJ - 5 * J)],
              MARC: [_ligne(MARC, AUJ - 6 * J), _ligne(MARC, AUJ - 2 * J)],
              INCONNU: [_ligne(INCONNU, AUJ - 3 * J)]}
    parts = [{"user_id": u, "etat": "acceptee"} for u in (PAUL, MARC, INCONNU)]
    profils = {MARC: {"prenom": "Marc"}, INCONNU: {"prenom": "Zoé"}}
    cl = calc.classement(d, parts, lignes, profils, PAUL, AUJ)
    assert [(l["nom"], l["rang"], l["valeur"]) for l in cl] == [("Marc", 1, 2), ("Toi", 1, 2), ("Zoé", 3, 1)]
    assert calc.annonce(d, cl) == "Égalité entre Marc et toi : 2 séances chacun."
    sans_marc = {**lignes, MARC: []}
    assert calc.annonce(d, calc.classement(d, parts, sans_marc, profils, PAUL, AUJ)) == "Tu gagnes avec 2 séances."
    vu_par_marc = calc.classement(d, parts, sans_marc, {**profils, PAUL: {"prenom": "Paul"}}, MARC, AUJ)
    assert calc.annonce(d, vu_par_marc) == "Paul gagne avec 2 séances."


def test_sans_point_marque_il_n_y_a_pas_de_gagnant():
    d = _defi("volume", debut=AUJ - 7 * J)
    parts = [{"user_id": u, "etat": "acceptee"} for u in (PAUL, MARC)]
    cl = calc.classement(d, parts, {}, {MARC: {"prenom": "Marc"}}, PAUL, AUJ)
    assert [l["rang"] for l in cl] == [1, 1] and calc.gagnants(cl) == []
    assert calc.annonce(d, cl) == "Pas de gagnant : personne n'a marqué de point."


def test_sans_reference_on_ne_gagne_pas_et_on_est_classe_apres():
    debut = AUJ - 3 * J
    d = _defi("progression", debut=debut, exercice="Squat")
    lignes = {PAUL: [_ligne(PAUL, debut - J, exo="Squat", poids=100), _ligne(PAUL, debut, exo="Squat", poids=102)],
              MARC: [_ligne(MARC, debut, exo="Squat", poids=180)]}
    parts = [{"user_id": u, "etat": "acceptee"} for u in (PAUL, MARC)]
    cl = calc.classement(d, parts, lignes, {MARC: {"prenom": "Marc"}}, PAUL, AUJ)
    assert [(l["nom"], l["rang"], l["texte"]) for l in cl] == [("Toi", 1, "+2 %"), ("Marc", None, "Pas de référence")]
    assert [l["nom"] for l in calc.gagnants(cl)] == ["Toi"]


def test_un_ami_masque_garde_son_score_sans_detail():
    d = _defi("volume", debut=AUJ)
    lignes = {MARC: [_ligne(MARC, AUJ)], PAUL: [_ligne(PAUL, AUJ, poids=10)]}
    parts = [{"user_id": u, "etat": "acceptee"} for u in (PAUL, MARC)]
    profils = {MARC: {"prenom": "Marc", "seances_masquees": True},
               PAUL: {"prenom": "Paul", "seances_masquees": True}}
    marc, paul = calc.classement(d, parts, lignes, profils, PAUL, AUJ)
    assert marc["texte"] == "480 kg" and marc["seances"] is None
    assert paul["moi"] and paul["seances"] == 1          # soi-même : toujours le détail


def test_les_invites_qui_n_ont_pas_accepte_ne_sont_pas_classes():
    d = _defi("regularite")
    parts = [{"user_id": PAUL, "etat": "acceptee"}, {"user_id": MARC, "etat": "invite"}]
    assert [l["nom"] for l in calc.classement(d, parts, {}, {}, PAUL, AUJ)] == ["Toi"]


# ── Lancer, inviter, accepter, refuser ───────────────────────────


def test_lancer_inviter_puis_accepter(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    r = _lancer(paul, MARC, type_="volume", semaines="2", depart="demain")
    assert r.status_code == 302 and "m=defi_cree" in r.headers["Location"]
    (d,) = _defis()
    assert (d["type"], d["semaines"], d["debut"], d["fin"]) == ("volume", 2, str(AUJ + J), str(AUJ + 14 * J))
    assert sorted((p["user_id"], p["etat"]) for p in _participants()) == [(MARC, "invite"), (PAUL, "acceptee")]
    assert "Pas encore répondu : Marc" in _carte(_page(paul), d["id"])

    invitation = _carte(_page(marc), d["id"])
    assert "Paul te lance un défi" in invitation and "Volume" in invitation
    # Celui qui a lancé ne répond pas à la place de l'autre.
    _post(paul, "/amis/defis/accepter", defi=d["id"])
    assert {p["user_id"]: p["etat"] for p in _participants()}[MARC] == "invite"
    r = _post(marc, "/amis/defis/accepter", defi=d["id"])
    assert "m=defi_acceptee" in r.headers["Location"]
    ligne = next(p for p in _participants() if p["user_id"] == MARC)
    assert ligne["etat"] == "acceptee" and ligne["repondu_le"]
    carte = _carte(_page(marc), d["id"])
    assert "Commence le" in carte and "Toi" in carte and "Paul" in carte
    assert "Pas encore répondu" not in _carte(_page(paul), d["id"])


def test_refuser_efface_l_invitation(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    _lancer(paul, MARC)
    (d,) = _defis()
    assert "m=defi_refusee" in _post(marc, "/amis/defis/refuser", defi=d["id"]).headers["Location"]
    assert [p["user_id"] for p in _participants()] == [PAUL]
    assert f'id="defi-{d["id"]}"' not in _page(marc)


def test_un_non_ami_ne_peut_pas_etre_invite(trois):
    paul, marc, zoe = trois
    _devenir_amis(paul, marc)
    r = _lancer(paul, MARC, INCONNU)
    assert "m=defi_pas_ami" in r.headers["Location"]
    assert _defis() == [] and _participants() == []
    # Une demande d'ami en attente ne suffit pas non plus.
    _post(zoe, "/amis/demande", code="paulcode")
    assert "m=defi_pas_ami" in _lancer(paul, INCONNU).headers["Location"] and _defis() == []
    assert "m=defi_personne" in _lancer(paul).headers["Location"]
    # Ni plus tard, par « Inviter d'autres amis ».
    _lancer(paul, MARC, depart="demain")
    (d,) = _defis()
    assert "m=defi_pas_ami" in _post(paul, "/amis/defis/inviter", defi=d["id"], amis=INCONNU).headers["Location"]
    assert INCONNU not in {p["user_id"] for p in _participants()}


def test_un_non_participant_ne_voit_rien(trois):
    paul, marc, zoe = trois
    _devenir_amis(paul, marc)
    _post(zoe, "/amis/demande", code="paulcode")
    _post(paul, "/amis/accepter", id=next(a["id"] for a in core_db.amities_de(PAUL) if a["demandeur"] == INCONNU))
    _lancer(paul, MARC, type_="volume")
    (d,) = _defis()
    # Zoé est l'amie de Paul, mais pas dans le défi : ni carte, ni réponse possible.
    assert f'defi-{d["id"]}' not in _page(zoe) and "Volume ·" not in _page(zoe)
    assert core_db.lire_defis(INCONNU, "0001-01-01") == []
    _post(zoe, "/amis/defis/accepter", defi=d["id"])
    assert INCONNU not in {p["user_id"] for p in _participants()}
    assert 'id="defis-accueil"' not in zoe.get("/accueil").get_data(as_text=True)


def test_le_createur_seul_invite_et_annule_avant_le_debut(trois):
    paul, marc, zoe = trois
    _devenir_amis(paul, marc)
    _post(zoe, "/amis/demande", code="marccode")
    _post(marc, "/amis/accepter", id=next(a["id"] for a in core_db.amities_de(MARC) if a["demandeur"] == INCONNU))
    _lancer(paul, MARC, depart="demain")
    (d,) = _defis()
    _post(marc, "/amis/defis/accepter", defi=d["id"])
    # Marc n'invite pas Zoé dans le défi de Paul, ni ne l'annule.
    assert _post(marc, "/amis/defis/inviter", defi=d["id"], amis=INCONNU).headers["Location"].endswith("/amis#defis")
    assert INCONNU not in {p["user_id"] for p in _participants()}
    _post(marc, "/amis/defis/annuler", defi=d["id"])
    assert len(_defis()) == 1
    assert "m=defi_annule" in _post(paul, "/amis/defis/annuler", defi=d["id"]).headers["Location"]
    assert _defis() == [] and _participants() == []


def test_un_defi_commence_ne_s_annule_plus(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    _lancer(paul, MARC, depart="aujourdhui")
    (d,) = _defis()
    _post(paul, "/amis/defis/annuler", defi=d["id"])
    assert len(_defis()) == 1


def test_l_invitation_ne_vaut_plus_apres_le_jour_du_debut(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    fake = core_db.current_client()
    hier = _inserer_defi(fake, AUJ - J, acceptes=(), invites=(MARC,))
    auj = _inserer_defi(fake, AUJ, acceptes=(), invites=(MARC,))
    page = _page(marc)
    assert f'id="defi-{hier}"' not in page and f'id="defi-{auj}"' in page
    assert "m=defi_expire" in _post(marc, "/amis/defis/accepter", defi=hier).headers["Location"]
    assert "m=defi_acceptee" in _post(marc, "/amis/defis/accepter", defi=auj).headers["Location"]


def test_le_defi_de_progression_porte_un_exercice_de_son_historique(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    fake = core_db.current_client()
    assert "m=defi_invalide" in _lancer(paul, MARC, type_="progression", exercice="Squat").headers["Location"]
    _serie(fake, PAUL, AUJ - 3 * J, exo="Développé couché (Barre)")
    assert 'value="Développé couché"' in _page(paul)
    assert "m=defi_invalide" in _lancer(paul, MARC, type_="progression", exercice="Squat").headers["Location"]
    assert "m=defi_cree" in _lancer(paul, MARC, type_="progression", exercice="Développé couché").headers["Location"]
    assert _defis()[0]["exercice"] == "Développé couché"
    for faux in ({"type_": "inconnu"}, {"semaines": "3"}, {"depart": "hier"}):
        assert "m=defi_invalide" in _lancer(paul, MARC, **faux).headers["Location"]


def test_dix_participants_au_plus(trois, fake_db):
    paul, _marc, _zoe = trois
    autres = [f"u-ami-{i:04d}" for i in range(10)]
    for i, uid in enumerate(autres):
        _compte(fake_db, uid, f"Ami{i}", f"ami{i:04d}a"[:8])
        fake_db.table("amities").insert({"demandeur": uid, "destinataire": PAUL, "etat": "acceptee",
                                         "acceptee_le": "2026-10-01T00:00:00+00:00"}).execute()
    assert "m=defi_trop_invites" in _lancer(paul, *autres).headers["Location"]
    assert "m=defi_cree" in _lancer(paul, *autres[:9]).headers["Location"]


# ── Le classement en direct, la fin ──────────────────────────────


def test_le_classement_bouge_apres_une_seance(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    _lancer(paul, MARC, type_="regularite", depart="aujourdhui")
    (d,) = _defis()
    _post(marc, "/amis/defis/accepter", defi=d["id"])
    avant = _carte(_page(paul), d["id"])
    assert "0 séance" in avant and "En cours" in avant
    _seance(core_db.current_client(), marc, MARC)
    carte = _carte(_page(paul), d["id"])
    classement = carte[carte.index('aria-label="Classement"'):]
    assert classement.index("Marc") < classement.index("Toi")    # Marc passe devant
    assert "1 séance" in classement[classement.index("Marc"):classement.index("Toi")]
    accueil = paul.get("/accueil").get_data(as_text=True)
    assert 'id="defis-accueil"' in accueil and "Régularité" in accueil and "Marc" in accueil


def test_le_score_suit_l_historique_une_seance_effacee_sort_du_score(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    _lancer(paul, MARC, type_="volume", depart="aujourdhui")
    (d,) = _defis()
    _post(marc, "/amis/defis/accepter", defi=d["id"])
    _seance(core_db.current_client(), marc, MARC)
    assert "960 kg" in _carte(_page(paul), d["id"])
    _post(marc, "/seance/reset-session", seance_name="Push", date=AUJ.isoformat(), mode="prefaite")
    core_db.vider_cache()
    assert "960 kg" not in _carte(_page(paul), d["id"])
    # Rien en base ne ressemble à un score : seules les colonnes du schéma.
    assert set(_defis()[0]) <= {"id", "createur", "type", "exercice", "semaines", "debut", "fin", "created_at"}


def test_a_la_fin_le_resultat_arrive_dans_le_fil(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    fake = core_db.current_client()
    fini = _inserer_defi(fake, AUJ - 8 * J, type_="volume")       # du J-8 au J-2
    _serie(fake, MARC, AUJ - 5 * J, poids=100, reps=10)
    _serie(fake, PAUL, AUJ - 4 * J, poids=50, reps=10)
    _serie(fake, PAUL, AUJ - J, poids=500, reps=10)               # après la fin : ne compte pas
    page = _page(paul)
    fil = page[page.index('id="amis-fil"'):]
    carte = _carte(fil, fini)
    assert "Défi terminé" in carte and "Marc gagne avec 1 000 kg." in carte
    assert f'class="card defi defi-resultat" id="defi-{fini}"' in fil
    # Plus dans les défis en cours, et Marc lit « Tu gagnes ».
    assert page.count(f'id="defi-{fini}"') == 1
    assert "Tu gagnes avec 1 000 kg." in _page(marc)


def test_egalite_a_la_fin(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    fake = core_db.current_client()
    fini = _inserer_defi(fake, AUJ - 14 * J, type_="regularite")
    for uid in (PAUL, MARC):
        _serie(fake, uid, AUJ - 12 * J)
        _serie(fake, uid, AUJ - 10 * J)
    assert "Égalité entre Marc et toi : 2 séances chacun." in _carte(_page(paul), fini)


def test_un_defi_fini_depuis_plus_de_30_jours_quitte_le_fil(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    vieux = _inserer_defi(core_db.current_client(), AUJ - 45 * J, semaines=2)
    assert f'id="defi-{vieux}"' not in _page(paul)


# ── Qui voit quoi ────────────────────────────────────────────────


def test_un_participant_aux_seances_masquees_reste_sans_detail(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    _lancer(paul, MARC, type_="volume", depart="aujourdhui")
    (d,) = _defis()
    _post(marc, "/amis/defis/accepter", defi=d["id"])
    sid = _seance(core_db.current_client(), marc, MARC)
    carte = _carte(_page(paul), d["id"])
    assert "960 kg" in carte and "1 séance" in carte                # visible : score et détail

    _post(marc, "/amis/masquer", masquer="1")
    page = _page(paul)
    carte = _carte(page, d["id"])
    assert "Marc" in carte and "960 kg" in carte                    # toujours classé
    assert "1 séance" not in carte                                  # mais sans aucun détail
    assert f"s-{sid}" not in page and "Développé couché · 60 kg" not in page
    for secret in ("SECRET-COMMENTAIRE", "93,7", "93.7", "SECRET-MEMOIRE"):
        assert secret not in page
    accueil = paul.get("/accueil").get_data(as_text=True)
    assert "960 kg" in accueil and "1 séance" not in accueil[accueil.index('id="defis-accueil"'):][:1500]


def test_retirer_l_ami_du_createur_sort_du_defi(trois):
    paul, marc, _zoe = trois
    amitie = _devenir_amis(paul, marc)
    _lancer(paul, MARC, type_="volume", depart="aujourdhui")
    (d,) = _defis()
    _post(marc, "/amis/defis/accepter", defi=d["id"])
    _seance(core_db.current_client(), marc, MARC)
    _post(marc, "/amis/retirer", id=amitie)
    assert f'id="defi-{d["id"]}"' not in _page(marc)
    assert "Marc" not in _carte(_page(paul), d["id"])
    assert core_db.lire_defis(MARC, "0001-01-01") == []


def test_entre_invites_le_classement_ne_montre_que_les_chiffres_du_defi(trois):
    """Marc et Zoé sont amis de Paul, pas entre eux : chacun voit l'autre
    dans le classement (prénom et score), rien de ses séances."""
    paul, marc, zoe = trois
    _devenir_amis(paul, marc)
    _post(zoe, "/amis/demande", code="paulcode")
    _post(paul, "/amis/accepter", id=next(a["id"] for a in core_db.amities_de(PAUL) if a["demandeur"] == INCONNU))
    _lancer(paul, MARC, INCONNU, type_="volume", depart="aujourdhui")
    (d,) = _defis()
    for c in (marc, zoe):
        _post(c, "/amis/defis/accepter", defi=d["id"])
    sid = _seance(core_db.current_client(), marc, MARC)
    page = _page(zoe)
    assert "960 kg" in _carte(page, d["id"]) and "Marc" in _carte(page, d["id"])
    assert f"s-{sid}" not in page                                   # pas son ami : pas sa séance


# ── Compte, données, base en retard, limites ─────────────────────


def test_la_suppression_du_compte_nettoie_les_defis(trois, monkeypatch):
    paul, marc, zoe = trois
    _devenir_amis(paul, marc)
    _post(zoe, "/amis/demande", code="marccode")
    _post(marc, "/amis/accepter", id=next(a["id"] for a in core_db.amities_de(MARC) if a["demandeur"] == INCONNU))
    _lancer(paul, MARC)                                   # lancé par Paul
    _lancer(marc, INCONNU)                                # lancé par Marc
    du_paul, du_marc = (d["id"] for d in _defis())
    _post(marc, "/amis/defis/accepter", defi=du_paul)
    from core import stripe_client
    monkeypatch.setattr(stripe_client, "resilier_avant_suppression", lambda *_a: None)
    monkeypatch.setattr(stripe_client, "client", lambda: None)

    assert _post(marc, "/gestion/delete-account", confirm="yes").status_code == 302
    assert [d["id"] for d in _defis()] == [du_paul]                 # son défi part, celui de Paul reste
    assert [(p["defi_id"], p["user_id"]) for p in _participants()] == [(du_paul, PAUL)]
    assert du_marc not in {p["defi_id"] for p in _participants()}


def test_l_export_contient_les_defis_sans_les_identifiants_des_autres(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    _lancer(paul, MARC, type_="volume", depart="demain")
    (d,) = _defis()
    _post(marc, "/amis/defis/accepter", defi=d["id"])
    donnees = json.loads(marc.get("/gestion/export").get_data(as_text=True))
    (mien,) = donnees["defis"]
    assert mien["type"] == "volume" and mien["ma_reponse"] == "acceptee" and not mien["lance_par_moi"]
    assert mien["avec"] == ["Paul"] and PAUL not in json.dumps(donnees["defis"])


def test_sans_la_v53_la_page_et_l_accueil_marchent(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    fake = core_db.current_client()

    def refuser_tables(table, _vrai=fake.table):
        if table in ("defis", "defis_participants"):
            raise Exception("{'code': '42P01', 'message': 'relation \"public.%s\" does not exist'}" % table)
        return _vrai(table)
    fake.table = refuser_tables
    page = _page(paul)
    assert "Les défis arrivent bientôt" in page and "Mes amis · 1" in page
    assert paul.get("/accueil").status_code == 200
    assert "m=defi_indisponible" in _lancer(paul, MARC).headers["Location"]
    _seance(fake, marc, MARC)                                       # la fin de séance marche
    from core import schema
    assert "defis_participants" in schema.etat()["absentes"] or "defis" in schema.etat()["absentes"]


def test_le_controle_du_schema_connait_les_tables_v53():
    from core.schema import ATTENDU
    assert {"defis", "defis_participants"} <= set(ATTENDU)
    assert "exercice" in ATTENDU["defis"] and "etat" in ATTENDU["defis_participants"]


def test_le_lancement_est_limite_par_compte(trois):
    paul, marc, _zoe = trois
    codes = [_lancer(paul, MARC).status_code for _ in range(11)]
    assert codes[:10] == [302] * 10 and codes[10] == 429
    assert _lancer(marc, PAUL).status_code == 302                   # le voisin n'est pas bridé


def test_les_invitations_sont_limitees(trois):
    paul, _marc, _zoe = trois
    codes = [_post(paul, "/amis/defis/inviter", defi="1", amis=MARC).status_code for _ in range(31)]
    assert codes[:30] == [302] * 30 and codes[30] == 429


def test_dix_defis_en_cours_au_plus(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    fake = core_db.current_client()
    for _ in range(calc.MAX_EN_COURS):
        _inserer_defi(fake, AUJ, acceptes=())
    assert "m=defi_trop" in _lancer(paul, MARC).headers["Location"]
    autre = _inserer_defi(fake, AUJ, acceptes=(), invites=(PAUL,), createur=MARC)
    assert "m=defi_trop" in _post(paul, "/amis/defis/accepter", defi=autre).headers["Location"]


def test_la_page_est_ouverte_aux_comptes_gratuits(trois):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    page = _page(paul)
    assert 'action="/amis/defis/lancer"' in page and 'x-data="defiForm"' in page
    assert "Lancer un défi" in page


# ── Le jour du début, rien d'avant le lancement (audit du 28/10, m10) ──


def _a(heures):
    """Un instant ISO, `heures` après maintenant (négatif : avant)."""
    return (dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=heures)).isoformat()


def test_le_jour_du_debut_une_seance_d_avant_le_lancement_ne_compte_pas():
    d = {**_defi("regularite", debut=AUJ), "created_at": _a(-1)}
    matin = [_ligne(PAUL, AUJ, created_at=_a(-3))]
    assert calc.score(d, matin, AUJ)["valeur"] == 0
    soir = matin + [_ligne(PAUL, AUJ, seance="Pull", created_at=_a(0))]
    assert calc.score(d, soir, AUJ)["valeur"] == 1
    # Le volume suit la même règle ; une série sans heure (base ancienne) compte.
    v = {**_defi("volume", debut=AUJ), "created_at": _a(-1)}
    assert calc.score(v, [_ligne(PAUL, AUJ, reps=10, poids=50, created_at=_a(-3)),
                          _ligne(PAUL, AUJ, reps=10, poids=40)], AUJ)["valeur"] == 400


def test_les_jours_suivants_tout_compte():
    d = {**_defi("regularite", debut=AUJ - J), "created_at": _a(-30)}
    assert calc.score(d, [_ligne(PAUL, AUJ, created_at=_a(-25))], AUJ)["valeur"] == 1


def test_sur_la_page_la_seance_du_matin_ne_compte_pas(trois, fake_db):
    paul, marc, _zoe = trois
    _devenir_amis(paul, marc)
    _serie(fake_db, MARC, AUJ)                                   # séance du matin
    fake_db.tables["history"][-1]["created_at"] = _a(-3)
    did = _inserer_defi(fake_db, AUJ)                            # lancé une heure après
    next(x for x in _defis(fake_db) if x["id"] == did)["created_at"] = _a(-2)
    assert "1 séance" not in _carte(_page(paul), did)
    _serie(fake_db, MARC, AUJ, seance="Pull")                    # après le lancement
    fake_db.tables["history"][-1]["created_at"] = _a(0)
    core_db.vider_cache()
    assert "1 séance" in _carte(_page(paul), did)
