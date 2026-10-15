# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

"""add_share_replicas_migration_support

Revision ID: 3d76bb97e252
Revises: 004e506e922e
Create Date: 2026-09-29 00:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = '3d76bb97e252'
down_revision = '004e506e922e'

from alembic import op
from oslo_log import log
import sqlalchemy as sa


LOG = log.getLogger(__name__)

shares_table = 'shares'


def upgrade():
    try:
        op.add_column(
            shares_table,
            sa.Column('share_replicas_migration_support',
                      sa.Boolean, nullable=True, default=False))
    except Exception:
        LOG.error("Column 'share_replicas_migration_support' could not be "
                  "added to the '%s' table.", shares_table)
        raise


def downgrade():
    try:
        op.drop_column(shares_table, 'share_replicas_migration_support')
    except Exception:
        LOG.error("Column 'share_replicas_migration_support' could not be "
                  "dropped from the '%s' table.", shares_table)
        raise
