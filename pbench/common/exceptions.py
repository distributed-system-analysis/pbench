class BadConfig(Exception):
    pass


class InvalidDataFormat(Exception):
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


class BadIterationName(Exception):
    """Raised when constructing an Iteration object where the given name does
    not exist on disk, or if the iteration name does not have a leading number.
    """

    pass


class BadSampleName(Exception):
    """Raised when constructing Sample object where the given name does not
    have a trailing number.
    """

    pass
