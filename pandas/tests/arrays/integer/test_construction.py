import numpy as np
import pytest

import pandas as pd
import pandas._testing as tm
from pandas.api.types import is_integer
from pandas.core.arrays import IntegerArray, integer_array
from pandas.core.arrays.integer import Int8Dtype, Int32Dtype, Int64Dtype


def test_uses_pandas_na():
    a = pd.array([1, None], dtype=Int64Dtype())
    assert a[1] is pd.NA


def test_from_dtype_from_float(data):
    # construct from our dtype & string dtype
    dtype = data.dtype

    # from float
    expected = pd.Series(data)
    result = pd.Series(data.to_numpy(na_value=np.nan, dtype="float"), dtype=str(dtype))
    tm.assert_series_equal(result, expected)

    # from int / list
    expected = pd.Series(data)
    result = pd.Series(np.array(data).tolist(), dtype=str(dtype))
    tm.assert_series_equal(result, expected)

    # from int / array
    expected = pd.Series(data).dropna().reset_index(drop=True)
    dropped = np.array(data.dropna()).astype(np.dtype(dtype.type))
    result = pd.Series(dropped, dtype=str(dtype))
    tm.assert_series_equal(result, expected)


def test_conversions(data_missing):

    # astype to object series
    df = pd.DataFrame({"A": data_missing})
    result = df["A"].astype("object")
    expected = pd.Series(np.array([np.nan, 1], dtype=object), name="A")
    tm.assert_series_equal(result, expected)

    # convert to object ndarray
    # we assert that we are exactly equal
    # including type conversions of scalars
    result = df["A"].astype("object").values
    expected = np.array([pd.NA, 1], dtype=object)
    tm.assert_numpy_array_equal(result, expected)

    for r, e in zip(result, expected):
        if pd.isnull(r):
            assert pd.isnull(e)
        elif is_integer(r):
            assert r == e
            assert is_integer(e)
        else:
            assert r == e
            assert type(r) == type(e)


def test_integer_array_constructor():
    values = np.array([1, 2, 3, 4], dtype="int64")
    mask = np.array([False, False, False, True], dtype="bool")

    result = IntegerArray(values, mask)
    expected = integer_array([1, 2, 3, np.nan], dtype="int64")
    tm.assert_extension_array_equal(result, expected)

    msg = r".* should be .* numpy array. Use the 'pd.array' function instead"
    with pytest.raises(TypeError, match=msg):
        IntegerArray(values.tolist(), mask)

    with pytest.raises(TypeError, match=msg):
        IntegerArray(values, mask.tolist())

    with pytest.raises(TypeError, match=msg):
        IntegerArray(values.astype(float), mask)
    msg = r"__init__\(\) missing 1 required positional argument: 'mask'"
    with pytest.raises(TypeError, match=msg):
        IntegerArray(values)


@pytest.mark.parametrize(
    "a, b",
    [
        ([1, None], [1, np.nan]),
        ([None], [np.nan]),
        ([None, np.nan], [np.nan, np.nan]),
        ([np.nan, np.nan], [np.nan, np.nan]),
    ],
)
def test_integer_array_constructor_none_is_nan(a, b):
    result = integer_array(a)
    expected = integer_array(b)
    tm.assert_extension_array_equal(result, expected)


def test_integer_array_constructor_copy():
    values = np.array([1, 2, 3, 4], dtype="int64")
    mask = np.array([False, False, False, True], dtype="bool")

    result = IntegerArray(values, mask)
    assert result._data is values
    assert result._mask is mask

    result = IntegerArray(values, mask, copy=True)
    assert result._data is not values
    assert result._mask is not mask


@pytest.mark.parametrize(
    "values",
    [
        ["foo", "bar"],
        ["1", "2"],
        "foo",
        1,
        1.0,
        pd.date_range("20130101", periods=2),
        np.array(["foo"]),
        [[1, 2], [3, 4]],
        [np.nan, {"a": 1}],
    ],
)
def test_to_integer_array_error(values):
    # error in converting existing arrays to IntegerArrays
    msg = (
        r"(:?.* cannot be converted to an IntegerDtype)"
        r"|(:?values must be a 1D list-like)"
    )
    with pytest.raises(TypeError, match=msg):
        integer_array(values)


def test_to_integer_array_inferred_dtype():
    # if values has dtype -> respect it
    result = integer_array(np.array([1, 2], dtype="int8"))
    assert result.dtype == Int8Dtype()
    result = integer_array(np.array([1, 2], dtype="int32"))
    assert result.dtype == Int32Dtype()

    # if values have no dtype -> always int64
    result = integer_array([1, 2])
    assert result.dtype == Int64Dtype()


def test_to_integer_array_dtype_keyword():
    result = integer_array([1, 2], dtype="int8")
    assert result.dtype == Int8Dtype()

    # if values has dtype -> override it
    result = integer_array(np.array([1, 2], dtype="int8"), dtype="int32")
    assert result.dtype == Int32Dtype()


def test_to_integer_array_float():
    result = integer_array([1.0, 2.0])
    expected = integer_array([1, 2])
    tm.assert_extension_array_equal(result, expected)

    with pytest.raises(TypeError, match="cannot safely cast non-equivalent"):
        integer_array([1.5, 2.0])

    # for float dtypes, the itemsize is not preserved
    result = integer_array(np.array([1.0, 2.0], dtype="float32"))
    assert result.dtype == Int64Dtype()


@pytest.mark.parametrize(
    "bool_values, int_values, target_dtype, expected_dtype",
    [
        ([False, True], [0, 1], Int64Dtype(), Int64Dtype()),
        ([False, True], [0, 1], "Int64", Int64Dtype()),
        ([False, True, np.nan], [0, 1, np.nan], Int64Dtype(), Int64Dtype()),
    ],
)
def test_to_integer_array_bool(bool_values, int_values, target_dtype, expected_dtype):
    result = integer_array(bool_values, dtype=target_dtype)
    assert result.dtype == expected_dtype
    expected = integer_array(int_values, dtype=target_dtype)
    tm.assert_extension_array_equal(result, expected)


@pytest.mark.parametrize(
    "values, to_dtype, result_dtype",
    [
        (np.array([1], dtype="int64"), None, Int64Dtype),
        (np.array([1, np.nan]), None, Int64Dtype),
        (np.array([1, np.nan]), "int8", Int8Dtype),
    ],
)
def test_to_integer_array(values, to_dtype, result_dtype):
    # convert existing arrays to IntegerArrays
    result = integer_array(values, dtype=to_dtype)
    assert result.dtype == result_dtype()
    expected = integer_array(values, dtype=result_dtype())
    tm.assert_extension_array_equal(result, expected)
