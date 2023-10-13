# Copyright (C) 2022 China Telecom Digital Intelligence.
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

"""
Handles all requests relating to transferring ownership of shares.
"""


import hashlib
import hmac
import os

from oslo_config import cfg
from oslo_log import log as logging
from oslo_utils import excutils
from oslo_utils import strutils

from manila.common import constants
from manila.db import base
from manila import exception
from manila.i18n import _
from manila import policy
from manila import quota
from manila.share import api as share_api
from manila.share import share_types
from manila.share import utils as share_utils


share_transfer_opts = [
    cfg.IntOpt('share_transfer_salt_length',
               default=8,
               help='The number of characters in the salt.',
               min=8,
               max=255),
    cfg.IntOpt('share_transfer_key_length',
               default=16,
               help='The number of characters in the autogenerated auth key.',
               min=16,
               max=255),
]

CONF = cfg.CONF
CONF.register_opts(share_transfer_opts)

LOG = logging.getLogger(__name__)
QUOTAS = quota.QUOTAS


class API(base.Base):
    """API for interacting share transfers."""

    def __init__(self):
        self.share_api = share_api.API()
        super().__init__()

    def get(self, context, transfer_id):
        transfer = self.db.transfer_get(context, transfer_id)
        return transfer

    def delete(self, context, transfer_id):
        """Delete a share transfer."""
        transfer = self.db.transfer_get(context, transfer_id)
        policy.check_policy(context, 'share_transfer', 'delete', target_obj={
            'project_id': transfer['source_project_id']})
        update_share_status = True
        share_ref = None
        try:
            share_ref = self.db.share_get(context, transfer.resource_id)
        except exception.NotFound:
            update_share_status = False
        if update_share_status:
            share_instance = share_ref['instance']
        if share_ref['status'] != constants.STATUS_AWAITING_TRANSFER:
            msg = (_('Transfer %(transfer_id)s: share id %(share_id)s '
                     'expected in awaiting_transfer state.'))
            msg_payload = {'transfer_id': transfer_id,
                           'share_id': share_ref['id']}
            LOG.error(msg, msg_payload)
            raise exception.InvalidShare(reason=msg)
        if update_share_status:
            share_utils.notify_about_share_usage(context, share_ref,
                                                 share_instance,
                                                 "transfer.delete.start")
        self.db.transfer_destroy(context, transfer_id,
                                 update_share_status=update_share_status)
        if update_share_status:
            share_utils.notify_about_share_usage(context, share_ref,
                                                 share_instance,
                                                 "transfer.delete.end")
        LOG.info('Transfer %s has been deleted successful.', transfer_id)

    def get_all(self, context, limit=None, sort_key=None,
                sort_dir=None, filters=None, offset=None):
        filters = filters or {}
        all_tenants = strutils.bool_from_string(filters.pop('all_tenants',
                                                            'false'))
        query_by_project = False

        if all_tenants:
            try:
                policy.check_policy(context, 'share_transfer',
                                    'get_all_tenant')
            except exception.PolicyNotAuthorized:
                query_by_project = True
        else:
            query_by_project = True

        if query_by_project:
            transfers = self.db.transfer_get_all_by_project(
                context, context.project_id,
                limit=limit, sort_key=sort_key, sort_dir=sort_dir,
                filters=filters, offset=offset)
        else:
            transfers = self.db.transfer_get_all(context,
                                                 limit=limit,
                                                 sort_key=sort_key,
                                                 sort_dir=sort_dir,
                                                 filters=filters,
                                                 offset=offset)

        return transfers

    def _get_random_string(self, length):
        """Get a random hex string of the specified length."""
        rndstr = ""

        # Note that the string returned by this function must contain only
        # characters that the recipient can enter on their keyboard. The
        # function sha256().hexdigit() achieves this by generating a hash
        # which will only contain hexadecimal digits.
        while len(rndstr) < length:
            rndstr += hashlib.sha256(os.urandom(255)).hexdigest()

        return rndstr[0:length]

    def _get_crypt_hash(self, salt, auth_key):
        """Generate a random hash based on the salt and the auth key."""
        def _format_str(input_str):
            if not isinstance(input_str, (bytes, str)):
                input_str = str(input_str)
            if isinstance(input_str, str):
                input_str = input_str.encode('utf-8')
            return input_str
        salt = _format_str(salt)
        auth_key = _format_str(auth_key)
        return hmac.new(salt, auth_key, hashlib.sha256).hexdigest()

    def create(self, context, share_id, display_name):
        """Creates an entry in the transfers table."""
        LOG.debug("Generating transfer record for share %s", share_id)
        try:
            share_ref = self.share_api.get(context, share_id)
        except exception.NotFound:
            msg = _("Share specified was not found.")
            raise exception.InvalidShare(reason=msg)
        policy.check_policy(context, "share_transfer", "create",
                            target_obj=share_ref)
        share_instance = share_ref['instance']
        if share_ref['status'] != "available":
            raise exception.InvalidShare(reason=_("Share's status must be "
                                                  "available"))
        if share_ref['share_network_id']:
            raise exception.InvalidShare(reason=_(
                "Shares exported over share networks cannot be transferred."))
        if share_ref['share_group_id']:
            raise exception.InvalidShare(reason=_(
                "Shares within share groups cannot be transferred."))

        if share_ref.has_replicas:
            raise exception.InvalidShare(reason=_(
                "Shares with replicas cannot be transferred."))

        snapshots = self.db.share_snapshot_get_all_for_share(context, share_id)
        for snapshot in snapshots:
            if snapshot['status'] != "available":
                msg = _("Snapshot: %s status must be "
                        "available") % snapshot['id']
                raise exception.InvalidSnapshot(reason=msg)

        share_utils.notify_about_share_usage(context, share_ref,
                                             share_instance,
                                             "transfer.create.start")
        # The salt is just a short random string.
        salt = self._get_random_string(CONF.share_transfer_salt_length)
        auth_key = self._get_random_string(CONF.share_transfer_key_length)
        crypt_hash = self._get_crypt_hash(salt, auth_key)

        transfer_rec = {'resource_type': constants.SHARE_RESOURCE_TYPE,
                        'resource_id': share_id,
                        'display_name': display_name,
                        'salt': salt,
                        'crypt_hash': crypt_hash,
                        'expires_at': None,
                        'source_project_id': share_ref['project_id']}

        try:
            transfer = self.db.transfer_create(context, transfer_rec)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.error("Failed to create transfer record for %s", share_id)
        share_utils.notify_about_share_usage(context, share_ref,
                                             share_instance,
                                             "transfer.create.end")
        return {'id': transfer['id'],
                'resource_type': transfer['resource_type'],
                'resource_id': transfer['resource_id'],
                'display_name': transfer['display_name'],
                'auth_key': auth_key,
                'created_at': transfer['created_at'],
                'source_project_id': transfer['source_project_id'],
                'destination_project_id': transfer['destination_project_id'],
                'accepted': transfer['accepted'],
                'expires_at': transfer['expires_at']}

    def _handle_snapshot_quota(self, context, snapshots, donor_id):
        snapshots_num = len(snapshots)
        share_snap_sizes = 0
        for snapshot in snapshots:
            share_snap_sizes += snapshot['size']
        try:
            reserve_opts = {'snapshots': snapshots_num,
                            'gigabytes': share_snap_sizes}
            reservations = QUOTAS.reserve(context, **reserve_opts)
        except exception.OverQuota as e:
            reservations = None
            overs = e.kwargs['overs']
            usages = e.kwargs['usages']
            quotas = e.kwargs['quotas']

            def _consumed(name):
                return (usages[name]['reserved'] + usages[name]['in_use'])

            if 'snapshot_gigabytes' in overs:
                msg = ("Quota exceeded for %(s_pid)s, tried to accept "
                       "%(s_size)sG snapshot (%(d_consumed)dG of "
                       "%(d_quota)dG already consumed).")
                LOG.warning(msg, {
                    's_pid': context.project_id,
                    's_size': share_snap_sizes,
                    'd_consumed': _consumed('snapshot_gigabytes'),
                    'd_quota': quotas['snapshot_gigabytes']})
                raise exception.SnapshotSizeExceedsAvailableQuota()
            elif 'snapshots' in overs:
                msg = ("Quota exceeded for %(s_pid)s, tried to accept "
                       "%(s_num)s snapshot (%(d_consumed)d of "
                       "%(d_quota)d already consumed).")
                LOG.warning(msg, {'s_pid': context.project_id,
                                  's_num': snapshots_num,
                                  'd_consumed': _consumed('snapshots'),
                                  'd_quota': quotas['snapshots']})
                raise exception.SnapshotLimitExceeded(
                    allowed=quotas['snapshots'])

        try:
            reserve_opts = {'snapshots': -snapshots_num,
                            'gigabytes': -share_snap_sizes}
            donor_reservations = QUOTAS.reserve(context,
                                                project_id=donor_id,
                                                **reserve_opts)
        except exception.OverQuota:
            donor_reservations = None
            LOG.exception("Failed to update share providing snapshots quota:"
                          " Over quota.")

        return reservations, donor_reservations

    @staticmethod
    def _check_share_type_access(context, share_type_id, share_id):
        share_type = share_types.get_share_type(
            context, share_type_id, expected_fields=['projects'])
        if not share_type['is_public']:
            if context.project_id not in share_type['projects']:
                msg = _("Share type of share %(share_id)s is not public, "
                        "and current project can not access the share "
                        "type ") % {'share_id': share_id}
                LOG.error(msg)
                raise exception.InvalidShare(reason=msg)

    def _check_transferred_project_quota(self, context, share_ref_size):
        try:
            reserve_opts = {'shares': 1, 'gigabytes': share_ref_size}
            reservations = QUOTAS.reserve(context,
                                          **reserve_opts)
        except exception.OverQuota as exc:
            reservations = None
            self.share_api.check_if_share_quotas_exceeded(context, exc,
                                                          share_ref_size)
        return reservations

    @staticmethod
    def _check_donor_project_quota(context, donor_id, share_ref_size,
                                   transfer_id):
        try:
            reserve_opts = {'shares': -1, 'gigabytes': -share_ref_size}
            donor_reservations = QUOTAS.reserve(context.elevated(),
                                                project_id=donor_id,
                                                **reserve_opts)
        except Exception:
            donor_reservations = None
            LOG.exception("Failed to update quota donating share"
                          " transfer id %s", transfer_id)
        return donor_reservations

    @staticmethod
    def _check_snapshot_status(snapshots, transfer_id):
        for snapshot in snapshots:
            # Only check snapshot with instances
            if snapshot.get('status'):
                if snapshot['status'] != 'available':
                    msg = (_('Transfer %(transfer_id)s: Snapshot '
                             '%(snapshot_id)s is not in the expected '
                             'available state.')
                           % {'transfer_id': transfer_id,
                              'snapshot_id': snapshot['id']})
                    LOG.error(msg)
                    raise exception.InvalidSnapshot(reason=msg)

    def accept(self, context, transfer_id, auth_key, clear_rules=False):
        """Accept a share that has been offered for transfer."""
        # We must use an elevated context to make sure we can find the
        # transfer.
        transfer = self.db.transfer_get(context.elevated(), transfer_id)

        crypt_hash = self._get_crypt_hash(transfer['salt'], auth_key)
        if crypt_hash != transfer['crypt_hash']:
            msg = (_("Attempt to transfer %s with invalid auth key.") %
                   transfer_id)
            LOG.error(msg)
            raise exception.InvalidAuthKey(reason=msg)

        share_id = transfer['resource_id']
        try:
            # We must use an elevated context to see the share that is still
            # owned by the donor.
            share_ref = self.share_api.get(context.elevated(), share_id)
        except exception.NotFound:
            msg = _("Share specified was not found.")
            raise exception.InvalidShare(reason=msg)
        share_instance = share_ref['instance']
        if share_ref['status'] != constants.STATUS_AWAITING_TRANSFER:
            msg = (_('Transfer %(transfer_id)s: share id %(share_id)s '
                     'expected in awaiting_transfer state.')
                   % {'transfer_id': transfer_id, 'share_id': share_id})
            LOG.error(msg)
            raise exception.InvalidShare(reason=msg)
        share_ref_size = share_ref['size']
        share_type_id = share_ref.get('share_type_id')
        # check share type access
        if share_type_id:
            self._check_share_type_access(context, share_type_id, share_id)

        # check per share quota limit
        self.share_api.check_is_share_size_within_per_share_quota_limit(
            context, share_ref_size)

        # check accept transferred project quotas
        reservations = self._check_transferred_project_quota(
            context, share_ref_size)

        # check donor project quotas
        donor_id = share_ref['project_id']
        donor_reservations = self._check_donor_project_quota(
            context, donor_id, share_ref_size, transfer_id)

        snap_res = None
        snap_donor_res = None
        accept_snapshots = False
        snapshots = self.db.share_snapshot_get_all_for_share(
            context.elevated(), share_id)
        if snapshots:
            self._check_snapshot_status(snapshots, transfer_id)
            accept_snapshots = True
            snap_res, snap_donor_res = self._handle_snapshot_quota(
                context, snapshots, share_ref['project_id'])

        share_utils.notify_about_share_usage(context, share_ref,
                                             share_instance,
                                             "transfer.accept.start")
        try:
            self.share_api.transfer_accept(context,
                                           share_ref,
                                           context.user_id,
                                           context.project_id,
                                           clear_rules=clear_rules)
            # Transfer ownership of the share now, must use an elevated
            # context.
            self.db.transfer_accept(context.elevated(),
                                    transfer_id,
                                    context.user_id,
                                    context.project_id,
                                    accept_snapshots=accept_snapshots)
            if reservations:
                QUOTAS.commit(context, reservations)
            if snap_res:
                QUOTAS.commit(context, snap_res)
            if donor_reservations:
                QUOTAS.commit(context, donor_reservations, project_id=donor_id)
            if snap_donor_res:
                QUOTAS.commit(context, snap_donor_res, project_id=donor_id)
            LOG.info("share %s has been transferred.", share_id)
        except Exception:
            with excutils.save_and_reraise_exception():
                try:
                    # storage try to rollback
                    self.share_api.transfer_accept(context,
                                                   share_ref,
                                                   share_ref['user_id'],
                                                   share_ref['project_id'])
                    # db try to rollback
                    self.db.transfer_accept_rollback(
                        context.elevated(), transfer_id,
                        share_ref['user_id'], share_ref['project_id'],
                        rollback_snap=accept_snapshots)
                finally:
                    if reservations:
                        QUOTAS.rollback(context, reservations)
                    if snap_res:
                        QUOTAS.rollback(context, snap_res)
                    if donor_reservations:
                        QUOTAS.rollback(context, donor_reservations,
                                        project_id=donor_id)
                    if snap_donor_res:
                        QUOTAS.rollback(context, snap_donor_res,
                                        project_id=donor_id)

        share_utils.notify_about_share_usage(context, share_ref,
                                             share_instance,
                                             "transfer.accept.end")