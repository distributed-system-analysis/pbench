# This is a mock file for selinux.restorecon test cases
import os


def restorecon(path, recursive=False, verbose=False, force=False):
    """ Restore SELinux context on a given path

    Arguments:
    path -- The pathname for the file or directory to be relabeled.

    Keyword arguments:
    recursive -- Change files and directories file labels recursively (default False)
    verbose -- Show changes in file labels (default False)
    force -- Force reset of context to match file_context for customizable files,
    and the default file context, changing the user, role, range portion  as well
    as the type (default False)
    """
    with open(os.environ["_testlog"], "a") as ofp:
        ofp.write(
            f"selinux.restorecon({str(path)!r}, recursive={recursive!r}, verbose={verbose!r}, force={force!r})\n"
        )

    return 0
