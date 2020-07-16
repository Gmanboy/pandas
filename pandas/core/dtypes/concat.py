"""
Utility functions related to concat.
"""
from typing import cast

import numpy as np

from pandas._typing import ArrayLike, DtypeObj

from pandas.core.dtypes.cast import find_common_type
from pandas.core.dtypes.common import (
    is_bool_dtype,
    is_categorical_dtype,
    is_datetime64_dtype,
    is_datetime64tz_dtype,
    is_dtype_equal,
    is_extension_array_dtype,
    is_object_dtype,
    is_sparse,
    is_timedelta64_dtype,
)
from pandas.core.dtypes.generic import ABCCategoricalIndex, ABCRangeIndex, ABCSeries

from pandas.core.arrays import ExtensionArray
from pandas.core.arrays.sparse import SparseArray
from pandas.core.construction import array


def get_dtype_kinds(l):
    """
    Parameters
    ----------
    l : list of arrays

    Returns
    -------
    a set of kinds that exist in this list of arrays
    """
    typs = set()
    for arr in l:

        dtype = arr.dtype
        if is_categorical_dtype(dtype):
            typ = "category"
        elif is_sparse(dtype):
            typ = "sparse"
        elif isinstance(arr, ABCRangeIndex):
            typ = "range"
        elif is_datetime64tz_dtype(dtype):
            # if to_concat contains different tz,
            # the result must be object dtype
            typ = str(dtype)
        elif is_datetime64_dtype(dtype):
            typ = "datetime"
        elif is_timedelta64_dtype(dtype):
            typ = "timedelta"
        elif is_object_dtype(dtype):
            typ = "object"
        elif is_bool_dtype(dtype):
            typ = "bool"
        elif is_extension_array_dtype(dtype):
            typ = str(dtype)
        else:
            typ = dtype.kind
        typs.add(typ)
    return typs


def _cast_to_common_type(arr: ArrayLike, dtype: DtypeObj) -> ArrayLike:
    """
    Helper function for `arr.astype(common_dtype)` but handling all special
    cases.
    """
    if (
        is_categorical_dtype(arr.dtype)
        and isinstance(dtype, np.dtype)
        and np.issubdtype(dtype, np.integer)
    ):
        # problem case: categorical of int -> gives int as result dtype,
        # but categorical can contain NAs -> fall back to object dtype
        try:
            return arr.astype(dtype, copy=False)
        except ValueError:
            return arr.astype(object, copy=False)

    if is_sparse(arr) and not is_sparse(dtype):
        # problem case: SparseArray.astype(dtype) doesn't follow the specified
        # dtype exactly, but converts this to Sparse[dtype] -> first manually
        # convert to dense array
        arr = cast(SparseArray, arr)
        return arr.to_dense().astype(dtype, copy=False)

    if (
        isinstance(arr, np.ndarray)
        and arr.dtype.kind in ["m", "M"]
        and dtype is np.dtype("object")
    ):
        # wrap datetime-likes in EA to ensure astype(object) gives Timestamp/Timedelta
        # this can happen when concat_compat is called directly on arrays (when arrays
        # are not coming from Index/Series._values), eg in BlockManager.quantile
        arr = array(arr)

    if is_extension_array_dtype(dtype):
        if isinstance(arr, np.ndarray):
            # numpy's astype cannot handle ExtensionDtypes
            return array(arr, dtype=dtype, copy=False)
    return arr.astype(dtype, copy=False)


def concat_compat(to_concat, axis: int = 0):
    """
    provide concatenation of an array of arrays each of which is a single
    'normalized' dtypes (in that for example, if it's object, then it is a
    non-datetimelike and provide a combined dtype for the resulting array that
    preserves the overall dtype if possible)

    Parameters
    ----------
    to_concat : array of arrays
    axis : axis to provide concatenation

    Returns
    -------
    a single array, preserving the combined dtypes
    """
    # filter empty arrays
    # 1-d dtypes always are included here
    def is_nonempty(x) -> bool:
        if x.ndim <= axis:
            return True
        return x.shape[axis] > 0

    # If all arrays are empty, there's nothing to convert, just short-cut to
    # the concatenation, #3121.
    #
    # Creating an empty array directly is tempting, but the winnings would be
    # marginal given that it would still require shape & dtype calculation and
    # np.concatenate which has them both implemented is compiled.
    non_empties = [x for x in to_concat if is_nonempty(x)]
    if non_empties and axis == 0:
        to_concat = non_empties

    typs = get_dtype_kinds(to_concat)
    _contains_datetime = any(typ.startswith("datetime") for typ in typs)

    all_empty = not len(non_empties)
    single_dtype = len({x.dtype for x in to_concat}) == 1
    any_ea = any(is_extension_array_dtype(x.dtype) for x in to_concat)

    if any_ea:
        if not single_dtype:
            target_dtype = find_common_type([x.dtype for x in to_concat])
            to_concat = [_cast_to_common_type(arr, target_dtype) for arr in to_concat]

        if isinstance(to_concat[0], ExtensionArray) and axis == 0:
            cls = type(to_concat[0])
            return cls._concat_same_type(to_concat)
        else:
            return np.concatenate(to_concat, axis=axis)

    elif _contains_datetime or "timedelta" in typs:
        return concat_datetime(to_concat, axis=axis, typs=typs)

    elif all_empty:
        # we have all empties, but may need to coerce the result dtype to
        # object if we have non-numeric type operands (numpy would otherwise
        # cast this to float)
        typs = get_dtype_kinds(to_concat)
        if len(typs) != 1:

            if not len(typs - {"i", "u", "f"}) or not len(typs - {"bool", "i", "u"}):
                # let numpy coerce
                pass
            else:
                # coerce to object
                to_concat = [x.astype("object") for x in to_concat]

    return np.concatenate(to_concat, axis=axis)


def union_categoricals(
    to_union, sort_categories: bool = False, ignore_order: bool = False
):
    """
    Combine list-like of Categorical-like, unioning categories.

    All categories must have the same dtype.

    Parameters
    ----------
    to_union : list-like
        Categorical, CategoricalIndex, or Series with dtype='category'.
    sort_categories : bool, default False
        If true, resulting categories will be lexsorted, otherwise
        they will be ordered as they appear in the data.
    ignore_order : bool, default False
        If true, the ordered attribute of the Categoricals will be ignored.
        Results in an unordered categorical.

    Returns
    -------
    Categorical

    Raises
    ------
    TypeError
        - all inputs do not have the same dtype
        - all inputs do not have the same ordered property
        - all inputs are ordered and their categories are not identical
        - sort_categories=True and Categoricals are ordered
    ValueError
        Empty list of categoricals passed

    Notes
    -----
    To learn more about categories, see `link
    <https://pandas.pydata.org/pandas-docs/stable/user_guide/categorical.html#unioning>`__

    Examples
    --------
    >>> from pandas.api.types import union_categoricals

    If you want to combine categoricals that do not necessarily have
    the same categories, `union_categoricals` will combine a list-like
    of categoricals. The new categories will be the union of the
    categories being combined.

    >>> a = pd.Categorical(["b", "c"])
    >>> b = pd.Categorical(["a", "b"])
    >>> union_categoricals([a, b])
    ['b', 'c', 'a', 'b']
    Categories (3, object): ['b', 'c', 'a']

    By default, the resulting categories will be ordered as they appear
    in the `categories` of the data. If you want the categories to be
    lexsorted, use `sort_categories=True` argument.

    >>> union_categoricals([a, b], sort_categories=True)
    ['b', 'c', 'a', 'b']
    Categories (3, object): ['a', 'b', 'c']

    `union_categoricals` also works with the case of combining two
    categoricals of the same categories and order information (e.g. what
    you could also `append` for).

    >>> a = pd.Categorical(["a", "b"], ordered=True)
    >>> b = pd.Categorical(["a", "b", "a"], ordered=True)
    >>> union_categoricals([a, b])
    ['a', 'b', 'a', 'b', 'a']
    Categories (2, object): ['a' < 'b']

    Raises `TypeError` because the categories are ordered and not identical.

    >>> a = pd.Categorical(["a", "b"], ordered=True)
    >>> b = pd.Categorical(["a", "b", "c"], ordered=True)
    >>> union_categoricals([a, b])
    Traceback (most recent call last):
        ...
    TypeError: to union ordered Categoricals, all categories must be the same

    New in version 0.20.0

    Ordered categoricals with different categories or orderings can be
    combined by using the `ignore_ordered=True` argument.

    >>> a = pd.Categorical(["a", "b", "c"], ordered=True)
    >>> b = pd.Categorical(["c", "b", "a"], ordered=True)
    >>> union_categoricals([a, b], ignore_order=True)
    ['a', 'b', 'c', 'c', 'b', 'a']
    Categories (3, object): ['a', 'b', 'c']

    `union_categoricals` also works with a `CategoricalIndex`, or `Series`
    containing categorical data, but note that the resulting array will
    always be a plain `Categorical`

    >>> a = pd.Series(["b", "c"], dtype='category')
    >>> b = pd.Series(["a", "b"], dtype='category')
    >>> union_categoricals([a, b])
    ['b', 'c', 'a', 'b']
    Categories (3, object): ['b', 'c', 'a']
    """
    from pandas import Categorical
    from pandas.core.arrays.categorical import recode_for_categories

    if len(to_union) == 0:
        raise ValueError("No Categoricals to union")

    def _maybe_unwrap(x):
        if isinstance(x, (ABCCategoricalIndex, ABCSeries)):
            return x._values
        elif isinstance(x, Categorical):
            return x
        else:
            raise TypeError("all components to combine must be Categorical")

    to_union = [_maybe_unwrap(x) for x in to_union]
    first = to_union[0]

    if not all(
        is_dtype_equal(other.categories.dtype, first.categories.dtype)
        for other in to_union[1:]
    ):
        raise TypeError("dtype of categories must be the same")

    ordered = False
    if all(first.is_dtype_equal(other) for other in to_union[1:]):
        # identical categories - fastpath
        categories = first.categories
        ordered = first.ordered

        if all(first.categories.equals(other.categories) for other in to_union[1:]):
            new_codes = np.concatenate([c.codes for c in to_union])
        else:
            codes = [first.codes] + [
                recode_for_categories(other.codes, other.categories, first.categories)
                for other in to_union[1:]
            ]
            new_codes = np.concatenate(codes)

        if sort_categories and not ignore_order and ordered:
            raise TypeError("Cannot use sort_categories=True with ordered Categoricals")

        if sort_categories and not categories.is_monotonic_increasing:
            categories = categories.sort_values()
            indexer = categories.get_indexer(first.categories)

            from pandas.core.algorithms import take_1d

            new_codes = take_1d(indexer, new_codes, fill_value=-1)
    elif ignore_order or all(not c.ordered for c in to_union):
        # different categories - union and recode
        cats = first.categories.append([c.categories for c in to_union[1:]])
        categories = cats.unique()
        if sort_categories:
            categories = categories.sort_values()

        new_codes = [
            recode_for_categories(c.codes, c.categories, categories) for c in to_union
        ]
        new_codes = np.concatenate(new_codes)
    else:
        # ordered - to show a proper error message
        if all(c.ordered for c in to_union):
            msg = "to union ordered Categoricals, all categories must be the same"
            raise TypeError(msg)
        else:
            raise TypeError("Categorical.ordered must be the same")

    if ignore_order:
        ordered = False

    return Categorical(new_codes, categories=categories, ordered=ordered, fastpath=True)


def _concatenate_2d(to_concat, axis: int):
    # coerce to 2d if needed & concatenate
    if axis == 1:
        to_concat = [np.atleast_2d(x) for x in to_concat]
    return np.concatenate(to_concat, axis=axis)


def concat_datetime(to_concat, axis=0, typs=None):
    """
    provide concatenation of an datetimelike array of arrays each of which is a
    single M8[ns], datetime64[ns, tz] or m8[ns] dtype

    Parameters
    ----------
    to_concat : array of arrays
    axis : axis to provide concatenation
    typs : set of to_concat dtypes

    Returns
    -------
    a single array, preserving the combined dtypes
    """
    if typs is None:
        typs = get_dtype_kinds(to_concat)

    to_concat = [_wrap_datetimelike(x) for x in to_concat]
    single_dtype = len({x.dtype for x in to_concat}) == 1

    # multiple types, need to coerce to object
    if not single_dtype:
        # wrap_datetimelike ensures that astype(object) wraps in Timestamp/Timedelta
        return _concatenate_2d([x.astype(object) for x in to_concat], axis=axis)

    if axis == 1:
        # TODO(EA2D): kludge not necessary with 2D EAs
        to_concat = [x.reshape(1, -1) if x.ndim == 1 else x for x in to_concat]

    result = type(to_concat[0])._concat_same_type(to_concat, axis=axis)

    if result.ndim == 2 and is_extension_array_dtype(result.dtype):
        # TODO(EA2D): kludge not necessary with 2D EAs
        assert result.shape[0] == 1
        result = result[0]
    return result


def _wrap_datetimelike(arr):
    """
    Wrap datetime64 and timedelta64 ndarrays in DatetimeArray/TimedeltaArray.

    DTA/TDA handle .astype(object) correctly.
    """
    from pandas.core.construction import array as pd_array, extract_array

    arr = extract_array(arr, extract_numpy=True)
    if isinstance(arr, np.ndarray) and arr.dtype.kind in ["m", "M"]:
        arr = pd_array(arr)
    return arr
