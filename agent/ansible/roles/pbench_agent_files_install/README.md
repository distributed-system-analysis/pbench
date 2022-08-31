pbench_agent_files_install
==========================

This role is used by pbench_agent_config to install a pbench-agent.cfg
file and an ssh key. pbench_agent_config sets the "source" and "files"
parameters to the URL of the containing directory and the list of
files to copy resp. and calls this role as a subroutine. This role
copies the files to local storage. We do it that way so that we can
copy the files to systems outside a firewall that do not have access
to the provided URLs.

Requirements
------------

Role Variables
--------------

- source: the URL of the directory containing the files to copy
- files: the list of files to copy


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
