from logging.config import fileConfig

from alembic import context

from config.settings import settings


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _legacy_alembic_message() -> str:
    return (
        "NOVA AI now uses MongoDB for persistence, so SQLAlchemy/Alembic migrations are "
        "not part of the active backend workflow. Collections and indexes are created "
        "automatically at startup in config.database.init_db(). "
        f"Current DATABASE_URL: {settings.DATABASE_URL}"
    )


def run_migrations_offline() -> None:
    raise RuntimeError(_legacy_alembic_message())


def run_migrations_online() -> None:
    raise RuntimeError(_legacy_alembic_message())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
