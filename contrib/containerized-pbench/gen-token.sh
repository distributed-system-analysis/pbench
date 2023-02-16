#!/bin/bash

# In a containerized environment, the Pbench Agent profile must be run to
# establish the proper execution environment.
source /opt/pbench-agent/profile

# Generate a token to move results to the target Pbench Server storing it in the
# mounted /var/lib/pbench-agent directory.
pbench-generate-token --output=/var/lib/pbench-agent/.token
