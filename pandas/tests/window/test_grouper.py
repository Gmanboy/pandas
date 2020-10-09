import numpy as np
import pytest

import pandas as pd
from pandas import DataFrame, Series
import pandas._testing as tm
from pandas.core.groupby.groupby import get_groupby


class TestGrouperGrouping:
    def setup_method(self):
        self.series = Series(np.arange(10))
        self.frame = DataFrame({"A": [1] * 20 + [2] * 12 + [3] * 8, "B": np.arange(40)})

    def test_mutated(self):

        msg = r"groupby\(\) got an unexpected keyword argument 'foo'"
        with pytest.raises(TypeError, match=msg):
            self.frame.groupby("A", foo=1)

        g = self.frame.groupby("A")
        assert not g.mutated
        g = get_groupby(self.frame, by="A", mutated=True)
        assert g.mutated

    def test_getitem(self):
        g = self.frame.groupby("A")
        g_mutated = get_groupby(self.frame, by="A", mutated=True)

        expected = g_mutated.B.apply(lambda x: x.rolling(2).mean())

        result = g.rolling(2).mean().B
        tm.assert_series_equal(result, expected)

        result = g.rolling(2).B.mean()
        tm.assert_series_equal(result, expected)

        result = g.B.rolling(2).mean()
        tm.assert_series_equal(result, expected)

        result = self.frame.B.groupby(self.frame.A).rolling(2).mean()
        tm.assert_series_equal(result, expected)

    def test_getitem_multiple(self):

        # GH 13174
        g = self.frame.groupby("A")
        r = g.rolling(2, min_periods=0)
        g_mutated = get_groupby(self.frame, by="A", mutated=True)
        expected = g_mutated.B.apply(lambda x: x.rolling(2, min_periods=0).count())

        result = r.B.count()
        tm.assert_series_equal(result, expected)

        result = r.B.count()
        tm.assert_series_equal(result, expected)

    @pytest.mark.parametrize(
        "f",
        [
            "sum",
            "mean",
            "min",
            "max",
            pytest.param(
                "count",
                marks=pytest.mark.filterwarnings("ignore:min_periods:FutureWarning"),
            ),
            "kurt",
            "skew",
        ],
    )
    def test_rolling(self, f):
        g = self.frame.groupby("A")
        r = g.rolling(window=4)

        result = getattr(r, f)()
        expected = g.apply(lambda x: getattr(x.rolling(4), f)())
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize("f", ["std", "var"])
    def test_rolling_ddof(self, f):
        g = self.frame.groupby("A")
        r = g.rolling(window=4)

        result = getattr(r, f)(ddof=1)
        expected = g.apply(lambda x: getattr(x.rolling(4), f)(ddof=1))
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize(
        "interpolation", ["linear", "lower", "higher", "midpoint", "nearest"]
    )
    def test_rolling_quantile(self, interpolation):
        g = self.frame.groupby("A")
        r = g.rolling(window=4)
        result = r.quantile(0.4, interpolation=interpolation)
        expected = g.apply(
            lambda x: x.rolling(4).quantile(0.4, interpolation=interpolation)
        )
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize("f", ["corr", "cov"])
    def test_rolling_corr_cov(self, f):
        g = self.frame.groupby("A")
        r = g.rolling(window=4)

        result = getattr(r, f)(self.frame)

        def func(x):
            return getattr(x.rolling(4), f)(self.frame)

        expected = g.apply(func)
        tm.assert_frame_equal(result, expected)

        result = getattr(r.B, f)(pairwise=True)

        def func(x):
            return getattr(x.B.rolling(4), f)(pairwise=True)

        expected = g.apply(func)
        tm.assert_series_equal(result, expected)

    def test_rolling_apply(self, raw):
        g = self.frame.groupby("A")
        r = g.rolling(window=4)

        # reduction
        result = r.apply(lambda x: x.sum(), raw=raw)
        expected = g.apply(lambda x: x.rolling(4).apply(lambda y: y.sum(), raw=raw))
        tm.assert_frame_equal(result, expected)

    def test_rolling_apply_mutability(self):
        # GH 14013
        df = pd.DataFrame({"A": ["foo"] * 3 + ["bar"] * 3, "B": [1] * 6})
        g = df.groupby("A")

        mi = pd.MultiIndex.from_tuples(
            [("bar", 3), ("bar", 4), ("bar", 5), ("foo", 0), ("foo", 1), ("foo", 2)]
        )

        mi.names = ["A", None]
        # Grouped column should not be a part of the output
        expected = pd.DataFrame([np.nan, 2.0, 2.0] * 2, columns=["B"], index=mi)

        result = g.rolling(window=2).sum()
        tm.assert_frame_equal(result, expected)

        # Call an arbitrary function on the groupby
        g.sum()

        # Make sure nothing has been mutated
        result = g.rolling(window=2).sum()
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize(
        "f", ["sum", "mean", "min", "max", "count", "kurt", "skew"]
    )
    def test_expanding(self, f):
        g = self.frame.groupby("A")
        r = g.expanding()

        result = getattr(r, f)()
        expected = g.apply(lambda x: getattr(x.expanding(), f)())
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize("f", ["std", "var"])
    def test_expanding_ddof(self, f):
        g = self.frame.groupby("A")
        r = g.expanding()

        result = getattr(r, f)(ddof=0)
        expected = g.apply(lambda x: getattr(x.expanding(), f)(ddof=0))
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize(
        "interpolation", ["linear", "lower", "higher", "midpoint", "nearest"]
    )
    def test_expanding_quantile(self, interpolation):
        g = self.frame.groupby("A")
        r = g.expanding()
        result = r.quantile(0.4, interpolation=interpolation)
        expected = g.apply(
            lambda x: x.expanding().quantile(0.4, interpolation=interpolation)
        )
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize("f", ["corr", "cov"])
    def test_expanding_corr_cov(self, f):
        g = self.frame.groupby("A")
        r = g.expanding()

        result = getattr(r, f)(self.frame)

        def func(x):
            return getattr(x.expanding(), f)(self.frame)

        expected = g.apply(func)
        tm.assert_frame_equal(result, expected)

        result = getattr(r.B, f)(pairwise=True)

        def func(x):
            return getattr(x.B.expanding(), f)(pairwise=True)

        expected = g.apply(func)
        tm.assert_series_equal(result, expected)

    def test_expanding_apply(self, raw):
        g = self.frame.groupby("A")
        r = g.expanding()

        # reduction
        result = r.apply(lambda x: x.sum(), raw=raw)
        expected = g.apply(lambda x: x.expanding().apply(lambda y: y.sum(), raw=raw))
        tm.assert_frame_equal(result, expected)

    @pytest.mark.parametrize("expected_value,raw_value", [[1.0, True], [0.0, False]])
    def test_groupby_rolling(self, expected_value, raw_value):
        # GH 31754

        def foo(x):
            return int(isinstance(x, np.ndarray))

        df = pd.DataFrame({"id": [1, 1, 1], "value": [1, 2, 3]})
        result = df.groupby("id").value.rolling(1).apply(foo, raw=raw_value)
        expected = Series(
            [expected_value] * 3,
            index=pd.MultiIndex.from_tuples(
                ((1, 0), (1, 1), (1, 2)), names=["id", None]
            ),
            name="value",
        )
        tm.assert_series_equal(result, expected)

    def test_groupby_rolling_center_center(self):
        # GH 35552
        series = Series(range(1, 6))
        result = series.groupby(series).rolling(center=True, window=3).mean()
        expected = Series(
            [np.nan] * 5,
            index=pd.MultiIndex.from_tuples(((1, 0), (2, 1), (3, 2), (4, 3), (5, 4))),
        )
        tm.assert_series_equal(result, expected)

        series = Series(range(1, 5))
        result = series.groupby(series).rolling(center=True, window=3).mean()
        expected = Series(
            [np.nan] * 4,
            index=pd.MultiIndex.from_tuples(((1, 0), (2, 1), (3, 2), (4, 3))),
        )
        tm.assert_series_equal(result, expected)

        df = pd.DataFrame({"a": ["a"] * 5 + ["b"] * 6, "b": range(11)})
        result = df.groupby("a").rolling(center=True, window=3).mean()
        expected = pd.DataFrame(
            [np.nan, 1, 2, 3, np.nan, np.nan, 6, 7, 8, 9, np.nan],
            index=pd.MultiIndex.from_tuples(
                (
                    ("a", 0),
                    ("a", 1),
                    ("a", 2),
                    ("a", 3),
                    ("a", 4),
                    ("b", 5),
                    ("b", 6),
                    ("b", 7),
                    ("b", 8),
                    ("b", 9),
                    ("b", 10),
                ),
                names=["a", None],
            ),
            columns=["b"],
        )
        tm.assert_frame_equal(result, expected)

        df = pd.DataFrame({"a": ["a"] * 5 + ["b"] * 5, "b": range(10)})
        result = df.groupby("a").rolling(center=True, window=3).mean()
        expected = pd.DataFrame(
            [np.nan, 1, 2, 3, np.nan, np.nan, 6, 7, 8, np.nan],
            index=pd.MultiIndex.from_tuples(
                (
                    ("a", 0),
                    ("a", 1),
                    ("a", 2),
                    ("a", 3),
                    ("a", 4),
                    ("b", 5),
                    ("b", 6),
                    ("b", 7),
                    ("b", 8),
                    ("b", 9),
                ),
                names=["a", None],
            ),
            columns=["b"],
        )
        tm.assert_frame_equal(result, expected)

    def test_groupby_subselect_rolling(self):
        # GH 35486
        df = DataFrame(
            {"a": [1, 2, 3, 2], "b": [4.0, 2.0, 3.0, 1.0], "c": [10, 20, 30, 20]}
        )
        result = df.groupby("a")[["b"]].rolling(2).max()
        expected = DataFrame(
            [np.nan, np.nan, 2.0, np.nan],
            columns=["b"],
            index=pd.MultiIndex.from_tuples(
                ((1, 0), (2, 1), (2, 3), (3, 2)), names=["a", None]
            ),
        )
        tm.assert_frame_equal(result, expected)

        result = df.groupby("a")["b"].rolling(2).max()
        expected = Series(
            [np.nan, np.nan, 2.0, np.nan],
            index=pd.MultiIndex.from_tuples(
                ((1, 0), (2, 1), (2, 3), (3, 2)), names=["a", None]
            ),
            name="b",
        )
        tm.assert_series_equal(result, expected)

    def test_groupby_rolling_custom_indexer(self):
        # GH 35557
        class SimpleIndexer(pd.api.indexers.BaseIndexer):
            def get_window_bounds(
                self, num_values=0, min_periods=None, center=None, closed=None
            ):
                min_periods = self.window_size if min_periods is None else 0
                end = np.arange(num_values, dtype=np.int64) + 1
                start = end.copy() - self.window_size
                start[start < 0] = min_periods
                return start, end

        df = pd.DataFrame(
            {"a": [1.0, 2.0, 3.0, 4.0, 5.0] * 3}, index=[0] * 5 + [1] * 5 + [2] * 5
        )
        result = (
            df.groupby(df.index)
            .rolling(SimpleIndexer(window_size=3), min_periods=1)
            .sum()
        )
        expected = df.groupby(df.index).rolling(window=3, min_periods=1).sum()
        tm.assert_frame_equal(result, expected)

    def test_groupby_rolling_subset_with_closed(self):
        # GH 35549
        df = pd.DataFrame(
            {
                "column1": range(6),
                "column2": range(6),
                "group": 3 * ["A", "B"],
                "date": [pd.Timestamp("2019-01-01")] * 6,
            }
        )
        result = (
            df.groupby("group").rolling("1D", on="date", closed="left")["column1"].sum()
        )
        expected = Series(
            [np.nan, 0.0, 2.0, np.nan, 1.0, 4.0],
            index=pd.MultiIndex.from_tuples(
                [("A", pd.Timestamp("2019-01-01"))] * 3
                + [("B", pd.Timestamp("2019-01-01"))] * 3,
                names=["group", "date"],
            ),
            name="column1",
        )
        tm.assert_series_equal(result, expected)

    def test_groupby_subset_rolling_subset_with_closed(self):
        # GH 35549
        df = pd.DataFrame(
            {
                "column1": range(6),
                "column2": range(6),
                "group": 3 * ["A", "B"],
                "date": [pd.Timestamp("2019-01-01")] * 6,
            }
        )

        result = (
            df.groupby("group")[["column1", "date"]]
            .rolling("1D", on="date", closed="left")["column1"]
            .sum()
        )
        expected = Series(
            [np.nan, 0.0, 2.0, np.nan, 1.0, 4.0],
            index=pd.MultiIndex.from_tuples(
                [("A", pd.Timestamp("2019-01-01"))] * 3
                + [("B", pd.Timestamp("2019-01-01"))] * 3,
                names=["group", "date"],
            ),
            name="column1",
        )
        tm.assert_series_equal(result, expected)

    @pytest.mark.parametrize("func", ["max", "min"])
    def test_groupby_rolling_index_changed(self, func):
        # GH: #36018 nlevels of MultiIndex changed
        ds = Series(
            [1, 2, 2],
            index=pd.MultiIndex.from_tuples(
                [("a", "x"), ("a", "y"), ("c", "z")], names=["1", "2"]
            ),
            name="a",
        )

        result = getattr(ds.groupby(ds).rolling(2), func)()
        expected = Series(
            [np.nan, np.nan, 2.0],
            index=pd.MultiIndex.from_tuples(
                [(1, "a", "x"), (2, "a", "y"), (2, "c", "z")], names=["a", "1", "2"]
            ),
            name="a",
        )
        tm.assert_series_equal(result, expected)

    def test_groupby_rolling_empty_frame(self):
        # GH 36197
        expected = pd.DataFrame({"s1": []})
        result = expected.groupby("s1").rolling(window=1).sum()
        expected.index = pd.MultiIndex.from_tuples([], names=["s1", None])
        tm.assert_frame_equal(result, expected)

        expected = pd.DataFrame({"s1": [], "s2": []})
        result = expected.groupby(["s1", "s2"]).rolling(window=1).sum()
        expected.index = pd.MultiIndex.from_tuples([], names=["s1", "s2", None])
        tm.assert_frame_equal(result, expected)

    def test_groupby_rolling_string_index(self):
        # GH: 36727
        df = pd.DataFrame(
            [
                ["A", "group_1", pd.Timestamp(2019, 1, 1, 9)],
                ["B", "group_1", pd.Timestamp(2019, 1, 2, 9)],
                ["Z", "group_2", pd.Timestamp(2019, 1, 3, 9)],
                ["H", "group_1", pd.Timestamp(2019, 1, 6, 9)],
                ["E", "group_2", pd.Timestamp(2019, 1, 20, 9)],
            ],
            columns=["index", "group", "eventTime"],
        ).set_index("index")

        groups = df.groupby("group")
        df["count_to_date"] = groups.cumcount()
        rolling_groups = groups.rolling("10d", on="eventTime")
        result = rolling_groups.apply(lambda df: df.shape[0])
        expected = pd.DataFrame(
            [
                ["A", "group_1", pd.Timestamp(2019, 1, 1, 9), 1.0],
                ["B", "group_1", pd.Timestamp(2019, 1, 2, 9), 2.0],
                ["H", "group_1", pd.Timestamp(2019, 1, 6, 9), 3.0],
                ["Z", "group_2", pd.Timestamp(2019, 1, 3, 9), 1.0],
                ["E", "group_2", pd.Timestamp(2019, 1, 20, 9), 1.0],
            ],
            columns=["index", "group", "eventTime", "count_to_date"],
        ).set_index(["group", "index"])
        tm.assert_frame_equal(result, expected)

    def test_groupby_rolling_no_sort(self):
        # GH 36889
        result = (
            pd.DataFrame({"foo": [2, 1], "bar": [2, 1]})
            .groupby("foo", sort=False)
            .rolling(1)
            .min()
        )
        expected = pd.DataFrame(
            np.array([[2.0, 2.0], [1.0, 1.0]]),
            columns=["foo", "bar"],
            index=pd.MultiIndex.from_tuples([(2, 0), (1, 1)], names=["foo", None]),
        )
        tm.assert_frame_equal(result, expected)
