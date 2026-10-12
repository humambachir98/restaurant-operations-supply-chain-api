from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text

from app.database import Base
from app.database.migrations import alembic_config


def test_migrations_match_models_and_downgrade_cleanly(tmp_path):
    url = f"sqlite:///{(tmp_path / 'migrations.db').as_posix()}"
    config = alembic_config(url)

    command.upgrade(config, "head")
    engine = create_engine(url)
    with engine.connect() as connection:
        context = MigrationContext.configure(connection, opts={"compare_type": True})
        head = ScriptDirectory.from_config(config).get_current_head()
        assert context.get_current_revision() == head
        # If this fails, a model changed without a migration: run
        #   alembic revision --autogenerate -m "<what changed>"
        assert compare_metadata(context, Base.metadata) == []

    command.downgrade(config, "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()


def test_pack_size_and_role_migration_keeps_existing_data(tmp_path):
    url = f"sqlite:///{(tmp_path / 'legacy.db').as_posix()}"
    config = alembic_config(url)
    command.upgrade(config, "b0d822ceb00f")  # initial schema: free-text roles, unit quantities

    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO employees (id, name, role, is_active) VALUES "
            "(1, 'A', 'Manager', 1), (2, 'B', 'shift_manager', 1), (3, 'C', 'cook', 1)"
        ))
        conn.execute(text(
            "INSERT INTO inventory_items (id, name, unit, quantity, reorder_level, is_daily_tracked) "
            "VALUES (1, 'Fries', 'kg', 0, 0, 1)"
        ))
        conn.execute(text(
            "INSERT INTO purchase_orders (id, status, created_at, expected_delivery_date) "
            "VALUES (1, 'pending', '2026-10-06 10:00:00', '2026-10-08')"
        ))
        conn.execute(text(
            "INSERT INTO purchase_order_items (id, order_id, item_id, quantity) VALUES (1, 1, 1, 40), (2, 1, 1, 12.5)"
        ))

    command.upgrade(config, "head")
    with engine.connect() as conn:
        roles = conn.execute(text("SELECT role FROM employees ORDER BY id")).scalars().all()
        assert roles == ["shift_manager", "shift_manager", "crew"]
        assert conn.execute(text("SELECT pack_size FROM inventory_items")).scalar() == 1.0
        lines = conn.execute(text("SELECT packs, pack_size FROM purchase_order_items ORDER BY id")).all()
        assert [tuple(line) for line in lines] == [(40, 1.0), (1, 12.5)]  # same stock on receipt

    command.downgrade(config, "b0d822ceb00f")
    with engine.connect() as conn:
        quantities = conn.execute(text("SELECT quantity FROM purchase_order_items ORDER BY id")).scalars().all()
        assert quantities == [40, 12.5]
    engine.dispose()


def test_monthly_audits_survive_downgrade_as_weekly(tmp_path):
    url = f"sqlite:///{(tmp_path / 'monthly.db').as_posix()}"
    config = alembic_config(url)
    command.upgrade(config, "head")

    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO inventory_audits (id, audit_type, created_at) VALUES "
            "(1, 'monthly', '2026-10-31 20:00:00'), (2, 'daily', '2026-10-31 08:00:00')"
        ))

    command.downgrade(config, "b21e66ccd8c4")  # before monthly audits existed
    with engine.connect() as conn:
        types = conn.execute(text("SELECT audit_type FROM inventory_audits ORDER BY id")).scalars().all()
        assert types == ["weekly", "daily"]
        assert "waste_logs" not in inspect(engine).get_table_names()
    engine.dispose()


def test_waste_without_reason_survives_downgrade(tmp_path):
    url = f"sqlite:///{(tmp_path / 'waste.db').as_posix()}"
    config = alembic_config(url)
    command.upgrade(config, "head")

    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO inventory_items (id, name, unit, quantity, reorder_level, is_daily_tracked, pack_size) "
            "VALUES (1, 'Fries', 'kg', 0, 0, 1, 15)"
        ))
        conn.execute(text(
            "INSERT INTO waste_logs (item_id, quantity, reason, created_at) VALUES "
            "(1, 2.5, NULL, '2026-10-12 20:00:00'), (1, 1, 'Dropped', '2026-10-12 21:00:00')"
        ))

    command.downgrade(config, "1df1f3dbdfe5")  # waste still had audit_type and a required reason
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT audit_type, reason FROM waste_logs ORDER BY id")).all()
        assert [tuple(r) for r in rows] == [("daily", "Not specified"), ("daily", "Dropped")]

    command.upgrade(config, "head")  # and back up again
    with engine.connect() as conn:
        assert "audit_type" not in {c["name"] for c in inspect(conn).get_columns("waste_logs")}
    engine.dispose()
