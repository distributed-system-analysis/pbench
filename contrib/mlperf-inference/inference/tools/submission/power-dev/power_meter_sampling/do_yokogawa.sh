#!/bin/bash
# Copyright 2018 The MLPerf Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# =============================================================================


usage(){
    echo "Usage: $0 -i <interval> -d <duration>"
}

is_number() {
    number=$1
    if ! [[ "$number" =~ ^[0-9]+$ ]] ; then
        usage
        exit 1
    fi
}

sampling_interval=2
sampling_duration=60

while getopts "i:d:h" opt; do
    case ${opt} in
    i  ) is_number $OPTARG ; sampling_interval=$OPTARG ;;
    d  ) is_number $OPTARG ; sampling_duration=$OPTARG ;;
    h  ) usage; exit 0 ;;
    \? ) usage; exit 1 ;;
    :  ) echo "Invalid option: $OPTARG requires an argument" 1>&2; exit 1 ;;
  esac
done

logfile=sample_metrics_$(hostname -s)_$(date '+%Y-%m-%d_%H-%M-%S')_${sampling_interval}_${sampling_duration}.log

python3 sample_metrics.py -v \
        -I $sampling_interval \
        -D $sampling_duration \
        -l $logfile \
        samplers.yokogawa

