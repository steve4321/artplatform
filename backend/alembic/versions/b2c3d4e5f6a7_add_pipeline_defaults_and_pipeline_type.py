"""Add pipeline_defaults table and pipeline_type to provider_settings

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-21 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create pipeline_defaults table
    op.create_table('pipeline_defaults',
        sa.Column('pipeline_type', sa.Text(), nullable=False),
        sa.Column('default_mode', sa.Text(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('pipeline_type'),
    )

    # Recreate provider_settings with pipeline_type column
    # SQLite requires table recreation for column addition + constraint change
    op.create_table('provider_settings_new',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('pipeline_type', sa.Text(), nullable=False, server_default='3d_scene'),
        sa.Column('stage', sa.Text(), nullable=False),
        sa.Column('mode', sa.Text(), nullable=False),
        sa.Column('processor_name', sa.Text(), nullable=False),
        sa.Column('cloud_provider', sa.Text(), nullable=True),
        sa.Column('api_key', sa.Text(), nullable=True),
        sa.Column('base_url', sa.Text(), nullable=True),
        sa.Column('extra_config', sa.JSON(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('pipeline_type', 'stage', name='uq_provider_settings_pipeline_type_stage'),
    )

    # Copy existing data with default pipeline_type
    op.execute("""
        INSERT INTO provider_settings_new (id, pipeline_type, stage, mode, processor_name, cloud_provider, api_key, base_url, extra_config, updated_at)
        SELECT id, '3d_scene', stage, mode, processor_name, cloud_provider, api_key, base_url, extra_config, updated_at FROM provider_settings
    """)

    # Drop old table, rename new one
    op.drop_table('provider_settings')
    op.rename_table('provider_settings_new', 'provider_settings')


def downgrade() -> None:
    # Restore old provider_settings (drop pipeline_type)
    op.create_table('provider_settings_old',
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

    op.execute("""
        INSERT INTO provider_settings_old (id, stage, mode, processor_name, cloud_provider, api_key, base_url, extra_config, updated_at)
        SELECT id, stage, mode, processor_name, cloud_provider, api_key, base_url, extra_config, updated_at FROM provider_settings
    """)

    op.drop_table('provider_settings')
    op.rename_table('provider_settings_old', 'provider_settings')

    op.drop_table('pipeline_defaults')
