Name:           uperf
Version:        1.0.4
Release:        1%{?dist}
Summary:        Unified Network Performance Tool

License:        GPLv3+
URL:            http://www.uperf.org/
Source0:        http://sourceforge.net/projects/uperf/files/uperf/%{name}-%{version}.tar.bz2
Buildarch:      x86_64

Patch0: uperf.patch
Patch1: uperf-service.patch

%description
Unified Network Performance Tool

%prep
%setup -q

%patch0 -p1
%patch1 -p1

%build
CFLAGS=-lpthread ./configure --disable-sctp
make

%install
rm -rf %{buildroot}

make %{?_smp_mflags} DESTDIR=$RPM_BUILD_ROOT install
install -c -m 644 uperf.service %{buildroot}/usr/local/share

%post

%preun

%postun

%files
/usr/local/bin/uperf
/usr/local/share/connect.xml
/usr/local/share/iperf.xml
/usr/local/share/ldap.xml
/usr/local/share/netperf.xml
/usr/local/share/oltpnet.xml
/usr/local/share/oraclerac.xml
/usr/local/share/sctp.xml
/usr/local/share/specweb.xml
/usr/local/share/ssl.xml
/usr/local/share/telnet.xml
/usr/local/share/two-hosts.xml
/usr/local/share/uperf.service

%doc
