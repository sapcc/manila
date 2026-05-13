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


import re

from keystoneauth1 import loading as ks_loading
from oslo_config import cfg
from oslo_log import log
from oslo_utils import importutils
from oslo_utils import timeutils

from manila.common import client_auth
from manila import exception
from manila.i18n import _

_designateclient_module = importutils.try_import('designateclient.v2.client')
_designate_exceptions = importutils.try_import('designateclient.exceptions')

LOG = log.getLogger(__name__)

DESIGNATE_GROUP = 'designate'
AUTH_OBJ = None

_ZONE_CACHE_TTL_SECONDS = 300
_RECORD_TYPE = 'A'
_LABEL_RE = re.compile(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$')
_DOMAIN_LABEL_RE = re.compile(r'^[a-z0-9_]([a-z0-9_-]{0,61}[a-z0-9_])?$')

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
    cfg.BoolOpt(
        'all_projects',
        default=True,
        help='Send the X-Auth-All-Projects header so that the service '
             'account can see and modify zones owned by other projects. '
             'Requires the admin role for the service account in Designate. '
             'Set to False when every zone used by Manila shares is owned '
             'by the Manila service project.'),
]

CONF = cfg.CONF
CONF.register_opts(designate_opts, DESIGNATE_GROUP)
ks_loading.register_session_conf_options(CONF, DESIGNATE_GROUP)
ks_loading.register_auth_conf_options(CONF, DESIGNATE_GROUP)


def list_opts():
    return client_auth.AuthClientLoader.list_opts(DESIGNATE_GROUP)


def _get_auth_loader():
    global AUTH_OBJ
    if _designateclient_module is None:
        raise ImportError(
            "python-designateclient is required for Designate integration. "
            "Install it with: pip install python-designateclient")
    if not AUTH_OBJ:
        AUTH_OBJ = client_auth.AuthClientLoader(
            client_class=_designateclient_module.Client,
            cfg_group=DESIGNATE_GROUP)
    return AUTH_OBJ


def designateclient(context):
    """Get an authenticated Designate client using service credentials."""
    loader = _get_auth_loader()
    return loader.get_client(
        context,
        admin=True,
        endpoint_type=CONF[DESIGNATE_GROUP].endpoint_type,
        region_name=CONF[DESIGNATE_GROUP].region_name,
        all_projects=CONF[DESIGNATE_GROUP].all_projects,
    )


def service_project_id():
    """Project ID of the configured Designate service credentials.

    Returns None when it cannot be determined; a None value simply means
    that zones owned by the service project are not treated as shared.
    """
    try:
        loader = _get_auth_loader()
        if not loader.session:
            loader.session = ks_loading.load_session_from_conf_options(
                CONF, DESIGNATE_GROUP)
        if not loader.admin_auth:
            loader.admin_auth = loader._load_auth_plugin()
        return loader.session.get_project_id(auth=loader.admin_auth)
    except Exception:
        LOG.debug("Could not determine the Designate service project id.",
                  exc_info=True)
        return None


def _is_not_found(exc):
    if _designate_exceptions is not None and isinstance(
            exc, _designate_exceptions.NotFound):
        return True
    return getattr(exc, 'code', None) == 404


def _is_conflict(exc):
    if _designate_exceptions is not None and isinstance(
            exc, _designate_exceptions.Conflict):
        return True
    return getattr(exc, 'code', None) == 409


def make_fqdn(dns_name, dns_domain):
    """Return the canonical FQDN with a trailing dot."""
    domain = dns_domain if dns_domain.endswith('.') else dns_domain + '.'
    return '%s.%s' % (dns_name, domain)


def validate_dns_metadata_values(dns_name, dns_domain):
    """Validate a dns_name/dns_domain pair. Returns the normalized pair.

    ``dns_name`` must be a single RFC 1035 label. Both values are
    lower-cased (DNS is case-insensitive) and ``dns_domain`` gets a trailing
    dot appended when absent, so that equal names compare equal.
    """
    if dns_name and not dns_domain:
        raise exception.InvalidInput(
            reason=_("'dns_domain' is required when 'dns_name' is set."))
    if dns_domain and not dns_name:
        raise exception.InvalidInput(
            reason=_("'dns_name' is required when 'dns_domain' is set."))
    if not dns_name:
        return dns_name, dns_domain

    dns_name = str(dns_name).strip().lower()
    dns_domain = str(dns_domain).strip().lower()
    if '.' in dns_name:
        raise exception.InvalidInput(
            reason=_("'dns_name' must be a single DNS label and must "
                     "not contain dots. Got: '%s'.") % dns_name)
    if not _LABEL_RE.match(dns_name):
        raise exception.InvalidInput(
            reason=_("'dns_name' must be a valid RFC 1035 DNS label: "
                     "1-63 characters, alphanumeric and hyphens only, "
                     "not starting or ending with a hyphen. "
                     "Got: '%s'.") % dns_name)
    if not dns_domain.endswith('.'):
        dns_domain = dns_domain + '.'
    labels = dns_domain.rstrip('.').split('.')
    if not labels or not all(_DOMAIN_LABEL_RE.match(label)
                             for label in labels):
        raise exception.InvalidInput(
            reason=_("'dns_domain' must be a valid DNS domain name. "
                     "Got: '%s'.") % dns_domain)
    if len(make_fqdn(dns_name, dns_domain)) > 255:
        raise exception.InvalidInput(
            reason=_("The DNS name '%s' is longer than 255 characters.")
            % make_fqdn(dns_name, dns_domain))
    return dns_name, dns_domain


class API(object):
    """API for managing share DNS recordsets in Designate.

    All methods are no-ops when the integration is disabled.
    """

    def __init__(self):
        self._enabled = CONF[DESIGNATE_GROUP].enabled
        self._client = None
        self._zone_id_cache = {}
        self._service_project_id = None
        self._service_project_resolved = False

    @property
    def enabled(self):
        """Returns True if Designate integration is enabled."""
        return self._enabled

    def _get_client(self, context):
        if self._client is None:
            self._client = designateclient(context)
        return self._client

    def _get_service_project_id(self):
        if not self._service_project_resolved:
            self._service_project_id = service_project_id()
            self._service_project_resolved = True
        return self._service_project_id

    def _invalidate_zone(self, project_id, dns_domain):
        self._zone_id_cache.pop((project_id, dns_domain), None)

    def _get_zone_id(self, client, project_id, dns_domain,
                     force_refresh=False):
        """Find the Designate zone for ``dns_domain`` usable by a project.

        A zone is usable when it is owned by ``project_id`` or by the Manila
        service project. Results are cached for _ZONE_CACHE_TTL_SECONDS.
        """
        cache_key = (project_id, dns_domain)
        if not force_refresh and cache_key in self._zone_id_cache:
            zone_id, cached_at = self._zone_id_cache[cache_key]
            if timeutils.utcnow_ts() - cached_at < _ZONE_CACHE_TTL_SECONDS:
                return zone_id
            del self._zone_id_cache[cache_key]

        name = dns_domain if dns_domain.endswith('.') else dns_domain + '.'
        zones = client.zones.list(criterion={'name': name}) or []
        allowed_owners = {project_id, self._get_service_project_id()}
        allowed_owners.discard(None)
        zone = None
        for candidate in zones:
            owner = candidate.get('project_id')
            if owner is None or owner in allowed_owners:
                zone = candidate
                break
        if zone is None:
            if zones:
                LOG.warning("Designate zone '%s' exists but is not owned by "
                            "project '%s' or the Manila service project; "
                            "refusing to use it.", name, project_id)
            raise exception.DNSZoneNotFound(dns_domain=dns_domain,
                                            project_id=project_id)
        zone_id = zone['id']
        self._zone_id_cache[cache_key] = (zone_id, timeutils.utcnow_ts())
        return zone_id

    def _find_recordset(self, client, zone_id, fqdn):
        recordsets = client.recordsets.list(
            zone_id, criterion={'name': fqdn, 'type': _RECORD_TYPE}) or []
        for rs in recordsets:
            # Designate filters are exact, but be defensive about the name.
            if rs.get('name', fqdn) == fqdn:
                return rs
        return None

    def _get_recordset(self, client, zone_id, recordset_id):
        try:
            return client.recordsets.get(zone_id, recordset_id)
        except Exception as e:
            if _is_not_found(e):
                return None
            raise

    def ensure_record(self, context, project_id, dns_name, dns_domain,
                      ip_addresses, recordset_id=None):
        """Create or update the A recordset for a share. Idempotent.

        :param recordset_id: id of the recordset Manila created earlier, if
            known. It is looked up by id first so that the record owned by
            this share is the one that gets updated.
        :returns: the recordset id, or None when the integration is disabled.
        :raises: DNSZoneNotFound, DNSNameInUse or the Designate client error.
        """
        if not self.enabled:
            return None

        fqdn = make_fqdn(dns_name, dns_domain)
        records = sorted(set(ip_addresses))
        ttl = CONF[DESIGNATE_GROUP].ttl
        client = self._get_client(context)
        zone_id = self._get_zone_id(client, project_id, dns_domain)

        try:
            recordset = None
            if recordset_id:
                recordset = self._get_recordset(client, zone_id, recordset_id)
            if recordset is None:
                recordset = self._find_recordset(client, zone_id, fqdn)

            if recordset is not None:
                current = sorted(recordset.get('records') or [])
                if (current == records and recordset.get('ttl') == ttl
                        and recordset.get('name') == fqdn):
                    LOG.debug("DNS A record '%s' -> %s is up to date "
                              "(recordset %s).", fqdn, records,
                              recordset['id'])
                    return recordset['id']
                values = {'records': records, 'ttl': ttl}
                client.recordsets.update(zone_id, recordset['id'], values)
                LOG.info("Updated DNS A record '%s' -> %s (recordset %s).",
                         fqdn, records, recordset['id'])
                return recordset['id']

            recordset = client.recordsets.create(
                zone_id, fqdn, _RECORD_TYPE, records, ttl=ttl)
            LOG.info("Created DNS A record '%s' -> %s (recordset %s).",
                     fqdn, records, recordset['id'])
            return recordset['id']
        except exception.ManilaException:
            raise
        except Exception as e:
            self._invalidate_zone(project_id, dns_domain)
            if _is_conflict(e):
                raise exception.DNSNameInUse(fqdn=fqdn)
            if _is_not_found(e):
                raise exception.DNSZoneNotFound(dns_domain=dns_domain,
                                                project_id=project_id)
            LOG.exception("Failed to create or update DNS A record "
                          "'%s' -> %s.", fqdn, records)
            raise

    def delete_record(self, context, project_id, dns_name, dns_domain,
                      recordset_id=None):
        """Delete the A recordset for a share.

        Never raises; returns False when the record could not be removed so
        that callers can log and continue.
        """
        if not self.enabled:
            return True

        fqdn = make_fqdn(dns_name, dns_domain)
        try:
            client = self._get_client(context)
            zone_id = self._get_zone_id(client, project_id, dns_domain)
            recordset = None
            if recordset_id:
                recordset = self._get_recordset(client, zone_id, recordset_id)
            if recordset is None:
                recordset = self._find_recordset(client, zone_id, fqdn)
            if recordset is None:
                LOG.info("DNS A record '%s' not found; nothing to delete.",
                         fqdn)
                return True
            try:
                client.recordsets.delete(zone_id, recordset['id'])
            except Exception as e:
                if not _is_not_found(e):
                    raise
            LOG.info("Deleted DNS A record '%s' (recordset %s).",
                     fqdn, recordset['id'])
            return True
        except exception.DNSZoneNotFound:
            LOG.warning("Designate zone for '%s' not found while deleting "
                        "the record; assuming it is already gone.", fqdn)
            return True
        except Exception:
            self._invalidate_zone(project_id, dns_domain)
            LOG.exception("Failed to delete DNS A record '%s'. "
                          "Manual cleanup may be required.", fqdn)
            return False
