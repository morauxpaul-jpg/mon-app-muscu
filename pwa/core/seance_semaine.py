"""La semaine et le jour, vus depuis l'historique.

De quelle semaine de programme relève une date, quel nom porte un jour, et
quelle séance a réellement été faite ce jour-là. Ces fonctions ne lisent ni
n'écrivent rien : on leur passe l'historique et le programme.

Les noms gardent leur préfixe `_` : ils viennent tels quels de
`routes/seance.py`, et le déplacement a été fait sans en renommer un seul
pour que chaque corps de fonction reste comparable au caractère près.
"""
import logging
from datetime import datetime, timedelta

from core.dates import DAYS_FR, continuous_week
from core.hist import is_logged as _is_real_perf
from core.muscu import fix_muscle, get_base_name

logger = logging.getLogger(__name__)

def _normalize_hist(hist, prog):
    """Corrige le muscle de chaque ligne d'historique, sur place.

    Le muscle vient du programme quand il y est renseigné, sinon de ce que
    la ligne portait déjà, sinon de la déduction par le nom. Retourne
    `(hist, séances du programme)`.

    `routes/accueil.py` en avait sa propre copie, qui avait divergé sur un
    détail : un exercice du programme dont le muscle était vide effaçait
    celui de l'historique d'un côté, pas de l'autre. C'est la version
    prudente qui est gardée.
    """
    prog_seances = {k: v for k, v in prog.items() if not k.startswith("_")}
    muscle_mapping = {ex["name"]: ex.get("muscle", "Autre")
                      for s in prog_seances for ex in prog_seances[s]}
    # Un an d'entraînement, c'est ~2 000 lignes pour une vingtaine d'exercices
    # distincts. `fix_muscle` peut passer une soixantaine de règles de mots-clés
    # sur le nom : le refaire à chaque ligne, c'est des dizaines de milliers de
    # comparaisons pour vingt réponses différentes. On les retient.
    #
    # La clé porte le muscle DÉJÀ noté autant que le nom : `fix_muscle` ne
    # recalcule que si la valeur existante est vide ou héritée, donc deux
    # lignes du même exercice peuvent légitimement donner deux résultats.
    connus = {}
    for r in hist:
        cle = (r["Exercice"], r["Muscle"])
        muscle = connus.get(cle)
        if muscle is None:
            mappe = muscle_mapping.get(get_base_name(r["Exercice"]))
            # Un exercice du programme sans muscle renseigné n'efface pas
            # celui de l'historique : `fix_muscle` saura le déduire si besoin.
            muscle = fix_muscle(r["Exercice"], mappe if mappe else r["Muscle"])
            connus[cle] = muscle
        r["Muscle"] = muscle
    return hist, prog_seances


def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _iso_week(date_):
    # Index de semaine CONTINU (ancré 2024-01-01) — le n° ISO recommençait
    # chaque année et faisait collisionner l'historique au-delà d'un an.
    return continuous_week(date_)


def _display_week(target_date, prog, hist):
    """Semaine relative au début du programme (1-based).
    Utilise _started_at du programme, sinon la date de la 1ère séance."""
    started = prog.get("_started_at")
    if started:
        try:
            start = datetime.strptime(started, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            start = None
    else:
        start = None
    if start is None:
        # Repli : la date de la première séance. On ne l'enregistre PAS.
        #
        # Cette fonction est appelée par /accueil et /seance, deux GET que
        # `prefetch.js` déclenche au simple effleurement du lien. Le
        # `save_prog` qui vivait ici était la troisième écriture pendant un
        # GET, après les badges et le record de streak (cf.
        # tests/test_ecritures_pendant_get.py) — elle avait survécu au
        # correctif parce qu'elle se cachait dans un helper d'affichage,
        # derrière un import paresseux.
        #
        # Rien n'est perdu : `routes/progres.py:_compute_start_monday` fait
        # le même calcul sans rien graver, et les programmes créés depuis
        # l'onboarding portent déjà `_started_at` (routes/onboarding.py).
        dates = []
        for r in hist:
            d = r.get("Date")
            if d:
                try:
                    dates.append(datetime.strptime(d, "%Y-%m-%d").date())
                except (ValueError, TypeError):
                    pass
        start = min(dates) if dates else target_date
    start_monday = start - timedelta(days=start.weekday())
    target_monday = target_date - timedelta(days=target_date.weekday())
    return max(1, (target_monday - start_monday).days // 7 + 1)


def _date_label(date_):
    return f"{DAYS_FR[date_.weekday()]} {date_.day:02d}/{date_.month:02d}/{date_.year}"


def _find_done_session(date_iso, hist):
    """Si une séance a été effectivement réalisée ce jour-là, retourne son nom."""
    day_rows = [r for r in hist if r["Date"] == date_iso]
    real = [r for r in day_rows if _is_real_perf(r)]
    if not real:
        return None
    counts = {}
    for r in real:
        counts.setdefault(r["Séance"], set()).add(r["Exercice"])
    return max(counts.items(), key=lambda kv: len(kv[1]))[0]
