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

from oslo_log import versionutils
from oslo_policy import policy

from manila.policies import base


BASE_POLICY_NAME = 'share_export_location:%s'

DEPRECATED_REASON = """
The share export location API now support system scope and default roles.
"""

deprecated_export_location_index = policy.DeprecatedRule(
    name=BASE_POLICY_NAME % 'index',
    check_str=base.RULE_DEFAULT,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)
deprecated_export_location_show = policy.DeprecatedRule(
    name=BASE_POLICY_NAME % 'show',
    check_str=base.RULE_DEFAULT,
    deprecated_reason=DEPRECATED_REASON,
    deprecated_since=versionutils.deprecated.WALLABY
)


share_export_location_policies = [
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'index',
        check_str=base.SYSTEM_OR_PROJECT_READER,
        scope_types=['system', 'project'],
        description="Get all export locations of a given share.",
        operations=[
            {
                'method': 'GET',
                'path': '/shares/{share_id}/export_locations',
            }
        ],
        deprecated_rule=deprecated_export_location_index
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'show',
        check_str=base.SYSTEM_OR_PROJECT_READER,
        scope_types=['system', 'project'],
        description="Get details about the requested export location.",
        operations=[
            {
                'method': 'GET',
                'path': ('/shares/{share_id}/export_locations/'
                         '{export_location_id}'),
            }
        ],
        deprecated_rule=deprecated_export_location_show
    ),
]


def list_rules():
    return share_export_location_policies
