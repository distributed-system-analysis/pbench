title Operation of Reverse Proxies with the Pbench Server

entryspacing 1.5

# There can be many, many layers of proxies through
# requests are made to the Pbench Server.  The
# current Pbench Server "in-a-can", and our plans
# to deploy in a "production" environment, leverage
# a reverse proxy so that serving files from disk
# can be handled by the reverse proxy (for which it
# is designed, where Gunicorn is not), while
# seemlessly integrating the Gunicorn instance, 
# serving the Pbench Server APIs, behind a single
# host name and port number.

# A reverse proxy server is also useful for other
# operations as well, such as caching frequently
# accessed web pages, terminating SSL connections
# (often one certificate can be setup for the
# reverse proxy handling all services used),
# or insulating the server from various service
# attacks (Slow Loris [1], other DDoS attacks [2]).
#
# [1] https://www.cloudflare.com/learning/ddos/ddos-attack-tools/slowloris/
# [2] https://www.cloudflare.com/learning/ddos/what-is-a-ddos-attack/

participant Client
participant Proxy
participant Server

==Simple transfer, no proxy==

note left of Client:Typical HTTP(S) client/server exchange\nfor a small PUT operation
Client->Server:Open connection
activate Client
activate Server
Client->Server:Send header, PUT op, CONTENT_LENGTH 5,730
Client->Server:Send body (5,730)
Server->Client:Send response, OK 200
deactivate Server
deactivate Client

==Large file transfer, no proxy==

note left of Client:Typical HTTP(s) client/server exchange\n for a very large PUT operation
Client->Server:Open connection
activate Client
activate Server
Client->Server:Send header, PUT op, CONTENT_LENGTH 17,918,719,194
Client->Server:Send partial body (8,192)
Client->Server:Send partial body (8,192)
Client->Server:Send partial body (8,192)
note over Client: ...after many packets...
Client->Server:Send partial body (8,192)
Client->Server:Send final body (5,338)
Server->Client:Send response, OK 200
deactivate Server
deactivate Client

==Simple transfer, with proxy, no request buffering==

note left of Client:Typical HTTP(S) client/proxy/server exchange\nfor a small PUT operation
Client->Proxy:Open connection
activate Client
activate Proxy
Client->Proxy:Send header, PUT op, CONTENT_LENGTH 5,730
Proxy->Server:Open connection
activate Server
Proxy->Server:Send modified header, PUT op, CONTENT_LENGTH 5,730
Client->Proxy:Send body (5,730)
Proxy->Server:Send body (5,730)
Server->Proxy:Send response, OK 200
deactivate Server
Proxy->Client:Send modified response, OK 200
deactivate Proxy
deactivate Client

==Large transfer, with proxy, no request buffering==

note left of Client:Typical HTTP(S) client/proxy/server exchange\n for a very large PUT operation
Client->Proxy:Open connection
activate Client
activate Proxy
Client->Proxy:Send header, PUT op, CONTENT_LENGTH 17,918,719,194
Proxy->Server:Open connection
activate Server
Proxy->Server:Send modified header, PUT op, CONTENT_LENGTH 17,918,719,194
Client->Proxy:Send partial body (8,192)
Proxy->Server:Send partial body (8,192)
Client->Proxy:Send partial body (8,192)
Proxy->Server:Send partial body (8,192)
Client->Proxy:Send partial body (8,192)
Proxy->Server:Send partial body (8,192)
note over Client: ...after 2,187,339 more 8K packets...
Client->Proxy:Send partial body (8,192)
Proxy->Server:Send partial body (8,192)
Client->Proxy:Send final body (5,338)
Proxy->Server:Send final body (5,338)
Server->Proxy:Send response, OK 200
deactivate Server
Proxy->Client:Send modified response, OK 200
deactivate Proxy
deactivate Client

==Large transfer, with proxy request buffering==

note left of Client:Typical HTTP(S) client/proxy/server exchange\nfor a very large PUT operation
Client->Proxy:Open connection
activate Client
activate Proxy
Client->Proxy:Send header, PUT op, CONTENT_LENGTH 17,918,719,194
Client->Proxy:Send partial body (8,192)
Client->Proxy:Send partial body (8,192)
Client->Proxy:Send partial body (8,192)
note over Client: ...after 2,187,342 8K packets...
Client->Proxy:Send partial body (8,192)
Client->Proxy:Send final body (5,338)
Proxy->Server:Open connection
activate Server
Proxy->Server:Send modified header, PUT op, CONTENT_LENGTH 17,918,719,194
Proxy->Server:Send partial body (262,144)
Proxy->Server:Send partial body (262,144)
Proxy->Server:Send partial body (262,144)
note over Proxy: ...after 68,350 more 262K packets...
Proxy->Server:Send partial body (262,144)
Proxy->Server:Send final body (128,218)
Server->Proxy:Send response, OK 200
deactivate Server
Proxy->Client:Send modified response, OK 200
deactivate Proxy
deactivate Client

==Slow loris attacks==

note left of Client:Typical HTTP(S) client/proxy/server exchange\nfor a "slow loris" DDoS attack
Client->Proxy:Open connection
activate Client
activate Proxy
Client->Proxy:Send header, PUT op, CONTENT_LENGTH 5,730
Client->Proxy:Send partial body (256)
space 3
Client->Proxy:Send partial body (256)
space 3
Client->Proxy:Send partial body (256)
note over Client: ...after 94 more 256 byte packets with long delays between them...
Client->Proxy:Send partial body (256)
space 3
Client->Proxy:Send final body (22)
Proxy->Server:Open connection
activate Server
Proxy->Server:Send modified header, PUT op, CONTENT_LENGTH 5,730
Proxy->Server:Send body (5,730)
Server->Proxy:Send response, OK 200
deactivate Server
Proxy->Client:Send modified response, OK 200
deactivate Proxy
deactivate Client
note over Proxy:The Proxy server absorbed the long delays in sending the body, where an attack will send enough bytes to keep the connection open.\nThe Pbench Server was unaffected and did not see the effect of the attack.

==Caching (typically HEAD/GET methods on specified URLs==

note left of Client:Typical HTTP(S) client/proxy/server exchange\nfor a GET operation for a cachable page.
Client->Proxy:Open Connection
activate Client
activate Proxy
Client->Proxy:Send header, GET op, /objects/id42
Proxy->Proxy:Cache lookup for /objects/id42, not found
Proxy->Server:Open Connection
activate Server
Proxy->Server:Send modified header, GET op, /objects/id42
Server->Proxy:Send header, OK 200
Server->Proxy:Send response body (8K)
deactivate Server
Proxy->Client:Send modified header, OK 200
Proxy->Client:Send response body (8K)
deactivate Proxy
deactivate Client
space 1
Client->Proxy:Open Connection
activate Client
activate Proxy
Client->Proxy:Send header, GET op, /objects/id42
Proxy->Proxy:Cache lookup for /objects/id42, found
Proxy->Client:Send modified header, OK 200
Proxy->Client:Send response body (8K)
deactivate Proxy
deactivate Client