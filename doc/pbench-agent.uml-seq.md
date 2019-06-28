@startuml
'UML Sequence Diagram for pbench-agent work flow with Tool Meisters and Tool Data Sink.

User -> Controller: pbench-register-tool[-set] NodeA
note left of User: the "User" is the script or command line from which pbench-register-tool[-set]\nor pbench-user-benchmark is invoked.
note left of Controller: the notion of a "Controller" in the parlance of the pbench-agent is the host\nwhere tools are registered and benchmark scripts are invoked.

'Place holder to setup Controller, Tool Store, Redis, and Tool Data Sink together so that they are drawn in the diagram before the nodes and server.
Controller -> ToolStore
Controller -> Redis
Controller -> ToolDataSink

'Continue with first pbench-register-tool[-set]
Controller -> ToolStore: record
Controller -> User: success

User -> Controller: pbench-register-tool[-set] NodeB
Controller -> ToolStore: record
Controller -> User: success

User -> Controller: pbench-user-benchmark

par pbench-tool-meister-start (Setup Tool Meisters)
note left of Controller: pbench-user-benchmark calls pbench-tool-meister-start\nwhen all is ready to start running the benchmark(s).

Controller -> Redis: setup
note left of Redis: Redis Server\nContains all tool data for all nodes, loaded from the Tool Store by\nthe controller and stored in JSON format.  All Tool Meisters pull their\nindividual configuration from the Redis instance.  The Redis instance\nalso contains the configuration for the Tool Data Sink instance.
Redis -> Controller: success

Controller -> ToolDataSink: setup
ToolDataSink -> Redis: fetch config via Redis key
Redis -> ToolDataSink: success
ToolDataSink -> Controller: success

Controller --> NodeA: pbench-tool-meister setup
Controller --> NodeB: pbench-tool-meister setup
NodeA --> Redis: fetch config via Redis key
NodeB --> Redis: fetch config via Redis key
Redis --> NodeA: success
Redis --> NodeB: success
NodeA --> Controller: success
NodeB --> Controller: success

'End pbench-tool-meister-start (Setup Tool Meisters)
end

par pbench-start-tools
note left of Controller: pbench-user-benchmark calls pbench-start-tools\njust before it invokes the user's benchmark script.
Controller -> Redis: publish start tools, "tool group" "directory"
par Redis pub/sub mech
Redis --> ToolDataSink: start "tool group" "directory"
ToolDataSink --> PMLNodeA: start pmlogger for NodeA
ToolDataSink --> PMLNodeB: start pmlogger for NodeB
ToolDataSink --> Prometheus: start
Redis --> NodeA: start "tool group" "directory"
NodeA --> PMCdNodeA: start pmcd for NodeA
NodeA --> NodeANE: start node_exporter for NodeA
Redis --> NodeB: start "tool group" "directory"
NodeB --> PMCdNodeB: start pmcd for NodeB
NodeB --> NodeBNE: start node_exporter for NodeB
NodeA --> Redis: success
NodeB --> Redis: success
end
ToolDataSink -> Redis: success
note left of ToolDataSink: the Tool Data Sink publishes success for "start"\nwhen it sees all other registered nodes have posted their success.
Redis -> Controller: success (start tools)
'End pbench-start-tools
end

note left of Controller: Controller (pbench-user-benchmark) invokes benchmark script ...

par pbench-stop-tools
note left of Controller: pbench-user-benchmark calls pbench-stop-tools\nimmediately following the termination of the\nuser's benchmark script.
Controller -> Redis: publish stop tools, "tool group" "directory"
par Redis pub/sub mech
Redis --> ToolDataSink: stop "tool group" "directory"
Redis --> NodeA: stop "tool group" "directory"
NodeA --> PMCdNodeA: stop pmcd for NodeA
NodeA --> NodeANE: stop node_exporter for NodeA
Redis --> NodeB: stop "tool group" "directory"
NodeB --> PMCdNodeB: stop pmcd for NodeB
NodeB --> NodeBNE: stop node_exporter for NodeB
NodeA --> Redis: success
NodeB --> Redis: success
end
par ToolDataSink stop pmloggers
ToolDataSink --> PMLNodeA: stop pmlogger for NodeA
ToolDataSink --> PMLNodeB: stop pmlogger for NodeB
ToolDataSink --> Prometheus: stop
end
ToolDataSink -> Redis: success
note left of ToolDataSink: the Tool Data Sink publishes success for "stop"\nwhen it sees all other registered nodes have posted their success.
Redis -> Controller: success (stop tools)
'End pbench-stop-tools
end

par pbench-postprocess-tools
note left of Controller: pbench-user-benchmark calls pbench-postprocess-tools\nimmediately following the completion of\npbench-stop-tools.
Controller -> Redis: publish send tools
par Redis pub/sub mech
Redis --> ToolDataSink: send "tool group" "directory"
Redis --> NodeA: send "tool group" "directory"
Redis --> NodeB: send "tool group" "directory"
note left of NodeA: Nodes A & B build up tar balls containing all tool data for given iteration
par HTTP PUT of tar balls
NodeA --> ToolDataSink: PUT tool(s) tar ball(s)
note left of ToolDataSink: the PUT operations from nodes will receive a 412 status\nin the case where the Tool Data Sink failed to setup\nfor the "send" operation before PUT operations began;\nnodes are required to retry on 412 status codes until\nanother status code is returned.
NodeB --> ToolDataSink: PUT tool(s) tar ball(s)
ToolDataSink --> NodeA: success
ToolDataSink --> NodeB: success
end
NodeA --> Redis: success
NodeB --> Redis: success
end
ToolDataSink -> Redis: success
Redis -> Controller: success (send tools)
'End pbench-postprocess-tools
end

par pbench-collect-sysinfo
Controller --> NodeA: collect config
Controller --> NodeB: collect config
NodeA --> Controller: success (config tar ball)
NodeB --> Controller: success (config tar ball)
end

Controller -> User: success (pbench-user-benchmark)


User -> Controller: pbench-move-results
Controller -> Server: send result tar ball
Server -> Controller: success
Controller -> User: success (pbench-move-results)
@enduml
