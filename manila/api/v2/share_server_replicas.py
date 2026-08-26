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


class ShareServerReplicaController(wsgi.Controller,
                                   metadata.MetadataController,
                                   wsgi.AdminActionsMixin):
    """The Share Server Replica API controller for the OpenStack API."""

    resource_name = 'share_server_replica'
    _view_builder_class = replica_view.ReplicaViewBuilder
    valid_statuses = dict(wsgi.AdminActionsMixin.valid_statuses)
    valid_statuses['status'] = (set(constants.SHARE_SERVER_STATUSES) |
                                set([constants.STATUS_AVAILABLE]))

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
        except exception.InvalidInput as e:
            raise exc.HTTPBadRequest(explanation=e.msg)

    def _get_share_server_replica(self, context, replica_id):
        replica = db.share_server_get(context, replica_id)

        if not (share_utils.is_share_server_replica(replica) or
                share_utils.is_active_share_server_replica(replica)):
            raise exception.NotFound()

        return share_utils.build_share_server_replica_row(
            context,
            db,
            replica,
            source_share_server_id=(
                replica.get('source_share_server_id')
            ),
            metadata_data=db.share_server_replica_metadata_get(
                context, replica_id),
        )

    def _validate_body(self, body):
        if not self.is_valid_body(body, 'share_server_replica'):
            msg = _("Body does not contain 'share_server_replica' "
                    "information.")
            raise exc.HTTPUnprocessableEntity(explanation=msg)

    def _validate_reserved_metadata_keys(self, metadata_data):
        if metadata_data and 'backend_details' in metadata_data:
            raise exc.HTTPBadRequest(
                explanation=_(
                    'Metadata key "backend_details" is reserved and cannot '
                    'be updated for share server replicas.'
                ))

    def _get_share_server_replicas(self, req, is_detail=False):
        """Return list of share server replicas."""
        context = req.environ['manila.context']

        share_server_id = req.GET.get('share_server_id')
        sort_key = req.GET.get('sort_key', 'created_at')
        sort_dir = req.GET.get('sort_dir', 'desc')

        try:
            params = common.get_pagination_params(req)
            limit = params.get('limit')
            offset = params.get('offset')

            if share_server_id:
                source = db.share_server_get(context, share_server_id)
                if not share_utils.is_active_share_server_replica(source):
                    servers = []
                else:
                    servers = db.share_server_replicas_get_all(
                        context,
                        source_share_server_id=share_server_id,
                        sort_key=sort_key,
                        sort_dir=sort_dir,
                        limit=limit,
                        offset=offset,
                    )
            else:
                servers = db.share_server_replicas_get_all(
                    context,
                    sort_key=sort_key,
                    sort_dir=sort_dir,
                    limit=limit,
                    offset=offset,
                )

            replicas = []
            for server in servers:
                if share_utils.is_active_share_server_replica(server):
                    replicas.append(share_utils.build_share_server_replica_row(
                        context, db, server,
                        source_share_server_id=server.get(
                            'source_share_server_id'),
                        metadata_data={},
                        replica_state=constants.REPLICA_STATE_ACTIVE,
                    ))
                else:
                    replicas.append(share_utils.build_share_server_replica_row(
                        context, db, server,
                        source_share_server_id=server.get(
                            'source_share_server_id'),
                        metadata_data=db.share_server_replica_metadata_get(
                            context, server.get('id')),
                    ))
        except exception.InvalidInput as e:
            raise exc.HTTPBadRequest(explanation=e.msg)

        if is_detail:
            return self._view_builder.detail_list(req, replicas)

        return self._view_builder.summary_list(req, replicas)

    def _replica_not_found_msg(self, replica_id):
        return _("No share server replica exists with ID %s.") % replica_id

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION)
    @wsgi.response(http_client.OK)
    @wsgi.Controller.authorize
    def create(self, req, body):
        """Create a share server replica."""

        context = req.environ['manila.context']
        self._validate_body(body)
        replica_data = body.get('share_server_replica', {})

        share_server_id = replica_data.get('share_server')
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
        except exception.InvalidInput as e:
            raise exc.HTTPBadRequest(explanation=e.msg)
        except exception.NoValidHost as e:
            raise exc.HTTPBadRequest(explanation=e.msg)
        except exception.ShareServerReplicaExists as e:
            raise exc.HTTPConflict(explanation=e.msg)
        except exception.NotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)

        return self._view_builder.detail(req, replica)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION)
    @wsgi.Controller.authorize
    def index(self, req):
        """Return a summary list of share server replicas."""
        return self._get_share_server_replicas(req)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION)
    @wsgi.Controller.authorize('index')
    def detail(self, req):
        """Return a detailed list of share server replicas."""
        return self._get_share_server_replicas(req, is_detail=True)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION)
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

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION)
    @wsgi.Controller.authorize
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

        try:
            self.share_api.delete_share_server_replica(context, replica['id'])
        except exception.InvalidInput as e:
            raise exc.HTTPBadRequest(explanation=e.msg)

        return webob.Response(status_int=http_client.ACCEPTED)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION)
    @wsgi.action('force_delete')
    def force_delete(self, req, id, body):
        """Force delete a share server replica."""
        return self._force_delete(req, id, body)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION)
    @wsgi.action('promote')
    @wsgi.Controller.authorize
    @wsgi.response(http_client.ACCEPTED)
    def promote(self, req, id, body):
        """Promote a share server replica."""
        context = req.environ['manila.context']
        promote_data = body.get('promote', {})
        promote_data = {} if promote_data is None else promote_data
        wait = promote_data.get('wait', False)

        try:
            replica = db.share_server_replica_get(context, id)
        except exception.ShareServerReplicaNotFound:
            raise exc.HTTPNotFound(
                explanation=self._replica_not_found_msg(id))

        if replica.get('replica_state') == constants.REPLICA_STATE_ACTIVE:
            return webob.Response(status_int=http_client.OK)

        try:
            self.share_api.promote_share_server_replica(
                context, id, wait=wait)
            replica = self._get_share_server_replica(context, id)
        except exception.InvalidInput as e:
            raise exc.HTTPBadRequest(explanation=e.msg)
        except exception.AdminRequired as e:
            raise exc.HTTPForbidden(explanation=e.message)

        return self._view_builder.detail(req, replica)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION)
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
        except exception.InvalidInput as e:
            raise exc.HTTPBadRequest(explanation=e.msg)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION)
    @wsgi.action('reset_status')
    @wsgi.Controller.authorize
    @wsgi.response(http_client.ACCEPTED)
    def reset_status(self, req, id, body):
        """Reset the status of a share server replica."""
        context = req.environ['manila.context']
        body_attr = self.body_attributes['status']
        status_update = self.validate_update(
            body.get(body_attr),
            status_attr='status')
        resource = None

        if status_update['status'] == constants.STATUS_AVAILABLE:
            try:
                resource = self._get(context, id)
            except exception.NotFound:
                raise exc.HTTPNotFound(
                    explanation=self._replica_not_found_msg(id))

            normalized_status = constants.STATUS_INACTIVE
            if resource.get('replica_state') == constants.REPLICA_STATE_ACTIVE:
                normalized_status = constants.STATUS_ACTIVE

            status_update = dict(status_update)
            status_update['status'] = normalized_status
            body[body_attr] = status_update

        return self._reset_status(req, id, body, resource=resource)

    @wsgi.Controller.api_version(MIN_SUPPORTED_API_VERSION)
    @wsgi.action('reset_replica_state')
    @wsgi.Controller.authorize
    @wsgi.response(http_client.OK)
    def reset_replica_state(self, req, id, body):
        """Reset the replica_state of a share server replica."""
        return self._reset_status(req, id, body, status_attr='replica_state')

    @wsgi.Controller.api_version("2.100")
    @wsgi.Controller.authorize("get_metadata")
    def index_metadata(self, req, resource_id):
        return self._index_metadata(req, resource_id)

    @wsgi.Controller.api_version("2.100")
    @wsgi.Controller.authorize("update_metadata")
    def create_metadata(self, req, resource_id, body):
        metadata_data = (
            body.get('metadata') if isinstance(body, dict) else None)
        self._validate_reserved_metadata_keys(metadata_data)
        return self._create_metadata(req, resource_id, body)

    @wsgi.Controller.api_version("2.100")
    @wsgi.Controller.authorize("update_metadata")
    def update_all_metadata(self, req, resource_id, body):
        metadata_data = (
            body.get('metadata') if isinstance(body, dict) else None)

        if 'backend_details' in metadata_data:
            raise exc.HTTPBadRequest(
                explanation=_(
                    'Metadata key "backend_details" is reserved and cannot '
                    'be updated for share server replicas.'
                ))

        existing_metadata = db.share_server_replica_metadata_get(
            req.environ['manila.context'], resource_id)
        backend_details = existing_metadata.get('backend_details')
        if backend_details is not None:
            metadata_data = dict(metadata_data)
            metadata_data['backend_details'] = backend_details
            body = dict(body)
            body['metadata'] = metadata_data

        return self._update_all_metadata(req, resource_id, body)

    @wsgi.Controller.api_version("2.100")
    @wsgi.Controller.authorize("update_metadata")
    def update_metadata_item(self, req, resource_id, body, key):
        metadata_data = (
            body.get('metadata') if isinstance(body, dict) else None)
        self._validate_reserved_metadata_keys(metadata_data)
        return self._update_metadata_item(req, resource_id, body, key)

    @wsgi.Controller.api_version("2.100")
    @wsgi.Controller.authorize("delete_metadata")
    def delete_metadata(self, req, resource_id, key):
        if key == 'backend_details':
            raise exc.HTTPBadRequest(
                explanation=_(
                    'Metadata key "backend_details" is reserved and cannot '
                    'be deleted for share server replicas.'
                ))
        return self._delete_metadata(req, resource_id, key)

    @wsgi.Controller.api_version("2.100")
    @wsgi.Controller.authorize("get_metadata")
    def show_metadata(self, req, resource_id, key):
        return self._show_metadata(req, resource_id, key)


# URL routing configuration
def create_resource():
    """Create the WSGI application for share server replicas."""
    return wsgi.Resource(ShareServerReplicaController())
