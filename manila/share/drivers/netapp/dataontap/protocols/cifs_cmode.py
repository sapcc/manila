# Copyright (c) 2015 Clinton Knight.  All rights reserved.
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
NetApp cDOT CIFS protocol helper class.
"""

import re

from manila.common import constants
from manila import exception
from manila.i18n import _
from manila.share.drivers.netapp.dataontap.protocols import base
from manila.share.drivers.netapp import utils as na_utils


class NetAppCmodeCIFSHelper(base.NetAppBaseHelper):
    """NetApp cDOT CIFS protocol helper class."""

    @na_utils.trace
    def create_share(self, share, share_name,
                     clear_current_export_policy=True,
                     ensure_share_already_exists=False, replica=False,
                     is_flexgroup=False):
        """Creates CIFS share if does not exist on Data ONTAP Vserver.

        The new CIFS share has Everyone access, so it removes all access after
        creating.

        :param share: share entity.
        :param share_name: share name that must be the CIFS share name.
        :param clear_current_export_policy: ignored, NFS only.
        :param ensure_share_already_exists: ensures that CIFS share exists.
        :param replica: it is a replica volume (DP type).
        :param is_flexgroup: whether the share is a FlexGroup or not.
        """

        cifs_exist = self._client.cifs_share_exists(share_name)
        if ensure_share_already_exists and not cifs_exist:
            msg = _("The expected CIFS share %(share_name)s was not found.")
            msg_args = {'share_name': share_name}
            raise exception.NetAppException(msg % msg_args)
        elif not cifs_exist:
            self._client.create_cifs_share(share_name)
            self._client.remove_cifs_share_access(share_name, 'Everyone')

        # Ensure 'ntfs' security style for RW volume. DP volumes cannot set it.
        # Ensure 'ntfs' security style if not a MULTI share protocol
        if not replica and share['share_proto'].lower() != 'multi':
            self._client.set_volume_security_style(share_name,
                                                   security_style='ntfs')

        # Return a callback that may be used for generating export paths
        # for this share.
        return (lambda export_address, share_name=share_name:
                r'\\%s\%s' % (export_address, share_name))

    @na_utils.trace
    def delete_share(self, share, share_name):
        """Deletes CIFS share on Data ONTAP Vserver."""
        host_ip, share_name = self._get_export_location(share)
        self._client.remove_cifs_share(share_name)

    @na_utils.trace
    @base.access_rules_synchronized
    def update_access(self, share, share_name, rules):
        """Replaces the list of access rules known to the backend storage."""

        valid_rules = []
        # Ensure rules are valid
        for rule in rules:
            if share['share_proto'].lower() == 'multi':
                # multi-export share case, filter ip rules:
                if rule['access_type'] == 'ip':
                    continue

            self._validate_access_rule(rule)
            valid_rules.append(rule)

        new_rules = {r['access_to']: r['access_level'] for r in valid_rules}

        # Get rules from share
        existing_rules = self._get_access_rules(share, share_name)

        # Update rules in an order that will prevent transient disruptions
        self._handle_added_rules(share_name, existing_rules, new_rules)
        self._handle_ro_to_rw_rules(share_name, existing_rules, new_rules)
        self._handle_rw_to_ro_rules(share_name, existing_rules, new_rules)
        self._handle_deleted_rules(share_name, existing_rules, new_rules)

    @na_utils.trace
    def _validate_access_rule(self, rule):
        """Checks whether access rule type and level are valid."""

        if rule['access_type'] != 'user':
            msg = _("Clustered Data ONTAP supports only 'user' type for "
                    "share access rules with CIFS protocol.")
            raise exception.InvalidShareAccess(reason=msg)

        if rule['access_level'] not in constants.ACCESS_LEVELS:
            raise exception.InvalidShareAccessLevel(level=rule['access_level'])

    @na_utils.trace
    def _handle_added_rules(self, share_name, existing_rules, new_rules):
        """Updates access rules added between two rule sets."""
        added_rules = {
            user_or_group: permission
            for user_or_group, permission in new_rules.items()
            if user_or_group not in existing_rules
        }

        for user_or_group, permission in added_rules.items():
            self._client.add_cifs_share_access(
                share_name, user_or_group, self._is_readonly(permission))

    @na_utils.trace
    def _handle_ro_to_rw_rules(self, share_name, existing_rules, new_rules):
        """Updates access rules modified (RO-->RW) between two rule sets."""
        modified_rules = {
            user_or_group: permission
            for user_or_group, permission in new_rules.items()
            if (user_or_group in existing_rules and
                permission == constants.ACCESS_LEVEL_RW and
                existing_rules[user_or_group] != 'full_control')
        }

        for user_or_group, permission in modified_rules.items():
            self._client.modify_cifs_share_access(
                share_name, user_or_group, self._is_readonly(permission))

    @na_utils.trace
    def _handle_rw_to_ro_rules(self, share_name, existing_rules, new_rules):
        """Returns access rules modified (RW-->RO) between two rule sets."""
        modified_rules = {
            user_or_group: permission
            for user_or_group, permission in new_rules.items()
            if (user_or_group in existing_rules and
                permission == constants.ACCESS_LEVEL_RO and
                existing_rules[user_or_group] != 'read')
        }

        for user_or_group, permission in modified_rules.items():
            self._client.modify_cifs_share_access(
                share_name, user_or_group, self._is_readonly(permission))

    @na_utils.trace
    def _handle_deleted_rules(self, share_name, existing_rules, new_rules):
        """Returns access rules deleted between two rule sets."""
        deleted_rules = {
            user_or_group: permission
            for user_or_group, permission in existing_rules.items()
            if user_or_group not in new_rules
        }

        for user_or_group, permission in deleted_rules.items():
            self._client.remove_cifs_share_access(share_name, user_or_group)

    @na_utils.trace
    def _get_access_rules(self, share, share_name):
        """Returns the list of access rules known to the backend storage."""
        return self._client.get_cifs_share_access(share_name)

    @na_utils.trace
    def get_target(self, share):
        """Returns OnTap target IP based on share export location."""
        return self._get_export_location(share)[0]

    @na_utils.trace
    def get_share_name_for_share(self, share):
        """Returns the flexvol name that hosts a share."""
        _, share_name = self._get_export_location(share)
        return share_name

    @na_utils.trace
    def _get_export_location(self, share):
        """Returns host ip and share name for a given CIFS share."""
        export_location = self._get_share_export_location(share) or '\\\\\\'
        regex = r'^(?:\\\\|//)(?P<host_ip>.*)(?:\\|/)(?P<share_name>.*)$'
        match = re.match(regex, export_location)
        if match:
            return match.group('host_ip'), match.group('share_name')
        else:
            return '', ''

    @na_utils.trace
    def cleanup_demoted_replica(self, share, share_name):
        """Cleans up CIFS share for a demoted replica."""
        self._client.remove_cifs_share(share_name)
