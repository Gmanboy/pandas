import operator
import re

import numpy as np
import pytest

from pandas import DataFrame, Series
import pandas._testing as tm


class TestDataFrameLogicalOperators:
    # &, |, ^

    def test_logical_ops_empty_frame(self):
        # GH#5808
        # empty frames, non-mixed dtype
        df = DataFrame(index=[1])

        result = df & df
        tm.assert_frame_equal(result, df)

        result = df | df
        tm.assert_frame_equal(result, df)

        df2 = DataFrame(index=[1, 2])
        result = df & df2
        tm.assert_frame_equal(result, df2)

        dfa = DataFrame(index=[1], columns=["A"])

        result = dfa & dfa
        expected = DataFrame(False, index=[1], columns=["A"])
        tm.assert_frame_equal(result, expected)

    def test_logical_ops_bool_frame(self):
        # GH#5808
        df1a_bool = DataFrame(True, index=[1], columns=["A"])

        result = df1a_bool & df1a_bool
        tm.assert_frame_equal(result, df1a_bool)

        result = df1a_bool | df1a_bool
        tm.assert_frame_equal(result, df1a_bool)

    def test_logical_ops_int_frame(self):
        # GH#5808
        df1a_int = DataFrame(1, index=[1], columns=["A"])
        df1a_bool = DataFrame(True, index=[1], columns=["A"])

        result = df1a_int | df1a_bool
        tm.assert_frame_equal(result, df1a_bool)

        # Check that this matches Series behavior
        res_ser = df1a_int["A"] | df1a_bool["A"]
        tm.assert_series_equal(res_ser, df1a_bool["A"])

    def test_logical_ops_invalid(self):
        # GH#5808

        df1 = DataFrame(1.0, index=[1], columns=["A"])
        df2 = DataFrame(True, index=[1], columns=["A"])
        msg = re.escape("unsupported operand type(s) for |: 'float' and 'bool'")
        with pytest.raises(TypeError, match=msg):
            df1 | df2

        df1 = DataFrame("foo", index=[1], columns=["A"])
        df2 = DataFrame(True, index=[1], columns=["A"])
        msg = re.escape("unsupported operand type(s) for |: 'str' and 'bool'")
        with pytest.raises(TypeError, match=msg):
            df1 | df2

    def test_logical_operators(self):
        def _check_bin_op(op):
            result = op(df1, df2)
            expected = DataFrame(
                op(df1.values, df2.values), index=df1.index, columns=df1.columns
            )
            assert result.values.dtype == np.bool_
            tm.assert_frame_equal(result, expected)

        def _check_unary_op(op):
            result = op(df1)
            expected = DataFrame(op(df1.values), index=df1.index, columns=df1.columns)
            assert result.values.dtype == np.bool_
            tm.assert_frame_equal(result, expected)

        df1 = {
            "a": {"a": True, "b": False, "c": False, "d": True, "e": True},
            "b": {"a": False, "b": True, "c": False, "d": False, "e": False},
            "c": {"a": False, "b": False, "c": True, "d": False, "e": False},
            "d": {"a": True, "b": False, "c": False, "d": True, "e": True},
            "e": {"a": True, "b": False, "c": False, "d": True, "e": True},
        }

        df2 = {
            "a": {"a": True, "b": False, "c": True, "d": False, "e": False},
            "b": {"a": False, "b": True, "c": False, "d": False, "e": False},
            "c": {"a": True, "b": False, "c": True, "d": False, "e": False},
            "d": {"a": False, "b": False, "c": False, "d": True, "e": False},
            "e": {"a": False, "b": False, "c": False, "d": False, "e": True},
        }

        df1 = DataFrame(df1)
        df2 = DataFrame(df2)

        _check_bin_op(operator.and_)
        _check_bin_op(operator.or_)
        _check_bin_op(operator.xor)

        _check_unary_op(operator.inv)  # TODO: belongs elsewhere

    def test_logical_with_nas(self):
        d = DataFrame({"a": [np.nan, False], "b": [True, True]})

        # GH4947
        # bool comparisons should return bool
        result = d["a"] | d["b"]
        expected = Series([False, True])
        tm.assert_series_equal(result, expected)

        # GH4604, automatic casting here
        result = d["a"].fillna(False) | d["b"]
        expected = Series([True, True])
        tm.assert_series_equal(result, expected)

        result = d["a"].fillna(False, downcast=False) | d["b"]
        expected = Series([True, True])
        tm.assert_series_equal(result, expected)
