"""
Templates for invalid operations.
"""
import operator

import numpy as np


def invalid_comparison(left, right, op):
    """
    If a comparison has mismatched types and is not necessarily meaningful,
    follow python3 conventions by:

        - returning all-False for equality
        - returning all-True for inequality
        - raising TypeError otherwise

    Parameters
    ----------
    left : array-like
    right : scalar, array-like
    op : operator.{eq, ne, lt, le, gt}

    Raises
    ------
    TypeError : on inequality comparisons
    """
    if op is operator.eq:
        res_values = np.zeros(left.shape, dtype=bool)
    elif op is operator.ne:
        res_values = np.ones(left.shape, dtype=bool)
    else:
        raise TypeError(
            "Invalid comparison between dtype={dtype} and {typ}".format(
                dtype=left.dtype, typ=type(right).__name__
            )
        )
    return res_values


def make_invalid_op(name: str):
    """
    Return a binary method that always raises a TypeError.

    Parameters
    ----------
    name : str

    Returns
    -------
    invalid_op : function
    """

    def invalid_op(self, other=None):
        raise TypeError(
            "cannot perform {name} with this index type: "
            "{typ}".format(name=name, typ=type(self).__name__)
        )

    invalid_op.__name__ = name
    return invalid_op
