import pytest

import pandas as pd
from pandas import DataFrame
import pandas._testing as tm


@pytest.fixture(params=[True, False])
def by_blocks_fixture(request):
    return request.param


@pytest.fixture(params=["DataFrame", "Series"])
def obj_fixture(request):
    return request.param


def _assert_frame_equal_both(a, b, **kwargs):
    """
    Check that two DataFrame equal.

    This check is performed commutatively.

    Parameters
    ----------
    a : DataFrame
        The first DataFrame to compare.
    b : DataFrame
        The second DataFrame to compare.
    kwargs : dict
        The arguments passed to `tm.assert_frame_equal`.
    """
    tm.assert_frame_equal(a, b, **kwargs)
    tm.assert_frame_equal(b, a, **kwargs)


def _assert_not_frame_equal(a, b, **kwargs):
    """
    Check that two DataFrame are not equal.

    Parameters
    ----------
    a : DataFrame
        The first DataFrame to compare.
    b : DataFrame
        The second DataFrame to compare.
    kwargs : dict
        The arguments passed to `tm.assert_frame_equal`.
    """
    msg = "The two DataFrames were equal when they shouldn't have been"
    with pytest.raises(AssertionError, match=msg):
        tm.assert_frame_equal(a, b, **kwargs)


def _assert_not_frame_equal_both(a, b, **kwargs):
    """
    Check that two DataFrame are not equal.

    This check is performed commutatively.

    Parameters
    ----------
    a : DataFrame
        The first DataFrame to compare.
    b : DataFrame
        The second DataFrame to compare.
    kwargs : dict
        The arguments passed to `tm.assert_frame_equal`.
    """
    _assert_not_frame_equal(a, b, **kwargs)
    _assert_not_frame_equal(b, a, **kwargs)


@pytest.mark.parametrize("check_like", [True, False])
def test_frame_equal_row_order_mismatch(check_like, obj_fixture):
    df1 = DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}, index=["a", "b", "c"])
    df2 = DataFrame({"A": [3, 2, 1], "B": [6, 5, 4]}, index=["c", "b", "a"])

    if not check_like:  # Do not ignore row-column orderings.
        msg = f"{obj_fixture}.index are different"
        with pytest.raises(AssertionError, match=msg):
            tm.assert_frame_equal(df1, df2, check_like=check_like, obj=obj_fixture)
    else:
        _assert_frame_equal_both(df1, df2, check_like=check_like, obj=obj_fixture)


@pytest.mark.parametrize(
    "df1,df2",
    [
        (DataFrame({"A": [1, 2, 3]}), DataFrame({"A": [1, 2, 3, 4]})),
        (DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}), DataFrame({"A": [1, 2, 3]})),
    ],
)
def test_frame_equal_shape_mismatch(df1, df2, obj_fixture):
    msg = f"{obj_fixture} are different"

    with pytest.raises(AssertionError, match=msg):
        tm.assert_frame_equal(df1, df2, obj=obj_fixture)


@pytest.mark.parametrize(
    "df1,df2,msg",
    [
        # Index
        (
            DataFrame.from_records({"a": [1, 2], "c": ["l1", "l2"]}, index=["a"]),
            DataFrame.from_records({"a": [1.0, 2.0], "c": ["l1", "l2"]}, index=["a"]),
            "DataFrame\\.index are different",
        ),
        # MultiIndex
        (
            DataFrame.from_records(
                {"a": [1, 2], "b": [2.1, 1.5], "c": ["l1", "l2"]}, index=["a", "b"]
            ),
            DataFrame.from_records(
                {"a": [1.0, 2.0], "b": [2.1, 1.5], "c": ["l1", "l2"]}, index=["a", "b"]
            ),
            "MultiIndex level \\[0\\] are different",
        ),
    ],
)
def test_frame_equal_index_dtype_mismatch(df1, df2, msg, check_index_type):
    kwargs = dict(check_index_type=check_index_type)

    if check_index_type:
        with pytest.raises(AssertionError, match=msg):
            tm.assert_frame_equal(df1, df2, **kwargs)
    else:
        tm.assert_frame_equal(df1, df2, **kwargs)


def test_empty_dtypes(check_dtype):
    columns = ["col1", "col2"]
    df1 = DataFrame(columns=columns)
    df2 = DataFrame(columns=columns)

    kwargs = dict(check_dtype=check_dtype)
    df1["col1"] = df1["col1"].astype("int64")

    if check_dtype:
        msg = r"Attributes of DataFrame\..* are different"
        with pytest.raises(AssertionError, match=msg):
            tm.assert_frame_equal(df1, df2, **kwargs)
    else:
        tm.assert_frame_equal(df1, df2, **kwargs)


def test_frame_equal_index_mismatch(obj_fixture):
    msg = f"""{obj_fixture}\\.index are different

{obj_fixture}\\.index values are different \\(33\\.33333 %\\)
\\[left\\]:  Index\\(\\['a', 'b', 'c'\\], dtype='object'\\)
\\[right\\]: Index\\(\\['a', 'b', 'd'\\], dtype='object'\\)"""

    df1 = DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}, index=["a", "b", "c"])
    df2 = DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}, index=["a", "b", "d"])

    with pytest.raises(AssertionError, match=msg):
        tm.assert_frame_equal(df1, df2, obj=obj_fixture)


def test_frame_equal_columns_mismatch(obj_fixture):
    msg = f"""{obj_fixture}\\.columns are different

{obj_fixture}\\.columns values are different \\(50\\.0 %\\)
\\[left\\]:  Index\\(\\['A', 'B'\\], dtype='object'\\)
\\[right\\]: Index\\(\\['A', 'b'\\], dtype='object'\\)"""

    df1 = DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}, index=["a", "b", "c"])
    df2 = DataFrame({"A": [1, 2, 3], "b": [4, 5, 6]}, index=["a", "b", "c"])

    with pytest.raises(AssertionError, match=msg):
        tm.assert_frame_equal(df1, df2, obj=obj_fixture)


def test_frame_equal_block_mismatch(by_blocks_fixture, obj_fixture):
    obj = obj_fixture
    msg = f"""{obj}\\.iloc\\[:, 1\\] \\(column name="B"\\) are different

{obj}\\.iloc\\[:, 1\\] \\(column name="B"\\) values are different \\(33\\.33333 %\\)
\\[index\\]: \\[0, 1, 2\\]
\\[left\\]:  \\[4, 5, 6\\]
\\[right\\]: \\[4, 5, 7\\]"""

    df1 = DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    df2 = DataFrame({"A": [1, 2, 3], "B": [4, 5, 7]})

    with pytest.raises(AssertionError, match=msg):
        tm.assert_frame_equal(df1, df2, by_blocks=by_blocks_fixture, obj=obj_fixture)


@pytest.mark.parametrize(
    "df1,df2,msg",
    [
        (
            DataFrame({"A": ["á", "à", "ä"], "E": ["é", "è", "ë"]}),
            DataFrame({"A": ["á", "à", "ä"], "E": ["é", "è", "e̊"]}),
            """{obj}\\.iloc\\[:, 1\\] \\(column name="E"\\) are different

{obj}\\.iloc\\[:, 1\\] \\(column name="E"\\) values are different \\(33\\.33333 %\\)
\\[index\\]: \\[0, 1, 2\\]
\\[left\\]:  \\[é, è, ë\\]
\\[right\\]: \\[é, è, e̊\\]""",
        ),
        (
            DataFrame({"A": ["á", "à", "ä"], "E": ["é", "è", "ë"]}),
            DataFrame({"A": ["a", "a", "a"], "E": ["e", "e", "e"]}),
            """{obj}\\.iloc\\[:, 0\\] \\(column name="A"\\) are different

{obj}\\.iloc\\[:, 0\\] \\(column name="A"\\) values are different \\(100\\.0 %\\)
\\[index\\]: \\[0, 1, 2\\]
\\[left\\]:  \\[á, à, ä\\]
\\[right\\]: \\[a, a, a\\]""",
        ),
    ],
)
def test_frame_equal_unicode(df1, df2, msg, by_blocks_fixture, obj_fixture):
    # see gh-20503
    #
    # Test ensures that `tm.assert_frame_equals` raises the right exception
    # when comparing DataFrames containing differing unicode objects.
    msg = msg.format(obj=obj_fixture)
    with pytest.raises(AssertionError, match=msg):
        tm.assert_frame_equal(df1, df2, by_blocks=by_blocks_fixture, obj=obj_fixture)


def test_assert_frame_equal_extension_dtype_mismatch():
    # https://github.com/pandas-dev/pandas/issues/32747
    left = DataFrame({"a": [1, 2, 3]}, dtype="Int64")
    right = left.astype(int)

    msg = (
        "Attributes of DataFrame\\.iloc\\[:, 0\\] "
        '\\(column name="a"\\) are different\n\n'
        'Attribute "dtype" are different\n'
        "\\[left\\]:  Int64\n"
        "\\[right\\]: int[32|64]"
    )

    tm.assert_frame_equal(left, right, check_dtype=False)

    with pytest.raises(AssertionError, match=msg):
        tm.assert_frame_equal(left, right, check_dtype=True)


def test_assert_frame_equal_interval_dtype_mismatch():
    # https://github.com/pandas-dev/pandas/issues/32747
    left = DataFrame({"a": [pd.Interval(0, 1)]}, dtype="interval")
    right = left.astype(object)

    msg = (
        "Attributes of DataFrame\\.iloc\\[:, 0\\] "
        '\\(column name="a"\\) are different\n\n'
        'Attribute "dtype" are different\n'
        "\\[left\\]:  interval\\[int64\\]\n"
        "\\[right\\]: object"
    )

    tm.assert_frame_equal(left, right, check_dtype=False)

    with pytest.raises(AssertionError, match=msg):
        tm.assert_frame_equal(left, right, check_dtype=True)


@pytest.mark.parametrize("right_dtype", ["Int32", "int64"])
def test_assert_frame_equal_ignore_extension_dtype_mismatch(right_dtype):
    # https://github.com/pandas-dev/pandas/issues/35715
    left = DataFrame({"a": [1, 2, 3]}, dtype="Int64")
    right = DataFrame({"a": [1, 2, 3]}, dtype=right_dtype)
    tm.assert_frame_equal(left, right, check_dtype=False)


def test_allows_duplicate_labels():
    left = DataFrame()
    right = DataFrame().set_flags(allows_duplicate_labels=False)
    tm.assert_frame_equal(left, left)
    tm.assert_frame_equal(right, right)
    tm.assert_frame_equal(left, right, check_flags=False)
    tm.assert_frame_equal(right, left, check_flags=False)

    with pytest.raises(AssertionError, match="<Flags"):
        tm.assert_frame_equal(left, right)

    with pytest.raises(AssertionError, match="<Flags"):
        tm.assert_frame_equal(left, right)
