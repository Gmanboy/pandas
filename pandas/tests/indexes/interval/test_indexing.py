import re

import numpy as np
import pytest

from pandas import (
    CategoricalIndex,
    Interval,
    IntervalIndex,
    Timedelta,
    date_range,
    timedelta_range,
)
import pandas._testing as tm
from pandas.core.indexes.base import InvalidIndexError


class TestGetLoc:
    @pytest.mark.parametrize("side", ["right", "left", "both", "neither"])
    def test_get_loc_interval(self, closed, side):

        idx = IntervalIndex.from_tuples([(0, 1), (2, 3)], closed=closed)

        for bound in [[0, 1], [1, 2], [2, 3], [3, 4], [0, 2], [2.5, 3], [-1, 4]]:
            # if get_loc is supplied an interval, it should only search
            # for exact matches, not overlaps or covers, else KeyError.
            msg = re.escape(f"Interval({bound[0]}, {bound[1]}, closed='{side}')")
            if closed == side:
                if bound == [0, 1]:
                    assert idx.get_loc(Interval(0, 1, closed=side)) == 0
                elif bound == [2, 3]:
                    assert idx.get_loc(Interval(2, 3, closed=side)) == 1
                else:
                    with pytest.raises(KeyError, match=msg):
                        idx.get_loc(Interval(*bound, closed=side))
            else:
                with pytest.raises(KeyError, match=msg):
                    idx.get_loc(Interval(*bound, closed=side))

    @pytest.mark.parametrize("scalar", [-0.5, 0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5])
    def test_get_loc_scalar(self, closed, scalar):

        # correct = {side: {query: answer}}.
        # If query is not in the dict, that query should raise a KeyError
        correct = {
            "right": {0.5: 0, 1: 0, 2.5: 1, 3: 1},
            "left": {0: 0, 0.5: 0, 2: 1, 2.5: 1},
            "both": {0: 0, 0.5: 0, 1: 0, 2: 1, 2.5: 1, 3: 1},
            "neither": {0.5: 0, 2.5: 1},
        }

        idx = IntervalIndex.from_tuples([(0, 1), (2, 3)], closed=closed)

        # if get_loc is supplied a scalar, it should return the index of
        # the interval which contains the scalar, or KeyError.
        if scalar in correct[closed].keys():
            assert idx.get_loc(scalar) == correct[closed][scalar]
        else:
            with pytest.raises(KeyError, match=str(scalar)):
                idx.get_loc(scalar)

    @pytest.mark.parametrize("scalar", [-1, 0, 0.5, 3, 4.5, 5, 6])
    def test_get_loc_length_one_scalar(self, scalar, closed):
        # GH 20921
        index = IntervalIndex.from_tuples([(0, 5)], closed=closed)
        if scalar in index[0]:
            result = index.get_loc(scalar)
            assert result == 0
        else:
            with pytest.raises(KeyError, match=str(scalar)):
                index.get_loc(scalar)

    @pytest.mark.parametrize("other_closed", ["left", "right", "both", "neither"])
    @pytest.mark.parametrize("left, right", [(0, 5), (-1, 4), (-1, 6), (6, 7)])
    def test_get_loc_length_one_interval(self, left, right, closed, other_closed):
        # GH 20921
        index = IntervalIndex.from_tuples([(0, 5)], closed=closed)
        interval = Interval(left, right, closed=other_closed)
        if interval == index[0]:
            result = index.get_loc(interval)
            assert result == 0
        else:
            with pytest.raises(
                KeyError,
                match=re.escape(f"Interval({left}, {right}, closed='{other_closed}')"),
            ):
                index.get_loc(interval)

    # Make consistent with test_interval_new.py (see #16316, #16386)
    @pytest.mark.parametrize(
        "breaks",
        [
            date_range("20180101", periods=4),
            date_range("20180101", periods=4, tz="US/Eastern"),
            timedelta_range("0 days", periods=4),
        ],
        ids=lambda x: str(x.dtype),
    )
    def test_get_loc_datetimelike_nonoverlapping(self, breaks):
        # GH 20636
        # nonoverlapping = IntervalIndex method and no i8 conversion
        index = IntervalIndex.from_breaks(breaks)

        value = index[0].mid
        result = index.get_loc(value)
        expected = 0
        assert result == expected

        interval = Interval(index[0].left, index[0].right)
        result = index.get_loc(interval)
        expected = 0
        assert result == expected

    @pytest.mark.parametrize(
        "arrays",
        [
            (date_range("20180101", periods=4), date_range("20180103", periods=4)),
            (
                date_range("20180101", periods=4, tz="US/Eastern"),
                date_range("20180103", periods=4, tz="US/Eastern"),
            ),
            (
                timedelta_range("0 days", periods=4),
                timedelta_range("2 days", periods=4),
            ),
        ],
        ids=lambda x: str(x[0].dtype),
    )
    def test_get_loc_datetimelike_overlapping(self, arrays):
        # GH 20636
        index = IntervalIndex.from_arrays(*arrays)

        value = index[0].mid + Timedelta("12 hours")
        result = index.get_loc(value)
        expected = slice(0, 2, None)
        assert result == expected

        interval = Interval(index[0].left, index[0].right)
        result = index.get_loc(interval)
        expected = 0
        assert result == expected

    @pytest.mark.parametrize(
        "values",
        [
            date_range("2018-01-04", periods=4, freq="-1D"),
            date_range("2018-01-04", periods=4, freq="-1D", tz="US/Eastern"),
            timedelta_range("3 days", periods=4, freq="-1D"),
            np.arange(3.0, -1.0, -1.0),
            np.arange(3, -1, -1),
        ],
        ids=lambda x: str(x.dtype),
    )
    def test_get_loc_decreasing(self, values):
        # GH 25860
        index = IntervalIndex.from_arrays(values[1:], values[:-1])
        result = index.get_loc(index[0])
        expected = 0
        assert result == expected

    @pytest.mark.parametrize("key", [[5], (2, 3)])
    def test_get_loc_non_scalar_errors(self, key):
        # GH 31117
        idx = IntervalIndex.from_tuples([(1, 3), (2, 4), (3, 5), (7, 10), (3, 10)])

        msg = str(key)
        with pytest.raises(InvalidIndexError, match=msg):
            idx.get_loc(key)


class TestGetIndexer:
    @pytest.mark.parametrize(
        "query, expected",
        [
            ([Interval(2, 4, closed="right")], [1]),
            ([Interval(2, 4, closed="left")], [-1]),
            ([Interval(2, 4, closed="both")], [-1]),
            ([Interval(2, 4, closed="neither")], [-1]),
            ([Interval(1, 4, closed="right")], [-1]),
            ([Interval(0, 4, closed="right")], [-1]),
            ([Interval(0.5, 1.5, closed="right")], [-1]),
            ([Interval(2, 4, closed="right"), Interval(0, 1, closed="right")], [1, -1]),
            ([Interval(2, 4, closed="right"), Interval(2, 4, closed="right")], [1, 1]),
            ([Interval(5, 7, closed="right"), Interval(2, 4, closed="right")], [2, 1]),
            ([Interval(2, 4, closed="right"), Interval(2, 4, closed="left")], [1, -1]),
        ],
    )
    def test_get_indexer_with_interval(self, query, expected):

        tuples = [(0, 2), (2, 4), (5, 7)]
        index = IntervalIndex.from_tuples(tuples, closed="right")

        result = index.get_indexer(query)
        expected = np.array(expected, dtype="intp")
        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize(
        "query, expected",
        [
            ([-0.5], [-1]),
            ([0], [-1]),
            ([0.5], [0]),
            ([1], [0]),
            ([1.5], [1]),
            ([2], [1]),
            ([2.5], [-1]),
            ([3], [-1]),
            ([3.5], [2]),
            ([4], [2]),
            ([4.5], [-1]),
            ([1, 2], [0, 1]),
            ([1, 2, 3], [0, 1, -1]),
            ([1, 2, 3, 4], [0, 1, -1, 2]),
            ([1, 2, 3, 4, 2], [0, 1, -1, 2, 1]),
        ],
    )
    def test_get_indexer_with_int_and_float(self, query, expected):

        tuples = [(0, 1), (1, 2), (3, 4)]
        index = IntervalIndex.from_tuples(tuples, closed="right")

        result = index.get_indexer(query)
        expected = np.array(expected, dtype="intp")
        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize("item", [[3], np.arange(0.5, 5, 0.5)])
    def test_get_indexer_length_one(self, item, closed):
        # GH 17284
        index = IntervalIndex.from_tuples([(0, 5)], closed=closed)
        result = index.get_indexer(item)
        expected = np.array([0] * len(item), dtype="intp")
        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize("size", [1, 5])
    def test_get_indexer_length_one_interval(self, size, closed):
        # GH 17284
        index = IntervalIndex.from_tuples([(0, 5)], closed=closed)
        result = index.get_indexer([Interval(0, 5, closed)] * size)
        expected = np.array([0] * size, dtype="intp")
        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize(
        "target",
        [
            IntervalIndex.from_tuples([(7, 8), (1, 2), (3, 4), (0, 1)]),
            IntervalIndex.from_tuples([(0, 1), (1, 2), (3, 4), np.nan]),
            IntervalIndex.from_tuples([(0, 1), (1, 2), (3, 4)], closed="both"),
            [-1, 0, 0.5, 1, 2, 2.5, np.nan],
            ["foo", "foo", "bar", "baz"],
        ],
    )
    def test_get_indexer_categorical(self, target, ordered):
        # GH 30063: categorical and non-categorical results should be consistent
        index = IntervalIndex.from_tuples([(0, 1), (1, 2), (3, 4)])
        categorical_target = CategoricalIndex(target, ordered=ordered)

        result = index.get_indexer(categorical_target)
        expected = index.get_indexer(target)
        tm.assert_numpy_array_equal(result, expected)

    @pytest.mark.parametrize(
        "tuples, closed",
        [
            ([(0, 2), (1, 3), (3, 4)], "neither"),
            ([(0, 5), (1, 4), (6, 7)], "left"),
            ([(0, 1), (0, 1), (1, 2)], "right"),
            ([(0, 1), (2, 3), (3, 4)], "both"),
        ],
    )
    def test_get_indexer_errors(self, tuples, closed):
        # IntervalIndex needs non-overlapping for uniqueness when querying
        index = IntervalIndex.from_tuples(tuples, closed=closed)

        msg = (
            "cannot handle overlapping indices; use "
            "IntervalIndex.get_indexer_non_unique"
        )
        with pytest.raises(InvalidIndexError, match=msg):
            index.get_indexer([0, 2])

    @pytest.mark.parametrize(
        "query, expected",
        [
            ([-0.5], ([-1], [0])),
            ([0], ([0], [])),
            ([0.5], ([0], [])),
            ([1], ([0, 1], [])),
            ([1.5], ([0, 1], [])),
            ([2], ([0, 1, 2], [])),
            ([2.5], ([1, 2], [])),
            ([3], ([2], [])),
            ([3.5], ([2], [])),
            ([4], ([-1], [0])),
            ([4.5], ([-1], [0])),
            ([1, 2], ([0, 1, 0, 1, 2], [])),
            ([1, 2, 3], ([0, 1, 0, 1, 2, 2], [])),
            ([1, 2, 3, 4], ([0, 1, 0, 1, 2, 2, -1], [3])),
            ([1, 2, 3, 4, 2], ([0, 1, 0, 1, 2, 2, -1, 0, 1, 2], [3])),
        ],
    )
    def test_get_indexer_non_unique_with_int_and_float(self, query, expected):

        tuples = [(0, 2.5), (1, 3), (2, 4)]
        index = IntervalIndex.from_tuples(tuples, closed="left")

        result_indexer, result_missing = index.get_indexer_non_unique(query)
        expected_indexer = np.array(expected[0], dtype="intp")
        expected_missing = np.array(expected[1], dtype="intp")

        tm.assert_numpy_array_equal(result_indexer, expected_indexer)
        tm.assert_numpy_array_equal(result_missing, expected_missing)

        # TODO we may also want to test get_indexer for the case when
        # the intervals are duplicated, decreasing, non-monotonic, etc..

    def test_get_indexer_non_monotonic(self):
        # GH 16410
        idx1 = IntervalIndex.from_tuples([(2, 3), (4, 5), (0, 1)])
        idx2 = IntervalIndex.from_tuples([(0, 1), (2, 3), (6, 7), (8, 9)])
        result = idx1.get_indexer(idx2)
        expected = np.array([2, 0, -1, -1], dtype=np.intp)
        tm.assert_numpy_array_equal(result, expected)

        result = idx1.get_indexer(idx1[1:])
        expected = np.array([1, 2], dtype=np.intp)
        tm.assert_numpy_array_equal(result, expected)


class TestSliceLocs:
    def test_slice_locs_with_interval(self):

        # increasing monotonically
        index = IntervalIndex.from_tuples([(0, 2), (1, 3), (2, 4)])

        assert index.slice_locs(start=Interval(0, 2), end=Interval(2, 4)) == (0, 3)
        assert index.slice_locs(start=Interval(0, 2)) == (0, 3)
        assert index.slice_locs(end=Interval(2, 4)) == (0, 3)
        assert index.slice_locs(end=Interval(0, 2)) == (0, 1)
        assert index.slice_locs(start=Interval(2, 4), end=Interval(0, 2)) == (2, 1)

        # decreasing monotonically
        index = IntervalIndex.from_tuples([(2, 4), (1, 3), (0, 2)])

        assert index.slice_locs(start=Interval(0, 2), end=Interval(2, 4)) == (2, 1)
        assert index.slice_locs(start=Interval(0, 2)) == (2, 3)
        assert index.slice_locs(end=Interval(2, 4)) == (0, 1)
        assert index.slice_locs(end=Interval(0, 2)) == (0, 3)
        assert index.slice_locs(start=Interval(2, 4), end=Interval(0, 2)) == (0, 3)

        # sorted duplicates
        index = IntervalIndex.from_tuples([(0, 2), (0, 2), (2, 4)])

        assert index.slice_locs(start=Interval(0, 2), end=Interval(2, 4)) == (0, 3)
        assert index.slice_locs(start=Interval(0, 2)) == (0, 3)
        assert index.slice_locs(end=Interval(2, 4)) == (0, 3)
        assert index.slice_locs(end=Interval(0, 2)) == (0, 2)
        assert index.slice_locs(start=Interval(2, 4), end=Interval(0, 2)) == (2, 2)

        # unsorted duplicates
        index = IntervalIndex.from_tuples([(0, 2), (2, 4), (0, 2)])

        with pytest.raises(
            KeyError,
            match=re.escape(
                '"Cannot get left slice bound for non-unique label: '
                "Interval(0, 2, closed='right')\""
            ),
        ):
            index.slice_locs(start=Interval(0, 2), end=Interval(2, 4))

        with pytest.raises(
            KeyError,
            match=re.escape(
                '"Cannot get left slice bound for non-unique label: '
                "Interval(0, 2, closed='right')\""
            ),
        ):
            index.slice_locs(start=Interval(0, 2))

        assert index.slice_locs(end=Interval(2, 4)) == (0, 2)

        with pytest.raises(
            KeyError,
            match=re.escape(
                '"Cannot get right slice bound for non-unique label: '
                "Interval(0, 2, closed='right')\""
            ),
        ):
            index.slice_locs(end=Interval(0, 2))

        with pytest.raises(
            KeyError,
            match=re.escape(
                '"Cannot get right slice bound for non-unique label: '
                "Interval(0, 2, closed='right')\""
            ),
        ):
            index.slice_locs(start=Interval(2, 4), end=Interval(0, 2))

        # another unsorted duplicates
        index = IntervalIndex.from_tuples([(0, 2), (0, 2), (2, 4), (1, 3)])

        assert index.slice_locs(start=Interval(0, 2), end=Interval(2, 4)) == (0, 3)
        assert index.slice_locs(start=Interval(0, 2)) == (0, 4)
        assert index.slice_locs(end=Interval(2, 4)) == (0, 3)
        assert index.slice_locs(end=Interval(0, 2)) == (0, 2)
        assert index.slice_locs(start=Interval(2, 4), end=Interval(0, 2)) == (2, 2)

    def test_slice_locs_with_ints_and_floats_succeeds(self):

        # increasing non-overlapping
        index = IntervalIndex.from_tuples([(0, 1), (1, 2), (3, 4)])

        assert index.slice_locs(0, 1) == (0, 1)
        assert index.slice_locs(0, 2) == (0, 2)
        assert index.slice_locs(0, 3) == (0, 2)
        assert index.slice_locs(3, 1) == (2, 1)
        assert index.slice_locs(3, 4) == (2, 3)
        assert index.slice_locs(0, 4) == (0, 3)

        # decreasing non-overlapping
        index = IntervalIndex.from_tuples([(3, 4), (1, 2), (0, 1)])
        assert index.slice_locs(0, 1) == (3, 3)
        assert index.slice_locs(0, 2) == (3, 2)
        assert index.slice_locs(0, 3) == (3, 1)
        assert index.slice_locs(3, 1) == (1, 3)
        assert index.slice_locs(3, 4) == (1, 1)
        assert index.slice_locs(0, 4) == (3, 1)

    @pytest.mark.parametrize("query", [[0, 1], [0, 2], [0, 3], [0, 4]])
    @pytest.mark.parametrize(
        "tuples",
        [
            [(0, 2), (1, 3), (2, 4)],
            [(2, 4), (1, 3), (0, 2)],
            [(0, 2), (0, 2), (2, 4)],
            [(0, 2), (2, 4), (0, 2)],
            [(0, 2), (0, 2), (2, 4), (1, 3)],
        ],
    )
    def test_slice_locs_with_ints_and_floats_errors(self, tuples, query):
        start, stop = query
        index = IntervalIndex.from_tuples(tuples)
        with pytest.raises(
            KeyError,
            match=(
                "'can only get slices from an IntervalIndex if bounds are "
                "non-overlapping and all monotonic increasing or decreasing'"
            ),
        ):
            index.slice_locs(start, stop)
