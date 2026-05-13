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

from manila import context
from manila.share.drivers.netapp.dataontap.cluster_mode import lib_base
from manila import test


class NetAppLibBaseDNSMetadataTestCase(test.TestCase):
    """Tests that NetApp driver export addresses do NOT contain DNS metadata.

    DNS handling is the responsibility of ShareManager, not the driver.
    """

    def setUp(self):
        super(NetAppLibBaseDNSMetadataTestCase, self).setUp()
        self.context = context.get_admin_context()

    def _get_mock_driver(self):
        driver = mock.MagicMock(
            spec=lib_base.NetAppCmodeFileStorageLibrary)
        driver._is_flexgroup_pool = mock.Mock(return_value=False)
        driver._get_aggregate_node = mock.Mock(return_value='node1')
        driver._get_admin_addresses_for_share_server = mock.Mock(
            return_value=['10.0.0.1'])
        return driver

    def _get_mock_interfaces(self):
        return [
            {
                'address': '192.168.1.50',
                'home-node': 'node1',
            },
            {
                'address': '192.168.1.51',
                'home-node': 'node2',
            },
        ]

    def _get_mock_share(self, dns_name=None, dns_domain=None):
        metadata = {}
        if dns_name:
            metadata['dns_name'] = dns_name
        if dns_domain:
            metadata['dns_domain'] = dns_domain

        return {
            'id': 'share-id-123',
            'host': 'backend@pool1',
            'metadata': metadata,
        }

    def _call_method(self, share, share_server=None):
        driver = self._get_mock_driver()
        interfaces = self._get_mock_interfaces()
        method = lib_base.NetAppCmodeFileStorageLibrary\
            ._get_export_addresses_with_metadata
        return method(driver, share, share_server, interfaces, share['host'])

    def test_export_addresses_no_dns_metadata_without_share_dns(self):
        addresses = self._call_method(self._get_mock_share())

        for address, metadata in addresses.items():
            self.assertNotIn('dns_name', metadata)
            self.assertNotIn('dns_domain', metadata)
            self.assertIn('preferred', metadata)
            self.assertIn('is_admin_only', metadata)

    def test_export_addresses_no_dns_metadata_with_share_dns(self):
        share = self._get_mock_share(
            dns_name='my_pet_share', dns_domain='manila.com.')
        addresses = self._call_method(share)

        for address, metadata in addresses.items():
            self.assertNotIn('dns_name', metadata)
            self.assertNotIn('dns_domain', metadata)

    def test_preferred_path_identified_correctly(self):
        share = self._get_mock_share()
        addresses = self._call_method(share)

        self.assertTrue(addresses['192.168.1.50']['preferred'])
        self.assertFalse(addresses['192.168.1.51']['preferred'])

    def test_metadata_structure(self):
        addresses = self._call_method(self._get_mock_share())

        for address, metadata in addresses.items():
            self.assertIsInstance(metadata, dict)
            self.assertIn('is_admin_only', metadata)
            self.assertIn('preferred', metadata)
            self.assertIsInstance(metadata['is_admin_only'], bool)
            self.assertIsInstance(metadata['preferred'], bool)
