"""Réglages communs des appels à Claude : coach, générateur, bilan, mémoire.

Passage à Claude Haiku 5.5 (25/10) : le token coûte 10 fois moins que sur
Haiku 4.5 (0,10 $ / 0,50 $ le million, au lieu de 1 $ / 5 $), mais le même
texte compte environ 30 % de tokens en plus, et le modèle réfléchit avant de
répondre, ce qui est facturé en sortie. Ce qui en découle :
- `effort` fixe combien il réfléchit : « low » pour le coach, le bilan et la
  mémoire, « medium » pour le générateur, où la qualité du programme compte ;
- les plafonds `max_tokens` laissent de la place à cette réflexion, sinon
  elle les épuise et la réponse revient vide ;
- un refus de sécurité est une réponse normale (`stop_reason: "refusal"`),
  sans modèle de repli : chaque appel le traite comme un échec ;
- chaque appel journalise ses tokens, pour mesurer le coût réel.
"""
import logging

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-5-5"


def options(effort: str = "low") -> dict:
    """Paramètres communs à passer à `messages.create` ou `messages.stream`."""
    return {"model": MODEL, "output_config": {"effort": effort}}


def journaliser(route: str, message) -> None:
    usage = getattr(message, "usage", None)
    if usage is None:
        return
    logger.info("ia %s : %s tokens en entrée, %s en sortie, fin=%s", route,
                getattr(usage, "input_tokens", "?"), getattr(usage, "output_tokens", "?"),
                getattr(message, "stop_reason", "?"))


def refuse(route: str, message) -> bool:
    """Vrai si le modèle a décliné la demande. Journalise la catégorie."""
    if getattr(message, "stop_reason", None) != "refusal":
        return False
    details = getattr(message, "stop_details", None)
    logger.warning("ia %s : refus de sécurité (%s)", route,
                   getattr(details, "category", None) or "sans catégorie")
    return True


def textes(route: str, message) -> list[str] | None:
    """Les blocs de texte de la réponse, ou None si le modèle a refusé.
    Les blocs de réflexion (`thinking`) n'ont pas de `text` : ils sont ignorés."""
    journaliser(route, message)
    if refuse(route, message):
        return None
    return [b.text for b in (getattr(message, "content", None) or [])
            if getattr(b, "text", "")]
