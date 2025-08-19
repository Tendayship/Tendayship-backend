"""add cancel_reason to subscriptions

Revision ID: d4f394bd27db
Revises: ab17e43a40e0
Create Date: 2025-08-19 17:40:34.953239+09:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f394bd27db'
down_revision: Union[str, None] = 'ab17e43a40e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('subscriptions', 
                  sa.Column('cancel_reason', sa.Text(), nullable=True))

def downgrade() -> None:
    op.drop_column('subscriptions', 'cancel_reason')
