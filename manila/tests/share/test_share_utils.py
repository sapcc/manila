# Copyright 2011 OpenStack Foundation
# Copyright (c) 2015 Rushil Chugh
# All Rights Reserved.
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

"""Tests For miscellaneous util methods used with share."""

from unittest import mock

import ddt

from manila.common import constants
from manila import exception
from manila.share import utils as share_utils
from manila import test


@ddt.ddt
class ShareUtilsTestCase(test.TestCase):
    def test_extract_host_without_pool(self):
        host = 'Host@Backend'
        self.assertEqual(
            'Host@Backend', share_utils.extract_host(host))

    def test_extract_host_only_return_host(self):
        host = 'Host@Backend'
        self.assertEqual(
            'Host', share_utils.extract_host(host, 'host'))

    def test_extract_host_only_return_pool(self):
        host = 'Host@Backend'
        self.assertIsNone(
            share_utils.extract_host(host, 'pool'))

    def test_extract_host_only_return_backend(self):
        host = 'Host@Backend'
        self.assertEqual(
            'Host@Backend', share_utils.extract_host(host, 'backend'))

    def test_extract_host_missing_backend_and_pool(self):
        host = 'Host'
        # Default level is 'backend'
        self.assertEqual(
            'Host', share_utils.extract_host(host))

    def test_extract_host_only_return_backend_name(self):
        host = 'Host@Backend#Pool'
        self.assertEqual(
            'Backend', share_utils.extract_host(host, 'backend_name'))

    def test_extract_host_only_return_backend_name_index_error(self):
        host = 'Host#Pool'

        self.assertRaises(IndexError,
                          share_utils.extract_host,
                          host, 'backend_name')

    def test_extract_host_missing_backend(self):
        host = 'Host#Pool'
        self.assertEqual(
            'Host', share_utils.extract_host(host))
        self.assertEqual(
            'Host', share_utils.extract_host(host, 'host'))

    def test_extract_host_missing_backend_only_return_backend(self):
        host = 'Host#Pool'
        self.assertEqual(
            'Host', share_utils.extract_host(host, 'backend'))

    def test_extract_host_missing_backend_only_return_pool(self):
        host = 'Host#Pool'
        self.assertEqual(
            'Pool', share_utils.extract_host(host, 'pool'))
        self.assertEqual(
            'Pool', share_utils.extract_host(host, 'pool', True))

    def test_extract_host_missing_pool(self):
        host = 'Host@Backend'
        self.assertIsNone(
            share_utils.extract_host(host, 'pool'))

    def test_extract_host_missing_pool_use_default_pool(self):
        host = 'Host@Backend'
        self.assertEqual(
            '_pool0', share_utils.extract_host(host, 'pool', True))

    def test_extract_host_with_default_pool(self):
        host = 'Host'
        # Default_pool_name doesn't work for level other than 'pool'
        self.assertEqual(
            'Host', share_utils.extract_host(host, 'host', True))
        self.assertEqual(
            'Host', share_utils.extract_host(host, 'host', False))
        self.assertEqual(
            'Host', share_utils.extract_host(host, 'backend', True))
        self.assertEqual(
            'Host', share_utils.extract_host(host, 'backend', False))

    def test_extract_host_with_pool(self):
        host = 'Host@Backend#Pool'
        self.assertEqual(
            'Host@Backend', share_utils.extract_host(host))
        self.assertEqual(
            'Host', share_utils.extract_host(host, 'host'))
        self.assertEqual(
            'Host@Backend', share_utils.extract_host(host, 'backend'),)
        self.assertEqual(
            'Pool', share_utils.extract_host(host, 'pool'))
        self.assertEqual(
            'Pool', share_utils.extract_host(host, 'pool', True))

    def test_append_host_with_host_and_pool(self):
        host = 'Host'
        pool = 'Pool'
        expected = 'Host#Pool'
        self.assertEqual(expected,
                         share_utils.append_host(host, pool))

    def test_append_host_with_host(self):
        host = 'Host'
        pool = None
        expected = 'Host'
        self.assertEqual(expected,
                         share_utils.append_host(host, pool))

    def test_append_host_with_pool(self):
        host = None
        pool = 'pool'
        expected = None
        self.assertEqual(expected,
                         share_utils.append_host(host, pool))

    def test_append_host_with_no_values(self):
        host = None
        pool = None
        expected = None
        self.assertEqual(expected,
                         share_utils.append_host(host, pool))

    def test_get_active_replica_success(self):
        replica_list = [{'id': '123456',
                         'replica_state': constants.REPLICA_STATE_IN_SYNC},
                        {'id': '654321',
                         'replica_state': constants.REPLICA_STATE_ACTIVE},
                        ]
        replica = share_utils.get_active_replica(replica_list)
        self.assertEqual('654321', replica['id'])

    def test_get_active_replica_not_exist(self):
        replica_list = [{'id': '123456',
                         'replica_state': constants.REPLICA_STATE_IN_SYNC},
                        {'id': '654321',
                         'replica_state': constants.REPLICA_STATE_OUT_OF_SYNC},
                        ]
        replica = share_utils.get_active_replica(replica_list)
        self.assertIsNone(replica)

    @ddt.data(
        dict(include_metadata=True, metadata={'key': 'value'},
             expected_metadata={'key': 'value'}),
        # Asking for metadata when there is none yields an empty mapping.
        dict(include_metadata=True, expected_metadata={}),
        dict(include_metadata=False),
        # Statuses ride through untranslated, the active one included.
        dict(include_metadata=False, status=constants.STATUS_ACTIVE,
             replica_state=constants.REPLICA_STATE_ACTIVE),
    )
    @ddt.unpack
    def test_build_share_server_replica_payload(
            self, include_metadata, metadata=None, expected_metadata=None,
            status=constants.STATUS_INACTIVE,
            replica_state=constants.REPLICA_STATE_OUT_OF_SYNC):
        replica_server = {
            'id': 'fake_server_id',
            'status': status,
            'replica_state': replica_state,
            'backend_details': {'vserver_name': 'vs1',
                                'ports': '{"p1": "10.0.0.10"}'},
        }

        payload = share_utils.build_share_server_replica_payload(
            replica_server, include_metadata=include_metadata,
            metadata=metadata)

        self.assertEqual('fake_server_id', payload['id'])
        self.assertEqual(status, payload['status'])
        self.assertEqual(replica_state, payload['replica_state'])
        # The whole row rides along, so drivers keep their backend_details.
        self.assertEqual(replica_server, payload['share_server'])
        if include_metadata:
            self.assertEqual(expected_metadata, payload['metadata'])
        else:
            self.assertNotIn('metadata', payload)

    @ddt.data(
        # A secondary points at its source and carries a replication state.
        ({'source_share_server_id': 'source-id',
          'replica_state': constants.REPLICA_STATE_IN_SYNC}, True, False),
        # An active state on a secondary still does not make it the source.
        ({'source_share_server_id': 'source-id',
          'replica_state': constants.REPLICA_STATE_ACTIVE}, True, False),
        # The active replica is the source, so it points at none itself.
        ({'source_share_server_id': None,
          'replica_state': constants.REPLICA_STATE_ACTIVE}, False, True),
        # A migration destination has a source but no replication state.
        ({'source_share_server_id': 'source-id', 'replica_state': None},
         False, False),
        # A share server outside replication altogether is neither.
        ({'source_share_server_id': None, 'replica_state': None},
         False, False),
    )
    @ddt.unpack
    def test_share_server_replica_predicates(
            self, server, is_replica, is_active):
        self.assertEqual(is_replica,
                         share_utils.is_share_server_replica(server))
        self.assertEqual(is_active,
                         share_utils.is_active_share_server_replica(server))

    def test_get_share_server_replicas_skips_non_replica_rows(self):
        """Rows sharing a source id are not all replicas of it."""
        replica = {'source_share_server_id': 'source-id',
                   'replica_state': constants.REPLICA_STATE_IN_SYNC}
        migration_dest = {'source_share_server_id': 'source-id',
                          'replica_state': None}
        db = mock.Mock()
        db.share_server_get_all_with_filters.return_value = [
            replica, migration_dest]

        result = share_utils.get_share_server_replicas(
            mock.sentinel.context, db, 'source-id')

        self.assertEqual([replica], result)
        db.share_server_get_all_with_filters.assert_called_once_with(
            mock.sentinel.context, {'source_share_server_id': 'source-id'})

    @ddt.data(
        # A subnet naming a zone settles it without any lookup.
        dict(server={'availability_zone': 'az1', 'host': 'host@backend#pool'},
             expected='az1', expect_lookup=False),
        # Only default subnets, which name no zone: the host decides.
        dict(server={'host': 'host@backend#pool'}, service_az='az-of-host',
             expected='az-of-host'),
        # A service with no zone of its own leaves the replica without one.
        dict(server={'host': 'host@backend#pool'}, expected=None),
        # A replica the scheduler has not placed yet has no host to ask.
        dict(server={'host': ''}, expected=None, expect_lookup=False),
        # Neither does one whose host is not a known share service.
        dict(server={'host': 'host@backend#pool'},
             service=exception.ServiceNotFound(service_id='host@backend'),
             expected=None),
    )
    @ddt.unpack
    def test_get_share_server_availability_zone(
            self, server, expected, service_az=None, service=None,
            expect_lookup=True):
        db = mock.Mock()
        if isinstance(service, Exception):
            db.service_get_by_args.side_effect = service
        else:
            found = mock.Mock()
            found.availability_zone = None
            if service_az:
                found.availability_zone = mock.Mock()
                found.availability_zone.name = service_az
            db.service_get_by_args.return_value = found

        result = share_utils.get_share_server_availability_zone(
            mock.sentinel.context, db, server)

        self.assertEqual(expected, result)
        if expect_lookup:
            db.service_get_by_args.assert_called_once_with(
                mock.sentinel.context, 'host@backend', 'manila-share')
        else:
            db.service_get_by_args.assert_not_called()

    @ddt.data(
        {'fake_subnet': [{'neutron_net_id': 'fake_nn_id',
                          'neutron_subnet_id': 'fake_nsb_id'}],
         'fake_new_subnet': [{'neutron_net_id': 'fake_nn_id',
                             'neutron_subnet_id': 'fake_nsb_id'}],
         'is_compatible': True},
        {'fake_subnet': [{'neutron_net_id': 'fake_nn_id',
                         'neutron_subnet_id': 'fake_nsb_id'}],
         'fake_new_subnet': [{'neutron_net_id': 'fake_nn_id',
                             'neutron_subnet_id': 'fake_nsb_id2'}],
         'is_compatible': False},
        {'fake_subnet': [{'neutron_net_id': 'fake_nn_id',
                          'neutron_subnet_id': 'fake_nsb_id'},
                         {'neutron_net_id': 'fake_nn_id2',
                          'neutron_subnet_id': 'fake_nsb_id2'}],
         'fake_new_subnet': [{'neutron_net_id': 'fake_nn_id',
                              'neutron_subnet_id': 'fake_nsb_id'}],
         'is_compatible': False}
    )
    @ddt.unpack
    def test_is_az_subnets_compatible(self, fake_subnet, fake_new_subnet,
                                      is_compatible):
        expected_result = is_compatible
        result = share_utils.is_az_subnets_compatible(fake_subnet,
                                                      fake_new_subnet)
        self.assertEqual(expected_result, result)

    @ddt.data(
        ([{'id': 'replica-1',
           'replica_state': constants.REPLICA_STATE_ACTIVE}], True),
        ([{'id': 'replica-1', 'replica_state': None}], False),
    )
    @ddt.unpack
    def test_is_share_server_replication_enabled(
            self, replica_servers, expected_enabled):
        db = mock.Mock()
        db.share_server_get_all_with_filters.return_value = replica_servers
        share_server = {'id': 'source-server-id'}

        result = share_utils.is_share_server_replication_enabled(
            mock.sentinel.context, db, share_server)

        self.assertEqual(expected_enabled, result)
        db.share_server_get_all_with_filters.assert_called_once_with(
            mock.sentinel.context,
            {'source_share_server_id': 'source-server-id'})

    @ddt.data(
        # The server id is taken off the loaded instance...
        dict(share={'instance': {'share_server_id': 'server-id'}},
             enabled=True, expected=True),
        # ...or off the share itself...
        dict(share={'share_server_id': 'server-id'}, enabled=True,
             expected=True),
        # ...or off whichever instance carries one.
        dict(share={'instances': [{}, {'share_server_id': 'server-id'}]},
             enabled=True, expected=True),
        # A server without replication leaves its shares unprotected.
        dict(share={'instance': {'share_server_id': 'server-id'}},
             enabled=False, expected=False),
        # A share with no server at all is not worth looking up.
        dict(share={'instance': {}, 'instances': []}, expected=False,
             expect_lookup=False),
        # Neither is one whose share server has gone away.
        dict(share={'share_server_id': 'server-id'},
             server=exception.ShareServerNotFound(
                 share_server_id='server-id'),
             expected=False),
    )
    @ddt.unpack
    def test_is_share_protected_via_share_server_replica(
            self, share, expected, enabled=False, server=None,
            expect_lookup=True):
        db = mock.Mock()
        if isinstance(server, Exception):
            db.share_server_get.side_effect = server
        else:
            db.share_server_get.return_value = {'id': 'server-id'}
        self.mock_object(
            share_utils, 'is_share_server_replication_enabled',
            mock.Mock(return_value=enabled))

        result = share_utils.is_share_protected_via_share_server_replica(
            mock.sentinel.context, db, share)

        self.assertEqual(expected, result)
        if expect_lookup:
            db.share_server_get.assert_called_once_with(
                mock.sentinel.context, 'server-id')
        else:
            db.share_server_get.assert_not_called()


class NotifyUsageTestCase(test.TestCase):
    @mock.patch('manila.share.utils._usage_from_share')
    @mock.patch('manila.share.utils.CONF')
    @mock.patch('manila.share.utils.rpc')
    def test_notify_about_share_usage(self, mock_rpc, mock_conf, mock_usage):
        mock_conf.host = 'host1'
        output = share_utils.notify_about_share_usage(mock.sentinel.context,
                                                      mock.sentinel.share,
                                                      mock.sentinel.
                                                      share_instance,
                                                      'test_suffix')
        self.assertIsNone(output)
        mock_usage.assert_called_once_with(mock.sentinel.share,
                                           mock.sentinel.share_instance)
        mock_rpc.get_notifier.assert_called_once_with('share',
                                                      'host1')
        mock_rpc.get_notifier.return_value.info.assert_called_once_with(
            mock.sentinel.context,
            'share.test_suffix',
            mock_usage.return_value)

    @mock.patch('manila.share.utils._usage_from_share')
    @mock.patch('manila.share.utils.CONF')
    @mock.patch('manila.share.utils.rpc')
    def test_notify_about_share_usage_with_kwargs(self, mock_rpc, mock_conf,
                                                  mock_usage):
        mock_conf.host = 'host1'
        output = share_utils.notify_about_share_usage(mock.sentinel.context,
                                                      mock.sentinel.share,
                                                      mock.sentinel.
                                                      share_instance,
                                                      'test_suffix',
                                                      extra_usage_info={
                                                          'a': 'b', 'c': 'd'},
                                                      host='host2')
        self.assertIsNone(output)
        mock_usage.assert_called_once_with(mock.sentinel.share,
                                           mock.sentinel.share_instance,
                                           a='b', c='d')
        mock_rpc.get_notifier.assert_called_once_with('share',
                                                      'host2')
        mock_rpc.get_notifier.return_value.info.assert_called_once_with(
            mock.sentinel.context,
            'share.test_suffix',
            mock_usage.return_value)
