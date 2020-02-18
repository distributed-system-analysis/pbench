import logging
import sys

from cliff import app
from cliff import commandmanager
from pbr import version


class Main(app.App):

    log = logging.getLogger(__name__)

    def __init__(self):
        super(Main, self).__init__(
            description="A Benchmarking and Performance Analysis Framework",
            version=version.VersionInfo('pbench').version_string_with_vcs(),
            command_manager=commandmanager.CommandManager('pbench.cm'),
            deferred_help=True,
        )

    def initialize_app(self, argv):
        self.log.debug('pbench initialize_app')

    def prepare_to_run_command(self, cmd):
        self.log.debug('prepare_to_run_command %s', cmd.__class__.__name__)

    def clean_up(self, cmd, result, err):
        self.log.debug('pbench clean_up %s', cmd.__class__.__name__)
        if err:
            self.log.debug('pbench got an error: %s', err)


def main(argv=sys.argv[1:]):
    the_app = Main()
    return the_app.run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
