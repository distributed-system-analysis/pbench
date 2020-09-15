Name:           pbench-server
Version:        
%define gdist   none
Release:        1
Summary:        The pbench server bits

License:        GPLv3+
URL:            http://github.com/distributed-systems-analysis/pbench
Source0:        pbench-server-%{version}.tar.gz
Buildarch:      noarch

# policycoreutils for semanage and restorecon - used in pbench-server-activate-create-results-dir
Requires:       policycoreutils

%if 0%{?fedora}
BuildRequires:  python3 python3-setuptools
Requires:  policycoreutils-python-utils
%endif

%if 0%{?rhel} == 7
# need python3 - install scl to get it
# scl-utils is in the main repo, but the scl python3
# collection du jour is in the scl repo which
# is assumed to have been added already with:
#    yum install yum-utils
#    yum-config-manager --enable rhel-server-rhscl-7-rpms
#
# we can't do that in the spec file, because of the yum lock,
# so they have to be done beforehand.
BuildRequires: scl-utils, rh-python36
Requires: scl-utils, rh-python36, policycoreutils-python
%endif

%if 0%{?rhel} == 8
BuildRequires:  python3 python3-setuptools
Requires:  policycoreutils-python-utils
%endif

Requires: npm

# installdir has to agree with the definition of install-dir in
# pbench-server.cfg, but we can't go out and pluck it from there,
# because we don't know where the config file is. Note that we omit
# the initial / - it is added in every use below.  IMO, that's more
# readable since it appears in the middle of the path in all cases,
# *except* in the %files section (and one instance in the %post
# and %postun sections).

%define installdir opt/pbench-server
%define static html/static

%if 0%{?fedora} == 31
%define __python python3
%define pyversion python3.7
%endif

%if 0%{?fedora} == 32
%define __python python3
%define pyversion python3.8
%endif

%if 0%{?rhel}
%define __python python3
%endif

%if 0%{?rhel} == 7
%define __python scl enable rh-python36 -- python3
%define pyversion python3.6
%endif

# FIXME: this needs checking
%if 0%{?rhel} == 8
%define __python python3
%define pyversion python3.6
%endif

%description
The pbench server scripts.

%prep

%setup

%build

%install
rm -rf %{buildroot}

mkdir -p %{buildroot}/%{installdir}

(cd ./server; %{__python} setup.py install --prefix=%{buildroot}/%{installdir};
              %{__make} install DESTDIR=%{?buildroot}/%{installdir} INSTALL="%{__install} -p";
              %{__make} install-extra DESTDIR=%{?buildroot}/%{installdir} INSTALL="%{__install} -p")

(cd ./web-server;
 %{__make} clone DESTDIR=%{?buildroot}/%{installdir}/%{static} INSTALL="%{__install} -p")

cp -a %{?buildroot}/%{installdir}/%{static}/package.json %{?buildroot}/%{installdir}

# clean up unneeded files
cd %{buildroot}/%{installdir}
rm -rf Makefile %{static}/Makefile \
   lib/pbench.egg-info \
   lib/%{pyversion}/site-packages/* \
   lib/pbench/common/__pycache__ \
   lib/pbench/cli/__pycache__ \
   lib/pbench/cli/agent \
   lib/pbench/server/__pycache__

%post

chown -R pbench.pbench /%{installdir}

cd /%{installdir}

# Install python dependencies

# on RHEL7 we use scl to get python3
%if 0%{?rhel} == 7
echo "scl enable rh-python36 -- python3 -m pip install -r requirements.txt"
scl enable rh-python36 -- python3 -m pip install -r requirements.txt
%endif

%if 0%{?rhel} == 8
echo "python3 -m pip install -r requirements.txt"
python3 -m pip install -r requirements.txt
%endif

%if 0%{?fedora}
echo "python3 -m pip install -r requirements.txt"
python3 -m pip install -r requirements.txt
%endif

# install the js bits
cd /%{installdir}
rm -rf node_modules

# install node.js modules under /%{installdir}
npm install

%preun

%postun
# if uninstalling, rather than updating, remove everything
if [ $1 -eq 0 ] ;then
    crontab=/%{installdir}/lib/crontab/crontab
    if [ -f $crontab ] ;then
        crontab -u pbench -r
    fi
    rm -rf /%{installdir}
fi

%posttrans

%files
%defattr(644, pbench, pbench, 755)
/%{installdir}/VERSION
/%{installdir}/SEQNO
/%{installdir}/SHA1
/%{installdir}/%{static}/VERSION
/%{installdir}/%{static}/package.json
/%{installdir}/package.json
/%{installdir}/requirements.txt
/%{installdir}/setup.cfg
/%{installdir}/setup.py

/%{installdir}/lib/config/pbench-server-satellite.cfg.example
/%{installdir}/lib/config/pbench-server.cfg.example
/%{installdir}/lib/config/pbench-server-default.cfg

/%{installdir}/lib/crontab
/%{installdir}/lib/mappings
/%{installdir}/lib/settings

/%{installdir}/lib/pbench/common/configtools.py
/%{installdir}/lib/pbench/common/__init__.py
/%{installdir}/lib/pbench/common/conf.py
/%{installdir}/lib/pbench/common/constants.py
/%{installdir}/lib/pbench/common/exceptions.py
/%{installdir}/lib/pbench/common/logger.py
/%{installdir}/lib/pbench/__init__.py
/%{installdir}/lib/pbench/server/__init__.py
/%{installdir}/lib/pbench/server/indexer.py
/%{installdir}/lib/pbench/server/report.py
/%{installdir}/lib/pbench/server/mock.py
/%{installdir}/lib/pbench/server/utils.py
/%{installdir}/lib/pbench/server/api/__init__.py
/%{installdir}/lib/pbench/server/s3backup/__init__.py
/%{installdir}/lib/pbench/cli/__init__.py
/%{installdir}/lib/pbench/cli/getconf.py
/%{installdir}/lib/pbench/cli/server/shell.py

/%{installdir}/bin/pbench-base.sh

%defattr(755, pbench, pbench, 755)
/%{installdir}/bin/pbench-config
/%{installdir}/bin/pbench-server
/%{installdir}/bin/pbench-server-activate-create-crontab
/%{installdir}/bin/pbench-server-prep-shim-002
/%{installdir}/bin/pbench-audit-server
/%{installdir}/bin/pbench-backup-tarballs
/%{installdir}/bin/pbench-verify-backup-tarballs
/%{installdir}/bin/pbench-clean-up-dangling-results-links
/%{installdir}/bin/pbench-copy-sosreports
/%{installdir}/bin/pbench-index
/%{installdir}/bin/pbench-reindex
/%{installdir}/bin/pbench-unpack-tarballs
/%{installdir}/bin/pbench-satellite-cleanup
/%{installdir}/bin/pbench-satellite-state-change
/%{installdir}/bin/pbench-remote-satellite-state-change
/%{installdir}/bin/pbench-remote-sync-package-tarballs
/%{installdir}/bin/pbench-dispatch
/%{installdir}/bin/pbench-report-status
/%{installdir}/bin/pbench-pp-status
/%{installdir}/bin/pbench-sync-package-tarballs
/%{installdir}/bin/pbench-sync-satellite
/%{installdir}/bin/pbench-server-set-result-state
/%{installdir}/bin/pbench-audit-server.sh
/%{installdir}/bin/pbench-backup-tarballs.py
/%{installdir}/bin/pbench-base.py
/%{installdir}/bin/pbench-clean-up-dangling-results-links.sh
/%{installdir}/bin/pbench-copy-sosreports.sh
/%{installdir}/bin/pbench-dispatch.sh
/%{installdir}/bin/pbench-index.py
/%{installdir}/bin/pbench-reindex.py
/%{installdir}/bin/pbench-report-status.py
/%{installdir}/bin/pbench-satellite-cleanup.sh
/%{installdir}/bin/pbench-satellite-state-change.py
/%{installdir}/bin/pbench-server-prep-shim-002.py
/%{installdir}/bin/pbench-sync-package-tarballs.sh
/%{installdir}/bin/pbench-sync-satellite.sh
/%{installdir}/bin/pbench-trampoline
/%{installdir}/bin/pbench-unpack-tarballs.sh
/%{installdir}/bin/pbench-verify-backup-tarballs.py
/%{installdir}/bin/pbench-check-tb-age
/%{installdir}/bin/pbench-check-tb-age.py
/%{installdir}/bin/pbench-cull-unpacked-tarballs
/%{installdir}/bin/pbench-cull-unpacked-tarballs.py

/%{installdir}/lib/systemd/pbench-server.service.default
/%{installdir}/lib/systemd/pbench-server.service.rhel7

%defattr(644, pbench, pbench, 755)
/%{installdir}/%{static}/css/v0.2/pbench_utils.css
/%{installdir}/%{static}/js/v0.2/pbench_utils.js
/%{installdir}/%{static}/js/v0.2/app.js
/%{installdir}/%{static}/css/v0.3/jschart.css
/%{installdir}/%{static}/js/v0.3/jschart.js

%doc
/%{installdir}/README.md
/%{installdir}/lib/pbench/server/s3backup/README
/%{installdir}/lib/pbench/common/AUTHORS.log_formatter
/%{installdir}/lib/pbench/common/LICENSE.log_formatter
/%{installdir}/%{static}/css/v0.3/LICENSE.TXT
/%{installdir}/%{static}/js/v0.3/LICENSE.TXT
