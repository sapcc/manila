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

import ddt
from oslo_serialization import jsonutils

from manila.api.views import share_server_replicas
from manila.common import constants
from manila import test
from manila.tests.api import fakes


LINKS = [
    {'rel': 'self',
     'href': 'http://localhost/share/v2/share-server-replicas/replica-id'},
    {'rel': 'bookmark',
     'href': 'http://localhost/share/share-server-replicas/replica-id'},
]


@ddt.ddt
class ViewBuilderTestCase(test.TestCase):

    def setUp(self):
        super(ViewBuilderTestCase, self).setUp()
        self.builder = share_server_replicas.ReplicaViewBuilder()
        self.req = fakes.HTTPRequest.blank(
            '/share-server-replicas', version='2.100',
            base_url='http://localhost/share/v2')

    def _replica(self, **overrides):
        return dict({
            'id': 'replica-id',
            'source_share_server_id': 'source-server-id',
            'host': 'host@backend#pool',
            'status': constants.STATUS_INACTIVE,
            'replica_state': constants.REPLICA_STATE_IN_SYNC,
            'availability_zone': 'az1',
            'share_network_id': 'share-net-id',
            'share_network_name': 'share-net-name',
            'created_at': '2026-01-01T00:00:00.000000',
            'updated_at': '2026-01-01T01:00:00.000000',
            'metadata': {'foo': 'bar'},
        }, **overrides)

    def test_collection_properties(self):
        self.assertEqual(
            'share_server_replicas', self.builder._collection_name)
        self.assertEqual(
            'share-server-replicas', self.builder._collection_route_name)

    def test_summary(self):
        """The summary carries the fields a listing needs, and no more."""
        result = self.builder.summary(self.req, self._replica())

        self.assertEqual(
            {'share_server_replica': {
                'id': 'replica-id',
                'source_share_server_id': 'source-server-id',
                'host': 'host@backend#pool',
                'status': constants.STATUS_INACTIVE,
                'replica_state': constants.REPLICA_STATE_IN_SYNC,
                'availability_zone': 'az1',
                'links': LINKS,
            }},
            result)

    def test_detail_adds_to_the_summary(self):
        result = self.builder.detail(
            self.req, self._replica())['share_server_replica']

        self.assertEqual('2026-01-01T00:00:00.000000', result['created_at'])
        self.assertEqual('2026-01-01T01:00:00.000000', result['updated_at'])
        self.assertEqual('share-net-id', result['share_network_id'])
        self.assertEqual('share-net-name', result['share_network_name'])
        self.assertEqual({'foo': 'bar'}, result['metadata'])

    @ddt.data('summary', 'detail')
    def test_links(self, method_name):
        """The bookmark link is the self link with the API version removed."""
        result = getattr(self.builder, method_name)(self.req, self._replica())

        self.assertEqual(LINKS, result['share_server_replica']['links'])

    @ddt.data(constants.STATUS_ACTIVE, constants.STATUS_INACTIVE,
              constants.STATUS_CREATING, constants.STATUS_DELETING,
              constants.STATUS_ERROR)
    def test_status_is_reported_untranslated(self, status):
        """Replicas report the share server status as the database holds it."""
        result = self.builder.summary(self.req, self._replica(status=status))

        self.assertEqual(status, result['share_server_replica']['status'])

    @ddt.data(
        ({'foo': 'bar'}, {'foo': 'bar'}),
        # Anything that is not a mapping cannot be metadata.
        ('invalid-metadata', {}),
        (None, {}),
    )
    @ddt.unpack
    def test_detail_metadata(self, metadata, expected):
        result = self.builder.detail(
            self.req, self._replica(metadata=metadata))

        self.assertEqual(
            expected, result['share_server_replica']['metadata'])

    @ddt.data(
        # Drivers store backend_details as JSON, nested arbitrarily deep.
        (jsonutils.dumps({'ports': jsonutils.dumps({'id': '10.196.38.199'})}),
         {'ports': {'id': '10.196.38.199'}}),
        # A JSON list is decoded element by element.
        (jsonutils.dumps(['plain', jsonutils.dumps({'a': 'b'})]),
         ['plain', {'a': 'b'}]),
        # A decoded value that is not a string needs no decoding of its own.
        (jsonutils.dumps({'count': 5, 'enabled': True}),
         {'count': 5, 'enabled': True}),
        # A string that is not JSON is handed back untouched.
        ('vs_d_111f31c1-b468-4ae9-88f4-a26a41b7f0d9',
         'vs_d_111f31c1-b468-4ae9-88f4-a26a41b7f0d9'),
        # So is one that parses to a scalar rather than a container.
        ('123', '123'),
    )
    @ddt.unpack
    def test_detail_decodes_backend_details(self, stored, expected):
        replica = self._replica(metadata={'policy': 'AutomatedFailOver',
                                          'backend_details': stored})

        result = self.builder.detail(self.req, replica)

        self.assertEqual(
            {'policy': 'AutomatedFailOver', 'backend_details': expected},
            result['share_server_replica']['metadata'])

    @ddt.data('summary_list', 'detail_list')
    def test_list_views(self, method_name):
        replicas = [self._replica(id='rep-1'),
                    self._replica(id='rep-2', metadata='bad-metadata')]

        result = getattr(self.builder, method_name)(
            self.req, replicas)['share_server_replicas']

        self.assertEqual(['rep-1', 'rep-2'], [r['id'] for r in result])
        if method_name == 'summary_list':
            self.assertNotIn('metadata', result[0])
        else:
            self.assertEqual([{'foo': 'bar'}, {}],
                             [r['metadata'] for r in result])
