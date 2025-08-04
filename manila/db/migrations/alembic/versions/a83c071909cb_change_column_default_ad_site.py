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

"""add default_ad_site to security service

Revision ID: a83c071909cb
Revises: 0d8c8f6d54a4
Create Date: 2022-11-30 10:59:34.866946

"""

# revision identifiers, used by Alembic.
revision = 'a83c071909cb'
down_revision = '0d8c8f6d54a4'

from alembic import op
from oslo_log import log
import sqlalchemy as sa

from manila.db.migrations import utils

LOG = log.getLogger(__name__)
ss_table_name = 'security_services'


def upgrade():
    try:
        connection = op.get_bind()

        ss_table = utils.load_table(ss_table_name, connection)
        for record in connection.execute(ss_table.select()):
            op.execute(
                ss_table.update().where(
                    sa.and_(
                        ss_table.c.id == record.id,
                        ss_table.c.defaultadsite is not None
                    )
                ).values({
                    'default_ad_site': str(ss_table.c.defaultadsite)
                })
            )

        op.drop_column(ss_table_name, 'defaultadsite')
    except Exception:
        LOG.error("%s table column default_ad_site not updated", ss_table_name)
        raise


def downgrade():
    pass

    '''
    try:
        connection = op.get_bind()

        op.add_column(
            ss_table_name,
            sa.Column('defaultadsite', sa.String(255), nullable=True))

        ss_table = utils.load_table(ss_table_name, connection)
        for record in connection.execute(ss_table.select()):
            op.execute(
                ss_table.update().where(
                    sa.and_(
                        ss_table.c.id == record.id,
                        ss_table.c.default_ad_site is not None
                    )
                ).values({
                    'defaultadsite': str(ss_table.c.default_ad_site)
                })
            )
    except Exception:
        LOG.error("%s table column defaultadsite not updated", ss_table_name)
        raise
    '''
