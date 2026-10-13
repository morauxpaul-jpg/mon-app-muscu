"""Page Progrès, style « Instrument » : la liste « Mes exercices » et sa
mini-courbe (core/exercise_stats.resume_mouvement)."""
import re

from conftest import USER_ID
from core.exercise_stats import resume_mouvement


def _serie(date, exo, poids, reps, serie=1):
    return {"Date": date, "Exercice": exo, "Poids": poids, "Reps": reps, "Série": serie,
            "Séance": "Push", "Remarque": "", "RPE": None}


def test_une_ligne_porte_la_force_estimee_recente_et_ses_barres():
    hist = [_serie("2026-06-01", "Développé couché", 80, 8),          # 101,3
            _serie("2026-06-04", "Développé couché (Barre)", 80, 10),  # 106,7 (variante : même mouvement)
            _serie("2026-06-08", "Développé couché", 82.5, 9)]         # 107,3
    r = resume_mouvement(hist, "Développé couché")
    assert r["sessions"] == 3 and r["derniere"] == "8 juin"
    assert r["valeur"] == 107.2 and not r["au_pdc"]
    assert r["barres"][0] == 35 and r["barres"][-1] == 100      # du plus bas au plus haut
    assert r["nouveau_haut"] is True


def test_au_poids_du_corps_on_suit_les_repetitions():
    hist = [_serie("2026-06-01", "Tractions", 0, 10), _serie("2026-06-05", "Tractions", 0, 8)]
    r = resume_mouvement(hist, "Tractions")
    assert r["au_pdc"] and r["valeur"] == 8
    assert r["nouveau_haut"] is False                            # 8 ne bat pas 10


def test_dips_au_poids_du_corps_apres_une_seance_lestee():
    """Relu sur le vrai compte : des dips lestés (10 kg) puis au poids du
    corps affichaient « 0 ». On suit les répétitions des séances du même
    genre que la dernière."""
    hist = [_serie("2026-08-24", "Dips", 0, 10), _serie("2026-08-31", "Dips (Lesté)", 10, 10),
            _serie("2026-09-08", "Dips", 0, 24), _serie("2026-10-04", "Dips", 0, 10)]
    r = resume_mouvement(hist, "Dips")
    assert r["au_pdc"] and r["valeur"] == 10
    assert r["sessions"] == 4 and len(r["barres"]) == 3       # la séance lestée est à part


def test_une_seule_seance_donne_une_barre_mediane_et_aucun_record():
    r = resume_mouvement([_serie("2026-06-01", "Squat", 100, 5)], "Squat")
    assert r["barres"] == [70] and r["nouveau_haut"] is False
    assert resume_mouvement([], "Squat") is None


def test_la_page_progres_liste_les_exercices_avec_leur_valeur(fake_db, logged_in):
    for i, (d, p) in enumerate([("2026-06-01", 80), ("2026-06-08", 85)]):
        fake_db.table("history").insert({"user_id": USER_ID, "semaine": 1 + i, "seance": "Push",
                                         "exercice": "Développé couché", "serie": 1, "reps": 5,
                                         "poids": p, "date": d, "muscle": "Pecs"}).execute()
    html = logged_in.get("/progres").get_data(as_text=True)
    ligne = re.search(r'<a class="prg-exo" href="/progres/exercice\?exo=D%C3%A9velopp%C3%A9%20couch%C3%A9">(.*?)</a>',
                      html, re.S)
    assert ligne, "ligne « Développé couché » absente"
    assert "2 séances · 8 juin" in ligne.group(1)
    assert "99,2" in ligne.group(1)                              # 85 × (1 + 5/30)
    assert "prg-barre--haut" in ligne.group(1)
