'''
* Implements a gRPC client that initializes a stub and makes an RPC call to
* our server while propagating the span context in JSON text form
*
* Makes a request to the given host and port (localhost:50051 by default)
* Makes multiple requests on a given interval for a given duration (100ms and 1000ms by default)
*
* Arguments:
*   [host]
*   [port]
*   [interval in milliseconds]
*   [duration in milliseconds]
'''

from __future__ import print_function
import sys
import logging

import grpc

import node1_pb2
import node1_pb2_grpc

import time
from jaeger_client import Config
from opentracing.propagation import Format

import json


def init_tracer(service):
    # get the root logger (and reset its handlers?)
    logging.getLogger('').handlers = []
    logging.basicConfig(format='%(message)s', level=logging.DEBUG)

    config = Config(
        config={
            # a const sampler takes all traces if param=1, none if param=0
            'sampler': {
                'type': 'const',
                'param': 1,
            },
            'logging': True,
        },
        service_name=service,
        validate=True,
    )

    # this call also sets opentracing.tracer
    return config.initialize_tracer()

def run():
    # NOTE(gRPC Python Team): .close() is possible on a channel and should be
    # used in circumstances in which the with statement does not fit the needs
    # of the code.

    tracer = init_tracer('distributed-test')

    # get host and port to send request
    try:
        host = sys.argv[1]
    except IndexError:
        host = "localhost"
    try:
        port = sys.argv[2]
    except IndexError:
        port = "50051"

    # get interval and duration
    try:
        interval = int(sys.argv[3])
    except IndexError:
        interval = 100
    try:
        duration = int(sys.argv[4])
    except IndexError:
        duration = 1000

    loop_n_times = int(duration / interval)

    # start a span for the whole loop
    main_span = tracer.start_span('looping-requests')
    main_span.set_tag("interval", interval)
    main_span.set_tag("duration", duration)

    for i in range(loop_n_times):
        # start a span for the request
        span = tracer.start_span(operation_name=f'greet-request-{i}', child_of=main_span)

        # inject this span's context into a dict, then convert to JSON
        carrier = {}
        tracer.inject(span_context=span.context, format=Format.TEXT_MAP, carrier=carrier)
        context_json = json.dumps(carrier)

        span.log_event("Injected span context into carrier")

        # call the SayHello remote procedure with the context in the request
        with grpc.insecure_channel(f"{host}:{port}") as channel:
            stub = node1_pb2_grpc.GreeterStub(channel)
            response = stub.SayHello(node1_pb2.HelloRequest(spanContext=context_json, name='client'))
        print("Greeter client received: " + response.message)

        span.log_event("Completed request to gRPC server")

        # finish the span
        span.finish()

        time.sleep(float(interval)/1000)

    # close the main span
    main_span.finish()

    # note: does not send if we don't sleep first
    time.sleep(2)   # yield to IOLoop to flush the spans - https://github.com/jaegertracing/jaeger-client-python/issues/50
    tracer.close()  # flush any buffered spans


if __name__ == '__main__':
    logging.basicConfig()
    run()
