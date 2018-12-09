import itertools

import numpy as np
import pytest

import pandas as pd
from pandas.core.internals import ExtensionBlock

from .base import BaseExtensionTests


class BaseReshapingTests(BaseExtensionTests):
    """Tests for reshaping and concatenation."""
    @pytest.mark.parametrize('in_frame', [True, False])
    def test_concat(self, data, in_frame):
        wrapped = pd.Series(data)
        if in_frame:
            wrapped = pd.DataFrame(wrapped)
        result = pd.concat([wrapped, wrapped], ignore_index=True)

        assert len(result) == len(data) * 2

        if in_frame:
            dtype = result.dtypes[0]
        else:
            dtype = result.dtype

        assert dtype == data.dtype
        assert isinstance(result._data.blocks[0], ExtensionBlock)

    @pytest.mark.parametrize('in_frame', [True, False])
    def test_concat_all_na_block(self, data_missing, in_frame):
        valid_block = pd.Series(data_missing.take([1, 1]), index=[0, 1])
        na_block = pd.Series(data_missing.take([0, 0]), index=[2, 3])
        if in_frame:
            valid_block = pd.DataFrame({"a": valid_block})
            na_block = pd.DataFrame({"a": na_block})
        result = pd.concat([valid_block, na_block])
        if in_frame:
            expected = pd.DataFrame({"a": data_missing.take([1, 1, 0, 0])})
            self.assert_frame_equal(result, expected)
        else:
            expected = pd.Series(data_missing.take([1, 1, 0, 0]))
            self.assert_series_equal(result, expected)

    def test_concat_mixed_dtypes(self, data):
        # https://github.com/pandas-dev/pandas/issues/20762
        df1 = pd.DataFrame({'A': data[:3]})
        df2 = pd.DataFrame({"A": [1, 2, 3]})
        df3 = pd.DataFrame({"A": ['a', 'b', 'c']}).astype('category')
        dfs = [df1, df2, df3]

        # dataframes
        result = pd.concat(dfs)
        expected = pd.concat([x.astype(object) for x in dfs])
        self.assert_frame_equal(result, expected)

        # series
        result = pd.concat([x['A'] for x in dfs])
        expected = pd.concat([x['A'].astype(object) for x in dfs])
        self.assert_series_equal(result, expected)

        # simple test for just EA and one other
        result = pd.concat([df1, df2])
        expected = pd.concat([df1.astype('object'), df2.astype('object')])
        self.assert_frame_equal(result, expected)

        result = pd.concat([df1['A'], df2['A']])
        expected = pd.concat([df1['A'].astype('object'),
                              df2['A'].astype('object')])
        self.assert_series_equal(result, expected)

    def test_concat_columns(self, data, na_value):
        df1 = pd.DataFrame({'A': data[:3]})
        df2 = pd.DataFrame({'B': [1, 2, 3]})

        expected = pd.DataFrame({'A': data[:3], 'B': [1, 2, 3]})
        result = pd.concat([df1, df2], axis=1)
        self.assert_frame_equal(result, expected)
        result = pd.concat([df1['A'], df2['B']], axis=1)
        self.assert_frame_equal(result, expected)

        # non-aligned
        df2 = pd.DataFrame({'B': [1, 2, 3]}, index=[1, 2, 3])
        expected = pd.DataFrame({
            'A': data._from_sequence(list(data[:3]) + [na_value],
                                     dtype=data.dtype),
            'B': [np.nan, 1, 2, 3]})

        result = pd.concat([df1, df2], axis=1)
        self.assert_frame_equal(result, expected)
        result = pd.concat([df1['A'], df2['B']], axis=1)
        self.assert_frame_equal(result, expected)

    def test_align(self, data, na_value):
        a = data[:3]
        b = data[2:5]
        r1, r2 = pd.Series(a).align(pd.Series(b, index=[1, 2, 3]))

        # Assumes that the ctor can take a list of scalars of the type
        e1 = pd.Series(data._from_sequence(list(a) + [na_value],
                                           dtype=data.dtype))
        e2 = pd.Series(data._from_sequence([na_value] + list(b),
                                           dtype=data.dtype))
        self.assert_series_equal(r1, e1)
        self.assert_series_equal(r2, e2)

    def test_align_frame(self, data, na_value):
        a = data[:3]
        b = data[2:5]
        r1, r2 = pd.DataFrame({'A': a}).align(
            pd.DataFrame({'A': b}, index=[1, 2, 3])
        )

        # Assumes that the ctor can take a list of scalars of the type
        e1 = pd.DataFrame({'A': data._from_sequence(list(a) + [na_value],
                                                    dtype=data.dtype)})
        e2 = pd.DataFrame({'A': data._from_sequence([na_value] + list(b),
                                                    dtype=data.dtype)})
        self.assert_frame_equal(r1, e1)
        self.assert_frame_equal(r2, e2)

    def test_align_series_frame(self, data, na_value):
        # https://github.com/pandas-dev/pandas/issues/20576
        ser = pd.Series(data, name='a')
        df = pd.DataFrame({"col": np.arange(len(ser) + 1)})
        r1, r2 = ser.align(df)

        e1 = pd.Series(data._from_sequence(list(data) + [na_value],
                                           dtype=data.dtype),
                       name=ser.name)

        self.assert_series_equal(r1, e1)
        self.assert_frame_equal(r2, df)

    def test_set_frame_expand_regular_with_extension(self, data):
        df = pd.DataFrame({"A": [1] * len(data)})
        df['B'] = data
        expected = pd.DataFrame({"A": [1] * len(data), "B": data})
        self.assert_frame_equal(df, expected)

    def test_set_frame_expand_extension_with_regular(self, data):
        df = pd.DataFrame({'A': data})
        df['B'] = [1] * len(data)
        expected = pd.DataFrame({"A": data, "B": [1] * len(data)})
        self.assert_frame_equal(df, expected)

    def test_set_frame_overwrite_object(self, data):
        # https://github.com/pandas-dev/pandas/issues/20555
        df = pd.DataFrame({"A": [1] * len(data)}, dtype=object)
        df['A'] = data
        assert df.dtypes['A'] == data.dtype

    def test_merge(self, data, na_value):
        # GH-20743
        df1 = pd.DataFrame({'ext': data[:3], 'int1': [1, 2, 3],
                            'key': [0, 1, 2]})
        df2 = pd.DataFrame({'int2': [1, 2, 3, 4], 'key': [0, 0, 1, 3]})

        res = pd.merge(df1, df2)
        exp = pd.DataFrame(
            {'int1': [1, 1, 2], 'int2': [1, 2, 3], 'key': [0, 0, 1],
             'ext': data._from_sequence([data[0], data[0], data[1]],
                                        dtype=data.dtype)})
        self.assert_frame_equal(res, exp[['ext', 'int1', 'key', 'int2']])

        res = pd.merge(df1, df2, how='outer')
        exp = pd.DataFrame(
            {'int1': [1, 1, 2, 3, np.nan], 'int2': [1, 2, 3, np.nan, 4],
             'key': [0, 0, 1, 2, 3],
             'ext': data._from_sequence(
                 [data[0], data[0], data[1], data[2], na_value],
                 dtype=data.dtype)})
        self.assert_frame_equal(res, exp[['ext', 'int1', 'key', 'int2']])

    @pytest.mark.parametrize("columns", [
        ["A", "B"],
        pd.MultiIndex.from_tuples([('A', 'a'), ('A', 'b')],
                                  names=['outer', 'inner']),
    ])
    def test_stack(self, data, columns):
        df = pd.DataFrame({"A": data[:5], "B": data[:5]})
        df.columns = columns
        result = df.stack()
        expected = df.astype(object).stack()
        # we need a second astype(object), in case the constructor inferred
        # object -> specialized, as is done for period.
        expected = expected.astype(object)

        if isinstance(expected, pd.Series):
            assert result.dtype == df.iloc[:, 0].dtype
        else:
            assert all(result.dtypes == df.iloc[:, 0].dtype)

        result = result.astype(object)
        self.assert_equal(result, expected)

    @pytest.mark.parametrize("index", [
        # Two levels, uniform.
        pd.MultiIndex.from_product(([['A', 'B'], ['a', 'b']]),
                                   names=['a', 'b']),

        # non-uniform
        pd.MultiIndex.from_tuples([('A', 'a'), ('A', 'b'), ('B', 'b')]),

        # three levels, non-uniform
        pd.MultiIndex.from_product([('A', 'B'), ('a', 'b', 'c'), (0, 1, 2)]),
        pd.MultiIndex.from_tuples([
            ('A', 'a', 1),
            ('A', 'b', 0),
            ('A', 'a', 0),
            ('B', 'a', 0),
            ('B', 'c', 1),
        ]),
    ])
    @pytest.mark.parametrize("obj", ["series", "frame"])
    def test_unstack(self, data, index, obj):
        data = data[:len(index)]
        if obj == "series":
            ser = pd.Series(data, index=index)
        else:
            ser = pd.DataFrame({"A": data, "B": data}, index=index)

        n = index.nlevels
        levels = list(range(n))
        # [0, 1, 2]
        # [(0,), (1,), (2,), (0, 1), (0, 2), (1, 0), (1, 2), (2, 0), (2, 1)]
        combinations = itertools.chain.from_iterable(
            itertools.permutations(levels, i) for i in range(1, n)
        )

        for level in combinations:
            result = ser.unstack(level=level)
            assert all(isinstance(result[col].array, type(data))
                       for col in result.columns)
            expected = ser.astype(object).unstack(level=level)
            result = result.astype(object)

            self.assert_frame_equal(result, expected)
