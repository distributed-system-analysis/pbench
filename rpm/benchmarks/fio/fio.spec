Name:           fio
Version:     2.2.5
Release:     2%{?dist}
Summary:        Jens Axboe's fio benchmark

License:        GPLv3+
URL:            http://git.kernel.dk/?p=fio.git;a=summary
Source0:        http://brick.kernel.dk/snaps/%{name}-%{version}.tar.gz
Buildarch:      x86_64
BuildRequires:  libaio-devel

Patch0: 1-stat.patch
Patch1: 2-client.patch
Patch2: 3-hostfile.patch
Patch3: 4-singlefs.patch

%description
Jens Axboe's fio benchmark

%prep
%setup -q

%patch0 -p1
%patch1 -p1
%patch2 -p1
%patch3 -p1

%build
./configure
make

%install
rm -rf %{buildroot}

make %{?_smp_mflags} DESTDIR=$RPM_BUILD_ROOT install

%post

%preun

%postun

%files
# /usr/local/bin/axmap
/usr/local/bin/fio-btrace2fio
/usr/local/bin/fio-dedupe
/usr/local/bin/fio
/usr/local/bin/fio2gnuplot
/usr/local/bin/fio_generate_plots
/usr/local/bin/genfio
/usr/local/bin/fio-genzipf
# /usr/local/bin/ieee754
# /usr/local/bin/lfsr-test
# /usr/local/bin/stest
/usr/local/man/man1/fio.1
/usr/local/man/man1/fio2gnuplot.1
/usr/local/man/man1/fio_generate_plots.1
/usr/local/share/fio/graph2D.gpm
/usr/local/share/fio/graph3D.gpm
/usr/local/share/fio/math.gpm

%doc
