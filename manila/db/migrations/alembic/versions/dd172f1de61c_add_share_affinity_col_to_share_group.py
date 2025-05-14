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

"""add_share_affinity_col_to_share_group

Revision ID: dd172f1de61c
Revises: 636ecb8f3939
Create Date: 2024-11-07 15:56:42.899348

"""

# revision identifiers, used by Alembic.
revision = 'dd172f1de61c'
down_revision = '636ecb8f3939'

from alembic import op
import sqlalchemy as sa

TABLE_NAME = 'share_groups'
ATTR_NAME = 'share_affinity'

def upgrade():
    op.add_column(
        TABLE_NAME,
        sa.Column(
            ATTR_NAME,
            sa.Enum('affinity', 'anti-affinity', name=ATTR_NAME),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column(TABLE_NAME, ATTR_NAME)
