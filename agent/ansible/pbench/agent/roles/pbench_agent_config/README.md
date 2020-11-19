pbench_agent_config
===================

This role installs a pbench-agent.cfg file and an ssh key. The former
defines the server to be used for
pbench-move-results/pbench-copy-results and the latter allows the
communication to happen.

Requirements
------------

Role Variables
--------------
These variables are *NOT* defined by default. They *have* to be
defined in the user's inventory file:

-pbench_config_url: the location where the config file is to be fetched from
-pbench_key_url: the location where the key file is to be fetched from

These are the variables that are defined by default and do not
generally need to be modified:

- pbench_agent_install_dir: the installation directory for the pbench agent (default: /opt/pbench-agent)
- pbench_config_files: the list of config files to be installed (default '["pbench-agent.cfg"]')
- pbench_config_dest: the location where the config file(s) are to be installed (default: {{ pbench_agent_install_dir }}/config)
- pbench_key_dest: the location where the key file is to be installed (default: {{ pbench_agent_install_dir }})


Dependencies
------------
This role depends on another role in this collection:

- pbench_agent_files_install

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
