pbench_firewall_open_ports
==========================

This role punches a hole through the firewall for various ports that the tool meister
processes need to use.

Requirements
------------
None.

Role Variables
--------------
These are the variables that are defined by default and do not
generally need to be modified unless there is a conflict:

- pbench_redis_port: 17001
- pbench_wsgi_port: 8443

Dependencies
------------
None

Example Playbook
----------------
An example playbook can be obtained from

    https://github.com/distributed-system-analysis/pbench/blob/master/agent/ansible/pbench_agent_install.yml

or you can use the raw link to wget/curl the file:

    https://raw.githubusercontent.com/distributed-system-analysis/pbench/master/agent/ansible/pbench_agent_install.yml


License
-------
GPL-3.0-or-later.

Author Information
------------------
The Pbench team.
