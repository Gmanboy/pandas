from datetime import datetime

import pytest
import pytz

from pandas.errors import NullFrequencyError

import pandas as pd
from pandas import DatetimeIndex, Series, date_range
import pandas.util.testing as tm


class TestDatetimeIndexArithmetic:

    # -------------------------------------------------------------
    # DatetimeIndex.shift is used in integer addition

    def test_dti_shift_tzaware(self, tz_naive_fixture):
        # GH#9903
        tz = tz_naive_fixture
        idx = pd.DatetimeIndex([], name="xxx", tz=tz)
        tm.assert_index_equal(idx.shift(0, freq="H"), idx)
        tm.assert_index_equal(idx.shift(3, freq="H"), idx)

        idx = pd.DatetimeIndex(
            ["2011-01-01 10:00", "2011-01-01 11:00", "2011-01-01 12:00"],
            name="xxx",
            tz=tz,
        )
        tm.assert_index_equal(idx.shift(0, freq="H"), idx)
        exp = pd.DatetimeIndex(
            ["2011-01-01 13:00", "2011-01-01 14:00", "2011-01-01 15:00"],
            name="xxx",
            tz=tz,
        )
        tm.assert_index_equal(idx.shift(3, freq="H"), exp)
        exp = pd.DatetimeIndex(
            ["2011-01-01 07:00", "2011-01-01 08:00", "2011-01-01 09:00"],
            name="xxx",
            tz=tz,
        )
        tm.assert_index_equal(idx.shift(-3, freq="H"), exp)

    def test_dti_shift_freqs(self):
        # test shift for DatetimeIndex and non DatetimeIndex
        # GH#8083
        drange = pd.date_range("20130101", periods=5)
        result = drange.shift(1)
        expected = pd.DatetimeIndex(
            ["2013-01-02", "2013-01-03", "2013-01-04", "2013-01-05", "2013-01-06"],
            freq="D",
        )
        tm.assert_index_equal(result, expected)

        result = drange.shift(-1)
        expected = pd.DatetimeIndex(
            ["2012-12-31", "2013-01-01", "2013-01-02", "2013-01-03", "2013-01-04"],
            freq="D",
        )
        tm.assert_index_equal(result, expected)

        result = drange.shift(3, freq="2D")
        expected = pd.DatetimeIndex(
            ["2013-01-07", "2013-01-08", "2013-01-09", "2013-01-10", "2013-01-11"],
            freq="D",
        )
        tm.assert_index_equal(result, expected)

    def test_dti_shift_int(self):
        rng = date_range("1/1/2000", periods=20)

        result = rng + 5 * rng.freq
        expected = rng.shift(5)
        tm.assert_index_equal(result, expected)

        result = rng - 5 * rng.freq
        expected = rng.shift(-5)
        tm.assert_index_equal(result, expected)

    def test_dti_shift_no_freq(self):
        # GH#19147
        dti = pd.DatetimeIndex(["2011-01-01 10:00", "2011-01-01"], freq=None)
        with pytest.raises(NullFrequencyError):
            dti.shift(2)

    @pytest.mark.parametrize("tzstr", ["US/Eastern", "dateutil/US/Eastern"])
    def test_dti_shift_localized(self, tzstr):
        dr = date_range("2011/1/1", "2012/1/1", freq="W-FRI")
        dr_tz = dr.tz_localize(tzstr)

        result = dr_tz.shift(1, "10T")
        assert result.tz == dr_tz.tz

    def test_dti_shift_across_dst(self):
        # GH 8616
        idx = date_range("2013-11-03", tz="America/Chicago", periods=7, freq="H")
        s = Series(index=idx[:-1], dtype=object)
        result = s.shift(freq="H")
        expected = Series(index=idx[1:], dtype=object)
        tm.assert_series_equal(result, expected)

    @pytest.mark.parametrize(
        "shift, result_time",
        [
            [0, "2014-11-14 00:00:00"],
            [-1, "2014-11-13 23:00:00"],
            [1, "2014-11-14 01:00:00"],
        ],
    )
    def test_dti_shift_near_midnight(self, shift, result_time):
        # GH 8616
        dt = datetime(2014, 11, 14, 0)
        dt_est = pytz.timezone("EST").localize(dt)
        s = Series(data=[1], index=[dt_est])
        result = s.shift(shift, freq="H")
        expected = Series(1, index=DatetimeIndex([result_time], tz="EST"))
        tm.assert_series_equal(result, expected)
