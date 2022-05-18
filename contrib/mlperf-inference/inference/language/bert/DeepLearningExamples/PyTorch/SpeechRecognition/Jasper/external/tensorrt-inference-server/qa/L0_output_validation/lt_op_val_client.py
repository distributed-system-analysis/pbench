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

import numpy as np
import requests
import unittest

class OutputValidationTest(unittest.TestCase):
    # for datatype mismatch
    def test_datatype(self):
        url_ = 'http://localhost:8000/api/infer/libtorch_datatype_1_float32'
        input0_data = np.ones((1,)).astype(np.float32)
        headers = {'NV-InferRequest': 'batch_size: 1 input { name: "INPUT__0" } output { name: "OUTPUT__0"}'}
        r = requests.post(url_, data=input0_data.tobytes(), headers=headers)
        print(r.headers)
        self.assertTrue(str(r.headers).find("unexpected datatype") != -1)

    # for index mismatch
    def test_index(self):
        url_ = 'http://localhost:8000/api/infer/libtorch_index_1_float32'
        input0_data = np.ones((1,)).astype(np.float32)
        headers = {'NV-InferRequest': 'batch_size: 1 input { name: "INPUT__0" } output { name: "OUTPUT__1"}'}
        r = requests.post(url_, data=input0_data.tobytes(), headers=headers)
        print(r.headers)
        self.assertTrue(str(r.headers).find("output index which doesn\\\\\\'t exist") != -1)

    # for shape mismatch
    def test_shape(self):
        url_ = 'http://localhost:8000/api/infer/libtorch_shape_1_float32'
        input0_data = np.ones((1,)).astype(np.float32)
        headers = {'NV-InferRequest': 'batch_size: 1 input { name: "INPUT__0" } output { name: "OUTPUT__0"}'}
        r = requests.post(url_, data=input0_data.tobytes(), headers=headers)
        print(r.headers)
        self.assertTrue(str(r.headers).find("unexpected shape for output") != -1)

    # for reshape mismatch
    def test_reshape(self):
        url_ = 'http://localhost:8000/api/infer/libtorch_reshape_1_float32'
        input0_data = np.ones((1,)).astype(np.float32)
        headers = {'NV-InferRequest': 'batch_size: 1 input { name: "INPUT__0" } output { name: "OUTPUT__0"}'}
        r = requests.post(url_, data=input0_data.tobytes(), headers=headers)
        print(r.headers)
        self.assertTrue(str(r.headers).find("model configuration specifies shape") != -1)

    # for naming convention violation
    def test_name(self):
        url_ = 'http://localhost:8000/api/infer/libtorch_name_1_float32'
        input0_data = np.ones((1,)).astype(np.float32)
        headers = {'NV-InferRequest': 'batch_size: 1 input { name: "INPUT0" } output { name: "OUTPUT0"}'}
        r = requests.post(url_, data=input0_data.tobytes(), headers=headers)
        print(r.headers)
        # INTERNAL error (does not load model) hence unavailable
        self.assertTrue(str(r.headers).find("UNAVAILABLE") != -1)

    # successful run
    def test_success(self):
        url_ = 'http://localhost:8000/api/infer/libtorch_zero_1_float32'
        input0_data = np.ones((1,)).astype(np.float32)
        headers = {'NV-InferRequest': 'batch_size: 1 input { name: "INPUT__0" } output { name: "OUTPUT__0"}'}
        r = requests.post(url_, data=input0_data.tobytes(), headers=headers)
        print(r.headers)
        self.assertTrue(str(r.headers).find("SUCCESS") != -1)

if __name__ == '__main__':
    unittest.main()
