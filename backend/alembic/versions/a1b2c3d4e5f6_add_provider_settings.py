"""add provider_settings table

Revision ID: a1b2c3d4e5f6
Revises: 3ac248e42e48
Create Date: 2026-05-21 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '3ac248e42e48'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('provider_settings',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('stage', sa.Text(), nullable=False),
        sa.Column('mode', sa.Text(), nullable=False),
        sa.Column('processor_name', sa.Text(), nullable=False),
        sa.Column('cloud_provider', sa.Text(), nullable=True),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('base_url', sa.Text(), nullable=True),
        sa.Column('extra_config', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('stage', name='uq_provider_settings_stage'),
    )


def downgrade() -> None:
    op.drop_table('provider_settings')
