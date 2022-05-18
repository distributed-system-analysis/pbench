#!/bin/bash
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

REPO_VERSION=${NVIDIA_TENSORRT_SERVER_VERSION}
if [ "$#" -ge 1 ]; then
    REPO_VERSION=$1
fi
if [ -z "$REPO_VERSION" ]; then
    echo -e "Repository version must be specified"
    echo -e "\n***\n*** Test Failed\n***"
    exit 1
fi

IO_TEST_UTIL=./memory_alloc
CLIENT_LOG="./client.log"
MODELSDIR=`pwd`/models

DATADIR=/data/inferenceserver/${REPO_VERSION}/qa_model_repository
ENSEMBLEDIR=/data/inferenceserver/${REPO_VERSION}/qa_ensemble_model_repository/qa_model_repository

export CUDA_VISIBLE_DEVICES=0,1

rm -f $CLIENT_LOG.*

RET=0

# Prepare models with basic config
rm -rf $MODELSDIR
for trial in graphdef savedmodel netdef onnx libtorch plan ; do
    full=${trial}_float32_float32_float32
    mkdir -p $MODELSDIR/${full}/1 && \
        cp -r $DATADIR/${full}/1/* $MODELSDIR/${full}/1/. && \
        cp $DATADIR/${full}/config.pbtxt $MODELSDIR/${full}/. && \
        (cd $MODELSDIR/${full} && \
                sed -i "s/label_filename:.*//" config.pbtxt && \
                echo "instance_group [{ kind: KIND_CPU }]" >> config.pbtxt)

    # set up "addsub" ensemble.
    # [DLIS-843] Not copying the correspondent in ENSEMBLEDIR
    # because some backends (ONNX, PyTorch) don't have ensemble for them
    mkdir -p $MODELSDIR/fan_${full}/1 && \
    cp $ENSEMBLEDIR/fan_graphdef_float32_float32_float32/config.pbtxt $MODELSDIR/fan_${full}/. && \
        (cd $MODELSDIR/fan_${full} && \
                sed -i "s/graphdef_float32_float32_float32/${full}/" config.pbtxt && \
                sed -i "s/label_filename:.*//" config.pbtxt)

    if [ "$trial" == "libtorch" ]; then
        (cd $MODELSDIR/fan_${full} && \
                sed -i -e '{
                    N
                    s/key: "INPUT\([0-9]\)"\n\(.*\)value: "same_input/key: "INPUT__\1"\n\2value: "same_input/
                }' config.pbtxt && \
                sed -i -e '{
                    N
                    s/key: "OUTPUT\([0-9]\)"\n\(.*\)value: "same_output/key: "OUTPUT__\1"\n\2value: "same_output/
                }' config.pbtxt)
    fi
done

# custom model needs to be obtained elsewhere
full=custom_float32_float32_float32
rm -rf $MODELSDIR/${full}/1/*
mkdir -p $MODELSDIR/${full}/1 && \
    cp -r ../custom_models/${full}/1/* $MODELSDIR/${full}/1/. && \
    cp ../custom_models/${full}/config.pbtxt $MODELSDIR/${full}/.
        (cd $MODELSDIR/${full} && \
                sed -i "s/label_filename:.*//" config.pbtxt && \
                echo "instance_group [{ kind: KIND_CPU }]" >> config.pbtxt)

# set up "addsub" ensemble for custom model
cp -r $MODELSDIR/fan_graphdef_float32_float32_float32 $MODELSDIR/fan_${full} && \
    (cd $MODELSDIR/fan_${full} && \
            sed -i "s/graphdef_float32_float32_float32/${full}/" config.pbtxt)

# custom component of ensemble
cp -r $ENSEMBLEDIR/nop_TYPE_FP32_-1 $MODELSDIR/. && \
    mkdir -p $MODELSDIR/nop_TYPE_FP32_-1/1 && \
    cp libidentity.so $MODELSDIR/nop_TYPE_FP32_-1/1/.

for input_device in -1 0 1; do
    for output_device in -1 0 1; do
        for trial in graphdef savedmodel netdef onnx libtorch plan custom; do
            # TensorRT Plan should only be deployed on GPU device
            model_devices="-1 0 1" && [[ "$trial" == "plan" ]] && model_devices="0 1"
            for model_device in $model_devices; do
                full=${trial}_float32_float32_float32
                full_log=$CLIENT_LOG.$trial.$input_device.$output_device.$model_device
                
                if [ "$model_device" == "-1" ]; then
                    (cd $MODELSDIR/${full} && \
                        sed -i "s/instance_group.*/instance_group [{ kind: KIND_CPU }]/" config.pbtxt)
                else
                    (cd $MODELSDIR/${full} && \
                        sed -i "s/instance_group.*/instance_group [{ kind: KIND_GPU, gpus: [${model_device}] }]/" config.pbtxt)
                fi
                
                set +e
                $IO_TEST_UTIL -i $input_device -o $output_device -r $MODELSDIR -m $full >>$full_log 2>&1
                if [ $? -ne 0 ]; then
                    cat $full_log
                    echo -e "\n***\n*** Test Failed\n***"
                    RET=1
                fi
                set -e

                # ensemble
                set +e
                $IO_TEST_UTIL -i $input_device -o $output_device -r $MODELSDIR -m fan_$full >>$full_log.ensemble 2>&1
                if [ $? -ne 0 ]; then
                    cat $full_log.ensemble
                    echo -e "\n***\n*** Test Failed\n***"
                    RET=1
                fi
                set -e
            done
        done
    done
done

if [ $RET -eq 0 ]; then
    echo -e "\n***\n*** Test Passed\n***"
else
    echo -e "\n***\n*** Test FAILED\n***"
fi

exit $RET
