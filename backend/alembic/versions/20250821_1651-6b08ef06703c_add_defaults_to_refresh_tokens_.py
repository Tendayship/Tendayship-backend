"""add defaults to refresh_tokens timestamps

Revision ID: 6b08ef06703c
Revises: 0c46e139b523
Create Date: 2025-08-21 16:51:50.278682+09:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b08ef06703c'
down_revision: Union[str, None] = '0c46e139b523'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) 기존 NULL 데이터 보정
    op.execute("UPDATE refresh_tokens SET created_at = NOW() WHERE created_at IS NULL")
    op.execute("UPDATE refresh_tokens SET updated_at = NOW() WHERE updated_at IS NULL")

    # 2) 기본값 추가
    op.alter_column(
        'refresh_tokens',
        'created_at',
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text('NOW()'),
        existing_nullable=False
    )
    op.alter_column(
        'refresh_tokens',
        'updated_at',
        existing_type=sa.DateTime(timezone=True),
        server_default=sa.text('NOW()'),
        existing_nullable=False
    )

def downgrade() -> None:
    op.alter_column(
        'refresh_tokens',
        'updated_at',
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False
    )
    op.alter_column(
        'refresh_tokens',
        'created_at',
        server_default=None,
        existing_type=sa.DateTime(timezone=True),
        existing_nullable=False
    )