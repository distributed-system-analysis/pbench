#!/bin/bash

# In a containerized environment, the Pbench Agent profile must be run to
# establish the proper execution environment.
source /opt/pbench-agent/profile

# Move the results to the configured Pbench Server.
#
# NOTE: the required token must be provided in the file
# /var/lib/pbench-agent/.token ahead of time.
pbench-results-move --token=$(</var/lib/pbench-agent/.token)
