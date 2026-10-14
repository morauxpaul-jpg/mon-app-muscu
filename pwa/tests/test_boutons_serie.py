"""Boutons − / + de la séance (14/10/2026) : la charge d'à côté vient des
charges déjà soulevées sur l'exercice (core/seance_charges.py)."""
import re

from core.seance_charges import PAS_DEFAUT, PAS_HALTERES, echelle_charges


def _l(exo, poids, reps=8, date="2026-10-01"):
    return {"Exercice": exo, "Poids": poids, "Reps": reps, "Date": date,
            "Séance": "Leg", "Série": 1, "Remarque": ""}


def test_les_plaques_de_la_machine_donnent_le_pas():
    # Adducteurs du vrai compte (14/10) : plaques de 7 kg, 79 et non 80.
    hist = [_l("Machine adducteurs", p) for p in (52, 59, 66, 73, 79, 86, 93, 100)]
    e = echelle_charges(hist, "Machine adducteurs")
    assert e["charges"] == [52, 59, 66, 73, 79, 86, 93, 100]
    assert e["pas"] == 7


def test_a_egalite_l_ecart_le_plus_fin_l_emporte():
    # Développé décliné (Barre) du vrai compte : 60 80 100 110 115 120.
    hist = [_l("Développé décliné (Barre)", p) for p in (60, 80, 100, 110, 115, 120)]
    assert echelle_charges(hist, "Développé décliné (Barre)")["pas"] == 5


def test_poulie_et_arrondi_au_dixieme():
    hist = [_l("Extensions triceps (Poulie)", p) for p in (20.25, 22.5, 24.75, 27.0)]
    e = echelle_charges(hist, "Extensions triceps (Poulie)")
    assert e["charges"] == [20.2, 22.5, 24.8, 27.0]
    assert e["pas"] == 2.3          # 2,3 · 2,3 · 2,2 : le plus fréquent


def test_sans_historique_un_pas_par_defaut():
    assert echelle_charges([], "Squat")["pas"] == PAS_DEFAUT == 2.5
    assert echelle_charges([], "Curl (Haltères)")["pas"] == PAS_HALTERES == 2.0
    assert echelle_charges([], "Squat")["charges"] == []


def test_ni_series_vides_ni_poids_du_corps_ni_autre_materiel():
    hist = [_l("Dips", 0, 10), _l("Dips (Lesté)", 10), _l("Dips (Lesté)", 15),
            _l("Dips (Lesté)", 20, reps=0), _l("dips (lesté) ", 25)]
    e = echelle_charges(hist, "Dips (Lesté)")
    # 0 kg (poids du corps), 0 rep (série non faite) : écartés ; la casse
    # et les espaces ne séparent pas l'historique.
    assert e["charges"] == [10, 15, 25]


def test_la_carte_de_seance_recoit_l_echelle(fake_db, logged_in):
    from conftest import USER_ID
    from core.dates import continuous_week, logical_today_paris
    import datetime as dt
    fake_db.table("profiles").insert({"id": USER_ID, "tier": "free"}).execute()
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Leg": [{"name": "Machine adducteurs", "sets": 3, "muscle": "Adducteurs"}],
        "_settings": {}}}).execute()
    jour = logical_today_paris() - dt.timedelta(days=7)
    for k, p in enumerate((59, 66, 73), 1):
        fake_db.table("history").insert({
            "user_id": USER_ID, "semaine": continuous_week(jour), "seance": "Leg",
            "exercice": "Machine adducteurs", "serie": k, "reps": 10, "poids": p,
            "remarque": "", "muscle": "Adducteurs", "date": jour.isoformat()}).execute()
    html = logged_in.get("/seance?mode=prefaite&name=Leg").get_data(as_text=True)
    assert re.search(r'&#34;echelle&#34;: \{&#34;charges&#34;: \[59\.0, 66\.0, 73\.0\], &#34;pas&#34;: 7\.0\}', html) \
        or '"echelle": {"charges": [59.0, 66.0, 73.0], "pas": 7.0}' in html
    # Les boutons, nommés pour un lecteur d'écran.
    assert "'Plus lourd, série ' + (i + 1)" in html
    assert "'Une répétition de moins, série ' + (i + 1)" in html
