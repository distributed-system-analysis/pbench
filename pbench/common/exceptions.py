class PbenchException(Exception):
    """Base class for exceptions"""
    def __init__(self, message=None):
        self.message = message

    def __str__(self):
        return self.message


class PbenchInvalidConfiguration(PbenchException):
    """Pbench configuration is unknown"""
    def __init__(self, config_file):
        self.config_file = config_file

    def __str__(self):
        return "Configuration %s is invalid." % self.config_file


class PbenchMissingConfig(PbenchException):
    """Raised if configuration doesn't exist"""
    def __str__(self):
        return "No config file specified: set CONFIG env variable or use" \
               "--config <file> on the command line"


class PbenchNoSuchOption(PbenchException):
    """Raised if configuration section doesnt exist"""
    def __init__(self, section):
        self.section = section
    
    def __str__(self):
        return "Configuration option %s doesn't exist." % self.section
