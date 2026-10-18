"""Photos de progression (PRO) — ce qui se calcule sans base ni Flask.

Demande du propriétaire (18/10/2026) : « des images de son corps pour voir
l'évolution ». Choix faits avec lui : rangées sur le serveur, en privé ;
classées par angle (face, profil, dos) ; comparaison avant / après ; poids
du jour sous la photo ; rappel toutes les 4 semaines.

La table et les fichiers sont dans core/db_photos.py, la page dans
routes/photos.py.
"""
from datetime import date

ANGLES = ("face", "profil", "dos")
LIBELLES = {"face": "Face", "profil": "Profil", "dos": "Dos"}

# Le navigateur réduit la photo avant l'envoi (1 600 px, JPEG ≈ 300 Ko) :
# 2 Mo laisse de la marge sans ouvrir la porte à un fichier brut de 12 Mo.
OCTETS_MAX = 2 * 1024 * 1024
# Une photo par angle chaque semaine pendant deux ans et demi.
PHOTOS_MAX = 400
# Les photos plus anciennes que 1990 sont une date mal tapée, pas un souvenir.
DATE_MIN = date(1990, 1, 1)

RAPPEL_JOURS = 28
RAPPELS_MAX = 3      # 4, 8 et 12 semaines sans photo, puis on se tait


def angle_valide(valeur):
    a = str(valeur or "").strip().lower()
    return a if a in ANGLES else None


def date_valide(valeur, aujourdhui):
    """La date d'une photo : pas dans le futur (une photo de demain n'existe
    pas), pas avant DATE_MIN. None si illisible."""
    try:
        d = date.fromisoformat(str(valeur or "")[:10])
    except ValueError:
        return None
    return d if DATE_MIN <= d <= aujourdhui else None


def est_jpeg(octets) -> bool:
    """Le fichier commence comme un JPEG. Le navigateur envoie toujours du
    JPEG (canvas.toBlob) ; tout le reste est refusé, et le fichier est
    resservi tel quel avec `nosniff` : il ne peut pas devenir une page."""
    return isinstance(octets, (bytes, bytearray)) and len(octets) > 3 and octets[:3] == b"\xff\xd8\xff"


def ecart(avant, apres) -> str:
    """« 3 jours », « 8 semaines », « 5 mois », « 1 an et 2 mois »."""
    jours = abs((apres - avant).days)
    if jours == 0:
        return "même jour"
    if jours < 14:
        return f"{jours} jour{'s' if jours > 1 else ''}"
    if jours < 61:
        return f"{round(jours / 7)} semaines"
    mois = round(jours / 30.44)
    if mois < 12:
        return f"{mois} mois"
    ans, reste = divmod(mois, 12)
    texte = f"{ans} an{'s' if ans > 1 else ''}"
    return f"{texte} et {reste} mois" if reste else texte


def poids_par_date(pesees) -> dict:
    """{'2026-10-18': 91.4} : la pesée du jour, sous la photo du même jour."""
    out = {}
    for p in pesees or []:
        d, kg = str(p.get("date") or "")[:10], p.get("poids_kg")
        try:
            if d and kg is not None:
                out[d] = round(float(kg), 1)
        except (TypeError, ValueError):
            continue
    return out


def ecart_poids(avant, apres):
    """« −3,2 kg » entre deux pesées, ou "" s'il en manque une."""
    if avant is None or apres is None:
        return ""
    d = round(apres - avant, 1)
    if d == 0:
        return "même poids"
    return ("+" if d > 0 else "−") + f"{abs(d):.1f}".replace(".", ",") + " kg"


def par_angle(photos) -> dict:
    """{angle: [photos de la plus ancienne à la plus récente]}."""
    out = {a: [] for a in ANGLES}
    for p in photos or []:
        if p.get("angle") in out:
            out[p["angle"]].append(p)
    for liste in out.values():
        liste.sort(key=lambda p: (str(p.get("date")), p.get("id") or 0))
    return out


def fiche(p: dict, poids: dict) -> dict:
    """Ce que la page affiche d'une photo."""
    d = str(p.get("date") or "")[:10]
    return {
        "id": p.get("id"), "date": d, "date_fr": f"{d[8:10]}/{d[5:7]}/{d[0:4]}",
        "angle": p.get("angle"), "libelle": LIBELLES.get(p.get("angle"), ""),
        "kg": poids.get(d),
        "mini": f"/progres/photos/{p.get('id')}/image?mini=1",
        "image": f"/progres/photos/{p.get('id')}/image",
    }


def _choisie(liste, valeur, defaut):
    try:
        cle = int(valeur)
    except (TypeError, ValueError):
        return defaut
    return next((p for p in liste if p["id"] == cle), defaut)


def comparaison(liste: list, avant_id=None, apres_id=None):
    """Avant / après parmi les fiches d'un angle (de la plus ancienne à la
    plus récente) : la première et la dernière, sauf choix dans l'adresse.
    Toujours rendues dans l'ordre des dates. None sous deux photos."""
    if len(liste) < 2:
        return None
    avant = _choisie(liste, avant_id, liste[0])
    apres = _choisie(liste, apres_id, liste[-1])
    if avant["date"] > apres["date"]:
        avant, apres = apres, avant
    return {
        "avant": avant, "apres": apres,
        "ecart": ecart(date.fromisoformat(avant["date"]), date.fromisoformat(apres["date"])),
        "ecart_poids": ecart_poids(avant["kg"], apres["kg"]),
    }


def resume(photos: list, aujourdhui) -> dict:
    """Le bloc « Photos » de la page Progrès : combien, la dernière, et s'il
    est temps d'en reprendre. `photos` : les plus récentes d'abord."""
    if not photos:
        return {"dispo": True, "total": 0}
    derniere = fiche(photos[0], {})
    jours = jours_sans_photo(derniere["date"], aujourdhui)
    return {"dispo": True, "total": len(photos), "derniere": derniere,
            "a_reprendre": jours is not None and jours >= RAPPEL_JOURS}


def jours_sans_photo(derniere, aujourdhui):
    try:
        d = date.fromisoformat(str(derniere or "")[:10])
    except ValueError:
        return None
    return (aujourdhui - d).days


def rappel_du_jour(derniere, aujourdhui) -> bool:
    """Toutes les 4 semaines depuis la dernière photo, trois fois au plus.
    Sans état : le rappel tombe le jour où l'écart est un multiple de 28,
    et une nouvelle photo remet le compte à zéro."""
    n = jours_sans_photo(derniere, aujourdhui)
    return n is not None and n > 0 and n % RAPPEL_JOURS == 0 and n <= RAPPEL_JOURS * RAPPELS_MAX


def payload_rappel(jours: int) -> dict:
    semaines = jours // 7
    return {
        "title": "Tes photos de progression",
        "body": f"{semaines} semaines depuis les dernières : reprends-les, même lumière, même pose.",
        "url": "/progres/photos",
        "tag": "photos-rappel",
    }
