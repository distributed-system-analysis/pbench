Name:           pbench-report
Version:        0.01
%define gdist    none
Release:        1%{?dist}
Summary:        The pbench-report scripts

License:        GPLv3+
URL:            https://github.com/distributed-system-analysis/pbench
Source0:        pbench-report-%{version}.tar.gz
Buildarch:      noarch

# it also requires phantomjs, but we don't have an RPM for that - assumed installed.
Requires:       perl

%description
The pbench-report scripts.

%prep
%setup
%build

%install
rm -rf %{buildroot}

mkdir -p %{buildroot}/home/pbench
install -m 755 -d %{buildroot}/home/pbench/bin
install -m 755 scripts/convert_data %{buildroot}/home/pbench/bin/convert_data
install -m 755 scripts/patch_html %{buildroot}/home/pbench/bin/patch_html
install -m 755 scripts/post_convert %{buildroot}/home/pbench/bin/post_convert
install -m 755 scripts/patch_html_cron_script %{buildroot}/home/pbench/bin/patch_html_cron_script
install -m 755 scripts/html_summary_generator %{buildroot}/home/pbench/bin/html_summary_generator
install -m 755 scripts/normalizer.py %{buildroot}/home/pbench/bin/normalizer.py
install -m 755 -d %{buildroot}/home/pbench/lib/js
install -m 755 scripts/res/rasterize.js %{buildroot}/home/pbench/lib/js/rasterize.js
install -m 755 scripts/res/rasterize_delayed.js %{buildroot}/home/pbench/lib/js/rasterize_delayed.js
install -m 755 scripts/res/nvd3.tar.gz %{buildroot}/home/pbench/lib/nvd3.tar.gz
install -m 755 scripts/res/pbench-summary.html %{buildroot}/home/pbench/lib/pbench-summary.html

%pre
if adduser -M pbench 2>/dev/null ;then : ;else : ;fi

%post

%preun

%postun

%files
%defattr(755,pbench,pbench,755)
/home/pbench/bin
/home/pbench/lib

%doc
