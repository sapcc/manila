# Copyright (c) 2012 OpenStack Foundation
# Copyright (c) 2015 Rushil Chugh
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

"""Share-related Utilities and helpers."""

from oslo_config import cfg

from manila.common import constants
from manila.db import migration
from manila import exception
from manila import rpc
from manila import utils

DEFAULT_POOL_NAME = '_pool0'
CONF = cfg.CONF


def extract_host(host, level='backend', use_default_pool_name=False):
    """Extract Host, Backend or Pool information from host string.

    :param host: String for host, which could include host@backend#pool info
    :param level: Indicate which level of information should be extracted
                  from host string. Level can be 'host', 'backend', 'pool',
                  or 'backend_name', default value is 'backend'
    :param use_default_pool_name: This flag specifies what to do
                              if level == 'pool' and there is no 'pool' info
                              encoded in host string.  default_pool_name=True
                              will return DEFAULT_POOL_NAME, otherwise it will
                              return None. Default value of this parameter
                              is False.
    :return: expected level of information

    For example:
        host = 'HostA@BackendB#PoolC'
        ret = extract_host(host, 'host')
        # ret is 'HostA'
        ret = extract_host(host, 'backend')
        # ret is 'HostA@BackendB'
        ret = extract_host(host, 'pool')
        # ret is 'PoolC'
        ret = extract_host(host, 'backend_name')
        # ret is 'BackendB'
        host = 'HostX@BackendY'
        ret = extract_host(host, 'pool')
        # ret is None
        ret = extract_host(host, 'pool', True)
        # ret is '_pool0'
    """
    if level == 'host':
        # Make sure pool is not included
        hst = host.split('#')[0]
        return hst.split('@')[0]
    if level == 'backend_name':
        hst = host.split('#')[0]
        return hst.split('@')[1]
    elif level == 'backend':
        return host.split('#')[0]
    elif level == 'pool':
        lst = host.split('#')
        if len(lst) == 2:
            return lst[1]
        elif use_default_pool_name is True:
            return DEFAULT_POOL_NAME
        else:
            return None


def append_host(host, pool):
    """Encode pool into host info."""
    if not host or not pool:
        return host

    new_host = "#".join([host, pool])
    return new_host


def get_active_replica(replica_list):
    """Returns the first 'active' replica in the list of replicas provided."""
    for replica in replica_list:
        if replica['replica_state'] == constants.REPLICA_STATE_ACTIVE:
            return replica


def change_rules_to_readonly(access_rules, add_rules, delete_rules):
    dict_access_rules = cast_access_object_to_dict_in_readonly(access_rules)
    dict_add_rules = cast_access_object_to_dict_in_readonly(add_rules)
    dict_delete_rules = cast_access_object_to_dict_in_readonly(delete_rules)
    return dict_access_rules, dict_add_rules, dict_delete_rules


def cast_access_object_to_dict_in_readonly(rules):
    dict_rules = []
    for rule in rules:
        dict_rules.append({
            'access_level': constants.ACCESS_LEVEL_RO,
            'access_type': rule['access_type'],
            'access_to': rule['access_to']
        })
    return dict_rules


@utils.if_notifications_enabled
def notify_about_share_usage(context, share, share_instance,
                             event_suffix, extra_usage_info=None, host=None):

    if not host:
        host = CONF.host

    if not extra_usage_info:
        extra_usage_info = {}

    usage_info = _usage_from_share(share, share_instance, **extra_usage_info)

    rpc.get_notifier("share", host).info(context, 'share.%s' % event_suffix,
                                         usage_info)


def _usage_from_share(share_ref, share_instance_ref, **extra_usage_info):

    usage_info = {
        'share_id': share_ref['id'],
        'user_id': share_ref['user_id'],
        'project_id': share_ref['project_id'],
        'snapshot_id': share_ref['snapshot_id'],
        'share_group_id': share_ref['share_group_id'],
        'size': share_ref['size'],
        'name': share_ref['display_name'],
        'description': share_ref['display_description'],
        'proto': share_ref['share_proto'],
        'is_public': share_ref['is_public'],
        'availability_zone': share_instance_ref['availability_zone'],
        'host': share_instance_ref['host'],
        'status': share_instance_ref['status'],
        'share_type_id': share_instance_ref['share_type_id'],
        'share_type': share_instance_ref['share_type']['name'],
    }

    usage_info.update(extra_usage_info)

    return usage_info


def get_recent_db_migration_id():
    return migration.version()


def is_az_subnets_compatible(subnet_list, new_subnet_list):
    if len(subnet_list) != len(new_subnet_list):
        return False

    for subnet in subnet_list:
        found_compatible = False
        for new_subnet in new_subnet_list:
            if (subnet.get('neutron_net_id') ==
                    new_subnet.get('neutron_net_id') and
                    subnet.get('neutron_subnet_id') ==
                    new_subnet.get('neutron_subnet_id')):
                found_compatible = True
                break
        if not found_compatible:
            return False

    return True


def is_active_share_server_replica(server):
    """Return whether the given share server row is an active replica."""

    return (
        not server.get('source_share_server_id') and
        server.get('replica_state') == constants.REPLICA_STATE_ACTIVE
    )


def is_share_server_replica(server):
    """Return whether the given share server row is a replica."""

    return (
        bool(server.get('source_share_server_id')) and
        bool(server.get('replica_state'))
    )


def get_share_server_replicas(context, db, source_share_server_id):
    """Return replica members for a given source share server id."""

    replicas = db.share_server_get_all_with_filters(
        context, {'source_share_server_id': source_share_server_id})
    return [
        server for server in replicas
        if is_share_server_replica(server)
    ]


def get_share_server_availability_zone(context, db, server):
    """Extract availability zone for a share server replica."""

    for subnet in server.get('share_network_subnets') or []:
        az = subnet.get('availability_zone')
        if az:
            return az

    service_host = extract_host(server.get('host') or '')
    if not service_host:
        return None

    try:
        service = db.service_get_by_args(context, service_host, 'manila-share')
    except exception.NotFound:
        return None

    service_az = service.availability_zone
    return service_az.name if service_az else None


def build_share_server_replica_row(context, db, server,
                                   source_share_server_id,
                                   metadata_data=None,
                                   replica_state=None):
    """Build normalized API row for a share server replica."""

    row = dict(server)
    share_network_id = server.get('share_network_id')
    share_network_name = server.get('share_network_name')
    availability_zone = get_share_server_availability_zone(context, db, server)
    row['share_server_id'] = server['id']
    row['source_share_server_id'] = source_share_server_id
    row['share_network_id'] = share_network_id
    row['share_network_name'] = share_network_name
    row['availability_zone'] = availability_zone
    row['replica_state'] = (
        replica_state if replica_state is not None
        else server.get('replica_state')
    )
    if (row.get('replica_state') == constants.REPLICA_STATE_ACTIVE and
            row.get('status') == constants.STATUS_ACTIVE):
        row['status'] = constants.STATUS_AVAILABLE
    row['metadata'] = metadata_data or {}
    return row


def build_share_server_replica_rows(context, db, active_share_server_replica,
                                    all_share_server_replicas):
    """Build API rows for one active source and its replica members."""

    replicas = [build_share_server_replica_row(
        context,
        db,
        active_share_server_replica,
        source_share_server_id=active_share_server_replica['id'],
        metadata_data={},
        replica_state=(active_share_server_replica.get('replica_state') or
                       constants.REPLICA_STATE_ACTIVE),
    )]

    for replica in all_share_server_replicas:
        replicas.append(build_share_server_replica_row(
            context,
            db,
            replica,
            source_share_server_id=replica.get('source_share_server_id'),
            metadata_data=db.share_server_replica_metadata_get(
                context, replica['id']),
        ))

    return replicas


def is_share_server_replication_enabled(context, db, share_server):
    """Check if share server replication is enabled."""

    share_server_replicas = db.share_server_get_all_with_filters(
        context, {'source_share_server_id': share_server['id']})
    return any(r.get('replica_state') for r in share_server_replicas)


def is_share_protected_via_share_server_replica(context, db, share):
    """Return whether a share is protected by share server replication."""

    share_server_id = (
        share.get('instance', {}).get('share_server_id') or
        share.get('share_server_id')
    )

    if not share_server_id:
        instances = share.get('instances') or []
        for instance in instances:
            share_server_id = instance.get('share_server_id')
            if share_server_id:
                break

    if not share_server_id:
        return False

    try:
        share_server = db.share_server_get(context, share_server_id)
    except (exception.ShareServerNotFound, exception.NotFound):
        return False

    return is_share_server_replication_enabled(context, db, share_server)


def build_share_server_replica_payload(replica_server, include_metadata=False,
                                       metadata=None):
    """Build a normalized replica payload for share server replica flows."""
    status = replica_server.get('status')
    if status in (constants.STATUS_INACTIVE, constants.STATUS_ACTIVE):
        status = constants.STATUS_AVAILABLE

    payload = {
        'id': replica_server['id'],
        'status': status,
        'replica_state': replica_server.get('replica_state'),
        'share_server': replica_server,
    }

    if include_metadata:
        payload['metadata'] = metadata or {}

    return payload
