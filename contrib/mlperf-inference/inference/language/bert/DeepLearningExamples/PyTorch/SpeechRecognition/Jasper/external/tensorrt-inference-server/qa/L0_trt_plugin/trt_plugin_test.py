# Copyright (c) 2018-2019, NVIDIA CORPORATION. All rights reserved.
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

import sys
sys.path.append("../common")

from builtins import range
from future.utils import iteritems
import unittest
import numpy as np
from tensorrtserver.api import *
import os

class PluginModelTest(unittest.TestCase):
    def _full_exact(self, batch_size, input_dtype, output_dtype, model_name,
                    plugin_name):
        input_list = list()
        for b in range(batch_size):
            in0 = np.random.randn(16).astype(input_dtype)
            input_list.append(in0)

        ctx = InferContext("localhost:8000", ProtocolType.HTTP, model_name + '_' + plugin_name,
                           correlation_id=0, streaming=False, verbose=True)
        results = ctx.run(
            { "INPUT0" : input_list }, { "OUTPUT0" : InferContext.ResultFormat.RAW},
            batch_size=batch_size)

        self.assertEqual(len(results), 1)
        self.assertTrue("OUTPUT0" in results)
        result = results["OUTPUT0"]

        # Verify values of Leaky RELU (it uses 0.1 instead of the default 0.01)
        # and for CustomClipPlugin min_clip = 0.1, max_clip = 0.5
        for b in range(batch_size):
            if plugin_name == 'LReLU_TRT':
                test_input = np.where(input_list[b] > 0, input_list[b], input_list[b] * 0.1)
                self.assertTrue(all(np.isclose(result[b], test_input)))
            else:
                # [TODO] Add test for CustomClip output
                test_input = np.clip(input_list[b], 0.1, 0.5)

    def test_raw_fff_lrelu(self):
        # model that supports batching
        for bs in (1, 8):
            self._full_exact(bs, np.float32, np.float32, 'plan_float32_float32_float32', 'LReLU_TRT')

    # add test for CustomClipPlugin after model is fixed

if __name__ == '__main__':
    unittest.main()
