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
from builtins import range
import os
import sys
import numpy as np
import gen_ensemble_model_utils as emu

FLAGS = None
np_dtype_string = np.dtype(object)

def np_to_model_dtype(np_dtype):
    if np_dtype == np.bool:
        return "TYPE_BOOL"
    elif np_dtype == np.int8:
        return "TYPE_INT8"
    elif np_dtype == np.int16:
        return "TYPE_INT16"
    elif np_dtype == np.int32:
        return "TYPE_INT32"
    elif np_dtype == np.int64:
        return "TYPE_INT64"
    elif np_dtype == np.uint8:
        return "TYPE_UINT8"
    elif np_dtype == np.uint16:
        return "TYPE_UINT16"
    elif np_dtype == np.float16:
        return "TYPE_FP16"
    elif np_dtype == np.float32:
        return "TYPE_FP32"
    elif np_dtype == np.float64:
        return "TYPE_FP64"
    elif np_dtype == np_dtype_string:
        return "TYPE_STRING"
    return None

def np_to_tf_dtype(np_dtype):
    if np_dtype == np.bool:
        return tf.bool
    elif np_dtype == np.int8:
        return tf.int8
    elif np_dtype == np.int16:
        return tf.int16
    elif np_dtype == np.int32:
        return tf.int32
    elif np_dtype == np.int64:
        return tf.int64
    elif np_dtype == np.uint8:
        return tf.uint8
    elif np_dtype == np.uint16:
        return tf.uint16
    elif np_dtype == np.float16:
        return tf.float16
    elif np_dtype == np.float32:
        return tf.float32
    elif np_dtype == np.float64:
        return tf.float64
    elif np_dtype == np_dtype_string:
        return tf.string
    return None

def np_to_c2_dtype(np_dtype):
    if np_dtype == np.bool:
        return c2core.DataType.BOOL
    elif np_dtype == np.int8:
        return c2core.DataType.INT8
    elif np_dtype == np.int16:
        return c2core.DataType.INT16
    elif np_dtype == np.int32:
        return c2core.DataType.INT32
    elif np_dtype == np.int64:
        return c2core.DataType.INT64
    elif np_dtype == np.uint8:
        return c2core.DataType.UINT8
    elif np_dtype == np.uint16:
        return c2core.DataType.UINT16
    elif np_dtype == np.float16:
        return c2core.DataType.FLOAT16
    elif np_dtype == np.float32:
        return c2core.DataType.FLOAT
    elif np_dtype == np.float64:
        return c2core.DataType.DOUBLE
    elif np_dtype == np_dtype_string:
        return c2core.DataType.STRING
    return None

def np_to_trt_dtype(np_dtype):
    if np_dtype == np.int8:
        return trt.infer.DataType.INT8
    elif np_dtype == np.int32:
        return trt.infer.DataType.INT32
    elif np_dtype == np.float16:
        return trt.infer.DataType.HALF
    elif np_dtype == np.float32:
        return trt.infer.DataType.FLOAT
    return None

def np_to_onnx_dtype(np_dtype):
    if np_dtype == np.bool:
        return onnx.TensorProto.BOOL
    elif np_dtype == np.int8:
        return onnx.TensorProto.INT8
    elif np_dtype == np.int16:
        return onnx.TensorProto.INT16
    elif np_dtype == np.int32:
        return onnx.TensorProto.INT32
    elif np_dtype == np.int64:
        return onnx.TensorProto.INT64
    elif np_dtype == np.uint8:
        return onnx.TensorProto.UINT8
    elif np_dtype == np.uint16:
        return onnx.TensorProto.UINT16
    elif np_dtype == np.float16:
        return onnx.TensorProto.FLOAT16
    elif np_dtype == np.float32:
        return onnx.TensorProto.FLOAT
    elif np_dtype == np.float64:
        return onnx.TensorProto.DOUBLE
    elif np_dtype == np_dtype_string:
        return onnx.TensorProto.STRING
    return None

def np_to_torch_dtype(np_dtype):
    if np_dtype == np.bool:
        return torch.bool
    elif np_dtype == np.int8:
        return torch.int8
    elif np_dtype == np.int16:
        return torch.int16
    elif np_dtype == np.int32:
        return torch.int
    elif np_dtype == np.int64:
        return torch.long
    elif np_dtype == np.uint8:
        return torch.uint8
    elif np_dtype == np.uint16:
        return None # Not supported in Torch
    elif np_dtype == np.float16:
        return None
    elif np_dtype == np.float32:
        return torch.float
    elif np_dtype == np.float64:
        return torch.double
    elif np_dtype == np_dtype_string:
        return None # Not supported in Torch

def np_to_trt_dtype(np_dtype):
    if np_dtype == np.int8:
        return trt.infer.DataType.INT8
    elif np_dtype == np.int32:
        return trt.infer.DataType.INT32
    elif np_dtype == np.float16:
        return trt.infer.DataType.HALF
    elif np_dtype == np.float32:
        return trt.infer.DataType.FLOAT
    return None

def create_tf_modelfile(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):

    if not tu.validate_for_tf_model(dtype, dtype, dtype, shape, shape, shape):
        return

    tf_dtype = np_to_tf_dtype(dtype)

    # Create the model that copies inputs to corresponding outputs.
    tf.reset_default_graph()
    for io_num in range(io_cnt):
        input_name = "INPUT{}".format(io_num)
        output_name = "OUTPUT{}".format(io_num)
        if max_batch == 0:
            tin = tf.placeholder(tf_dtype, tu.shape_to_tf_shape(shape), input_name)
        else:
            tin = tf.placeholder(tf_dtype, [None,] + tu.shape_to_tf_shape(shape), input_name)
        toutput = tf.identity(tin, name=output_name)

    # Use model name based on io_cnt and non-batching variant
    if create_savedmodel:
        model_name = tu.get_zero_model_name(
            "savedmodel_nobatch" if max_batch == 0 else "savedmodel", io_cnt, dtype)
    else:
        model_name = tu.get_zero_model_name(
            "graphdef_nobatch" if max_batch == 0 else "graphdef", io_cnt, dtype)

    model_version_dir = models_dir + "/" + model_name + "/" + str(model_version)

    try:
        os.makedirs(model_version_dir)
    except OSError as ex:
        pass # ignore existing dir

    if create_savedmodel:
        with tf.Session() as sess:
            input_dict = {}
            output_dict = {}
            for io_num in range(io_cnt):
                input_name = "INPUT{}".format(io_num)
                output_name = "OUTPUT{}".format(io_num)
                input_tensor = tf.get_default_graph().get_tensor_by_name(input_name + ":0")
                output_tensor = tf.get_default_graph().get_tensor_by_name(output_name + ":0")
                input_dict[input_name] = input_tensor
                output_dict[output_name] = output_tensor
            tf.saved_model.simple_save(sess, model_version_dir + "/model.savedmodel",
                                       inputs=input_dict, outputs=output_dict)
    else:
        with tf.Session() as sess:
            graph_io.write_graph(sess.graph.as_graph_def(), model_version_dir,
                                 "model.graphdef", as_text=False)

def create_tf_modelconfig(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):

    if not tu.validate_for_tf_model(dtype, dtype, dtype, shape, shape, shape):
        return

    shape_str = tu.shape_to_dims_str(shape)

    # Use a different model name for the non-batching variant
    if create_savedmodel:
        model_name = tu.get_zero_model_name(
            "savedmodel_nobatch" if max_batch == 0 else "savedmodel", io_cnt, dtype)
    else:
        model_name = tu.get_zero_model_name(
            "graphdef_nobatch" if max_batch == 0 else "graphdef", io_cnt, dtype)

    config_dir = models_dir + "/" + model_name
    config = '''
name: "{}"
platform: "{}"
max_batch_size: {}
'''.format(model_name,
           "tensorflow_savedmodel" if create_savedmodel else "tensorflow_graphdef",
           max_batch)

    for io_num in range(io_cnt):
        config += '''
input [
  {{
    name: "INPUT{}"
    data_type: {}
    dims: [ {} ]
  }}
]
output [
  {{
    name: "OUTPUT{}"
    data_type: {}
    dims: [ {} ]
  }}
]
'''.format(io_num, np_to_model_dtype(dtype), shape_str,
           io_num, np_to_model_dtype(dtype), shape_str)

    try:
        os.makedirs(config_dir)
    except OSError as ex:
        pass # ignore existing dir

    with open(config_dir + "/config.pbtxt", "w") as cfile:
        cfile.write(config)


def create_netdef_modelfile(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):

    if not tu.validate_for_c2_model(dtype, dtype, dtype, shape, shape, shape):
        return

    c2_dtype = np_to_c2_dtype(dtype)
    model_name = tu.get_zero_model_name(
        "netdef_nobatch" if max_batch == 0 else "netdef", io_cnt, dtype)

    # Create the model that copies inputs to corresponding outputs.
    model = c2model_helper.ModelHelper(name=model_name)
    for io_num in range(io_cnt):
        model.net.Copy("INPUT{}".format(io_num), "OUTPUT{}".format(io_num))
    predict_net, _ = c2model_helper.ExtractPredictorNet(model.Proto(), \
        input_blobs = ["INPUT{}".format(i) for i in range(io_cnt)], \
        output_blobs = ["OUTPUT{}".format(i) for i in range(io_cnt)])

    model_version_dir = models_dir + "/" + model_name + "/" + str(model_version)

    try:
        os.makedirs(model_version_dir)
    except OSError as ex:
        pass # ignore existing dir

    with open(model_version_dir + "/model.netdef", "wb") as f:
        f.write(predict_net.Proto().SerializeToString())
    with open(model_version_dir + "/init_model.netdef", "wb") as f:
        f.write(model.InitProto().SerializeToString())


def create_netdef_modelconfig(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):

    if not tu.validate_for_c2_model(dtype, dtype, dtype, shape, shape, shape):
        return

    shape_str = tu.shape_to_dims_str(shape)

    model_name = tu.get_zero_model_name(
        "netdef_nobatch" if max_batch == 0 else "netdef", io_cnt, dtype)
    config_dir = models_dir + "/" + model_name
    config = '''
name: "{}"
platform: "caffe2_netdef"
max_batch_size: {}
'''.format(model_name, max_batch)

    for io_num in range(io_cnt):
        config += '''
input [
  {{
    name: "INPUT{}"
    data_type: {}
    dims: [ {} ]
  }}
]
output [
  {{
    name: "OUTPUT{}"
    data_type: {}
    dims: [ {} ]
  }}
]
'''.format(io_num, np_to_model_dtype(dtype), shape_str,
           io_num, np_to_model_dtype(dtype), shape_str)

    try:
        os.makedirs(config_dir)
    except OSError as ex:
        pass # ignore existing dir

    with open(config_dir + "/config.pbtxt", "w") as cfile:
        cfile.write(config)



def create_ensemble_modelfile(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):
    if not tu.validate_for_ensemble_model("zero", dtype, dtype, dtype,
                                    shape, shape, shape):
        return

    emu.create_identity_ensemble_modelfile(
        "zero", models_dir, model_version, max_batch,
        dtype, [shape] * io_cnt, [shape] * io_cnt)


def create_ensemble_modelconfig(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):
    if not tu.validate_for_ensemble_model("zero", dtype, dtype, dtype,
                                    shape, shape, shape):
        return

    emu.create_identity_ensemble_modelconfig(
        "zero", models_dir, model_version, max_batch, dtype,
        [shape] * io_cnt, [shape] * io_cnt, [shape] * io_cnt, [shape] * io_cnt)


def create_onnx_modelfile(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):

    if not tu.validate_for_onnx_model(dtype, dtype, dtype, shape, shape, shape):
        return

    onnx_dtype = np_to_onnx_dtype(dtype)

    # Create the model
    model_name = tu.get_zero_model_name("onnx_nobatch" if max_batch == 0 else "onnx",
                                   io_cnt, dtype)
    model_version_dir = models_dir + "/" + model_name + "/" + str(model_version)

    batch_dim = [] if max_batch == 0 else [None]

    onnx_nodes = []
    onnx_inputs = []
    onnx_outputs = []
    idx = 0
    for io_num in range(io_cnt):
        # Repeat so that the variable dimension name is different
        in_shape, idx = tu.shape_to_onnx_shape(shape, idx)
        out_shape, idx = tu.shape_to_onnx_shape(shape, idx)
        in_name = "INPUT{}".format(io_num)
        out_name = "OUTPUT{}".format(io_num)

        onnx_inputs.append(onnx.helper.make_tensor_value_info(in_name, onnx_dtype, batch_dim + in_shape))
        onnx_outputs.append(onnx.helper.make_tensor_value_info(out_name, onnx_dtype, batch_dim + out_shape))
        onnx_nodes.append(onnx.helper.make_node("Identity", [in_name], [out_name]))

    graph_proto = onnx.helper.make_graph(onnx_nodes, model_name, onnx_inputs, onnx_outputs)
    model_def = onnx.helper.make_model(graph_proto, producer_name="TRTIS")

    try:
        os.makedirs(model_version_dir)
    except OSError as ex:
        pass # ignore existing dir

    onnx.save(model_def, model_version_dir + "/model.onnx")


def create_onnx_modelconfig(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):

    if not tu.validate_for_onnx_model(dtype, dtype, dtype, shape, shape, shape):
        return

    # Use a different model name for the non-batching variant
    model_name = tu.get_zero_model_name("onnx_nobatch" if max_batch == 0 else "onnx",
                                   io_cnt, dtype)
    config_dir = models_dir + "/" + model_name

    config = emu.create_general_modelconfig(model_name, "onnxruntime_onnx", max_batch,
            emu.repeat(dtype, io_cnt), emu.repeat(shape, io_cnt), emu.repeat(shape, io_cnt),
            emu.repeat(dtype, io_cnt), emu.repeat(shape, io_cnt), emu.repeat(shape, io_cnt),
            emu.repeat(None, io_cnt), force_tensor_number_suffix=True)

    try:
        os.makedirs(config_dir)
    except OSError as ex:
        pass # ignore existing dir

    with open(config_dir + "/config.pbtxt", "w") as cfile:
        cfile.write(config)


def create_libtorch_modelfile(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):

    if not tu.validate_for_libtorch_model(dtype, dtype, dtype, shape, shape, shape):
        return

    torch_dtype = np_to_torch_dtype(dtype)

    model_name = tu.get_zero_model_name("libtorch_nobatch" if max_batch == 0 else "libtorch",
                                   io_cnt, dtype)
    # handle for -1 (when variable) since can't create tensor with shape of [-1]
    torch_shape = [abs(s) for s in shape]
    # Create the model
    if io_cnt == 1:
        class IdentityNet(nn.Module):
            def __init__(self):
                super(IdentityNet, self).__init__()
            def forward(self, input0):
                return input0
    elif io_cnt == 2:
        class IdentityNet(nn.Module):
            def __init__(self):
                super(IdentityNet, self).__init__()
            def forward(self, input0, input1):
                return input0, input1
    elif io_cnt == 3:
        class IdentityNet(nn.Module):
            def __init__(self):
                super(IdentityNet, self).__init__()
            def forward(self, input0, input1, input2):
                return input0, input1, input2
    elif io_cnt == 4:
        class IdentityNet(nn.Module):
            def __init__(self):
                super(IdentityNet, self).__init__()
            def forward(self, input0, input1, input2, input3):
                return input0, input1, input2, input3
    identityModel = IdentityNet()
    example_inputs = [torch.zeros(torch_shape, dtype=torch_dtype) for i in range(io_cnt)]
    traced = torch.jit.trace(identityModel, tuple(example_inputs[i] for i in range(io_cnt)))

    model_version_dir = models_dir + "/" + model_name + "/" + str(model_version)

    try:
        os.makedirs(model_version_dir)
    except OSError as ex:
        pass # ignore existing dir

    traced.save(model_version_dir + "/model.pt")


def create_libtorch_modelconfig(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):

    if not tu.validate_for_libtorch_model(dtype, dtype, dtype, shape, shape, shape):
        return

    # Unpack version policy
    version_policy_str = "{ latest { num_versions: 1 }}"

    # Use a different model name for the non-batching variant
    model_name = tu.get_zero_model_name("libtorch_nobatch" if max_batch == 0 else "libtorch",
                                   io_cnt, dtype)
    shape_str = tu.shape_to_dims_str(shape)

    config_dir = models_dir + "/" + model_name
    config = '''
name: "{}"
platform: "pytorch_libtorch"
max_batch_size: {}
version_policy: {}
'''.format(model_name, max_batch, version_policy_str)

    for io_num in range(io_cnt):
        config += '''
input [
  {{
    name: "INPUT__{}"
    data_type: {}
    dims: [ {} ]
  }}
]
output [
  {{
    name: "OUTPUT__{}"
    data_type: {}
    dims: [ {} ]
  }}
]
'''.format(io_num, np_to_model_dtype(dtype), shape_str,
           io_num, np_to_model_dtype(dtype), shape_str)

    try:
        os.makedirs(config_dir)
    except OSError as ex:
        pass # ignore existing dir

    with open(config_dir + "/config.pbtxt", "w") as cfile:
        cfile.write(config)


def create_plan_modelfile(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch,
        dtype, shape, profile_max_size):

    if not tu.validate_for_trt_model(dtype, dtype, dtype, shape, shape, shape):
        return

    # generate models with different configuration to ensure test coverage
    if dtype != np.float32:
        create_plan_dynamic_rf_modelfile(
            models_dir, model_version, io_cnt, max_batch, dtype, shape, profile_max_size)
    else:
        create_plan_dynamic_modelfile(
            models_dir, model_version, io_cnt, max_batch, dtype, shape, profile_max_size)

def create_plan_dynamic_rf_modelfile(
        models_dir, model_version, io_cnt, max_batch, dtype, shape, profile_max_size):
    # Create the model
    G_LOGGER = trt.infer.ConsoleLogger(trt.infer.LogSeverity.INFO)
    builder = trt.infer.create_infer_builder(G_LOGGER)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    if max_batch == 0:
        shape_with_batchsize = [i for i in shape]
    else:
        shape_with_batchsize = [-1] + [i for i in shape]

    trt_dtype = np_to_trt_dtype(dtype)
    trt_memory_format = trt.TensorFormat.LINEAR
    for io_num in range(io_cnt):
        in_node = network.add_input("INPUT{}".format(io_num), trt_dtype, shape_with_batchsize)
        in_node.allowed_formats = 1 << int(trt_memory_format)

        out_node = network.add_identity(in_node)

        out_node.get_output(0).set_name("OUTPUT{}".format(io_num))
        out_node.get_output(0).set_type(trt_dtype)
        network.mark_output(out_node.get_output(0))
        out_node.get_output(0).allowed_formats = 1 << int(trt_memory_format)

        if (trt_dtype == trt.DataType.INT8):
            in_node.dynamic_range = (-128.0, 127.0)
            out_node.get_output(0).dynamic_range = (-128.0, 127.0)

    min_shape = []
    opt_shape = []
    max_shape = []
    if max_batch != 0:
        min_shape = min_shape + [1]
        opt_shape = opt_shape + [max(1, max_batch)]
        max_shape = max_shape + [max(1, max_batch)]
    for i in shape:
        if i == -1:
            # Generating a very generous optimization profile
            min_shape = min_shape + [1]
            opt_shape = opt_shape + [8]
            max_shape = max_shape + [profile_max_size]
        else:
            min_shape = min_shape + [i]
            opt_shape = opt_shape + [i]
            max_shape = max_shape + [i]

    profile = builder.create_optimization_profile()
    profile = builder.create_optimization_profile()
    for io_num in range(io_cnt):
        profile.set_shape("INPUT{}".format(io_num), min_shape, opt_shape, max_shape)

    flags = 1 <<  int(trt.BuilderFlag.STRICT_TYPES)
    datatype_set = set([trt_dtype])
    for dt in datatype_set:
        if (dt == trt.DataType.INT8):
            builder.int8_mode = True
            flags |= 1 << int(trt.BuilderFlag.INT8)
        elif (dt == trt.DataType.HALF):
            builder.fp16_mode = True
            flags |= 1 << int(trt.BuilderFlag.FP16)
    builder.strict_type_constraints = True
    config = builder.create_builder_config()
    config.flags=flags
    config.add_optimization_profile(profile)
    builder.set_max_workspace_size(1 << 20)
    engine = builder.build_engine(network,config)


    model_name = tu.get_zero_model_name(
        "plan_nobatch" if max_batch == 0 else "plan", io_cnt, dtype)
    model_version_dir = models_dir + "/" + model_name + "/" + str(model_version)

    try:
        os.makedirs(model_version_dir)
    except OSError as ex:
        pass # ignore existing dir

    with open(model_version_dir + "/model.plan", "wb") as f:
        f.write(engine.serialize())

    engine.destroy()
    builder.destroy()


def create_plan_dynamic_modelfile(
        models_dir, model_version, io_cnt, max_batch, dtype, shape, profile_max_size):
    # Create the model
    G_LOGGER = trt.infer.ConsoleLogger(trt.infer.LogSeverity.INFO)
    builder = trt.infer.create_infer_builder(G_LOGGER)
    network = builder.create_network(1 << int(trt.NetworkDefinitionCreationFlag.EXPLICIT_BATCH))
    if max_batch == 0:
        shape_with_batchsize = [i for i in shape]
    else:
        shape_with_batchsize = [-1] + [i for i in shape]

    trt_dtype = np_to_trt_dtype(dtype)
    for io_num in range(io_cnt):
        in_node = network.add_input("INPUT{}".format(io_num), trt_dtype, shape_with_batchsize)
        out_node = network.add_identity(in_node)
        out_node.get_output(0).set_name("OUTPUT{}".format(io_num))
        network.mark_output(out_node.get_output(0))

    min_shape = []
    opt_shape = []
    max_shape = []
    if max_batch != 0:
        min_shape = min_shape + [1]
        opt_shape = opt_shape + [max(1, max_batch)]
        max_shape = max_shape + [max(1, max_batch)]
    for i in shape:
        if i == -1:
            # Generating a very generous optimization profile
            min_shape = min_shape + [1]
            opt_shape = opt_shape + [8]
            max_shape = max_shape + [profile_max_size]
        else:
            min_shape = min_shape + [i]
            opt_shape = opt_shape + [i]
            max_shape = max_shape + [i]

    profile = builder.create_optimization_profile()
    for io_num in range(io_cnt):
        profile.set_shape("INPUT{}".format(io_num), min_shape, opt_shape, max_shape)
    config = builder.create_builder_config()
    config.add_optimization_profile(profile)
    builder.set_max_workspace_size(1 << 20)
    engine = builder.build_engine(network,config)

    model_name = tu.get_zero_model_name(
        "plan_nobatch" if max_batch == 0 else "plan", io_cnt, dtype)
    model_version_dir = models_dir + "/" + model_name + "/" + str(model_version)

    try:
        os.makedirs(model_version_dir)
    except OSError as ex:
        pass # ignore existing dir

    with open(model_version_dir + "/model.plan", "wb") as f:
        f.write(engine.serialize())

    engine.destroy()
    builder.destroy()


def create_plan_modelconfig(
        create_savedmodel, models_dir, model_version, io_cnt, max_batch, dtype, shape):
    if not tu.validate_for_trt_model(dtype, dtype, dtype, shape, shape, shape):
        return

    shape_str = tu.shape_to_dims_str(shape)

    model_name = tu.get_zero_model_name(
        "plan_nobatch" if max_batch == 0 else "plan", io_cnt, dtype)
    config_dir = models_dir + "/" + model_name
    config = '''
name: "{}"
platform: "tensorrt_plan"
max_batch_size: {}
'''.format(model_name, max_batch)

    for io_num in range(io_cnt):
        config += '''
input [
  {{
    name: "INPUT{}"
    data_type: {}
    dims: [ {} ]
  }}
]
output [
  {{
    name: "OUTPUT{}"
    data_type: {}
    dims: [ {} ]
  }}
]
'''.format(io_num, np_to_model_dtype(dtype), shape_str,
           io_num, np_to_model_dtype(dtype), shape_str)

    try:
        os.makedirs(config_dir)
    except OSError as ex:
        pass # ignore existing dir

    with open(config_dir + "/config.pbtxt", "w") as cfile:
        cfile.write(config)


def create_models(models_dir, dtype, shape, io_cnt=1, no_batch=True):
    model_version = 1

    if FLAGS.graphdef:
        create_tf_modelconfig(False, models_dir, model_version, io_cnt, 8, dtype, shape)
        create_tf_modelfile(False, models_dir, model_version, io_cnt, 8, dtype, shape)
        if no_batch:
            create_tf_modelconfig(False, models_dir, model_version, io_cnt, 0, dtype, shape)
            create_tf_modelfile(False, models_dir, model_version, io_cnt, 0, dtype, shape)

    if FLAGS.savedmodel:
        create_tf_modelconfig(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        create_tf_modelfile(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        if no_batch:
            create_tf_modelconfig(True, models_dir, model_version, io_cnt, 0, dtype, shape)
            create_tf_modelfile(True, models_dir, model_version, io_cnt, 0, dtype, shape)

    if FLAGS.netdef:
        create_netdef_modelconfig(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        create_netdef_modelfile(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        if no_batch:
            create_netdef_modelconfig(True, models_dir, model_version, io_cnt, 0, dtype, shape)
            create_netdef_modelfile(True, models_dir, model_version, io_cnt, 0, dtype, shape)

    if FLAGS.onnx:
        create_onnx_modelconfig(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        create_onnx_modelfile(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        if no_batch:
            create_onnx_modelconfig(True, models_dir, model_version, io_cnt, 0, dtype, shape)
            create_onnx_modelfile(True, models_dir, model_version, io_cnt, 0, dtype, shape)

    if FLAGS.libtorch:
        create_libtorch_modelconfig(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        create_libtorch_modelfile(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        if no_batch:
            create_libtorch_modelconfig(True, models_dir, model_version, io_cnt, 0, dtype, shape)
            create_libtorch_modelfile(True, models_dir, model_version, io_cnt, 0, dtype, shape)

    if FLAGS.tensorrt:
        create_plan_modelconfig(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        create_plan_modelfile(True, models_dir, model_version, io_cnt, 8, dtype, shape, 32)
        if no_batch:
            create_plan_modelconfig(True, models_dir, model_version, io_cnt, 0, dtype, shape)
            create_plan_modelfile(True, models_dir, model_version, io_cnt, 0, dtype, shape, 32)

    if FLAGS.tensorrt_big:
        create_plan_modelconfig(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        create_plan_modelfile(True, models_dir, model_version, io_cnt, 8,
                              dtype, shape, 16 * 1024 * 1024)
        if no_batch:
            create_plan_modelconfig(True, models_dir, model_version, io_cnt, 0, dtype, shape)
            create_plan_modelfile(True, models_dir, model_version, io_cnt, 0,
                                  dtype, shape, 16 * 1024 * 1024)

    if FLAGS.ensemble:
        emu.create_nop_modelconfig(models_dir, shape, dtype)
        create_ensemble_modelconfig(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        create_ensemble_modelfile(True, models_dir, model_version, io_cnt, 8, dtype, shape)
        if no_batch:
            create_ensemble_modelconfig(True, models_dir, model_version, io_cnt, 0, dtype, shape)
            create_ensemble_modelfile(True, models_dir, model_version, io_cnt, 0, dtype, shape)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--models_dir', type=str, required=True,
                        help='Top-level model directory')
    parser.add_argument('--graphdef', required=False, action='store_true',
                        help='Generate GraphDef models')
    parser.add_argument('--savedmodel', required=False, action='store_true',
                        help='Generate SavedModel models')
    parser.add_argument('--netdef', required=False, action='store_true',
                        help='Generate NetDef models')
    parser.add_argument('--onnx', required=False, action='store_true',
                        help='Generate Onnx Runtime Onnx models')
    parser.add_argument('--libtorch', required=False, action='store_true',
                        help='Generate Pytorch LibTorch models')
    parser.add_argument('--tensorrt', required=False, action='store_true',
                        help='Generate TensorRT PLAN models')
    parser.add_argument('--tensorrt-big', required=False, action='store_true',
                        help='Generate TensorRT PLAN models w/ opt profile with large max')
    parser.add_argument('--ensemble', required=False, action='store_true',
                        help='Generate ensemble models')
    FLAGS, unparsed = parser.parse_known_args()

    if FLAGS.netdef:
        from caffe2.python import core as c2core
        from caffe2.python import model_helper as c2model_helper
    if FLAGS.graphdef or FLAGS.savedmodel:
        import tensorflow as tf
        from tensorflow.python.framework import graph_io, graph_util
    if FLAGS.onnx:
        import onnx
    if FLAGS.libtorch:
        import torch
        from torch import nn
    if FLAGS.tensorrt or FLAGS.tensorrt_big:
        import tensorrt.legacy as trt

    import test_util as tu

    # Create models with variable-sized input and output. For big
    # TensorRT models only create the one needed for performance
    # testing
    if FLAGS.tensorrt_big:
        create_models(FLAGS.models_dir, np.float32, [-1], io_cnt=1)
    else:
        create_models(FLAGS.models_dir, np.float32, [-1], io_cnt=1)
        create_models(FLAGS.models_dir, np.float32, [-1], io_cnt=3)
        create_models(FLAGS.models_dir, np.float16, [-1,-1], io_cnt=1)
        create_models(FLAGS.models_dir, np.float16, [-1,-1], io_cnt=3)
        create_models(FLAGS.models_dir, np_dtype_string, [-1], io_cnt=1)
        create_models(FLAGS.models_dir, np_dtype_string, [-1,-1], io_cnt=3)
