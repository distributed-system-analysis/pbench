#!/usr/bin/python

#
# LPCPU (Linux Performance Customer Profiler Utility): ./tools/results-web-server.py
#
# (C) Copyright IBM Corp. 2015
#
# This file is subject to the terms and conditions of the Eclipse
# Public License.  See the file LICENSE.TXT in this directory for more
# details.
#


import SimpleHTTPServer
import SocketServer
import socket
import signal
import os
import sys
import threading
import thread

# allow restarts of the web server to continue to reuse the same address
SocketServer.TCPServer.allow_reuse_address = True

# prevent logging of each request by sending STDERR to null
FD = open(os.devnull, "w")
sys.stderr = FD

INTERFACE = "127.0.0.1"
PORT = 8080

event = threading.Event()

Handler = SimpleHTTPServer.SimpleHTTPRequestHandler

# most of the files that we serve are plain text but don't have valid mime types...so force plain text for unknown
Handler.extensions_map[""] = "text/plain"

httpd = SocketServer.TCPServer((INTERFACE, PORT), Handler)


def shutdown(msg, evt):
    print "%s: Stopping web server..." % (msg)
    httpd.shutdown()
    print "Shutdown complete"
    evt.set()
    return


def handler(signum, frame):
    # since httpd.server_forever below is blocking, must issue the shutdown command in a separate thread
    t = threading.Thread(target=shutdown, args=("\nSIGINT received", event))
    t.start()


signal.signal(signal.SIGINT, handler)

print "Using your browser, open http://%s:%d/demo.html to view the demo charts or http://%s:%d to browse all files." % (
    INTERFACE,
    PORT,
    INTERFACE,
    PORT,
)
print "Press CTRL-C to quit..."
# this will block....
httpd.serve_forever()

event.wait()
print "Goodbye!"
sys.exit()
