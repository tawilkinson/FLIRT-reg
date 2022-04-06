import numpy as np
from enum import Enum


class Indexing(Enum):
    orig = 1
    rand = 2
    alternate = 3


def get_indexes(length, train=0, indexing=1):
    """
    Generate indexing array
    """
    idx = np.zeros((3, length))

    if Indexing(indexing) == Indexing.orig:
        idx[1, :] = range(length)
    elif Indexing(indexing) == Indexing.rand:
        idx[1, :] = np.vectorize(
            np.concatenate(np.random.permutation(train), range(train, length))
        )
    elif Indexing(indexing) == Indexing.alternate:
        idx[1, :] = np.vectorize(
            np.concatenate(
                range(1, length - 1, 2), np.concatenate(range(2, length, 2))
            )
        )

    idx[1, :] = range(length)
    col_sort = idx[np.argsort(idx[:, 1])]
    idx[2, :] = col_sort[1, :]
