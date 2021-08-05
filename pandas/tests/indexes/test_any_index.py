"""
Tests that can be parametrized over _any_ Index object.

TODO: consider using hypothesis for these.
"""
import re

import numpy as np
import pytest

from pandas.core.dtypes.common import is_float_dtype

import pandas._testing as tm


def test_boolean_context_compat(index):
    # GH#7897
    with pytest.raises(ValueError, match="The truth value of a"):
        if index:
            pass

    with pytest.raises(ValueError, match="The truth value of a"):
        bool(index)


def test_sort(index):
    msg = "cannot sort an Index object in-place, use sort_values instead"
    with pytest.raises(TypeError, match=msg):
        index.sort()


def test_hash_error(index):
    with pytest.raises(TypeError, match=f"unhashable type: '{type(index).__name__}'"):
        hash(index)


def test_copy_dtype_deprecated(index):
    # GH#35853
    with tm.assert_produces_warning(FutureWarning):
        index.copy(dtype=object)


def test_mutability(index):
    if not len(index):
        return
    msg = "Index does not support mutable operations"
    with pytest.raises(TypeError, match=msg):
        index[0] = index[0]


def test_map_identity_mapping(index):
    # GH#12766
    result = index.map(lambda x: x)
    if index._is_backward_compat_public_numeric_index:
        if is_float_dtype(index.dtype):
            expected = index.astype(np.float64)
        elif index.dtype == np.uint64:
            expected = index.astype(np.uint64)
        else:
            expected = index.astype(np.int64)
    else:
        expected = index
    tm.assert_index_equal(result, expected)


def test_wrong_number_names(index):
    names = index.nlevels * ["apple", "banana", "carrot"]
    with pytest.raises(ValueError, match="^Length"):
        index.names = names


def test_view_preserves_name(index):
    assert index.view().name == index.name


def test_ravel_deprecation(index):
    # GH#19956 ravel returning ndarray is deprecated
    with tm.assert_produces_warning(FutureWarning):
        index.ravel()


def test_is_type_compatible_deprecation(index):
    # GH#42113
    msg = "is_type_compatible is deprecated"
    with tm.assert_produces_warning(FutureWarning, match=msg):
        index.is_type_compatible(index.inferred_type)


class TestConversion:
    def test_to_series(self, index):
        # assert that we are creating a copy of the index

        ser = index.to_series()
        assert ser.values is not index.values
        assert ser.index is not index
        assert ser.name == index.name

    def test_to_series_with_arguments(self, index):
        # GH#18699

        # index kwarg
        ser = index.to_series(index=index)

        assert ser.values is not index.values
        assert ser.index is index
        assert ser.name == index.name

        # name kwarg
        ser = index.to_series(name="__test")

        assert ser.values is not index.values
        assert ser.index is not index
        assert ser.name != index.name

    def test_tolist_matches_list(self, index):
        assert index.tolist() == list(index)


class TestRoundTrips:
    def test_pickle_roundtrip(self, index):
        result = tm.round_trip_pickle(index)
        tm.assert_index_equal(result, index)
        if result.nlevels > 1:
            # GH#8367 round-trip with timezone
            assert index.equal_levels(result)

    def test_pickle_preserves_name(self, index):
        original_name, index.name = index.name, "foo"
        unpickled = tm.round_trip_pickle(index)
        assert index.equals(unpickled)
        index.name = original_name


class TestIndexing:
    def test_slice_keeps_name(self, index):
        assert index.name == index[1:].name

    @pytest.mark.parametrize("item", [101, "no_int"])
    # FutureWarning from non-tuple sequence of nd indexing
    @pytest.mark.filterwarnings("ignore::FutureWarning")
    def test_getitem_error(self, index, item):
        msg = r"index 101 is out of bounds for axis 0 with size [\d]+|" + re.escape(
            "only integers, slices (`:`), ellipsis (`...`), numpy.newaxis (`None`) "
            "and integer or boolean arrays are valid indices"
        )
        with pytest.raises(IndexError, match=msg):
            index[item]


class TestRendering:
    def test_str(self, index):
        # test the string repr
        index.name = "foo"
        assert "'foo'" in str(index)
        assert type(index).__name__ in str(index)


class TestReductions:
    def test_argmax_axis_invalid(self, index):
        # GH#23081
        msg = r"`axis` must be fewer than the number of dimensions \(1\)"
        with pytest.raises(ValueError, match=msg):
            index.argmax(axis=1)
        with pytest.raises(ValueError, match=msg):
            index.argmin(axis=2)
        with pytest.raises(ValueError, match=msg):
            index.min(axis=-2)
        with pytest.raises(ValueError, match=msg):
            index.max(axis=-3)
