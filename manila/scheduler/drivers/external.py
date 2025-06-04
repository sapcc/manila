# Copyright (c) 2025 SAP SE
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
This module provides functionality to interact with an external scheduler API
to reorder and filter hosts based on additional criteria.

The external scheduler API is expected to take a list of weighed hosts and
their weights, along with the request specification, and return a reordered
and filtered list of host names.
"""
import jsonschema
from oslo_config import cfg
from oslo_log import log as logging
import requests

LOG = logging.getLogger(__name__)

CONF = cfg.CONF
CONF.register_opts([
    cfg.StrOpt(
        "external_scheduler_api_url",
        default="",
        help="""
The API URL of the external scheduler.

If this URL is provided, Manila will call an external service after filters
and weighers have been applied. This service can reorder and filter the
list of hosts before Manila attempts to place the share.

If not provided, this step will be skipped.
"""),
    cfg.IntOpt(
        "external_scheduler_timeout",
        default=10,
        min=1,
        help="""
The timeout in seconds for the external scheduler.

If external_scheduler_api_url is configured, Manila will call and wait for the
external scheduler to respond for this long. If the external scheduler does not
respond within this time, the request will be aborted. In this case, the
scheduler will continue with the original host selection and weights.
""")
])

# The expected response schema from the external scheduler api.
# The response should contain a list of ordered host names.
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "hosts": {
            "type": "array",
            "items": {
                "type": "string"
            }
        }
    },
    "required": ["hosts"],
    "additionalProperties": False,
}


def call_external_scheduler_api(context, weighed_hosts, spec_dict):
    """Reorder and filter hosts using an external scheduler service.

    :param context: The RequestContext object containing request id, user, etc.
    :param weighed_hosts: List of w. hosts to send to the external scheduler.
    :param spec_dict: The RequestSpec object with the vm specification.
    """
    if not weighed_hosts:
        return weighed_hosts
    if not (url := CONF.external_scheduler_api_url):
        LOG.debug("External scheduler API is not enabled.")
        return weighed_hosts
    timeout = CONF.external_scheduler_timeout

    json_data = {
        "spec": spec_dict,
        # Also serialize the request context, which contains the global request
        # id and other information helpful for logging and request tracing.
        "context": context.to_dict(),
        # Only provide basic information for the hosts for now.
        # The external scheduler is expected to fetch statistics
        # about the hosts separately, so we don't need to pass
        # them here.
        "hosts": [
            {
                "host": h.obj.host,
            } for h in weighed_hosts
        ],
        # Also pass previous weights from the Manila weigher pipeline.
        # The external scheduler api is expected to take these weights
        # into account if provided.
        "weights": {h.obj.host: h.weight for h in weighed_hosts},
    }
    LOG.debug("Calling external scheduler API with %s", json_data)
    try:
        response = requests.post(url, json=json_data, timeout=timeout)
        response.raise_for_status()
        # If the JSON parsing fails, this will also raise a RequestException.
        response_json = response.json()
    except requests.RequestException as e:
        LOG.error("Failed to call external scheduler API: %s", e)
        return weighed_hosts

    # The external scheduler api is expected to return a json with
    # a sorted list of host names. Note that no weights are returned.
    try:
        jsonschema.validate(response_json, RESPONSE_SCHEMA)
    except jsonschema.ValidationError as e:
        LOG.error("External scheduler response is invalid: %s", e)
        return weighed_hosts

    # The list of host names can also be empty. In this case, we trust
    # the external scheduler decision and return an empty list.
    if not (host_names := response_json["hosts"]):
        # If this case happens often, it may indicate an issue.
        LOG.warning("External scheduler filtered out all hosts.")

    # Reorder the weighed hosts based on the list of host names returned
    # by the external scheduler api.
    weighed_hosts_dict = {h.obj.host: h for h in weighed_hosts}
    return [weighed_hosts_dict[h] for h in host_names]
