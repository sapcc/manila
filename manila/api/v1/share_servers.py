# Copyright 2014 OpenStack Foundation
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

from oslo_log import log
from six.moves import http_client
import webob
from webob import exc

from manila.api.openstack import wsgi
from manila.api.views import share_servers as share_servers_views
from manila.common import constants
from manila.db import api as db_api
from manila import exception
from manila.i18n import _
from manila import share

LOG = log.getLogger(__name__)


class ShareServerController(wsgi.Controller):
    """The Share Server API controller for the OpenStack API."""

    _view_builder_class = share_servers_views.ViewBuilder
    resource_name = 'share_server'

    def __init__(self):
        self.share_api = share.API()
        super(ShareServerController, self).__init__()

    @wsgi.Controller.authorize
    def index(self, req):
        """Returns a list of share servers."""

        context = req.environ['manila.context']

        search_opts = {}
        search_opts.update(req.GET)

        ss_filters = {}
        if 'host' in search_opts:
            ss_filters['host'] = search_opts.pop('host')
        if 'status' in search_opts:
            ss_filters['status'] = search_opts.pop('status')
        if 'source_share_server_id' in search_opts:
            ss_filters['source_share_server_id'] = search_opts.pop(
                'source_share_server_id')
        if 'identifier' in search_opts:
            ss_filters['identifier'] = search_opts.pop('identifier')
        share_servers = db_api.share_server_get_all_with_filters(
            context, ss_filters)

        if 'share_network_id' in search_opts:
            share_networks = [
                db_api.share_network_get(context,
                                         search_opts['share_network_id'])
            ]
        else:
            share_networks = db_api.share_network_get_all(context)
        share_network_map = {s["id"]: s for s in share_networks}
        for s in share_servers:
            if s.share_network_subnet:
                s.share_network_id = s.share_network_subnet['share_network_id']
                sn = share_network_map.get(s.share_network_id)
            else:
                s.share_network_id = None
                sn = None
            if sn:
                s.project_id = sn['project_id']
                s.share_network_name = sn['name'] or sn['id']
            else:
                # NOTE(dviroel): The share-network may already be deleted while
                # the share-server is in 'deleting' state. In this scenario,
                # we will return some empty values.
                LOG.debug("Unable to retrieve share network details for share "
                          "server %(server)s, the network %(network)s was "
                          "not found.",
                          {'server': s.id, 'network': s.share_network_id})
                s.project_id = ''
                s.share_network_name = ''
        if search_opts:
            for k, v in search_opts.items():
                share_servers = [s for s in share_servers if
                                 (hasattr(s, k) and
                                  s[k] == v or k == 'share_network' and
                                  v in [s.share_network_name,
                                        s.share_network_id])]
        return self._view_builder.build_share_servers(req, share_servers)

    @wsgi.Controller.authorize
    def show(self, req, id):
        """Return data about the requested share server."""
        context = req.environ['manila.context']
        try:
            server = db_api.share_server_get(context, id)
            share_network = db_api.share_network_get(
                context, server.share_network_subnet['share_network_id'])
            server.share_network_id = share_network['id']
            server.project_id = share_network['project_id']
            if share_network['name']:
                server.share_network_name = share_network['name']
            else:
                server.share_network_name = share_network['id']
        except exception.ShareServerNotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)
        except exception.ShareNetworkNotFound:
            msg = _("Share server %s could not be found. Its associated "
                    "share network does not "
                    "exist.") % server.share_network_subnet['share_network_id']
            raise exc.HTTPNotFound(explanation=msg)
        return self._view_builder.build_share_server(req, server)

    @wsgi.Controller.authorize
    def details(self, req, id):
        """Return details for requested share server."""
        context = req.environ['manila.context']
        try:
            share_server = db_api.share_server_get(context, id)
        except exception.ShareServerNotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)

        return self._view_builder.build_share_server_details(
            share_server['backend_details'])

    @wsgi.Controller.authorize
    def delete(self, req, id):
        """Delete specified share server."""
        context = req.environ['manila.context']
        try:
            share_server = db_api.share_server_get(context, id)
        except exception.ShareServerNotFound as e:
            raise exc.HTTPNotFound(explanation=e.msg)
        allowed_statuses = [constants.STATUS_ERROR, constants.STATUS_ACTIVE]
        if share_server['status'] not in allowed_statuses:
            data = {
                'status': share_server['status'],
                'allowed_statuses': allowed_statuses,
            }
            msg = _("Share server's actual status is %(status)s, allowed "
                    "statuses for deletion are %(allowed_statuses)s.") % (data)
            raise exc.HTTPForbidden(explanation=msg)
        LOG.debug("Deleting share server with id: %s.", id)
        try:
            self.share_api.delete_share_server(context, share_server)
        except exception.ShareServerInUse as e:
            raise exc.HTTPConflict(explanation=e.msg)
        return webob.Response(status_int=http_client.ACCEPTED)


def create_resource():
    return wsgi.Resource(ShareServerController())
