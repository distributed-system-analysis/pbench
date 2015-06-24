Name:        configtools
Version:     0.2
Release:     76%{?gdist}%{!?gdist:%{dist}}
Summary:     The configtools module

License:     GPLv3+
URL:         https://github.com/distributed-system-analysis/pbench
Source0:     configtools-%{version}.tar.gz
Buildarch:   noarch

BuildRequires:	python2-devel

%description
The configtools python module and the getconf.py command-line script.

%prep
%setup

%build
%{__python} setup.py build

%install
rm -rf %{buildroot}
%{__python} setup.py install --skip-build --root %{buildroot}

mkdir -p %{buildroot}/opt/configtools
install -m 755 -d %{buildroot}/opt/configtools/bin
install -m 755 bin/getconf.2.py %{buildroot}/opt/configtools/bin/getconf.py
install -m 755 bin/gethosts.2.py %{buildroot}/opt/configtools/bin/gethosts.py

%files
/opt/configtools/bin/getconf.py
/opt/configtools/bin/gethosts.py
%{python_sitelib}/configtools
%{python_sitelib}/%{name}-%{version}-py*.egg-info

%doc
