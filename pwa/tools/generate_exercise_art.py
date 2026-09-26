# -*- coding: utf-8 -*-
"""Génère les illustrations d'exercices via l'API Gemini.

Générer 87 images une par une dans une fenêtre de chat, c'est trois heures
de copier-coller — et la cohérence se perd en route, parce qu'on oublie de
rejoindre l'image de référence. Ici la référence est jointe à CHAQUE appel :
c'est elle qui tient le style sur 87 images.

    # 1. Une clé gratuite sur https://aistudio.google.com/apikey
    # 2. La première image sert de référence à toutes les autres
    cd pwa
    python tools/generate_exercise_art.py --cle VOTRE_CLE \\
        --reference static/img/exercises/arnold-press.webp \\
        --sortie ../art_genere

Le script est REPRENABLE : il saute ce qui existe déjà. Coupez-le, relancez-
le, il continue. En cas de dépassement de quota il attend et réessaie au
lieu d'abandonner la file.

Vérifiez les images avant de les importer : un modèle se trompe souvent sur
les articulations et le matériel, et une illustration fausse apprend un
mauvais geste.
"""
import argparse
import base64
import io
import json
import mimetypes
import os
import sys

# La console Windows est en cp1252 : sans ça, un simple accent dans un
# message fait planter le script après que le travail est fait.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import time
import urllib.error
import urllib.request

RACINE = os.path.dirname(__file__)
PROMPTS = os.path.join(RACINE, "exercise_prompts.json")
MODELE = "gemini-2.5-flash-image"
URL = "https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"

PAUSE = 4.0          # secondes entre deux images, pour rester sous le quota gratuit
ATTENTE_QUOTA = 65   # secondes après un 429
ESSAIS = 3


def _resume_quota(corps):
    """Traduit le corps d'un 429 en une phrase utile."""
    try:
        erreur = json.loads(corps).get("error", {})
    except ValueError:
        return "quota atteint (réponse illisible)"
    message = erreur.get("message", "")
    details = " ".join(json.dumps(d) for d in erreur.get("details", []))
    # Les libellés de quota s'écrivent tantôt « per minute », tantôt
    # « per_minute » : on normalise avant de chercher.
    blob = (message + " " + details).lower().replace("_", " ")
    if "per day" in blob or "perday" in blob or "daily" in blob:
        return ("quota JOURNALIER atteint : inutile d'attendre, il repart "
                "demain (ou activez la facturation).")
    if "per minute" in blob or "perminute" in blob:
        return "quota par minute atteint : l'attente suffit."
    if "billing" in blob or "not available" in blob or "free" in blob:
        return ("ce modèle n'est pas accessible sur le palier gratuit de ce "
                "projet : il faut activer la facturation.")
    return "quota atteint : " + (message[:160] or "sans détail")


def _reference(chemin):
    """L'image de style, encodée pour être jointe à chaque requête."""
    if not chemin:
        return None
    mime = mimetypes.guess_type(chemin)[0] or "image/png"
    with open(chemin, "rb") as f:
        return {"inline_data": {"mime_type": mime,
                                "data": base64.b64encode(f.read()).decode()}}


def _demander(cle, prompt, reference, modele=MODELE):
    """Renvoie les octets de l'image, ou lève une erreur explicite."""
    parties = [{"text": prompt}]
    if reference:
        # La consigne de cohérence accompagne la référence : sans elle, le
        # modèle s'inspire de l'image au lieu d'en reprendre le style.
        parties.insert(0, {"text": "Same character, same style, same lighting, "
                                   "same framing and same background as the "
                                   "reference image."})
        parties.append(reference)

    corps = json.dumps({"contents": [{"parts": parties}]}).encode()
    requete = urllib.request.Request(
        URL.format(modele=modele) + "?key=" + cle,
        data=corps, headers={"Content-Type": "application/json"})

    with urllib.request.urlopen(requete, timeout=180) as reponse:
        charge = json.loads(reponse.read().decode())

    for candidat in charge.get("candidates") or []:
        for partie in (candidat.get("content") or {}).get("parts") or []:
            donnees = partie.get("inlineData") or partie.get("inline_data")
            if donnees and donnees.get("data"):
                return base64.b64decode(donnees["data"])

    # Pas d'image : on rend la réponse brute plutôt qu'un « échec » opaque.
    raise RuntimeError("aucune image dans la réponse : "
                       + json.dumps(charge)[:600])


def generer(cle, sortie, reference=None, modele=MODELE, seulement=None):
    os.makedirs(sortie, exist_ok=True)
    entrees = json.loads(io.open(PROMPTS, encoding="utf-8").read())
    if seulement:
        entrees = [e for e in entrees if e["fichier"] in seulement
                   or e["nom"] in seulement][:len(seulement)]

    ref = _reference(reference)
    faits = ignores = echecs = 0

    for i, entree in enumerate(entrees, 1):
        chemin = os.path.join(sortie, entree["fichier"])
        if os.path.exists(chemin):
            ignores += 1
            continue

        for essai in range(1, ESSAIS + 1):
            try:
                image = _demander(cle, entree["prompt"], ref, modele)
                with open(chemin, "wb") as f:
                    f.write(image)
                faits += 1
                print(f"  [{i}/{len(entrees)}] {entree['nom']}")
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    # Un 429 ne dit pas la même chose selon le quota touché :
                    # « par minute » s'attend, « par jour » ou « modèle non
                    # disponible » ne s'attendent pas. Sans le détail, on
                    # relance indéfiniment une requête qui ne passera jamais.
                    detail = e.read().decode(errors="replace")
                    if essai == 1:
                        print("  " + _resume_quota(detail))
                    if essai == ESSAIS:
                        print("  Abandon : ce quota ne se libère pas en attendant.")
                        print("  Réponse complète de Google :")
                        print(detail[:900])
                        echecs += 1
                        break
                    print(f"  nouvelle tentative dans {ATTENTE_QUOTA} s "
                          f"({essai}/{ESSAIS - 1})…")
                    time.sleep(ATTENTE_QUOTA)
                    continue
                detail = e.read().decode(errors="replace")[:400]
                print(f"  ÉCHEC {entree['nom']} : HTTP {e.code} {detail}")
                echecs += 1
                break
            except Exception as e:
                if essai == ESSAIS:
                    print(f"  ÉCHEC {entree['nom']} : {e}")
                    echecs += 1
                else:
                    time.sleep(3 * essai)
        time.sleep(PAUSE)

    return faits, ignores, echecs


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cle", default=os.environ.get("GEMINI_API_KEY"),
                   help="clé API (ou variable d'environnement GEMINI_API_KEY)")
    p.add_argument("--sortie", default="../art_genere", help="dossier de destination")
    p.add_argument("--reference", help="image dont reprendre le style")
    p.add_argument("--modele", default=MODELE)
    p.add_argument("--un", action="append", dest="seulement",
                   help="ne générer que cet exercice (répétable) — pour essayer")
    a = p.parse_args()

    if not a.cle:
        print("Clé manquante : --cle, ou GEMINI_API_KEY dans l'environnement.")
        print("Une clé gratuite s'obtient sur https://aistudio.google.com/apikey")
        raise SystemExit(1)

    faits, ignores, echecs = generer(a.cle, a.sortie, a.reference, a.modele, a.seulement)
    print(f"\n{faits} générée(s), {ignores} déjà présente(s), {echecs} en échec")
    print(f"Images dans {os.path.abspath(a.sortie)}")
    if faits:
        print("Regardez-les, puis : python tools/import_exercise_art.py "
              + os.path.abspath(a.sortie))
