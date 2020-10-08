from functools import partial
import hashlib
import os
import sys
import shutil


def rename_tb_link(tb, dest, logger):
    try:
        os.mkdir(dest)
    except FileExistsError:
        # directory already exists, ignore
        pass
    except Exception:
        logger.exception(
            "os.mkdir: Unable to create tar ball destination directory: {}".format(dest)
        )
        raise
    tbname = os.path.basename(tb)
    tbnewname = os.path.join(dest, tbname)
    try:
        os.rename(tb, tbnewname)
    except Exception:
        logger.exception(
            "os.rename: Unable to move tar ball link {} to destination directory: {}".format(
                tb, dest
            )
        )
        raise


def filesize_bytes(size):
    size = size.strip()
    size_name = ["B", "KB", "MB", "GB", "TB"]
    try:
        parts = size.split(" ", 1)
        if len(parts) == 1:
            try:
                num = int(size)
            except ValueError:
                for i, c in enumerate(size):
                    if not c.isdigit():
                        break
                num = int(size[:i])
                unit = size[i:]
            else:
                unit = ""
        else:
            num = int(parts[0])
            unit = parts[1].strip()

        idx = size_name.index(unit.upper()) if unit else 0
        factor = 1024 ** idx
    except Exception as exc:
        raise Exception("Invalid file size value encountered, '%s': %s", size, exc)
    else:
        return num * factor


def md5sum(filename):
    """
    Return the MD5 check-sum of a given file.
    We don't want to read the entire file into memory.
    """
    with open(filename, mode="rb") as f:
        d = hashlib.md5()
        for buf in iter(partial(f.read, 128), b""):
            d.update(buf)
    return d.hexdigest()


def quarantine(dest, logger, *files):
    """Quarantine problematic tarballs.
    Errors here are fatal but we log an error message to help diagnose
    problems.
    """
    try:
        os.mkdir(dest)
    except FileExistsError:
        # directory already exists, ignore
        pass
    except Exception:
        logger.exception('quarantine {} {!r}: "mkdir -p {}/" failed', dest, files, dest)
        sys.exit(101)

    for afile in files:
        if not os.path.exists(afile) and not os.path.islink(afile):
            continue
        try:
            shutil.move(afile, os.path.join(dest, os.path.basename(afile)))
        except Exception:
            logger.exception(
                'quarantine {} {!r}: "mv {} {}/" failed', dest, files, afile, dest
            )
            sys.exit(102)
