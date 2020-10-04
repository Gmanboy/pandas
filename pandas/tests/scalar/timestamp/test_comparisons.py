from datetime import datetime
import operator

import numpy as np
import pytest

from pandas import Timestamp
import pandas._testing as tm


class TestTimestampComparison:
    def test_comparison_dt64_ndarray(self):
        ts = Timestamp.now()
        ts2 = Timestamp("2019-04-05")
        arr = np.array([[ts.asm8, ts2.asm8]], dtype="M8[ns]")

        result = ts == arr
        expected = np.array([[True, False]], dtype=bool)
        tm.assert_numpy_array_equal(result, expected)

        result = arr == ts
        tm.assert_numpy_array_equal(result, expected)

        result = ts != arr
        tm.assert_numpy_array_equal(result, ~expected)

        result = arr != ts
        tm.assert_numpy_array_equal(result, ~expected)

        result = ts2 < arr
        tm.assert_numpy_array_equal(result, expected)

        result = arr < ts2
        tm.assert_numpy_array_equal(result, np.array([[False, False]], dtype=bool))

        result = ts2 <= arr
        tm.assert_numpy_array_equal(result, np.array([[True, True]], dtype=bool))

        result = arr <= ts2
        tm.assert_numpy_array_equal(result, ~expected)

        result = ts >= arr
        tm.assert_numpy_array_equal(result, np.array([[True, True]], dtype=bool))

        result = arr >= ts
        tm.assert_numpy_array_equal(result, np.array([[True, False]], dtype=bool))

    @pytest.mark.parametrize("reverse", [True, False])
    def test_comparison_dt64_ndarray_tzaware(self, reverse, all_compare_operators):
        op = getattr(operator, all_compare_operators.strip("__"))

        ts = Timestamp.now("UTC")
        arr = np.array([ts.asm8, ts.asm8], dtype="M8[ns]")

        left, right = ts, arr
        if reverse:
            left, right = arr, ts

        if op is operator.eq:
            expected = np.array([False, False], dtype=bool)
            result = op(left, right)
            tm.assert_numpy_array_equal(result, expected)
        elif op is operator.ne:
            expected = np.array([True, True], dtype=bool)
            result = op(left, right)
            tm.assert_numpy_array_equal(result, expected)
        else:
            msg = "Cannot compare tz-naive and tz-aware timestamps"
            with pytest.raises(TypeError, match=msg):
                op(left, right)

    def test_comparison_object_array(self):
        # GH#15183
        ts = Timestamp("2011-01-03 00:00:00-0500", tz="US/Eastern")
        other = Timestamp("2011-01-01 00:00:00-0500", tz="US/Eastern")
        naive = Timestamp("2011-01-01 00:00:00")

        arr = np.array([other, ts], dtype=object)
        res = arr == ts
        expected = np.array([False, True], dtype=bool)
        assert (res == expected).all()

        # 2D case
        arr = np.array([[other, ts], [ts, other]], dtype=object)
        res = arr != ts
        expected = np.array([[True, False], [False, True]], dtype=bool)
        assert res.shape == expected.shape
        assert (res == expected).all()

        # tzaware mismatch
        arr = np.array([naive], dtype=object)
        msg = "Cannot compare tz-naive and tz-aware timestamps"
        with pytest.raises(TypeError, match=msg):
            arr < ts

    def test_comparison(self):
        # 5-18-2012 00:00:00.000
        stamp = 1337299200000000000

        val = Timestamp(stamp)

        assert val == val
        assert not val != val
        assert not val < val
        assert val <= val
        assert not val > val
        assert val >= val

        other = datetime(2012, 5, 18)
        assert val == other
        assert not val != other
        assert not val < other
        assert val <= other
        assert not val > other
        assert val >= other

        other = Timestamp(stamp + 100)

        assert val != other
        assert val != other
        assert val < other
        assert val <= other
        assert other > val
        assert other >= val

    def test_compare_invalid(self):
        # GH#8058
        val = Timestamp("20130101 12:01:02")
        assert not val == "foo"
        assert not val == 10.0
        assert not val == 1
        assert not val == []
        assert not val == {"foo": 1}
        assert not val == np.float64(1)
        assert not val == np.int64(1)

        assert val != "foo"
        assert val != 10.0
        assert val != 1
        assert val != []
        assert val != {"foo": 1}
        assert val != np.float64(1)
        assert val != np.int64(1)

    def test_cant_compare_tz_naive_w_aware(self, utc_fixture):
        # see GH#1404
        a = Timestamp("3/12/2012")
        b = Timestamp("3/12/2012", tz=utc_fixture)

        msg = "Cannot compare tz-naive and tz-aware timestamps"
        assert not a == b
        assert a != b
        with pytest.raises(TypeError, match=msg):
            a < b
        with pytest.raises(TypeError, match=msg):
            a <= b
        with pytest.raises(TypeError, match=msg):
            a > b
        with pytest.raises(TypeError, match=msg):
            a >= b

        assert not b == a
        assert b != a
        with pytest.raises(TypeError, match=msg):
            b < a
        with pytest.raises(TypeError, match=msg):
            b <= a
        with pytest.raises(TypeError, match=msg):
            b > a
        with pytest.raises(TypeError, match=msg):
            b >= a

        assert not a == b.to_pydatetime()
        assert not a.to_pydatetime() == b

    def test_timestamp_compare_scalars(self):
        # case where ndim == 0
        lhs = np.datetime64(datetime(2013, 12, 6))
        rhs = Timestamp("now")
        nat = Timestamp("nat")

        ops = {"gt": "lt", "lt": "gt", "ge": "le", "le": "ge", "eq": "eq", "ne": "ne"}

        for left, right in ops.items():
            left_f = getattr(operator, left)
            right_f = getattr(operator, right)
            expected = left_f(lhs, rhs)

            result = right_f(rhs, lhs)
            assert result == expected

            expected = left_f(rhs, nat)
            result = right_f(nat, rhs)
            assert result == expected

    def test_timestamp_compare_with_early_datetime(self):
        # e.g. datetime.min
        stamp = Timestamp("2012-01-01")

        assert not stamp == datetime.min
        assert not stamp == datetime(1600, 1, 1)
        assert not stamp == datetime(2700, 1, 1)
        assert stamp != datetime.min
        assert stamp != datetime(1600, 1, 1)
        assert stamp != datetime(2700, 1, 1)
        assert stamp > datetime(1600, 1, 1)
        assert stamp >= datetime(1600, 1, 1)
        assert stamp < datetime(2700, 1, 1)
        assert stamp <= datetime(2700, 1, 1)

    def test_compare_zerodim_array(self):
        # GH#26916
        ts = Timestamp.now()
        dt64 = np.datetime64("2016-01-01", "ns")
        arr = np.array(dt64)
        assert arr.ndim == 0

        result = arr < ts
        assert result is np.bool_(True)
        result = arr > ts
        assert result is np.bool_(False)


def test_rich_comparison_with_unsupported_type():
    # Comparisons with unsupported objects should return NotImplemented
    # (it previously raised TypeError, see #24011)

    class Inf:
        def __lt__(self, o):
            return False

        def __le__(self, o):
            return isinstance(o, Inf)

        def __gt__(self, o):
            return not isinstance(o, Inf)

        def __ge__(self, o):
            return True

        def __eq__(self, other) -> bool:
            return isinstance(other, Inf)

    inf = Inf()
    timestamp = Timestamp("2018-11-30")

    for left, right in [(inf, timestamp), (timestamp, inf)]:
        assert left > right or left < right
        assert left >= right or left <= right
        assert not (left == right)
        assert left != right
