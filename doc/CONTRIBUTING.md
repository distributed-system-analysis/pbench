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


