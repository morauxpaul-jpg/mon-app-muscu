# -*- coding: utf-8 -*-
"""Génère les illustrations d'exercices via l'API Gemini.

Générer 87 images une par une dans une fenêtre de chat, c'est trois heures
de copier-coller — et la cohérence se perd en route, parce qu'on oublie de
rejoindre l'image de référence. Ici la référence est jointe à CHAQUE appel :
c'est elle qui tient le style sur 87 images.

En DEUX temps, et pas autrement : la référence gouverne les 86 autres
images, donc elle se regarde avant de lancer la série.

    # 1. Une clé sur https://aistudio.google.com/apikey
    # 2. Une image SEULE, sans référence — c'est elle qui fixera le style
    cd pwa
    python tools/generate_exercise_art.py --cle VOTRE_CLE \\
        --un "Arnold press" --sortie ../art_genere

    # 3. On la REGARDE. Si elle convient, elle sert de modèle au reste
    python tools/generate_exercise_art.py --cle VOTRE_CLE \\
        --reference ../art_genere/arnold-press.png \\
        --sortie ../art_genere

Pour refaire ou compléter le catalogue dans le style existant, une
illustration déjà livrée et JUSTE sert de référence telle quelle :

    python tools/generate_exercise_art.py --modele gemini-3-pro-image \\
        --reference static/img/exercises/squat.webp \\
        --un "Tractions" --limite 1 --sortie ../art_genere

La clé part dans l'en-tête `x-goog-api-key`, jamais dans l'adresse : une
adresse finit dans les journaux, et une clé qui y figure passe AVANT celle
que le réseau ajoute. Sans --cle ni GEMINI_API_KEY, rien n'est envoyé :
c'est le cas d'un environnement qui ajoute lui-même l'en-tête à chaque
requête vers Google (les « Network secrets » d'un environnement cloud).

Le script est REPRENABLE : il saute ce qui existe déjà. Coupez-le, relancez-
le, il continue. En cas de dépassement de quota il attend et réessaie au
lieu d'abandonner la file. Après chaque image, il affiche les jetons
facturés par Google et le coût estimé.

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

from PIL import Image

RACINE = os.path.dirname(__file__)
PROMPTS = os.path.join(RACINE, "exercise_prompts.json")
MODELE = "gemini-2.5-flash-image"
URL = "https://generativelanguage.googleapis.com/v1beta/models/{modele}:generateContent"

PAUSE = 4.0          # secondes entre deux images, pour rester sous le quota gratuit
ATTENTE_QUOTA = 65   # secondes après un 429
ESSAIS = 3

# Dollars par million de jetons : (entrée, sortie texte et réflexion,
# sortie image). Grille publique du palier payant relevée le 14/10/2026 ;
# elle sert à ESTIMER, la facture fait foi. Un modèle absent d'ici affiche
# ses jetons sans estimation plutôt qu'un prix inventé.
TARIFS = {
    "gemini-2.5-flash-image": (0.30, 2.50, 30.0),
    "gemini-3-pro-image": (2.00, 12.0, 120.0),
    "gemini-3-pro-image-preview": (2.00, 12.0, 120.0),
    "gemini-3.1-flash-image": (0.50, 3.00, 60.0),
    "gemini-3.1-flash-image-preview": (0.50, 3.00, 60.0),
}


def _jetons(usage):
    """(entrée, sortie texte et réflexion, sortie image) d'une réponse."""
    usage = usage or {}
    entree = usage.get("promptTokenCount") or 0
    image = sum(d.get("tokenCount") or 0
                for d in usage.get("candidatesTokensDetails") or []
                if d.get("modality") == "IMAGE")
    sortie = (usage.get("candidatesTokenCount") or 0) - image
    return entree, sortie + (usage.get("thoughtsTokenCount") or 0), image


def cout_estime(modele, usage):
    """Dollars estimés pour une réponse, ou None si le tarif est inconnu."""
    tarif = TARIFS.get(modele)
    if not tarif:
        return None
    return sum(n * prix / 1e6 for n, prix in zip(_jetons(usage), tarif))


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


class CleRefusee(Exception):
    """Google a refusé la clé : rien ne sert de continuer la file."""


def _forme_de_cle(cle):
    """Ce que la clé a l'air d'être, avant de la soumettre à Google.

    Une clé API Gemini commence par « AIza ». Un jeton de session AI Studio
    commence par « AQ. » et ne donne PAS accès à cette API : Google répond
    alors 401 « Expected OAuth 2 access token », ce qui n'aide personne à
    comprendre qu'il faut aller chercher une vraie clé.
    """
    cle = (cle or "").strip()
    if cle.startswith("AIza"):
        return None, None
    if cle.startswith("AQ."):
        # Ces jetons FONCTIONNENT, mais quelques heures seulement. On
        # avertit sans bloquer : refuser ce que Google peut accepter serait
        # pire que l'avertissement.
        return None, ("Attention : cette valeur est un jeton de session AI "
                      "Studio (« AQ. »), pas une clé API. Il marche, mais il "
                      "EXPIRE au bout de quelques heures — c'est la cause "
                      "des erreurs 401 qui arrivent sans rien avoir changé. "
                      "Une vraie clé commence par « AIza » et ne périme pas.")
    return ("cette valeur ne ressemble ni à une clé API Gemini (« AIza ») "
            "ni à un jeton AI Studio (« AQ. »)."), None


def _resume_cle(corps, cle_locale=True):
    if not cle_locale:
        return ("Google n'a reçu aucune clé valable. Aucune n'a été donnée "
                "ici (ni --cle, ni GEMINI_API_KEY), et le réseau n'en a pas "
                "ajouté d'utilisable dans l'en-tête x-goog-api-key. Vérifiez "
                "le secret réseau de l'environnement (site autorisé : "
                "generativelanguage.googleapis.com), ou passez --cle.")
    if "OAuth 2 access token" in corps or "UNAUTHENTICATED" in corps:
        return ("clé refusée. Si c'est un jeton AI Studio (« AQ. »), il a "
                "sans doute expiré : ils ne durent que quelques heures. "
                "Prenez une vraie clé sur https://aistudio.google.com/apikey "
                "— elle commence par « AIza » et ne périme pas.")
    if "TA_CLE" in corps or "VOTRE_CLE" in corps:
        return "la commande a été lancée avec le modèle de clé, pas la vôtre."
    return ("clé refusée par Google. Vérifiez --cle, ou laissez tomber "
            "l'option si GEMINI_API_KEY est déjà dans l'environnement.")


def _sans_rouge(chemin):
    """L'image de référence, son muscle rouge effacé.

    La référence est jointe aux 86 autres appels pour tenir le style. Mais
    le modèle recopiait aussi sa zone rouge : tous les exercices sortaient
    avec les épaules en rouge, curl compris. Une phrase le lui interdisant
    n'a pas suffi — alors on enlève le rouge de l'image elle-même. Il ne
    reste rien à recopier, et la seule consigne de couleur qui subsiste est
    celle de l'exercice en cours.

    Le mannequin est gris (r ≈ v ≈ b) : un pixel dont le rouge domine
    franchement les deux autres canaux est du coloriage, pas une ombre.

    Une image au fond transparent (une illustration déjà livrée, un PNG
    détouré) est d'abord posée sur du noir, le fond que demandent les
    prompts. Convertie telle quelle, c'est la couleur cachée sous la
    transparence qui ressortirait : presque noire dans nos WebP, mais
    n'importe laquelle dans un PNG.
    """
    source = Image.open(chemin)
    if "A" in source.getbands():
        fond = Image.new("RGBA", source.size, (0, 0, 0, 255))
        fond.alpha_composite(source.convert("RGBA"))
        source = fond
    im = source.convert("RGB")
    px = im.load()
    largeur, hauteur = im.size
    efface = 0
    for y in range(hauteur):
        for x in range(largeur):
            r, v, b = px[x, y]
            if r - max(v, b) > 8:
                # Le rouge est un canal lumineux : le remplacer par la
                # luminance laisserait une zone plus claire que le reste.
                # Le vert porte déjà la forme sous le coloriage.
                gris = min(int(0.299 * r + 0.587 * v + 0.114 * b), v + 10)
                px[x, y] = (gris, gris, gris)
                efface += 1
    tampon = io.BytesIO()
    im.save(tampon, "PNG")
    return tampon.getvalue(), efface


def _reference(chemin):
    """L'image de style, encodée pour être jointe à chaque requête."""
    if not chemin:
        return None
    octets, efface = _sans_rouge(chemin)
    print(f"  référence : {efface} pixels de coloriage effacés avant envoi")
    return {"inline_data": {"mime_type": "image/png",
                            "data": base64.b64encode(octets).decode()}}


def _demander(cle, prompt, reference, modele=MODELE):
    """Renvoie (octets de l'image, jetons facturés), ou lève une erreur
    explicite. Sans clé, la requête part sans : le réseau l'ajoute."""
    parties = [{"text": prompt}]
    if reference:
        # La référence doit gouverner le STYLE, rien d'autre. Sans ce cadrage,
        # le modèle recopiait aussi sa pose et sa zone musclée en rouge : tous
        # les exercices ressortaient avec les épaules en rouge. Les poses
        # copiées ont surtout été DEBOUT (tractions, rowing barre) : la
        # consigne le nomme.
        parties.insert(0, {"text": "Use the reference image ONLY for the "
                                   "rendering style, the mannequin's look and "
                                   "materials, the lighting and the background. "
                                   "The reference shows one particular "
                                   "exercise with a BARBELL: neither its pose "
                                   "nor its equipment apply here. Draw only "
                                   "the equipment named in the instructions "
                                   "below — if they say dumbbells, there is "
                                   "no bar of any kind in the image. "
                                   "Your pose comes from the instructions "
                                   "below and will usually be completely "
                                   "different: lying, hanging, kneeling or "
                                   "seated when they say so, never standing "
                                   "by default. Do NOT copy its pose. "
                                   "The reference has "
                                   "no coloured muscle; the red area is "
                                   "described in the instructions below and "
                                   "nowhere else."})
        parties.append(reference)

    demande = {"contents": [{"parts": parties}]}
    if modele.startswith("gemini-3"):
        # Carré, et la plus petite taille qui garde du détail : l'import
        # réduit tout à 400 px, une 2K coûterait plus pour rien.
        demande["generationConfig"] = {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": "1:1", "imageSize": "1K"}}
    entetes = {"Content-Type": "application/json"}
    if cle:
        entetes["x-goog-api-key"] = cle
    requete = urllib.request.Request(
        URL.format(modele=modele), data=json.dumps(demande).encode(),
        headers=entetes)

    with urllib.request.urlopen(requete, timeout=300) as reponse:
        charge = json.loads(reponse.read().decode())

    for candidat in charge.get("candidates") or []:
        for partie in (candidat.get("content") or {}).get("parts") or []:
            if partie.get("thought"):
                # Gemini 3 peut joindre des brouillons pendant sa réflexion :
                # seule l'image finale compte.
                continue
            donnees = partie.get("inlineData") or partie.get("inline_data")
            if donnees and donnees.get("data"):
                return (base64.b64decode(donnees["data"]),
                        charge.get("usageMetadata") or {})

    # Pas d'image : on rend la réponse brute plutôt qu'un « échec » opaque.
    raise RuntimeError("aucune image dans la réponse : "
                       + json.dumps(charge)[:600])


def generer(cle, sortie, reference=None, modele=MODELE, seulement=None, limite=None):
    os.makedirs(sortie, exist_ok=True)
    entrees = json.loads(io.open(PROMPTS, encoding="utf-8").read())
    if seulement:
        entrees = [e for e in entrees if e["fichier"] in seulement
                   or e["nom"] in seulement][:len(seulement)]
        # Un nom qui ne correspond à rien donnait « 0 générée, 0 en échec » :
        # le script se taisait, et on croyait avoir lancé la génération.
        # Arrive après l'ajout d'un exercice si les prompts n'ont pas été
        # reconstruits — exactement ce qui vient de se passer.
        trouves = {e["nom"] for e in entrees} | {e["fichier"] for e in entrees}
        inconnus = [n for n in seulement if n not in trouves]
        if inconnus:
            raise SystemExit(
                "Aucun prompt pour : " + ", ".join(inconnus) + "."
                " Soit le nom est mal orthographié, soit l'exercice a"
                " été ajouté depuis la dernière construction des"
                " prompts — dans ce cas :"
                " python tools/build_exercise_prompts.py")

    ref = _reference(reference)
    faits = ignores = echecs = 0
    depense = 0.0

    for i, entree in enumerate(entrees, 1):
        if limite and faits >= limite:
            print(f"  limite de {limite} image(s) atteinte, arrêt volontaire.")
            break
        chemin = os.path.join(sortie, entree["fichier"])
        if os.path.exists(chemin):
            ignores += 1
            continue

        for essai in range(1, ESSAIS + 1):
            try:
                image, usage = _demander(cle, entree["prompt"], ref, modele)
                # Gemini 3 renvoie du JPEG : écrit tel quel, un « .png »
                # contiendrait un JPEG. Réencodé, le nom dit la vérité.
                Image.open(io.BytesIO(image)).save(chemin, "PNG")
                faits += 1
                entree_j, texte_j, image_j = _jetons(usage)
                cout = cout_estime(modele, usage)
                prix = (f" ≈ {cout:.3f} $" if cout is not None
                        else " (tarif inconnu pour ce modèle)")
                depense += cout or 0
                print(f"  [{i}/{len(entrees)}] {entree['nom']} — jetons : "
                      f"{entree_j} en entrée, {texte_j} de texte et "
                      f"réflexion, {image_j} d'image{prix}")
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
                detail = e.read().decode(errors="replace")
                if e.code == 401 or (e.code in (400, 403)
                                     and ("API_KEY" in detail or not cle)):
                    # La clé ne deviendra pas valide à l'exercice suivant.
                    # Répéter l'erreur 87 fois noie le message utile.
                    raise CleRefusee(_resume_cle(detail, cle_locale=bool(cle)))
                if e.code == 402:
                    # Crédits épuisés : l'image suivante coûte le même prix.
                    # Continuer la file ne fait qu'aligner le même refus.
                    raise CleRefusee(
                        "crédits Gemini épuisés. Les images déjà produites sont "
                        "gardées ; rechargez sur https://ai.studio/projects "
                        "puis relancez, le script reprendra où il s'est "
                        "arrêté.")
                print(f"  ÉCHEC {entree['nom']} : HTTP {e.code} "
                      + detail[:400])
                echecs += 1
                break
            except Exception as e:
                if essai == ESSAIS:
                    print(f"  ÉCHEC {entree['nom']} : {e}")
                    echecs += 1
                else:
                    time.sleep(3 * essai)
        time.sleep(PAUSE)

    if faits:
        print(f"  coût estimé de cette exécution : {depense:.3f} $ "
              f"({modele}, la facture Google fait foi)")
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
    p.add_argument("--limite", type=int,
                   help="s'arrêter après N images — pour vérifier le coût réel "
                        "avant de lancer tout le catalogue")
    a = p.parse_args()

    if not a.cle:
        # Pas d'arrêt : un environnement cloud peut ajouter la clé lui-même
        # à chaque requête. S'il ne le fait pas, Google refuse dès la
        # première image et le message dit quoi faire.
        print("Pas de clé ici (ni --cle, ni GEMINI_API_KEY) : la requête part "
              "sans, le réseau doit l'ajouter (en-tête x-goog-api-key).")
        print()

    # Un modèle de commande collé tel quel se reconnaît sans rien demander
    # à Google : autant le dire tout de suite.
    probleme, avertissement = _forme_de_cle(a.cle) if a.cle else (None, None)
    if probleme:
        print(probleme)
        print("Une clé s'obtient sur https://aistudio.google.com/apikey,")
        print("bouton « Create API key ». Elle commence par AIza.")
        raise SystemExit(1)
    if avertissement:
        print(avertissement)
        print()

    if a.cle in ("TA_CLE", "VOTRE_CLE", "CLE", "cle"):
        print(f"« {a.cle} » est le modèle de la commande, pas votre clé.")
        print("Remplacez-le, ou retirez --cle si GEMINI_API_KEY est déjà")
        print("dans l'environnement — le script la prend tout seul.")
        raise SystemExit(1)

    try:
        faits, ignores, echecs = generer(a.cle, a.sortie, a.reference, a.modele,
                                         a.seulement, a.limite)
    except CleRefusee as e:
        print("Arrêt immédiat :", e)
        raise SystemExit(1)
    print(f"\n{faits} générée(s), {ignores} déjà présente(s), {echecs} en échec")
    print(f"Images dans {os.path.abspath(a.sortie)}")
    if faits:
        print("Regardez-les, puis : python tools/import_exercise_art.py "
              + os.path.abspath(a.sortie))
