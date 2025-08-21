"""fix refresh_tokens timestamps

Revision ID: fc4c19cda1b7
Revises: cda400c39ebb
Create Date: 2025-08-21 16:20:43.928531+09:00
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'fc4c19cda1b7'  # ← '[새로운 ID]'에서 수정
down_revision: Union[str, None] = 'cda400c39ebb'  # ← 'fc4c19cda1b7'에서 수정
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