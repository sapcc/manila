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

from keystoneauth1 import loading as ks_loading
from oslo_config import cfg
from oslo_log import log
from oslo_utils import importutils
from oslo_utils import timeutils

from manila.common import client_auth
from manila import exception

_designateclient_module = importutils.try_import('designateclient.v2.client')

LOG = log.getLogger(__name__)

DESIGNATE_GROUP = 'designate'
AUTH_OBJ = None

_ZONE_CACHE_TTL_SECONDS = 300

designate_opts = [
    cfg.BoolOpt(
        'enabled',
        default=False,
        help='Enable Designate DNS integration for shares with DNS metadata.'),
    cfg.StrOpt(
        'endpoint_type',
        default='publicURL',
        help='Endpoint type to be used with Designate client calls.'),
    cfg.StrOpt(
        'region_name',
        help='Region name for connecting to Designate.'),
    cfg.IntOpt(
        'ttl',
        default=300,
        help='TTL in seconds for DNS A records created by Manila.'),
]

CONF = cfg.CONF
CONF.register_opts(designate_opts, DESIGNATE_GROUP)
ks_loading.register_session_conf_options(CONF, DESIGNATE_GROUP)
ks_loading.register_auth_conf_options(CONF, DESIGNATE_GROUP)


def list_opts():
    return client_auth.AuthClientLoader.list_opts(DESIGNATE_GROUP)


def designateclient(context):
    """Get authenticated Designate client using service credentials."""
    if _designateclient_module is None:
        raise ImportError(
            "python-designateclient is required for Designate integration. "
            "Install it with: pip install python-designateclient")
    global AUTH_OBJ
    if not AUTH_OBJ:
        AUTH_OBJ = client_auth.AuthClientLoader(
            client_class=_designateclient_module.Client,
            cfg_group=DESIGNATE_GROUP)
    return AUTH_OBJ.get_client(
        context,
        admin=True,
        endpoint_type=CONF[DESIGNATE_GROUP].endpoint_type,
        region_name=CONF[DESIGNATE_GROUP].region_name,
    )


class API(object):
    """API for interacting with Designate for DNS record management."""

    def __init__(self):
        self._enabled = CONF[DESIGNATE_GROUP].enabled
        self._client = None
        self._zone_id_cache = {}

    @property
    def enabled(self):
        """Returns True if Designate integration is enabled."""
        return self._enabled

    def _get_client(self, context):
        """Get and cache the Designate client."""

        if self._client is None:
            self._client = designateclient(context)
        return self._client

    def _get_zone_id(self, context, client, dns_domain, force_refresh=False):
        """Find Designate zone ID by domain name, scoped to project.

        Looks up the zone dynamically so that different shares can use
        different DNS domains without a hardcoded zone_id in the config.
        The lookup is filtered by the caller's project_id to prevent a
        privileged Manila service from writing into another project's zone.

        Results are cached for _ZONE_CACHE_TTL_SECONDS seconds. Pass
        force_refresh=True to bypass the cache (e.g. after a NotFound on
        write, which indicates the zone was recreated with a new ID).
        """
        project_id = context.project_id
        cache_key = (project_id, dns_domain)
        if not force_refresh and cache_key in self._zone_id_cache:
            zone_id, cached_at = self._zone_id_cache[cache_key]
            age = timeutils.utcnow_ts() - cached_at
            if age < _ZONE_CACHE_TTL_SECONDS:
                return zone_id
            # Cache expired — fall through to re-lookup below.
            del self._zone_id_cache[cache_key]

        name = dns_domain if dns_domain.endswith('.') else dns_domain + '.'
        criterion = {'name': name}
        if project_id:
            criterion['project_id'] = project_id
        zones = client.zones.list(criterion=criterion)
        if not zones:
            raise exception.NotFound(
                "Designate zone for domain '%s' not found in project '%s'. "
                "Ensure the zone exists and the Manila service account "
                "has access to it." % (dns_domain, project_id))
        zone_id = zones[0]['id']
        self._zone_id_cache[cache_key] = (zone_id, timeutils.utcnow_ts())
        return zone_id

    def create_record(self, context, dns_name, dns_domain, ip_addresses):
        """Create a DNS A recordset in Designate."""

        if not self.enabled:
            return None

        fqdn = '%s.%s' % (dns_name, dns_domain)
        client = self._get_client(context)
        zone_id = self._get_zone_id(context, client, dns_domain)
        try:
            recordset = client.recordsets.create(
                zone_id,
                fqdn,
                'A',
                ip_addresses,
                ttl=CONF[DESIGNATE_GROUP].ttl,
            )
        except Exception:
            # Invalidate the cached zone_id in case it became stale.
            self._zone_id_cache.pop((context.project_id, dns_domain), None)
            LOG.exception("Failed to create DNS A record '%s' -> %s.",
                          fqdn, ip_addresses)
            raise
        LOG.info("Created DNS A record '%s' -> %s (recordset %s)",
                 fqdn, ip_addresses, recordset['id'])
        return recordset['id']

    def delete_record(self, context, dns_name, dns_domain):
        """Delete a DNS A recordset from Designate."""

        if not self.enabled:
            return True

        fqdn = '%s.%s' % (dns_name, dns_domain)
        try:
            client = self._get_client(context)
            zone_id = self._get_zone_id(context, client, dns_domain)
            recordsets = client.recordsets.list(
                zone_id, criterion={'name': fqdn, 'type': 'A'})
            for rs in recordsets:
                client.recordsets.delete(zone_id, rs['id'])
                LOG.info("Deleted DNS A record '%s' (recordset %s)",
                         fqdn, rs['id'])
            return True
        except Exception:
            LOG.exception("Failed to delete DNS A record '%s'. "
                          "Manual cleanup may be required.", fqdn)
            return False

    def update_record(self, context, dns_name, dns_domain, ip_addresses):
        """Update a DNS A recordset in Designate."""

        if not self.enabled:
            return True

        fqdn = '%s.%s' % (dns_name, dns_domain)
        try:
            client = self._get_client(context)
            zone_id = self._get_zone_id(context, client, dns_domain)
            recordsets = client.recordsets.list(
                zone_id, criterion={'name': fqdn, 'type': 'A'})
            found = False
            for rs in recordsets:
                client.recordsets.update(
                    zone_id, rs['id'],
                    records=ip_addresses)
                LOG.info("Updated DNS A record '%s' -> %s",
                         fqdn, ip_addresses)
                found = True
                break
            if not found:
                return self.create_record(
                    context, dns_name, dns_domain, ip_addresses)
            return True
        except exception.NotFound:
            LOG.warning("Zone not found while updating '%s'; "
                        "refreshing zone cache and retrying.", fqdn)
            self._zone_id_cache.pop((context.project_id, dns_domain), None)
            try:
                self.create_record(context, dns_name, dns_domain, ip_addresses)
                return True
            except Exception:
                LOG.exception("Failed to update DNS A record '%s' after "
                              "zone cache refresh.", fqdn)
                return False
        except Exception:
            LOG.exception("Failed to update DNS A record '%s'.", fqdn)
            return False
