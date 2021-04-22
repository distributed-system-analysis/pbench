'''
* Implements a gRPC server that represents a node in our simulated
* distributed systems
*
* Listens over port 50051 for incoming "SayHello" requests
'''


from concurrent import futures
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

# initialize a tracer with the same service name as the client
tracer = init_tracer('distributed-test')

class Greeter(node1_pb2_grpc.GreeterServicer):

	def SayHello(self, request, context):
		# convert the span context JSON to a dict, then extract
		carrier = json.loads(request.spanContext)
		span_ctx = tracer.extract(Format.TEXT_MAP, carrier)

		# start a new span as a child of the client's span
		span = tracer.start_span(operation_name='greet-service', child_of=span_ctx)

		span.log_event("Created child span from propagated context")

		reply = node1_pb2.HelloReply(
			message='Hello, %s, this is node 1!' % request.name)

		span.log_event("Generated reply")

		# close the span
		span.finish()

		return reply


# start the server
def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    node1_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()


if __name__ == '__main__':
    logging.basicConfig()
    serve()
    tracer.close()