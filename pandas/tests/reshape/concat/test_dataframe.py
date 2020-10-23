import numpy as np
import pytest

import pandas as pd
from pandas import DataFrame, Index, Series
import pandas._testing as tm


class TestDataFrameConcat:
    def test_concat_multiple_frames_dtypes(self):

        # GH#2759
        A = DataFrame(data=np.ones((10, 2)), columns=["foo", "bar"], dtype=np.float64)
        B = DataFrame(data=np.ones((10, 2)), dtype=np.float32)
        results = pd.concat((A, B), axis=1).dtypes
        expected = Series(
            [np.dtype("float64")] * 2 + [np.dtype("float32")] * 2,
            index=["foo", "bar", 0, 1],
        )
        tm.assert_series_equal(results, expected)

    def test_concat_tuple_keys(self):
        # GH#14438
        df1 = DataFrame(np.ones((2, 2)), columns=list("AB"))
        df2 = DataFrame(np.ones((3, 2)) * 2, columns=list("AB"))
        results = pd.concat((df1, df2), keys=[("bee", "bah"), ("bee", "boo")])
        expected = DataFrame(
            {
                "A": {
                    ("bee", "bah", 0): 1.0,
                    ("bee", "bah", 1): 1.0,
                    ("bee", "boo", 0): 2.0,
                    ("bee", "boo", 1): 2.0,
                    ("bee", "boo", 2): 2.0,
                },
                "B": {
                    ("bee", "bah", 0): 1.0,
                    ("bee", "bah", 1): 1.0,
                    ("bee", "boo", 0): 2.0,
                    ("bee", "boo", 1): 2.0,
                    ("bee", "boo", 2): 2.0,
                },
            }
        )
        tm.assert_frame_equal(results, expected)

    def test_concat_named_keys(self):
        # GH#14252
        df = DataFrame({"foo": [1, 2], "bar": [0.1, 0.2]})
        index = Index(["a", "b"], name="baz")
        concatted_named_from_keys = pd.concat([df, df], keys=index)
        expected_named = DataFrame(
            {"foo": [1, 2, 1, 2], "bar": [0.1, 0.2, 0.1, 0.2]},
            index=pd.MultiIndex.from_product((["a", "b"], [0, 1]), names=["baz", None]),
        )
        tm.assert_frame_equal(concatted_named_from_keys, expected_named)

        index_no_name = Index(["a", "b"], name=None)
        concatted_named_from_names = pd.concat(
            [df, df], keys=index_no_name, names=["baz"]
        )
        tm.assert_frame_equal(concatted_named_from_names, expected_named)

        concatted_unnamed = pd.concat([df, df], keys=index_no_name)
        expected_unnamed = DataFrame(
            {"foo": [1, 2, 1, 2], "bar": [0.1, 0.2, 0.1, 0.2]},
            index=pd.MultiIndex.from_product((["a", "b"], [0, 1]), names=[None, None]),
        )
        tm.assert_frame_equal(concatted_unnamed, expected_unnamed)

    def test_concat_axis_parameter(self):
        # GH#14369
        df1 = DataFrame({"A": [0.1, 0.2]}, index=range(2))
        df2 = DataFrame({"A": [0.3, 0.4]}, index=range(2))

        # Index/row/0 DataFrame
        expected_index = DataFrame({"A": [0.1, 0.2, 0.3, 0.4]}, index=[0, 1, 0, 1])

        concatted_index = pd.concat([df1, df2], axis="index")
        tm.assert_frame_equal(concatted_index, expected_index)

        concatted_row = pd.concat([df1, df2], axis="rows")
        tm.assert_frame_equal(concatted_row, expected_index)

        concatted_0 = pd.concat([df1, df2], axis=0)
        tm.assert_frame_equal(concatted_0, expected_index)

        # Columns/1 DataFrame
        expected_columns = DataFrame(
            [[0.1, 0.3], [0.2, 0.4]], index=[0, 1], columns=["A", "A"]
        )

        concatted_columns = pd.concat([df1, df2], axis="columns")
        tm.assert_frame_equal(concatted_columns, expected_columns)

        concatted_1 = pd.concat([df1, df2], axis=1)
        tm.assert_frame_equal(concatted_1, expected_columns)

        series1 = Series([0.1, 0.2])
        series2 = Series([0.3, 0.4])

        # Index/row/0 Series
        expected_index_series = Series([0.1, 0.2, 0.3, 0.4], index=[0, 1, 0, 1])

        concatted_index_series = pd.concat([series1, series2], axis="index")
        tm.assert_series_equal(concatted_index_series, expected_index_series)

        concatted_row_series = pd.concat([series1, series2], axis="rows")
        tm.assert_series_equal(concatted_row_series, expected_index_series)

        concatted_0_series = pd.concat([series1, series2], axis=0)
        tm.assert_series_equal(concatted_0_series, expected_index_series)

        # Columns/1 Series
        expected_columns_series = DataFrame(
            [[0.1, 0.3], [0.2, 0.4]], index=[0, 1], columns=[0, 1]
        )

        concatted_columns_series = pd.concat([series1, series2], axis="columns")
        tm.assert_frame_equal(concatted_columns_series, expected_columns_series)

        concatted_1_series = pd.concat([series1, series2], axis=1)
        tm.assert_frame_equal(concatted_1_series, expected_columns_series)

        # Testing ValueError
        with pytest.raises(ValueError, match="No axis named"):
            pd.concat([series1, series2], axis="something")

    def test_concat_numerical_names(self):
        # GH#15262, GH#12223
        df = DataFrame(
            {"col": range(9)},
            dtype="int32",
            index=(
                pd.MultiIndex.from_product(
                    [["A0", "A1", "A2"], ["B0", "B1", "B2"]], names=[1, 2]
                )
            ),
        )
        result = pd.concat((df.iloc[:2, :], df.iloc[-2:, :]))
        expected = DataFrame(
            {"col": [0, 1, 7, 8]},
            dtype="int32",
            index=pd.MultiIndex.from_tuples(
                [("A0", "B0"), ("A0", "B1"), ("A2", "B1"), ("A2", "B2")], names=[1, 2]
            ),
        )
        tm.assert_frame_equal(result, expected)

    def test_concat_astype_dup_col(self):
        # GH#23049
        df = DataFrame([{"a": "b"}])
        df = pd.concat([df, df], axis=1)

        result = df.astype("category")
        expected = DataFrame(
            np.array(["b", "b"]).reshape(1, 2), columns=["a", "a"]
        ).astype("category")
        tm.assert_frame_equal(result, expected)
