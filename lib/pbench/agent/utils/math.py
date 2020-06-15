import numpy as np


def calculate_stddev(values=None):
    values = list(values)
    avg = np.average(values)
    stddev = np.std(values)
    stddevpct = 100 * stddev / avg

    values = np.array(values)
    closest_index = np.abs(values - avg).argmin() + 1

    return (avg, stddev, stddevpct, closest_index)
