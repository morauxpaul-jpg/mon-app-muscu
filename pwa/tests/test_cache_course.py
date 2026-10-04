"""Une lecture lente ne remet pas en cache une valeur périmée (vague 4).

Une requête lit la base (cache vide), une autre écrit et invalide, puis la
première remettait en cache l'ANCIENNE valeur, servie jusqu'à 60 s."""
import threading

from core import db_base


def test_lecture_croisee_par_une_ecriture_n_est_pas_mise_en_cache():
    cle = "prog:u-course"
    db_base._cache_invalidate(cle)
    assert db_base._cache_get(cle) is None          # ce fil commence sa lecture
    ecrivain = threading.Thread(target=db_base._cache_invalidate, args=(cle,))
    ecrivain.start(); ecrivain.join()                # une écriture passe entre-temps
    db_base._cache_set(cle, {"ancien": True})        # la lecture se termine
    assert db_base._cache_get(cle) is None           # refusée : périmée


def test_lecture_normale_mise_en_cache():
    cle = "prog:u-normal"
    assert db_base._cache_get(cle) is None
    db_base._cache_set(cle, {"v": 1})
    assert db_base._cache_get(cle) == {"v": 1}
    db_base._cache_set(cle, {"v": 2})                # mise à jour après un succès de lecture
    assert db_base._cache_get(cle) == {"v": 2}


def test_vider_cache_refuse_les_lectures_d_avant():
    cle = "hist:u-vide"
    assert db_base._cache_get(cle) is None
    db_base.vider_cache()
    db_base._cache_set(cle, ["vieux"])
    assert db_base._cache_get(cle) is None
