"""
ig_iphone/health.py — Health check du compte IG avant session.

Verifie que le compte n'est pas en checkpoint/challenge/login_required
avant de lancer une task. Utilise la base de donnees backend.

Usage:
    from app.services.automation.ig_iphone.health import check_account_health
    result = await check_account_health(compte_id, log=log)
    if not result["ok"]:
        log("Compte en %s" % result["status"])
"""

import logging
from uuid import UUID

logger = logging.getLogger("automation.ig_health")


async def check_account_health(compte_id: UUID, log=None) -> dict:
    """Verifie que le compte n est pas en checkpoint/challenge.

    Appeler AVANT de lancer une task.
    Returns: dict {ok, status, error}
      ok=True  -> compte sain, peut lancer la task
      ok=False -> checkpoint/challenge/login_required/suspended
    """
    log = log or logger.info

    try:
        from app.db import AsyncSessionLocal
        from app.models.compte import Compte

        async with AsyncSessionLocal() as db:
            compte = await db.get(Compte, compte_id)
            if not compte:
                log("   [health] compte %s introuvable" % compte_id)
                return {"ok": False, "status": "not_found", "error": "Compte introuvable"}

            status = (compte.status or "").lower()
            handle = compte.handle or "?"

            # Statuts bloquants
            if status in ("checkpoint", "challenge"):
                log("   [health] CHALLENGE - @%s en checkpoint!" % handle)
                return {"ok": False, "status": "challenge", "error": "Compte en checkpoint"}

            if status in ("suspended", "banned", "disabled"):
                log("   [health] SUSPENDED - @%s suspendu!" % handle)
                return {"ok": False, "status": "suspended", "error": "Compte suspendu"}

            if status in ("login_required", "expired"):
                log("   [health] LOGIN_REQUIRED - @%s session expiree!" % handle)
                return {"ok": False, "status": "login_required", "error": "Session expiree"}

            if status in ("consent_required",):
                log("   [health] CONSENT - @%s acceptation requise!" % handle)
                return {"ok": False, "status": "consent_required", "error": "Consentement requis"}

            if status in ("feedback_required",):
                log("   [health] FEEDBACK - @%s action bloquee!" % handle)
                return {"ok": False, "status": "feedback_required", "error": "Action bloquee"}

            # Verifier le champ checkpoint si present
            if hasattr(compte, 'checkpoint') and compte.checkpoint:
                log("   [health] CHECKPOINT flag - @%s" % handle)
                return {"ok": False, "status": "challenge", "error": "Flag checkpoint actif"}

            log("   [health] OK - @%s (status=%s)" % (handle, status or "active"))
            return {"ok": True, "status": "ok", "username": handle}

    except Exception as e:
        log("   [health] erreur: %s" % str(e)[:100])
        return {"ok": False, "status": "error", "error": str(e)[:100]}
