from datetime import datetime

import numpy as np
import pytest

import pandas.util._test_decorators as td

import pandas as pd
from pandas import DataFrame, Index, MultiIndex, date_range, period_range
import pandas._testing as tm

# TODO(ArrayManager) concat with reindexing
pytestmark = td.skip_array_manager_not_yet_implemented


@pytest.fixture
def frame_with_period_index():
    return DataFrame(
        data=np.arange(20).reshape(4, 5),
        columns=list("abcde"),
        index=period_range(start="2000", freq="A", periods=4),
    )


@pytest.fixture
def left():
    return DataFrame({"a": [20, 10, 0]}, index=[2, 1, 0])


@pytest.fixture
def right():
    return DataFrame({"b": [300, 100, 200]}, index=[3, 1, 2])


@pytest.mark.parametrize(
    "how, sort, expected",
    [
        ("inner", False, DataFrame({"a": [20, 10], "b": [200, 100]}, index=[2, 1])),
        ("inner", True, DataFrame({"a": [10, 20], "b": [100, 200]}, index=[1, 2])),
        (
            "left",
            False,
            DataFrame({"a": [20, 10, 0], "b": [200, 100, np.nan]}, index=[2, 1, 0]),
        ),
        (
            "left",
            True,
            DataFrame({"a": [0, 10, 20], "b": [np.nan, 100, 200]}, index=[0, 1, 2]),
        ),
        (
            "right",
            False,
            DataFrame({"a": [np.nan, 10, 20], "b": [300, 100, 200]}, index=[3, 1, 2]),
        ),
        (
            "right",
            True,
            DataFrame({"a": [10, 20, np.nan], "b": [100, 200, 300]}, index=[1, 2, 3]),
        ),
        (
            "outer",
            False,
            DataFrame(
                {"a": [0, 10, 20, np.nan], "b": [np.nan, 100, 200, 300]},
                index=[0, 1, 2, 3],
            ),
        ),
        (
            "outer",
            True,
            DataFrame(
                {"a": [0, 10, 20, np.nan], "b": [np.nan, 100, 200, 300]},
                index=[0, 1, 2, 3],
            ),
        ),
    ],
)
def test_join(left, right, how, sort, expected):

    result = left.join(right, how=how, sort=sort)
    tm.assert_frame_equal(result, expected)


def test_join_index(float_frame):
    # left / right

    f = float_frame.loc[float_frame.index[:10], ["A", "B"]]
    f2 = float_frame.loc[float_frame.index[5:], ["C", "D"]].iloc[::-1]

    joined = f.join(f2)
    tm.assert_index_equal(f.index, joined.index)
    expected_columns = Index(["A", "B", "C", "D"])
    tm.assert_index_equal(joined.columns, expected_columns)

    joined = f.join(f2, how="left")
    tm.assert_index_equal(joined.index, f.index)
    tm.assert_index_equal(joined.columns, expected_columns)

    joined = f.join(f2, how="right")
    tm.assert_index_equal(joined.index, f2.index)
    tm.assert_index_equal(joined.columns, expected_columns)

    # inner

    joined = f.join(f2, how="inner")
    tm.assert_index_equal(joined.index, f.index[5:10])
    tm.assert_index_equal(joined.columns, expected_columns)

    # outer

    joined = f.join(f2, how="outer")
    tm.assert_index_equal(joined.index, float_frame.index.sort_values())
    tm.assert_index_equal(joined.columns, expected_columns)

    with pytest.raises(ValueError, match="join method"):
        f.join(f2, how="foo")

    # corner case - overlapping columns
    msg = "columns overlap but no suffix"
    for how in ("outer", "left", "inner"):
        with pytest.raises(ValueError, match=msg):
            float_frame.join(float_frame, how=how)


def test_join_index_more(float_frame):
    af = float_frame.loc[:, ["A", "B"]]
    bf = float_frame.loc[::2, ["C", "D"]]

    expected = af.copy()
    expected["C"] = float_frame["C"][::2]
    expected["D"] = float_frame["D"][::2]

    result = af.join(bf)
    tm.assert_frame_equal(result, expected)

    result = af.join(bf, how="right")
    tm.assert_frame_equal(result, expected[::2])

    result = bf.join(af, how="right")
    tm.assert_frame_equal(result, expected.loc[:, result.columns])


def test_join_index_series(float_frame):
    df = float_frame.copy()
    s = df.pop(float_frame.columns[-1])
    joined = df.join(s)

    # TODO should this check_names ?
    tm.assert_frame_equal(joined, float_frame, check_names=False)

    s.name = None
    with pytest.raises(ValueError, match="must have a name"):
        df.join(s)


def test_join_overlap(float_frame):
    df1 = float_frame.loc[:, ["A", "B", "C"]]
    df2 = float_frame.loc[:, ["B", "C", "D"]]

    joined = df1.join(df2, lsuffix="_df1", rsuffix="_df2")
    df1_suf = df1.loc[:, ["B", "C"]].add_suffix("_df1")
    df2_suf = df2.loc[:, ["B", "C"]].add_suffix("_df2")

    no_overlap = float_frame.loc[:, ["A", "D"]]
    expected = df1_suf.join(df2_suf).join(no_overlap)

    # column order not necessarily sorted
    tm.assert_frame_equal(joined, expected.loc[:, joined.columns])


def test_join_period_index(frame_with_period_index):
    other = frame_with_period_index.rename(columns=lambda key: f"{key}{key}")

    joined_values = np.concatenate([frame_with_period_index.values] * 2, axis=1)

    joined_cols = frame_with_period_index.columns.append(other.columns)

    joined = frame_with_period_index.join(other)
    expected = DataFrame(
        data=joined_values, columns=joined_cols, index=frame_with_period_index.index
    )

    tm.assert_frame_equal(joined, expected)


def test_join_left_sequence_non_unique_index():
    # https://github.com/pandas-dev/pandas/issues/19607
    df1 = DataFrame({"a": [0, 10, 20]}, index=[1, 2, 3])
    df2 = DataFrame({"b": [100, 200, 300]}, index=[4, 3, 2])
    df3 = DataFrame({"c": [400, 500, 600]}, index=[2, 2, 4])

    joined = df1.join([df2, df3], how="left")

    expected = DataFrame(
        {
            "a": [0, 10, 10, 20],
            "b": [np.nan, 300, 300, 200],
            "c": [np.nan, 400, 500, np.nan],
        },
        index=[1, 2, 2, 3],
    )

    tm.assert_frame_equal(joined, expected)


@pytest.mark.parametrize("sort_kw", [True, False])
def test_suppress_future_warning_with_sort_kw(sort_kw):
    a = DataFrame({"col1": [1, 2]}, index=["c", "a"])

    b = DataFrame({"col2": [4, 5]}, index=["b", "a"])

    c = DataFrame({"col3": [7, 8]}, index=["a", "b"])

    expected = DataFrame(
        {
            "col1": {"a": 2.0, "b": float("nan"), "c": 1.0},
            "col2": {"a": 5.0, "b": 4.0, "c": float("nan")},
            "col3": {"a": 7.0, "b": 8.0, "c": float("nan")},
        }
    )
    if sort_kw is False:
        expected = expected.reindex(index=["c", "a", "b"])

    with tm.assert_produces_warning(None, check_stacklevel=False):
        result = a.join([b, c], how="outer", sort=sort_kw)
    tm.assert_frame_equal(result, expected)


class TestDataFrameJoin:
    def test_join(self, multiindex_dataframe_random_data):
        frame = multiindex_dataframe_random_data

        a = frame.loc[frame.index[:5], ["A"]]
        b = frame.loc[frame.index[2:], ["B", "C"]]

        joined = a.join(b, how="outer").reindex(frame.index)
        expected = frame.copy()
        expected.values[np.isnan(joined.values)] = np.nan

        assert not np.isnan(joined.values).all()

        # TODO what should join do with names ?
        tm.assert_frame_equal(joined, expected, check_names=False)

    def test_join_segfault(self):
        # GH#1532
        df1 = DataFrame({"a": [1, 1], "b": [1, 2], "x": [1, 2]})
        df2 = DataFrame({"a": [2, 2], "b": [1, 2], "y": [1, 2]})
        df1 = df1.set_index(["a", "b"])
        df2 = df2.set_index(["a", "b"])
        # it works!
        for how in ["left", "right", "outer"]:
            df1.join(df2, how=how)

    def test_join_str_datetime(self):
        str_dates = ["20120209", "20120222"]
        dt_dates = [datetime(2012, 2, 9), datetime(2012, 2, 22)]

        A = DataFrame(str_dates, index=range(2), columns=["aa"])
        C = DataFrame([[1, 2], [3, 4]], index=str_dates, columns=dt_dates)

        tst = A.join(C, on="aa")

        assert len(tst.columns) == 3

    def test_join_multiindex_leftright(self):
        # GH 10741
        df1 = DataFrame(
            [
                ["a", "x", 0.471780],
                ["a", "y", 0.774908],
                ["a", "z", 0.563634],
                ["b", "x", -0.353756],
                ["b", "y", 0.368062],
                ["b", "z", -1.721840],
                ["c", "x", 1],
                ["c", "y", 2],
                ["c", "z", 3],
            ],
            columns=["first", "second", "value1"],
        ).set_index(["first", "second"])

        df2 = DataFrame([["a", 10], ["b", 20]], columns=["first", "value2"]).set_index(
            ["first"]
        )

        exp = DataFrame(
            [
                [0.471780, 10],
                [0.774908, 10],
                [0.563634, 10],
                [-0.353756, 20],
                [0.368062, 20],
                [-1.721840, 20],
                [1.000000, np.nan],
                [2.000000, np.nan],
                [3.000000, np.nan],
            ],
            index=df1.index,
            columns=["value1", "value2"],
        )

        # these must be the same results (but columns are flipped)
        tm.assert_frame_equal(df1.join(df2, how="left"), exp)
        tm.assert_frame_equal(df2.join(df1, how="right"), exp[["value2", "value1"]])

        exp_idx = pd.MultiIndex.from_product(
            [["a", "b"], ["x", "y", "z"]], names=["first", "second"]
        )
        exp = DataFrame(
            [
                [0.471780, 10],
                [0.774908, 10],
                [0.563634, 10],
                [-0.353756, 20],
                [0.368062, 20],
                [-1.721840, 20],
            ],
            index=exp_idx,
            columns=["value1", "value2"],
        )

        tm.assert_frame_equal(df1.join(df2, how="right"), exp)
        tm.assert_frame_equal(df2.join(df1, how="left"), exp[["value2", "value1"]])

    def test_merge_join_different_levels(self):
        # GH#9455

        # first dataframe
        df1 = DataFrame(columns=["a", "b"], data=[[1, 11], [0, 22]])

        # second dataframe
        columns = MultiIndex.from_tuples([("a", ""), ("c", "c1")])
        df2 = DataFrame(columns=columns, data=[[1, 33], [0, 44]])

        # merge
        columns = ["a", "b", ("c", "c1")]
        expected = DataFrame(columns=columns, data=[[1, 11, 33], [0, 22, 44]])
        with tm.assert_produces_warning(UserWarning):
            result = pd.merge(df1, df2, on="a")
        tm.assert_frame_equal(result, expected)

        # join, see discussion in GH#12219
        columns = ["a", "b", ("a", ""), ("c", "c1")]
        expected = DataFrame(columns=columns, data=[[1, 11, 0, 44], [0, 22, 1, 33]])
        with tm.assert_produces_warning(UserWarning):
            result = df1.join(df2, on="a")
        tm.assert_frame_equal(result, expected)

    def test_frame_join_tzaware(self):
        test1 = DataFrame(
            np.zeros((6, 3)),
            index=date_range(
                "2012-11-15 00:00:00", periods=6, freq="100L", tz="US/Central"
            ),
        )
        test2 = DataFrame(
            np.zeros((3, 3)),
            index=date_range(
                "2012-11-15 00:00:00", periods=3, freq="250L", tz="US/Central"
            ),
            columns=range(3, 6),
        )

        result = test1.join(test2, how="outer")
        expected = test1.index.union(test2.index)

        tm.assert_index_equal(result.index, expected)
        assert result.index.tz.zone == "US/Central"
