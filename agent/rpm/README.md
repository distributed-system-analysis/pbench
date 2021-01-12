Install as root:
    `dnf install git rpm-build python3 python3-pip python3-jinja2 rpmlint`

If the `python3-jinja2-cli` exists for your distro, install it:
 * `dnf install python3-jinja2-cli`
Otherwise, `pip3 install jinja2-cli` for the local user:
 * `pip3 install --user jinja2-cli`

Assuming you have cloned the `pbench` tree as follows:
```
git clone https://github.com/distributed-system-analysis/pbench.git
cd pbench
```

Build the RPM as follows:
```
cd agent/rpm
make rpm
```

If you want to keep track of separate build IDs in the `pbench-agent`
version string, `echo "1" > seqno` in the `agent/rpm` directory and the
build mechanism will auto increment the number.  The contents of the
`seqno` file is used (if it exists) to set the build number the next
time an spec file is created, and then the `seqno` value is incremented
for any subsequent use.

Finally, you can engage Fedora COPR builds by using `make copr`.  However
you need to have setup an account with Fedora; see [1].  Once you have an
account, if the account name is not the same as the logged in user locally,
then you can use `make copr COPR_USER=<name>` (replacing `<name>` as
appropriate).  The `copr` target expects that you have created a `pbench`
repository in Fedora COPR.  You can also use the `copr-test` target which
expects that you have created a `pbench-test` repository target.

[1] https://developer.fedoraproject.org/deployment/copr/about.html
