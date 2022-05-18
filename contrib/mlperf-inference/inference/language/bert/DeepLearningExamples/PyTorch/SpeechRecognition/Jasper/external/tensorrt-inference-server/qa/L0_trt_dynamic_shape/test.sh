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

CLIENT_LOG="./client.log"
PERF_CLIENT=../clients/perf_client

DATADIR="./models"

mkdir -p ${DATADIR}
cp -r /data/inferenceserver/${REPO_VERSION}/qa_variable_model_repository/plan_float32_float32_float32-4-32 ${DATADIR}/

SERVER=/opt/tensorrtserver/bin/trtserver
SERVER_ARGS=--model-repository=$DATADIR
SERVER_LOG="./inference_server.log"
source ../common/util.sh

rm -f $SERVER_LOG ${CLIENT_LOG}*

RET=0

run_server
if [ "$SERVER_PID" == "0" ]; then
    echo -e "\n***\n*** Failed to start $SERVER\n***"
    cat $SERVER_LOG
    exit 1
fi

# Shape beyond the limits of optimization profile
set +e
$PERF_CLIENT -v -i grpc -u localhost:8001 -m plan_float32_float32_float32-4-32 --shape INPUT0:33 --shape INPUT1:33 -t 1 -p2000 -b 1 > ${CLIENT_LOG}_max 2>&1
if [ $? -eq 0 ]; then
    cat ${CLIENT_LOG}_max
    echo -e "\n***\n*** Test Failed\n***"
    RET=1
fi

EXPECTED_MESSAGE="The shape of dimension 1 is expected to be in range from 4 to 32, Got:"
if [ $(cat ${CLIENT_LOG}_max | grep "${EXPECTED_MESSAGE} 33" | wc -l) -eq 0 ]; then
    cat ${CLIENT_LOG}_max
    echo -e "\n***\n*** Test Failed\n***"
    RET=1
fi

$PERF_CLIENT -v -i grpc -u localhost:8001 -m plan_float32_float32_float32-4-32 --shape INPUT0:3 --shape INPUT1:3 -t 1 -p2000 -b 1 > ${CLIENT_LOG}_min 2>&1
if [ $? -eq 0 ]; then
    cat ${CLIENT_LOG}_min
    echo -e "\n***\n*** Test Failed\n***"
    RET=1
fi
if [ $(cat ${CLIENT_LOG}_min | grep "${EXPECTED_MESSAGE} 3" | wc -l) -eq 0 ]; then
    cat ${CLIENT_LOG}_min
    echo -e "\n***\n*** Test Failed\n***"
    RET=1
fi

set -e

kill $SERVER_PID
wait $SERVER_PID

if [ $RET -eq 0 ]; then
  echo -e "\n***\n*** Test Passed\n***"
fi

exit $RET


