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

from oslo_config import cfg

from manila.dns import designate
from manila import test


CONF = cfg.CONF


class DesignateShareLifecycleTestCase(test.TestCase):
    def setUp(self):
        super(DesignateShareLifecycleTestCase, self).setUp()
        self.context = mock.Mock()
        self.context.is_admin = True
        self.zone_id = '9cd5947b-9173-488a-940f-57eeeb7604a3'
        self.dns_name = 'test-share'
        self.dns_domain = 'user_test.com.'
        self.ip_addresses = ['192.168.1.50']

    def _make_client_mock(self, zone_id=None):
        """Return a mock Designate client with zones.list pre-configured."""
        mock_client = mock.Mock()
        mock_client.zones.list.return_value = [
            {'id': zone_id or self.zone_id, 'name': self.dns_domain}
        ]
        return mock_client

    @mock.patch('manila.dns.designate.designateclient')
    @mock.patch('manila.dns.designate.CONF')
    def test_share_lifecycle_with_dns(self, mock_conf, mock_designate_client):
        mock_conf.__getitem__.return_value.enabled = True
        mock_conf.__getitem__.return_value.ttl = 300

        mock_client = self._make_client_mock()
        mock_designate_client.return_value = mock_client

        mock_client.recordsets.create.return_value = {
            'id': 'recordset-1',
            'name': f'{self.dns_name}.{self.dns_domain}',
            'type': 'A',
            'records': self.ip_addresses
        }

        api = designate.API()
        recordset_id = api.create_record(
            self.context,
            self.dns_name,
            self.dns_domain,
            self.ip_addresses
        )
        self.assertEqual(recordset_id, 'recordset-1')

        new_ip = ['192.168.1.100']
        mock_client.recordsets.list.return_value = [
            {'id': 'recordset-1', 'name': f'{self.dns_name}.{self.dns_domain}'}
        ]

        update_result = api.update_record(
            self.context,
            self.dns_name,
            self.dns_domain,
            new_ip
        )
        self.assertTrue(update_result)
        mock_client.recordsets.update.assert_called_once()

        delete_result = api.delete_record(
            self.context,
            self.dns_name,
            self.dns_domain
        )
        self.assertTrue(delete_result)
        mock_client.recordsets.delete.assert_called_once()

    @mock.patch('manila.dns.designate.designateclient')
    @mock.patch('manila.dns.designate.CONF')
    def test_multiple_ips_for_single_share(self, mock_conf,
                                           mock_designate_client):
        mock_conf.__getitem__.return_value.enabled = True
        mock_conf.__getitem__.return_value.ttl = 300

        mock_client = self._make_client_mock()
        mock_designate_client.return_value = mock_client

        multiple_ips = ['192.168.1.50', '192.168.1.51', '192.168.1.52']

        mock_client.recordsets.create.return_value = {
            'id': 'recordset-multi',
            'name': f'{self.dns_name}.{self.dns_domain}',
            'type': 'A',
            'records': multiple_ips
        }

        api = designate.API()
        recordset_id = api.create_record(
            self.context,
            self.dns_name,
            self.dns_domain,
            multiple_ips
        )

        self.assertEqual(recordset_id, 'recordset-multi')
        call_args = mock_client.recordsets.create.call_args
        self.assertEqual(call_args[0][3], multiple_ips)

    @mock.patch('manila.dns.designate.CONF')
    def test_api_disabled_with_missing_config(self, mock_conf):
        mock_conf.__getitem__.return_value.enabled = False

        api = designate.API()
        self.assertFalse(api.enabled)

        result = api.create_record(
            self.context,
            self.dns_name,
            self.dns_domain,
            self.ip_addresses
        )
        self.assertIsNone(result)

        result = api.delete_record(
            self.context,
            self.dns_name,
            self.dns_domain
        )
        self.assertTrue(result)

    @mock.patch('manila.dns.designate.designateclient')
    @mock.patch('manila.dns.designate.CONF')
    def test_different_domains_use_different_zones(self, mock_conf,
                                                   mock_designate_client):
        """Each dns_domain resolves its own zone independently."""
        mock_conf.__getitem__.return_value.enabled = True
        mock_conf.__getitem__.return_value.ttl = 300

        mock_client = mock.Mock()
        mock_designate_client.return_value = mock_client

        zone_map = {
            'team-a.example.com.': 'zone-aaa',
            'team-b.internal.': 'zone-bbb',
        }

        def zones_list(criterion):
            name = criterion['name']
            zid = zone_map.get(name)
            return [{'id': zid, 'name': name}] if zid else []

        mock_client.zones.list.side_effect = zones_list
        mock_client.recordsets.create.side_effect = lambda zid, *a, **kw: {
            'id': 'rs-' + zid}

        api = designate.API()

        r1 = api.create_record(self.context, 'share1',
                               'team-a.example.com.', ['10.0.0.1'])
        r2 = api.create_record(self.context, 'share2',
                               'team-b.internal.', ['10.0.0.2'])

        self.assertEqual(r1, 'rs-zone-aaa')
        self.assertEqual(r2, 'rs-zone-bbb')
        self.assertEqual(mock_client.zones.list.call_count, 2)
