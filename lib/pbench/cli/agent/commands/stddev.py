import click

import numpy as np


@click.command("values", nargs=-1, type=click.FLOAT)
def main(values):
    values = list(values)
    avg = np.average(values)
    stddev = np.std(values)
    stddevpct = 100 * stddev / avg

    values = np.array(values)
    closest_index = np.abs(values - avg).argmin() + 1

    print("%.4f %.4f %.4f %d" % (avg, stddev, stddevpct, closest_index))
