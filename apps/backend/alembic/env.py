import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.db import Base

# Import ALL models so autogenerate detects every table
from app.models.compte import Compte  # noqa: F401
from app.models.marche import Marche  # noqa: F401
from app.models.niche import Niche  # noqa: F401
from app.models.persona import Persona  # noqa: F401
from app.models.comportement import Preset  # noqa: F401
from app.models.crm import Fan, Transaction, Script  # noqa: F401
from app.models.iphone import IPhone  # noqa: F401
from app.models.lien import Domain, TrackedLink, ClickEvent  # noqa: F401
from app.models.log import Event, Incident, AlertRule  # noqa: F401
from app.models.posting import Collection, Media, Template, Campagne, Publication  # noqa: F401
from app.models.proxy import Proxy  # noqa: F401
from app.models.scenario import Scenario, Run, PlageHoraire  # noqa: F401
from app.models.settings import WorkspaceSettings  # noqa: F401
from app.models.statistique import DailyStat  # noqa: F401
from app.models.target import Target  # noqa: F401
from app.models.telegram_pending import TelegramPending  # noqa: F401
from app.models.telegram_pending_group import TelegramPendingGroup  # noqa: F401
from app.models.veille import VeilleSource, Inspiration, Favorite, Snipe, Album  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(settings.database_url, poolclass=pool.NullPool)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
