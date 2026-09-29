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

"""View definitions for share server replicas."""

from oslo_serialization import jsonutils

from manila.api import common
from manila.common import constants


class ReplicaViewBuilder(common.ViewBuilder):
    """Builds the view for share server replicas for REST API responses."""

    _collection_name = "share_server_replicas"
    _collection_route_name = "share-server-replicas"

    def _display_status(self, replica):
        status = replica.get("status")
        replica_state = replica.get("replica_state")

        # For non-active replicas, present backend "inactive" as
        # API/CLI-facing "available".
        if (
            status == constants.STATUS_INACTIVE
            and replica_state != constants.REPLICA_STATE_ACTIVE
        ):
            return constants.STATUS_AVAILABLE

        return status

    def summary_list(self, request, replicas):
        """Summary view of a list of share server replicas."""
        return self._list_view(self.summary, request, replicas)

    def detail_list(self, request, replicas):
        """Detailed view of a list of share server replicas."""
        return self._list_view(self.detail, request, replicas)

    def summary(self, request, replica):
        """Generic, non-detailed view of a share server replica."""
        replica_dict = {
            "id": replica.get("id"),
            "source_share_server_id": replica.get(
                "source_share_server_id"),
            "host": replica.get("host"),
            "status": self._display_status(replica),
            "replica_state": replica.get("replica_state"),
            "availability_zone": replica.get("availability_zone"),
        }

        return {"share_server_replica": replica_dict}

    def detail(self, request, replica):
        """Detailed view of a single share server replica."""
        replica_dict = self.summary(request, replica)["share_server_replica"]
        replica_dict.update({
            "created_at": replica.get("created_at"),
            "updated_at": replica.get("updated_at"),
            "share_network_id": replica.get("share_network_id"),
            "share_network_name": replica.get("share_network_name"),
        })

        metadata = replica.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        elif 'backend_details' in metadata:
            metadata = dict(metadata)
            metadata['backend_details'] = self._decode_metadata_value(
                metadata['backend_details'])
        replica_dict["metadata"] = metadata

        return {"share_server_replica": replica_dict}

    def _list_view(self, func, request, replicas):
        """Provide a view for a list of share server replicas."""
        replicas_list = [func(request, replica)["share_server_replica"]
                         for replica in replicas]

        return {self._collection_name: replicas_list}

    def _decode_metadata_value(self, value):
        if isinstance(value, dict):
            return {
                key: self._decode_metadata_value(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._decode_metadata_value(item) for item in value]
        if isinstance(value, str):
            try:
                parsed = jsonutils.loads(value)
            except (TypeError, ValueError):
                return value
            if isinstance(parsed, (dict, list)):
                return self._decode_metadata_value(parsed)
        return value
