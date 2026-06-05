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

"""add_share_server_replication

Revision ID: 2151d715b110
Revises: afc3b5e1f406
Create Date: 2026-09-02 14:19:11.575538

"""

# revision identifiers, used by Alembic.
revision = '2151d715b110'
down_revision = '004e506e922e'

from alembic import op
from oslo_log import log
import sqlalchemy as sa


LOG = log.getLogger(__name__)


share_servers_table = 'share_servers'
share_server_metadata_table = 'share_server_metadata'


def upgrade():
    try:
        op.add_column(
            share_servers_table,
            sa.Column('replica_state', sa.String(length=32), nullable=True))
    except Exception:
        LOG.error("Column 'replica_state' can not be added to the "
                  "'share_servers' table!")
        raise

    context = op.get_context()
    mysql_dl = context.bind.dialect.name == 'mysql'
    datetime_type = (sa.dialects.mysql.DATETIME(fsp=6)
                     if mysql_dl else sa.DateTime)

    try:
        op.create_table(
            share_server_metadata_table,
            sa.Column('id', sa.Integer, primary_key=True, nullable=False),
            sa.Column('share_server_id', sa.String(36),
                      sa.ForeignKey('share_servers.id'), nullable=False,
                      index=True),
            sa.Column('key', sa.String(255), nullable=False),
            sa.Column('value', sa.String(1023), nullable=False),
            sa.Column('deleted', sa.String(36), default='False'),
            sa.Column('created_at', datetime_type),
            sa.Column('updated_at', datetime_type),
            sa.Column('deleted_at', datetime_type),
            mysql_engine='InnoDB',
            mysql_charset='utf8'
        )
    except Exception:
        LOG.error("Table |%s| not created!", share_server_metadata_table)
        raise


def downgrade():
    try:
        op.drop_table(share_server_metadata_table)
    except Exception:
        LOG.error("%s table not dropped", share_server_metadata_table)
        raise

    try:
        op.drop_column(share_servers_table, 'replica_state')
    except Exception:
        LOG.error("Column 'replica_state' can not be dropped for "
                  "'share_servers' table!")
        raise
