"""
pbench-avg-stddev


input: a bunch of numbers on cmd line
output: an average (mean), sample standard deviation, sample standard deviation
percent, and which input was closest to the average.

nargs = -1, accepts an unlimited number of arguments
"""

import click

import statistics


@click.command()
@click.argument("values", nargs=-1, type=click.FLOAT)
def main(values):
    values = list(values)
    avg = statistics.mean(values)
    stddev = statistics.stdev(values)
    stddevpct = 100 * stddev / avg

    closest_index = min(range(len(values)), key=lambda i: abs(values[i] - avg))

    print("%.4f %.4f %.4f %d" % (avg, stddev, stddevpct, closest_index))
