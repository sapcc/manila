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

from manila import exception
from manila.i18n import _


class Resource(object):

    SHARE = 'SHARE'
    SHARE_GROUP = 'SHARE_GROUP'
    SHARE_REPLICA = 'SHARE_REPLICA'
    SHARE_SNAPSHOT = 'SHARE_SNAPSHOT'
    SECURITY_SERVICE = 'SECURITY_SERVICE'


class Action(object):

    ALLOCATE_HOST = ('001', _('allocate host'))
    CREATE = ('002', _('create'))
    DELETE_ACCESS_RULES = ('003', _('delete access rules'))
    PROMOTE = ('004', _('promote'))
    UPDATE = ('005', _('update'))
    REVERT_TO_SNAPSHOT = ('006', _('revert to snapshot'))
    DELETE = ('007', _('delete'))
    EXTEND = ('008', _('extend'))
    SHRINK = ('009', _('shrink'))
    UPDATE_ACCESS_RULES = ('010', _('update access rules'))
    ADD_UPDATE_SECURITY_SERVICE = ('011', _('add or update security service'))
    ALL = (
        ALLOCATE_HOST,
        CREATE,
        DELETE_ACCESS_RULES,
        PROMOTE,
        UPDATE,
        REVERT_TO_SNAPSHOT,
        DELETE,
        EXTEND,
        SHRINK,
        UPDATE_ACCESS_RULES,
        ADD_UPDATE_SECURITY_SERVICE,
    )


class Detail(object):

    UNKNOWN_ERROR = ('001', _('An unknown error occurred.'))
    NO_VALID_HOST = (
        '002', _("No storage could be allocated for this share request. "
                 "Trying again with a different size or share type may "
                 "succeed."))
    UNEXPECTED_NETWORK = (
        '003', _("Driver does not expect share-network to be provided with "
                 "current configuration."))
    NO_SHARE_SERVER = (
        '004', _("Could not find an existing share server or allocate one on "
                 "the share network provided. You may use a different share "
                 "network, or verify the network details in the share network "
                 "and retry your request. If this doesn't work, contact your "
                 "administrator to troubleshoot issues with your network."))
    NO_ACTIVE_AVAILABLE_REPLICA = (
        '005', _("An 'active' replica must exist in 'available' state to "
                 "create a new replica for share."))
    NO_ACTIVE_REPLICA = (
        '006', _("Share has no replica with 'replica_state' set to 'active'."))

    FILTER_MSG = _("No storage could be allocated for this share request, "
                   "%s filter didn't succeed.")
    FILTER_AVAILABILITY = ('007', FILTER_MSG % 'AvailabilityZone')
    FILTER_CAPABILITIES = ('008', FILTER_MSG % 'Capabilities')
    FILTER_CAPACITY = ('009', FILTER_MSG % 'Capacity')
    FILTER_DRIVER = ('010', FILTER_MSG % 'Driver')
    FILTER_IGNORE = ('011', FILTER_MSG % 'IgnoreAttemptedHosts')
    FILTER_JSON = ('012', FILTER_MSG % 'Json')
    FILTER_RETRY = ('013', FILTER_MSG % 'Retry')
    FILTER_REPLICATION = ('014', FILTER_MSG % 'ShareReplication')
    DRIVER_FAILED_EXTEND = (
        '015',
        _("Share Driver failed to extend share, The share status has been "
          "set to extending_error. This action cannot be re-attempted until "
          "the status has been rectified. Contact your administrator to "
          "determine the cause of this failure."))
    FILTER_CREATE_FROM_SNAPSHOT = ('016', FILTER_MSG % 'CreateFromSnapshot')
    DRIVER_FAILED_CREATING_FROM_SNAP = (
        '017',
        _("Share Driver has failed to create the share from snapshot. This "
          "operation can be re-attempted by creating a new share. Contact "
          "your administrator to determine the cause of this failure."))
    DRIVER_REFUSED_SHRINK = (
        '018',
        _("Share Driver refused to shrink the share. The size to be shrunk is"
          " smaller than the current used space. The share status has been"
          " set to available. Please select a size greater than the current"
          " used space."))
    DRIVER_FAILED_SHRINK = (
        '019',
        _("Share Driver does not support shrinking shares."
          " Shrinking share operation failed."))
    FORBIDDEN_CLIENT_ACCESS = (
        '020',
        _("Failed to grant access to client. The client ID used may be "
          "forbidden. You may try again with a different client identifier."))
    UNSUPPORTED_CLIENT_ACCESS = (
        '021',
        _("Failed to grant access to client. The access level or type may "
          "be unsupported. You may try again with a different access level "
          "or access type."))
    UNSUPPORTED_ADD_UDPATE_SECURITY_SERVICE = (
        '022',
        _("Share driver has failed to setup one or more security services "
          "that are associated with the used share network. The security "
          "service may be unsupported or the provided parameters are invalid. "
          "You may try again with a different set of configurations."))
    SECURITY_SERVICE_FAILED_AUTH = (
        '023',
        _("Share Driver failed to create share due to a security service "
          "authentication issue. The security service user has either "
          "insufficient privileges or wrong credentials. Please check your "
          "user, password, ou and domain."))

    NO_DEFAULT_SHARE_TYPE = (
        '024',
        _("No default share type has been made available. "
          "You must specify a share type for creating shares."))
    MISSING_SECURITY_SERVICE = (
        '025',
        _("Share Driver failed to create share because a security service "
          "has not been added to the share network used. Please add a "
          "security service to the share network."))
    DRIVER_FAILED_DELETE_SHARE_SNAPMIRROR = (
        '026',
        _("Share Driver failed to delete the share. A backup SnapMirror "
          "configuration exist in the backend that has to be removed first in "
          "order to delete the share. Please contact Storage Team via SNOW "
          "ticket."))
    FILTER_AFFINITY = ('027', FILTER_MSG % 'AffinityFilter')
    FILTER_ANTI_AFFINITY = ('028', FILTER_MSG % 'AntiAffinityFilter')
    SHARE_NETWORK_PORT_QUOTA_LIMIT_EXCEEDED = (
        '029',
        _("Share Driver failed to create share server on share network "
          "due to port limit exceeded. You may increase quota of network "
          "ports and retry your request. If this doesn't work, contact your "
          "administrator to troubleshoot issues with your network."))
    NEUTRON_SUBNET_FULL = (
        '030',
        _("Share Driver failed to create share server on share network "
          "due no more free IP addresses in the neutron subnet."
          "You may free some IP addresses in the subnet "
          "or create a new subnet/share network. If this doesn't work, "
          "contact your administrator to troubleshoot "
          "issues with your network."))
    EXTERNAL_SCHEDULER_FILTERED_ALL_HOSTS = (
        '031',
        _("External scheduler API has filtered out all hosts."))
    ALL = (
        UNKNOWN_ERROR,
        NO_VALID_HOST,
        UNEXPECTED_NETWORK,
        NO_SHARE_SERVER,
        NO_ACTIVE_AVAILABLE_REPLICA,
        NO_ACTIVE_REPLICA,
        FILTER_AVAILABILITY,
        FILTER_CAPABILITIES,
        FILTER_CAPACITY,
        FILTER_DRIVER,
        FILTER_IGNORE,
        FILTER_JSON,
        FILTER_RETRY,
        FILTER_REPLICATION,
        DRIVER_FAILED_EXTEND,
        FILTER_CREATE_FROM_SNAPSHOT,
        DRIVER_FAILED_CREATING_FROM_SNAP,
        DRIVER_REFUSED_SHRINK,
        DRIVER_FAILED_SHRINK,
        FORBIDDEN_CLIENT_ACCESS,
        UNSUPPORTED_CLIENT_ACCESS,
        UNSUPPORTED_ADD_UDPATE_SECURITY_SERVICE,
        SECURITY_SERVICE_FAILED_AUTH,
        NO_DEFAULT_SHARE_TYPE,
        MISSING_SECURITY_SERVICE,
        DRIVER_FAILED_DELETE_SHARE_SNAPMIRROR,
        FILTER_AFFINITY,
        FILTER_ANTI_AFFINITY,
        SHARE_NETWORK_PORT_QUOTA_LIMIT_EXCEEDED,
        NEUTRON_SUBNET_FULL,
        EXTERNAL_SCHEDULER_FILTERED_ALL_HOSTS,
    )

    # Exception and detail mappings
    EXCEPTION_DETAIL_MAPPINGS = {
        NO_VALID_HOST: ['NoValidHost'],
    }

    # Use special code for each filter rather then categorize all as
    # NO_VALID_HOST
    FILTER_DETAIL_MAPPINGS = {
        'AvailabilityZoneFilter': FILTER_AVAILABILITY,
        'CapabilitiesFilter': FILTER_CAPABILITIES,
        'CapacityFilter': FILTER_CAPACITY,
        'DriverFilter': FILTER_DRIVER,
        'IgnoreAttemptedHostsFilter': FILTER_IGNORE,
        'JsonFilter': FILTER_JSON,
        'RetryFilter': FILTER_RETRY,
        'ShareReplicationFilter': FILTER_REPLICATION,
        'CreateFromSnapshotFilter': FILTER_CREATE_FROM_SNAPSHOT,
        'AffinityFilter': FILTER_AFFINITY,
        'AntiAffinityFilter': FILTER_ANTI_AFFINITY,
        'call_external_scheduler_api': EXTERNAL_SCHEDULER_FILTERED_ALL_HOSTS,
    }


def translate_action(action_id):
    action_message = next((action[1] for action in Action.ALL
                           if action[0] == action_id), None)
    return action_message or 'unknown action'


def translate_detail(detail_id):
    detail_message = next((action[1] for action in Detail.ALL
                           if action[0] == detail_id), None)
    return detail_message or Detail.UNKNOWN_ERROR[1]


def translate_detail_id(excep, detail):
    if excep is not None:
        detail = _translate_exception_to_detail(excep)
    if detail in Detail.ALL:
        return detail[0]
    return Detail.UNKNOWN_ERROR[0]


def _translate_exception_to_detail(ex):
    if isinstance(ex, exception.NoValidHost):
        # if NoValidHost was raised because a filter failed (a filter
        # didn't return any hosts), use a filter-specific detail
        details = getattr(ex, 'detail_data', {})
        last_filter = details.get('last_filter')
        return Detail.FILTER_DETAIL_MAPPINGS.get(
            last_filter, Detail.NO_VALID_HOST)
    else:
        for key, value in Detail.EXCEPTION_DETAIL_MAPPINGS.items():
            if ex.__class__.__name__ in value:
                return key
