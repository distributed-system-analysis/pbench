import errno
from configparser import NoSectionError

from pbench.common import MetadataLog


def add_metalog_option(log_file, section, option, value):
    mdlog = MetadataLog()

    try:
        mdlog.read(log_file)
    except OSError as ex:
        if ex.errno == errno.ENOENT:
            raise Exception(f"Log file does not exist: {log_file}")
        raise

    try:
        mdlog.set(section, option, value)
    except NoSectionError:
        mdlog.add_section(section)
        mdlog.set(section, option, value)
    mdlog.write(open(log_file, "w"))
