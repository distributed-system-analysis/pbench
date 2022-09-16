import configparser

from pbench.common import MetadataLog


def add_metalog_option(log_file: str, section: str, option: str, value: str):
    """add_metalog_option - add the value to the option in the section of the
    provided log file.

    If the section does not exist, it is created.

    If the option already exists, the value is updated.

    No return value is provided; all exceptions are exposed to the caller.
    """
    mdlog = MetadataLog()
    mdlog.read(log_file)
    try:
        mdlog.set(section, option, value)
    except configparser.NoSectionError:
        mdlog.add_section(section)
        mdlog.set(section, option, value)
    mdlog.write(open(log_file, "w"))
