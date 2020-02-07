# Setup 

To create a development environment, one just clones what they need

## Getting the code

Grab the code from git

$ git clone https://github.com/distributed-system-analysis/pbench
$ cd pbench

## Run unit tests

The first step is to install the necessary dependencies that are required to
run on the system:

sudo yum install -y perl-JSON
sudo yum install -y python3-pip
sudo pip3 install tox

Once tox is installed you can run the unittests:

tox -e agent (for pbench agent)
tox -e server (for pbench server)
tox -e pytest_agent (for pytest pbench agent)
tox -e pytest_server (for pytest pbench server)

# Python formatting

This project uses the flake8 method of code style enforcement, linting and checking,
 [flake8](http://flake8.pycqa.org/en/latest)

All python code contributed to pbench must match the style requirements. These
requirements are enforced by [pre-commit] (https://pre-commit.com).

## Use pre-commit to set automatic commit requirements

This project makes use of [pre-commit](https://pre-commit.com/) to do automatic
lint and style checking on every commit containing Python files.

To install the pre-commit hook, run the executable from your Python 3 framework
while in your current pbench git checkout:

$ cd ~/pbench
$ pip3 install pre-commit
$ pre-commit install --install-hooks

Once installed, all commits will run the test hooks. If your commit fails any of
the tests, the commit will be rejected.


