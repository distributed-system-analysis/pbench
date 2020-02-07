#!/usr/bin/env python3

# Usage: pbench-add-metalog-option <metadata log file> <section> <option>

# Add an option to a section of the metadata.log file.
# E.g. using an 'iterations' arg for the option
#
# iterations: 1-iter, 2-iter, 3-iter
#
# where the iterations are in the <iterations.file>, one iteration per line.
import errno
import sys
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


if __name__ == "__main__":
    _log_file = sys.argv[1]
    _section = sys.argv[2]
    _option = sys.argv[3]
    _value = sys.argv[4]
    add_metalog_option(_log_file, _section, _option, _value)
