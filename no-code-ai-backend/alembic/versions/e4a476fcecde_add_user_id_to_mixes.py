"""add_user_id_to_mixes

Revision ID: e4a476fcecde
Revises: 2025120101_add_quality_level_to_mixes
Create Date: 2025-12-03 11:12:26.505213

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e4a476fcecde'
down_revision: Union[str, Sequence[str], None] = '2025120101_add_quality_level_to_mixes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('mixes', sa.Column('user_id', sa.String(), nullable=True))
    op.create_index('ix_mixes_user_id', 'mixes', ['user_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_mixes_user_id', 'mixes')
    op.drop_column('mixes', 'user_id')
