"""Illustrations d'exercices — branchées par convention de nom.

Déposer `arnold-press.webp` dans `static/img/exercises/` suffit à illustrer
« Arnold press » : aucune ligne à éditer, aucune liste à tenir à jour. Une
liste manuelle de 87 entrées finit toujours par mentir — c'est déjà ce qui
s'était passé avec les 18 dessins au trait, recyclés sur 87 fiches
(`row.svg` servait à 11 exercices, dont les shrugs).
"""
import datetime as dt
import json

import pytest

from conftest import USER_ID, CSRF
from core import exercises_data
from core.exercises_data import get_exercise_info, illustration_slug

MONDAY = dt.date(2026, 9, 14)


@pytest.fixture()
def illustrations(monkeypatch):
    """Simule la présence de deux fichiers, sans toucher au dépôt."""
    monkeypatch.setattr(exercises_data, "_ILLUSTRATIONS",
                        {"arnold-press", "developpe-couche"})


# ── Convention de nom ────────────────────────────────────────────


def test_le_nom_de_fichier_se_deduit_du_nom_de_lexercice():
    assert illustration_slug("Développé couché") == "developpe-couche"
    assert illustration_slug("Arnold press") == "arnold-press"
    assert illustration_slug("Élévations latérales") == "elevations-laterales"
    assert illustration_slug("Rowing barre (pronation)") == "rowing-barre-pronation"


# ── Résolution ───────────────────────────────────────────────────


def test_lillustration_remplace_le_dessin_quand_elle_existe(illustrations):
    info = get_exercise_info("Arnold press")
    assert info["image"] == "arnold-press.webp"
    assert info["illustration"] is True


def test_sans_illustration_le_dessin_au_trait_reste(illustrations):
    """87 exercices ne s'illustrent pas en un jour : l'un ne doit pas
    empêcher l'autre d'être affiché."""
    info = get_exercise_info("Squat")
    assert info["image"].endswith(".svg")
    assert info.get("illustration") is not True


def test_une_variante_herite_de_lillustration_de_base(illustrations):
    """« Développé couché (Haltères) » retombe sur la fiche « Développé
    couché » : l'illustration doit suivre le même chemin."""
    info = get_exercise_info("Développé couché (Haltères)")
    assert info["image"] == "developpe-couche.webp"


def test_la_fiche_partagee_nest_jamais_modifiee(illustrations):
    """`EXERCISES_INFO` est un dictionnaire de module : le résoudre en place
    contaminerait toutes les requêtes suivantes."""
    get_exercise_info("Arnold press")
    assert exercises_data.EXERCISES_INFO["Arnold press"]["image"].endswith(".svg")


def test_un_dossier_absent_ne_casse_rien(monkeypatch):
    monkeypatch.setattr(exercises_data, "_DOSSIER_ART", "/chemin/qui/n/existe/pas")
    assert exercises_data._illustrations_presentes() == set()


# ── Affichage ────────────────────────────────────────────────────


def test_lillustration_apparait_sur_la_carte_pas_seulement_dans_la_fiche(
        fake_db, logged_in, illustrations):
    """Hevy la montre pendant la séance. Cachée derrière le « ? », elle ne
    sert qu'à ceux qui savent déjà qu'elle existe."""
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Arnold press", "sets": 3, "muscle": "Épaules"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": MONDAY.isoformat(),
    }}).execute()
    html = logged_in.get(
        f"/seance?mode=prefaite&name=Push&date={MONDAY.isoformat()}"
    ).get_data(as_text=True)
    assert 'class="exo-vignette"' in html, "la vignette manque sur la carte"
    assert "/static/img/exercises/arnold-press.webp" in html


def test_aucune_vignette_sans_illustration(fake_db, logged_in, illustrations):
    """Un dessin au trait de 80 px agrandi sur la carte serait laid : tant
    qu'il n'y a pas d'illustration, la carte reste telle quelle."""
    fake_db.table("programs").insert({"user_id": USER_ID, "data": {
        "Push": [{"name": "Squat", "sets": 3, "muscle": "Quadriceps"}],
        "_planning": {"Lundi": "Push"}, "_settings": {},
        "_started_at": MONDAY.isoformat(),
    }}).execute()
    html = logged_in.get(
        f"/seance?mode=prefaite&name=Push&date={MONDAY.isoformat()}"
    ).get_data(as_text=True)
    # La règle CSS est toujours dans la page ; c'est l'ÉLÉMENT qui ne doit
    # pas y être.
    assert 'class="exo-vignette"' not in html


# ── Poids des fichiers ───────────────────────────────────────────


def test_les_illustrations_livrees_restent_legeres():
    """Une image générée pèse 1,5 Mo. Telles quelles, 87 feraient 130 Mo et
    la séance mettrait une minute à s'afficher en 4G."""
    import glob
    import io
    import os
    lourdes = []
    for f in glob.glob("static/img/exercises/*.webp"):
        ko = os.path.getsize(f) // 1024
        if ko > 60:
            lourdes.append(f"{os.path.basename(f)} : {ko} ko")
    assert not lourdes, lourdes


# ── Prompts de génération ────────────────────────────────────────
# Les illustrations sont générées à partir de `tools/exercise_prompts.json`.
# Un prompt faux coûte de l'argent ET apprend un mauvais geste : ces
# vérifications valent d'être automatiques.


def _prompts():
    import io
    import json
    import os
    import sys
    sys.path.insert(0, "tools")
    from build_exercise_prompts import construire
    return {e["nom"]: e for e in construire()}


def test_le_prompt_decrit_le_mouvement_pas_seulement_la_position_de_depart():
    """Le bug qui a produit un développé couché au lieu d'une barre au front.

    La description de « Barre au front » commence par « Allongé sur un banc,
    barre tenue à bout de bras au-dessus de la poitrine » — c'est la position
    de départ, et c'est mot pour mot celle du développé couché. Le prompt ne
    gardait que cette première phrase : le modèle a dessiné un développé
    couché, red flag invisible tant qu'on ne regarde pas l'image.
    """
    p = _prompts()["Barre au front"]["prompt"].lower()
    assert "forehead" in p or "vers le front" in p, \
        "le prompt ne dit pas où va la barre : bras tendus au-dessus de " \
        "la poitrine, c'est un développé couché — et c'est ce qui est sorti"


def test_aucune_description_nest_tronquee_en_chemin():
    """Généralise le cas « barre au front » aux 87 fiches.

    Chaque fiche décrit le départ PUIS le mouvement. Ne garder qu'un bout,
    c'est laisser le modèle inventer la moitié du geste — et une illustration
    fausse apprend un mauvais mouvement à celui qui la regarde pendant sa
    série.
    """
    from build_exercise_prompts import GESTES
    from core.exercises_data import EXERCISES_INFO
    tronquees = []
    for nom, entree in _prompts().items():
        if nom in GESTES:          # geste écrit à la main, la fiche ne sert plus
            continue
        description = " ".join((EXERCISES_INFO[nom].get("description") or "").split())
        if description and description not in entree["prompt"]:
            tronquees.append(nom)
    assert not tronquees, f"description coupée dans le prompt : {tronquees}"


def test_les_fiches_qui_ne_decrivent_aucun_geste_en_recoivent_un():
    """« Même principe que le curl classique mais avec une barre droite ou EZ.
    La barre permet de charger plus lourd. » — rien, dans ces trois phrases,
    ne dit à quoi ressemble un curl. Le modèle avait dessiné les bras le long
    du corps, épaules en rouge.
    """
    p = _prompts()["Curl barre"]["prompt"].lower()
    assert "barbell" in p and "elbows" in p, \
        "le geste du curl n'est décrit nulle part dans le prompt"


def test_chaque_exercice_sait_quel_muscle_peindre():
    """« Dos (grand dorsal) » ne dit rien à un modèle d'image, et « Triceps »
    sans précision finit régulièrement peint sur les biceps. Chaque libellé
    doit être traduit en une zone anatomique située sur le corps — sinon
    l'exercice part sans rouge, silencieusement."""
    from build_exercise_prompts import ZONES
    from core.exercises_data import EXERCISES_INFO
    inconnus = sorted({(f.get("muscles") or ["(aucun)"])[0]
                       for f in EXERCISES_INFO.values()
                       if (f.get("muscles") or ["(aucun)"])[0] not in ZONES})
    assert not inconnus, f"muscle sans zone anatomique : {inconnus}"


def test_le_prompt_ne_designe_quune_seule_zone_rouge():
    """Deux zones rouges dans une image, c'est deux muscles désignés comme
    cibles alors que la fiche n'en annonce qu'un."""
    for nom, entree in _prompts().items():
        p = entree["prompt"]
        assert p.lower().count("red-orange") <= 1, nom


def test_un_exercice_global_ne_se_colorie_pas():
    """Les burpees sollicitent tout : un corps entièrement rouge ne désigne
    plus rien, et le reste du catalogue devient illisible par contraste."""
    p = _prompts()["Burpees"]["prompt"].lower()
    assert "red-orange" not in p
    assert "no coloured muscle" in p


def test_le_rouge_de_la_reference_est_efface_avant_lenvoi(tmp_path):
    """La référence part avec les 86 autres appels pour tenir le style. Le
    modèle en recopiait AUSSI la zone rouge : tous les exercices sortaient
    avec les épaules en rouge, curl compris. La phrase le lui interdisant
    n'a pas suffi, donc le rouge est retiré de l'image elle-même — il ne
    reste rien à recopier."""
    import io as _io
    import sys
    from PIL import Image
    sys.path.insert(0, "tools")
    from generate_exercise_art import _sans_rouge

    source = Image.new("RGB", (40, 40), (150, 150, 150))
    for y in range(10, 20):
        for x in range(10, 20):
            source.putpixel((x, y), (210, 90, 70))       # le muscle colorié
    chemin = tmp_path / "ref.png"
    source.save(chemin)

    octets, efface = _sans_rouge(str(chemin))
    assert efface == 100, efface
    sortie = Image.open(_io.BytesIO(octets)).convert("RGB")
    px = sortie.load()
    rouges = [(x, y) for y in range(40) for x in range(40)
              if px[x, y][0] - max(px[x, y][1], px[x, y][2]) > 8]
    assert not rouges, rouges
    # Le mannequin autour n'a pas bougé : on efface le coloriage, pas l'image.
    assert px[0, 0] == (150, 150, 150)


def test_la_consigne_de_reference_ne_gouverne_que_le_style(monkeypatch):
    """Sans ce cadrage, la référence imposait aussi sa pose : les cinq
    premières images avaient toutes la même. On inspecte ce qui part
    vraiment sur le réseau, pas ce que le code a l'air de dire."""
    import base64
    import contextlib
    import io as flux
    import json
    import sys
    sys.path.insert(0, "tools")
    import generate_exercise_art as g

    envoye = {}

    @contextlib.contextmanager
    def _faux_appel(requete, timeout=None):
        envoye["corps"] = json.loads(requete.data.decode())
        image = base64.b64encode(b"PNG").decode()
        yield flux.BytesIO(json.dumps({"candidates": [{"content": {
            "parts": [{"inline_data": {"data": image}}]}}]}).encode())

    monkeypatch.setattr(g.urllib.request, "urlopen", _faux_appel)
    g._demander("cle", "PROMPT DE L'EXERCICE",
                {"inline_data": {"mime_type": "image/png", "data": "eA=="}})

    parties = envoye["corps"]["contents"][0]["parts"]
    cadrage = parties[0]["text"]
    assert "ONLY for the" in cadrage, "la référence n'est pas cadrée au style"
    assert "Do NOT copy its pose" in cadrage
    # Le prompt de l'exercice passe après le cadrage, l'image en dernier.
    assert parties[1]["text"] == "PROMPT DE L'EXERCICE"
    assert "inline_data" in parties[-1]


def test_le_nom_de_fichier_du_prompt_est_celui_que_lapp_ira_chercher():
    """Les deux viennent de `illustration_slug` : un fichier généré sous un
    autre nom ne serait jamais affiché, sans aucune erreur nulle part."""
    for nom, entree in _prompts().items():
        assert entree["fichier"] == illustration_slug(nom) + ".png"


def test_le_nom_du_muscle_ne_se_repete_pas_dans_sa_description():
    """L'ancre porte le nom, la description porte l'ENDROIT.

    Quand les deux portaient le nom, la phrase sortait bancale : « Paint
    ONLY the biceps — the bulge on the FRONT of each upper arm, strictly
    BETWEEN the shoulder joint and the elbow **in a flat soft red-orange
    overlay** ». La couleur se retrouvait à dix mots de son verbe.
    """
    from build_exercise_prompts import ZONES
    doublons = []
    for libelle, zone in ZONES.items():
        if zone is None:
            continue
        ancre, description, _ = zone
        if description.lower().startswith(ancre.lower()):
            doublons.append(libelle)
    assert not doublons, f"le nom du muscle ouvre sa propre description : {doublons}"


def test_le_prompt_exige_que_la_camera_voie_le_muscle():
    """Sur une planche les abdos regardent le sol, sur un hip thrust les
    fessiers sont dessous, sur un soulevé de terre les érecteurs sont
    derrière. Trois fois, le modèle a peint la face qu'il avait sous les
    yeux : lombaires, avant de la cuisse, flanc. Ce n'était pas un problème
    de formulation mais d'angle de prise de vue."""
    manquants = [n for n, e in _prompts().items()
                 if "red-orange" in e["prompt"] and "faces the viewer" not in e["prompt"]]
    assert not manquants, manquants


def test_le_bas_des_pectoraux_reste_sur_la_poitrine():
    """« the BOTTOM edge of the chest » s'est lu « sous la poitrine » : les
    cinq dips avaient le rouge sur le ventre ou la taille."""
    p = _prompts()["Dips"]["prompt"].lower()
    assert "still on the chest" in p
    assert "do not paint the stomach" in p


def test_un_exercice_qui_cache_sa_cible_ne_se_colorie_pas():
    """À plat ventre, les abdos regardent le sol : aucun angle ne montre à
    la fois le gainage et sa ceinture abdominale. Deux générations de suite
    ont mis le rouge sur les LOMBAIRES — l'opposé exact du muscle travaillé.
    Une anatomie fausse affichée pendant la série est pire que pas de rouge,
    et la pose, elle, se reconnaît seule."""
    prompts = _prompts()
    # Nommés ici, pas parcourus depuis la liste : sinon en retirer un
    # ferait juste sauter le tour de boucle, sans rien signaler.
    for nom in ("Gainage", "Planche", "Mountain climbers"):
        p = prompts[nom]["prompt"].lower()
        assert "red-orange" not in p, nom
        assert "no coloured muscle" in p, nom


def test_les_halteres_sont_decrits_par_leur_forme_pas_par_une_absence():
    """« There is NO barbell » a produit une barre trois fois de suite : une
    absence ne se dessine pas. C'est la géométrie qui la remplace — deux
    objets courts séparés, rien entre les deux mains."""
    p = _prompts()["Curl haltères"]["prompt"].lower()
    assert "two separate" in p and "gap between the two hands" in p


def test_un_refus_global_arrete_la_file_au_lieu_de_se_repeter(monkeypatch):
    """Crédits épuisés ou clé refusée : l'exercice suivant coûte le même
    prix et reçoit le même refus. Continuer la file n'aligne que 87 copies
    du même message, et le seul utile — que faire — disparaît dedans."""
    import sys
    import urllib.error
    sys.path.insert(0, "tools")
    import generate_exercise_art as g

    appels = []

    def _refus(requete, timeout=None):
        appels.append(1)
        raise urllib.error.HTTPError(
            "http://x", 402, "Payment Required", {},
            __import__("io").BytesIO(b'{"error":{"code":402}}'))

    monkeypatch.setattr(g.urllib.request, "urlopen", _refus)
    with pytest.raises(g.CleRefusee) as refus:
        g.generer("cle", str(__import__("tempfile").mkdtemp()))
    assert "crédits" in str(refus.value).lower()
    assert len(appels) == 1, f"{len(appels)} appels au lieu d'un seul"
