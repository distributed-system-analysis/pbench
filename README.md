# Pbench

A Benchmarking and Performance Analysis Framework

This is the `b0.69` branch of the code base.  It is currently focused on support
for the legacy Pbench Server code and behaviors.  The Pbench Agent code has been
removed entirely, please use the `main` branch for the Pbench Agent.

For see the `README.md` on the `main` branch for further details.

## Testing

    $ tox -e lint        # Runs code linting tasks
    $ tox -e py3-server  # Runs all Python3 Unit tests
    $ tox -e server      # Runs all legacy Pbench Server tests
