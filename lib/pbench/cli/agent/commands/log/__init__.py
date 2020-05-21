import errno
from configparser import ConfigParser, NoSectionError


def add_metalog_option(log_file, section, option, value):
    config = ConfigParser()

    try:
        config.read(log_file)
    except OSError as ex:
        if ex.errno == errno.ENOENT:
            raise Exception(f"Log file does not exist: {log_file}")
        raise

    try:
        config.set(section, option, value)
    except NoSectionError:
        config.add_section(section)
        config.set(section, option, value)
    config.write(open(log_file, "w"))
