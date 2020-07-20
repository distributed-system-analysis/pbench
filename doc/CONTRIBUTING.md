# Setup 

To create a development environment, one just clones the pbench repository.

## Getting the code

Grab the code from git

```
$ git clone https://github.com/distributed-system-analysis/pbench
$ cd pbench
```

## Run unit tests

The first step is to install the necessary dependencies that are required to
run on the system:

```
sudo yum install -y perl-JSON
sudo yum install -y python3-pip
sudo yum install -y python3-tox
```

Once tox is installed you can run the unittests (use `tox --listenvs` to see
the full list); e.g.:

  * `tox -e util-scripts`  -- for agent/util-scripts tests
  * `tox -e server`  -- for server tests
  * `tox -e lint`  -- to run the linting and code style checks

To run the full suite of unit tests, invoke the `run-unittests` script at
the top-level of the pbench repository.

# Python formatting

This project uses the [flake8](http://flake8.pycqa.org/en/latest) method of
code style enforcement, linting, and checking.

All python code contributed to pbench must match the style requirements. These
requirements are enforced by the [pre-commit](https://pre-commit.com) hook
using the [black](https://github.com/psf/black) Python code formatter.

## Use pre-commit to set automatic commit requirements

This project makes use of [pre-commit](https://pre-commit.com/) to do automatic
lint and style checking on every commit containing Python files.

To install the pre-commit hook, run the executable from your Python 3 framework
while in your current pbench git checkout:

```
$ cd ~/pbench
$ pip3 install pre-commit
$ pre-commit install --install-hooks
```

Once installed, all commits will run the test hooks. If your changes fail any of
the tests, the commit will be rejected.
