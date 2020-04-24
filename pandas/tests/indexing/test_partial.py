"""
test setting *parts* of objects both positionally and label based

TODO: these should be split among the indexer tests
"""

import numpy as np
import pytest

import pandas as pd
from pandas import DataFrame, Index, Series, date_range
import pandas._testing as tm


class TestPartialSetting:
    def test_partial_setting(self):

        # GH2578, allow ix and friends to partially set

        # series
        s_orig = Series([1, 2, 3])

        s = s_orig.copy()
        s[5] = 5
        expected = Series([1, 2, 3, 5], index=[0, 1, 2, 5])
        tm.assert_series_equal(s, expected)

        s = s_orig.copy()
        s.loc[5] = 5
        expected = Series([1, 2, 3, 5], index=[0, 1, 2, 5])
        tm.assert_series_equal(s, expected)

        s = s_orig.copy()
        s[5] = 5.0
        expected = Series([1, 2, 3, 5.0], index=[0, 1, 2, 5])
        tm.assert_series_equal(s, expected)

        s = s_orig.copy()
        s.loc[5] = 5.0
        expected = Series([1, 2, 3, 5.0], index=[0, 1, 2, 5])
        tm.assert_series_equal(s, expected)

        # iloc/iat raise
        s = s_orig.copy()

        msg = "iloc cannot enlarge its target object"
        with pytest.raises(IndexError, match=msg):
            s.iloc[3] = 5.0

        msg = "index 3 is out of bounds for axis 0 with size 3"
        with pytest.raises(IndexError, match=msg):
            s.iat[3] = 5.0

        # ## frame ##

        df_orig = DataFrame(
            np.arange(6).reshape(3, 2), columns=["A", "B"], dtype="int64"
        )

        # iloc/iat raise
        df = df_orig.copy()

        msg = "iloc cannot enlarge its target object"
        with pytest.raises(IndexError, match=msg):
            df.iloc[4, 2] = 5.0

        msg = "index 2 is out of bounds for axis 0 with size 2"
        with pytest.raises(IndexError, match=msg):
            df.iat[4, 2] = 5.0

        # row setting where it exists
        expected = DataFrame(dict({"A": [0, 4, 4], "B": [1, 5, 5]}))
        df = df_orig.copy()
        df.iloc[1] = df.iloc[2]
        tm.assert_frame_equal(df, expected)

        expected = DataFrame(dict({"A": [0, 4, 4], "B": [1, 5, 5]}))
        df = df_orig.copy()
        df.loc[1] = df.loc[2]
        tm.assert_frame_equal(df, expected)

        # like 2578, partial setting with dtype preservation
        expected = DataFrame(dict({"A": [0, 2, 4, 4], "B": [1, 3, 5, 5]}))
        df = df_orig.copy()
        df.loc[3] = df.loc[2]
        tm.assert_frame_equal(df, expected)

        # single dtype frame, overwrite
        expected = DataFrame(dict({"A": [0, 2, 4], "B": [0, 2, 4]}))
        df = df_orig.copy()
        df.loc[:, "B"] = df.loc[:, "A"]
        tm.assert_frame_equal(df, expected)

        # mixed dtype frame, overwrite
        expected = DataFrame(dict({"A": [0, 2, 4], "B": Series([0, 2, 4])}))
        df = df_orig.copy()
        df["B"] = df["B"].astype(np.float64)
        df.loc[:, "B"] = df.loc[:, "A"]
        tm.assert_frame_equal(df, expected)

        # single dtype frame, partial setting
        expected = df_orig.copy()
        expected["C"] = df["A"]
        df = df_orig.copy()
        df.loc[:, "C"] = df.loc[:, "A"]
        tm.assert_frame_equal(df, expected)

        # mixed frame, partial setting
        expected = df_orig.copy()
        expected["C"] = df["A"]
        df = df_orig.copy()
        df.loc[:, "C"] = df.loc[:, "A"]
        tm.assert_frame_equal(df, expected)

        # GH 8473
        dates = date_range("1/1/2000", periods=8)
        df_orig = DataFrame(
            np.random.randn(8, 4), index=dates, columns=["A", "B", "C", "D"]
        )

        expected = pd.concat(
            [df_orig, DataFrame({"A": 7}, index=dates[-1:] + dates.freq)], sort=True
        )
        df = df_orig.copy()
        df.loc[dates[-1] + dates.freq, "A"] = 7
        tm.assert_frame_equal(df, expected)
        df = df_orig.copy()
        df.at[dates[-1] + dates.freq, "A"] = 7
        tm.assert_frame_equal(df, expected)

        exp_other = DataFrame({0: 7}, index=[dates[-1] + dates.freq])
        expected = pd.concat([df_orig, exp_other], axis=1)

        df = df_orig.copy()
        df.loc[dates[-1] + dates.freq, 0] = 7
        tm.assert_frame_equal(df, expected)
        df = df_orig.copy()
        df.at[dates[-1] + dates.freq, 0] = 7
        tm.assert_frame_equal(df, expected)

    def test_partial_setting_mixed_dtype(self):

        # in a mixed dtype environment, try to preserve dtypes
        # by appending
        df = DataFrame([[True, 1], [False, 2]], columns=["female", "fitness"])

        s = df.loc[1].copy()
        s.name = 2
        expected = df.append(s)

        df.loc[2] = df.loc[1]
        tm.assert_frame_equal(df, expected)

        # columns will align
        df = DataFrame(columns=["A", "B"])
        df.loc[0] = Series(1, index=range(4))
        tm.assert_frame_equal(df, DataFrame(columns=["A", "B"], index=[0]))

        # columns will align
        df = DataFrame(columns=["A", "B"])
        df.loc[0] = Series(1, index=["B"])

        exp = DataFrame([[np.nan, 1]], columns=["A", "B"], index=[0], dtype="float64")
        tm.assert_frame_equal(df, exp)

        # list-like must conform
        df = DataFrame(columns=["A", "B"])

        msg = "cannot set a row with mismatched columns"
        with pytest.raises(ValueError, match=msg):
            df.loc[0] = [1, 2, 3]

        # TODO: #15657, these are left as object and not coerced
        df = DataFrame(columns=["A", "B"])
        df.loc[3] = [6, 7]

        exp = DataFrame([[6, 7]], index=[3], columns=["A", "B"], dtype="object")
        tm.assert_frame_equal(df, exp)

    def test_series_partial_set(self):
        # partial set with new index
        # Regression from GH4825
        ser = Series([0.1, 0.2], index=[1, 2])

        # loc equiv to .reindex
        expected = Series([np.nan, 0.2, np.nan], index=[3, 2, 3])
        with pytest.raises(KeyError, match="with any missing labels"):
            result = ser.loc[[3, 2, 3]]

        result = ser.reindex([3, 2, 3])
        tm.assert_series_equal(result, expected, check_index_type=True)

        expected = Series([np.nan, 0.2, np.nan, np.nan], index=[3, 2, 3, "x"])
        with pytest.raises(KeyError, match="with any missing labels"):
            result = ser.loc[[3, 2, 3, "x"]]

        result = ser.reindex([3, 2, 3, "x"])
        tm.assert_series_equal(result, expected, check_index_type=True)

        expected = Series([0.2, 0.2, 0.1], index=[2, 2, 1])
        result = ser.loc[[2, 2, 1]]
        tm.assert_series_equal(result, expected, check_index_type=True)

        expected = Series([0.2, 0.2, np.nan, 0.1], index=[2, 2, "x", 1])
        with pytest.raises(KeyError, match="with any missing labels"):
            result = ser.loc[[2, 2, "x", 1]]

        result = ser.reindex([2, 2, "x", 1])
        tm.assert_series_equal(result, expected, check_index_type=True)

        # raises as nothing in in the index
        msg = (
            r"\"None of \[Int64Index\(\[3, 3, 3\], dtype='int64'\)\] are "
            r"in the \[index\]\""
        )
        with pytest.raises(KeyError, match=msg):
            ser.loc[[3, 3, 3]]

        expected = Series([0.2, 0.2, np.nan], index=[2, 2, 3])
        with pytest.raises(KeyError, match="with any missing labels"):
            ser.loc[[2, 2, 3]]

        result = ser.reindex([2, 2, 3])
        tm.assert_series_equal(result, expected, check_index_type=True)

        s = Series([0.1, 0.2, 0.3], index=[1, 2, 3])
        expected = Series([0.3, np.nan, np.nan], index=[3, 4, 4])
        with pytest.raises(KeyError, match="with any missing labels"):
            s.loc[[3, 4, 4]]

        result = s.reindex([3, 4, 4])
        tm.assert_series_equal(result, expected, check_index_type=True)

        s = Series([0.1, 0.2, 0.3, 0.4], index=[1, 2, 3, 4])
        expected = Series([np.nan, 0.3, 0.3], index=[5, 3, 3])
        with pytest.raises(KeyError, match="with any missing labels"):
            s.loc[[5, 3, 3]]

        result = s.reindex([5, 3, 3])
        tm.assert_series_equal(result, expected, check_index_type=True)

        s = Series([0.1, 0.2, 0.3, 0.4], index=[1, 2, 3, 4])
        expected = Series([np.nan, 0.4, 0.4], index=[5, 4, 4])
        with pytest.raises(KeyError, match="with any missing labels"):
            s.loc[[5, 4, 4]]

        result = s.reindex([5, 4, 4])
        tm.assert_series_equal(result, expected, check_index_type=True)

        s = Series([0.1, 0.2, 0.3, 0.4], index=[4, 5, 6, 7])
        expected = Series([0.4, np.nan, np.nan], index=[7, 2, 2])
        with pytest.raises(KeyError, match="with any missing labels"):
            s.loc[[7, 2, 2]]

        result = s.reindex([7, 2, 2])
        tm.assert_series_equal(result, expected, check_index_type=True)

        s = Series([0.1, 0.2, 0.3, 0.4], index=[1, 2, 3, 4])
        expected = Series([0.4, np.nan, np.nan], index=[4, 5, 5])
        with pytest.raises(KeyError, match="with any missing labels"):
            s.loc[[4, 5, 5]]

        result = s.reindex([4, 5, 5])
        tm.assert_series_equal(result, expected, check_index_type=True)

        # iloc
        expected = Series([0.2, 0.2, 0.1, 0.1], index=[2, 2, 1, 1])
        result = ser.iloc[[1, 1, 0, 0]]
        tm.assert_series_equal(result, expected, check_index_type=True)

    def test_series_partial_set_with_name(self):
        # GH 11497

        idx = Index([1, 2], dtype="int64", name="idx")
        ser = Series([0.1, 0.2], index=idx, name="s")

        # loc
        with pytest.raises(KeyError, match="with any missing labels"):
            ser.loc[[3, 2, 3]]

        with pytest.raises(KeyError, match="with any missing labels"):
            ser.loc[[3, 2, 3, "x"]]

        exp_idx = Index([2, 2, 1], dtype="int64", name="idx")
        expected = Series([0.2, 0.2, 0.1], index=exp_idx, name="s")
        result = ser.loc[[2, 2, 1]]
        tm.assert_series_equal(result, expected, check_index_type=True)

        with pytest.raises(KeyError, match="with any missing labels"):
            ser.loc[[2, 2, "x", 1]]

        # raises as nothing in in the index
        msg = (
            r"\"None of \[Int64Index\(\[3, 3, 3\], dtype='int64', "
            r"name='idx'\)\] are in the \[index\]\""
        )
        with pytest.raises(KeyError, match=msg):
            ser.loc[[3, 3, 3]]

        with pytest.raises(KeyError, match="with any missing labels"):
            ser.loc[[2, 2, 3]]

        idx = Index([1, 2, 3], dtype="int64", name="idx")
        with pytest.raises(KeyError, match="with any missing labels"):
            Series([0.1, 0.2, 0.3], index=idx, name="s").loc[[3, 4, 4]]

        idx = Index([1, 2, 3, 4], dtype="int64", name="idx")
        with pytest.raises(KeyError, match="with any missing labels"):
            Series([0.1, 0.2, 0.3, 0.4], index=idx, name="s").loc[[5, 3, 3]]

        idx = Index([1, 2, 3, 4], dtype="int64", name="idx")
        with pytest.raises(KeyError, match="with any missing labels"):
            Series([0.1, 0.2, 0.3, 0.4], index=idx, name="s").loc[[5, 4, 4]]

        idx = Index([4, 5, 6, 7], dtype="int64", name="idx")
        with pytest.raises(KeyError, match="with any missing labels"):
            Series([0.1, 0.2, 0.3, 0.4], index=idx, name="s").loc[[7, 2, 2]]

        idx = Index([1, 2, 3, 4], dtype="int64", name="idx")
        with pytest.raises(KeyError, match="with any missing labels"):
            Series([0.1, 0.2, 0.3, 0.4], index=idx, name="s").loc[[4, 5, 5]]

        # iloc
        exp_idx = Index([2, 2, 1, 1], dtype="int64", name="idx")
        expected = Series([0.2, 0.2, 0.1, 0.1], index=exp_idx, name="s")
        result = ser.iloc[[1, 1, 0, 0]]
        tm.assert_series_equal(result, expected, check_index_type=True)

    def test_partial_set_invalid(self):

        # GH 4940
        # allow only setting of 'valid' values

        orig = tm.makeTimeDataFrame()
        df = orig.copy()

        # don't allow not string inserts
        msg = "cannot insert DatetimeIndex with incompatible label"

        with pytest.raises(TypeError, match=msg):
            df.loc[100.0, :] = df.iloc[0]

        with pytest.raises(TypeError, match=msg):
            df.loc[100, :] = df.iloc[0]

        # allow object conversion here
        df = orig.copy()
        df.loc["a", :] = df.iloc[0]
        exp = orig.append(Series(df.iloc[0], name="a"))
        tm.assert_frame_equal(df, exp)
        tm.assert_index_equal(df.index, Index(orig.index.tolist() + ["a"]))
        assert df.index.dtype == "object"

    def test_partial_set_empty_series(self):

        # GH5226

        # partially set with an empty object series
        s = Series(dtype=object)
        s.loc[1] = 1
        tm.assert_series_equal(s, Series([1], index=[1]))
        s.loc[3] = 3
        tm.assert_series_equal(s, Series([1, 3], index=[1, 3]))

        s = Series(dtype=object)
        s.loc[1] = 1.0
        tm.assert_series_equal(s, Series([1.0], index=[1]))
        s.loc[3] = 3.0
        tm.assert_series_equal(s, Series([1.0, 3.0], index=[1, 3]))

        s = Series(dtype=object)
        s.loc["foo"] = 1
        tm.assert_series_equal(s, Series([1], index=["foo"]))
        s.loc["bar"] = 3
        tm.assert_series_equal(s, Series([1, 3], index=["foo", "bar"]))
        s.loc[3] = 4
        tm.assert_series_equal(s, Series([1, 3, 4], index=["foo", "bar", 3]))

    def test_partial_set_empty_frame(self):

        # partially set with an empty object
        # frame
        df = DataFrame()

        msg = "cannot set a frame with no defined columns"

        with pytest.raises(ValueError, match=msg):
            df.loc[1] = 1

        with pytest.raises(ValueError, match=msg):
            df.loc[1] = Series([1], index=["foo"])

        msg = "cannot set a frame with no defined index and a scalar"
        with pytest.raises(ValueError, match=msg):
            df.loc[:, 1] = 1

        # these work as they don't really change
        # anything but the index
        # GH5632
        expected = DataFrame(columns=["foo"], index=Index([], dtype="object"))

        def f():
            df = DataFrame(index=Index([], dtype="object"))
            df["foo"] = Series([], dtype="object")
            return df

        tm.assert_frame_equal(f(), expected)

        def f():
            df = DataFrame()
            df["foo"] = Series(df.index)
            return df

        tm.assert_frame_equal(f(), expected)

        def f():
            df = DataFrame()
            df["foo"] = df.index
            return df

        tm.assert_frame_equal(f(), expected)

        expected = DataFrame(columns=["foo"], index=Index([], dtype="int64"))
        expected["foo"] = expected["foo"].astype("float64")

        def f():
            df = DataFrame(index=Index([], dtype="int64"))
            df["foo"] = []
            return df

        tm.assert_frame_equal(f(), expected)

        def f():
            df = DataFrame(index=Index([], dtype="int64"))
            df["foo"] = Series(np.arange(len(df)), dtype="float64")
            return df

        tm.assert_frame_equal(f(), expected)

        def f():
            df = DataFrame(index=Index([], dtype="int64"))
            df["foo"] = range(len(df))
            return df

        expected = DataFrame(columns=["foo"], index=Index([], dtype="int64"))
        expected["foo"] = expected["foo"].astype("float64")
        tm.assert_frame_equal(f(), expected)

        df = DataFrame()
        tm.assert_index_equal(df.columns, Index([], dtype=object))
        df2 = DataFrame()
        df2[1] = Series([1], index=["foo"])
        df.loc[:, 1] = Series([1], index=["foo"])
        tm.assert_frame_equal(df, DataFrame([[1]], index=["foo"], columns=[1]))
        tm.assert_frame_equal(df, df2)

        # no index to start
        expected = DataFrame({0: Series(1, index=range(4))}, columns=["A", "B", 0])

        df = DataFrame(columns=["A", "B"])
        df[0] = Series(1, index=range(4))
        df.dtypes
        str(df)
        tm.assert_frame_equal(df, expected)

        df = DataFrame(columns=["A", "B"])
        df.loc[:, 0] = Series(1, index=range(4))
        df.dtypes
        str(df)
        tm.assert_frame_equal(df, expected)

    def test_partial_set_empty_frame_row(self):
        # GH5720, GH5744
        # don't create rows when empty
        expected = DataFrame(columns=["A", "B", "New"], index=Index([], dtype="int64"))
        expected["A"] = expected["A"].astype("int64")
        expected["B"] = expected["B"].astype("float64")
        expected["New"] = expected["New"].astype("float64")

        df = DataFrame({"A": [1, 2, 3], "B": [1.2, 4.2, 5.2]})
        y = df[df.A > 5]
        y["New"] = np.nan
        tm.assert_frame_equal(y, expected)
        # tm.assert_frame_equal(y,expected)

        expected = DataFrame(columns=["a", "b", "c c", "d"])
        expected["d"] = expected["d"].astype("int64")
        df = DataFrame(columns=["a", "b", "c c"])
        df["d"] = 3
        tm.assert_frame_equal(df, expected)
        tm.assert_series_equal(df["c c"], Series(name="c c", dtype=object))

        # reindex columns is ok
        df = DataFrame({"A": [1, 2, 3], "B": [1.2, 4.2, 5.2]})
        y = df[df.A > 5]
        result = y.reindex(columns=["A", "B", "C"])
        expected = DataFrame(columns=["A", "B", "C"], index=Index([], dtype="int64"))
        expected["A"] = expected["A"].astype("int64")
        expected["B"] = expected["B"].astype("float64")
        expected["C"] = expected["C"].astype("float64")
        tm.assert_frame_equal(result, expected)

    def test_partial_set_empty_frame_set_series(self):
        # GH 5756
        # setting with empty Series
        df = DataFrame(Series(dtype=object))
        tm.assert_frame_equal(df, DataFrame({0: Series(dtype=object)}))

        df = DataFrame(Series(name="foo", dtype=object))
        tm.assert_frame_equal(df, DataFrame({"foo": Series(dtype=object)}))

    def test_partial_set_empty_frame_empty_copy_assignment(self):
        # GH 5932
        # copy on empty with assignment fails
        df = DataFrame(index=[0])
        df = df.copy()
        df["a"] = 0
        expected = DataFrame(0, index=[0], columns=["a"])
        tm.assert_frame_equal(df, expected)

    def test_partial_set_empty_frame_empty_consistencies(self):
        # GH 6171
        # consistency on empty frames
        df = DataFrame(columns=["x", "y"])
        df["x"] = [1, 2]
        expected = DataFrame(dict(x=[1, 2], y=[np.nan, np.nan]))
        tm.assert_frame_equal(df, expected, check_dtype=False)

        df = DataFrame(columns=["x", "y"])
        df["x"] = ["1", "2"]
        expected = DataFrame(dict(x=["1", "2"], y=[np.nan, np.nan]), dtype=object)
        tm.assert_frame_equal(df, expected)

        df = DataFrame(columns=["x", "y"])
        df.loc[0, "x"] = 1
        expected = DataFrame(dict(x=[1], y=[np.nan]))
        tm.assert_frame_equal(df, expected, check_dtype=False)
