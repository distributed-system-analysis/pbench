"""
Helper functions to get the elasticsearch specific configurations
"""

from configparser import NoSectionError, NoOptionError


def get_es_host(config):
    try:
        return config.get("elasticsearch", "host")
    except (NoOptionError, NoSectionError):
        return ""


def get_es_port(config):
    try:
        return config.get("elasticsearch", "port")
    except (NoOptionError, NoSectionError):
        return ""


def get_es_url(config):
    try:
        return f"http://{get_es_host(config)}:{get_es_port(config)}"
    except (NoOptionError, NoSectionError):
        return ""


def get_index_prefix(config):
    try:
        return config.get("Indexing", "index_prefix")
    except (NoOptionError, NoSectionError):
        return ""
