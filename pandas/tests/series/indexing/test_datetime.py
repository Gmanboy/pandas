"""
Also test support for datetime64[ns] in Series / DataFrame
"""
from datetime import datetime, timedelta
import re

from dateutil.tz import gettz, tzutc
import numpy as np
import pytest
import pytz

from pandas._libs import iNaT, index as libindex

import pandas as pd
from pandas import (
    DataFrame,
    DatetimeIndex,
    NaT,
    Series,
    Timestamp,
    date_range,
    period_range,
)
import pandas._testing as tm


def test_fancy_getitem():
    dti = date_range(
        freq="WOM-1FRI", start=datetime(2005, 1, 1), end=datetime(2010, 1, 1)
    )

    s = Series(np.arange(len(dti)), index=dti)

    assert s[48] == 48
    assert s["1/2/2009"] == 48
    assert s["2009-1-2"] == 48
    assert s[datetime(2009, 1, 2)] == 48
    assert s[Timestamp(datetime(2009, 1, 2))] == 48
    with pytest.raises(KeyError, match=r"^'2009-1-3'$"):
        s["2009-1-3"]
    tm.assert_series_equal(
        s["3/6/2009":"2009-06-05"], s[datetime(2009, 3, 6) : datetime(2009, 6, 5)]
    )


def test_fancy_setitem():
    dti = date_range(
        freq="WOM-1FRI", start=datetime(2005, 1, 1), end=datetime(2010, 1, 1)
    )

    s = Series(np.arange(len(dti)), index=dti)
    s[48] = -1
    assert s[48] == -1
    s["1/2/2009"] = -2
    assert s[48] == -2
    s["1/2/2009":"2009-06-05"] = -3
    assert (s[48:54] == -3).all()


def test_slicing_datetimes():
    # GH 7523

    # unique
    df = DataFrame(
        np.arange(4.0, dtype="float64"),
        index=[datetime(2001, 1, i, 10, 00) for i in [1, 2, 3, 4]],
    )
    result = df.loc[datetime(2001, 1, 1, 10) :]
    tm.assert_frame_equal(result, df)
    result = df.loc[: datetime(2001, 1, 4, 10)]
    tm.assert_frame_equal(result, df)
    result = df.loc[datetime(2001, 1, 1, 10) : datetime(2001, 1, 4, 10)]
    tm.assert_frame_equal(result, df)

    result = df.loc[datetime(2001, 1, 1, 11) :]
    expected = df.iloc[1:]
    tm.assert_frame_equal(result, expected)
    result = df.loc["20010101 11":]
    tm.assert_frame_equal(result, expected)

    # duplicates
    df = DataFrame(
        np.arange(5.0, dtype="float64"),
        index=[datetime(2001, 1, i, 10, 00) for i in [1, 2, 2, 3, 4]],
    )

    result = df.loc[datetime(2001, 1, 1, 10) :]
    tm.assert_frame_equal(result, df)
    result = df.loc[: datetime(2001, 1, 4, 10)]
    tm.assert_frame_equal(result, df)
    result = df.loc[datetime(2001, 1, 1, 10) : datetime(2001, 1, 4, 10)]
    tm.assert_frame_equal(result, df)

    result = df.loc[datetime(2001, 1, 1, 11) :]
    expected = df.iloc[1:]
    tm.assert_frame_equal(result, expected)
    result = df.loc["20010101 11":]
    tm.assert_frame_equal(result, expected)


def test_getitem_setitem_datetime_tz_pytz():
    N = 50
    # testing with timezone, GH #2785
    rng = date_range("1/1/1990", periods=N, freq="H", tz="US/Eastern")
    ts = Series(np.random.randn(N), index=rng)

    # also test Timestamp tz handling, GH #2789
    result = ts.copy()
    result["1990-01-01 09:00:00+00:00"] = 0
    result["1990-01-01 09:00:00+00:00"] = ts[4]
    tm.assert_series_equal(result, ts)

    result = ts.copy()
    result["1990-01-01 03:00:00-06:00"] = 0
    result["1990-01-01 03:00:00-06:00"] = ts[4]
    tm.assert_series_equal(result, ts)

    # repeat with datetimes
    result = ts.copy()
    result[datetime(1990, 1, 1, 9, tzinfo=pytz.timezone("UTC"))] = 0
    result[datetime(1990, 1, 1, 9, tzinfo=pytz.timezone("UTC"))] = ts[4]
    tm.assert_series_equal(result, ts)

    result = ts.copy()

    # comparison dates with datetime MUST be localized!
    date = pytz.timezone("US/Central").localize(datetime(1990, 1, 1, 3))
    result[date] = 0
    result[date] = ts[4]
    tm.assert_series_equal(result, ts)


def test_getitem_setitem_datetime_tz_dateutil():

    tz = (
        lambda x: tzutc() if x == "UTC" else gettz(x)
    )  # handle special case for utc in dateutil

    N = 50

    # testing with timezone, GH #2785
    rng = date_range("1/1/1990", periods=N, freq="H", tz="America/New_York")
    ts = Series(np.random.randn(N), index=rng)

    # also test Timestamp tz handling, GH #2789
    result = ts.copy()
    result["1990-01-01 09:00:00+00:00"] = 0
    result["1990-01-01 09:00:00+00:00"] = ts[4]
    tm.assert_series_equal(result, ts)

    result = ts.copy()
    result["1990-01-01 03:00:00-06:00"] = 0
    result["1990-01-01 03:00:00-06:00"] = ts[4]
    tm.assert_series_equal(result, ts)

    # repeat with datetimes
    result = ts.copy()
    result[datetime(1990, 1, 1, 9, tzinfo=tz("UTC"))] = 0
    result[datetime(1990, 1, 1, 9, tzinfo=tz("UTC"))] = ts[4]
    tm.assert_series_equal(result, ts)

    result = ts.copy()
    result[datetime(1990, 1, 1, 3, tzinfo=tz("America/Chicago"))] = 0
    result[datetime(1990, 1, 1, 3, tzinfo=tz("America/Chicago"))] = ts[4]
    tm.assert_series_equal(result, ts)


def test_getitem_setitem_datetimeindex():
    N = 50
    # testing with timezone, GH #2785
    rng = date_range("1/1/1990", periods=N, freq="H", tz="US/Eastern")
    ts = Series(np.random.randn(N), index=rng)

    result = ts["1990-01-01 04:00:00"]
    expected = ts[4]
    assert result == expected

    result = ts.copy()
    result["1990-01-01 04:00:00"] = 0
    result["1990-01-01 04:00:00"] = ts[4]
    tm.assert_series_equal(result, ts)

    result = ts["1990-01-01 04:00:00":"1990-01-01 07:00:00"]
    expected = ts[4:8]
    tm.assert_series_equal(result, expected)

    result = ts.copy()
    result["1990-01-01 04:00:00":"1990-01-01 07:00:00"] = 0
    result["1990-01-01 04:00:00":"1990-01-01 07:00:00"] = ts[4:8]
    tm.assert_series_equal(result, ts)

    lb = "1990-01-01 04:00:00"
    rb = "1990-01-01 07:00:00"
    # GH#18435 strings get a pass from tzawareness compat
    result = ts[(ts.index >= lb) & (ts.index <= rb)]
    expected = ts[4:8]
    tm.assert_series_equal(result, expected)

    lb = "1990-01-01 04:00:00-0500"
    rb = "1990-01-01 07:00:00-0500"
    result = ts[(ts.index >= lb) & (ts.index <= rb)]
    expected = ts[4:8]
    tm.assert_series_equal(result, expected)

    # But we do not give datetimes a pass on tzawareness compat
    # TODO: do the same with Timestamps and dt64
    msg = "Cannot compare tz-naive and tz-aware datetime-like objects"
    naive = datetime(1990, 1, 1, 4)
    with tm.assert_produces_warning(FutureWarning):
        # GH#36148 will require tzawareness compat
        result = ts[naive]
    expected = ts[4]
    assert result == expected

    result = ts.copy()
    with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
        # GH#36148 will require tzawareness compat
        result[datetime(1990, 1, 1, 4)] = 0
    with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
        # GH#36148 will require tzawareness compat
        result[datetime(1990, 1, 1, 4)] = ts[4]
    tm.assert_series_equal(result, ts)

    with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
        # GH#36148 will require tzawareness compat
        result = ts[datetime(1990, 1, 1, 4) : datetime(1990, 1, 1, 7)]
    expected = ts[4:8]
    tm.assert_series_equal(result, expected)

    result = ts.copy()
    with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
        # GH#36148 will require tzawareness compat
        result[datetime(1990, 1, 1, 4) : datetime(1990, 1, 1, 7)] = 0
    with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
        # GH#36148 will require tzawareness compat
        result[datetime(1990, 1, 1, 4) : datetime(1990, 1, 1, 7)] = ts[4:8]
    tm.assert_series_equal(result, ts)

    lb = datetime(1990, 1, 1, 4)
    rb = datetime(1990, 1, 1, 7)
    msg = r"Invalid comparison between dtype=datetime64\[ns, US/Eastern\] and datetime"
    with pytest.raises(TypeError, match=msg):
        # tznaive vs tzaware comparison is invalid
        # see GH#18376, GH#18162
        ts[(ts.index >= lb) & (ts.index <= rb)]

    lb = Timestamp(datetime(1990, 1, 1, 4)).tz_localize(rng.tzinfo)
    rb = Timestamp(datetime(1990, 1, 1, 7)).tz_localize(rng.tzinfo)
    result = ts[(ts.index >= lb) & (ts.index <= rb)]
    expected = ts[4:8]
    tm.assert_series_equal(result, expected)

    result = ts[ts.index[4]]
    expected = ts[4]
    assert result == expected

    result = ts[ts.index[4:8]]
    expected = ts[4:8]
    tm.assert_series_equal(result, expected)

    result = ts.copy()
    result[ts.index[4:8]] = 0
    result.iloc[4:8] = ts.iloc[4:8]
    tm.assert_series_equal(result, ts)

    # also test partial date slicing
    result = ts["1990-01-02"]
    expected = ts[24:48]
    tm.assert_series_equal(result, expected)

    result = ts.copy()
    result["1990-01-02"] = 0
    result["1990-01-02"] = ts[24:48]
    tm.assert_series_equal(result, ts)


def test_getitem_setitem_periodindex():

    N = 50
    rng = period_range("1/1/1990", periods=N, freq="H")
    ts = Series(np.random.randn(N), index=rng)

    result = ts["1990-01-01 04"]
    expected = ts[4]
    assert result == expected

    result = ts.copy()
    result["1990-01-01 04"] = 0
    result["1990-01-01 04"] = ts[4]
    tm.assert_series_equal(result, ts)

    result = ts["1990-01-01 04":"1990-01-01 07"]
    expected = ts[4:8]
    tm.assert_series_equal(result, expected)

    result = ts.copy()
    result["1990-01-01 04":"1990-01-01 07"] = 0
    result["1990-01-01 04":"1990-01-01 07"] = ts[4:8]
    tm.assert_series_equal(result, ts)

    lb = "1990-01-01 04"
    rb = "1990-01-01 07"
    result = ts[(ts.index >= lb) & (ts.index <= rb)]
    expected = ts[4:8]
    tm.assert_series_equal(result, expected)

    # GH 2782
    result = ts[ts.index[4]]
    expected = ts[4]
    assert result == expected

    result = ts[ts.index[4:8]]
    expected = ts[4:8]
    tm.assert_series_equal(result, expected)

    result = ts.copy()
    result[ts.index[4:8]] = 0
    result.iloc[4:8] = ts.iloc[4:8]
    tm.assert_series_equal(result, ts)


def test_datetime_indexing():

    index = date_range("1/1/2000", "1/7/2000")
    index = index.repeat(3)

    s = Series(len(index), index=index)
    stamp = Timestamp("1/8/2000")

    with pytest.raises(KeyError, match=re.escape(repr(stamp))):
        s[stamp]
    s[stamp] = 0
    assert s[stamp] == 0

    # not monotonic
    s = Series(len(index), index=index)
    s = s[::-1]

    with pytest.raises(KeyError, match=re.escape(repr(stamp))):
        s[stamp]
    s[stamp] = 0
    assert s[stamp] == 0


"""
test duplicates in time series
"""


@pytest.fixture
def dups():
    dates = [
        datetime(2000, 1, 2),
        datetime(2000, 1, 2),
        datetime(2000, 1, 2),
        datetime(2000, 1, 3),
        datetime(2000, 1, 3),
        datetime(2000, 1, 3),
        datetime(2000, 1, 4),
        datetime(2000, 1, 4),
        datetime(2000, 1, 4),
        datetime(2000, 1, 5),
    ]

    return Series(np.random.randn(len(dates)), index=dates)


def test_constructor(dups):
    assert isinstance(dups, Series)
    assert isinstance(dups.index, DatetimeIndex)


def test_is_unique_monotonic(dups):
    assert not dups.index.is_unique


def test_index_unique(dups):
    uniques = dups.index.unique()
    expected = DatetimeIndex(
        [
            datetime(2000, 1, 2),
            datetime(2000, 1, 3),
            datetime(2000, 1, 4),
            datetime(2000, 1, 5),
        ]
    )
    assert uniques.dtype == "M8[ns]"  # sanity
    tm.assert_index_equal(uniques, expected)
    assert dups.index.nunique() == 4

    # #2563
    assert isinstance(uniques, DatetimeIndex)

    dups_local = dups.index.tz_localize("US/Eastern")
    dups_local.name = "foo"
    result = dups_local.unique()
    expected = DatetimeIndex(expected, name="foo")
    expected = expected.tz_localize("US/Eastern")
    assert result.tz is not None
    assert result.name == "foo"
    tm.assert_index_equal(result, expected)

    # NaT, note this is excluded
    arr = [1370745748 + t for t in range(20)] + [iNaT]
    idx = DatetimeIndex(arr * 3)
    tm.assert_index_equal(idx.unique(), DatetimeIndex(arr))
    assert idx.nunique() == 20
    assert idx.nunique(dropna=False) == 21

    arr = [
        Timestamp("2013-06-09 02:42:28") + timedelta(seconds=t) for t in range(20)
    ] + [NaT]
    idx = DatetimeIndex(arr * 3)
    tm.assert_index_equal(idx.unique(), DatetimeIndex(arr))
    assert idx.nunique() == 20
    assert idx.nunique(dropna=False) == 21


def test_duplicate_dates_indexing(dups):
    ts = dups

    uniques = ts.index.unique()
    for date in uniques:
        result = ts[date]

        mask = ts.index == date
        total = (ts.index == date).sum()
        expected = ts[mask]
        if total > 1:
            tm.assert_series_equal(result, expected)
        else:
            tm.assert_almost_equal(result, expected[0])

        cp = ts.copy()
        cp[date] = 0
        expected = Series(np.where(mask, 0, ts), index=ts.index)
        tm.assert_series_equal(cp, expected)

    key = datetime(2000, 1, 6)
    with pytest.raises(KeyError, match=re.escape(repr(key))):
        ts[key]

    # new index
    ts[datetime(2000, 1, 6)] = 0
    assert ts[datetime(2000, 1, 6)] == 0


def test_groupby_average_dup_values(dups):
    result = dups.groupby(level=0).mean()
    expected = dups.groupby(dups.index).mean()
    tm.assert_series_equal(result, expected)


def test_indexing_over_size_cutoff(monkeypatch):
    # #1821

    monkeypatch.setattr(libindex, "_SIZE_CUTOFF", 1000)

    # create large list of non periodic datetime
    dates = []
    sec = timedelta(seconds=1)
    half_sec = timedelta(microseconds=500000)
    d = datetime(2011, 12, 5, 20, 30)
    n = 1100
    for i in range(n):
        dates.append(d)
        dates.append(d + sec)
        dates.append(d + sec + half_sec)
        dates.append(d + sec + sec + half_sec)
        d += 3 * sec

    # duplicate some values in the list
    duplicate_positions = np.random.randint(0, len(dates) - 1, 20)
    for p in duplicate_positions:
        dates[p + 1] = dates[p]

    df = DataFrame(np.random.randn(len(dates), 4), index=dates, columns=list("ABCD"))

    pos = n * 3
    timestamp = df.index[pos]
    assert timestamp in df.index

    # it works!
    df.loc[timestamp]
    assert len(df.loc[[timestamp]]) > 0


def test_indexing_over_size_cutoff_period_index(monkeypatch):
    # GH 27136

    monkeypatch.setattr(libindex, "_SIZE_CUTOFF", 1000)

    n = 1100
    idx = pd.period_range("1/1/2000", freq="T", periods=n)
    assert idx._engine.over_size_threshold

    s = Series(np.random.randn(len(idx)), index=idx)

    pos = n - 1
    timestamp = idx[pos]
    assert timestamp in s.index

    # it works!
    s[timestamp]
    assert len(s.loc[[timestamp]]) > 0


def test_indexing_unordered():
    # GH 2437
    rng = date_range(start="2011-01-01", end="2011-01-15")
    ts = Series(np.random.rand(len(rng)), index=rng)
    ts2 = pd.concat([ts[0:4], ts[-4:], ts[4:-4]])

    for t in ts.index:

        expected = ts[t]
        result = ts2[t]
        assert expected == result

    # GH 3448 (ranges)
    def compare(slobj):
        result = ts2[slobj].copy()
        result = result.sort_index()
        expected = ts[slobj]
        expected.index = expected.index._with_freq(None)
        tm.assert_series_equal(result, expected)

    compare(slice("2011-01-01", "2011-01-15"))
    with tm.assert_produces_warning(FutureWarning):
        compare(slice("2010-12-30", "2011-01-15"))
    compare(slice("2011-01-01", "2011-01-16"))

    # partial ranges
    compare(slice("2011-01-01", "2011-01-6"))
    compare(slice("2011-01-06", "2011-01-8"))
    compare(slice("2011-01-06", "2011-01-12"))

    # single values
    result = ts2["2011"].sort_index()
    expected = ts["2011"]
    expected.index = expected.index._with_freq(None)
    tm.assert_series_equal(result, expected)

    # diff freq
    rng = date_range(datetime(2005, 1, 1), periods=20, freq="M")
    ts = Series(np.arange(len(rng)), index=rng)
    ts = ts.take(np.random.permutation(20))

    result = ts["2005"]
    for t in result.index:
        assert t.year == 2005


def test_indexing():
    idx = date_range("2001-1-1", periods=20, freq="M")
    ts = Series(np.random.rand(len(idx)), index=idx)

    # getting

    # GH 3070, make sure semantics work on Series/Frame
    expected = ts["2001"]
    expected.name = "A"

    df = DataFrame(dict(A=ts))
    with tm.assert_produces_warning(FutureWarning):
        # GH#36179 string indexing on rows for DataFrame deprecated
        result = df["2001"]["A"]
    tm.assert_series_equal(expected, result)

    # setting
    ts["2001"] = 1
    expected = ts["2001"]
    expected.name = "A"

    df.loc["2001", "A"] = 1

    with tm.assert_produces_warning(FutureWarning):
        # GH#36179 string indexing on rows for DataFrame deprecated
        result = df["2001"]["A"]
    tm.assert_series_equal(expected, result)

    # GH3546 (not including times on the last day)
    idx = date_range(start="2013-05-31 00:00", end="2013-05-31 23:00", freq="H")
    ts = Series(range(len(idx)), index=idx)
    expected = ts["2013-05"]
    tm.assert_series_equal(expected, ts)

    idx = date_range(start="2013-05-31 00:00", end="2013-05-31 23:59", freq="S")
    ts = Series(range(len(idx)), index=idx)
    expected = ts["2013-05"]
    tm.assert_series_equal(expected, ts)

    idx = [
        Timestamp("2013-05-31 00:00"),
        Timestamp(datetime(2013, 5, 31, 23, 59, 59, 999999)),
    ]
    ts = Series(range(len(idx)), index=idx)
    expected = ts["2013"]
    tm.assert_series_equal(expected, ts)

    # GH14826, indexing with a seconds resolution string / datetime object
    df = DataFrame(
        np.random.rand(5, 5),
        columns=["open", "high", "low", "close", "volume"],
        index=date_range("2012-01-02 18:01:00", periods=5, tz="US/Central", freq="s"),
    )
    expected = df.loc[[df.index[2]]]

    # this is a single date, so will raise
    with pytest.raises(KeyError, match=r"^'2012-01-02 18:01:02'$"):
        df["2012-01-02 18:01:02"]
    msg = r"Timestamp\('2012-01-02 18:01:02-0600', tz='US/Central', freq='S'\)"
    with pytest.raises(KeyError, match=msg):
        df[df.index[2]]
