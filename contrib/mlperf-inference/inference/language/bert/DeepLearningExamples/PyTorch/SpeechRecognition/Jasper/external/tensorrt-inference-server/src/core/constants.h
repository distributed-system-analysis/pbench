// Copyright (c) 2018-2019, NVIDIA CORPORATION. All rights reserved.
//
// Redistribution and use in source and binary forms, with or without
// modification, are permitted provided that the following conditions
// are met:
//  * Redistributions of source code must retain the above copyright
//    notice, this list of conditions and the following disclaimer.
//  * Redistributions in binary form must reproduce the above copyright
//    notice, this list of conditions and the following disclaimer in the
//    documentation and/or other materials provided with the distribution.
//  * Neither the name of NVIDIA CORPORATION nor the names of its
//    contributors may be used to endorse or promote products derived
//    from this software without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS ``AS IS'' AND ANY
// EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
// PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR
// CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
// EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
// PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
// PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY
// OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
// (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#pragma once

#include <stdint.h>

namespace nvidia { namespace inferenceserver {

constexpr char kInferRequestHTTPHeader[] = "NV-InferRequest";
constexpr char kInferResponseHTTPHeader[] = "NV-InferResponse";
constexpr char kStatusHTTPHeader[] = "NV-Status";

constexpr char kInferRESTEndpoint[] = "api/infer";
constexpr char kStatusRESTEndpoint[] = "api/status";
constexpr char kHealthRESTEndpoint[] = "api/health";
constexpr char kModelControlRESTEndpoint[] = "api/modelcontrol";
constexpr char kSharedMemoryControlRESTEndpoint[] = "api/sharedmemorycontrol";

#ifdef TRTIS_ENABLE_TENSORFLOW
constexpr char kTensorFlowGraphDefPlatform[] = "tensorflow_graphdef";
constexpr char kTensorFlowSavedModelPlatform[] = "tensorflow_savedmodel";
constexpr char kTensorFlowGraphDefFilename[] = "model.graphdef";
constexpr char kTensorFlowSavedModelFilename[] = "model.savedmodel";
#endif  // TRTIS_ENABLE_TENSORFLOW

#ifdef TRTIS_ENABLE_TENSORRT
constexpr char kTensorRTPlanPlatform[] = "tensorrt_plan";
constexpr char kTensorRTPlanFilename[] = "model.plan";
#endif  // TRTIS_ENABLE_TENSORRT

#ifdef TRTIS_ENABLE_CAFFE2
constexpr char kCaffe2NetDefPlatform[] = "caffe2_netdef";
constexpr char kCaffe2NetDefFilename[] = "model.netdef";
constexpr char kCaffe2NetDefInitFilenamePrefix[] = "init_";
#endif  // TRTIS_ENABLE_CAFFE2

#ifdef TRTIS_ENABLE_ONNXRUNTIME
constexpr char kOnnxRuntimeOnnxPlatform[] = "onnxruntime_onnx";
constexpr char kOnnxRuntimeOnnxFilename[] = "model.onnx";
#endif  // TRTIS_ENABLE_ONNXRUNTIME

#ifdef TRTIS_ENABLE_PYTORCH
constexpr char kPyTorchLibTorchPlatform[] = "pytorch_libtorch";
constexpr char kPyTorchLibTorchFilename[] = "model.pt";
#endif  // TRTIS_ENABLE_PYTORCH

#ifdef TRTIS_ENABLE_CUSTOM
constexpr char kCustomPlatform[] = "custom";
constexpr char kCustomFilename[] = "libcustom.so";
#endif  // TRTIS_ENABLE_CUSTOM

constexpr char kTensorRTExecutionAccelerator[] = "tensorrt";
constexpr char kOpenVINOExecutionAccelerator[] = "openvino";
constexpr char kGPUIOExecutionAccelerator[] = "gpu_io";

constexpr char kEnsemblePlatform[] = "ensemble";
constexpr char kModelConfigPbTxt[] = "config.pbtxt";

constexpr char kMetricsLabelModelName[] = "model";
constexpr char kMetricsLabelModelVersion[] = "version";
constexpr char kMetricsLabelGpuUuid[] = "gpu_uuid";

constexpr uint64_t NANOS_PER_SECOND = 1000000000;
constexpr int MAX_GRPC_MESSAGE_SIZE = INT32_MAX;
constexpr int SCHEDULER_DEFAULT_NICE = 5;
constexpr uint64_t SEQUENCE_IDLE_DEFAULT_MICROSECONDS = 1000 * 1000;

#define TIMESPEC_TO_NANOS(TS) \
  ((TS).tv_sec * nvidia::inferenceserver::NANOS_PER_SECOND + (TS).tv_nsec)

#define DISALLOW_MOVE(TypeName) TypeName(Context&& o) = delete;
#define DISALLOW_COPY(TypeName) TypeName(const TypeName&) = delete;
#define DISALLOW_ASSIGN(TypeName) void operator=(const TypeName&) = delete;
#define DISALLOW_COPY_AND_ASSIGN(TypeName) \
  DISALLOW_COPY(TypeName)                  \
  DISALLOW_ASSIGN(TypeName)

}}  // namespace nvidia::inferenceserver
