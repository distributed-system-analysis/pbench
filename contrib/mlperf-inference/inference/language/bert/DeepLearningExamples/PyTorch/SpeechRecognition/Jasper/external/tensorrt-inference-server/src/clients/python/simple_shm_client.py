#!/usr/bin/python
# Copyright (c) 2019, NVIDIA CORPORATION. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
#  * Neither the name of NVIDIA CORPORATION nor the names of its
#    contributors may be used to endorse or promote products derived
#    from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
# OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import argparse
import numpy as np
import os
from builtins import range
from tensorrtserver.api import *
import tensorrtserver.shared_memory as shm
from ctypes import *

FLAGS = None

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action="store_true", required=False, default=False,
                        help='Enable verbose output')
    parser.add_argument('-u', '--url', type=str, required=False, default='localhost:8000',
                        help='Inference server URL. Default is localhost:8000.')
    parser.add_argument('-i', '--protocol', type=str, required=False, default='http',
                        help='Protocol ("http"/"grpc") used to ' +
                        'communicate with inference service. Default is "http".')
    parser.add_argument('-H', dest='http_headers', metavar="HTTP_HEADER",
                        required=False, action='append',
                        help='HTTP headers to add to inference server requests. ' +
                        'Format is -H"Header:Value".')

    FLAGS = parser.parse_args()
    protocol = ProtocolType.from_str(FLAGS.protocol)

    # We use a simple model that takes 2 input tensors of 16 integers
    # each and returns 2 output tensors of 16 integers each. One
    # output tensor is the element-wise sum of the inputs and one
    # output is the element-wise difference.
    model_name = "simple"
    model_version = -1
    batch_size = 1

    # Create a health context, get the ready and live state of server.
    health_ctx = ServerHealthContext(FLAGS.url, protocol,
                                     http_headers=FLAGS.http_headers, verbose=FLAGS.verbose)
    print("Health for model {}".format(model_name))
    print("Live: {}".format(health_ctx.is_live()))
    print("Ready: {}".format(health_ctx.is_ready()))

    # Create a status context and get server status
    status_ctx = ServerStatusContext(FLAGS.url, protocol, model_name,
                                     http_headers=FLAGS.http_headers, verbose=FLAGS.verbose)
    print("Status for model {}".format(model_name))
    print(status_ctx.get_server_status())

    # Create the inference context for the model.
    infer_ctx = InferContext(FLAGS.url, protocol, model_name, model_version,
                             http_headers=FLAGS.http_headers, verbose=FLAGS.verbose)

    # Create the shared memory control context
    shared_memory_ctx = SharedMemoryControlContext(FLAGS.url, protocol, \
                            http_headers=FLAGS.http_headers, verbose=FLAGS.verbose)

    # Create the data for the two input tensors. Initialize the first
    # to unique integers and the second to all ones.
    input0_data = np.arange(start=0, stop=16, dtype=np.int32)
    input1_data = np.ones(shape=16, dtype=np.int32)

    input_byte_size = input0_data.size * input0_data.itemsize
    output_byte_size = input_byte_size

    # Create Output0 and Output1 in Shared Memory and store shared memory handle
    shm_op0_handle = shm.create_shared_memory_region("output0_data", "/output0_simple", output_byte_size)
    shm_op1_handle = shm.create_shared_memory_region("output1_data", "/output1_simple", output_byte_size)

    # Register Output0 and Output1 shared memory with TRTIS
    shared_memory_ctx.register(shm_op0_handle)
    shared_memory_ctx.register(shm_op1_handle)

    # Create Input0 and Input1 in Shared Memory and store shared memory handle
    shm_ip0_handle = shm.create_shared_memory_region("input0_data", "/input0_simple", input_byte_size)
    shm_ip1_handle = shm.create_shared_memory_region("input1_data", "/input1_simple", input_byte_size)

    # Put input data values into shared memory
    shm.set_shared_memory_region(shm_ip0_handle, [input0_data])
    shm.set_shared_memory_region(shm_ip1_handle, [input1_data])

    # Register Input0 and Input1 shared memory with TRTIS
    shared_memory_ctx.register(shm_ip0_handle)
    shared_memory_ctx.register(shm_ip1_handle)

    # Send inference request to the inference server. Get results for
    # both output tensors.
    results = infer_ctx.run({ 'INPUT0' : shm_ip0_handle,
                            'INPUT1' : shm_ip1_handle, },
                            { 'OUTPUT0' : (InferContext.ResultFormat.RAW, shm_op0_handle),
                            'OUTPUT1' : (InferContext.ResultFormat.RAW, shm_op1_handle) },
                            batch_size)

    # Read output from shared memory
    output0_data = results['OUTPUT0'][0]
    output1_data = results['OUTPUT1'][0]

    # We expect there to be 2 results (each with batch-size 1). Walk
    # over all 16 result elements and print the sum and difference
    # calculated by the model.
    for i in range(16):
        print(str(input0_data[i]) + " + " + str(input1_data[i]) + " = " + str(output0_data[i]))
        print(str(input0_data[i]) + " - " + str(input1_data[i]) + " = " + str(output1_data[i]))
        if (input0_data[i] + input1_data[i]) != output0_data[i]:
            print("error: incorrect sum");
            sys.exit(1);
        if (input0_data[i] - input1_data[i]) != output1_data[i]:
            print("error: incorrect difference");
            sys.exit(1);

    del results
    print(shared_memory_ctx.get_shared_memory_status())
    shared_memory_ctx.unregister_all()
    shm.destroy_shared_memory_region(shm_ip0_handle)
    shm.destroy_shared_memory_region(shm_ip1_handle)
    shm.destroy_shared_memory_region(shm_op0_handle)
    shm.destroy_shared_memory_region(shm_op1_handle)
