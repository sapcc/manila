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

from unittest import mock

import ddt
from webob import exc

from manila.api.v2 import share_server_replicas
from manila.common import constants
from manila import context
from manila import exception
from manila import policy
from manila import test
from manila.tests.api import fakes


MIN_VERSION = share_server_replicas.MIN_SUPPORTED_API_VERSION
RESERVED = share_server_replicas.RESERVED_METADATA_KEY
REPLICA_ID = 'fake-replica-id'
SOURCE_ID = 'source-server-id'
NOT_FOUND = exception.ShareServerReplicaNotFound(replica_id=REPLICA_ID)
CREATE_BODY = {'share_server_replica': {'share_server_id': SOURCE_ID}}
NOT_FOUND_MSG = 'No share server replica exists with ID %s.' % REPLICA_ID


@ddt.ddt
class ShareServerReplicasApiTest(test.TestCase):
    """Share Server Replicas API Test Cases."""

    def setUp(self):
        super(ShareServerReplicasApiTest, self).setUp()
        self.controller = share_server_replicas.ShareServerReplicaController()
        self.ctxt = context.get_admin_context()
        self.req = self._request()
        self.mock_object(policy, 'check_policy', mock.Mock(return_value=True))

    def _request(self, microversion=MIN_VERSION, is_admin=True):
        req = fakes.HTTPRequest.blank(
            '/share-server-replicas', version=microversion,
            use_admin_context=is_admin, experimental=True,
            base_url='http://localhost/share/v2')
        req.environ['manila.context'] = (
            self.ctxt if is_admin else context.RequestContext('fake', 'fake'))
        return req

    def _replica(self, **values):
        """A secondary replica row, shaped the way the database hands it back.

        The availability zone is set, standing in for a replica whose subnet
        names a zone; tests covering the fallback drop it.
        """
        return dict({
            'id': REPLICA_ID,
            'share_server_id': REPLICA_ID,
            'source_share_server_id': SOURCE_ID,
            'share_network_id': 'share-network-id',
            'share_network_name': 'share-network-name',
            'host': 'host@backend#pool',
            'availability_zone': 'az1',
            'status': constants.STATUS_INACTIVE,
            'replica_state': constants.REPLICA_STATE_IN_SYNC,
            'created_at': None,
            'updated_at': None,
        }, **values)

    def _mock_db(self, attr, **kwargs):
        return self.mock_object(
            share_server_replicas.db, attr, mock.Mock(**kwargs))

    def _mock_api(self, attr, **kwargs):
        return self.mock_object(
            self.controller.share_api, attr, mock.Mock(**kwargs))

    def _mock_controller(self, attr, **kwargs):
        return self.mock_object(self.controller, attr, mock.Mock(**kwargs))

    def _mock_lookups(self, **values):
        """Make every replica lookup succeed.

        Tests then break the single step they are about to exercise, instead
        of each spelling out the preconditions that get it that far.
        """
        replica = self._replica(**values)
        self._mock_db('share_server_replica_get', return_value=replica)
        self._mock_db('share_server_get', return_value=replica)
        self._mock_db('share_server_replica_metadata_get', return_value={})
        return replica

    @ddt.data(('index', False), ('detail', True))
    @ddt.unpack
    def test_list_replicas(self, method_name, is_detail):
        source = self._replica(
            id=SOURCE_ID, source_share_server_id=None,
            status=constants.STATUS_ACTIVE,
            replica_state=constants.REPLICA_STATE_ACTIVE)
        self._mock_db('share_server_replicas_get_all',
                      return_value=[source, self._replica()])
        metadata_get = self._mock_db(
            'share_server_replica_metadata_get', return_value={'k': 'v'})

        replicas = getattr(self.controller, method_name)(
            self.req)['share_server_replicas']

        self.assertEqual([SOURCE_ID, REPLICA_ID], [r['id'] for r in replicas])
        if not is_detail:
            self.assertNotIn('metadata', replicas[0])
            self.assertFalse(metadata_get.called)
            return
        # Only secondaries carry metadata, so the active source is skipped.
        metadata_get.assert_called_once_with(self.ctxt, REPLICA_ID)
        self.assertEqual([{}, {'k': 'v'}], [r['metadata'] for r in replicas])

    @ddt.data(
        ({}, dict(source_share_server_id=None, sort_key='created_at',
                  sort_dir='desc', limit=None, offset=None)),
        ({'share_server_id': SOURCE_ID, 'sort_key': 'updated_at',
          'sort_dir': 'asc', 'limit': '10', 'offset': '2'},
         dict(source_share_server_id=SOURCE_ID, sort_key='updated_at',
              sort_dir='asc', limit=10, offset=2)),
    )
    @ddt.unpack
    def test_detail_passes_filter_and_sort_params(self, query, expected):
        req = self._request()
        req.GET.update(query)
        server_get = self._mock_db('share_server_get')
        replicas_get_all = self._mock_db(
            'share_server_replicas_get_all', return_value=[])

        self.controller.detail(req)

        replicas_get_all.assert_called_once_with(self.ctxt, **expected)
        # Filtering by source is enough; the source is never fetched to
        # decide whether it is a replica at all.
        self.assertFalse(server_get.called)

    def test_index_propagates_invalid_input_as_400(self):
        self._mock_db('share_server_replicas_get_all',
                      side_effect=exception.InvalidInput(reason='bad input'))

        ex = self.assertRaises(
            exception.InvalidInput, self.controller.index, self.req)

        self.assertEqual(400, ex.code)

    def test_show(self):
        replica = self._mock_lookups()
        self._mock_db('share_server_replica_metadata_get',
                      return_value={'k': 'v'})

        result = self.controller.show(
            self.req, REPLICA_ID)['share_server_replica']

        self.assertEqual(replica['id'], result['id'])
        self.assertEqual({'k': 'v'}, result['metadata'])
        self.assertEqual('az1', result['availability_zone'])
        self.assertEqual('share-network-id', result['share_network_id'])
        self.assertEqual('share-network-name', result['share_network_name'])

    @ddt.data(
        # A plain share server, in no replication relationship at all.
        {'source_share_server_id': None, 'replica_state': None},
        # A migration destination: it has a source but no replica state.
        {'replica_state': None},
    )
    def test_show_share_server_that_is_not_a_replica(self, values):
        self._mock_lookups(**values)

        ex = self.assertRaises(
            exc.HTTPNotFound, self.controller.show, self.req, REPLICA_ID)

        self.assertIn(NOT_FOUND_MSG, ex.explanation)

    def test_availability_zone_falls_back_to_the_hosting_service(self):
        """A replica on a default subnet names no zone, so its host does."""
        self._mock_lookups(availability_zone=None)
        service = mock.Mock()
        service.availability_zone.name = 'az-from-service'
        service_get = self._mock_db('service_get_by_args',
                                    return_value=service)

        result = self.controller.show(self.req, REPLICA_ID)

        self.assertEqual(
            'az-from-service',
            result['share_server_replica']['availability_zone'])
        service_get.assert_called_once_with(
            self.ctxt, 'host@backend', 'manila-share')

    def test_create(self):
        replica = self._replica()
        create = self._mock_api('create_share_server_replica',
                                return_value=replica)
        metadata = {'policy': 'AutomatedFailOver'}
        body = {'share_server_replica': {
            'share_server_id': SOURCE_ID,
            'availability_zone': 'az1',
            'share_network_id': 'share-network-id',
            'metadata': metadata,
        }}

        result = self.controller.create(
            self.req, body)['share_server_replica']

        create.assert_called_once_with(
            self.ctxt, share_server_id=SOURCE_ID, availability_zone='az1',
            share_network_id='share-network-id', metadata=metadata)
        self.assertEqual(replica['id'], result['id'])
        self.assertEqual(metadata, result['metadata'])

    def test_create_defaults_the_optional_fields(self):
        create = self._mock_api('create_share_server_replica',
                                return_value=self._replica())

        self.controller.create(self.req, CREATE_BODY)

        create.assert_called_once_with(
            self.ctxt, share_server_id=SOURCE_ID, availability_zone=None,
            share_network_id=None, metadata={})

    @ddt.data(
        ({}, exc.HTTPUnprocessableEntity),
        ({'not_a_share_server_replica': {}}, exc.HTTPUnprocessableEntity),
        # The source share server is the one field callers must supply.
        ({'share_server_replica': {}}, exc.HTTPBadRequest),
    )
    @ddt.unpack
    def test_create_body_validation(self, body, expected_exception):
        self.assertRaises(expected_exception, self.controller.create,
                          self.req, body)

    def test_create_rejects_reserved_metadata_key(self):
        create = self._mock_api('create_share_server_replica')
        body = {'share_server_replica': {
            'share_server_id': SOURCE_ID,
            'metadata': {RESERVED: {'managed_by': 'driver'}},
        }}

        self.assertRaises(exc.HTTPBadRequest, self.controller.create,
                          self.req, body)
        self.assertFalse(create.called)

    @ddt.data(('delete', (), False),
              ('force_delete', ({'force_delete': None},), True))
    @ddt.unpack
    def test_delete_variants(self, method_name, extra_args, force):
        self._mock_lookups()
        delete = self._mock_api('delete_share_server_replica')

        response = getattr(self.controller, method_name)(
            self.req, REPLICA_ID, *extra_args)

        delete.assert_called_once_with(self.ctxt, REPLICA_ID, force=force)
        self.assertEqual(202, response.status_int)

    def test_promote(self):
        replica = self._mock_lookups()
        promote = self._mock_api('promote_share_server_replica')

        result = self.controller.promote(
            self.req, REPLICA_ID, {'promote': {}})

        promote.assert_called_once_with(self.ctxt, REPLICA_ID)
        self.assertEqual(replica['id'], result['share_server_replica']['id'])

    def test_resync(self):
        self._mock_lookups()
        resync = self._mock_api('update_share_server_replica_state')

        self.assertIsNone(self.controller.resync(
            self.req, REPLICA_ID, {'resync': {}}))

        resync.assert_called_once_with(self.ctxt, REPLICA_ID)

    @ddt.data(('promote', 'promote_share_server_replica'),
              ('resync', 'update_share_server_replica_state'))
    @ddt.unpack
    def test_active_replica_needs_no_work(self, method_name, api_attr):
        """The active replica is already where these actions would take it."""
        self._mock_lookups(replica_state=constants.REPLICA_STATE_ACTIVE)
        api_call = self._mock_api(api_attr)

        response = getattr(self.controller, method_name)(
            self.req, REPLICA_ID, {method_name: {}})

        self.assertEqual(200, response.status_int)
        self.assertFalse(api_call.called)

    @ddt.data(*(
        [('reset_status', 'status', status)
         for status in constants.SHARE_SERVER_STATUSES] +
        [('reset_replica_state', 'replica_state', state)
         for state in (constants.REPLICA_STATE_ACTIVE,
                       constants.REPLICA_STATE_IN_SYNC,
                       constants.REPLICA_STATE_OUT_OF_SYNC,
                       constants.STATUS_ERROR)]
    ))
    @ddt.unpack
    def test_reset(self, method_name, attr, value):
        self._mock_lookups()
        update = self._mock_db('share_server_update')

        response = getattr(self.controller, method_name)(
            self.req, REPLICA_ID, {method_name: {attr: value}})

        self.assertEqual(202, response.status_int)
        update.assert_called_once_with(self.ctxt, REPLICA_ID, {attr: value})

    @ddt.data(
        # "available" belongs to shares; a replica reports the status of the
        # share server underneath it.
        ('reset_status', {'status': constants.STATUS_AVAILABLE}),
        ('reset_status', {'status': 'not-a-status'}),
        ('reset_status', {}),
        ('reset_replica_state', {'replica_state': 'not-a-state'}),
        ('reset_replica_state', {}),
    )
    @ddt.unpack
    def test_reset_rejects_invalid_value(self, method_name, update):
        self._mock_lookups()
        db_update = self._mock_db('share_server_update')

        self.assertRaises(
            exc.HTTPBadRequest, getattr(self.controller, method_name),
            self.req, REPLICA_ID, {method_name: update})
        self.assertFalse(db_update.called)

    def test_reset_replica_state_rejects_the_active_replica(self):
        """Only a secondary's replica state is an administrator's to reset."""
        self._mock_lookups(replica_state=constants.REPLICA_STATE_ACTIVE)
        db_update = self._mock_db('share_server_update')

        self.assertRaises(
            exc.HTTPBadRequest, self.controller.reset_replica_state,
            self.req, REPLICA_ID,
            {'reset_replica_state': {
                'replica_state': constants.REPLICA_STATE_IN_SYNC}})
        self.assertFalse(db_update.called)

    @ddt.data(
        ('create', (CREATE_BODY,), 'create_share_server_replica',
         exception.InvalidInput(reason='bad'), exc.HTTPBadRequest),
        ('create', (CREATE_BODY,), 'create_share_server_replica',
         exception.ReplicationException(reason='bad'), exc.HTTPBadRequest),
        ('create', (CREATE_BODY,), 'create_share_server_replica',
         exception.ShareServerReplicaExists(
             share_server_id=SOURCE_ID, host='h@b#p'), exc.HTTPConflict),
        ('create', (CREATE_BODY,), 'create_share_server_replica',
         exception.NotFound(), exc.HTTPNotFound),
        ('delete', (REPLICA_ID,), 'delete_share_server_replica',
         exception.InvalidInput(reason='bad'), exc.HTTPBadRequest),
        ('delete', (REPLICA_ID,), 'delete_share_server_replica',
         exception.ReplicationException(reason='bad'), exc.HTTPBadRequest),
        ('force_delete', (REPLICA_ID, {'force_delete': None}),
         'delete_share_server_replica',
         exception.InvalidInput(reason='bad'), exc.HTTPBadRequest),
        ('force_delete', (REPLICA_ID, {'force_delete': None}),
         'delete_share_server_replica',
         exception.ReplicationException(reason='bad'), exc.HTTPBadRequest),
        ('promote', (REPLICA_ID, {'promote': {}}),
         'promote_share_server_replica',
         exception.InvalidInput(reason='bad'), exc.HTTPBadRequest),
        ('promote', (REPLICA_ID, {'promote': {}}),
         'promote_share_server_replica',
         exception.ReplicationException(reason='bad'), exc.HTTPBadRequest),
        ('resync', (REPLICA_ID, {'resync': {}}),
         'update_share_server_replica_state',
         exception.InvalidInput(reason='bad'), exc.HTTPBadRequest),
        ('resync', (REPLICA_ID, {'resync': {}}),
         'update_share_server_replica_state',
         exception.ReplicationException(reason='bad'), exc.HTTPBadRequest),
    )
    @ddt.unpack
    def test_share_api_errors_map_to_http_errors(
            self, method_name, args, api_attr, side_effect, expected):
        self._mock_lookups()
        self._mock_api(api_attr, side_effect=side_effect)

        self.assertRaises(expected, getattr(self.controller, method_name),
                          self.req, *args)

    @ddt.data(
        ('show', 'share_server_get', ()),
        ('delete', 'share_server_replica_get', ()),
        ('promote', 'share_server_replica_get', ({'promote': {}},)),
        ('resync', 'share_server_replica_get', ({'resync': {}},)),
    )
    @ddt.unpack
    def test_missing_replica_maps_to_404(self, method_name, db_attr, extra):
        self._mock_lookups()
        self._mock_db(db_attr, side_effect=NOT_FOUND)

        ex = self.assertRaises(
            exc.HTTPNotFound, getattr(self.controller, method_name),
            self.req, REPLICA_ID, *extra)

        self.assertIn(NOT_FOUND_MSG, ex.explanation)

    @ddt.data(('force_delete', {'force_delete': None}),
              ('reset_status', {'reset_status': {
                  'status': constants.STATUS_ERROR}}),
              ('reset_replica_state', {'reset_replica_state': {
                  'replica_state': constants.REPLICA_STATE_IN_SYNC}}))
    @ddt.unpack
    def test_admin_action_on_missing_replica_maps_to_404(
            self, method_name, body):
        self._mock_db('share_server_get', side_effect=exception.NotFound())

        self.assertRaises(
            exc.HTTPNotFound, getattr(self.controller, method_name),
            self.req, REPLICA_ID, body)

    @ddt.data(
        ('create_metadata', '_create_metadata',
         ({'metadata': {RESERVED: {'managed_by': 'driver'}}},)),
        ('update_all_metadata', '_update_all_metadata',
         ({'metadata': {RESERVED: {'managed_by': 'driver'}}},)),
        ('update_metadata_item', '_update_metadata_item',
         ({'metadata': {RESERVED: {'managed_by': 'driver'}}}, RESERVED)),
        # The key comes from the URL, so the body content is irrelevant.
        ('update_metadata_item', '_update_metadata_item',
         ({'metadata': {'other_key': 'value'}}, RESERVED)),
        ('delete_metadata', '_delete_metadata', (RESERVED,)),
    )
    @ddt.unpack
    def test_metadata_rejects_reserved_key(
            self, method_name, delegate_name, args):
        delegate = self._mock_controller(delegate_name)

        self.assertRaises(
            exc.HTTPBadRequest, getattr(self.controller, method_name),
            self.req, REPLICA_ID, *args)
        self.assertFalse(delegate.called)

    @ddt.data(
        ('index_metadata', '_index_metadata', ()),
        ('show_metadata', '_show_metadata', ('key1',)),
        ('create_metadata', '_create_metadata', ({'metadata': {'k': 'v'}},)),
        ('update_metadata_item', '_update_metadata_item',
         ({'meta': {'k': 'v'}}, 'k')),
        ('delete_metadata', '_delete_metadata', ('key1',)),
    )
    @ddt.unpack
    def test_metadata_delegates_to_base_controller(
            self, method_name, delegate_name, args):
        delegate = self._mock_controller(delegate_name,
                                         return_value='delegated')

        result = getattr(self.controller, method_name)(
            self.req, REPLICA_ID, *args)

        self.assertEqual('delegated', result)
        delegate.assert_called_once_with(self.req, REPLICA_ID, *args)

    @ddt.data(
        # backend_details is the driver's, so it outlives what callers send.
        ({'key2': 'value3'},
         {RESERVED: '{"a": "b"}', 'old_key': 'old_value'},
         {'key2': 'value3', RESERVED: '{"a": "b"}'}),
        # Even wiping the metadata leaves backend_details in place.
        ({}, {RESERVED: '{"a": "b"}'}, {RESERVED: '{"a": "b"}'}),
        # Nothing to carry over when the replica has no backend_details.
        ({'key2': 'value3'}, {'old_key': 'old_value'}, {'key2': 'value3'}),
    )
    @ddt.unpack
    def test_update_all_metadata_preserves_backend_details(
            self, sent, existing, expected):
        self._mock_db('share_server_replica_metadata_get',
                      return_value=existing)
        update_all = self._mock_controller('_update_all_metadata')

        self.controller.update_all_metadata(
            self.req, REPLICA_ID, {'metadata': sent})

        _, _, body = update_all.call_args[0]
        self.assertEqual(expected, body['metadata'])

    def test_update_all_metadata_body_without_metadata(self):
        """A body carrying no metadata is left for the base controller."""
        self._mock_db('share_server_replica_metadata_get',
                      return_value={RESERVED: '{"a": "b"}'})
        update_all = self._mock_controller('_update_all_metadata')

        body = {'not_metadata': {'key1': 'value1'}}
        self.controller.update_all_metadata(self.req, REPLICA_ID, body)

        update_all.assert_called_once_with(self.req, REPLICA_ID, body)

    def test_create_resource(self):
        self.assertIsNotNone(share_server_replicas.create_resource())
