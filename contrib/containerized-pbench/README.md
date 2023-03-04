# Running a Pbench Agent-driven Workload in a Container
1. Create a workload script (`example-workload.sh` can be used to start)
   This script performs the invocation of a Pbench Agent workload driver, e.g.
   `pbench-user-benchmark`, or `pbench-fio`, or `pbench-uperf`.
2. Setup the local execution environment to be aware of the target Pbench Server
   `./setup.sh <pbench server host name>:<port number>`
3. Execute the workload
   Typically this script performs the necessary setup required for the
   containerized environment (`example-driver.sh` can be used to start, note
   that it also moves the results to the Pbench Server).
