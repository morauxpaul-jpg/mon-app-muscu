"""Compression gzip des réponses texte.

L'app n'en faisait aucune (audit du 03/10, Q2) : la page de séance pesait
180 ko sur le réseau, 21 ko une fois compressée — la différence se paie en
salle, sur une 4G faible. Bibliothèque standard, pas de dépendance.

Ce qui n'est PAS compressé : les flux (le coach répond en SSE, chaque
morceau doit partir tout de suite), les réponses déjà encodées, les petites
(< 1 ko, le gain ne couvre pas l'en-tête), les codes autres que 200, et les
types déjà compressés (images, vidéos, polices woff2).
"""
import gzip

TYPES = {"text/html", "text/css", "text/plain", "text/javascript", "application/javascript",
         "application/json", "application/manifest+json", "image/svg+xml", "text/csv"}
TAILLE_MIN = 1024
NIVEAU = 6


def compresser(request, response):
    if response.status_code != 200 or response.headers.get("Content-Encoding"):
        return response
    if response.mimetype not in TYPES or response.mimetype == "text/event-stream":
        return response
    if "gzip" not in (request.headers.get("Accept-Encoding") or "").lower():
        return response
    if response.is_streamed and not response.direct_passthrough:
        return response                      # générateur : un flux, on le laisse filer
    response.direct_passthrough = False      # fichier statique : on lit son contenu
    data = response.get_data()
    if len(data) < TAILLE_MIN:
        return response
    response.set_data(gzip.compress(data, compresslevel=NIVEAU))
    response.headers["Content-Encoding"] = "gzip"
    response.headers["Content-Length"] = str(len(response.get_data()))
    vary = response.headers.get("Vary")
    if not vary:
        response.headers["Vary"] = "Accept-Encoding"
    elif "accept-encoding" not in vary.lower():
        response.headers["Vary"] = vary + ", Accept-Encoding"
    # Un ETag fort décrit le contenu NON compressé : on le rend faible pour
    # qu'un cache ne serve pas l'un à la place de l'autre.
    etag = response.headers.get("ETag")
    if etag and not etag.startswith("W/"):
        response.headers["ETag"] = "W/" + etag
    return response
