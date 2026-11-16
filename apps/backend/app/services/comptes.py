import asyncio
import logging
import traceback
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.crypto import decrypt_creds, encrypt_creds
from app.models.compte import Compte
from app.models.iphone import IPhone
from app.models.persona import Persona
from app.schemas.compte import CompteCreate, CompteUpdate

logger = logging.getLogger("services.comptes")


class PersonaNotFound(Exception):
    pass


# ── Bundle mapping ──────────────────────────────────────────────────────────

_PLATEFORME_TO_BUNDLE = {
    "ig": "com.burbn.instagram",
    "th": "com.burbn.barcelona",
}


async def _log(module, event_type, level, target, message, **kw):
    """Emit a log event (fire-and-forget)."""
    try:
        from app.services.logs import emit_event
        await emit_event(module=module, event_type=event_type, level=level, target=target, message=message, **kw)
    except Exception:
        import logging
        logging.getLogger("comptes").warning("Failed to emit log event: %s", message)


async def _check_persona(db: AsyncSession, persona_id: UUID | None) -> None:
    if persona_id is not None and await db.get(Persona, persona_id) is None:
        raise PersonaNotFound


async def _auto_assign_container(
    db: AsyncSession,
    compte: Compte,
    iphone: IPhone,
) -> str | None:
    """Create a ScaleTweak container on the iPhone for this account.

    Called automatically when device_id is set and no container_uuid exists.
    Returns the container UUID or None on failure.
    """
    bundle = _PLATEFORME_TO_BUNDLE.get(compte.plateforme)
    if not bundle:
        logger.warning("auto_assign_container: plateforme '%s' sans bundle connu", compte.plateforme)
        await _log("comptes", "container", "error", compte.handle, f"Plateforme {compte.plateforme} sans bundle connu — impossible de créer le container")
        return None

    if (iphone.connection_type or "usb") != "tunnel":
        logger.info("auto_assign_container: iPhone %s en mode USB, skip auto-create", iphone.name)
        await _log("infra", "device", "warning", iphone.name, f"{iphone.name} en mode USB — création container ignorée pour @{compte.handle}")
        return None

    ssh_port = iphone.ssh_port
    if not ssh_port:
        logger.warning("auto_assign_container: iPhone %s sans ssh_port", iphone.name)
        await _log("infra", "device", "error", iphone.name, f"{iphone.name} sans port SSH configuré — impossible de créer le container pour @{compte.handle}")
        return None

    # Import here to avoid circular imports
    from app.services.dispatch import scalectl_create_container

    container_name = f"{compte.handle}_{compte.plateforme}"
    country = "FR"  # default geo profile

    logger.info(
        "auto_assign_container: création container '%s' sur %s (port SSH %d)",
        container_name, iphone.name, ssh_port,
    )

    container_uuid = await scalectl_create_container(
        ssh_port, bundle, container_name, country,
    )

    if not container_uuid:
        logger.error("auto_assign_container: scalectl_create_container a échoué")
        await _log("infra", "device", "error", iphone.name, f"Création du container échouée sur {iphone.name} pour @{compte.handle}", code="CONTAINER_CREATE_FAILED")
        return None

    logger.info("auto_assign_container: container créé → %s", container_uuid[:8])
    return container_uuid


async def _ensure_container_on_assign(
    db: AsyncSession,
    compte: Compte,
    new_device_id: str | None,
) -> None:
    """If device_id is being set and no container_uuid exists, auto-create one."""
    if not new_device_id:
        return

    # Already has a container?
    env = compte.env or {}
    if env.get("container_uuid"):
        return

    # Load the iPhone
    try:
        iphone_uuid = UUID(new_device_id)
    except (ValueError, TypeError):
        logger.warning("_ensure_container: device_id invalide: %s", new_device_id)
        await _log("comptes", "session", "error", compte.handle, f"Device ID invalide: {new_device_id}")
        return

    iphone = await db.get(IPhone, iphone_uuid)
    if not iphone:
        logger.warning("_ensure_container: iPhone %s introuvable", new_device_id)
        await _log("infra", "device", "error", str(new_device_id), f"iPhone {new_device_id} introuvable en base")
        return

    container_uuid = await _auto_assign_container(db, compte, iphone)
    if container_uuid:
        env["container_uuid"] = container_uuid
        compte.env = env


async def list_comptes(
    db: AsyncSession, persona_id: UUID | None = None, plateforme: str | None = None
) -> Sequence[Compte]:
    q = select(Compte).order_by(Compte.handle)
    if persona_id:
        q = q.where(Compte.persona_id == persona_id)
    if plateforme:
        q = q.where(Compte.plateforme == plateforme)
    result = await db.execute(q)
    return result.scalars().all()


async def get_compte(db: AsyncSession, compte_id: UUID) -> Compte | None:
    return await db.get(Compte, compte_id)


async def _dispatch_auto_login(compte_id: UUID, plateforme: str) -> None:
    """Fire the automatic login task after compte creation.

    Runs as a background asyncio task — errors are logged, not raised.
    Uses LogCollector to capture session logs for display in alert modals.
    """
    from app.services.engine import LogCollector

    runner_log = logging.getLogger("automation.ig_runner")
    collector = LogCollector(upstream=runner_log.info)
    try:
        if plateforme == "ig":
            from app.services.automation.ig_runner import run_ig_task
            ok, msg = await run_ig_task(compte_id, "ig_login", log=collector)
        elif plateforme == "th":
            from app.services.automation.th_runner import run_th_task
            ok, msg = await run_th_task(compte_id, "th_login", log=collector)
        else:
            logger.info("auto_login: pas de script login pour plateforme '%s'", plateforme)
            await _log("comptes", "login", "warning", str(compte_id), f"Pas de script de login pour la plateforme {plateforme}")
            return

        meta = {"session_logs": collector.lines} if collector.lines else None
        if ok:
            logger.info("auto_login: compte %s connecté — %s", compte_id, msg)
            await _log("comptes", "login", "success", str(compte_id), f"Compte connecté — {msg}", meta=meta)
        else:
            logger.error("auto_login: échec compte %s — %s", compte_id, msg)
            await _log("comptes", "login", "error", str(compte_id), f"Échec connexion — {msg}", code="LOGIN_FAILED", meta=meta)
    except Exception:
        logger.exception("auto_login: erreur inattendue pour compte %s", compte_id)
        meta = {"session_logs": collector.lines} if collector.lines else None
        await _log("comptes", "login", "error", str(compte_id), f"Erreur inattendue lors du login: {traceback.format_exc()[-200:]}", code="LOGIN_EXCEPTION", meta=meta)


async def _dispatch_profile_edit(compte_id: UUID, plateforme: str, fields: dict, handle: str = "") -> None:
    """Dispatch profile edit to the iPhone automation.

    Runs as a background asyncio task. Maps frontend field names to
    configure_profile kwargs (bio, name, link, etc.) and captures session logs.
    """
    from app.services.engine import LogCollector

    runner_log = logging.getLogger("automation.ig_runner")
    logger.info("_dispatch_profile_edit: %s fields=%s", handle or compte_id, list(fields.keys()))
    collector = LogCollector(upstream=runner_log.info)

    # Map frontend fields to configure_profile kwargs
    FIELD_MAP = {
        "username": "username",
        "full_name": "name",
        "biography": "bio",
        "external_url": "link",
        "is_private": "private",
        "is_business": "pro",
        "age_limit": "age_limit",
        "photo_url": "photo_url",
    }

    config_values = {}
    requested_fields = []
    for frontend_key, value in fields.items():
        config_key = FIELD_MAP.get(frontend_key, frontend_key)
        config_values[config_key] = value
        requested_fields.append(config_key)

    if not config_values:
        await _log("comptes", "profile_edit", "warning", handle or str(compte_id),
                    "Modification profil — aucun champ à modifier", code="PROFILE_EDIT_EMPTY")
        return

    collector = LogCollector()
    try:
        if plateforme == "ig":
            from app.services.automation.ig_runner import run_ig_task
            ok, msg = await run_ig_task(compte_id, "ig_config", values={"config": config_values}, log=collector)
        else:
            await _log("comptes", "profile_edit", "warning", handle or str(compte_id),
                        f"Pas de script de config profil pour {plateforme}")
            return

        meta = {
            "session_logs": collector.lines,
            "fields": requested_fields,
        }
        if ok:
            logger.info("profile_edit: %s configuré — %s", handle or compte_id, msg)
            await _log("comptes", "profile_edit", "success", handle or str(compte_id),
                        f"Profil configuré — {', '.join(requested_fields)}", meta=meta)
            # Persist age_limit in profile_config after successful automation
            if "age_limit" in config_values:
                try:
                    from app.db import AsyncSessionLocal
                    from app.models.compte import Compte
                    from sqlalchemy.orm.attributes import flag_modified
                    async with AsyncSessionLocal() as db:
                        c = await db.get(Compte, compte_id)
                        if c:
                            cfg = dict(c.profile_config or {})
                            cfg["age_limit"] = config_values["age_limit"]
                            c.profile_config = cfg
                            flag_modified(c, "profile_config")
                            await db.commit()
                            logger.info("profile_edit: age_limit=%s saved to profile_config", config_values["age_limit"])
                except Exception as e:
                    logger.warning("profile_edit: failed to persist age_limit: %s", e)
        else:
            logger.error("profile_edit: échec %s — %s", handle or compte_id, msg)
            await _log("comptes", "profile_edit", "error", handle or str(compte_id),
                        f"Échec modification profil — ig_config: aucun champ configuré (demandés: {requested_fields})",
                        code="PROFILE_EDIT_FAILED", meta=meta)
    except Exception:
        logger.exception("profile_edit: erreur inattendue pour %s", handle or compte_id)
        meta = {"session_logs": collector.lines, "fields": requested_fields}
        await _log("comptes", "profile_edit", "error", handle or str(compte_id),
                    f"Erreur inattendue modification profil: {traceback.format_exc()[-200:]}",
                    code="PROFILE_EDIT_EXCEPTION", meta=meta)


async def _pick_free_iphone(db: AsyncSession):
    """Pick the iPhone with the fewest assigned accounts (load balancing)."""
    from sqlalchemy import func
    stmt = (
        select(IPhone)
        .where(IPhone.status == "online")
        .outerjoin(Compte, Compte.device_id == IPhone.id)
        .group_by(IPhone.id)
        .order_by(func.count(Compte.id).asc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def create_compte(db: AsyncSession, data: CompteCreate) -> Compte:
    await _check_persona(db, data.persona_id)
    dump = data.model_dump()
    # Encrypt credentials before storing
    if dump.get("creds_encrypted"):
        dump["creds_encrypted"] = encrypt_creds(dump["creds_encrypted"])
    compte = Compte(**dump)
    # Auto-assign iPhone for scraper accounts without a specific device
    if compte.is_scraper and not compte.device_id:
        free_iphone = await _pick_free_iphone(db)
        if free_iphone:
            compte.device_id = free_iphone.id
            logger.info("create_compte: auto-assigned scraper @%s to iPhone %s", compte.handle, free_iphone.name)
    # Auto-assign container if device_id provided at creation
    if compte.device_id:
        await _ensure_container_on_assign(db, compte, compte.device_id)
    db.add(compte)
    await db.commit()

    # ── Auto-login dispatch ──────────────────────────────────────────────
    # If a device was assigned and a container successfully created,
    # fire the platform login script as a background task.
    if compte.device_id and (compte.env or {}).get("container_uuid"):
        asyncio.create_task(
            _dispatch_auto_login(compte.id, compte.plateforme),
            name=f"auto_login_{compte.handle}",
        )
        logger.info(
            "create_compte: login auto lancé pour %s sur device %s (container %s)",
            compte.handle, compte.device_id, compte.env["container_uuid"][:8],
        )
        await _log("comptes", "login", "info", compte.handle, f"Login auto lancé sur container {compte.env['container_uuid'][:8]}")

    return compte


async def get_compte_creds(db: AsyncSession, compte_id: UUID) -> dict | None:
    """Return decrypted credentials for a compte (internal use only)."""
    compte = await db.get(Compte, compte_id)
    if not compte or not compte.creds_encrypted:
        return None
    return decrypt_creds(compte.creds_encrypted)


async def update_compte(db: AsyncSession, compte: Compte, data: CompteUpdate) -> Compte:
    changes = data.model_dump(exclude_unset=True)
    await _check_persona(db, changes.get("persona_id"))

    # Encrypt credentials before storing
    if "creds_encrypted" in changes and changes["creds_encrypted"]:
        changes["creds_encrypted"] = encrypt_creds(changes["creds_encrypted"])

    # Detect device_id change → auto container
    new_device_id = changes.get("device_id")
    device_changed = (
        new_device_id is not None
        and new_device_id != compte.device_id
    )

    for key, value in changes.items():
        # MERGE env JSONB instead of overwriting — the frontend sends partial
        # env (web/phone/iphone) without container_uuid, proxy_country etc.
        if key == "env" and isinstance(value, dict):
            merged = {**(compte.env or {}), **value}
            setattr(compte, key, merged)
        else:
            setattr(compte, key, value)

    # Auto-create container when assigning to a new iPhone
    if device_changed:
        await _ensure_container_on_assign(db, compte, new_device_id)

    await db.commit()
    return compte


async def delete_compte(db: AsyncSession, compte: Compte) -> None:
    await db.delete(compte)
    await db.commit()
