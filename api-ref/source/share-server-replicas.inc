.. -*- rst -*-

Share server replicas (since API v2.100)
========================================

Share server replicas provide replication and failover controls for
share servers.

Share server replicas are a built-in Manila resource for disaster recovery
at the share server level. Administrators can create, view, update,
promote, resync, and delete replicas by using standard Manila APIs.

Manila manages failover and role changes at the share server layer. You can
choose placement by availability zone and share network, and track both
``status`` and ``replica_state`` during operations.

.. note::

   In this deployment the share server replica APIs are **experimental**.
   Requests must include the ``X-OpenStack-Manila-API-Experimental: true``
   header in addition to ``X-OpenStack-Manila-API-Version: 2.100`` (or
   later).


Administrative actions
~~~~~~~~~~~~~~~~~~~~~~

By default, only administrators can use share server replica APIs.

Use ``policy.yaml`` to grant these permissions to other roles.


Create share server replica
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. rest_method::  POST /v2/share-server-replicas

.. versionadded:: 2.100

Creates a replica from an existing source share server.

You can optionally pass ``availability_zone`` and ``share_network_id`` to
control where Manila places the share server replica. When
``share_network_id`` is omitted, the replica is created on the share
network of its source share server. When ``availability_zone`` is omitted,
it is resolved from the subnets of that share network.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 202

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404
   - 409
   - 422

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_id: share_server_replica_share_server_id
   - availability_zone: share_server_replica_az_request
   - share_network_id: share_server_replica_share_network_id_request
   - metadata: share_server_replica_metadata_request

Request example
---------------

.. literalinclude:: samples/share-server-replica-create-request.json
   :language: javascript

Response parameters
-------------------

.. rest_parameters:: parameters.yaml

   - id: share_server_replica_id
   - source_share_server_id: source_share_server_id
   - host: share_server_replica_host
   - status: share_server_replica_status
   - replica_state: share_server_replica_replica_state
   - availability_zone: share_server_replica_az_response
   - links: links
   - share_network_id: share_server_replica_share_network_id
   - share_network_name: share_network_name
   - created_at: created_at
   - updated_at: updated_at
   - metadata: share_server_replica_metadata_response

Response example
----------------

.. literalinclude:: samples/share-server-replica-create-response.json
   :language: javascript


List share server replicas
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. rest_method::  GET /v2/share-server-replicas

.. versionadded:: 2.100

Returns a list of share server replicas. When ``share_server_id`` is
specified, only the replicas of that share server are returned.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 200

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_id: share_server_id_query

Response parameters
-------------------

.. rest_parameters:: parameters.yaml

   - id: share_server_replica_id
   - source_share_server_id: source_share_server_id
   - host: share_server_replica_host
   - status: share_server_replica_status
   - replica_state: share_server_replica_replica_state
   - availability_zone: share_server_replica_az_response
   - links: links

Response example
----------------

.. literalinclude:: samples/share-server-replicas-list-response.json
   :language: javascript


List share server replicas with details
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. rest_method::  GET /v2/share-server-replicas/detail

.. versionadded:: 2.100

Returns a detailed list of share server replicas. When ``share_server_id``
is specified, only the replicas of that share server are returned.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 200

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_id: share_server_id_query

Response parameters
-------------------

.. rest_parameters:: parameters.yaml

   - id: share_server_replica_id
   - source_share_server_id: source_share_server_id
   - host: share_server_replica_host
   - status: share_server_replica_status
   - replica_state: share_server_replica_replica_state
   - availability_zone: share_server_replica_az_response
   - links: links
   - share_network_id: share_server_replica_share_network_id
   - share_network_name: share_network_name
   - created_at: created_at
   - updated_at: updated_at
   - metadata: share_server_replica_metadata_response

Response example
----------------

.. literalinclude:: samples/share-server-replicas-list-detail-response.json
   :language: javascript


Show share server replica
~~~~~~~~~~~~~~~~~~~~~~~~~

.. rest_method::  GET /v2/share-server-replicas/{share_server_replica_id}

.. versionadded:: 2.100

Returns details for one share server replica.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 200

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path

Response parameters
-------------------

.. rest_parameters:: parameters.yaml

   - id: share_server_replica_id
   - source_share_server_id: source_share_server_id
   - host: share_server_replica_host
   - status: share_server_replica_status
   - replica_state: share_server_replica_replica_state
   - availability_zone: share_server_replica_az_response
   - links: links
   - share_network_id: share_server_replica_share_network_id
   - share_network_name: share_network_name
   - created_at: created_at
   - updated_at: updated_at
   - metadata: share_server_replica_metadata_response

Response example
----------------

.. literalinclude:: samples/share-server-replica-show-response.json
   :language: javascript


Delete share server replica
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. rest_method::  DELETE /v2/share-server-replicas/{share_server_replica_id}

.. versionadded:: 2.100

Deletes a share server replica.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 202

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path


Force delete share server replica
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. rest_method::  POST /v2/share-server-replicas/{share_server_replica_id}/action

.. versionadded:: 2.100

Force-deletes a share server replica.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 202

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path

Request example
---------------

.. literalinclude:: samples/share-server-replica-force-delete-request.json
   :language: javascript


Promote share server replica
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. rest_method::  POST /v2/share-server-replicas/{share_server_replica_id}/action

.. versionadded:: 2.100

Promotes a share server replica to active.
If the target replica is already ``active``, this API returns HTTP 200 and no
state transition is performed.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 200
   - 202

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path

Request example
---------------

.. literalinclude:: samples/share-server-replica-promote-request.json
   :language: javascript


Resync share server replica
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. rest_method::  POST /v2/share-server-replicas/{share_server_replica_id}/action

.. versionadded:: 2.100

Resyncs a share server replica with the active replica.
If the target replica is already ``active``, this API returns HTTP 200 and no
resync operation is performed.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 200
   - 202

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path

Request example
---------------

.. literalinclude:: samples/share-server-replica-resync-request.json
   :language: javascript


Reset status of the share server replica
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. rest_method::  POST /v2/share-server-replicas/{share_server_replica_id}/action

.. versionadded:: 2.100

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 202

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path
   - reset_status: reset_status
   - status: share_server_replica_status

Request example
---------------

.. literalinclude:: samples/share-server-replica-reset-status-request.json
   :language: javascript


Reset share server replica state
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. rest_method::  POST /v2/share-server-replicas/{share_server_replica_id}/action

.. versionadded:: 2.100

Resets ``replica_state`` for a share server replica.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 202

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path
   - reset_replica_state: share_server_replica_reset_replica_state

Request example
---------------

.. literalinclude:: samples/share-server-replica-reset-replica-state-request.json
   :language: javascript


Share server replica metadata
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Show all share server replica metadata
---------------------------------------

.. rest_method::  GET /v2/share-server-replicas/{share_server_replica_id}/metadata

.. versionadded:: 2.100

Returns all metadata key/value pairs for the replica.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 200

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path

Response parameters
-------------------

.. rest_parameters:: parameters.yaml

   - metadata: metadata

Response example
----------------

.. literalinclude:: samples/share-server-replica-show-metadata-response.json
   :language: javascript


Show share server replica metadata item
----------------------------------------

.. rest_method::  GET /v2/share-server-replicas/{share_server_replica_id}/metadata/{key}

.. versionadded:: 2.100

Returns one metadata item by key.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 200

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path
   - key: metadata_key_path

Response parameters
-------------------

.. rest_parameters:: parameters.yaml

   - meta: metadata_item

Response example
----------------

.. literalinclude:: samples/share-server-replica-show-metadata-item-response.json
   :language: javascript


Set share server replica metadata
---------------------------------

.. rest_method::  POST /v2/share-server-replicas/{share_server_replica_id}/metadata

.. versionadded:: 2.100

Adds metadata items. If a key already exists, its value is updated.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 200

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path
   - metadata: metadata_request

Request example
---------------

.. literalinclude:: samples/share-server-replica-set-metadata-request.json
   :language: javascript

Response parameters
-------------------

.. rest_parameters:: parameters.yaml

   - metadata: metadata

Response example
----------------

.. literalinclude:: samples/share-server-replica-set-metadata-response.json
   :language: javascript


Update share server replica metadata
------------------------------------

.. rest_method::  PUT /v2/share-server-replicas/{share_server_replica_id}/metadata

.. versionadded:: 2.100

Replaces all existing metadata with the metadata in the request body.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 200

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path
   - metadata: metadata_request

Request example
---------------

.. literalinclude:: samples/share-server-replica-update-metadata-request.json
   :language: javascript

Response parameters
-------------------

.. rest_parameters:: parameters.yaml

   - metadata: metadata

Response example
----------------

.. literalinclude:: samples/share-server-replica-update-metadata-response.json
   :language: javascript

To delete all existing metadata items on a share server replica,
the request object needs to specify an empty metadata object:

Request example
---------------

.. literalinclude:: samples/share-server-replica-update-null-metadata-request.json
   :language: javascript

Response example
----------------

.. literalinclude:: samples/share-server-replica-update-null-metadata-response.json
   :language: javascript


Delete share server replica metadata item
------------------------------------------

.. rest_method::  DELETE /v2/share-server-replicas/{share_server_replica_id}/metadata/{key}

.. versionadded:: 2.100

Deletes one metadata item by key.

Response codes
--------------

.. rest_status_code:: success status.yaml

   - 200

.. rest_status_code:: error status.yaml

   - 400
   - 401
   - 403
   - 404

Request
-------

.. rest_parameters:: parameters.yaml

   - project_id: project_id_path
   - share_server_replica_id: share_server_replica_id_path
   - key: metadata_key_path
