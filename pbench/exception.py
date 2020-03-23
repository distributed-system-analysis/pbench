class BadConfig(Exception):
    pass


class BadDate(Exception):
    pass


class ConfigFileNotSpecified(Exception):
    pass


class ConfigFileError(Exception):
    pass


class BadMDLogFormat(Exception):
    pass


class UnsupportedTarballFormat(Exception):
    pass


class SosreportHostname(Exception):
    pass


class JsonFileError(Exception):
    pass


class MappingFileError(JsonFileError):
    pass


class TemplateError(Exception):
    pass
