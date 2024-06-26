# Copyright (c) 2016 Clinton Knight
# All rights reserved.
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
"""
Performance metrics functions and cache for NetApp systems.
"""

import copy

from oslo_log import log as logging

from manila import exception
from manila.i18n import _
from manila.share.drivers.netapp.dataontap.client import api as netapp_api


LOG = logging.getLogger(__name__)
DEFAULT_UTILIZATION = 50


class PerformanceLibrary(object):

    def __init__(self, zapi_client):

        self.zapi_client = zapi_client
        self.performance_counters = {}
        self.pool_utilization = {}
        self._init_counter_info()

    def _init_counter_info(self):
        """Set a few counter names based on Data ONTAP version."""

        self.system_object_name = None
        self.avg_processor_busy_base_counter_name = None

        try:
            if self.zapi_client.features.SYSTEM_CONSTITUENT_METRICS:
                self.system_object_name = 'system:constituent'
                self.avg_processor_busy_base_counter_name = (
                    self._get_base_counter_name('system:constituent',
                                                'avg_processor_busy'))
            elif self.zapi_client.features.SYSTEM_METRICS:
                self.system_object_name = 'system'
                self.avg_processor_busy_base_counter_name = (
                    self._get_base_counter_name('system',
                                                'avg_processor_busy'))
        except netapp_api.NaApiError:
            if self.zapi_client.features.SYSTEM_CONSTITUENT_METRICS:
                self.avg_processor_busy_base_counter_name = 'cpu_elapsed_time'
            else:
                self.avg_processor_busy_base_counter_name = 'cpu_elapsed_time1'
            LOG.exception('Could not get performance base counter '
                          'name. Performance-based scheduler '
                          'functions may not be available.')

    def update_performance_cache(self, flexvol_pools, aggregate_pools):
        """Called periodically to update per-pool node utilization metrics."""

        # not working for us
        return
        # Nothing to do on older systems
        if not (self.zapi_client.features.SYSTEM_METRICS or
                self.zapi_client.features.SYSTEM_CONSTITUENT_METRICS):
            return

        # Get aggregates and nodes for all known pools
        aggr_names = self._get_aggregates_for_pools(flexvol_pools,
                                                    aggregate_pools)
        node_names, aggr_node_map = self._get_nodes_for_aggregates(aggr_names)

        # Update performance counter cache for each node
        node_utilization = {}
        for node_name in node_names:
            if node_name not in self.performance_counters:
                self.performance_counters[node_name] = []

            # Get new performance counters and save only the last 10
            counters = self._get_node_utilization_counters(node_name)
            if not counters:
                continue

            self.performance_counters[node_name].append(counters)
            self.performance_counters[node_name] = (
                self.performance_counters[node_name][-10:])

            # Update utilization for each node using newest & oldest sample
            counters = self.performance_counters[node_name]
            if len(counters) < 2:
                node_utilization[node_name] = DEFAULT_UTILIZATION
            else:
                node_utilization[node_name] = self._get_node_utilization(
                    counters[0], counters[-1], node_name)

        # Update pool utilization map atomically
        pool_utilization = {}
        all_pools = copy.deepcopy(flexvol_pools)
        all_pools.update(aggregate_pools)
        for pool_name, pool_info in all_pools.items():
            aggr_name = pool_info.get('netapp_aggregate', 'unknown')
            node_name = aggr_node_map.get(aggr_name)
            if node_name:
                pool_utilization[pool_name] = node_utilization.get(
                    node_name, DEFAULT_UTILIZATION)
            else:
                pool_utilization[pool_name] = DEFAULT_UTILIZATION

        self.pool_utilization = pool_utilization

    def get_node_utilization_for_pool(self, pool_name):
        """Get the node utilization for the specified pool, if available."""

        return self.pool_utilization.get(pool_name, DEFAULT_UTILIZATION)

    def update_for_failover(self, zapi_client, flexvol_pools, aggregate_pools):
        """Change API client after a whole-backend failover event."""

        self.zapi_client = zapi_client
        self.update_performance_cache(flexvol_pools, aggregate_pools)

    def _get_aggregates_for_pools(self, flexvol_pools, aggregate_pools):
        """Get the set of aggregates that contain the specified pools."""

        aggr_names = set()
        for pool_name, pool_info in aggregate_pools.items():
            if pool_info.get('netapp_flexgroup', False):
                continue
            aggr_names.add(pool_info.get('netapp_aggregate'))

        for pool_name, pool_info in flexvol_pools.items():
            if pool_info.get('netapp_flexgroup', False):
                continue
            aggr_names.add(pool_info.get('netapp_aggregate'))

        return list(aggr_names)

    def _get_nodes_for_aggregates(self, aggr_names):
        """Get the cluster nodes that own the specified aggregates."""

        node_names = set()
        aggr_node_map = {}

        for aggr_name in aggr_names:
            node_name = self.zapi_client.get_node_for_aggregate(aggr_name)
            if node_name:
                node_names.add(node_name)
                aggr_node_map[aggr_name] = node_name

        return list(node_names), aggr_node_map

    def _get_node_utilization(self, counters_t1, counters_t2, node_name):
        """Get node utilization from two sets of performance counters."""

        try:
            # Time spent in the single-threaded Kahuna domain
            kahuna_percent = self._get_kahuna_utilization(counters_t1,
                                                          counters_t2)

            # If Kahuna is using >60% of the CPU, the controller is fully busy
            if kahuna_percent > 60:
                return 100.0

            # Average CPU busyness across all processors
            avg_cpu_percent = 100.0 * self._get_average_cpu_utilization(
                counters_t1, counters_t2)

            # Total Consistency Point (CP) time
            total_cp_time_msec = self._get_total_consistency_point_time(
                counters_t1, counters_t2)

            # Time spent in CP Phase 2 (buffer flush)
            p2_flush_time_msec = self._get_consistency_point_p2_flush_time(
                counters_t1, counters_t2)

            # Wall-clock time between the two counter sets
            poll_time_msec = self._get_total_time(counters_t1,
                                                  counters_t2,
                                                  'total_cp_msecs')

            # If two polls happened in quick succession, use CPU utilization
            if total_cp_time_msec == 0 or poll_time_msec == 0:
                return max(min(100.0, avg_cpu_percent), 0)

            # Adjusted Consistency Point time
            adjusted_cp_time_msec = self._get_adjusted_consistency_point_time(
                total_cp_time_msec, p2_flush_time_msec)
            adjusted_cp_percent = (100.0 *
                                   adjusted_cp_time_msec / poll_time_msec)

            # Utilization is the greater of CPU busyness & CP time
            node_utilization = max(avg_cpu_percent, adjusted_cp_percent)
            return max(min(100.0, node_utilization), 0)

        except Exception:
            LOG.exception('Could not calculate node utilization for '
                          'node %s.', node_name)
            return DEFAULT_UTILIZATION

    def _get_kahuna_utilization(self, counters_t1, counters_t2):
        """Get time spent in the single-threaded Kahuna domain."""

        # Note(cknight): Because Kahuna is single-threaded, running only on
        # one CPU at a time, we can safely sum the Kahuna CPU usage
        # percentages across all processors in a node.
        return sum(self._get_performance_counter_average_multi_instance(
            counters_t1, counters_t2, 'domain_busy:kahuna',
            'processor_elapsed_time')) * 100.0

    def _get_average_cpu_utilization(self, counters_t1, counters_t2):
        """Get average CPU busyness across all processors."""

        return self._get_performance_counter_average(
            counters_t1, counters_t2, 'avg_processor_busy',
            self.avg_processor_busy_base_counter_name)

    def _get_total_consistency_point_time(self, counters_t1, counters_t2):
        """Get time spent in Consistency Points in msecs."""

        return float(self._get_performance_counter_delta(
            counters_t1, counters_t2, 'total_cp_msecs'))

    def _get_consistency_point_p2_flush_time(self, counters_t1, counters_t2):
        """Get time spent in CP Phase 2 (buffer flush) in msecs."""

        return float(self._get_performance_counter_delta(
            counters_t1, counters_t2, 'cp_phase_times:p2_flush'))

    def _get_total_time(self, counters_t1, counters_t2, counter_name):
        """Get wall clock time between two successive counters in msecs."""

        timestamp_t1 = float(self._find_performance_counter_timestamp(
            counters_t1, counter_name))
        timestamp_t2 = float(self._find_performance_counter_timestamp(
            counters_t2, counter_name))
        return (timestamp_t2 - timestamp_t1) * 1000.0

    def _get_adjusted_consistency_point_time(self, total_cp_time,
                                             p2_flush_time):
        """Get adjusted CP time by limiting CP phase 2 flush time to 20%."""

        return (total_cp_time - p2_flush_time) * 1.20

    def _get_performance_counter_delta(self, counters_t1, counters_t2,
                                       counter_name):
        """Calculate a delta value from two performance counters."""

        counter_t1 = int(
            self._find_performance_counter_value(counters_t1, counter_name))
        counter_t2 = int(
            self._find_performance_counter_value(counters_t2, counter_name))

        return counter_t2 - counter_t1

    def _get_performance_counter_average(self, counters_t1, counters_t2,
                                         counter_name, base_counter_name,
                                         instance_name=None):
        """Calculate an average value from two performance counters."""

        counter_t1 = float(self._find_performance_counter_value(
            counters_t1, counter_name, instance_name))
        counter_t2 = float(self._find_performance_counter_value(
            counters_t2, counter_name, instance_name))
        base_counter_t1 = float(self._find_performance_counter_value(
            counters_t1, base_counter_name, instance_name))
        base_counter_t2 = float(self._find_performance_counter_value(
            counters_t2, base_counter_name, instance_name))

        return (counter_t2 - counter_t1) / (base_counter_t2 - base_counter_t1)

    def _get_performance_counter_average_multi_instance(self, counters_t1,
                                                        counters_t2,
                                                        counter_name,
                                                        base_counter_name):
        """Calculate an average value from multiple counter instances."""

        averages = []
        instance_names = []
        for counter in counters_t1:
            if counter_name in counter:
                instance_names.append(counter['instance-name'])

        for instance_name in instance_names:
            average = self._get_performance_counter_average(
                counters_t1, counters_t2, counter_name, base_counter_name,
                instance_name)
            averages.append(average)

        return averages

    def _find_performance_counter_value(self, counters, counter_name,
                                        instance_name=None):
        """Given a counter set, return the value of a named instance."""

        for counter in counters:
            if counter_name in counter:
                if (instance_name is None
                        or counter['instance-name'] == instance_name):
                    return counter[counter_name]
        else:
            raise exception.NotFound(_('Counter %s not found') % counter_name)

    def _find_performance_counter_timestamp(self, counters, counter_name,
                                            instance_name=None):
        """Given a counter set, return the timestamp of a named instance."""

        for counter in counters:
            if counter_name in counter:
                if (instance_name is None
                        or counter['instance-name'] == instance_name):
                    return counter['timestamp']
        else:
            raise exception.NotFound(_('Counter %s not found') % counter_name)

    def _expand_performance_array(self, object_name, counter_name, counter):
        """Get array labels and expand counter data array."""

        # Get array labels for counter value
        counter_info = self.zapi_client.get_performance_counter_info(
            object_name, counter_name)

        array_labels = [counter_name + ':' + label.lower()
                        for label in counter_info['labels']]
        array_values = counter[counter_name].split(',')

        # Combine labels and values, and then mix into existing counter
        array_data = dict(zip(array_labels, array_values))
        counter.update(array_data)

    def _get_base_counter_name(self, object_name, counter_name):
        """Get the name of the base counter for the specified counter."""

        counter_info = self.zapi_client.get_performance_counter_info(
            object_name, counter_name)
        return counter_info['base-counter']

    def _get_node_utilization_counters(self, node_name):
        """Get all performance counters for calculating node utilization."""

        try:
            return (self._get_node_utilization_system_counters(node_name) +
                    self._get_node_utilization_wafl_counters(node_name) +
                    self._get_node_utilization_processor_counters(node_name))
        except netapp_api.NaApiError:
            LOG.exception('Could not get utilization counters from node '
                          '%s', node_name)
            return None

    def _get_node_utilization_system_counters(self, node_name):
        """Get the system counters for calculating node utilization."""

        system_instance_uuids = (
            self.zapi_client.get_performance_instance_uuids(
                self.system_object_name, node_name))

        system_counter_names = [
            'avg_processor_busy',
            self.avg_processor_busy_base_counter_name,
        ]
        if 'cpu_elapsed_time1' in system_counter_names:
            system_counter_names.append('cpu_elapsed_time')

        system_counters = self.zapi_client.get_performance_counters(
            self.system_object_name, system_instance_uuids,
            system_counter_names)

        return system_counters

    def _get_node_utilization_wafl_counters(self, node_name):
        """Get the WAFL counters for calculating node utilization."""

        wafl_instance_uuids = self.zapi_client.get_performance_instance_uuids(
            'wafl', node_name)

        wafl_counter_names = ['total_cp_msecs', 'cp_phase_times']
        wafl_counters = self.zapi_client.get_performance_counters(
            'wafl', wafl_instance_uuids, wafl_counter_names)

        # Expand array data so we can use wafl:cp_phase_times[P2_FLUSH]
        for counter in wafl_counters:
            if 'cp_phase_times' in counter:
                self._expand_performance_array(
                    'wafl', 'cp_phase_times', counter)

        return wafl_counters

    def _get_node_utilization_processor_counters(self, node_name):
        """Get the processor counters for calculating node utilization."""

        processor_instance_uuids = (
            self.zapi_client.get_performance_instance_uuids('processor',
                                                            node_name))

        processor_counter_names = ['domain_busy', 'processor_elapsed_time']
        processor_counters = self.zapi_client.get_performance_counters(
            'processor', processor_instance_uuids, processor_counter_names)

        # Expand array data so we can use processor:domain_busy[kahuna]
        for counter in processor_counters:
            if 'domain_busy' in counter:
                self._expand_performance_array(
                    'processor', 'domain_busy', counter)

        return processor_counters
