# Copyright 2026 SAP SE.
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

from unittest import mock

import ddt
from oslo_config import cfg

from manila.dns import designate
from manila import exception
from manila import test

CONF = cfg.CONF

ZONE_ID = '9cd5947b-9173-488a-940f-57eeeb7604a3'
PROJECT_ID = 'tenant-project'
SERVICE_PROJECT_ID = 'manila-service-project'


class FakeRemoteError(Exception):
    def __init__(self, code):
        super(FakeRemoteError, self).__init__('remote error %s' % code)
        self.code = code


@ddt.ddt
class ValidateDNSMetadataValuesTestCase(test.TestCase):

    @ddt.data(('share', 'example.com.', 'share', 'example.com.'),
              ('Share-1', 'Example.COM', 'share-1', 'example.com.'),
              (' share ', ' example.com. ', 'share', 'example.com.'),
              ('s', 'a.b.c', 's', 'a.b.c.'),
              (None, None, None, None),
              ('', '', '', ''))
    @ddt.unpack
    def test_normalizes(self, name, domain, exp_name, exp_domain):
        self.assertEqual(
            (exp_name, exp_domain),
            designate.validate_dns_metadata_values(name, domain))

    @ddt.data(('share', None), (None, 'example.com.'), ('share', ''),
              ('a.b', 'example.com.'), ('-share', 'example.com.'),
              ('share-', 'example.com.'), ('sh are', 'example.com.'),
              ('share_1', 'example.com.'), ('a' * 64, 'example.com.'),
              ('share', 'exa mple.com.'), ('share', '-bad.com.'),
              ('share', '.'), ('share', 'bad..com.'),
              ('share', '.'.join(['x' * 63] * 4) + '.'))
    @ddt.unpack
    def test_rejects(self, name, domain):
        self.assertRaises(exception.InvalidInput,
                          designate.validate_dns_metadata_values,
                          name, domain)

    def test_make_fqdn(self):
        self.assertEqual('share.example.com.',
                         designate.make_fqdn('share', 'example.com'))
        self.assertEqual('share.example.com.',
                         designate.make_fqdn('share', 'example.com.'))


@ddt.ddt
class DesignateAPITestCase(test.TestCase):

    def setUp(self):
        super(DesignateAPITestCase, self).setUp()
        self.context = mock.Mock(is_admin=True, project_id=PROJECT_ID)
        self.client = mock.Mock()
        self.client.zones.list.return_value = [
            {'id': ZONE_ID, 'name': 'example.com.',
             'project_id': PROJECT_ID}]
        self.mock_object(designate, 'designateclient',
                         mock.Mock(return_value=self.client))
        self.mock_object(designate, 'service_project_id',
                         mock.Mock(return_value=SERVICE_PROJECT_ID))
        self._set_enabled(True)
        CONF.set_override('ttl', 300, group='designate')
        self.addCleanup(CONF.clear_override, 'ttl', group='designate')
        self.api = designate.API()

    def _set_enabled(self, enabled):
        CONF.set_override('enabled', enabled, group='designate')
        self.addCleanup(CONF.clear_override, 'enabled', group='designate')

    def _recordset(self, records, rs_id='rs-1', name='share.example.com.',
                   ttl=300):
        return {'id': rs_id, 'name': name, 'type': 'A',
                'records': list(records), 'ttl': ttl}

    def test_disabled(self):
        self._set_enabled(False)
        api = designate.API()

        self.assertFalse(api.enabled)
        self.assertIsNone(api.ensure_record(
            self.context, PROJECT_ID, 'share', 'example.com.', ['10.0.0.1']))
        self.assertTrue(api.delete_record(
            self.context, PROJECT_ID, 'share', 'example.com.'))
        self.assertFalse(designate.designateclient.called)

    def test_get_zone_id_owned_by_project(self):
        zone_id = self.api._get_zone_id(self.client, PROJECT_ID,
                                        'example.com')

        self.assertEqual(ZONE_ID, zone_id)
        self.client.zones.list.assert_called_once_with(
            criterion={'name': 'example.com.'})

    def test_get_zone_id_owned_by_service_project(self):
        self.client.zones.list.return_value = [
            {'id': ZONE_ID, 'name': 'example.com.',
             'project_id': SERVICE_PROJECT_ID}]

        self.assertEqual(ZONE_ID, self.api._get_zone_id(
            self.client, PROJECT_ID, 'example.com.'))

    def test_get_zone_id_owned_by_other_project(self):
        self.client.zones.list.return_value = [
            {'id': ZONE_ID, 'name': 'example.com.',
             'project_id': 'someone-else'}]

        self.assertRaises(exception.DNSZoneNotFound,
                          self.api._get_zone_id,
                          self.client, PROJECT_ID, 'example.com.')

    def test_get_zone_id_not_found(self):
        self.client.zones.list.return_value = []

        self.assertRaises(exception.DNSZoneNotFound,
                          self.api._get_zone_id,
                          self.client, PROJECT_ID, 'example.com.')

    def test_get_zone_id_is_cached_per_project(self):
        self.api._get_zone_id(self.client, PROJECT_ID, 'example.com.')
        self.api._get_zone_id(self.client, PROJECT_ID, 'example.com.')
        self.assertEqual(1, self.client.zones.list.call_count)

        self.client.zones.list.return_value = [
            {'id': ZONE_ID, 'name': 'example.com.',
             'project_id': SERVICE_PROJECT_ID}]
        self.api._get_zone_id(self.client, 'another-project',
                              'example.com.')
        self.assertEqual(2, self.client.zones.list.call_count)

    def test_get_zone_id_cache_expires(self):
        self.mock_object(designate.timeutils, 'utcnow_ts',
                         mock.Mock(side_effect=[1000, 1301, 1301]))
        self.api._get_zone_id(self.client, PROJECT_ID, 'example.com.')
        self.api._get_zone_id(self.client, PROJECT_ID, 'example.com.')

        self.assertEqual(2, self.client.zones.list.call_count)

    def test_ensure_record_creates(self):
        self.client.recordsets.list.return_value = []
        self.client.recordsets.create.return_value = self._recordset(
            ['10.0.0.1'], rs_id='rs-new')

        rs_id = self.api.ensure_record(
            self.context, PROJECT_ID, 'share', 'example.com.',
            ['10.0.0.2', '10.0.0.1', '10.0.0.1'])

        self.assertEqual('rs-new', rs_id)
        self.client.recordsets.create.assert_called_once_with(
            ZONE_ID, 'share.example.com.', 'A', ['10.0.0.1', '10.0.0.2'],
            ttl=300)
        self.assertFalse(self.client.recordsets.update.called)

    def test_ensure_record_updates_by_name(self):
        self.client.recordsets.list.return_value = [
            self._recordset(['10.0.0.9'])]

        rs_id = self.api.ensure_record(
            self.context, PROJECT_ID, 'share', 'example.com.', ['10.0.0.1'])

        self.assertEqual('rs-1', rs_id)
        self.client.recordsets.list.assert_called_once_with(
            ZONE_ID, criterion={'name': 'share.example.com.', 'type': 'A'})
        self.client.recordsets.update.assert_called_once_with(
            ZONE_ID, 'rs-1', {'records': ['10.0.0.1'], 'ttl': 300})
        self.assertFalse(self.client.recordsets.create.called)

    def test_ensure_record_prefers_known_recordset_id(self):
        self.client.recordsets.get.return_value = self._recordset(
            ['10.0.0.9'], rs_id='rs-known')

        rs_id = self.api.ensure_record(
            self.context, PROJECT_ID, 'share', 'example.com.', ['10.0.0.1'],
            recordset_id='rs-known')

        self.assertEqual('rs-known', rs_id)
        self.client.recordsets.get.assert_called_once_with(
            ZONE_ID, 'rs-known')
        self.assertFalse(self.client.recordsets.list.called)
        self.client.recordsets.update.assert_called_once_with(
            ZONE_ID, 'rs-known', {'records': ['10.0.0.1'], 'ttl': 300})

    def test_ensure_record_falls_back_to_name_when_id_is_gone(self):
        self.client.recordsets.get.side_effect = FakeRemoteError(404)
        self.client.recordsets.list.return_value = []
        self.client.recordsets.create.return_value = self._recordset(
            ['10.0.0.1'], rs_id='rs-new')

        rs_id = self.api.ensure_record(
            self.context, PROJECT_ID, 'share', 'example.com.', ['10.0.0.1'],
            recordset_id='rs-old')

        self.assertEqual('rs-new', rs_id)
        self.client.recordsets.create.assert_called_once()

    def test_ensure_record_noop_when_up_to_date(self):
        self.client.recordsets.list.return_value = [
            self._recordset(['10.0.0.2', '10.0.0.1'])]

        rs_id = self.api.ensure_record(
            self.context, PROJECT_ID, 'share', 'example.com.',
            ['10.0.0.1', '10.0.0.2'])

        self.assertEqual('rs-1', rs_id)
        self.assertFalse(self.client.recordsets.update.called)
        self.assertFalse(self.client.recordsets.create.called)

    def test_ensure_record_conflict(self):
        self.client.recordsets.list.return_value = []
        self.client.recordsets.create.side_effect = FakeRemoteError(409)

        self.assertRaises(exception.DNSNameInUse,
                          self.api.ensure_record,
                          self.context, PROJECT_ID, 'share', 'example.com.',
                          ['10.0.0.1'])

    def test_ensure_record_zone_not_found(self):
        self.client.zones.list.return_value = []

        self.assertRaises(exception.DNSZoneNotFound,
                          self.api.ensure_record,
                          self.context, PROJECT_ID, 'share', 'example.com.',
                          ['10.0.0.1'])
        self.assertFalse(self.client.recordsets.create.called)

    def test_ensure_record_error_invalidates_zone_cache(self):
        self.client.recordsets.list.return_value = []
        self.client.recordsets.create.side_effect = RuntimeError('boom')

        self.assertRaises(RuntimeError, self.api.ensure_record,
                          self.context, PROJECT_ID, 'share', 'example.com.',
                          ['10.0.0.1'])
        self.assertEqual({}, self.api._zone_id_cache)

    def test_delete_record_by_id(self):
        self.client.recordsets.get.return_value = self._recordset(
            ['10.0.0.1'], rs_id='rs-known')

        self.assertTrue(self.api.delete_record(
            self.context, PROJECT_ID, 'share', 'example.com.',
            recordset_id='rs-known'))
        self.client.recordsets.delete.assert_called_once_with(
            ZONE_ID, 'rs-known')
        self.assertFalse(self.client.recordsets.list.called)

    def test_delete_record_by_name(self):
        self.client.recordsets.list.return_value = [
            self._recordset(['10.0.0.1'])]

        self.assertTrue(self.api.delete_record(
            self.context, PROJECT_ID, 'share', 'example.com.'))
        self.client.recordsets.delete.assert_called_once_with(
            ZONE_ID, 'rs-1')

    def test_delete_record_already_gone(self):
        self.client.recordsets.get.side_effect = FakeRemoteError(404)
        self.client.recordsets.list.return_value = []

        self.assertTrue(self.api.delete_record(
            self.context, PROJECT_ID, 'share', 'example.com.',
            recordset_id='rs-old'))
        self.assertFalse(self.client.recordsets.delete.called)

    def test_delete_record_zone_gone(self):
        self.client.zones.list.return_value = []

        self.assertTrue(self.api.delete_record(
            self.context, PROJECT_ID, 'share', 'example.com.'))

    def test_delete_record_failure_returns_false(self):
        self.client.recordsets.list.return_value = [
            self._recordset(['10.0.0.1'])]
        self.client.recordsets.delete.side_effect = RuntimeError('boom')

        self.assertFalse(self.api.delete_record(
            self.context, PROJECT_ID, 'share', 'example.com.'))
        self.assertEqual({}, self.api._zone_id_cache)

    def test_client_is_created_once(self):
        self.client.recordsets.list.return_value = [
            self._recordset(['10.0.0.1'])]

        self.api.ensure_record(self.context, PROJECT_ID, 'share',
                               'example.com.', ['10.0.0.1'])
        self.api.delete_record(self.context, PROJECT_ID, 'share',
                               'example.com.')

        designate.designateclient.assert_called_once_with(self.context)


class DesignateClientTestCase(test.TestCase):

    def test_designateclient_passes_options(self):
        loader = mock.Mock()
        self.mock_object(designate, '_get_auth_loader',
                         mock.Mock(return_value=loader))
        CONF.set_override('region_name', 'RegionOne', group='designate')
        self.addCleanup(CONF.clear_override, 'region_name',
                        group='designate')
        CONF.set_override('all_projects', False, group='designate')
        self.addCleanup(CONF.clear_override, 'all_projects',
                        group='designate')
        context = mock.Mock()

        client = designate.designateclient(context)

        self.assertEqual(loader.get_client.return_value, client)
        loader.get_client.assert_called_once_with(
            context, admin=True, endpoint_type='publicURL',
            region_name='RegionOne', all_projects=False)

    def test_service_project_id_failure_is_none(self):
        self.mock_object(designate, '_get_auth_loader',
                         mock.Mock(side_effect=ImportError('no client')))

        self.assertIsNone(designate.service_project_id())
