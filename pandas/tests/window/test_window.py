import numpy as np
import pytest

from pandas.errors import UnsupportedFunctionCall
import pandas.util._test_decorators as td

import pandas as pd
from pandas import Series


@td.skip_if_no_scipy
def test_constructor(which):
    # GH 12669
    c = which.rolling

    # valid
    c(win_type="boxcar", window=2, min_periods=1)
    c(win_type="boxcar", window=2, min_periods=1, center=True)
    c(win_type="boxcar", window=2, min_periods=1, center=False)


@pytest.mark.parametrize("w", [2.0, "foo", np.array([2])])
@td.skip_if_no_scipy
def test_invalid_constructor(which, w):
    # not valid

    c = which.rolling
    with pytest.raises(ValueError, match="min_periods must be an integer"):
        c(win_type="boxcar", window=2, min_periods=w)
    with pytest.raises(ValueError, match="center must be a boolean"):
        c(win_type="boxcar", window=2, min_periods=1, center=w)


@pytest.mark.parametrize("wt", ["foobar", 1])
@td.skip_if_no_scipy
def test_invalid_constructor_wintype(which, wt):
    c = which.rolling
    with pytest.raises(ValueError, match="Invalid win_type"):
        c(win_type=wt, window=2)


@td.skip_if_no_scipy
def test_constructor_with_win_type(which, win_types):
    # GH 12669
    c = which.rolling
    c(win_type=win_types, window=2)


@pytest.mark.parametrize("method", ["sum", "mean"])
def test_numpy_compat(method):
    # see gh-12811
    w = Series([2, 4, 6]).rolling(window=2)

    msg = "numpy operations are not valid with window objects"

    with pytest.raises(UnsupportedFunctionCall, match=msg):
        getattr(w, method)(1, 2, 3)
    with pytest.raises(UnsupportedFunctionCall, match=msg):
        getattr(w, method)(dtype=np.float64)


@td.skip_if_no_scipy
@pytest.mark.parametrize("arg", ["median", "kurt", "skew"])
def test_agg_function_support(arg):
    df = pd.DataFrame({"A": np.arange(5)})
    roll = df.rolling(2, win_type="triang")

    msg = f"'{arg}' is not a valid function for 'Window' object"
    with pytest.raises(AttributeError, match=msg):
        roll.agg(arg)

    with pytest.raises(AttributeError, match=msg):
        roll.agg([arg])

    with pytest.raises(AttributeError, match=msg):
        roll.agg({"A": arg})


@td.skip_if_no_scipy
def test_invalid_scipy_arg():
    # This error is raised by scipy
    msg = r"boxcar\(\) got an unexpected"
    with pytest.raises(TypeError, match=msg):
        Series(range(3)).rolling(1, win_type="boxcar").mean(foo="bar")
