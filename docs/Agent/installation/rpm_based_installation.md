# RPM based installation

The Pbench Agent requires the installation of some generic bits, but it also
requires some localization. It needs to know where to send the results for
storage and analysis and it needs to be able to authenticate to the results
server.

The generic bits are packaged as an RPM, available from
[COPR](https://copr.fedorainfracloud.org/coprs/ndokos).
Pbench Agent is build for all major releases of
Fedora, RHEL, CentOS and openSUSE.

In the following, we describe how to install Pbench Agent using an RPM.

## Setup

1. Pbench Agent rpm is packaged in [COPR](https://copr.fedorainfracloud.org/coprs/ndokos). Choose a release(prefeably the latest) and enable the repo.

	```console
	dnf copr enable ndokos/pbench-0.72
	```

    :::{note}
	- This documentation source describes Pbench Agent 0.72, and here's where you find the RPMs [COPR](https://copr.fedorainfracloud.org/coprs/ndokos/pbench-0.72).
    - On RHEL based system enable subscription manager & also enable EPEL repo.
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

:::{important}
Make sure you run all your `pbench` commands as a root user.
:::
