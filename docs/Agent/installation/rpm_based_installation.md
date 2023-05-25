# RPM based installation

The pbench agent requires the installation of some generic bits, but it also requires some localization: it needs to know where to send the results for storage and analysis and it needs to be able to authenticate to the results server.

The generic bits are packaged as an RPM, available from [COPR](https://copr.fedorainfracloud.org/coprs/ndokos). We try to build a new release every month or so. Pbench-agent is build for  all major releases of Fedora, RHEL, CentOS and openSUSE.

The localization bits are of course, specific to a particular installation. Internally, we make them available through an ansible playbook. We used to make them available through an internal RPM, but we have deprecated that method: we no longer build internal RPMs. Other installations may use different methods to make them available. Consult your local pbench guru for help.

In the following, we describe how to install pbench-agent using an RPM.

## Setup

1. Pbench-agent rpm is packaged in [COPR](https://copr.fedorainfracloud.org/coprs/ndokos). Choose a release(prefeably the latest) and enable the repo.

	```console
	dnf copr enable ndokos/pbench-0.72
	```

    :::{note}
	- At the time of writing this doc  [pbench-agent-0.72](https://copr.fedorainfracloud.org/coprs/ndokos/pbench-0.72) is the lastest release.
    - On RHEL based system make sure you subscribe to subscription manager & also enable EPEL repo.
    :::

2. Install pbench-agent package

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
