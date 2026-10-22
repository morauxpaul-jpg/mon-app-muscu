"""Photos de progression (PRO) — ce qui se calcule sans base ni Flask.

Demande du propriétaire (18/10/2026) : « des images de son corps pour voir
l'évolution ». Choix faits avec lui : rangées sur le serveur, en privé ;
classées par angle (face, profil, dos) ; comparaison avant / après ; poids
du jour sous la photo ; rappel toutes les 4 semaines.

La table et les fichiers sont dans core/db_photos.py, la page dans
routes/corps.py (onglet « Corps » de Progrès, avec le poids).
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


# Segments retirés : APP1 (EXIF et XMP : position GPS, appareil, date
# exacte), APP13 (IPTC) et les commentaires. Le profil couleur (APP2
# « ICC_PROFILE ») reste ; l'index MPF (APP2 aussi) part avec les images
# qu'il désigne, rangées après la fin de la principale.
_SEGMENTS_RETIRES = {0xE1, 0xED, 0xFE}


def sans_metadonnees(octets):
    """Le JPEG sans ses métadonnées, ou None s'il est mal formé.

    Le navigateur réduit déjà la photo et perd l'EXIF en la redessinant
    (canvas), mais le serveur lui faisait confiance : un envoi hors de l'app
    gardait la position de la prise de vue (audit du 18/10, m12). Pillow
    n'est pas en production (requirements-dev.txt) : on parcourt les
    segments à la main, jusqu'au début des données de l'image, recopiées
    telles quelles jusqu'à la fin de l'image (FFD9 ne peut pas apparaître
    dans les données : un octet FF y est toujours suivi de 00)."""
    if not est_jpeg(octets):
        return None
    octets = bytes(octets)
    n = len(octets)
    sortie = bytearray(b"\xff\xd8")
    i = 2
    while i + 4 <= n:
        if octets[i] != 0xFF:
            return None
        marqueur = octets[i + 1]
        if marqueur == 0xFF:                       # octet de remplissage
            i += 1
            continue
        if marqueur == 0xD9 or 0xD0 <= marqueur <= 0xD7 or marqueur in (0x00, 0x01):
            return None                            # fin ou marqueur isolé avant l'image
        longueur = (octets[i + 2] << 8) | octets[i + 3]
        fin = i + 2 + longueur
        if longueur < 2 or fin > n:
            return None
        if marqueur == 0xDA:                       # début des données de l'image
            fin_image = octets.find(b"\xff\xd9", fin)
            return bytes(sortie + (octets[i:] if fin_image < 0 else octets[i:fin_image + 2]))
        corps = octets[i + 4:fin]
        mpf = marqueur == 0xE2 and corps.startswith(b"MPF\x00")
        if marqueur not in _SEGMENTS_RETIRES and not mpf:
            sortie += octets[i:fin]
        i = fin
    return None


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


def index_pesees(pesees) -> list:
    """[('2026-10-16', 91.2), …] de la plus ancienne à la plus récente."""
    out = {}
    for p in pesees or []:
        d, kg = str(p.get("date") or "")[:10], p.get("poids_kg")
        try:
            if d and kg is not None:
                out[d] = round(float(kg), 1)
        except (TypeError, ValueError):
            continue
    return sorted(out.items())


def pesee_pour(index: list, jour: str):
    """La pesée à afficher sous une photo du `jour` : celle du jour même,
    sinon la dernière d'avant (choix du propriétaire, 18/10 : « afficher la
    dernière pesée », rien d'inventé). (kg, date ISO de la pesée) ou
    (None, None) sans pesée jusqu'à ce jour."""
    avant = [(d, kg) for d, kg in index if d <= jour]
    if not avant:
        return None, None
    d, kg = avant[-1]
    return kg, d


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


def fiche(p: dict, pesees: list) -> dict:
    """Ce que la page affiche d'une photo. `kg_le` : la date de la pesée
    quand elle n'est pas du jour de la photo (« pesée du 16/10 »)."""
    d = str(p.get("date") or "")[:10]
    kg, le = pesee_pour(pesees, d)
    return {
        "id": p.get("id"), "date": d, "date_fr": f"{d[8:10]}/{d[5:7]}/{d[0:4]}",
        "angle": p.get("angle"), "libelle": LIBELLES.get(p.get("angle"), ""),
        "kg": kg, "kg_le": f"{le[8:10]}/{le[5:7]}" if le and le != d else "", "pesee": le,
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
        # Les deux photos reprennent la même pesée : leur écart ne dit rien.
        "ecart_poids": ecart_poids(avant["kg"], apres["kg"]) if avant["pesee"] != apres["pesee"] else "",
    }


PESEE_RECENTE_JOURS = 7


def pesee_manquante(photos, pesees: list, aujourdhui):
    """L'invitation à se peser, par date et non par photo (demande du
    propriétaire, 18/10 : « on ne pense pas forcément à se peser »). Pour la
    photo la plus récente, prise il y a 7 jours au plus, si aucune pesée
    n'est notée ce jour-là : {date, date_fr, derniere: (kg, 'jj/mm') | None}.
    Sinon None : de vieilles photos importées ne réclament rien."""
    jours = sorted({str(p.get("date") or "")[:10] for p in photos or []})
    if not jours:
        return None
    jour = jours[-1]
    n = jours_sans_photo(jour, aujourdhui)
    if n is None or not 0 <= n <= PESEE_RECENTE_JOURS or any(d == jour for d, _ in pesees):
        return None
    kg, le = pesee_pour(pesees, jour)
    return {"date": jour, "date_fr": f"{jour[8:10]}/{jour[5:7]}",
            "derniere": (kg, f"{le[8:10]}/{le[5:7]}") if kg is not None else None}


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
        "url": "/progres/corps#photos",
        "tag": "photos-rappel",
    }
