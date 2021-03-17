from typing import (
    Any,
    Callable,
)

import numpy as np

_BinOp = Callable[[Any, Any], Any]
_BoolOp = Callable[[Any, Any], bool]


def scalar_compare(
    values: np.ndarray,  # object[:]
    val: object,
    op: _BoolOp,          # {operator.eq, operator.ne, ...}
) -> np.ndarray: ...     # np.ndarray[bool]

def vec_compare(
    left: np.ndarray,   # np.ndarray[object]
    right: np.ndarray,  # np.ndarray[object]
    op: _BoolOp,         # {operator.eq, operator.ne, ...}
) -> np.ndarray: ...    # np.ndarray[bool]


def scalar_binop(
    values: np.ndarray,   # object[:]
    val: object,
    op: _BinOp,           # binary operator
) -> np.ndarray: ...


def vec_binop(
    left: np.ndarray,   # object[:]
    right: np.ndarray,  # object[:]
    op: _BinOp,         # binary operator
) -> np.ndarray: ...


def maybe_convert_bool(
    arr: np.ndarray,  # np.ndarray[object]
    true_values=...,
    false_values=...
) -> np.ndarray: ...
