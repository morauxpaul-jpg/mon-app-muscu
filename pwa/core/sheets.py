"""Connexion Google Sheets — même Sheet 'Muscu_App' que le Streamlit d'origine."""
import os
import json
import gspread

_SHEET_NAME = "Muscu_App"
_cache = {"gc": None, "ws_h": None, "ws_p": None}


def _load_credentials():
    """Lit les credentials depuis l'env.

    Supporte :
    1. GOOGLE_CREDENTIALS : le JSON complet du service account (nouvelle variable)
    2. GCP_* : les variables individuelles utilisées par le Streamlit existant sur Render
    """
    raw = os.getenv("GOOGLE_CREDENTIALS")
    if raw:
        return json.loads(raw)

    if os.getenv("GCP_PROJECT_ID"):
        return {
            "type": os.getenv("GCP_TYPE", "service_account"),
            "project_id": os.getenv("GCP_PROJECT_ID"),
            "private_key_id": os.getenv("GCP_PRIVATE_KEY_ID"),
            "private_key": os.getenv("GCP_PRIVATE_KEY", "").replace("\\n", "\n"),
            "client_email": os.getenv("GCP_CLIENT_EMAIL"),
            "client_id": os.getenv("GCP_CLIENT_ID"),
            "auth_uri": os.getenv("GCP_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
            "token_uri": os.getenv("GCP_TOKEN_URI", "https://oauth2.googleapis.com/token"),
            "auth_provider_x509_cert_url": os.getenv("GCP_AUTH_PROVIDER_CERT", "https://www.googleapis.com/oauth2/v1/certs"),
            "client_x509_cert_url": os.getenv("GCP_CLIENT_CERT"),
        }

    # Fallback local : fichier credentials.json dans /pwa/
    local = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")
    if os.path.exists(local):
        with open(local, "r", encoding="utf-8") as f:
            return json.load(f)

    raise RuntimeError("Aucun credential Google trouvé (GOOGLE_CREDENTIALS, GCP_*, ou credentials.json).")


def get_worksheets():
    """Retourne (ws_historique, ws_programme). Cache process-wide."""
    if _cache["ws_h"] is None:
        creds = _load_credentials()
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open(_SHEET_NAME)
        _cache["gc"] = gc
        _cache["ws_h"] = sh.get_worksheet(0)
        _cache["ws_p"] = sh.worksheet("Programme")
    return _cache["ws_h"], _cache["ws_p"]


def get_prog():
    """Programme (dict) depuis la cellule A1 de l'onglet Programme."""
    try:
        _, ws_p = get_worksheets()
        raw = ws_p.acell("A1").value or "{}"
        return json.loads(raw)
    except Exception:
        return {}


def save_prog(prog_dict):
    _, ws_p = get_worksheets()
    ws_p.update_acell("A1", json.dumps(prog_dict))


def get_hist():
    """Historique des séries sous forme de liste de dicts (équivalent df_h en Streamlit)."""
    try:
        ws_h, _ = get_worksheets()
        rows = ws_h.get_all_records()
    except Exception:
        return []

    cleaned = []
    for r in rows:
        try:
            poids = float(str(r.get("Poids", 0) or 0).replace(",", "."))
        except (ValueError, TypeError):
            poids = 0.0
        try:
            reps = int(float(r.get("Reps", 0) or 0))
        except (ValueError, TypeError):
            reps = 0
        try:
            semaine = int(float(r.get("Semaine", 1) or 1))
        except (ValueError, TypeError):
            semaine = 1
        cleaned.append({
            "Semaine": semaine,
            "Séance": str(r.get("Séance", "")),
            "Exercice": str(r.get("Exercice", "")),
            "Série": r.get("Série", ""),
            "Reps": reps,
            "Poids": poids,
            "Remarque": str(r.get("Remarque", "")),
            "Muscle": str(r.get("Muscle", "")),
            "Date": str(r.get("Date", "")),
        })
    return cleaned


def save_hist(rows):
    """Écrase l'onglet historique avec la liste de dicts fournie."""
    ws_h, _ = get_worksheets()
    headers = ["Semaine", "Séance", "Exercice", "Série", "Reps", "Poids", "Remarque", "Muscle", "Date"]
    data = [headers]
    for r in rows:
        data.append([r.get(h, "") if r.get(h, "") is not None else "" for h in headers])
    ws_h.clear()
    ws_h.update(data, value_input_option="USER_ENTERED")
