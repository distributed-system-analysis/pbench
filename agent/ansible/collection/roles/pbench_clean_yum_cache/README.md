pbench_clean_yum_cache
==========================

This role is used by pbench_agent_config to make sure that the yum cache is clean. Without it, in some cases, we fail to install the latest version.

Requirements
------------

Role Variables
--------------

Dependencies
------------

Example Playbook
----------------
An example playbook that uses this role can be obtained from

    https://github.com/distributed-system-analysis/pbench/blob/master/agent/ansible/pbench_agent_install.yml

or you can use the raw link to wget/curl the file:

    https://raw.githubusercontent.com/distributed-system-analysis/pbench/master/agent/ansible/pbench_agent_install.yml

License
-------

GPL-3.0-or-later.

Author Information
------------------

The Pbench team.
