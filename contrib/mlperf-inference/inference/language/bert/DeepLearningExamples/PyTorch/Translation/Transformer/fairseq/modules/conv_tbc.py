# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the license found in the LICENSE file in
# the root directory of this source tree. An additional grant of patent rights
# can be found in the PATENTS file in the same directory.

import torch
from torch.nn.modules.utils import _single


class ConvTBC(torch.nn.Module):
    """1D convolution over an input of shape (time x batch x channel)

    The implementation uses gemm to perform the convolution. This implementation
    is faster than cuDNN for small kernel sizes.
    """
    def __init__(self, in_channels, out_channels, kernel_size, padding=0):
        super(ConvTBC, self).__init__()
        self.in_channels = in_channels
        self.out_channels = out_channels
        self.kernel_size = _single(kernel_size)
        self.padding = _single(padding)

        self.weight = torch.nn.Parameter(torch.Tensor(
            self.kernel_size[0], in_channels, out_channels))
        self.bias = torch.nn.Parameter(torch.Tensor(out_channels))

    def forward(self, input):
        return input.contiguous().conv_tbc(self.weight, self.bias, self.padding[0])

    def __repr__(self):
        s = ('{name}({in_channels}, {out_channels}, kernel_size={kernel_size}'
             ', padding={padding}')
        if self.bias is None:
            s += ', bias=False'
        s += ')'
        return s.format(name=self.__class__.__name__, **self.__dict__)
