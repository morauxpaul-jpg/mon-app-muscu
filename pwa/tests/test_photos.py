"""Photos de progression (PRO) dans l'onglet « Corps » de Progrès : ajout,
comparaison, poids sous les photos, accès, suppression.

Demande du propriétaire (18/10/2026) : « des images de son corps pour voir
l'évolution ». Rangées sur le serveur, dans un dossier privé : le point qui
compte le plus ici est qu'un compte ne voie jamais la photo d'un autre.
"""
import io
import json
from datetime import date, timedelta

import pytest

from conftest import CSRF, USER_ID
from core import photos_corps as pc
from core.dates import today_paris

AUTRE = "u-autre-0002"
JPEG = b"\xff\xd8\xff\xe0" + b"photo" * 40 + b"\xff\xd9"
MINI = b"\xff\xd8\xff\xe0" + b"mini" * 10 + b"\xff\xd9"
EN_TETES = {"X-CSRFToken": CSRF, "Accept": "application/json"}


def _envoyer(client, angle="face", jour=None, image=JPEG, mini=MINI):
    jour = jour or today_paris()
    return client.post("/progres/photos", headers=EN_TETES, content_type="multipart/form-data", data={
        "angle": angle, "date": jour.isoformat(),
        "image": (io.BytesIO(image), "photo.jpg"), "miniature": (io.BytesIO(mini), "miniature.jpg"),
    })


def _fichiers(fake_db):
    return fake_db.storage.dossiers.get("photos-corps", {})


def _lignes(fake_db):
    return fake_db.tables.get("photos_corps", [])


# ── Les calculs ──────────────────────────────────────────────────


def test_l_ecart_se_lit_comme_on_le_dirait():
    j = date(2026, 1, 1)
    assert pc.ecart(j, j) == "même jour"
    assert pc.ecart(j, j + timedelta(days=1)) == "1 jour"
    assert pc.ecart(j, j + timedelta(days=3)) == "3 jours"
    assert pc.ecart(j, j + timedelta(days=56)) == "8 semaines"
    assert pc.ecart(j, j + timedelta(days=152)) == "5 mois"
    assert pc.ecart(j, j + timedelta(days=426)) == "1 an et 2 mois"
    assert pc.ecart(j, j + timedelta(days=730)) == "2 ans"


def test_l_ecart_de_poids_dit_le_sens():
    assert pc.ecart_poids(94.6, 91.4) == "−3,2 kg"
    assert pc.ecart_poids(80, 82.5) == "+2,5 kg"
    assert pc.ecart_poids(80, 80) == "même poids"
    assert pc.ecart_poids(None, 80) == ""


def test_une_photo_ne_peut_pas_etre_datee_demain():
    auj = date(2026, 10, 18)
    assert pc.date_valide("2026-10-18", auj) == auj
    assert pc.date_valide("2026-10-19", auj) is None
    assert pc.date_valide("1989-12-31", auj) is None
    assert pc.date_valide("hier", auj) is None


def test_le_rappel_tombe_toutes_les_4_semaines_trois_fois():
    auj = date(2026, 10, 18)
    jours = [n for n in range(0, 140) if pc.rappel_du_jour((auj - timedelta(days=n)).isoformat(), auj)]
    assert jours == [28, 56, 84]


def test_la_comparaison_part_de_la_premiere_et_de_la_derniere():
    pesees = [("2026-08-01", 94.6), ("2026-10-01", 91.4)]
    liste = [pc.fiche({"id": i, "date": d, "angle": "face"}, pesees)
             for i, d in ((1, "2026-08-01"), (2, "2026-09-01"), (3, "2026-10-01"))]
    c = pc.comparaison(liste)
    assert (c["avant"]["id"], c["apres"]["id"]) == (1, 3)
    assert c["ecart"] == "2 mois" and c["ecart_poids"] == "−3,2 kg"
    c = pc.comparaison(liste, avant_id="3", apres_id="2")
    assert (c["avant"]["id"], c["apres"]["id"]) == (2, 3), "toujours dans l'ordre des dates"
    assert pc.comparaison(liste[:1]) is None


def test_sous_une_photo_sans_pesee_du_jour_la_derniere_pesee_et_sa_date():
    """Choix du propriétaire (18/10) : « afficher la dernière pesée », rien
    d'inventé dans la courbe de poids."""
    pesees = pc.index_pesees([{"date": "2026-10-16", "poids_kg": 91.2},
                              {"date": "2026-10-07", "poids_kg": "91.4"}])
    assert pesees == [("2026-10-07", 91.4), ("2026-10-16", 91.2)]
    du_jour = pc.fiche({"id": 1, "date": "2026-10-16", "angle": "face"}, pesees)
    assert (du_jour["kg"], du_jour["kg_le"]) == (91.2, "")
    plus_tard = pc.fiche({"id": 2, "date": "2026-10-18", "angle": "face"}, pesees)
    assert (plus_tard["kg"], plus_tard["kg_le"]) == (91.2, "16/10")
    trop_tot = pc.fiche({"id": 3, "date": "2026-10-01", "angle": "face"}, pesees)
    assert trop_tot["kg"] is None, "pas de pesée d'après la photo"
    meme_pesee = pc.comparaison([du_jour, plus_tard])
    assert meme_pesee["ecart_poids"] == "", "même pesée sous les deux photos : pas d'écart inventé"


def test_l_invitation_a_se_peser_vaut_pour_la_date_des_photos_recentes():
    auj = date(2026, 10, 18)
    photos = [{"date": "2026-10-18", "angle": a} for a in ("face", "profil", "dos")]
    pesees = [("2026-10-16", 91.2)]
    assert pc.pesee_manquante(photos, pesees, auj) == {
        "date": "2026-10-18", "date_fr": "18/10", "derniere": (91.2, "16/10")}
    assert pc.pesee_manquante(photos, pesees + [("2026-10-18", 91.0)], auj) is None, "déjà pesé ce jour-là"
    assert pc.pesee_manquante(photos, [], auj)["derniere"] is None
    vieilles = [{"date": "2026-07-26", "angle": "face"}]
    assert pc.pesee_manquante(vieilles, pesees, auj) is None, "une vieille photo importée ne réclame rien"
    assert pc.pesee_manquante([], pesees, auj) is None


# ── La page et l'ajout ───────────────────────────────────────────


def test_un_compte_gratuit_voit_son_poids_et_les_photos_verrouillees(fake_db, client):
    with client.session_transaction() as s:
        s.update({"user_id": USER_ID, "onboarded": True, "is_vip": False, "_csrf": CSRF})
    page = client.get("/progres/corps").get_data(as_text=True)
    assert 'action="/progres/poids"' in page, "le poids reste gratuit"
    photos = page.split('id="photos"')[1]
    assert "Débloquer" in photos and 'id="ph-form"' not in photos
    assert _envoyer(client).status_code == 403
    assert _lignes(fake_db) == [] and _fichiers(fake_db) == {}


def test_l_ancienne_adresse_des_photos_mene_a_l_onglet_corps(fake_db, logged_in):
    r = logged_in.get("/progres/photos?angle=dos&avant=3")
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/progres/corps?angle=dos&avant=3#photos")


def test_ajouter_une_photo_la_range_chez_soi_et_l_affiche(fake_db, logged_in):
    r = _envoyer(logged_in, "profil")
    assert r.status_code == 200 and r.get_json()["ok"] is True
    [ligne] = _lignes(fake_db)
    assert ligne["user_id"] == USER_ID and ligne["angle"] == "profil" and ligne["octets"] == len(JPEG)
    assert set(_fichiers(fake_db)) == {ligne["chemin"], ligne["miniature"]}
    assert all(c.startswith(USER_ID + "/") for c in _fichiers(fake_db))

    assert r.get_json()["url"] == "/progres/corps?angle=profil#photos"
    page = logged_in.get(r.get_json()["url"]).get_data(as_text=True)
    assert f'/progres/photos/{ligne["id"]}/image' in page and "Profil · 1" in page
    image = logged_in.get(f'/progres/photos/{ligne["id"]}/image')
    assert image.data == JPEG and image.mimetype == "image/jpeg"
    assert image.headers["Cache-Control"] == "private, no-cache"
    assert logged_in.get(f'/progres/photos/{ligne["id"]}/image?mini=1').data == MINI


def test_reprendre_le_meme_angle_le_meme_jour_remplace_la_photo(fake_db, logged_in):
    _envoyer(logged_in, "face")
    ancienne = dict(_lignes(fake_db)[0])
    r = _envoyer(logged_in, "face", image=JPEG + b"v2")
    assert r.get_json()["remplace"] is True
    [ligne] = _lignes(fake_db)
    assert ligne["id"] == ancienne["id"] and ligne["chemin"] != ancienne["chemin"]
    assert set(_fichiers(fake_db)) == {ligne["chemin"], ligne["miniature"]}, "l'ancien fichier est retiré"


@pytest.mark.parametrize("champs, code", [
    ({"angle": "cote"}, 400),
    ({"jour": today_paris() + timedelta(days=1)}, 400),
    ({"image": b"<html>pas une photo</html>"}, 400),
    ({"image": b"\xff\xd8\xff" + b"0" * pc.OCTETS_MAX}, 413),
])
def test_ce_qui_n_est_pas_une_photo_valable_est_refuse(fake_db, logged_in, champs, code):
    assert _envoyer(logged_in, **champs).status_code == code
    assert _lignes(fake_db) == [] and _fichiers(fake_db) == {}


def test_la_photo_d_un_autre_compte_reste_introuvable(fake_db, logged_in):
    fake_db.storage.from_("photos-corps").upload(AUTRE + "/x.jpg", JPEG)
    fake_db.table("photos_corps").insert({"user_id": AUTRE, "date": "2026-10-01", "angle": "face",
                                          "chemin": AUTRE + "/x.jpg", "miniature": AUTRE + "/x_mini.jpg",
                                          "octets": len(JPEG)}).execute()
    autre = _lignes(fake_db)[0]["id"]
    assert logged_in.get(f"/progres/photos/{autre}/image").status_code == 404
    assert logged_in.get(f"/progres/photos/{autre}/image?telecharger=1").status_code == 404
    logged_in.post(f"/progres/photos/{autre}/supprimer", headers={"X-CSRFToken": CSRF})
    assert len(_lignes(fake_db)) == 1 and AUTRE + "/x.jpg" in _fichiers(fake_db)
    assert f"/progres/photos/{autre}/" not in logged_in.get("/progres/corps").get_data(as_text=True)


def test_le_navigateur_revalide_sans_relire_le_fichier(fake_db, logged_in):
    _envoyer(logged_in)
    pid = _lignes(fake_db)[0]["id"]
    premiere = logged_in.get(f"/progres/photos/{pid}/image")
    fake_db.storage.pannes.add("download")
    r = logged_in.get(f"/progres/photos/{pid}/image", headers={"If-None-Match": premiere.headers["ETag"]})
    assert r.status_code == 304


def test_telecharger_donne_un_nom_de_fichier_lisible(fake_db, logged_in):
    _envoyer(logged_in, "dos")
    pid = _lignes(fake_db)[0]["id"]
    r = logged_in.get(f"/progres/photos/{pid}/image?telecharger=1")
    assert r.headers["Content-Disposition"] == f"attachment; filename=photo-dos-{today_paris().isoformat()}.jpg"


def test_avant_apres_avec_le_poids_du_jour(fake_db, logged_in):
    auj = today_paris()
    avant = auj - timedelta(days=56)
    for d, kg in ((avant, 94.6), (auj, 91.4)):
        fake_db.table("body_weight").insert({"user_id": USER_ID, "date": d.isoformat(), "poids_kg": kg}).execute()
        _envoyer(logged_in, "face", d)
    page = logged_in.get("/progres/corps?angle=face").get_data(as_text=True)
    assert "Avant / après · 8 semaines · −3,2 kg" in page
    assert "94,6 kg" in page and "91,4 kg" in page
    assert 'id="ph-pesee"' not in page, "pesé le jour des photos : rien à demander"


def test_photos_sans_pesee_du_jour_invitation_puis_poids_note(fake_db, logged_in):
    auj = today_paris()
    il_y_a_2 = (auj - timedelta(days=2)).isoformat()
    fake_db.table("body_weight").insert({"user_id": USER_ID, "date": il_y_a_2, "poids_kg": 91.2}).execute()
    _envoyer(logged_in, "face")
    _envoyer(logged_in, "dos")
    page = logged_in.get("/progres/corps").get_data(as_text=True)
    invitation = page.split('id="ph-pesee"')[1].split("</div>")[0]
    assert f"Pas de pesée le {auj.strftime('%d/%m')}" in invitation
    assert f"91,2 kg</b> (le {il_y_a_2[8:10]}/{il_y_a_2[5:7]})" in invitation
    assert page.count('id="ph-pesee"') == 1, "une invitation par date, pas par photo"
    assert f"91,2 kg <span class=\"ph-pesee-le\">(pesée du {il_y_a_2[8:10]}/{il_y_a_2[5:7]})</span>" in page

    r = logged_in.post("/progres/poids", headers={"X-CSRFToken": CSRF},
                       data={"date": auj.isoformat(), "poids_kg": "90,8", "retour": "photos"})
    assert r.headers["Location"].endswith("/progres/corps#photos")
    page = logged_in.get("/progres/corps").get_data(as_text=True)
    assert 'id="ph-pesee"' not in page and "90,8 kg" in page
    assert "(pesée du" not in page, "la pesée du jour remplace l'ancienne sous les photos"


def test_supprimer_retire_le_fichier_et_la_ligne(fake_db, logged_in):
    _envoyer(logged_in, "face")
    pid = _lignes(fake_db)[0]["id"]
    r = logged_in.post(f"/progres/photos/{pid}/supprimer", data={"angle": "face"},
                       headers={"X-CSRFToken": CSRF})
    assert r.status_code == 302 and _lignes(fake_db) == [] and _fichiers(fake_db) == {}


def test_un_fichier_qui_resiste_garde_la_ligne_pour_reessayer(fake_db, logged_in):
    _envoyer(logged_in, "face")
    pid = _lignes(fake_db)[0]["id"]
    fake_db.storage.pannes.add("remove")
    r = logged_in.post(f"/progres/photos/{pid}/supprimer", headers={"X-CSRFToken": CSRF})
    assert "erreur=suppression" in r.headers["Location"] and len(_lignes(fake_db)) == 1
    assert "n'a pas pu être supprimée" in logged_in.get(r.headers["Location"]).get_data(as_text=True)


def test_un_envoi_rate_ne_laisse_pas_de_fichier_orphelin(fake_db, logged_in, monkeypatch):
    from conftest import FakeQuery
    vraie = FakeQuery.execute

    def refuse(self):
        if self._table == "photos_corps" and self._op == "insert":
            raise Exception("réseau coupé")
        return vraie(self)
    monkeypatch.setattr(FakeQuery, "execute", refuse)
    assert _envoyer(logged_in).status_code == 502
    assert _fichiers(fake_db) == {}


def test_un_compte_redevenu_gratuit_garde_ses_photos(fake_db, logged_in):
    _envoyer(logged_in, "face")
    pid = _lignes(fake_db)[0]["id"]
    with logged_in.session_transaction() as s:
        s.update({"is_vip": False, "is_vip_full": False})
    assert logged_in.get(f"/progres/photos/{pid}/image?telecharger=1").data == JPEG
    logged_in.post(f"/progres/photos/{pid}/supprimer", headers={"X-CSRFToken": CSRF})
    assert _lignes(fake_db) == []


# ── Base en retard ───────────────────────────────────────────────


@pytest.fixture()
def sans_table(monkeypatch):
    from conftest import FakeQuery
    vraie = FakeQuery.execute

    def refuse(self):
        if self._table == "photos_corps":
            raise Exception("{'code': 'PGRST205', 'message': \"Could not find the table "
                            "'public.photos_corps' in the schema cache\"}")
        return vraie(self)
    monkeypatch.setattr(FakeQuery, "execute", refuse)


def test_sans_la_migration_le_poids_marche_et_les_photos_le_disent(fake_db, logged_in, sans_table):
    from core import schema
    page = logged_in.get("/progres/corps").get_data(as_text=True)
    assert "arrivent bientôt" in page and 'action="/progres/poids"' in page
    assert _envoyer(logged_in).status_code == 503
    assert "photos_corps" in schema.etat()["absentes"]


# ── Export et suppression du compte ──────────────────────────────


def test_l_export_liste_les_photos(fake_db, logged_in):
    _envoyer(logged_in, "dos")
    pid = _lignes(fake_db)[0]["id"]
    export = json.loads(logged_in.get("/gestion/export").get_data(as_text=True))
    assert export["photos"] == [{"date": today_paris().isoformat(), "angle": "dos",
                                 "fichier": f"/progres/photos/{pid}/image?telecharger=1"}]


def test_supprimer_le_compte_efface_les_fichiers(fake_db, logged_in):
    _envoyer(logged_in, "face")
    _envoyer(logged_in, "dos")
    from core import db
    db.delete_user_account(USER_ID)
    assert _lignes(fake_db) == [] and _fichiers(fake_db) == {}


def test_si_un_fichier_resiste_le_compte_n_est_pas_supprime(fake_db, logged_in):
    _envoyer(logged_in, "face")
    fake_db.storage.pannes.add("remove")
    from core import db
    with pytest.raises(Exception):
        db.delete_user_account(USER_ID)
    assert fake_db.auth.admin.deleted_users == [], "sinon la photo resterait, rattachée à rien"


# ── Le rappel des 4 semaines ─────────────────────────────────────


def test_le_rappel_va_aux_comptes_pro_qui_l_attendent_a_leur_heure():
    from core.rappel_photos import cibles
    auj = date(2026, 10, 18)
    il_y_a_28 = (auj - timedelta(days=28)).isoformat()
    dernieres = {"a": il_y_a_28, "b": il_y_a_28, "c": il_y_a_28, "d": il_y_a_28,
                 "e": (auj - timedelta(days=27)).isoformat()}
    reglages = {"a": {"notifications": True, "reminder_hour": 7}, "b": {"notifications": True},
                "c": {"notifications": False}, "d": {"notifications": True}, "e": {"notifications": True}}
    pro = {"a", "b", "c", "e"}
    assert cibles(dernieres, reglages, pro, 18, auj) == {"b": 28}
    assert cibles(dernieres, reglages, pro, 7, auj) == {"a": 28}


def test_le_cron_envoie_le_rappel(fake_db, monkeypatch):
    from core import push as core_push, rappel_photos
    envoyes = []
    monkeypatch.setattr(core_push, "is_configured", lambda: True)
    monkeypatch.setattr(core_push, "send_push", lambda sub, p: envoyes.append((sub["endpoint"], p)) or "ok")
    il_y_a_28 = (today_paris() - timedelta(days=28)).isoformat()
    fake_db.table("photos_corps").insert({"user_id": USER_ID, "date": il_y_a_28, "angle": "face",
                                          "chemin": "c", "miniature": "m", "octets": 1}).execute()
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "vip"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {}}).execute()
    fake_db.table("reglages").insert({"user_id": USER_ID, "notifications": True, "reminder_hour": 18}).execute()
    fake_db.table("push_subscriptions").insert({"user_id": USER_ID, "endpoint": "https://push.test/x",
                                                "p256dh": "p", "auth": "a"}).execute()
    assert rappel_photos.run_rappel_photos(heure=17)["sent"] == 0
    assert rappel_photos.run_rappel_photos(heure=18)["sent"] == 1
    endpoint, charge = envoyes[0]
    assert endpoint == "https://push.test/x" and charge["url"] == "/progres/corps#photos"
    assert charge["body"].startswith("4 semaines depuis les dernières")
