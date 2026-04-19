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
