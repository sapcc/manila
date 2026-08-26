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

"""add_replica_state_to_share_server

Revision ID: 2e78ba7e5234
Revises: 004e506e922e
Create Date: 2026-08-23 11:49:23.846639

"""

# revision identifiers, used by Alembic.
revision = '2e78ba7e5234'
down_revision = '004e506e922e'

from alembic import op
from oslo_log import log
import sqlalchemy as sa


LOG = log.getLogger(__name__)


def upgrade():
    try:
        op.add_column(
            'share_servers',
            sa.Column('replica_state', sa.String(length=32), nullable=True)
        )
    except Exception:
        LOG.error("Column |%s| not created!", 'share_servers.replica_state')
        raise


def downgrade():
    try:
        op.drop_column('share_servers', 'replica_state')
    except Exception:
        LOG.error("share_servers.replica_state column not dropped")
        raise
