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

"""REST API Controller for Share Server Replicas."""

from http import client as http_client

import webob
from webob import exc

from manila.api import common
from manila.api.openstack import wsgi
from manila.api.v2 import metadata
from manila.api.views import share_server_replicas as replica_view
from manila.common import constants
from manila import db
from manila import exception
from manila.i18n import _
from manila.share import api as share_api
from manila.share import utils as share_utils

MIN_SUPPORTED_API_VERSION = '2.100'
RESERVED_METADATA_KEY = 'backend_details'


class ShareServerReplicaController(wsgi.Controller,
                                   metadata.MetadataController,
                                   wsgi.AdminActionsMixin):
    """The Share Server Replica API controller for the OpenStack API."""

    resource_name = 'share_server_replica'
    _view_builder_class = replica_view.ReplicaViewBuilder
    valid_statuses = dict(wsgi.AdminActionsMixin.valid_statuses)
    valid_statuses['status'] = set(constants.SHARE_SERVER_STATUSES)

    def __init__(self):
        super(ShareServerReplicaController, self).__init__()
        self.share_api = share_api.API()

    def _update(self, *args, **kwargs):
        db.share_server_update(*args, **kwargs)

    def _get(self, *args, **kwargs):
        return db.share_server_get(*args, **kwargs)

    def _delete(self, context, resource, force=False):
        try:
            self.share_api.delete_share_server_replica(
                context, resource['id'], force=force)
        except (exception.InvalidInput, exception.ReplicationException) as e:
            raise exc.HTTPBadRequest(explanation=e.msg)

    def _replica_view_data(self, context, replica, metadata=None):
        """Build a share server replica for the view builder."""

        data = dict(replica)
        data['share_network_id'] = replica.get('share_network_id')
        data['share_network_name'] = replica.get('share_network_name')
        data['availability_zone'] = (
            share_utils.get_share_server_availability_zone(
                context, db, replica))
        data['metadata'] = metadata or {}
        return data

    def _get_share_server_replica(self, context, replica_id):
        replica = db.share_server_get(context, replica_id)

        if not (share_utils.is_share_server_replica(replica) or
                share_utils.is_active_share_server_replica(replica)):
            raise exception.NotFound()

        return self._replica_view_data(
            context, replica,
            metadata=db.share_server_replica_metadata_get(
                context, replica_id))

    def _validate_body(self, body):
        if not self.is_valid_body(body, 'share_server_replica'):
            msg = _("Body does not contain 'share_server_replica' "
                    "information.")
            raise exc.HTTPUnprocessableEntity(explanation=msg)

    def _validate_reserved_metadata_key(self, key):
        if key == RESERVED_METADATA_KEY:
            raise exc.HTTPBadRequest(
                explanation=_(
                    'Metadata key "backend_details" is reserved for share '
                    'server replicas and cannot be modified.'
                ))

    def _validate_reserved_metadata_keys(self, metadata):
        for key in metadata or ():
            self._validate_reserved_metadata_key(key)

    def _validate_reserved_metadata_body(self, body):
        metadata = body.get('metadata') if isinstance(body, dict) else None
        self._validate_reserved_metadata_keys(metadata)
        return metadata

    def _get_share_server_replicas(self, req, is_detail=False):
        """Return list of share server replicas."""
        context = req.environ['manila.context']

        share_server_id = req.GET.get('share_server_id')
        sort_key = req.GET.get('sort_key', 'created_at')
        sort_dir = req.GET.get('sort_dir', 'desc')

        params = common.get_pagination_params(req)
        limit = params.get('limit')
        offset = params.get('offset')

        servers = db.share_server_replicas_get_all(
            context,
            source_share_server_id=share_server_id,
            sort_key=sort_key,
            sort_dir=sort_dir,
            limit=limit,
            offset=offset,
        )

        replicas = []
        for server in servers:
            metadata_data = {}
            if (is_detail and
                    not share_utils.is_active_share_server_replica(server)):
                metadata_data = db.share_server_replica_metadata_get(
                    context, server['id'])

            replicas.append(
                self._replica_view_data(context, server,
                                        metadata=metadata_data))

        if is_detail:
            return self._view_builder.detail_list(req, replicas)

        return self._view_builder.summary_list(req, replicas)

    def _replica_not_found_msg(self, replica_id):
        return _("No share server replica exists with ID %s.") % replica_id

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION, experimental=True)
    @wsgi.Controller.authorize
    @wsgi.response(http_client.ACCEPTED)
    def create(self, req, body):
        """Create a share server replica."""

        context = req.environ['manila.context']
        self._validate_body(body)
        replica_data = body.get('share_server_replica', {})

        share_server_id = replica_data.get('share_server_id')
        if not share_server_id:
            raise exc.HTTPBadRequest(
                explanation=_(
                    "Must provide Share Server ID to create share "
                    "server replica."
                )
            )

        availability_zone = replica_data.get('availability_zone')
        metadata_data = replica_data.get('metadata', {})
        share_network_id = replica_data.get('share_network_id')
        self._validate_reserved_metadata_keys(metadata_data)

        try:
            replica = self.share_api.create_share_server_replica(
                context,
                share_server_id=share_server_id,
                availability_zone=availability_zone,
                share_network_id=share_network_id,
                metadata=metadata_data,
            )
        except (exception.InvalidInput, exception.ReplicationException) as e:
            raise exc.HTTPBadRequest(explanation=e.msg)
        except exception.ShareServerReplicaExists as e:
            raise exc.HTTPConflict(explanation=e.msg)
        except exception.NotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)

        return self._view_builder.detail(
            req, self._replica_view_data(context, replica,
                                         metadata=metadata_data))

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION, experimental=True)
    @wsgi.Controller.authorize
    def index(self, req):
        """Return a summary list of share server replicas."""
        return self._get_share_server_replicas(req)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION, experimental=True)
    @wsgi.Controller.authorize('index')
    def detail(self, req):
        """Return a detailed list of share server replicas."""
        return self._get_share_server_replicas(req, is_detail=True)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION, experimental=True)
    @wsgi.Controller.authorize
    def show(self, req, id):
        """Show details of a share server replica."""
        context = req.environ['manila.context']

        try:
            replica = self._get_share_server_replica(context, id)
        except (exception.ShareServerReplicaNotFound, exception.NotFound):
            raise exc.HTTPNotFound(
                explanation=self._replica_not_found_msg(id))
        return self._view_builder.detail(req, replica)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION, experimental=True)
    def delete(self, req, id):
        return self._delete_share_server_replica(req, id)

    @wsgi.Controller.authorize('delete')
    def _delete_share_server_replica(self, req, id):
        """Delete a share server replica."""

        context = req.environ['manila.context']
        try:
            replica = db.share_server_replica_get(context, id)
        except exception.ShareServerReplicaNotFound:
            raise exc.HTTPNotFound(
                explanation=self._replica_not_found_msg(id))

        self._delete(context, replica)

        return webob.Response(status_int=http_client.ACCEPTED)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION, experimental=True)
    @wsgi.action('force_delete')
    def force_delete(self, req, id, body):
        """Force delete a share server replica."""
        return self._force_delete(req, id, body)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION, experimental=True)
    @wsgi.action('promote')
    @wsgi.Controller.authorize
    @wsgi.response(http_client.ACCEPTED)
    def promote(self, req, id, body):
        """Promote a share server replica."""
        context = req.environ['manila.context']

        try:
            replica = db.share_server_replica_get(context, id)
        except exception.ShareServerReplicaNotFound:
            raise exc.HTTPNotFound(
                explanation=self._replica_not_found_msg(id))

        if replica.get('replica_state') == constants.REPLICA_STATE_ACTIVE:
            return webob.Response(status_int=http_client.OK)

        try:
            self.share_api.promote_share_server_replica(context, id)
            replica = self._get_share_server_replica(context, id)
        except (exception.InvalidInput, exception.ReplicationException) as e:
            raise exc.HTTPBadRequest(explanation=e.msg)

        return self._view_builder.detail(req, replica)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION, experimental=True)
    @wsgi.action('resync')
    @wsgi.Controller.authorize
    @wsgi.response(http_client.ACCEPTED)
    def resync(self, req, id, body):
        """Resync a share server replica."""

        context = req.environ['manila.context']

        try:
            replica = db.share_server_replica_get(context, id)
        except exception.ShareServerReplicaNotFound:
            raise exc.HTTPNotFound(
                explanation=self._replica_not_found_msg(id))

        if replica.get('replica_state') == constants.REPLICA_STATE_ACTIVE:
            return webob.Response(status_int=http_client.OK)

        try:
            self.share_api.update_share_server_replica_state(context, id)
        except (exception.InvalidInput, exception.ReplicationException) as e:
            raise exc.HTTPBadRequest(explanation=e.msg)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION, experimental=True)
    @wsgi.action('reset_status')
    def reset_status(self, req, id, body):
        """Reset the 'status' attribute in the database."""
        return self._reset_status(req, id, body)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION, experimental=True)
    @wsgi.action('reset_replica_state')
    @wsgi.Controller.authorize
    def reset_replica_state(self, req, id, body):
        """Reset the replica_state of a share server replica."""
        return self._reset_status(req, id, body, status_attr='replica_state')

    @wsgi.Controller.api_version("2.100", experimental=True)
    @wsgi.Controller.authorize("get_metadata")
    def index_metadata(self, req, resource_id):
        return self._index_metadata(req, resource_id)

    @wsgi.Controller.api_version("2.100", experimental=True)
    @wsgi.Controller.authorize("update_metadata")
    def create_metadata(self, req, resource_id, body):
        self._validate_reserved_metadata_body(body)
        return self._create_metadata(req, resource_id, body)

    @wsgi.Controller.api_version("2.100", experimental=True)
    @wsgi.Controller.authorize("update_metadata")
    def update_all_metadata(self, req, resource_id, body):
        metadata_data = self._validate_reserved_metadata_body(body)

        existing_metadata = db.share_server_replica_metadata_get(
            req.environ['manila.context'], resource_id)
        backend_details = existing_metadata.get(RESERVED_METADATA_KEY)
        if backend_details is not None and metadata_data is not None:
            metadata_data = dict(metadata_data)
            metadata_data[RESERVED_METADATA_KEY] = backend_details
            body = dict(body)
            body['metadata'] = metadata_data

        return self._update_all_metadata(req, resource_id, body)

    @wsgi.Controller.api_version("2.100", experimental=True)
    @wsgi.Controller.authorize("update_metadata")
    def update_metadata_item(self, req, resource_id, body, key):
        self._validate_reserved_metadata_key(key)
        return self._update_metadata_item(req, resource_id, body, key)

    @wsgi.Controller.api_version("2.100", experimental=True)
    @wsgi.Controller.authorize("delete_metadata")
    def delete_metadata(self, req, resource_id, key):
        self._validate_reserved_metadata_key(key)
        return self._delete_metadata(req, resource_id, key)

    @wsgi.Controller.api_version("2.100", experimental=True)
    @wsgi.Controller.authorize("get_metadata")
    def show_metadata(self, req, resource_id, key):
        return self._show_metadata(req, resource_id, key)


# URL routing configuration
def create_resource():
    """Create the WSGI application for share server replicas."""
    return wsgi.Resource(ShareServerReplicaController())
