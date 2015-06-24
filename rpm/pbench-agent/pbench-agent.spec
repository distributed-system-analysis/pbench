Name:           pbench-agent
Version:        0.33
%define gdist   none
Release:        1%{?dist}
Summary:        The pbench harness

License:        GPLv3+
URL:            https://github.com/distributed-system-analysis/pbench
Source0:        pbench-agent-%{version}.tar.gz
Buildarch:      noarch

%if 0%{?rhel} == 6
%define turbostatpkg cpupowerutils
%else
%define turbostatpkg kernel-tools
%endif

Requires:       bzip2, tar, xz, screen, perl, net-tools, numactl, perf, psmisc, bc, configtools >= 0.1-64, pbench-sysstat, sos
Obsoletes: pbench <= 0.32
Conflicts: pbench <= 0.32

%description
The pbench harness

%prep
%setup
%build

%install
rm -rf %{buildroot}

mkdir -p %{buildroot}/opt/pbench-agent
install -m 755 -d %{buildroot}/opt/pbench-agent/bench-scripts
install -m 755 -d %{buildroot}/opt/pbench-agent/bench-scripts/postprocess
install -m 755 -d %{buildroot}/opt/pbench-agent/config
install -m 755 -d %{buildroot}/opt/pbench-agent/doc
install -m 755 -d %{buildroot}/opt/pbench-agent/run-scripts
install -m 755 -d %{buildroot}/opt/pbench-agent/tool-scripts
install -m 755 -d %{buildroot}/opt/pbench-agent/tool-scripts/datalog
install -m 755 -d %{buildroot}/opt/pbench-agent/tool-scripts/postprocess
install -m 755 -d %{buildroot}/opt/pbench-agent/util-scripts

# being lazy here - some things should not be 755
for x in `cat MANIFEST`
do
    install -m 755 $x %{buildroot}/opt/pbench-agent/`dirname $x`
done

%pre
if adduser -M pbench 2>/dev/null ;then : ;else : ;fi

%post
cd /opt/pbench-agent/tool-scripts
# symlinks
ln -sf kvm-spinlock cpuacct
ln -sf kvm-spinlock kvmstat
ln -sf kvm-spinlock numastat
ln -sf kvm-spinlock proc-interrupts
ln -sf kvm-spinlock proc-sched_debug
ln -sf kvm-spinlock proc-vmstat
ln -sf kvm-spinlock qemu-migrate
ln -sf kvm-spinlock virsh-migrate
ln -sf kvm-spinlock vmstat
ln -sf sar iostat
ln -sf sar mpstat
ln -sf sar pidstat

cd /opt/pbench-agent/util-scripts
ln -sf move-results copy-results

cd /opt/pbench-agent/bench-scripts
ln -sf postprocess/compare-bench-results compare-bench-results

# link the pbench profile, so it'll automatically be sourced on login
ln -sf /opt/pbench-agent/profile /etc/profile.d/pbench-agent.sh

%preun
# if uninstalling, rather than updating, delete the link
if [ $1 -eq 0 ] ;then
    rm -f /etc/profile.d/pbench-agent.sh
fi


%postun
# if uninstalling, rather than updating, remove /opt/pbench-agent
if [ $1 -eq 0 ] ;then
    rm -rf /opt/pbench-agent
fi

%files
%defattr(755,pbench,pbench,755)
/opt/pbench-agent/base
%attr(600,pbench,pbench) /opt/pbench-agent/id_rsa
/opt/pbench-agent/bench-scripts
/opt/pbench-agent/config
/opt/pbench-agent/doc
/opt/pbench-agent/MANIFEST
/opt/pbench-agent/profile
/opt/pbench-agent/run-scripts
/opt/pbench-agent/tool-scripts
/opt/pbench-agent/util-scripts

%doc
