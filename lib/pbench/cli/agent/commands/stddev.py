"""
pbench-avg-stddev


input: a bunch of numbers on cmd line
output: an average (mean), sample standard deviation, sample standard deviation
percent, and which input was closest to the average.

nargs = -1, accepts an unlimited number of arguments
"""

import click

import numpy as np


@click.command()
@click.argument("values", nargs=-1, type=click.FLOAT)
def main(values):
    values = list(values)
    avg = np.average(values)
    stddev = np.std(values)
    stddevpct = 100 * stddev / avg

    values = np.array(values)
    closest_index = np.abs(values - avg).argmin() + 1

    print("%.4f %.4f %.4f %d" % (avg, stddev, stddevpct, closest_index))
