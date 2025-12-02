"""add quality_level to mixes

Revision ID: 2025120101_add_quality_level_to_mixes
Revises: d28d82c7a598
Create Date: 2025-12-01 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2025120101_add_quality_level_to_mixes'
down_revision = 'd28d82c7a598'
branch_labels = None
depends_on = None


def upgrade():
    # Add quality_level column to mixes table
    op.add_column('mixes', sa.Column('quality_level', sa.String(), nullable=False, server_default='2'))


def downgrade():
    # Remove quality_level column from mixes table
    op.drop_column('mixes', 'quality_level')
