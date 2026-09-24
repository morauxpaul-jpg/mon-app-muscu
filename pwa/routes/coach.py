"""Blueprint coach — assistant IA musculation via Claude Haiku.

- /coach     : page chat (GET)
- /coach/ask : endpoint JSON (POST) → appelle l'API Anthropic

Accès réservé VIP (vip_wall pour les free). Quota : 15 messages/jour/user
via profiles.coach_quota_date + profiles.coach_quota_count (reset
automatique à chaque nouveau jour) — protège le coût API Anthropic.
"""
import logging

import json

from flask import (
    Blueprint, Response, render_template, request, jsonify, redirect, url_for,
    g, stream_with_context,
)

from core import db

from core.data import (
    get_prog, get_hist, get_profile, save_profile, get_onboarding,
    list_coach_messages, clear_coach_messages,
    list_coach_conversations, delete_coach_conversation,
)
from core.dates import today_paris_str
from core.db import _env
from core.limiter import limiter
from core import catalog
from core.analytics import track, paywall
from core import coach_memory

logger = logging.getLogger(__name__)

bp = Blueprint("coach", __name__)

DAILY_QUOTA = 15  # quota VIP/jour — aligné sur la page Premium (« 15 msg/jour »)
MODEL = "claude-haiku-4-5-20251001"
# 500 tokens coupaient toute réponse un peu construite en plein milieu — le
# défaut le plus visible du coach. La réponse étant désormais affichée au fil
# de l'eau, une réponse plus longue ne fait pas attendre davantage.
MAX_TOKENS = 1400

SYSTEM_PROMPT_TMPL = (
    "Tu es le coach IA intégré à l'application Muscu Tracker PRO (PWA Flask). "
    "Tu réponds en français, concis et pratique. Tu connais le programme, "
    "l'historique et l'app elle-même — profite de cette double connaissance.\n"
    "Tu ne donnes JAMAIS de conseils médicaux — renvoie vers un "
    "professionnel de santé si besoin. Tu es encourageant mais honnête.\n\n"
    "## ONGLETS DE L'APP (tu peux rediriger l'utilisateur avec des liens)\n"
    "- [Accueil](/accueil) : dashboard, planning de la semaine, streak, stats\n"
    "- [Séance](/seance) : reprendre la séance du jour\n"
    "- [Progrès](/progres) : calendrier mensuel, volume hebdo, body map, hall of fame, zoom par exercice\n"
    "- [Programme](/programme) : gérer ses séances, planning hebdo, profils d'entraînement\n"
    "- [Plus](/plus) : hub → Programme, Arcade, Gestion, Tutoriel\n"
    "- [Gestion](/gestion) : paramètres, export/import, notifications, reset\n\n"
    "## LIENS SPÉCIAUX (utilise-les quand pertinent)\n"
    "- Pour proposer un programme du catalogue → lien [nom](/programme?apply=ID) "
    "où ID est l'identifiant du programme. Cela ouvre l'onglet Programme sur la section "
    "'Changer de programme' avec le bon programme pré-sélectionné et surligné.\n"
    "- Pour aider à ajouter une séance précise → lien [nom](/programme#planning) vers le planning.\n\n"
    "## CATALOGUE DES PROGRAMMES DISPONIBLES\n"
    "{catalog_list}\n\n"
    "{memory_block}"
    "## CONTEXTE UTILISATEUR\n"
    "- Prénom : {prenom}\n"
    "- Âge : {age}\n"
    "- Poids : {poids}\n"
    "- Taille : {taille}\n"
    "- Niveau : {niveau}\n"
    "- Objectif : {objectif}\n"
    "- Équipement : {equipement}\n\n"
    "## PROGRAMME ACTUEL\n"
    "{programme_detail}\n\n"
    "## 14 DERNIÈRES SÉANCES\n"
    "{dernieres_seances}\n\n"
    "## RÈGLES DE FORMULATION\n"
    "- Utilise du markdown : **gras**, listes à puce, titres avec ##.\n"
    "- Quand tu mentionnes un programme du catalogue, fais-en un lien cliquable "
    "[Titre du programme](/programme?apply=ID) pour que l'utilisateur puisse y aller en un clic.\n"
    "- Quand tu suggères de consulter une section de l'app, mets un lien [nom onglet](/chemin).\n"
    "- Reste bref : 3-6 phrases max par réponse, sauf si l'utilisateur demande un plan détaillé."
)

SUGGESTIONS = [
    "Comment progresser au développé couché ?",
    "Mon programme est-il adapté ?",
    "J'ai mal à l'épaule, que faire ?",
    "Combien de protéines par jour ?",
]


def _catalog_list_for_prompt():
    """Liste compacte des programmes du catalogue pour le system prompt.

    Format : `- ID : Titre — sous-titre (niveau, X séances)`
    """
    try:
        items = catalog.list_programs() or []
    except Exception as e:
        logger.error("coach catalog list FAILED: %s", e)
        return "(catalogue indisponible)"
    lines = []
    for p in items:
        lines.append(
            f"- `{p['id']}` : {p['title']} — {p['subtitle']} "
            f"({p['nb_seances']} séances, {p['duration']})"
        )
    return "\n".join(lines) or "(vide)"


def _programme_detail(prog):
    """Programme actuel avec jours assignés et exercices détaillés."""
    if not prog:
        return "Aucun programme défini."
    seances = {k: v for k, v in prog.items() if not k.startswith("_")}
    if not seances:
        return "Aucun programme défini."
    planning = prog.get("_planning") or {}
    day_to_seance = {v: k for k, v in planning.items() if v}
    seance_to_days = {}
    for day, sname in planning.items():
        if sname:
            seance_to_days.setdefault(sname, []).append(day)
    name = prog.get("_name") or "Programme personnalisé"
    lines = [f"Nom : {name}"]
    for sname, exos in seances.items():
        days = seance_to_days.get(sname, [])
        day_str = ", ".join(days) if days else "non planifiée"
        exo_details = []
        for e in (exos or [])[:8]:
            ename = e.get("name") or "?"
            sets = e.get("sets") or 3
            exo_details.append(f"  - {ename} ({sets} séries)")
        lines.append(f"\n{sname} ({day_str}) :")
        lines.extend(exo_details if exo_details else ["  (aucun exercice)"])
    return "\n".join(lines)


def _dernieres_seances(hist):
    """14 dernières séances avec exercices et séries, triées date desc."""
    if not hist:
        return "Aucune séance enregistrée."
    by_date_seance = {}
    for r in hist:
        d = r.get("Date") or ""
        s = r.get("Séance") or ""
        exo = r.get("Exercice") or ""
        if not d or s == "" or exo == "SESSION":
            continue
        key = (d, s)
        entry = by_date_seance.setdefault(key, {"exos": {}, "vol": 0})
        try:
            reps = int(r.get("Reps") or 0)
            poids = float(r.get("Poids") or 0)
        except (TypeError, ValueError):
            reps, poids = 0, 0
        if reps > 0:
            exo_entry = entry["exos"].setdefault(exo, {"sets": 0, "best": 0})
            exo_entry["sets"] += 1
            if poids > exo_entry["best"]:
                exo_entry["best"] = poids
            entry["vol"] += int(reps * poids)
    if not by_date_seance:
        return "Aucune séance récente."
    items = sorted(by_date_seance.items(), key=lambda kv: kv[0][0], reverse=True)[:14]
    lines = []
    for (d, s), e in items:
        exo_parts = []
        for ename, edata in list(e["exos"].items())[:6]:
            best = f" @{edata['best']:g}kg" if edata["best"] > 0 else ""
            exo_parts.append(f"{ename} {edata['sets']}s{best}")
        exo_str = ", ".join(exo_parts)
        lines.append(f"- {d} · {s} (vol {e['vol']}kg) : {exo_str}")
    return "\n".join(lines)


def _check_and_bump_quota(profile):
    """Retourne (allowed: bool, count_after: int, limit: int).

    Reset automatique à chaque changement de jour. Si allowed, incrémente
    déjà le compteur et le persiste avant l'appel à l'API. En cas d'échec
    API, l'appelant doit appeler _revert_quota(profile) pour ne pas faire
    payer un message qui n'a jamais abouti.
    """
    today = today_paris_str()
    q_date = str(profile.get("coach_quota_date") or "")
    q_count = int(profile.get("coach_quota_count") or 0)
    if q_date != today:
        q_count = 0  # nouveau jour → reset
    if q_count >= DAILY_QUOTA:
        return False, q_count, DAILY_QUOTA
    q_count += 1
    try:
        save_profile({"coach_quota_date": today, "coach_quota_count": q_count})
    except Exception as e:
        logger.error("coach save_profile quota FAILED: %s", e)
    return True, q_count, DAILY_QUOTA


def _revert_quota():
    """Décrémente le compteur de 1 (si > 0) après un échec API."""
    try:
        profile = get_profile() or {}
        today = today_paris_str()
        q_date = str(profile.get("coach_quota_date") or "")
        q_count = int(profile.get("coach_quota_count") or 0)
        if q_date == today and q_count > 0:
            save_profile({"coach_quota_date": today, "coach_quota_count": q_count - 1})
    except Exception as e:
        logger.error("coach revert_quota FAILED: %s", e)


def _quota_remaining(profile):
    today = today_paris_str()
    q_date = str(profile.get("coach_quota_date") or "")
    q_count = int(profile.get("coach_quota_count") or 0)
    if q_date != today:
        q_count = 0
    return max(0, DAILY_QUOTA - q_count)


def _title_from_message(msg: str) -> str:
    """Titre court d'une conversation à partir du 1er message."""
    t = " ".join((msg or "").split())
    if not t:
        return "Nouvelle conversation"
    return (t[:40].rstrip() + "…") if len(t) > 40 else t


@bp.route("/coach")
def index():
    if not getattr(g, "is_vip_full", False):
        return paywall("Coach IA")
    try:
        profile = get_profile() or {}
        onboarding = get_onboarding() or {}
    except Exception as e:
        logger.error("/coach load profile/onboarding FAILED: %s", e)
        profile, onboarding = {}, {}
    # Liste des conversations pour la sidebar (drawer).
    try:
        conversations = list_coach_conversations(50) or []
    except Exception as e:
        logger.error("/coach load conversations FAILED: %s", e)
        conversations = []
    # ?c=<id> reprend une conversation ; sinon, nouveau chat vide par défaut.
    conv_id = str(request.args.get("c") or "").strip()
    messages = []
    active_conversation = None
    if conv_id and any(str(c.get("id")) == conv_id for c in conversations):
        active_conversation = conv_id
        try:
            messages = list_coach_messages(conversation_id=conv_id, limit=100) or []
        except Exception as e:
            logger.error("/coach load conv messages FAILED: %s", e)
            messages = []
    prenom = (onboarding.get("prenom") or profile.get("prenom") or "").strip()
    remaining = _quota_remaining(profile)
    prefill = (request.args.get("q") or "").strip()[:500]
    return render_template(
        "coach.html",
        active="plus",
        prenom=prenom or "l'athlète",
        suggestions=SUGGESTIONS,
        quota_remaining=remaining,
        quota_limit=DAILY_QUOTA,
        messages=messages,
        conversations=conversations,
        active_conversation=active_conversation,
        prefill=prefill,
    )


@bp.route("/coach/clear", methods=["POST"])
@limiter.limit("10 per minute")
def clear():
    if not getattr(g, "is_vip_full", False):
        return redirect(url_for("accueil.index"))
    try:
        clear_coach_messages()
    except Exception as e:
        logger.error("/coach/clear FAILED: %s", e)
    return redirect(url_for("coach.index"))


@bp.route("/coach/conversation/delete", methods=["POST"])
@limiter.limit("20 per minute")
def delete_conversation():
    if not getattr(g, "is_vip_full", False):
        return jsonify({"error": "réservé aux membres PRO"}), 403
    payload = request.get_json(silent=True) or {}
    conv_id = str(payload.get("conversation_id") or "").strip()
    if not conv_id:
        return jsonify({"error": "conversation_id manquant"}), 400
    try:
        delete_coach_conversation(conv_id)
    except Exception as e:
        logger.error("/coach/conversation/delete FAILED: %s", e)
        return jsonify({"error": "suppression échouée"}), 500
    return jsonify({"ok": True})


def _wants_stream() -> bool:
    """Le client demande un flux (Accept: text/event-stream)."""
    return "text/event-stream" in (request.headers.get("Accept") or "")


def _sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _persist_turn(user_id, message, reply, conversation_id, profile, api_key):
    """Enregistre le tour de conversation et met à jour la mémoire du coach.

    Appelé APRÈS que la réponse a été envoyée : ni l'écriture en base ni le
    résumé de mémoire n'allongent l'attente de l'utilisateur.
    """
    new_conversation = False
    conversation_title = None
    if not conversation_id:
        try:
            conversation_title = _title_from_message(message)
            conversation_id = db.create_coach_conversation(user_id, conversation_title)
            new_conversation = bool(conversation_id)
        except Exception as e:
            logger.error("coach create conversation FAILED: %s", e)
            conversation_id = None
    try:
        db.insert_coach_message(user_id, "user", message, conversation_id)
        db.insert_coach_message(user_id, "assistant", reply, conversation_id)
        if conversation_id:
            db.touch_coach_conversation(user_id, conversation_id)
    except Exception as e:
        logger.error("coach persist FAILED: %s", e)

    # Mémoire : on repart de l'historique complet de la conversation.
    try:
        history = db.list_coach_messages(user_id, conversation_id, limit=20) if conversation_id else []
        if coach_memory.should_update(history):
            import anthropic  # type: ignore
            note = coach_memory.build_summary(
                anthropic.Anthropic(api_key=api_key), MODEL,
                coach_memory.get_memory(profile), history)
            if note and note != coach_memory.get_memory(profile):
                db.save_profile(user_id, {"coach_memory": note})
    except Exception as e:
        logger.warning("coach memory update FAILED: %s", e)

    return conversation_id, conversation_title, new_conversation


def _stream_reply(api_key, system_prompt, api_messages, message,
                  conversation_id, limit, count_after, profile):
    """Réponse envoyée au fil de l'eau (Server-Sent Events).

    Le coach mettait 3 à 8 secondes à afficher quoi que ce soit : on regardait
    un point clignoter sans savoir si ça marchait. Ici le texte arrive mot à
    mot, comme dans n'importe quel assistant moderne.
    """
    import anthropic  # type: ignore
    user_id = g.user_id

    def generate():
        chunks = []
        try:
            client = anthropic.Anthropic(api_key=api_key)
            with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                messages=api_messages,
            ) as stream:
                for text in stream.text_stream:
                    if text:
                        chunks.append(text)
                        yield _sse("delta", {"text": text})
        except Exception as e:
            err_type = type(e).__name__
            logger.error("/coach/ask stream FAILED (%s): %s", err_type, str(e)[:300])
            _revert_quota_for(user_id)
            yield _sse("error", {"error": _user_error(str(e))})
            return

        reply = "".join(chunks).strip()
        if not reply:
            _revert_quota_for(user_id)
            yield _sse("error", {"error": "Réponse vide, réessaie."})
            return

        conv_id, title, is_new = _persist_turn(
            user_id, message, reply, conversation_id, profile, api_key)
        yield _sse("done", {
            "conversation_id": conv_id,
            "conversation_title": title,
            "new_conversation": is_new,
            "quota_remaining": max(0, limit - count_after),
            "quota_limit": limit,
        })

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",   # pas de tampon côté proxy
            "Connection": "keep-alive",
        },
    )


def _user_error(err_msg: str) -> str:
    """Message affichable. Les détails (fournisseur, hébergeur, clé) restent
    dans les logs : ils n'apprennent rien à l'utilisateur et font amateur."""
    lower = (err_msg or "").lower()
    if "authentication" in lower or ("invalid" in lower and "api" in lower):
        return "Le coach est momentanément indisponible. Réessaie dans un instant."
    if "credit" in lower or "billing" in lower or "quota" in lower:
        return "Le coach est momentanément indisponible. Réessaie plus tard."
    if "overloaded" in lower or "rate" in lower:
        return "Le coach est très sollicité. Réessaie dans quelques secondes."
    return "Le coach n'a pas pu répondre. Réessaie dans un instant."


def _revert_quota_for(user_id):
    """Comme _revert_quota, mais utilisable hors contexte de requête."""
    try:
        profile = db.get_profile(user_id) or {}
        today = today_paris_str()
        if str(profile.get("coach_quota_date") or "") == today:
            count = int(profile.get("coach_quota_count") or 0)
            if count > 0:
                db.save_profile(user_id, {"coach_quota_date": today,
                                          "coach_quota_count": count - 1})
    except Exception as e:
        logger.error("coach revert_quota (stream) FAILED: %s", e)


@bp.route("/coach/ask", methods=["POST"])
@limiter.limit("30 per minute")
def ask():
    if not getattr(g, "is_vip_full", False):
        return jsonify({"error": "Coach IA réservé aux membres PRO."}), 403
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message vide"}), 400
    if len(message) > 1500:
        message = message[:1500]
    # str() : le client renvoie ce qu'on lui a donné, et rien ne garantit que
    # ce soit une chaîne (un id numérique faisait planter la route).
    conversation_id = str(payload.get("conversation_id") or "").strip() or None

    # _env() strip les guillemets et `=` parasites souvent injectés par Railway
    api_key = _env("ANTHROPIC_API_KEY")
    if not api_key:
        return jsonify({"error": "Coach IA non configuré (ANTHROPIC_API_KEY manquante)."}), 503

    try:
        import anthropic  # type: ignore
    except ImportError:
        return jsonify({"error": "Bibliothèque anthropic absente."}), 503

    # Contexte utilisateur
    try:
        profile = get_profile() or {}
        onboarding = get_onboarding() or {}
        prog = get_prog() or {}
        hist = get_hist() or []
    except Exception as e:
        logger.error("/coach/ask context load FAILED: %s", e)
        profile, onboarding, prog, hist = {}, {}, {}, []

    # Quota (persisté).
    allowed, count_after, limit = _check_and_bump_quota(profile)
    if not allowed:
        return jsonify({
            "error": f"Limite quotidienne atteinte : {limit}/{limit} messages utilisés aujourd'hui. Reviens demain.",
            "quota_remaining": 0,
            "quota_limit": limit,
        }), 429
    track("coach_message", {"count_today": count_after})

    prenom = (onboarding.get("prenom") or "l'athlète").strip() or "l'athlète"
    niveau = onboarding.get("niveau") or "non précisé"
    objectif = onboarding.get("objectif") or "non précisé"
    equipement = onboarding.get("equipement") or "non précisé"
    if isinstance(equipement, list):
        equipement = ", ".join(str(x) for x in equipement) or "non précisé"
    age = onboarding.get("age") or profile.get("age")
    age_str = f"{age} ans" if age else "non précisé"
    poids = profile.get("poids_kg")
    poids_str = f"{poids} kg" if poids else "non précisé"
    taille = profile.get("taille_cm")
    taille_str = f"{taille} cm" if taille else "non précisé"

    system_prompt = SYSTEM_PROMPT_TMPL.format(
        memory_block=coach_memory.format_for_prompt(coach_memory.get_memory(profile)),
        prenom=prenom,
        age=age_str,
        poids=poids_str,
        taille=taille_str,
        niveau=niveau,
        objectif=objectif,
        equipement=equipement,
        programme_detail=_programme_detail(prog),
        dernieres_seances=_dernieres_seances(hist),
        catalog_list=_catalog_list_for_prompt(),
    )

    # Historique (10 derniers) de CETTE conversation comme contexte. Un
    # nouveau chat (conversation_id absent) démarre sans contexte antérieur.
    history = []
    if conversation_id:
        try:
            history = list_coach_messages(conversation_id=conversation_id, limit=10) or []
        except Exception as e:
            logger.error("/coach/ask history load FAILED: %s", e)
            history = []
    api_messages = [
        {"role": m["role"], "content": m["content"]}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    api_messages.append({"role": "user", "content": message})

    if _wants_stream():
        return _stream_reply(api_key, system_prompt, api_messages, message,
                             conversation_id, limit, count_after, profile)

    try:
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=system_prompt,
            messages=api_messages,
        )
        # Concatène les blocs text (Anthropic renvoie une liste de content blocks)
        reply_parts = []
        for block in response.content or []:
            text = getattr(block, "text", None)
            if text:
                reply_parts.append(text)
        reply = "\n".join(reply_parts).strip() or "Désolé, je n'ai pas pu répondre."
    except Exception as e:
        # L'appel API a échoué : on reverse l'incrément de quota pour ne pas
        # faire payer un message qui n'a jamais abouti.
        _revert_quota()
        # On log le détail côté serveur et on renvoie un message parlant au
        # client pour faciliter le debug (sans fuiter la clé API).
        logger.error("/coach/ask anthropic FAILED (%s): %s",
                     type(e).__name__, str(e)[:300])
        return jsonify({"error": _user_error(str(e))}), 502

    # Conversation créée et tour persisté APRÈS l'appel API (pas de
    # conversation vide si l'IA échoue), mémoire mise à jour au passage.
    conversation_id, conversation_title, new_conversation = _persist_turn(
        g.user_id, message, reply, conversation_id, profile, api_key)

    return jsonify({
        "reply": reply,
        "conversation_id": conversation_id,
        "conversation_title": conversation_title,
        "new_conversation": new_conversation,
        "quota_remaining": max(0, limit - count_after),
        "quota_limit": limit,
    })
