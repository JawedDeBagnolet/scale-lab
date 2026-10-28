import asyncio
import logging
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
        return None

    if (iphone.connection_type or "usb") != "tunnel":
        logger.info("auto_assign_container: iPhone %s en mode USB, skip auto-create", iphone.name)
        return None

    ssh_port = iphone.ssh_port
    if not ssh_port:
        logger.warning("auto_assign_container: iPhone %s sans ssh_port", iphone.name)
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
        return

    iphone = await db.get(IPhone, iphone_uuid)
    if not iphone:
        logger.warning("_ensure_container: iPhone %s introuvable", new_device_id)
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
    """
    try:
        if plateforme == "ig":
            from app.services.automation.ig_runner import run_ig_task
            ok, msg = await run_ig_task(compte_id, "ig_login")
        elif plateforme == "th":
            from app.services.automation.th_runner import run_th_task
            ok, msg = await run_th_task(compte_id, "th_login")
        else:
            logger.info("auto_login: pas de script login pour plateforme '%s'", plateforme)
            return

        if ok:
            logger.info("auto_login: compte %s connecté — %s", compte_id, msg)
        else:
            logger.error("auto_login: échec compte %s — %s", compte_id, msg)
    except Exception:
        logger.exception("auto_login: erreur inattendue pour compte %s", compte_id)


async def create_compte(db: AsyncSession, data: CompteCreate) -> Compte:
    await _check_persona(db, data.persona_id)
    dump = data.model_dump()
    # Encrypt credentials before storing
    if dump.get("creds_encrypted"):
        dump["creds_encrypted"] = encrypt_creds(dump["creds_encrypted"])
    compte = Compte(**dump)
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
        setattr(compte, key, value)

    # Auto-create container when assigning to a new iPhone
    if device_changed:
        await _ensure_container_on_assign(db, compte, new_device_id)

    await db.commit()
    return compte


async def delete_compte(db: AsyncSession, compte: Compte) -> None:
    await db.delete(compte)
    await db.commit()
