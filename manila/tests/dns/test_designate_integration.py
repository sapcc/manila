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

from manila.dns import designate
from manila import exception
from manila import test


class DesignateAPIIntegrationTestCase(test.TestCase):
    def setUp(self):
        super(DesignateAPIIntegrationTestCase, self).setUp()
        self.context = mock.Mock()
        self.context.is_admin = True

    @mock.patch('manila.dns.designate.CONF')
    def test_designate_api_enabled_when_configured(self, mock_conf):
        mock_conf.__getitem__.return_value.enabled = True

        api = designate.API()
        self.assertTrue(api.enabled)

    @mock.patch('manila.dns.designate.CONF')
    def test_designate_api_disabled_when_not_enabled(self, mock_conf):
        mock_conf.__getitem__.return_value.enabled = False

        api = designate.API()
        self.assertFalse(api.enabled)

    @mock.patch('manila.dns.designate.designateclient')
    @mock.patch('manila.dns.designate.CONF')
    def test_create_dns_record_success(self, mock_conf, mock_designate_client):
        mock_conf.__getitem__.return_value.enabled = True
        mock_conf.__getitem__.return_value.ttl = 300

        mock_client = mock.Mock()
        mock_designate_client.return_value = mock_client
        mock_client.zones.list.return_value = [
            {'id': '9cd5947b-9173-488a-940f-57eeeb7604a3',
             'name': 'user_test.com.'}
        ]
        mock_client.recordsets.create.return_value = {
            'id': 'recordset-123',
            'name': 'test-share.user_test.com.',
            'type': 'A',
            'records': ['192.168.1.50']
        }
        self.context.project_id = None

        api = designate.API()
        result = api.create_record(
            self.context,
            dns_name='test-share',
            dns_domain='user_test.com.',
            ip_addresses=['192.168.1.50']
        )

        self.assertEqual(result, 'recordset-123')
        mock_client.zones.list.assert_called_once_with(
            criterion={'name': 'user_test.com.'})
        mock_client.recordsets.create.assert_called_once()

    @mock.patch('manila.dns.designate.designateclient')
    @mock.patch('manila.dns.designate.CONF')
    def test_create_dns_record_zone_not_found(self, mock_conf,
                                              mock_designate_client):
        mock_conf.__getitem__.return_value.enabled = True
        mock_conf.__getitem__.return_value.ttl = 300

        mock_client = mock.Mock()
        mock_designate_client.return_value = mock_client
        mock_client.zones.list.return_value = []

        api = designate.API()
        self.assertRaises(
            exception.NotFound,
            api.create_record,
            self.context,
            dns_name='test-share',
            dns_domain='unknown.com.',
            ip_addresses=['192.168.1.50'],
        )
        mock_client.recordsets.create.assert_not_called()

    @mock.patch('manila.dns.designate.designateclient')
    @mock.patch('manila.dns.designate.CONF')
    def test_create_dns_record_failure_raises(self, mock_conf,
                                              mock_designate_client):
        mock_conf.__getitem__.return_value.enabled = True
        mock_conf.__getitem__.return_value.ttl = 300

        mock_client = mock.Mock()
        mock_designate_client.return_value = mock_client
        mock_client.zones.list.return_value = [
            {'id': '9cd5947b-9173-488a-940f-57eeeb7604a3',
             'name': 'user_test.com.'}
        ]
        mock_client.recordsets.create.side_effect = RuntimeError(
            "Designate API error")

        api = designate.API()
        self.assertRaises(
            RuntimeError,
            api.create_record,
            self.context,
            dns_name='test-share',
            dns_domain='user_test.com.',
            ip_addresses=['192.168.1.50'],
        )

    @mock.patch('manila.dns.designate.designateclient')
    @mock.patch('manila.dns.designate.CONF')
    def test_delete_dns_record_success(self, mock_conf,
                                       mock_designate_client):
        """Test successful DNS record deletion."""
        mock_conf.__getitem__.return_value.enabled = True

        mock_client = mock.Mock()
        mock_designate_client.return_value = mock_client
        mock_client.zones.list.return_value = [
            {'id': '9cd5947b-9173-488a-940f-57eeeb7604a3',
             'name': 'user_test.com.'}
        ]
        mock_client.recordsets.list.return_value = [
            {'id': 'recordset-123', 'name': 'test-share.user_test.com.'}
        ]

        api = designate.API()
        result = api.delete_record(
            self.context,
            dns_name='test-share',
            dns_domain='user_test.com.'
        )

        self.assertTrue(result)
        mock_client.recordsets.list.assert_called_once()
        mock_client.recordsets.delete.assert_called_once()

    @mock.patch('manila.dns.designate.designateclient')
    @mock.patch('manila.dns.designate.CONF')
    def test_update_dns_record_success(self, mock_conf,
                                       mock_designate_client):
        mock_conf.__getitem__.return_value.enabled = True

        mock_client = mock.Mock()
        mock_designate_client.return_value = mock_client
        mock_client.zones.list.return_value = [
            {'id': '9cd5947b-9173-488a-940f-57eeeb7604a3',
             'name': 'user_test.com.'}
        ]
        mock_client.recordsets.list.return_value = [
            {'id': 'recordset-123', 'name': 'test-share.user_test.com.'}
        ]

        api = designate.API()
        result = api.update_record(
            self.context,
            dns_name='test-share',
            dns_domain='user_test.com.',
            ip_addresses=['192.168.1.100']
        )

        self.assertTrue(result)
        mock_client.recordsets.update.assert_called_once()

    @mock.patch('manila.dns.designate.designateclient')
    @mock.patch('manila.dns.designate.CONF')
    def test_update_dns_record_creates_if_not_exists(self, mock_conf,
                                                     mock_designate_client):
        mock_conf.__getitem__.return_value.enabled = True
        mock_conf.__getitem__.return_value.ttl = 300

        mock_client = mock.Mock()
        mock_designate_client.return_value = mock_client
        mock_client.zones.list.return_value = [
            {'id': '9cd5947b-9173-488a-940f-57eeeb7604a3',
             'name': 'user_test.com.'}
        ]
        mock_client.recordsets.list.return_value = []
        mock_client.recordsets.create.return_value = {
            'id': 'recordset-456',
            'name': 'new-share.user_test.com.',
            'type': 'A',
            'records': ['192.168.1.200']
        }

        api = designate.API()
        result = api.update_record(
            self.context,
            dns_name='new-share',
            dns_domain='user_test.com.',
            ip_addresses=['192.168.1.200']
        )

        self.assertEqual(result, 'recordset-456')
        mock_client.recordsets.create.assert_called_once()

    @mock.patch('manila.dns.designate.designateclient')
    @mock.patch('manila.dns.designate.CONF')
    def test_get_zone_id_appends_dot_if_missing(self, mock_conf,
                                                mock_designate_client):
        """_get_zone_id normalises domain to trailing dot before lookup."""
        mock_conf.__getitem__.return_value.enabled = True

        mock_client = mock.Mock()
        mock_client.zones.list.return_value = [
            {'id': 'zone-abc', 'name': 'example.com.'}
        ]

        api = designate.API()
        zone_id = api._get_zone_id(self.context, mock_client, 'example.com')

        self.assertEqual(zone_id, 'zone-abc')
        mock_client.zones.list.assert_called_once_with(
            criterion={'name': 'example.com.',
                       'project_id': self.context.project_id})
