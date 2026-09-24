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

# New share_servers.status ENUM values introduced alongside share server
# replication. On MySQL the status column is an ENUM, so the physical column
# definition must be altered to accept these values; without this an upgraded
# deployment raises LookupError when a row with one of these values is read.
share_server_status_enum_new = (
    'inactive', 'active', 'error', 'error_deleting', 'deleting',
    'creating', 'deleted', 'manage_starting', 'unmanage_starting',
    'unmanage_error', 'manage_error', 'server_migrating',
    'server_migrating_to', 'network_change', 'replication_change',
)
share_server_status_enum_old = (
    'inactive', 'active', 'error', 'deleting',
    'creating', 'deleted', 'manage_starting', 'unmanage_starting',
    'unmanage_error', 'manage_error', 'server_migrating',
    'server_migrating_to', 'network_change',
)


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

    # Teach the DB about the new status values ('error_deleting',
    # 'replication_change'). Only MySQL enforces the ENUM at the column level;
    # other backends store status as a plain string and need no change.
    if mysql_dl:
        try:
            op.alter_column(
                share_servers_table, 'status',
                existing_type=sa.Enum(*share_server_status_enum_old),
                type_=sa.Enum(*share_server_status_enum_new),
                existing_nullable=True)
        except Exception:
            LOG.error("Column 'status' ENUM can not be altered for the "
                      "'share_servers' table!")
            raise

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

    context = op.get_context()
    mysql_dl = context.bind.dialect.name == 'mysql'

    if mysql_dl:
        # Rows carrying a status value that the reverted ENUM does not accept
        # would break the ALTER; map them to 'error' first.
        try:
            share_servers = sa.Table(
                share_servers_table, sa.MetaData(),
                autoload_with=op.get_bind())
            op.execute(
                share_servers.update().where(
                    share_servers.c.status.in_(
                        ('error_deleting', 'replication_change'))
                ).values(status='error'))
            op.alter_column(
                share_servers_table, 'status',
                existing_type=sa.Enum(*share_server_status_enum_new),
                type_=sa.Enum(*share_server_status_enum_old),
                existing_nullable=True)
        except Exception:
            LOG.error("Column 'status' ENUM can not be reverted for the "
                      "'share_servers' table!")
            raise

    try:
        op.drop_column(share_servers_table, 'replica_state')
    except Exception:
        LOG.error("Column 'replica_state' can not be dropped for "
                  "'share_servers' table!")
        raise
