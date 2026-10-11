from logging.config import fileConfig

from alembic import context
from sqlalchemy import Engine, create_engine, event, pool

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.config import settings
from app.database import Base
from app.database.types import LocalDateTime

config = context.config

# Skip when run from inside the app (see app/database/migrations.py) so Alembic
# doesn't reconfigure uvicorn's logging.
if config.config_file_name is not None and config.attributes.get("configure_logger", True):
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_url() -> str:
    # An explicit sqlalchemy.url (set programmatically, e.g. by tests) wins over .env settings.
    return config.get_main_option("sqlalchemy.url") or settings.database_url


def _render_item(type_, obj, autogen_context):
    # LocalDateTime is a Python-side conversion over a plain DATETIME column; render it as
    # sa.DateTime() so migration scripts don't import application code.
    if type_ == "type" and isinstance(obj, LocalDateTime):
        return "sa.DateTime()"
    return False


_CONTEXT_OPTS = dict(
    target_metadata=target_metadata,
    render_as_batch=True,  # SQLite can't ALTER most things; batch mode recreates the table instead
    compare_type=True,
    render_item=_render_item,
)


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of running it (`alembic upgrade head --sql`)."""
    context.configure(
        url=_database_url(),
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        **_CONTEXT_OPTS,
    )
    with context.begin_transaction():
        context.run_migrations()


def _make_sqlite_migrations_transactional(engine: Engine) -> None:
    # pysqlite doesn't put DDL (CREATE/DROP/ALTER) in a transaction by default, so a failed
    # migration would be left half-applied. Take over transaction control so BEGIN covers
    # everything (SQLAlchemy's documented pysqlite recipe).
    @event.listens_for(engine, "connect")
    def _driver_autocommit(dbapi_connection, _):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _explicit_begin(connection):
        connection.exec_driver_sql("BEGIN")


def run_migrations_online() -> None:
    engine = create_engine(_database_url(), poolclass=pool.NullPool)
    is_sqlite = engine.dialect.name == "sqlite"
    if is_sqlite:
        _make_sqlite_migrations_transactional(engine)

    with engine.connect() as connection:
        if is_sqlite:
            # Batch mode drops and recreates tables; with FKs enforced that would cascade or
            # fail. The pragma only works outside a transaction, so send it straight to the driver.
            connection.connection.dbapi_connection.execute("PRAGMA foreign_keys=OFF")

        # Alembic assumes SQLite DDL is non-transactional; with the engine setup above it is.
        context.configure(
            connection=connection, transactional_ddl=True if is_sqlite else None, **_CONTEXT_OPTS
        )
        with context.begin_transaction():
            context.run_migrations()
            if is_sqlite:
                violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                if violations:
                    raise RuntimeError(f"Migration would leave foreign key violations: {violations}")


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
