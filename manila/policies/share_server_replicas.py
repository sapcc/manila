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

from oslo_policy import policy

from manila.policies import base


BASE_POLICY_NAME = 'share_server_replica:%s'


share_server_replica_policies = [
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'create',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Create share server replica.',
        operations=[
            {
                'method': 'POST',
                'path': '/share-server-replicas',
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'delete',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Delete share server replica.',
        operations=[
            {
                'method': 'DELETE',
                'path': '/share-server-replicas/{share_server_replica_id}',
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'force_delete',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Force delete share server replica.',
        operations=[
            {
                'method': 'POST',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/action'),
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'show',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Show share server replica details.',
        operations=[
            {
                'method': 'GET',
                'path': '/share-server-replicas/{share_server_replica_id}',
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'index',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='List share server replicas.',
        operations=[
            {
                'method': 'GET',
                'path': '/share-server-replicas',
            },
            {
                'method': 'GET',
                'path': '/share-server-replicas?{query}',
            },
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'promote',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Promote share server replica.',
        operations=[
            {
                'method': 'POST',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/action'),
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'resync',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Resync share server replica.',
        operations=[
            {
                'method': 'POST',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/action'),
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'reset_replica_state',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Reset the replica_state of a share server replica.',
        operations=[
            {
                'method': 'POST',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/action'),
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'reset_status',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Reset the status of a share server replica.',
        operations=[
            {
                'method': 'POST',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/action'),
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'update_metadata',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Update share server replica metadata.',
        operations=[
            {
                'method': 'PUT',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/metadata'
                ),
            },
            {
                'method': 'POST',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/metadata/{key}'
                ),
            },
            {
                'method': 'POST',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/metadata'
                ),
            },
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'delete_metadata',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Delete share server replica metadata item.',
        operations=[
            {
                'method': 'DELETE',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/metadata/{key}'
                ),
            }
        ]
    ),
    policy.DocumentedRuleDefault(
        name=BASE_POLICY_NAME % 'get_metadata',
        check_str=base.ADMIN,
        scope_types=['project'],
        description='Get share server replica metadata.',
        operations=[
            {
                'method': 'GET',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/metadata'
                ),
            },
            {
                'method': 'GET',
                'path': (
                    '/share-server-replicas/'
                    '{share_server_replica_id}/metadata/{key}'
                ),
            }
        ]
    ),
]


def list_rules():
    return share_server_replica_policies
