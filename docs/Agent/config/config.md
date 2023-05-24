###Configuration

**Note**: This Documentation is only required for administrative purposes.
 &ensp;&ensp;&ensp;&ensp;&ensp;&ensp;By Default the collected results are moved to pbench-server


####Configure with Server < 1.0

For the purpose of defining the required configuration, a pbench-agent configuration file must be created. The config file and the ssh key file must be present in the specified place for the ansible roles to function.

The installation includes a sample configuration file at '/opt/pbench-agent/config/pbench-agent.cfg'. Make a backup of this file, then update the lines marked with # CHANGE ME! comments to suit your setup. Please make sure to make this file accessible to users.

The ssh key pair can be generated with:

	ssh-keygen -t rsa

with an empty passphrase. The private key must be made available to users before they can complete the installation of pbench-agent as stated above. The authorized_keys list should include the public key.


####Configure with Server-1.0

For the purpose of defining the required configuration, a pbench-agent configuration file must be created. The pbench-agent installation contains an example configuration file at '/opt/pbench-agent/config/pbench-agent.cfg'. Make a backup copy of this file, update the lines marked with # CHANGE ME! comments to suit your configuration. Please make sure to make this file accessible to users.
