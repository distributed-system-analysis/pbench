Name:           smallfile
Version:     1.9.1
Release:     11%{?dist}
Summary:        Ben England's smallfile benchmark
License:        http://www.apache.org/licenses/LICENSE-2.0
URL:            https://github.com/bengland2/smallfile.git
Source0:        smallfile-%{version}.tar.gz
Buildarch:      x86_64

%description
Ben England's smallfile benchmark

%prep
%setup

%build

%install

mkdir -p %{buildroot}
install -d -m 755 %{buildroot}/opt/smallfile
install -m 755 default.html %{buildroot}/opt/smallfile/default.html
install -m 755 drop_buffer_cache.py %{buildroot}/opt/smallfile/drop_buffer_cache.py
install -m 755 fallocate.py %{buildroot}/opt/smallfile/fallocate.py
install -m 755 invoke_process.py %{buildroot}/opt/smallfile/invoke_process.py
install -m 755 launcher_thread.py %{buildroot}/opt/smallfile/launcher_thread.py
install -m 755 launch_smf_host.py %{buildroot}/opt/smallfile/launch_smf_host.py
install -m 755 multi_thread_workload.py %{buildroot}/opt/smallfile/multi_thread_workload.py
install -m 755 output_results.py %{buildroot}/opt/smallfile/output_results.py
install -m 755 parse.py %{buildroot}/opt/smallfile/parse.py
install -m 755 parse_slave.py %{buildroot}/opt/smallfile/parse_slave.py
install -m 755 profile.sh %{buildroot}/opt/smallfile/profile.sh
install -m 755 profile_workload.py %{buildroot}/opt/smallfile/profile_workload.py
install -m 755 README.md %{buildroot}/opt/smallfile/README.md
install -m 755 regtest.sh %{buildroot}/opt/smallfile/regtest.sh
install -m 755 smallfile_cli.py %{buildroot}/opt/smallfile/smallfile_cli.py
install -m 755 smallfile.py %{buildroot}/opt/smallfile/smallfile.py
install -m 755 smallfile_remote.py %{buildroot}/opt/smallfile/smallfile_remote.py
install -m 755 smf_test_params.py %{buildroot}/opt/smallfile/smf_test_params.py
install -m 755 ssh_thread.py %{buildroot}/opt/smallfile/ssh_thread.py
install -m 755 sync_files.py %{buildroot}/opt/smallfile/sync_files.py

%post

%preun

%postun

%files
/opt/smallfile/default.html
/opt/smallfile/drop_buffer_cache.py
/opt/smallfile/fallocate.py
/opt/smallfile/invoke_process.py
/opt/smallfile/launcher_thread.py
/opt/smallfile/launch_smf_host.py
/opt/smallfile/multi_thread_workload.py
/opt/smallfile/output_results.py
/opt/smallfile/parse.py
/opt/smallfile/parse_slave.py
/opt/smallfile/profile.sh
/opt/smallfile/profile_workload.py
/opt/smallfile/README.md
/opt/smallfile/regtest.sh
/opt/smallfile/smallfile_cli.py
/opt/smallfile/smallfile.py
/opt/smallfile/smallfile_remote.py
/opt/smallfile/smf_test_params.py
/opt/smallfile/ssh_thread.py
/opt/smallfile/sync_files.py

# the mock environment for RHEL6 contains python and brp-python-bytecompile
# insists on compiling these files, so we have to include the compiled version here,
# otherwise the RPM build fails with "installed but unpackaged files" errors. The
# other three mock environments do not install python, so the files are *not* compiled
# and we *cannot* include them here.

%if 0%{?rhel} == 6
/opt/smallfile/drop_buffer_cache.pyc
/opt/smallfile/drop_buffer_cache.pyo
/opt/smallfile/fallocate.pyc
/opt/smallfile/fallocate.pyo
/opt/smallfile/invoke_process.pyc
/opt/smallfile/invoke_process.pyo
/opt/smallfile/launch_smf_host.pyc
/opt/smallfile/launch_smf_host.pyo
/opt/smallfile/launcher_thread.pyc
/opt/smallfile/launcher_thread.pyo
/opt/smallfile/multi_thread_workload.pyc
/opt/smallfile/multi_thread_workload.pyo
/opt/smallfile/output_results.pyc
/opt/smallfile/output_results.pyo
/opt/smallfile/parse.pyc
/opt/smallfile/parse.pyo
/opt/smallfile/parse_slave.pyc
/opt/smallfile/parse_slave.pyo
/opt/smallfile/profile_workload.pyc
/opt/smallfile/profile_workload.pyo
/opt/smallfile/smallfile.pyc
/opt/smallfile/smallfile.pyo
/opt/smallfile/smallfile_cli.pyc
/opt/smallfile/smallfile_cli.pyo
/opt/smallfile/smallfile_remote.pyc
/opt/smallfile/smallfile_remote.pyo
/opt/smallfile/smf_test_params.pyc
/opt/smallfile/smf_test_params.pyo
/opt/smallfile/ssh_thread.pyc
/opt/smallfile/ssh_thread.pyo
/opt/smallfile/sync_files.pyc
/opt/smallfile/sync_files.pyo
%endif
%doc
