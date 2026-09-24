"""Mémoire du coach — ce qu'il doit retenir d'une conversation à l'autre.

Sans mémoire, chaque nouvelle conversation repartait de zéro : l'utilisateur
devait redire qu'il a mal à l'épaule droite, qu'il s'entraîne le matin, ou
qu'il ne supporte pas le squat barre. Un coach humain qui oublie ça à chaque
séance n'est pas un coach.

Ce module maintient une note courte (quelques lignes) mise à jour après les
échanges, stockée dans `profiles.coach_memory`. Elle est injectée dans le
prompt système de toutes les conversations suivantes.

Volontairement minimaliste : pas de base vectorielle, pas de recherche
sémantique. Une note de 600 caractères couvre l'essentiel (blessures,
contraintes, préférences, objectif du moment) pour un coût dérisoire.
"""
import logging

logger = logging.getLogger(__name__)

MAX_CHARS = 700
# On ne résume qu'après quelques échanges : condenser un « bonjour » n'apporte
# rien et coûte un appel API.
MIN_TURNS_BEFORE_SUMMARY = 4

SUMMARY_PROMPT = (
    "Voici la note que tu gardes sur cet utilisateur, puis les derniers "
    "messages échangés.\n\n"
    "Mets la note à jour : garde UNIQUEMENT ce qui sera encore utile dans un "
    "mois — blessures et douleurs, contraintes (horaires, matériel, lieu), "
    "préférences et aversions d'exercices, objectif en cours, échéances.\n\n"
    "Règles :\n"
    "- 6 lignes maximum, une information par ligne, style télégraphique.\n"
    "- Pas de politesses, pas de conseils, pas de résumé de la conversation.\n"
    "- Si une information contredit la note, garde la plus récente.\n"
    "- Si rien de durable n'est apparu, renvoie la note inchangée.\n"
    "- Réponds UNIQUEMENT par la note, sans introduction.\n\n"
    "NOTE ACTUELLE :\n{memory}\n\n"
    "DERNIERS MESSAGES :\n{transcript}"
)


def get_memory(profile: dict) -> str:
    return (profile or {}).get("coach_memory") or ""


def format_for_prompt(memory: str) -> str:
    """Bloc à insérer dans le prompt système, ou chaîne vide."""
    memory = (memory or "").strip()
    if not memory:
        return ""
    return (
        "\n## CE QUE TU SAIS DÉJÀ DE LUI\n"
        "(notes de tes échanges précédents — tiens-en compte sans les répéter "
        "mot pour mot)\n" + memory + "\n"
    )


def _transcript(messages: list[dict], limit: int = 10) -> str:
    lines = []
    for m in (messages or [])[-limit:]:
        role = "Utilisateur" if m.get("role") == "user" else "Coach"
        content = (m.get("content") or "").strip().replace("\n", " ")
        if content:
            lines.append(f"{role} : {content[:400]}")
    return "\n".join(lines)


def should_update(messages: list[dict]) -> bool:
    return len([m for m in (messages or []) if m.get("role") == "user"]) >= MIN_TURNS_BEFORE_SUMMARY


def build_summary(client, model: str, memory: str, messages: list[dict]) -> str | None:
    """Nouvelle note, ou None si l'appel échoue (la note actuelle est gardée).

    L'appel est court (200 tokens) et se fait APRÈS la réponse envoyée à
    l'utilisateur : il n'allonge jamais l'attente perçue.
    """
    transcript = _transcript(messages)
    if not transcript:
        return None
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=250,
            messages=[{
                "role": "user",
                "content": SUMMARY_PROMPT.format(
                    memory=memory or "(vide)", transcript=transcript),
            }],
        )
        parts = [getattr(b, "text", "") for b in (resp.content or []) if getattr(b, "text", "")]
        note = "\n".join(parts).strip()
    except Exception as e:
        logger.warning("coach memory summary failed: %s", e)
        return None
    if not note:
        return None
    return note[:MAX_CHARS]
