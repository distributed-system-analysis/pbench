@startuml
'UML Sequence Diagram for pbench-agent work flow with Tool Meisters and Tool Data Sink.

User -> Controller: pbench-register-tool[-set] NodeA
note left of User: the "User" is the script or command line from which pbench-register-tool[-set]\nor pbench-user-benchmark is invoked.
note left of Controller: the notion of a "Controller" in the parlance of the pbench-agent is the host\nwhere tools are registered and benchmark scripts are invoked.

'Place holder to setup Controller, Tool Store, Redis, and Tool Data Sink together so that they are drawn in the diagram before the nodes and server.
Controller -> ToolStore: no-op
Controller -> ToolDataSink: no-op
Controller -> Redis: no-op

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
note left of ToolDataSink: The Tool Data Sink now waits for the Tool Meisters to show up.

Controller --> NodeA: pbench-tool-meister startup
Controller --> NodeB: pbench-tool-meister startup
NodeA --> Redis: fetch config via Redis key
NodeB --> Redis: fetch config via Redis key
Redis --> NodeA: success startup
Redis --> NodeB: success startup
NodeA --> ToolDataSink: success startup
NodeB --> ToolDataSink: success startup

ToolDataSink -> Redis: success "startup"
note left of ToolDataSink: The Tool Data Sink reports success to the Controller only through Redis.
Redis -> Controller: success "startup"

note right of Controller: (optional) sysinfo is collected
Controller -> Redis: publish "sysinfo", "tool group", "directory", "args"
Redis -> ToolDataSink: "tds-sysinfo", "tool group", "directory", "args"
ToolDataSink -> Redis: "tm-sysinfo", "tool group", "directory", "args"
par Redis pub/sub mech for "sysinfo"
Redis --> NodeA: "tm-sysinfo", "tool group", "directory", "args"
Redis --> NodeB: "tm-sysinfo", "tool group", "directory", "args"
NodeA --> ToolDataSink: PUT "sysinfo" config tar ball
ToolDataSink --> NodeA: success
NodeB --> ToolDataSink: PUT "sysinfo" config tar ball
ToolDataSink --> NodeB: success
NodeA --> Redis: "success"
NodeB --> Redis: "success"
Redis --> ToolDataSink: "success (NodeA)"
Redis --> ToolDataSink: "success (NodeB)"
'End sysinfo
end
ToolDataSink -> Redis: "success - sysinfo"
Redis -> Controller: "success - sysinfo"

note right of Controller: the "init" tools phase (required) is started
Controller -> Redis: publish init, "tool group", "directory", "args"
Redis -> ToolDataSink: "tds-init", "tool group", "directory", "args"
par Tool Data Sink persistent collectors started
ToolDataSink --> NodeApml: start pmlogger for NodeA
ToolDataSink --> NodeBpml: start pmlogger for NodeB
ToolDataSink --> Prometheus: start
'End persistent collectors
end
ToolDataSink -> Redis: "tm-init", "tool group", "directory", "args"
par Redis pub/sub mech for "tm-init"
Redis --> NodeA: "tm-init", "tool group", "directory", "args"
Redis --> NodeB: "tm-init", "tool group", "directory", "args"
NodeA --> NodeApmcd: start pmcd
NodeA --> NodeAne: start node_exporter
NodeB --> NodeBpmcd: start pmcd
NodeB --> NodeBne: start node_exporter
NodeA --> Redis: "success"
NodeB --> Redis: "success"
Redis --> ToolDataSink: "success (NodeA)"
Redis --> ToolDataSink: "success (NodeB)"
'End tm-init
end
ToolDataSink -> Redis: "success - init"
Redis -> Controller: "success - init"

'End pbench-tool-meister-start (Setup Tool Meisters)
end


par pbench-start-tools
note left of Controller: pbench-user-benchmark calls pbench-start-tools\njust before it invokes the user's benchmark script.
Controller -> Redis: publish start tools, "tool group" "directory"
Redis -> ToolDataSink: start tools, "tool group" "directory"
par Redis pub/sub mech
ToolDataSink --> Redis: tm-start, "tool group" "directory"
ToolDataSink --> Redis: tm-start, "tool group" "directory"
Redis --> NodeA: tm-start, "tool group" "directory"
Redis --> NodeB: tm-start, "tool group" "directory"
NodeA --> Redis: success, tm-start
NodeB --> Redis: success, tm-start
'End pub/sub mech
end
ToolDataSink -> Redis: success start tools
note left of ToolDataSink: the Tool Data Sink publishes success for "start"\nwhen it sees all other registered nodes have posted their success.
Redis -> Controller: success (start tools)
'End pbench-start-tools
end


note left of Controller: Controller (pbench-user-benchmark) invokes benchmark script ...


par pbench-stop-tools
note left of Controller: pbench-user-benchmark calls pbench-stop-tools\nimmediately following the termination of the\nuser's benchmark script.
Controller -> Redis: publish stop tools, "tool group" "directory"
Redis -> ToolDataSink: stop tools, "tool group" "directory"
par Redis pub/sub mech
ToolDataSink --> Redis: tm-stop, "tool group" "directory"
ToolDataSink --> Redis: tm-stop, "tool group" "directory"
Redis --> NodeA: tm-stop, "tool group" "directory"
Redis --> NodeB: tm-stop, "tool group" "directory"
NodeA --> Redis: success, tm-stop
NodeB --> Redis: success, tm-stop
'End pub/sub mech
end
ToolDataSink -> Redis: success stop tools
note left of ToolDataSink: the Tool Data Sink publishes success for "stop"\nwhen it sees all other registered nodes have posted their success.
Redis -> Controller: success (stop tools)
'End pbench-stop-tools
end


par pbench-send-tools
note left of Controller: pbench-user-benchmark calls pbench-send-tools\nimmediately following the completion of\npbench-stop-tools.
Controller -> Redis: publish send tools
Redis -> ToolDataSink: send "tool group" "directory"
ToolDataSink -> Redis: tm-send "tool group" "directory"
par Redis pub/sub mech
Redis --> NodeA: tm-send "tool group" "directory"
Redis --> NodeB: tm-send "tool group" "directory"
note left of NodeA: Nodes A & B build up tar balls containing all tool data for given iteration
par HTTP PUT of tar balls
NodeA --> ToolDataSink: PUT tool(s) tar ball(s)
note left of ToolDataSink: the PUT operations from nodes will receive a 412 status\nin the case where the Tool Data Sink failed to setup\nfor the "send" operation before PUT operations began;\nnodes are required to retry on 412 status codes until\nanother status code is returned.
NodeB --> ToolDataSink: PUT tool(s) tar ball(s)
ToolDataSink --> NodeA: success PUT
ToolDataSink --> NodeB: success PUT
end
NodeA --> Redis: success tm-send
NodeB --> Redis: success tm-send
Redis --> ToolDataSink: success tm-send
Redis --> ToolDataSink: success tm-send
end
ToolDataSink -> Redis: success send
Redis -> Controller: success send
'End pbench-send-tools
end


par pbench-tool-meister-stop (Shutdown Tool Meisters)

note right of Controller: the "end" tools phase (required) is started
Controller -> Redis: publish end, "tool group", "directory", "args"
Redis -> ToolDataSink: "tds-end", "tool group", "directory", "args"
ToolDataSink -> Redis: "tm-end", "tool group", "directory", "args"

par Redis pub/sub mech for "tm-end"
Redis --> NodeA: "tm-end", "tool group", "directory", "args"
Redis --> NodeB: "tm-end", "tool group", "directory", "args"
NodeA --> NodeApmcd: stop pmcd
NodeA --> NodeAne: stop node_exporter
NodeB --> NodeBpmcd: stop pmcd
NodeB --> NodeBne: stop node_exporter
NodeA --> Redis: "success"
NodeB --> Redis: "success"
Redis --> ToolDataSink: "success (NodeA)"
Redis --> ToolDataSink: "success (NodeB)"
'End tm-end
end

par Tool Data Sink persistent collectors stopped
ToolDataSink --> NodeApml: stop pmlogger for NodeA
ToolDataSink --> NodeBpml: stop pmlogger for NodeB
ToolDataSink --> Prometheus: stop
'End persistent collectors stopped
end

ToolDataSink -> Redis: "success - end"
Redis -> Controller: "success - end"

note right of Controller: (optional) sysinfo is collected
Controller -> Redis: publish "sysinfo", "tool group", "directory", "args"
Redis -> ToolDataSink: "tds-sysinfo", "tool group", "directory", "args"
ToolDataSink -> Redis: "tm-sysinfo", "tool group", "directory", "args"
par Redis pub/sub mech for "sysinfo"
Redis --> NodeA: "tm-sysinfo", "tool group", "directory", "args"
Redis --> NodeB: "tm-sysinfo", "tool group", "directory", "args"
NodeA --> ToolDataSink: PUT "sysinfo" config tar ball
ToolDataSink --> NodeA: success
NodeB --> ToolDataSink: PUT "sysinfo" config tar ball
ToolDataSink --> NodeB: success
NodeA --> Redis: "success"
NodeB --> Redis: "success"
Redis --> ToolDataSink: "success (NodeA)"
Redis --> ToolDataSink: "success (NodeB)"
'End sysinfo
end
ToolDataSink -> Redis: "success - sysinfo"
Redis -> Controller: "success - sysinfo"

note right of Controller: terminate
Controller -> Redis: publish "terminate"
Redis -> ToolDataSink: "tds-terminate"
ToolDataSink -> Redis: "tm-terminate"
par Redis pub/sub mech for "tm-terminate"
Redis --> NodeA: "tm-terminate"
Redis --> NodeB: "tm-terminate"
NodeA --> Redis: "success"
NodeB --> Redis: "success"
Redis --> ToolDataSink: "success (NodeA)"
Redis --> ToolDataSink: "success (NodeB)"
'End sysinfo
end
ToolDataSink -> Redis: "success - terminate"
Redis -> Controller: "success - terminate"

'End pbench-tool-meister-stop
end


Controller -> User: success (pbench-user-benchmark)


User -> Controller: pbench-move-results
Controller -> Server: send result tar ball
Server -> Controller: success
Controller -> User: success (pbench-move-results)
@enduml
