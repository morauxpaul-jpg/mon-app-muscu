"""Helpers date — fuseau horaire Europe/Paris (identique au Streamlit d'origine)."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PARIS_TZ = ZoneInfo("Europe/Paris")

DAYS_FR = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
MONTHS_FR = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
             "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]


def now_paris():
    return datetime.now(PARIS_TZ)


def today_paris():
    return now_paris().date()


def today_paris_str():
    return today_paris().strftime("%Y-%m-%d")


# ── Tolérance "journée logique" ────────────────────────────────
# Une séance faite entre 00h00 et 04h00 est considérée comme appartenant
# à la veille (cas typique : "je fais ma séance du lundi le mardi à 1h du
# matin"). Seuils bas pour ne pas impacter les réveils matinaux normaux.
LOGICAL_DAY_CUTOFF_HOUR = 4


def logical_today_paris():
    """Date « logique » : retourne la veille si l'heure locale est
    avant 04h00 (permet de logguer une séance faite « tard hier soir »
    sans qu'elle soit rangée au mauvais jour)."""
    now = now_paris()
    if now.hour < LOGICAL_DAY_CUTOFF_HOUR:
        return (now - timedelta(days=1)).date()
    return now.date()


def logical_today_paris_str():
    return logical_today_paris().strftime("%Y-%m-%d")


def monday_of(date_):
    """Lundi de la semaine ISO du jour donné."""
    return date_ - timedelta(days=date_.weekday())


def iso_week(date_):
    return date_.isocalendar().week


# ── Semaine continue ───────────────────────────────────────────
# Le n° de semaine ISO (1-53) recommence chaque année : la semaine 23 de 2025
# et celle de 2026 sont indistinguables, ce qui mélange l'historique au-delà
# d'un an et casse le streak / « dernière fois » au passage du Nouvel An.
# On utilise donc un index de semaine CONTINU, ancré sur le lundi 2024-01-01 :
# il croît indéfiniment et ne collisionne jamais. Le n° affiché à l'utilisateur
# reste relatif au début de son programme (cf. _display_week / _rel_week).
from datetime import date as _date

WEEK_EPOCH = _date(2024, 1, 1)  # un lundi


def continuous_week(date_) -> int:
    """Index de semaine continu (1-based) depuis WEEK_EPOCH (lun→dim)."""
    return (monday_of(date_) - WEEK_EPOCH).days // 7 + 1


def week_range(date_):
    """(lundi, dimanche) de la semaine contenant la date — bornes ISO str."""
    monday = monday_of(date_)
    sunday = monday + timedelta(days=6)
    return monday.isoformat(), sunday.isoformat()
