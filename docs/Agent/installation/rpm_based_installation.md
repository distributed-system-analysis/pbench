# RPM based installation

The Pbench Agent requires the installation of some generic bits, but it also
requires some localization. It needs to know where to send the results for
storage and analysis, and it needs to be able to authenticate to the results
server.

The generic bits are packaged as an RPM, available from
[COPR](https://copr.fedorainfracloud.org/coprs/ndokos).
Pbench Agent is built for all major releases of
Fedora, RHEL, CentOS and openSUSE.

In the following, we describe how to install Pbench Agent using an RPM.

## Setup

1. Enable required repos.

	```console
	dnf copr enable ndokos/pbench-0.72
	dnf copr enable ndokos/pbench
	```

    :::{note}
	- This documentation source describes Pbench Agent 0.72, and [here's](https://copr.fedorainfracloud.org/coprs/ndokos/pbench-0.72) where you find the RPMs.
	- There are some RPMs that are shared between versions (e.g. pbench-sysstat). We maintain those in [ndokos/pbench](https://copr.fedorainfracloud.org/coprs/ndokos/pbench) repo.
    - On a RHEL-based system enable the subscription manager and enable the `EPEL` repo.
	:::

2. Install Pbench Agent package

	```console
	dnf install pbench-agent
	```

3. Restart terminal/shell session so that all environment varibales and PATH variables are updated

	or 

	```console
	source /etc/profile.d/pbench-agent.sh
	```

