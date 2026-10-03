"""Compression gzip des réponses (audit du 03/10, Q2)."""
import gzip

from flask import Flask, Response, request

from core.compression import compresser

GZ = {"Accept-Encoding": "gzip, deflate, br"}


def test_page_html_compressee_et_lisible(fake_db, logged_in):
    r = logged_in.get("/gestion", headers=GZ)
    assert r.headers["Content-Encoding"] == "gzip"
    assert "Accept-Encoding" in r.headers["Vary"]
    brut = gzip.decompress(r.data)
    assert int(r.headers["Content-Length"]) == len(r.data) < len(brut)
    assert b"</html>" in brut


def test_sans_accept_encoding_rien(fake_db, logged_in):
    r = logged_in.get("/gestion")
    assert "Content-Encoding" not in r.headers and b"</html>" in r.data


def test_fichier_statique_compresse(client):
    r = client.get("/static/css/components-pages.css", headers=GZ)
    assert r.status_code == 200 and r.headers["Content-Encoding"] == "gzip"
    assert b".sm-liste" in gzip.decompress(r.data)


def test_flux_sse_jamais_compresse():
    app = Flask(__name__)

    def flux():
        yield "data: a\n\n"
        yield "data: b\n\n"

    with app.test_request_context(headers=GZ):
        r = compresser(request, Response(flux(), mimetype="text/event-stream"))
        assert "Content-Encoding" not in r.headers
        r2 = compresser(request, Response(flux(), mimetype="text/html"))   # générateur HTML
        assert "Content-Encoding" not in r2.headers


def test_petites_reponses_images_et_erreurs_intactes():
    app = Flask(__name__)
    with app.test_request_context(headers=GZ):
        assert "Content-Encoding" not in compresser(request, Response("x" * 100, mimetype="text/html")).headers
        assert "Content-Encoding" not in compresser(request, Response(b"\x89PNG" * 900, mimetype="image/png")).headers
        assert "Content-Encoding" not in compresser(request, Response("x" * 5000, status=404, mimetype="text/html")).headers
        r = Response("x" * 5000, mimetype="text/html")
        r.headers["ETag"] = '"abc"'
        assert compresser(request, r).headers["ETag"] == 'W/"abc"'
