from datetime import datetime, time, timedelta

import numpy as np
import pytest

import pandas as pd
from pandas import DatetimeIndex, Index, Timestamp, date_range, notna
import pandas._testing as tm
from pandas.core.indexes.base import InvalidIndexError

from pandas.tseries.offsets import BDay, CDay

START, END = datetime(2009, 1, 1), datetime(2010, 1, 1)


class TestGetItem:
    def test_ellipsis(self):
        # GH#21282
        idx = pd.date_range(
            "2011-01-01", "2011-01-31", freq="D", tz="Asia/Tokyo", name="idx"
        )

        result = idx[...]
        assert result.equals(idx)
        assert result is not idx

    def test_getitem_slice_keeps_name(self):
        # GH4226
        st = pd.Timestamp("2013-07-01 00:00:00", tz="America/Los_Angeles")
        et = pd.Timestamp("2013-07-02 00:00:00", tz="America/Los_Angeles")
        dr = pd.date_range(st, et, freq="H", name="timebucket")
        assert dr[1:].name == dr.name

    def test_getitem(self):
        idx1 = pd.date_range("2011-01-01", "2011-01-31", freq="D", name="idx")
        idx2 = pd.date_range(
            "2011-01-01", "2011-01-31", freq="D", tz="Asia/Tokyo", name="idx"
        )

        for idx in [idx1, idx2]:
            result = idx[0]
            assert result == Timestamp("2011-01-01", tz=idx.tz)

            result = idx[0:5]
            expected = pd.date_range(
                "2011-01-01", "2011-01-05", freq="D", tz=idx.tz, name="idx"
            )
            tm.assert_index_equal(result, expected)
            assert result.freq == expected.freq

            result = idx[0:10:2]
            expected = pd.date_range(
                "2011-01-01", "2011-01-09", freq="2D", tz=idx.tz, name="idx"
            )
            tm.assert_index_equal(result, expected)
            assert result.freq == expected.freq

            result = idx[-20:-5:3]
            expected = pd.date_range(
                "2011-01-12", "2011-01-24", freq="3D", tz=idx.tz, name="idx"
            )
            tm.assert_index_equal(result, expected)
            assert result.freq == expected.freq

            result = idx[4::-1]
            expected = DatetimeIndex(
                ["2011-01-05", "2011-01-04", "2011-01-03", "2011-01-02", "2011-01-01"],
                freq="-1D",
                tz=idx.tz,
                name="idx",
            )
            tm.assert_index_equal(result, expected)
            assert result.freq == expected.freq

    def test_dti_business_getitem(self):
        rng = pd.bdate_range(START, END)
        smaller = rng[:5]
        exp = DatetimeIndex(rng.view(np.ndarray)[:5], freq="B")
        tm.assert_index_equal(smaller, exp)
        assert smaller.freq == exp.freq

        assert smaller.freq == rng.freq

        sliced = rng[::5]
        assert sliced.freq == BDay() * 5

        fancy_indexed = rng[[4, 3, 2, 1, 0]]
        assert len(fancy_indexed) == 5
        assert isinstance(fancy_indexed, DatetimeIndex)
        assert fancy_indexed.freq is None

        # 32-bit vs. 64-bit platforms
        assert rng[4] == rng[np.int_(4)]

    def test_dti_business_getitem_matplotlib_hackaround(self):
        rng = pd.bdate_range(START, END)
        with tm.assert_produces_warning(DeprecationWarning):
            # GH#30588 multi-dimensional indexing deprecated
            values = rng[:, None]
        expected = rng.values[:, None]
        tm.assert_numpy_array_equal(values, expected)

    def test_dti_custom_getitem(self):
        rng = pd.bdate_range(START, END, freq="C")
        smaller = rng[:5]
        exp = DatetimeIndex(rng.view(np.ndarray)[:5], freq="C")
        tm.assert_index_equal(smaller, exp)
        assert smaller.freq == exp.freq
        assert smaller.freq == rng.freq

        sliced = rng[::5]
        assert sliced.freq == CDay() * 5

        fancy_indexed = rng[[4, 3, 2, 1, 0]]
        assert len(fancy_indexed) == 5
        assert isinstance(fancy_indexed, DatetimeIndex)
        assert fancy_indexed.freq is None

        # 32-bit vs. 64-bit platforms
        assert rng[4] == rng[np.int_(4)]

    def test_dti_custom_getitem_matplotlib_hackaround(self):
        rng = pd.bdate_range(START, END, freq="C")
        with tm.assert_produces_warning(DeprecationWarning):
            # GH#30588 multi-dimensional indexing deprecated
            values = rng[:, None]
        expected = rng.values[:, None]
        tm.assert_numpy_array_equal(values, expected)

    def test_getitem_int_list(self):
        dti = date_range(start="1/1/2005", end="12/1/2005", freq="M")
        dti2 = dti[[1, 3, 5]]

        v1 = dti2[0]
        v2 = dti2[1]
        v3 = dti2[2]

        assert v1 == Timestamp("2/28/2005")
        assert v2 == Timestamp("4/30/2005")
        assert v3 == Timestamp("6/30/2005")

        # getitem with non-slice drops freq
        assert dti2.freq is None


class TestWhere:
    def test_where_doesnt_retain_freq(self):
        dti = date_range("20130101", periods=3, freq="D", name="idx")
        cond = [True, True, False]
        expected = DatetimeIndex([dti[0], dti[1], dti[0]], freq=None, name="idx")

        result = dti.where(cond, dti[::-1])
        tm.assert_index_equal(result, expected)

    def test_where_other(self):
        # other is ndarray or Index
        i = pd.date_range("20130101", periods=3, tz="US/Eastern")

        for arr in [np.nan, pd.NaT]:
            result = i.where(notna(i), other=np.nan)
            expected = i
            tm.assert_index_equal(result, expected)

        i2 = i.copy()
        i2 = Index([pd.NaT, pd.NaT] + i[2:].tolist())
        result = i.where(notna(i2), i2)
        tm.assert_index_equal(result, i2)

        i2 = i.copy()
        i2 = Index([pd.NaT, pd.NaT] + i[2:].tolist())
        result = i.where(notna(i2), i2._values)
        tm.assert_index_equal(result, i2)

    def test_where_invalid_dtypes(self):
        dti = pd.date_range("20130101", periods=3, tz="US/Eastern")

        i2 = Index([pd.NaT, pd.NaT] + dti[2:].tolist())

        with pytest.raises(TypeError, match="Where requires matching dtype"):
            # passing tz-naive ndarray to tzaware DTI
            dti.where(notna(i2), i2.values)

        with pytest.raises(TypeError, match="Where requires matching dtype"):
            # passing tz-aware DTI to tznaive DTI
            dti.tz_localize(None).where(notna(i2), i2)

        with pytest.raises(TypeError, match="Where requires matching dtype"):
            dti.where(notna(i2), i2.tz_localize(None).to_period("D"))

        with pytest.raises(TypeError, match="Where requires matching dtype"):
            dti.where(notna(i2), i2.asi8.view("timedelta64[ns]"))

        with pytest.raises(TypeError, match="Where requires matching dtype"):
            dti.where(notna(i2), i2.asi8)

        with pytest.raises(TypeError, match="Where requires matching dtype"):
            # non-matching scalar
            dti.where(notna(i2), pd.Timedelta(days=4))

    def test_where_mismatched_nat(self, tz_aware_fixture):
        tz = tz_aware_fixture
        dti = pd.date_range("2013-01-01", periods=3, tz=tz)
        cond = np.array([True, False, True])

        msg = "Where requires matching dtype"
        with pytest.raises(TypeError, match=msg):
            # wrong-dtyped NaT
            dti.where(cond, np.timedelta64("NaT", "ns"))

    def test_where_tz(self):
        i = pd.date_range("20130101", periods=3, tz="US/Eastern")
        result = i.where(notna(i))
        expected = i
        tm.assert_index_equal(result, expected)

        i2 = i.copy()
        i2 = Index([pd.NaT, pd.NaT] + i[2:].tolist())
        result = i.where(notna(i2))
        expected = i2
        tm.assert_index_equal(result, expected)


class TestTake:
    def test_take(self):
        # GH#10295
        idx1 = pd.date_range("2011-01-01", "2011-01-31", freq="D", name="idx")
        idx2 = pd.date_range(
            "2011-01-01", "2011-01-31", freq="D", tz="Asia/Tokyo", name="idx"
        )

        for idx in [idx1, idx2]:
            result = idx.take([0])
            assert result == Timestamp("2011-01-01", tz=idx.tz)

            result = idx.take([0, 1, 2])
            expected = pd.date_range(
                "2011-01-01", "2011-01-03", freq="D", tz=idx.tz, name="idx"
            )
            tm.assert_index_equal(result, expected)
            assert result.freq == expected.freq

            result = idx.take([0, 2, 4])
            expected = pd.date_range(
                "2011-01-01", "2011-01-05", freq="2D", tz=idx.tz, name="idx"
            )
            tm.assert_index_equal(result, expected)
            assert result.freq == expected.freq

            result = idx.take([7, 4, 1])
            expected = pd.date_range(
                "2011-01-08", "2011-01-02", freq="-3D", tz=idx.tz, name="idx"
            )
            tm.assert_index_equal(result, expected)
            assert result.freq == expected.freq

            result = idx.take([3, 2, 5])
            expected = DatetimeIndex(
                ["2011-01-04", "2011-01-03", "2011-01-06"],
                freq=None,
                tz=idx.tz,
                name="idx",
            )
            tm.assert_index_equal(result, expected)
            assert result.freq is None

            result = idx.take([-3, 2, 5])
            expected = DatetimeIndex(
                ["2011-01-29", "2011-01-03", "2011-01-06"],
                freq=None,
                tz=idx.tz,
                name="idx",
            )
            tm.assert_index_equal(result, expected)
            assert result.freq is None

    def test_take_invalid_kwargs(self):
        idx = pd.date_range("2011-01-01", "2011-01-31", freq="D", name="idx")
        indices = [1, 6, 5, 9, 10, 13, 15, 3]

        msg = r"take\(\) got an unexpected keyword argument 'foo'"
        with pytest.raises(TypeError, match=msg):
            idx.take(indices, foo=2)

        msg = "the 'out' parameter is not supported"
        with pytest.raises(ValueError, match=msg):
            idx.take(indices, out=indices)

        msg = "the 'mode' parameter is not supported"
        with pytest.raises(ValueError, match=msg):
            idx.take(indices, mode="clip")

    # TODO: This method came from test_datetime; de-dup with version above
    @pytest.mark.parametrize("tz", [None, "US/Eastern", "Asia/Tokyo"])
    def test_take2(self, tz):
        dates = [
            datetime(2010, 1, 1, 14),
            datetime(2010, 1, 1, 15),
            datetime(2010, 1, 1, 17),
            datetime(2010, 1, 1, 21),
        ]

        idx = pd.date_range(
            start="2010-01-01 09:00",
            end="2010-02-01 09:00",
            freq="H",
            tz=tz,
            name="idx",
        )
        expected = DatetimeIndex(dates, freq=None, name="idx", tz=tz)

        taken1 = idx.take([5, 6, 8, 12])
        taken2 = idx[[5, 6, 8, 12]]

        for taken in [taken1, taken2]:
            tm.assert_index_equal(taken, expected)
            assert isinstance(taken, DatetimeIndex)
            assert taken.freq is None
            assert taken.tz == expected.tz
            assert taken.name == expected.name

    def test_take_fill_value(self):
        # GH#12631
        idx = pd.DatetimeIndex(["2011-01-01", "2011-02-01", "2011-03-01"], name="xxx")
        result = idx.take(np.array([1, 0, -1]))
        expected = pd.DatetimeIndex(
            ["2011-02-01", "2011-01-01", "2011-03-01"], name="xxx"
        )
        tm.assert_index_equal(result, expected)

        # fill_value
        result = idx.take(np.array([1, 0, -1]), fill_value=True)
        expected = pd.DatetimeIndex(["2011-02-01", "2011-01-01", "NaT"], name="xxx")
        tm.assert_index_equal(result, expected)

        # allow_fill=False
        result = idx.take(np.array([1, 0, -1]), allow_fill=False, fill_value=True)
        expected = pd.DatetimeIndex(
            ["2011-02-01", "2011-01-01", "2011-03-01"], name="xxx"
        )
        tm.assert_index_equal(result, expected)

        msg = (
            "When allow_fill=True and fill_value is not None, "
            "all indices must be >= -1"
        )
        with pytest.raises(ValueError, match=msg):
            idx.take(np.array([1, 0, -2]), fill_value=True)
        with pytest.raises(ValueError, match=msg):
            idx.take(np.array([1, 0, -5]), fill_value=True)

        msg = "out of bounds"
        with pytest.raises(IndexError, match=msg):
            idx.take(np.array([1, -5]))

    def test_take_fill_value_with_timezone(self):
        idx = pd.DatetimeIndex(
            ["2011-01-01", "2011-02-01", "2011-03-01"], name="xxx", tz="US/Eastern"
        )
        result = idx.take(np.array([1, 0, -1]))
        expected = pd.DatetimeIndex(
            ["2011-02-01", "2011-01-01", "2011-03-01"], name="xxx", tz="US/Eastern"
        )
        tm.assert_index_equal(result, expected)

        # fill_value
        result = idx.take(np.array([1, 0, -1]), fill_value=True)
        expected = pd.DatetimeIndex(
            ["2011-02-01", "2011-01-01", "NaT"], name="xxx", tz="US/Eastern"
        )
        tm.assert_index_equal(result, expected)

        # allow_fill=False
        result = idx.take(np.array([1, 0, -1]), allow_fill=False, fill_value=True)
        expected = pd.DatetimeIndex(
            ["2011-02-01", "2011-01-01", "2011-03-01"], name="xxx", tz="US/Eastern"
        )
        tm.assert_index_equal(result, expected)

        msg = (
            "When allow_fill=True and fill_value is not None, "
            "all indices must be >= -1"
        )
        with pytest.raises(ValueError, match=msg):
            idx.take(np.array([1, 0, -2]), fill_value=True)
        with pytest.raises(ValueError, match=msg):
            idx.take(np.array([1, 0, -5]), fill_value=True)

        msg = "out of bounds"
        with pytest.raises(IndexError, match=msg):
            idx.take(np.array([1, -5]))


class TestGetLoc:
    @pytest.mark.parametrize("method", [None, "pad", "backfill", "nearest"])
    def test_get_loc_method_exact_match(self, method):
        idx = pd.date_range("2000-01-01", periods=3)
        assert idx.get_loc(idx[1], method) == 1
        assert idx.get_loc(idx[1].to_pydatetime(), method) == 1
        assert idx.get_loc(str(idx[1]), method) == 1

        if method is not None:
            assert idx.get_loc(idx[1], method, tolerance=pd.Timedelta("0 days")) == 1

    def test_get_loc(self):
        idx = pd.date_range("2000-01-01", periods=3)

        assert idx.get_loc("2000-01-01", method="nearest") == 0
        assert idx.get_loc("2000-01-01T12", method="nearest") == 1

        assert idx.get_loc("2000-01-01T12", method="nearest", tolerance="1 day") == 1
        assert (
            idx.get_loc("2000-01-01T12", method="nearest", tolerance=pd.Timedelta("1D"))
            == 1
        )
        assert (
            idx.get_loc(
                "2000-01-01T12", method="nearest", tolerance=np.timedelta64(1, "D")
            )
            == 1
        )
        assert (
            idx.get_loc("2000-01-01T12", method="nearest", tolerance=timedelta(1)) == 1
        )
        with pytest.raises(ValueError, match="unit abbreviation w/o a number"):
            idx.get_loc("2000-01-01T12", method="nearest", tolerance="foo")
        with pytest.raises(KeyError, match="'2000-01-01T03'"):
            idx.get_loc("2000-01-01T03", method="nearest", tolerance="2 hours")
        with pytest.raises(
            ValueError, match="tolerance size must match target index size"
        ):
            idx.get_loc(
                "2000-01-01",
                method="nearest",
                tolerance=[
                    pd.Timedelta("1day").to_timedelta64(),
                    pd.Timedelta("1day").to_timedelta64(),
                ],
            )

        assert idx.get_loc("2000", method="nearest") == slice(0, 3)
        assert idx.get_loc("2000-01", method="nearest") == slice(0, 3)

        assert idx.get_loc("1999", method="nearest") == 0
        assert idx.get_loc("2001", method="nearest") == 2

        with pytest.raises(KeyError, match="'1999'"):
            idx.get_loc("1999", method="pad")
        with pytest.raises(KeyError, match="'2001'"):
            idx.get_loc("2001", method="backfill")

        with pytest.raises(KeyError, match="'foobar'"):
            idx.get_loc("foobar")
        with pytest.raises(InvalidIndexError, match=r"slice\(None, 2, None\)"):
            idx.get_loc(slice(2))

        idx = pd.to_datetime(["2000-01-01", "2000-01-04"])
        assert idx.get_loc("2000-01-02", method="nearest") == 0
        assert idx.get_loc("2000-01-03", method="nearest") == 1
        assert idx.get_loc("2000-01", method="nearest") == slice(0, 2)

        # time indexing
        idx = pd.date_range("2000-01-01", periods=24, freq="H")
        tm.assert_numpy_array_equal(
            idx.get_loc(time(12)), np.array([12]), check_dtype=False
        )
        tm.assert_numpy_array_equal(
            idx.get_loc(time(12, 30)), np.array([]), check_dtype=False
        )
        msg = "cannot yet lookup inexact labels when key is a time object"
        with pytest.raises(NotImplementedError, match=msg):
            idx.get_loc(time(12, 30), method="pad")

    def test_get_loc_tz_aware(self):
        # https://github.com/pandas-dev/pandas/issues/32140
        dti = pd.date_range(
            pd.Timestamp("2019-12-12 00:00:00", tz="US/Eastern"),
            pd.Timestamp("2019-12-13 00:00:00", tz="US/Eastern"),
            freq="5s",
        )
        key = pd.Timestamp("2019-12-12 10:19:25", tz="US/Eastern")
        result = dti.get_loc(key, method="nearest")
        assert result == 7433

    def test_get_loc_nat(self):
        # GH#20464
        index = DatetimeIndex(["1/3/2000", "NaT"])
        assert index.get_loc(pd.NaT) == 1

        assert index.get_loc(None) == 1

        assert index.get_loc(np.nan) == 1

        assert index.get_loc(pd.NA) == 1

        assert index.get_loc(np.datetime64("NaT")) == 1

        with pytest.raises(KeyError, match="NaT"):
            index.get_loc(np.timedelta64("NaT"))

    @pytest.mark.parametrize("key", [pd.Timedelta(0), pd.Timedelta(1), timedelta(0)])
    def test_get_loc_timedelta_invalid_key(self, key):
        # GH#20464
        dti = pd.date_range("1970-01-01", periods=10)
        msg = "Cannot index DatetimeIndex with [Tt]imedelta"
        with pytest.raises(TypeError, match=msg):
            dti.get_loc(key)

    def test_get_loc_reasonable_key_error(self):
        # GH#1062
        index = DatetimeIndex(["1/3/2000"])
        with pytest.raises(KeyError, match="2000"):
            index.get_loc("1/1/2000")


class TestContains:
    def test_dti_contains_with_duplicates(self):
        d = datetime(2011, 12, 5, 20, 30)
        ix = DatetimeIndex([d, d])
        assert d in ix

    @pytest.mark.parametrize(
        "vals",
        [
            [0, 1, 0],
            [0, 0, -1],
            [0, -1, -1],
            ["2015", "2015", "2016"],
            ["2015", "2015", "2014"],
        ],
    )
    def test_contains_nonunique(self, vals):
        # GH#9512
        idx = DatetimeIndex(vals)
        assert idx[0] in idx


class TestGetIndexer:
    def test_get_indexer(self):
        idx = pd.date_range("2000-01-01", periods=3)
        exp = np.array([0, 1, 2], dtype=np.intp)
        tm.assert_numpy_array_equal(idx.get_indexer(idx), exp)

        target = idx[0] + pd.to_timedelta(["-1 hour", "12 hours", "1 day 1 hour"])
        tm.assert_numpy_array_equal(
            idx.get_indexer(target, "pad"), np.array([-1, 0, 1], dtype=np.intp)
        )
        tm.assert_numpy_array_equal(
            idx.get_indexer(target, "backfill"), np.array([0, 1, 2], dtype=np.intp)
        )
        tm.assert_numpy_array_equal(
            idx.get_indexer(target, "nearest"), np.array([0, 1, 1], dtype=np.intp)
        )
        tm.assert_numpy_array_equal(
            idx.get_indexer(target, "nearest", tolerance=pd.Timedelta("1 hour")),
            np.array([0, -1, 1], dtype=np.intp),
        )
        tol_raw = [
            pd.Timedelta("1 hour"),
            pd.Timedelta("1 hour"),
            pd.Timedelta("1 hour").to_timedelta64(),
        ]
        tm.assert_numpy_array_equal(
            idx.get_indexer(
                target, "nearest", tolerance=[np.timedelta64(x) for x in tol_raw]
            ),
            np.array([0, -1, 1], dtype=np.intp),
        )
        tol_bad = [
            pd.Timedelta("2 hour").to_timedelta64(),
            pd.Timedelta("1 hour").to_timedelta64(),
            "foo",
        ]
        with pytest.raises(ValueError, match="abbreviation w/o a number"):
            idx.get_indexer(target, "nearest", tolerance=tol_bad)
        with pytest.raises(ValueError, match="abbreviation w/o a number"):
            idx.get_indexer(idx[[0]], method="nearest", tolerance="foo")


class TestMaybeCastSliceBound:
    def test_maybe_cast_slice_bounds_empty(self):
        # GH#14354
        empty_idx = date_range(freq="1H", periods=0, end="2015")

        right = empty_idx._maybe_cast_slice_bound("2015-01-02", "right", "loc")
        exp = Timestamp("2015-01-02 23:59:59.999999999")
        assert right == exp

        left = empty_idx._maybe_cast_slice_bound("2015-01-02", "left", "loc")
        exp = Timestamp("2015-01-02 00:00:00")
        assert left == exp

    def test_maybe_cast_slice_duplicate_monotonic(self):
        # https://github.com/pandas-dev/pandas/issues/16515
        idx = DatetimeIndex(["2017", "2017"])
        result = idx._maybe_cast_slice_bound("2017-01-01", "left", "loc")
        expected = Timestamp("2017-01-01")
        assert result == expected


class TestDatetimeIndex:
    def test_get_value(self):
        # specifically make sure we have test for np.datetime64 key
        dti = pd.date_range("2016-01-01", periods=3)

        arr = np.arange(6, 9)
        ser = pd.Series(arr, index=dti)

        key = dti[1]

        with pytest.raises(AttributeError, match="has no attribute '_values'"):
            dti.get_value(arr, key)

        result = dti.get_value(ser, key)
        assert result == 7

        result = dti.get_value(ser, key.to_pydatetime())
        assert result == 7

        result = dti.get_value(ser, key.to_datetime64())
        assert result == 7
