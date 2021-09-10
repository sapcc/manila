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

from oslo_log import log
from oslo_utils import uuidutils

from manila.exception import ManilaException
from manila.exception import NotFound as ManilaNotFound
from manila.exception import PolicyNotAuthorized as ManilaNotAuthorized
from manila.scheduler.filters import base_host
from manila.share import api

LOG = log.getLogger(__name__)


class AffinityBaseFilter(base_host.BaseHostFilter):
    """Base class of affinity filters"""
    _filter_type = None

    def __init__(self):
        self.share_api = api.API()

    def filter_all(self, filter_obj_list, filter_properties):
        # _filter_type should be defined in subclass
        if self._filter_type is None:
            raise AffinityFilterTypeNotSetError

        try:
            filter_properties = self._validate(filter_properties)
        except SchedulerHintsNotSet:
            # AffinityFilter/AntiAffinityFilter is skipped if corresponding
            # hint is not set. If the "scheduler_hints" is not set, both
            # filters are skipped.
            return filter_obj_list
        except (InvalidUUIDError,
                InvalidUUIDListError,
                ShareNotFoundError,
                ShareInstanceNotFoundError) as e:
            # Stop scheduling share when above errors are caught
            LOG.error('%(filter_name)s: %(error)s', {
                'filter_name': self.__class__.__name__,
                'error': e})
            return None
        else:
            # Return list of hosts which pass the function host_passes()
            # overriden in AffinityFilter and AntiAffinityFilter.
            return [obj for obj in filter_obj_list
                    if self._filter_one(obj, filter_properties)]

    def _validate(self, filter_properties):
        context = filter_properties['context']
        hints = filter_properties.get('scheduler_hints')

        if hints is None:
            raise SchedulerHintsNotSet
        else:
            share_uuids = hints.get(self._filter_type)
            if share_uuids is None:
                raise SchedulerHintsNotSet

        # (ccloud): do not allow string, should be list of strings?
        if not isinstance(share_uuids, (tuple, list)):
            share_uuids = share_uuids.split(",")
            #raise InvalidUUIDListError(share_uuids)

        filter_properties['scheduler_hints'][self._filter_type] = []

        for uuid in share_uuids:
            if not uuidutils.is_uuid_like(uuid):
                raise InvalidUUIDError(uuid)
            try:
                # NOTE(ccloud):
                # if we want to allow to specify uuid from another project,
                # we need to change the policy as context.elevated() right now
                # still hard tied to the current project:
                share = self.share_api.get(context, uuid)
            except (ManilaNotFound, ManilaNotAuthorized):
                raise ShareNotFoundError(uuid)
            instances = share.get('instances')
            if len(instances) == 0:
                raise ShareInstanceNotFoundError(uuid)
            filter_properties['scheduler_hints'][self._filter_type].extend(
                [instance.get('host') for instance in instances])

        return filter_properties

    def _get_host_name_from_state(self, host_state_host):
        """Returns the actual host_name from the host_state"""
        host_name = ""
        if host_state_host:
            full_name = host_state_host.split('@')
            if len(full_name) == 2:
                # we can relibly say that first is the hostname
                host_name = full_name[0]
            #TODO: missing error handling here...

        return host_name


class AffinityFilter(AffinityBaseFilter):
    _filter_type = api.AFFINITY_HINT

    def host_passes(self, host_state, filter_properties):
        allowed_hosts = \
            filter_properties['scheduler_hints'][self._filter_type]
        host_name = self._get_host_name_from_state(host_state.host)

        allowed_host_names = set()
        for allowed_host in allowed_hosts:
            allowed_host_name = self._get_host_name_from_state(allowed_host)
            allowed_host_names.add(allowed_host_name)

        if len(allowed_host_names) > 1:
            # The given share uuids are located on different filers.
            # Affinity with both at the same time is not possible.
            return None

        if host_name in allowed_host_names:
            # Valid, pass the host:
            return host_state.host


class AntiAffinityFilter(AffinityBaseFilter):
    _filter_type = api.ANTI_AFFINITY_HINT

    def host_passes(self, host_state, filter_properties):
        forbidden_hosts = \
            filter_properties['scheduler_hints'][self._filter_type]
        host_name = self._get_host_name_from_state(host_state.host)

        for forbidden_host in forbidden_hosts:
            if host_name in self._get_host_name_from_state(forbidden_host):
                # do not pass the host if there is a host_name match:
                return None

        return host_state.host


class SchedulerHintsNotSet(ManilaException):
    pass


class InvalidUUIDError(ManilaException):
    def __init__(self, uuid):
        message = '%s is not a valid uuid' % uuid
        detail_data = {'detail_message': message}
        super(InvalidUUIDError, self).__init__(message, detail_data)


class InvalidUUIDListError(ManilaException):
    def __init__(self, uuid):
        message = '%s is not a valid list of uuid-s' % uuid
        detail_data = {'detail_message': message}
        super(InvalidUUIDListError, self).__init__(message, detail_data)


class ShareNotFoundError(ManilaException):
    def __init__(self, share_uuid):
        message = 'share %s not found' % share_uuid
        detail_data = {'detail_message': message}
        super(ShareNotFoundError, self).__init__(message, detail_data)


class ShareInstanceNotFoundError(ManilaException):
    def __init__(self, share_uuid):
        message = 'share instance not found for share "%s"' % share_uuid
        detail_data = {'detail_message': message}
        super(ShareInstanceNotFoundError, self).__init__(message, detail_data)


class AffinityFilterTypeNotSetError(ManilaException):
    pass
