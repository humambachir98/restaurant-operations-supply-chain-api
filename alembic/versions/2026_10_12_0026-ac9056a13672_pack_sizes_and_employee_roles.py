"""pack sizes and employee roles

- inventory_items.pack_size: units per supplier pack (existing items default to 1.0).
- purchase_order_items: `quantity` (units) is replaced by `packs` + a `pack_size` snapshot.
  Existing lines keep exactly the stock they add on receipt: whole quantities become
  N packs of 1, fractional ones (e.g. 12.5 kg) become 1 pack of 12.5.
- employees.role becomes an enum ('shift_manager', 'crew'). Existing free-text roles are
  mapped: anything containing "manager" -> shift_manager, everything else -> crew.

Revision ID: ac9056a13672
Revises: b0d822ceb00f
Create Date: 2026-10-12 00:26:13.212068

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac9056a13672'
down_revision: Union[str, Sequence[str], None] = 'b0d822ceb00f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "UPDATE employees SET role = CASE "
        "WHEN lower(role) LIKE '%manager%' THEN 'shift_manager' ELSE 'crew' END"
    )
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.alter_column('role',
               existing_type=sa.VARCHAR(length=50),
               type_=sa.Enum('shift_manager', 'crew', name='employeerole'),
               existing_nullable=False)

    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('pack_size', sa.Double(), server_default='1.0', nullable=False))

    # Add as nullable, backfill from the old unit quantity, then tighten.
    with op.batch_alter_table('purchase_order_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('packs', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('pack_size', sa.Double(), nullable=True))
    op.execute(
        "UPDATE purchase_order_items SET "
        "packs = CASE WHEN quantity = CAST(quantity AS INTEGER) THEN CAST(quantity AS INTEGER) ELSE 1 END, "
        "pack_size = CASE WHEN quantity = CAST(quantity AS INTEGER) THEN 1.0 ELSE quantity END"
    )
    with op.batch_alter_table('purchase_order_items', schema=None) as batch_op:
        batch_op.alter_column('packs', existing_type=sa.Integer(), nullable=False)
        batch_op.alter_column('pack_size', existing_type=sa.Double(), nullable=False)
        batch_op.drop_column('quantity')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('purchase_order_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('quantity', sa.DOUBLE(), nullable=True))
    op.execute("UPDATE purchase_order_items SET quantity = packs * pack_size")
    with op.batch_alter_table('purchase_order_items', schema=None) as batch_op:
        batch_op.alter_column('quantity', existing_type=sa.DOUBLE(), nullable=False)
        batch_op.drop_column('pack_size')
        batch_op.drop_column('packs')

    with op.batch_alter_table('inventory_items', schema=None) as batch_op:
        batch_op.drop_column('pack_size')

    # Role values stay valid strings ('shift_manager' / 'crew').
    with op.batch_alter_table('employees', schema=None) as batch_op:
        batch_op.alter_column('role',
               existing_type=sa.Enum('shift_manager', 'crew', name='employeerole'),
               type_=sa.VARCHAR(length=50),
               existing_nullable=False)
