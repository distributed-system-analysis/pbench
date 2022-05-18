#!/usr/bin/env python3
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

from typing import List
import sys
import argparse
import re

watts_value_reg_exp = re.compile("Watts,([-]?[0-9]+[.][0-9]+)")


def get_values(path: str) -> List[float]:
    watts_values = []
    try:
        with open(path, "r") as log:
            lines = log.readlines()
            if len(lines) == 0:
                print(f"{path} is empty", file=sys.stderr)
                exit(2)
            for line in lines:
                watts = watts_value_reg_exp.findall(line)[0]
                watts_values.append(float(watts))
    except FileNotFoundError:
        print(f"{path} does not exist", file=sys.stderr)
        exit(2)
    except IndexError:
        print(f"There are no watts values in {path}", file=sys.stderr)
        exit(2)
    return watts_values


def are_charts_identical(
    ranging_values: List[float], testing_values: List[float], uncertainty: float
) -> bool:
    min_len = min(len(ranging_values), len(testing_values))
    longest_list = ranging_values if min_len == len(testing_values) else testing_values
    diff_sum = 0.0
    ranging_sum = 0.0
    for i in range(min_len):
        diff_sum += abs(ranging_values[i] - testing_values[i])
    for i in range(min_len, len(longest_list)):
        diff_sum += longest_list[i]
    for el in ranging_values:
        ranging_sum += el
    charts_identity = diff_sum / ranging_sum * 100
    print(f"Charts differ by {charts_identity}%", file=sys.stderr)
    return charts_identity < uncertainty


parser = argparse.ArgumentParser(
    description="Compare two power log files (spl.txt) with a given threshold",
    formatter_class=lambda prog: argparse.RawDescriptionHelpFormatter(
        prog, max_help_position=35
    ),
)

parser.add_argument("spl_log1", help="spl file path")
parser.add_argument("spl_log2", help="spl file path")
parser.add_argument(
    "-u",
    "--uncertainty",
    type=float,
    default=10,
    help="required uncertainty in percent. Default is 10 (percent)",
)

args = parser.parse_args()

if args.uncertainty > 100 or args.uncertainty < 0:
    print("Uncertainty should be in range 0..100", file=sys.stderr)
    exit(2)

watts_values1 = get_values(args.spl_log1)
watts_values2 = get_values(args.spl_log2)

if are_charts_identical(watts_values1, watts_values2, args.uncertainty):
    print("Charts are nearly identical", file=sys.stderr)
else:
    print("Charts are not identical", file=sys.stderr)
    exit(1)
