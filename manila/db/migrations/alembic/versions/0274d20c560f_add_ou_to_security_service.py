# Copyright 2018 SAP SE
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Add ou to security service

Revision ID: 0274d20c560f
Revises: 829a09b0ddd4
Create Date: 2017-05-19 17:27:30.274440

"""

# revision identifiers, used by Alembic.
revision = '0274d20c560f'
down_revision = '829a09b0ddd4'

from alembic import op
from oslo_log import log
import sqlalchemy as sa

LOG = log.getLogger(__name__)


def upgrade():
    try:
        op.add_column(
            'security_services',
            sa.Column('ou', sa.String(255), nullable=True))
    except Exception:
        LOG.error('Column ou could not be added')


def downgrade():
    try:
        op.drop_column('security_services', 'ou')
    except Exception:
        LOG.error('Column ou could not be dropped')
