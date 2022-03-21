"""SELinux wrapper module.

There is no "pip" installable `selinux` python module, just a shim, of sorts [1],
which provides a way to add the installed (via RPM) system's `selinux` module to
a virtualenv.  But that does not work when the virtualenv uses a version of
python different from the python version where the real `selinux` module is
installed.

This wrapper acts as a pass-through to the real `selinux` module for the methods
we need, when that module is present.  When that module is not present, we
provide module methods to mimic the behaviors we need.

[1] https://github.com/pycontribs/selinux
"""
try:
    import selinux
except ImportError:
    # The import failed; provide stub implementations.

    def is_selinux_enabled():
        """Always indicates "disabled"."""
        return 0

    def restorecon(path):
        """Always raises an exception, to identify logic problems."""
        raise NotImplementedError(
            "Logic bomb!  selinux.restorecon() called when selinux is not enabled."
        )

else:
    # The import succeeded; forward our functions to the real implementations.
    is_selinux_enabled = selinux.is_selinux_enabled
    restorecon = selinux.restorecon
