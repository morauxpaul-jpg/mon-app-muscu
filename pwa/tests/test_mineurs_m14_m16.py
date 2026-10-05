"""Derniers points mineurs de l'audit du 03/10 : M14, M15, M16."""
import datetime as dt
from pathlib import Path

from conftest import USER_ID

import core.db as db

PWA = Path(__file__).resolve().parents[1]


def _il_y_a(jours):
    return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=jours)).isoformat()


# ── M14 : l'étape VIP du funnel compte la même fenêtre que les autres ──


def test_le_funnel_ne_compte_que_les_vip_de_la_fenetre(fake_db):
    """Un VIP abonné il y a 3 mois comptait dans la conversion des 30
    derniers jours : le taux « Checkout → VIP » pouvait dépasser 100 %."""
    fake_db.table("profiles").insert({"id": "ancien", "tier": "vip"}).execute()
    fake_db.table("events").insert({"user_id": "ancien", "event": "vip_activated",
                                    "created_at": _il_y_a(90)}).execute()
    fake_db.table("profiles").insert({"id": "recent", "tier": "vip"}).execute()
    for ev in ("checkout_started", "vip_activated"):
        fake_db.table("events").insert({"user_id": "recent", "event": ev,
                                        "created_at": _il_y_a(2)}).execute()
    etapes = {s["key"]: s for s in db.get_funnel_stats(30)["steps"]}
    assert etapes["vip"]["users"] == 1
    assert etapes["vip"]["pct_of_prev"] == 100.0


def test_un_vip_rembourse_dans_la_fenetre_compte_quand_meme_comme_conversion(fake_db):
    """Le funnel mesure la conversion, pas le stock : un remboursement
    ultérieur ne réécrit pas le fait que la personne a payé."""
    fake_db.table("profiles").insert({"id": "u1", "tier": "free"}).execute()
    fake_db.table("events").insert({"user_id": "u1", "event": "vip_activated",
                                    "created_at": _il_y_a(5)}).execute()
    etapes = {s["key"]: s for s in db.get_funnel_stats(30)["steps"]}
    assert etapes["vip"]["users"] == 1


# ── M15 : le tonnage admin ne compte pas le cardio ─────────────────────


def _lignes(fake):
    fake.table("history").insert({
        "user_id": USER_ID, "date": "2026-09-14", "seance": "Push", "exercice": "Squat",
        "serie": 1, "reps": 5, "poids": 100.0}).execute()
    # ancienne ligne cardio : 30 min dans reps, 5 km dans poids
    fake.table("history").insert({
        "user_id": USER_ID, "date": "2026-09-14", "seance": "Push",
        "exercice": "CARDIO:Course", "serie": 1, "reps": 30, "poids": 5.0}).execute()


def test_le_tonnage_admin_sans_la_vue_exclut_le_cardio(fake_db):
    _lignes(fake_db)
    assert db.get_admin_stats()["total_tonnage"] == 500


def test_la_fiche_utilisateur_exclut_le_cardio(fake_db):
    _lignes(fake_db)
    assert db.get_user_details(USER_ID)["total_tonnage"] == 500


def test_la_vue_admin_exclut_le_cardio():
    sql = (PWA / "supabase_schema_v44_cardio_colonnes.sql").read_text(encoding="utf-8")
    vue = sql[sql.index("create or replace view public.admin_history_stats"):]
    vue = vue[:vue.index(";")]
    assert "exercice not like 'CARDIO:%'" in vue


# ── M16 : les commentaires disent ce que fait le code ──────────────────


def _lire(chemin):
    return (PWA / chemin).read_text(encoding="utf-8")


def test_le_catalogue_ne_dit_plus_que_les_reps_ne_sont_pas_stockees():
    """Elles le sont depuis : `build_program` copie `_reps_hint` en `reps`."""
    assert "Les reps ne sont PAS stockées" not in _lire("core/catalog.py")


def test_lonboarding_ne_dit_plus_quil_ecrase_le_programme():
    """Depuis l'audit du 03/10 (I6), refaire l'onboarding AJOUTE un dossier."""
    src = _lire("routes/onboarding.py")
    assert "on écrase\n    #    le programme existant" not in src
    assert "on écrase le programme" not in src
