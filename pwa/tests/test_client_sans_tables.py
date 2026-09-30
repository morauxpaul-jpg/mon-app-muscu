"""Le navigateur ne touche jamais une table Supabase.

La migration v38 retire aux rôles anon et authenticated tout droit sur les
tables : la règle « profiles: self update » laissait un compte gratuit se
passer `tier = 'vip'` depuis la console. Ça ne tient que si le client
n'utilise Supabase QUE pour l'authentification — toutes les données passent
par le serveur (clé service_role).

Ce test garde cette condition : un `supabase.from(...)` ou `.rpc(...)`
ajouté dans une page échouerait en production, et surtout inviterait à
rouvrir des règles côté client.
"""
import re
from pathlib import Path

PWA = Path(__file__).resolve().parents[1]
FICHIERS = [p for p in list((PWA / "templates").rglob("*.html")) + list((PWA / "static" / "js").rglob("*.js"))
            if not p.name.endswith(".min.js")]

APPEL_TABLE = re.compile(r"\bsupabase\s*\.\s*(from|rpc|storage|channel)\s*\(")


def test_aucune_page_ne_lit_ni_necrit_une_table():
    fautifs = []
    for f in FICHIERS:
        for n, ligne in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
            if APPEL_TABLE.search(ligne):
                fautifs.append(f"{f.relative_to(PWA)}:{n}")
    assert not fautifs, "accès direct à Supabase depuis le navigateur : " + ", ".join(fautifs)


def test_le_client_supabase_ne_sert_qua_lauthentification():
    """Les deux seules pages qui créent un client Supabase ne l'utilisent
    que pour `supabase.auth.*`."""
    for nom in ("login.html", "bridge.html"):
        src = (PWA / "templates" / nom).read_text(encoding="utf-8")
        usages = set(re.findall(r"\bsupabase\s*\.\s*(\w+)", src))
        assert usages <= {"auth"}, f"{nom} utilise supabase.{usages - {'auth'}}"
