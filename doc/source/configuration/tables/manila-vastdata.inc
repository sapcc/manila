..
    Warning: Do not edit this file. It is automatically generated from the
    software project's code and your changes will be overwritten.

    The tool to generate this file lives in openstack-doc-tools repository.

    Please make any changes needed in the code, then run the
    autogenerate-config-doc tool from the openstack-doc-tools repository, or
    ask for help on the documentation mailing list, IRC channel or meeting.

.. _manila-vastdata:

.. list-table:: Description of Vastdata share driver configuration options
   :header-rows: 1
   :class: config-ref-table

   * - Configuration option = Default value
     - Description
   * - **[DEFAULT]**
     -
   * - ``vast_mgmt_host`` =
     - (String) Hostname or IP address VAST storage system management VIP.
   * - ``vast_mgmt_port`` = ``443``
     - (String) Port for VAST management API.
   * - ``vast_vippool_name`` =
     - (String) Name of Virtual IP pool.
   * - ``vast_root_export`` = ``manila``
     - (String) Base path for shares.
   * - ``vast_mgmt_user`` =
     - (String) Username for VAST management API.
   * - ``vast_mgmt_password`` =
     - (String) Password for VAST management API.