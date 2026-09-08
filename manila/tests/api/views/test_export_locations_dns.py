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

from manila.api.openstack import api_version_request
from manila.api.views import export_locations
from manila import test


class ExportLocationsViewBuilderDNSTestCase(test.TestCase):
    def setUp(self):
        super(ExportLocationsViewBuilderDNSTestCase, self).setUp()
        self.view_builder = export_locations.ViewBuilder()

    def _get_mock_export_location(self, dns_name=None, dns_domain=None,
                                  preferred=False):
        el_metadata = {'preferred': str(preferred).lower()}
        if dns_name:
            el_metadata['dns_name'] = dns_name
        if dns_domain:
            el_metadata['dns_domain'] = dns_domain

        return {
            'uuid': 'location-id-123',
            'path': '192.168.1.50:/share',
            'is_admin_only': False,
            'share_instance_id': 'instance-id-123',
            'created_at': '2026-04-09T10:00:00Z',
            'updated_at': '2026-04-09T10:00:00Z',
            'el_metadata': el_metadata,
        }

    def _get_request(self, version, is_admin=False):
        context = mock.Mock()
        context.is_admin = is_admin
        request = mock.Mock()
        request.environ = {'manila.context': context}
        request.api_version_request = api_version_request.APIVersionRequest(
            version)
        return request

    def test_dns_metadata_added_to_export_location_view(self):
        export_location = self._get_mock_export_location(
            dns_name='my_pet_share',
            dns_domain='manila.com.')

        request = self._get_request('2.96', is_admin=True)
        view = self.view_builder.summary(request, export_location)
        view_dict = view['export_location']

        self.assertEqual(view_dict['dns_name'], 'my_pet_share')
        self.assertEqual(view_dict['dns_domain'], 'manila.com.')

    def test_dns_metadata_not_added_when_missing(self):
        export_location = self._get_mock_export_location()

        request = self._get_request('2.96')
        view = self.view_builder.summary(request, export_location)
        view_dict = view['export_location']

        self.assertNotIn('dns_name', view_dict)
        self.assertNotIn('dns_domain', view_dict)

    def test_partial_dns_metadata(self):
        """Test with only dns_name (no dns_domain)."""
        export_location = self._get_mock_export_location(
            dns_name='test_share')

        request = self._get_request('2.96', is_admin=True)
        view = self.view_builder.summary(request, export_location)
        view_dict = view['export_location']

        self.assertEqual(view_dict['dns_name'], 'test_share')
        self.assertNotIn('dns_domain', view_dict)

    def test_dns_domain_only(self):
        """Test with only dns_domain (no dns_name)."""
        export_location = self._get_mock_export_location(
            dns_domain='example.com.')

        request = self._get_request('2.96', is_admin=True)
        view = self.view_builder.summary(request, export_location)
        view_dict = view['export_location']

        self.assertEqual(view_dict['dns_domain'], 'example.com.')
        self.assertNotIn('dns_name', view_dict)

    def test_dns_metadata_preserved_with_preferred(self):
        export_location = self._get_mock_export_location(
            dns_name='share1',
            dns_domain='test.com.',
            preferred=True)

        request = self._get_request('2.96', is_admin=True)
        view = self.view_builder.summary(request, export_location)
        view_dict = view['export_location']

        self.assertTrue(view_dict['preferred'])
        self.assertEqual(view_dict['dns_name'], 'share1')
        self.assertEqual(view_dict['dns_domain'], 'test.com.')

    def test_dns_fields_absent_before_2_96(self):
        export_location = self._get_mock_export_location(
            dns_name='share1',
            dns_domain='test.com.')

        request = self._get_request('2.95', is_admin=True)
        view = self.view_builder.summary(request, export_location)
        view_dict = view['export_location']

        self.assertNotIn('dns_name', view_dict)
        self.assertNotIn('dns_domain', view_dict)
