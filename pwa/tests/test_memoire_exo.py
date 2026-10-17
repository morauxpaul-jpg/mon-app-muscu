"""Les remarques de la fois d'avant reviennent sur la carte (core/memoire_exo.py).

Retour du 14/10 : « les remarques ne s'affichent pas d'une séance à une
autre ». Elles étaient enregistrées, mais ne revenaient que dans le tableau
replié « Historique et options », pour les semaines PRÉCÉDENTES : la séance
du lundi était invisible le jeudi."""
import datetime as dt

from conftest import CSRF, USER_ID
from core.dates import continuous_week
from core.memoire_exo import derniere_remarque, nettoyer_remarque

LUNDI = dt.date(2026, 9, 14)
JEUDI = dt.date(2026, 9, 17)


def _ligne(date, serie, remarque, seance="Push", exercice="Développé couché", reps=8):
    return {"Date": date.isoformat(), "Séance": seance, "Exercice": exercice,
            "Série": serie, "Reps": reps, "Poids": 80.0, "Remarque": remarque}


def test_la_remarque_garde_ce_que_l_utilisateur_a_tape():
    assert nettoyer_remarque("SKIP épaule douloureuse") == "épaule douloureuse"
    assert nettoyer_remarque("@RPE8 siège cran 4") == "siège cran 4"
    assert nettoyer_remarque("Import Hevy") == ""
    assert nettoyer_remarque("SKIP") == ""


def test_la_seance_du_lundi_se_voit_le_jeudi():
    hist = [_ligne(LUNDI, 1, ""), _ligne(LUNDI, 2, "siège cran 4"), _ligne(LUNDI, 3, "dernière aidée")]
    assert derniere_remarque(hist, "Développé couché", "Push", JEUDI.isoformat()) == \
        "lun. 14/09 · S2 siège cran 4 · S3 dernière aidée"


def test_seule_la_derniere_seance_annotee_revient():
    plus_tot = LUNDI - dt.timedelta(days=7)
    hist = [_ligne(plus_tot, 1, "vieille note"), _ligne(LUNDI, 1, "nouvelle note")]
    assert derniere_remarque(hist, "Développé couché", "Push", JEUDI.isoformat()) == \
        "lun. 14/09 · S1 nouvelle note"


def test_la_note_du_jour_meme_ne_compte_pas_comme_la_fois_d_avant():
    hist = [_ligne(JEUDI, 1, "aujourd'hui")]
    assert derniere_remarque(hist, "Développé couché", "Push", JEUDI.isoformat()) == ""


def test_une_serie_passee_garde_sa_raison():
    hist = [_ligne(LUNDI, 1, "SKIP épaule douloureuse", reps=0)]
    assert derniere_remarque(hist, "Développé couché", "Push", JEUDI.isoformat()) == \
        "lun. 14/09 · S1 épaule douloureuse"


def test_un_exercice_deplace_garde_ses_notes():
    hist = [_ligne(LUNDI, 1, "prise serrée", seance="Push 2")]
    assert derniere_remarque(hist, "Développé couché", "Push", JEUDI.isoformat()) == \
        "lun. 14/09 · S1 prise serrée"


# ── De la base à la page ─────────────────────────────────────────


def _seed(fake):
    fake.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Développé couché", "sets": 3, "muscle": "Pecs"}],
        "_planning": {"Lundi": "Push", "Jeudi": "Push"}, "_settings": {},
        "_started_at": LUNDI.isoformat(),
    }}).execute()
    fake.table("history").insert({
        "user_id": USER_ID, "semaine": continuous_week(LUNDI), "seance": "Push",
        "exercice": "Développé couché", "serie": 2, "reps": 8, "poids": 80.0,
        "remarque": "cran 4 poignee haute", "muscle": "Pecs", "date": LUNDI.isoformat(),
    }).execute()


def test_la_carte_du_jeudi_affiche_la_remarque_du_lundi(fake_db, logged_in):
    _seed(fake_db)
    html = logged_in.get(f"/seance?mode=prefaite&name=Push&date={JEUDI.isoformat()}").get_data(as_text=True)
    assert "S2 cran 4 poignee haute" in html
    assert 'x-if="lastNote"' in html


def test_changer_de_variante_renvoie_ses_remarques(fake_db, logged_in):
    _seed(fake_db)
    r = logged_in.post("/seance/api/variant-history", headers={"X-CSRFToken": CSRF}, json={
        "exo_base": "Développé couché", "variant": "Standard", "seance": "Push",
        "date": JEUDI.isoformat(), "s_act": continuous_week(JEUDI), "week_offset": 0})
    assert r.get_json()["derniere_remarque"] == "lun. 14/09 · S2 cran 4 poignee haute"
