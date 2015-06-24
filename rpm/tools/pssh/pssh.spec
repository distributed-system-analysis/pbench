Summary: 	Parallel ssh tools: pssh, pscp, prsync, pslurp, pnuke
Name: 		pssh
Version: 	2.3.1
Release: 	1
License: 	BSD
Group: 		Applications/System
Source0: 	https://parallel-ssh.googlecode.com/files/%{name}-%{version}.tar.gz
URL:		https://code.google.com/p/parallel-ssh/
Packager:	amcnabb@gmail.com
Buildarch:      noarch
BuildRoot:	%{_tmppath}/%{name}-%{version}-root-%(id -u -n)
BuildRequires:	gettext

%if 0%{?rhel} == 6
%define _pythondir python2.6
%define _pyegg py2.6
%else
%define _pythondir python2.7
%define _pyegg py2.7
%endif

%description
Parallel ssh tools: pssh, pscp, prsync, pslurp, pnuke

%prep

%setup
echo %{_prefix}

%build
python2 setup.py build

%install
python2 setup.py install --skip-build --root $RPM_BUILD_ROOT

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(755,root,root,755)
/usr/bin/pnuke
/usr/bin/prsync
/usr/bin/pscp
/usr/bin/pslurp
/usr/bin/pssh
/usr/bin/pssh-askpass
%defattr(644,root,root,755)
/usr/lib/%{_pythondir}/site-packages/pssh-2.3.1-%{_pyegg}.egg-info
/usr/lib/%{_pythondir}/site-packages/psshlib/__init__.py
/usr/lib/%{_pythondir}/site-packages/psshlib/__init__.pyc
/usr/lib/%{_pythondir}/site-packages/psshlib/askpass_client.py
/usr/lib/%{_pythondir}/site-packages/psshlib/askpass_client.pyc
/usr/lib/%{_pythondir}/site-packages/psshlib/askpass_server.py
/usr/lib/%{_pythondir}/site-packages/psshlib/askpass_server.pyc
/usr/lib/%{_pythondir}/site-packages/psshlib/cli.py
/usr/lib/%{_pythondir}/site-packages/psshlib/cli.pyc
/usr/lib/%{_pythondir}/site-packages/psshlib/color.py
/usr/lib/%{_pythondir}/site-packages/psshlib/color.pyc
/usr/lib/%{_pythondir}/site-packages/psshlib/manager.py
/usr/lib/%{_pythondir}/site-packages/psshlib/manager.pyc
/usr/lib/%{_pythondir}/site-packages/psshlib/psshutil.py
/usr/lib/%{_pythondir}/site-packages/psshlib/psshutil.pyc
/usr/lib/%{_pythondir}/site-packages/psshlib/task.py
/usr/lib/%{_pythondir}/site-packages/psshlib/task.pyc
/usr/lib/%{_pythondir}/site-packages/psshlib/version.py
/usr/lib/%{_pythondir}/site-packages/psshlib/version.pyc
/usr/man/man1/pnuke.1.gz
/usr/man/man1/prsync.1.gz
/usr/man/man1/pscp.1.gz
/usr/man/man1/pslurp.1.gz
/usr/man/man1/pssh.1.gz

/usr/lib/%{_pythondir}/site-packages/psshlib/__init__.pyo
/usr/lib/%{_pythondir}/site-packages/psshlib/askpass_client.pyo
/usr/lib/%{_pythondir}/site-packages/psshlib/askpass_server.pyo
/usr/lib/%{_pythondir}/site-packages/psshlib/cli.pyo
/usr/lib/%{_pythondir}/site-packages/psshlib/color.pyo
/usr/lib/%{_pythondir}/site-packages/psshlib/manager.pyo
/usr/lib/%{_pythondir}/site-packages/psshlib/psshutil.pyo
/usr/lib/%{_pythondir}/site-packages/psshlib/task.pyo
/usr/lib/%{_pythondir}/site-packages/psshlib/version.pyo
