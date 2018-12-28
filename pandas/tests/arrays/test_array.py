import decimal

import numpy as np
import pytest

from pandas.core.dtypes.dtypes import registry

import pandas as pd
from pandas.api.extensions import register_extension_dtype
from pandas.core.arrays import PandasArray, integer_array, period_array
from pandas.tests.extension.decimal import (
    DecimalArray, DecimalDtype, to_decimal)
import pandas.util.testing as tm


@pytest.mark.parametrize("data, dtype, expected", [
    # Basic NumPy defaults.
    ([1, 2], None, PandasArray(np.array([1, 2]))),
    ([1, 2], object, PandasArray(np.array([1, 2], dtype=object))),
    ([1, 2], np.dtype('float32'),
     PandasArray(np.array([1., 2.0], dtype=np.dtype('float32')))),
    (np.array([1, 2]), None, PandasArray(np.array([1, 2]))),

    # String alias passes through to NumPy
    ([1, 2], 'float32', PandasArray(np.array([1, 2], dtype='float32'))),

    # Period alias
    ([pd.Period('2000', 'D'), pd.Period('2001', 'D')], 'Period[D]',
     period_array(['2000', '2001'], freq='D')),

    # Period dtype
    ([pd.Period('2000', 'D')], pd.PeriodDtype('D'),
     period_array(['2000'], freq='D')),

    # Datetime (naive)
    ([1, 2], np.dtype('datetime64[ns]'),
     PandasArray(np.array([1, 2], dtype='datetime64[ns]'))),
    # TODO(DatetimeArray): add here

    # Category
    (['a', 'b'], 'category', pd.Categorical(['a', 'b'])),
    (['a', 'b'], pd.CategoricalDtype(None, ordered=True),
     pd.Categorical(['a', 'b'], ordered=True)),

    # Interval
    ([pd.Interval(1, 2), pd.Interval(3, 4)], 'interval',
     pd.IntervalArray.from_tuples([(1, 2), (3, 4)])),

    # Sparse
    ([0, 1], 'Sparse[int64]', pd.SparseArray([0, 1], dtype='int64')),

    # IntegerNA
    ([1, None], 'Int16', integer_array([1, None], dtype='Int16')),
    (pd.Series([1, 2]), None, PandasArray(np.array([1, 2], dtype=np.int64))),

    # Index
    (pd.Index([1, 2]), None, PandasArray(np.array([1, 2], dtype=np.int64))),

    # Series[EA] returns the EA
    (pd.Series(pd.Categorical(['a', 'b'], categories=['a', 'b', 'c'])),
     None,
     pd.Categorical(['a', 'b'], categories=['a', 'b', 'c'])),

    # "3rd party" EAs work
    ([decimal.Decimal(0), decimal.Decimal(1)], 'decimal', to_decimal([0, 1])),

    # pass an ExtensionArray, but a different dtype
    (period_array(['2000', '2001'], freq='D'),
     'category',
     pd.Categorical([pd.Period('2000', 'D'), pd.Period('2001', 'D')])),
])
def test_array(data, dtype, expected):
    result = pd.array(data, dtype=dtype)
    tm.assert_equal(result, expected)


def test_array_copy():
    a = np.array([1, 2])
    # default is to copy
    b = pd.array(a)
    assert np.shares_memory(a, b._ndarray) is False

    # copy=True
    b = pd.array(a, copy=True)
    assert np.shares_memory(a, b._ndarray) is False

    # copy=False
    b = pd.array(a, copy=False)
    assert np.shares_memory(a, b._ndarray) is True


@pytest.mark.parametrize('data, expected', [
    ([pd.Period("2000", "D"), pd.Period("2001", "D")],
     period_array(["2000", "2001"], freq="D")),
    ([pd.Interval(0, 1), pd.Interval(1, 2)],
     pd.IntervalArray.from_breaks([0, 1, 2])),
])
def test_array_inference(data, expected):
    result = pd.array(data)
    tm.assert_equal(result, expected)


@pytest.mark.parametrize('data', [
    # mix of frequencies
    [pd.Period("2000", "D"), pd.Period("2001", "A")],
    # mix of closed
    [pd.Interval(0, 1, closed='left'), pd.Interval(1, 2, closed='right')],
])
def test_array_inference_fails(data):
    result = pd.array(data)
    expected = PandasArray(np.array(data, dtype=object))
    tm.assert_extension_array_equal(result, expected)


@pytest.mark.parametrize("data", [
    np.array([[1, 2], [3, 4]]),
    [[1, 2], [3, 4]],
])
def test_nd_raises(data):
    with pytest.raises(ValueError, match='PandasArray must be 1-dimensional'):
        pd.array(data)


def test_scalar_raises():
    with pytest.raises(ValueError,
                       match="Cannot pass scalar '1'"):
        pd.array(1)

# ---------------------------------------------------------------------------
# A couple dummy classes to ensure that Series and Indexes are unboxed before
# getting to the EA classes.


@register_extension_dtype
class DecimalDtype2(DecimalDtype):
    name = 'decimal2'

    @classmethod
    def construct_array_type(cls):
        return DecimalArray2


class DecimalArray2(DecimalArray):
    @classmethod
    def _from_sequence(cls, scalars, dtype=None, copy=False):
        if isinstance(scalars, (pd.Series, pd.Index)):
            raise TypeError

        return super(DecimalArray2, cls)._from_sequence(
            scalars, dtype=dtype, copy=copy
        )


@pytest.mark.parametrize("box", [pd.Series, pd.Index])
def test_array_unboxes(box):
    data = box([decimal.Decimal('1'), decimal.Decimal('2')])
    # make sure it works
    with pytest.raises(TypeError):
        DecimalArray2._from_sequence(data)

    result = pd.array(data, dtype='decimal2')
    expected = DecimalArray2._from_sequence(data.values)
    tm.assert_equal(result, expected)


@pytest.fixture
def registry_without_decimal():
    idx = registry.dtypes.index(DecimalDtype)
    registry.dtypes.pop(idx)
    yield
    registry.dtypes.append(DecimalDtype)


def test_array_not_registered(registry_without_decimal):
    # check we aren't on it
    assert registry.find('decimal') is None
    data = [decimal.Decimal('1'), decimal.Decimal('2')]

    result = pd.array(data, dtype=DecimalDtype)
    expected = DecimalArray._from_sequence(data)
    tm.assert_equal(result, expected)
