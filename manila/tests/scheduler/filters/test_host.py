# Copyright (c) 2021 SAP.
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

import ddt

from manila.scheduler.filters import host
from manila import test
from manila.tests.scheduler import fakes


fake_host1 = fakes.FakeHostState('host1', {})
fake_host2 = fakes.FakeHostState('host2', {})
fake_host3 = fakes.FakeHostState('host3', {})


@ddt.ddt
class OnlyHostFilterTestCase(test.TestCase):
    """Test case for OnlyHostFilter."""

    def setUp(self):
        super(OnlyHostFilterTestCase, self).setUp()
        self.filter = host.OnlyHostFilter()

    def _make_filter_hints(self):
        return {
            'context': None,
            'scheduler_hints': {'only_host': fake_host1.host},
        }

    @ddt.data((fake_host1, {'context': None}),
              (fake_host1, {'context': None, 'scheduler_hints': None}),
              (fake_host1, {'context': None, 'scheduler_hints': {}}))
    @ddt.unpack
    def test_only_host_scheduler_hint_not_set(self, host, hints):
        self.assertTrue(self.filter.host_passes(host, hints))

    @ddt.data((fake_host1, True),
              (fake_host2, False),
              (fake_host3, False))
    @ddt.unpack
    def test_only_host_filter(self, host, host_passes):
        hints = self._make_filter_hints()
        self.assertEqual(host_passes, self.filter.host_passes(host, hints))
