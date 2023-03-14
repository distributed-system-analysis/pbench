import os
import sys

from pbench.common.conf import common_main


def main():
    sys.exit(common_main(os.path.basename(sys.argv[0]), "_PBENCH_AGENT_CONFIG"))


if __name__ == "__main__":
    main()
