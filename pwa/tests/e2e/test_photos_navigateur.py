"""Onglet « Corps » dans le navigateur : pesée, photos, avant / après.

Ce que les tests sans navigateur ne voient pas : la photo redessinée dans un
canevas avant l'envoi (taille bornée, métadonnées retirées, donc la position
GPS), l'envoi par fetch sous la CSP, l'avant / après affiché, et
l'invitation à se peser qu'on peut écarter (« Garder la dernière pesée »).
"""
import base64
from datetime import date, timedelta

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

# Une photo de téléphone : 3 000 × 4 000, avec un bloc EXIF qui porte une
# position GPS (inséré juste après le début du fichier).
FABRIQUER = """([w, h]) => {
  const c = document.createElement('canvas'); c.width = w; c.height = h;
  const g = c.getContext('2d');
  g.fillStyle = '#334'; g.fillRect(0, 0, w, h);
  g.fillStyle = '#c8f031'; g.fillRect(w / 4, h / 4, w / 2, h / 2);
  return c.toDataURL('image/jpeg', 0.9).split(',')[1];
}"""


def _photo_de_telephone(pg, w=3000, h=4000):
    jpeg = base64.b64decode(pg.evaluate(FABRIQUER, [w, h]))
    exif = b"Exif\x00\x00GPSLatitude 48.8566 N GPSLongitude 2.3522 E"
    app1 = b"\xff\xe1" + (len(exif) + 2).to_bytes(2, "big") + exif
    return jpeg[:2] + app1 + jpeg[2:]


def _envoyer(pg, angle, date_iso, fichier):
    pg.locator(".ph-angle", has_text=angle).click()
    pg.locator("#ph-date").fill(date_iso)
    with pg.expect_navigation():
        pg.locator("#ph-fichier").set_input_files(
            {"name": "IMG_2041.jpg", "mimeType": "image/jpeg", "buffer": fichier})


def test_une_photo_est_reduite_sans_gps_puis_comparee(serveur, navigateur):
    ctx = navigateur.new_context(viewport={"width": 390, "height": 844}, locale="fr-FR")
    ctx.add_init_script("localStorage.setItem('tutoSeen','true'); localStorage.setItem('notifPrompted','1');")
    pg = ctx.new_page()
    erreurs = []
    pg.on("console", lambda m: erreurs.append(m.text)
          if ("Alpine" in m.text or "Content Security Policy" in m.text) else None)
    pg.on("pageerror", lambda e: erreurs.append(str(e)))
    pg.goto(serveur + "/test-vierge")
    pg.goto(serveur + "/test-login?vip=1&to=/progres/corps")
    pg.goto(serveur + "/progres")
    pg.get_by_role("link", name="Corps").click()
    pg.wait_for_url("**/progres/corps")
    pg.wait_for_selector("#ph-date")

    apres = date.fromisoformat(pg.locator("#ph-date").input_value())   # aujourd'hui, à Paris
    avant = apres - timedelta(days=56)
    # Une pesée le jour de la première photo, dans la même page.
    poids = pg.locator('#poids form[action="/progres/poids"]')
    poids.locator('input[name="date"]').fill(avant.isoformat())
    poids.locator('input[name="poids_kg"]').fill("94.6")
    with pg.expect_navigation():
        poids.get_by_role("button", name="OK").click()
    fichier = _photo_de_telephone(pg)
    assert b"GPSLatitude" in fichier and len(fichier) > 50_000
    _envoyer(pg, "Face", avant.isoformat(), fichier)
    _envoyer(pg, "Face", apres.isoformat(), _photo_de_telephone(pg, 2400, 3200))

    # La seconde photo n'a pas de pesée ce jour-là : la dernière s'affiche,
    # avec sa date, et l'écart de poids n'est pas inventé.
    sync_api.expect(pg.locator("#comparaison .ph-surtitre")).to_have_text("Avant / après · 8 semaines")
    legendes = pg.locator(".ph-cote figcaption")
    sync_api.expect(legendes.first).to_contain_text(avant.strftime("%d/%m/%Y"))
    sync_api.expect(legendes.first).to_contain_text("94,6 kg")
    sync_api.expect(legendes.last).to_contain_text(f"94,6 kg (pesée du {avant.strftime('%d/%m')})")

    invitation = pg.locator("#ph-pesee")
    sync_api.expect(invitation).to_contain_text(f"Pas de pesée le {apres.strftime('%d/%m')}")
    pg.get_by_role("button", name="Garder la dernière pesée").click()
    sync_api.expect(invitation).to_be_hidden()
    pg.reload()
    sync_api.expect(pg.locator("#ph-pesee")).to_be_hidden()

    # Ce que le serveur a reçu : 1 600 px au plus, miniature 400, plus d'EXIF.
    recu = pg.evaluate("""async () => {
      const src = document.querySelector('.ph-grande').getAttribute('src');
      const octets = new Uint8Array(await (await fetch(src)).arrayBuffer());
      const texte = Array.from(octets.slice(0, 4096), b => String.fromCharCode(b)).join('');
      const img = (u) => new Promise(ok => { const i = new Image(); i.onload = () => ok([i.naturalWidth, i.naturalHeight]); i.src = u; });
      return { taille: octets.length, exif: texte.includes('Exif') || texte.includes('GPS'),
               grande: await img(src), mini: await img(document.querySelector('.ph-mini').getAttribute('src')) };
    }""")
    assert recu["exif"] is False, "la position GPS est partie avec la photo"
    assert recu["grande"] == [1200, 1600] and recu["mini"] == [300, 400]
    assert recu["taille"] < 2 * 1024 * 1024

    # Changer la photo « Après » recharge la comparaison, sans bouton.
    with pg.expect_navigation():
        pg.locator('select[name="apres"]').select_option(index=1)
    sync_api.expect(pg.locator("#comparaison .ph-surtitre")).to_have_text("Avant / après · même jour")
    assert erreurs == [], erreurs
    ctx.close()
