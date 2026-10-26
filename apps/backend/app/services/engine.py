"""Execution engine — background service that advances scenario runs.

Lifecycle:
    pending → running → done | error | aborted
    running ↔ paused (manual toggle)

Step lifecycle per account:
    todo → delay → running → ok | error | skipped

The engine loop wakes periodically (or at next_wake_at) and processes all
active runs. iPhone command dispatch is a stub until Point 5 (USB detection).
"""

import asyncio
import logging
import random
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models.compte import Compte
from app.models.iphone import IPhone
from app.models.scenario import PlageHoraire, Run, Scenario
from app.services.logs import emit_event
from app.ws import manager as ws_manager

logger = logging.getLogger("engine")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TICK_INTERVAL = 5          # seconds between engine ticks
BLOCKED_STATUSES = {"error", "suspendu", "session"}  # compte.status values that block execution
JOURNAL_BROADCAST_TAIL = 5  # how many recent journal entries to broadcast


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(UTC)


def _journal_entry(
    run_id: UUID,
    event: str,
    *,
    account_id: UUID | None = None,
    step: int | None = None,
    detail: str | None = None,
) -> dict:
    return {
        "ts": _now().isoformat(),
        "run_id": str(run_id),
        "account_id": str(account_id) if account_id else None,
        "step": step,
        "event": event,
        "detail": detail,
    }


def _delay_seconds(delay_cfg: dict) -> float:
    """Convert a delay config to seconds to wait.

    Delay modes (from frontend norm):
        none  → 0
        dur   → fixed minutes  {mode:"dur", min: N}
        rand  → random range   {mode:"rand", min: N, max: M}
        at    → specific time  {mode:"at", time: "HH:MM", day: offset}
    """
    mode = delay_cfg.get("mode", "none")
    if mode == "none":
        return 0
    if mode == "dur":
        return float(delay_cfg.get("min", 0)) * 60
    if mode == "rand":
        lo = float(delay_cfg.get("min", 0))
        hi = float(delay_cfg.get("max", lo))
        return random.uniform(lo, hi) * 60
    if mode == "at":
        # Calculate seconds until target time (today or +day offset)
        target_time = delay_cfg.get("time", "00:00")
        day_offset = int(delay_cfg.get("day", 0))
        h, m = (int(x) for x in target_time.split(":"))
        now = _now()
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        target += timedelta(days=day_offset)
        diff = (target - now).total_seconds()
        return max(diff, 0)
    return 0


async def _is_in_slot(db: AsyncSession, slot_ids: list, now: datetime | None = None) -> bool:
    """Check if current time falls within any of the given plage horaire slots."""
    if not slot_ids:
        return True  # no slot restriction

    now = now or _now()
    weekday = now.weekday()  # 0=Monday
    current_time = now.strftime("%H:%M")

    for sid in slot_ids:
        try:
            uid = UUID(str(sid)) if not isinstance(sid, UUID) else sid
        except (ValueError, AttributeError):
            continue
        plage = await db.get(PlageHoraire, uid)
        if not plage:
            continue
        # Check day
        days = plage.days or list(range(7))
        if weekday not in days:
            continue
        # Check time ranges
        ranges = plage.ranges or []
        if not ranges:
            return True  # day matches, no time restriction
        for r in ranges:
            if r.get("start", "00:00") <= current_time <= r.get("end", "23:59"):
                return True
    return False


async def _next_slot_opening(db: AsyncSession, slot_ids: list) -> datetime | None:
    """Find the earliest future datetime when a slot opens.

    Returns None if no slot data or slots are always open.
    """
    if not slot_ids:
        return None

    now = _now()
    best: datetime | None = None

    for sid in slot_ids:
        try:
            uid = UUID(str(sid)) if not isinstance(sid, UUID) else sid
        except (ValueError, AttributeError):
            continue
        plage = await db.get(PlageHoraire, uid)
        if not plage:
            continue

        days = plage.days or list(range(7))
        ranges = plage.ranges or [{"start": "00:00", "end": "23:59"}]

        # Check next 7 days
        for day_offset in range(8):
            candidate = now + timedelta(days=day_offset)
            wd = candidate.weekday()
            if wd not in days:
                continue
            for r in ranges:
                h, m = (int(x) for x in r.get("start", "00:00").split(":"))
                slot_start = candidate.replace(hour=h, minute=m, second=0, microsecond=0)
                if slot_start > now:
                    if best is None or slot_start < best:
                        best = slot_start
    return best


async def _check_account_status(db: AsyncSession, account_id: UUID) -> str:
    """Return 'ok', 'blocked', or 'waiting' based on account + device state.

    Uses the USB monitor's live connected set when available,
    falls back to the DB status field.
    """
    from app.services.usb import usb_monitor, _find_iphone_by_udid

    compte = await db.get(Compte, account_id)
    if not compte:
        return "blocked"  # account deleted

    if compte.status in BLOCKED_STATUSES:
        return "blocked"

    # Check if the account's iPhone is online (for iPhone platforms)
    if compte.device_id:
        try:
            device_uid = UUID(compte.device_id)
            iphone = await db.get(IPhone, device_uid)
            if iphone:
                # Prefer live USB monitor state
                if usb_monitor.is_running:
                    udid = (iphone.telemetry or {}).get("udid")
                    if udid and udid not in usb_monitor._known_serials:
                        return "waiting"
                elif iphone.status != "online":
                    return "waiting"
        except (ValueError, AttributeError):
            pass

    return "ok"


# ---------------------------------------------------------------------------
# Action execution
# ---------------------------------------------------------------------------

# iPhone platform prefixes that require a USB-connected device
IPHONE_PLATFORMS = {"ig_iph", "th_iph"}

async def _execute_action(
    account_id: UUID,
    platform: str,
    action_type: str,
    values: dict,
    preset_ids: list,
) -> tuple[bool, str]:
    """Execute a single action on an account.

    Returns (success: bool, detail: str).

    For iPhone platforms: dispatches via USB if the device is connected.
    For web platforms: STUB (will be replaced by browser automation in Point 4).
    """
    if platform in IPHONE_PLATFORMS:
        return await _execute_iphone_action(account_id, platform, action_type, values, preset_ids)

    # Web platforms (th_web, x_web, stories) — still a stub
    logger.info(
        "STUB web execute: account=%s platform=%s action=%s",
        account_id, platform, action_type,
    )
    await asyncio.sleep(0.1)
    return True, f"stub: {action_type} executed (web)"


async def _execute_iphone_action(
    account_id: UUID,
    platform: str,
    action_type: str,
    values: dict,
    preset_ids: list,
) -> tuple[bool, str]:
    """Execute an action on an iPhone via the automation stack.

    Uses DeviceSession + IGDriver/THDriver for real UI automation.
    DeviceSession handles connection mode (USB/tunnel) transparently
    by resolving the account → device → MCP/SSH ports from PostgreSQL.
    """
    if platform == "ig_iph":
        from app.services.automation.ig_runner import run_ig_task
        return await run_ig_task(
            account_id,
            action_type,
            values=values,
            preset_ids=preset_ids,
        )

    elif platform == "th_iph":
        from app.services.automation.th_runner import run_th_task
        return await run_th_task(
            account_id,
            action_type,
            values=values,
            preset_ids=preset_ids,
        )

    return False, f"Plateforme iPhone inconnue : {platform}"


# ---------------------------------------------------------------------------
# Core engine tick
# ---------------------------------------------------------------------------

async def _process_run(db: AsyncSession, run: Run) -> None:
    """Advance a single run by one tick."""
    # Load scenario
    scenario = await db.get(Scenario, run.scenario_id)
    if not scenario:
        run.status = "error"
        run.journal = (run.journal or []) + [
            _journal_entry(run.id, "error", detail="Scenario not found")
        ]
        run.finished_at = _now()
        await db.commit()
        return

    steps = scenario.steps or []
    if not steps:
        run.status = "done"
        run.journal = (run.journal or []) + [
            _journal_entry(run.id, "done", detail="No steps to execute")
        ]
        run.finished_at = _now()
        await db.commit()
        return

    accounts = [UUID(a) if isinstance(a, str) else a for a in (run.comptes or [])]
    if not accounts:
        run.status = "done"
        run.finished_at = _now()
        await db.commit()
        return

    progress: dict = dict(run.account_progress or {})
    config: dict = dict(run.config or {})
    journal: list = list(run.journal or [])
    ignore_slots = config.get("ignore_slots", False)

    current_step_idx = run.current_step or 0

    if current_step_idx >= len(steps):
        # All steps done — check if loop
        if scenario.loop:
            run.current_step = 0
            journal.append(_journal_entry(run.id, "loop_restart"))
            run.journal = journal
            await db.commit()
            return
        run.status = "done"
        run.finished_at = _now()
        journal.append(_journal_entry(run.id, "done"))
        run.journal = journal
        await db.commit()
        await _broadcast_run(run)
        return

    # Current step data: [platform, [[action_type, {values}, [preset_ids]], ...], {delay_config}, [slot_ids]]
    step = steps[current_step_idx]
    platform = step[0] if len(step) > 0 else ""
    actions = step[1] if len(step) > 1 else []
    delay_cfg = step[2] if len(step) > 2 else {}
    step_slots = step[3] if len(step) > 3 else (scenario.slots or [])

    # Check plage horaire (unless ignore_slots)
    if not ignore_slots and step_slots:
        in_slot = await _is_in_slot(db, step_slots)
        if not in_slot:
            # Schedule wake at next slot opening
            next_open = await _next_slot_opening(db, step_slots)
            run.next_wake_at = next_open
            # Mark all accounts on this step as waiting
            for acc_id in accounts:
                acc_key = str(acc_id)
                acc_progress = progress.get(acc_key, {})
                step_key = str(current_step_idx)
                if acc_progress.get(step_key) not in ("ok", "error", "skipped"):
                    acc_progress[step_key] = "waiting"
                progress[acc_key] = acc_progress
            run.account_progress = progress
            run.journal = journal
            await db.commit()
            await _broadcast_run(run)
            return

    # Process delay phase
    delay_secs = _delay_seconds(delay_cfg or {})
    if delay_secs > 0:
        # Check if we've already started the delay
        delay_started_key = f"_delay_started_{current_step_idx}"
        delay_start_ts = config.get(delay_started_key)
        if not delay_start_ts:
            # Start the delay now
            config[delay_started_key] = _now().isoformat()
            run.config = config
            run.next_wake_at = _now() + timedelta(seconds=delay_secs)
            # Mark accounts as delay
            for acc_id in accounts:
                acc_key = str(acc_id)
                acc_progress = progress.get(acc_key, {})
                step_key = str(current_step_idx)
                if acc_progress.get(step_key) not in ("ok", "error", "skipped"):
                    acc_progress[step_key] = "delay"
                progress[acc_key] = acc_progress
            run.account_progress = progress
            journal.append(_journal_entry(
                run.id, "delay_start", step=current_step_idx,
                detail=f"{delay_secs:.0f}s delay",
            ))
            run.journal = journal
            await db.commit()
            await _broadcast_run(run)
            return
        else:
            # Check if delay has elapsed
            started = datetime.fromisoformat(delay_start_ts)
            if (_now() - started).total_seconds() < delay_secs:
                # Still waiting
                return

    # Execute actions on each account
    all_done = True
    any_running = False

    for acc_id in accounts:
        acc_key = str(acc_id)
        acc_progress = progress.get(acc_key, {})
        step_key = str(current_step_idx)
        current_status = acc_progress.get(step_key, "todo")

        # Skip already completed accounts
        if current_status in ("ok", "error", "skipped"):
            continue

        # Check account health
        acc_status = await _check_account_status(db, acc_id)
        if acc_status == "blocked":
            acc_progress[step_key] = "blocked"
            progress[acc_key] = acc_progress
            journal.append(_journal_entry(
                run.id, "blocked", account_id=acc_id, step=current_step_idx,
                detail="Account blocked (checkpoint/suspended/session)",
            ))
            # Add to blocked_accounts if not already there
            blocked = list(run.blocked_accounts or [])
            if acc_key not in blocked:
                blocked.append(acc_key)
                run.blocked_accounts = blocked
            continue

        if acc_status == "waiting":
            acc_progress[step_key] = "waiting"
            progress[acc_key] = acc_progress
            all_done = False
            continue

        # Mark as running
        acc_progress[step_key] = "running"
        progress[acc_key] = acc_progress
        any_running = True

        # Execute each action in the step
        step_ok = True
        for action_tuple in actions:
            action_type = action_tuple[0] if len(action_tuple) > 0 else ""
            values = action_tuple[1] if len(action_tuple) > 1 else {}
            preset_ids = action_tuple[2] if len(action_tuple) > 2 else []

            success, detail = await _execute_action(
                acc_id, platform, action_type, values, preset_ids,
            )
            journal.append(_journal_entry(
                run.id,
                "action_ok" if success else "action_err",
                account_id=acc_id,
                step=current_step_idx,
                detail=f"{action_type}: {detail}",
            ))
            if not success:
                step_ok = False
                await emit_event(
                    module="scenarios",
                    event_type="action.error",
                    level="error",
                    target=str(acc_id),
                    message=f"Erreur action '{action_type}' step {current_step_idx}: {detail}",
                    meta={"run_id": str(run.id), "step": current_step_idx, "platform": platform},
                )
                break

        acc_progress[step_key] = "ok" if step_ok else "error"
        progress[acc_key] = acc_progress

    # Update run
    run.account_progress = progress
    run.journal = journal

    # Check if all accounts have finished this step
    all_accounts_done = True
    for acc_id in accounts:
        acc_key = str(acc_id)
        acc_progress = progress.get(acc_key, {})
        step_key = str(current_step_idx)
        status = acc_progress.get(step_key, "todo")
        if status not in ("ok", "error", "skipped", "blocked"):
            all_accounts_done = False
            break

    if all_accounts_done:
        # Advance to next step
        run.current_step = current_step_idx + 1
        run.next_wake_at = None  # clear delay tracking
        # Clean delay tracking from config
        delay_started_key = f"_delay_started_{current_step_idx}"
        if delay_started_key in (run.config or {}):
            cfg = dict(run.config)
            del cfg[delay_started_key]
            run.config = cfg

        journal.append(_journal_entry(
            run.id, "step_done", step=current_step_idx,
        ))
        run.journal = journal

        # Check if this was the last step
        if run.current_step >= len(steps):
            if scenario.loop:
                run.current_step = 0
                journal.append(_journal_entry(run.id, "loop_restart"))
                run.journal = journal
            else:
                run.status = "done"
                run.finished_at = _now()
                journal.append(_journal_entry(run.id, "done"))
                run.journal = journal

    await db.commit()
    await _broadcast_run(run)

    if run.status == "done":
        await emit_event(
            module="scenarios",
            event_type="run.done",
            level="info",
            target=scenario.name if scenario else None,
            message=f"Run terminé avec succès",
            meta={"run_id": str(run.id)},
        )


async def _broadcast_run(run: Run) -> None:
    """Send run progress to WebSocket clients."""
    if ws_manager.count == 0:
        return
    journal = run.journal or []
    tail = journal[-JOURNAL_BROADCAST_TAIL:] if journal else []
    await ws_manager.broadcast({
        "type": "run_progress",
        "run_id": str(run.id),
        "status": run.status,
        "current_step": run.current_step,
        "account_progress": run.account_progress or {},
        "journal_tail": tail,
        "ts": _now().isoformat(),
    })


# ---------------------------------------------------------------------------
# Engine loop
# ---------------------------------------------------------------------------

class ExecutionEngine:
    """Background asyncio service that ticks active runs."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop(), name="execution-engine")
        logger.info("Execution engine started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Execution engine stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                await self._tick()
            except Exception:
                logger.exception("Engine tick error")
            await asyncio.sleep(TICK_INTERVAL)

    async def _tick(self) -> None:
        """Find active runs and process them."""
        async with AsyncSessionLocal() as db:
            now = _now()
            # Find runs that are running and due for processing
            q = (
                select(Run)
                .where(Run.status == "running")
                .where(
                    # Either no wake time, or wake time has passed
                    (Run.next_wake_at.is_(None)) | (Run.next_wake_at <= now)
                )
            )
            result = await db.execute(q)
            runs = result.scalars().all()

            for run in runs:
                try:
                    await _process_run(db, run)
                except Exception:
                    logger.exception("Error processing run %s", run.id)
                    # Mark run as errored
                    run.status = "error"
                    run.finished_at = now
                    run.journal = (run.journal or []) + [
                        _journal_entry(run.id, "error", detail="Engine processing error")
                    ]
                    await db.commit()
                    await _broadcast_run(run)
                    await emit_event(
                        module="scenarios",
                        event_type="run.error",
                        level="critical",
                        message=f"Erreur critique moteur d'exécution",
                        meta={"run_id": str(run.id)},
                    )

    @property
    def is_running(self) -> bool:
        return self._running


# Singleton
engine = ExecutionEngine()


# ---------------------------------------------------------------------------
# Control functions (called from API endpoints)
# ---------------------------------------------------------------------------

async def launch_run(
    db: AsyncSession,
    scenario_id: UUID,
    comptes: list[UUID],
    *,
    ignore_slots: bool = False,
    launched_by: str | None = None,
) -> Run:
    """Create and start a new run."""
    scenario = await db.get(Scenario, scenario_id)
    if not scenario:
        raise ValueError("Scenario not found")

    # Initialize per-account progress
    account_progress: dict = {}
    for acc_id in comptes:
        account_progress[str(acc_id)] = {}

    run = Run(
        scenario_id=scenario_id,
        comptes=[str(a) for a in comptes],
        current_step=0,
        status="running",
        account_progress=account_progress,
        config={
            "ignore_slots": ignore_slots,
            "launched_by": launched_by,
            "scenario_name": scenario.name,
        },
        journal=[_journal_entry(
            UUID("00000000-0000-0000-0000-000000000000"),  # placeholder, will update
            "started",
            detail=f"Launched scenario '{scenario.name}' on {len(comptes)} account(s)",
        )],
        started_at=_now(),
    )
    db.add(run)
    await db.flush()

    # Fix journal entry with real run ID
    run.journal = [_journal_entry(
        run.id, "started",
        detail=f"Launched scenario '{scenario.name}' on {len(comptes)} account(s)",
    )]
    await db.commit()
    await db.refresh(run)

    await _broadcast_run(run)
    logger.info("Launched run %s for scenario %s", run.id, scenario.name)
    await emit_event(
        module="scenarios",
        event_type="run.started",
        level="info",
        target=scenario.name,
        message=f"Run lancé : '{scenario.name}' sur {len(comptes)} compte(s)",
        meta={"run_id": str(run.id), "scenario_id": str(scenario_id)},
    )
    return run


async def pause_run(db: AsyncSession, run: Run) -> Run:
    """Pause a running run."""
    if run.status != "running":
        raise ValueError(f"Cannot pause run in status '{run.status}'")
    run.status = "paused"
    run.journal = (run.journal or []) + [
        _journal_entry(run.id, "paused")
    ]
    await db.commit()
    await db.refresh(run)
    await _broadcast_run(run)
    await emit_event(
        module="scenarios",
        event_type="run.paused",
        level="warning",
        message=f"Run mis en pause",
        meta={"run_id": str(run.id)},
    )
    return run


async def resume_run(db: AsyncSession, run: Run) -> Run:
    """Resume a paused run."""
    if run.status != "paused":
        raise ValueError(f"Cannot resume run in status '{run.status}'")
    run.status = "running"
    run.next_wake_at = None  # process immediately
    run.journal = (run.journal or []) + [
        _journal_entry(run.id, "resumed")
    ]
    await db.commit()
    await db.refresh(run)
    await _broadcast_run(run)
    await emit_event(
        module="scenarios",
        event_type="run.resumed",
        level="info",
        message=f"Run repris",
        meta={"run_id": str(run.id)},
    )
    return run


async def skip_step(db: AsyncSession, run: Run) -> Run:
    """Skip current step for all accounts."""
    if run.status not in ("running", "paused"):
        raise ValueError(f"Cannot skip step on run in status '{run.status}'")

    scenario = await db.get(Scenario, run.scenario_id)
    steps = (scenario.steps if scenario else []) or []
    current = run.current_step or 0

    if current >= len(steps):
        raise ValueError("No more steps to skip")

    # Mark current step as skipped for all accounts
    progress = dict(run.account_progress or {})
    for acc_key in progress:
        acc_progress = progress[acc_key]
        step_key = str(current)
        if acc_progress.get(step_key) not in ("ok", "error"):
            acc_progress[step_key] = "skipped"
        progress[acc_key] = acc_progress

    run.account_progress = progress
    run.current_step = current + 1
    run.next_wake_at = None
    # Clean delay tracking
    cfg = dict(run.config or {})
    cfg.pop(f"_delay_started_{current}", None)
    run.config = cfg
    run.journal = (run.journal or []) + [
        _journal_entry(run.id, "skipped", step=current, detail="Step skipped by user")
    ]

    # Check if run is done
    if run.current_step >= len(steps):
        if scenario and scenario.loop:
            run.current_step = 0
        else:
            run.status = "done"
            run.finished_at = _now()
            run.journal = run.journal + [_journal_entry(run.id, "done")]

    await db.commit()
    await db.refresh(run)
    await _broadcast_run(run)
    return run


async def abort_run(db: AsyncSession, run: Run) -> Run:
    """Abort a run entirely."""
    if run.status in ("done", "aborted"):
        raise ValueError(f"Run already in terminal status '{run.status}'")
    run.status = "aborted"
    run.finished_at = _now()
    run.journal = (run.journal or []) + [
        _journal_entry(run.id, "aborted")
    ]
    await db.commit()
    await db.refresh(run)
    await _broadcast_run(run)
    await emit_event(
        module="scenarios",
        event_type="run.aborted",
        level="warning",
        message=f"Run annulé",
        meta={"run_id": str(run.id)},
    )
    return run
