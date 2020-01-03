import pytest

from pandas.errors import NullFrequencyError

import pandas as pd
from pandas import TimedeltaIndex
import pandas._testing as tm


class TestTimedeltaIndexShift:

    # -------------------------------------------------------------
    # TimedeltaIndex.shift is used by __add__/__sub__

    def test_tdi_shift_empty(self):
        # GH#9903
        idx = pd.TimedeltaIndex([], name="xxx")
        tm.assert_index_equal(idx.shift(0, freq="H"), idx)
        tm.assert_index_equal(idx.shift(3, freq="H"), idx)

    def test_tdi_shift_hours(self):
        # GH#9903
        idx = pd.TimedeltaIndex(["5 hours", "6 hours", "9 hours"], name="xxx")
        tm.assert_index_equal(idx.shift(0, freq="H"), idx)
        exp = pd.TimedeltaIndex(["8 hours", "9 hours", "12 hours"], name="xxx")
        tm.assert_index_equal(idx.shift(3, freq="H"), exp)
        exp = pd.TimedeltaIndex(["2 hours", "3 hours", "6 hours"], name="xxx")
        tm.assert_index_equal(idx.shift(-3, freq="H"), exp)

    def test_tdi_shift_minutes(self):
        # GH#9903
        idx = pd.TimedeltaIndex(["5 hours", "6 hours", "9 hours"], name="xxx")
        tm.assert_index_equal(idx.shift(0, freq="T"), idx)
        exp = pd.TimedeltaIndex(["05:03:00", "06:03:00", "9:03:00"], name="xxx")
        tm.assert_index_equal(idx.shift(3, freq="T"), exp)
        exp = pd.TimedeltaIndex(["04:57:00", "05:57:00", "8:57:00"], name="xxx")
        tm.assert_index_equal(idx.shift(-3, freq="T"), exp)

    def test_tdi_shift_int(self):
        # GH#8083
        trange = pd.to_timedelta(range(5), unit="d") + pd.offsets.Hour(1)
        result = trange.shift(1)
        expected = TimedeltaIndex(
            [
                "1 days 01:00:00",
                "2 days 01:00:00",
                "3 days 01:00:00",
                "4 days 01:00:00",
                "5 days 01:00:00",
            ],
            freq="D",
        )
        tm.assert_index_equal(result, expected)

    def test_tdi_shift_nonstandard_freq(self):
        # GH#8083
        trange = pd.to_timedelta(range(5), unit="d") + pd.offsets.Hour(1)
        result = trange.shift(3, freq="2D 1s")
        expected = TimedeltaIndex(
            [
                "6 days 01:00:03",
                "7 days 01:00:03",
                "8 days 01:00:03",
                "9 days 01:00:03",
                "10 days 01:00:03",
            ],
            freq="D",
        )
        tm.assert_index_equal(result, expected)

    def test_shift_no_freq(self):
        # GH#19147
        tdi = TimedeltaIndex(["1 days 01:00:00", "2 days 01:00:00"], freq=None)
        with pytest.raises(NullFrequencyError):
            tdi.shift(2)
