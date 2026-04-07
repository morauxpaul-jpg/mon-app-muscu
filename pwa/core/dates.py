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


def monday_of(date_):
    """Lundi de la semaine ISO du jour donné."""
    return date_ - timedelta(days=date_.weekday())


def iso_week(date_):
    return date_.isocalendar().week
