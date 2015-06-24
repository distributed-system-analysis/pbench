%define _hardened_build 1
Name:           stress
Version:        1.0.4
Release:        12%{?dist}
Summary:        A tool to put given subsystems under a specified load

Group:          Development/Tools
License:        GPLv2+
URL:            http://people.seas.harvard.edu/~apw/stress/
Source0:        http://people.seas.harvard.edu/~apw/stress/%{name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildRequires:  texinfo
Requires(post): info
Requires(preun): info

%description
stress is not a benchmark, but is rather a tool designed to put given
subsytems under a specified load. Instances in which this is useful
include those in which a system administrator wishes to perform tuning
activities, a kernel or libc programmer wishes to evaluate denial of 
service possibilities, etc.

%prep
%setup -q
chmod -x README TODO AUTHORS doc/Makefile.am doc/mdate-sh NEWS src/stress.c
rm INSTALL

%build
%configure
make %{?_smp_mflags}


%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT

rm -f $RPM_BUILD_ROOT%{_infodir}/dir


%post
/sbin/install-info %{_infodir}/%{name}.info %{_infodir}/dir || :


%preun
if [ $1 = 0 ]; then
    /sbin/install-info --delete %{_infodir}/%{name}.info %{_infodir}/dir || :
fi


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(-,root,root,-)
%doc AUTHORS ChangeLog COPYING NEWS README TODO doc/stress.html
%{_bindir}/stress
%{_infodir}/stress*
%{_mandir}/man1/stress.1*


%changelog
* Sun Jun 08 2014 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.4-12
- Rebuilt for https://fedoraproject.org/wiki/Fedora_21_Mass_Rebuild

* Wed Feb 26 2014 Jon Ciesla <limburgher@gmail.com> - 1.0.4-11
- Update URL and Source0, BZ 1070090.

* Sun Aug 04 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.4-10
- Rebuilt for https://fedoraproject.org/wiki/Fedora_20_Mass_Rebuild

* Fri Feb 15 2013 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.4-9
- Rebuilt for https://fedoraproject.org/wiki/Fedora_19_Mass_Rebuild

* Sat Jul 21 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.4-8
- Rebuilt for https://fedoraproject.org/wiki/Fedora_18_Mass_Rebuild

* Fri Apr 13 2012 Jon Ciesla <limburgher@gmail.com> - 1.0.4-7
- Add hardened build.

* Sat Jan 14 2012 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.4-6
- Rebuilt for https://fedoraproject.org/wiki/Fedora_17_Mass_Rebuild

* Wed Feb 09 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 1.0.4-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Fri May 07 2010 Jon Ciesla <limb@jcomserv.net> - 1.0.4-4
- Info requires fix, dropped INSTALL.

* Thu May 06 2010 Jon Ciesla <limb@jcomserv.net> - 1.0.4-3
- Corrected license tag.
- Moved chmod to setup.

* Thu May 06 2010 Jon Ciesla <limb@jcomserv.net> - 1.0.4-2
- Fixed spurious executable perms.

* Wed May 05 2010 Jon Ciesla <limb@jcomserv.net> - 1.0.4-1
- First build.
