import numbers
from typing import TYPE_CHECKING, List, Tuple, Type, Union
import warnings

import numpy as np

from pandas._libs import lib, missing as libmissing
from pandas._typing import ArrayLike
from pandas.compat import set_function_name
from pandas.compat.numpy import function as nv

from pandas.core.dtypes.base import ExtensionDtype
from pandas.core.dtypes.cast import astype_nansafe
from pandas.core.dtypes.common import (
    is_bool_dtype,
    is_extension_array_dtype,
    is_float,
    is_float_dtype,
    is_integer_dtype,
    is_list_like,
    is_numeric_dtype,
    is_scalar,
    pandas_dtype,
)
from pandas.core.dtypes.dtypes import register_extension_dtype
from pandas.core.dtypes.generic import ABCDataFrame, ABCIndexClass, ABCSeries
from pandas.core.dtypes.missing import isna, notna

from pandas.core import nanops, ops
from pandas.core.array_algos import masked_reductions
from pandas.core.indexers import check_array_indexer

from .masked import BaseMaskedArray

if TYPE_CHECKING:
    import pyarrow  # noqa: F401


@register_extension_dtype
class BooleanDtype(ExtensionDtype):
    """
    Extension dtype for boolean data.

    .. versionadded:: 1.0.0

    .. warning::

       BooleanDtype is considered experimental. The implementation and
       parts of the API may change without warning.

    Attributes
    ----------
    None

    Methods
    -------
    None

    Examples
    --------
    >>> pd.BooleanDtype()
    BooleanDtype
    """

    name = "boolean"

    @property
    def na_value(self) -> libmissing.NAType:
        """
        BooleanDtype uses :attr:`pandas.NA` as the missing NA value.

        .. warning::

           `na_value` may change in a future release.
        """
        return libmissing.NA

    @property
    def type(self) -> Type[np.bool_]:
        return np.bool_

    @property
    def kind(self) -> str:
        return "b"

    @classmethod
    def construct_array_type(cls) -> Type["BooleanArray"]:
        """
        Return the array type associated with this dtype.

        Returns
        -------
        type
        """
        return BooleanArray

    def __repr__(self) -> str:
        return "BooleanDtype"

    @property
    def _is_boolean(self) -> bool:
        return True

    def __from_arrow__(
        self, array: Union["pyarrow.Array", "pyarrow.ChunkedArray"]
    ) -> "BooleanArray":
        """
        Construct BooleanArray from pyarrow Array/ChunkedArray.
        """
        import pyarrow  # noqa: F811

        if isinstance(array, pyarrow.Array):
            chunks = [array]
        else:
            # pyarrow.ChunkedArray
            chunks = array.chunks

        results = []
        for arr in chunks:
            # TODO should optimize this without going through object array
            bool_arr = BooleanArray._from_sequence(np.array(arr))
            results.append(bool_arr)

        return BooleanArray._concat_same_type(results)


def coerce_to_array(
    values, mask=None, copy: bool = False
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Coerce the input values array to numpy arrays with a mask.

    Parameters
    ----------
    values : 1D list-like
    mask : bool 1D array, optional
    copy : bool, default False
        if True, copy the input

    Returns
    -------
    tuple of (values, mask)
    """
    if isinstance(values, BooleanArray):
        if mask is not None:
            raise ValueError("cannot pass mask for BooleanArray input")
        values, mask = values._data, values._mask
        if copy:
            values = values.copy()
            mask = mask.copy()
        return values, mask

    mask_values = None
    if isinstance(values, np.ndarray) and values.dtype == np.bool_:
        if copy:
            values = values.copy()
    elif isinstance(values, np.ndarray) and is_numeric_dtype(values.dtype):
        mask_values = isna(values)

        values_bool = np.zeros(len(values), dtype=bool)
        values_bool[~mask_values] = values[~mask_values].astype(bool)

        if not np.all(
            values_bool[~mask_values].astype(values.dtype) == values[~mask_values]
        ):
            raise TypeError("Need to pass bool-like values")

        values = values_bool
    else:
        values_object = np.asarray(values, dtype=object)

        inferred_dtype = lib.infer_dtype(values_object, skipna=True)
        integer_like = ("floating", "integer", "mixed-integer-float")
        if inferred_dtype not in ("boolean", "empty") + integer_like:
            raise TypeError("Need to pass bool-like values")

        mask_values = isna(values_object)
        values = np.zeros(len(values), dtype=bool)
        values[~mask_values] = values_object[~mask_values].astype(bool)

        # if the values were integer-like, validate it were actually 0/1's
        if inferred_dtype in integer_like:
            if not np.all(
                values[~mask_values].astype(float)
                == values_object[~mask_values].astype(float)
            ):
                raise TypeError("Need to pass bool-like values")

    if mask is None and mask_values is None:
        mask = np.zeros(len(values), dtype=bool)
    elif mask is None:
        mask = mask_values
    else:
        if isinstance(mask, np.ndarray) and mask.dtype == np.bool_:
            if mask_values is not None:
                mask = mask | mask_values
            else:
                if copy:
                    mask = mask.copy()
        else:
            mask = np.array(mask, dtype=bool)
            if mask_values is not None:
                mask = mask | mask_values

    if not values.ndim == 1:
        raise ValueError("values must be a 1D list-like")
    if not mask.ndim == 1:
        raise ValueError("mask must be a 1D list-like")

    return values, mask


class BooleanArray(BaseMaskedArray):
    """
    Array of boolean (True/False) data with missing values.

    This is a pandas Extension array for boolean data, under the hood
    represented by 2 numpy arrays: a boolean array with the data and
    a boolean array with the mask (True indicating missing).

    BooleanArray implements Kleene logic (sometimes called three-value
    logic) for logical operations. See :ref:`boolean.kleene` for more.

    To construct an BooleanArray from generic array-like input, use
    :func:`pandas.array` specifying ``dtype="boolean"`` (see examples
    below).

    .. versionadded:: 1.0.0

    .. warning::

       BooleanArray is considered experimental. The implementation and
       parts of the API may change without warning.

    Parameters
    ----------
    values : numpy.ndarray
        A 1-d boolean-dtype array with the data.
    mask : numpy.ndarray
        A 1-d boolean-dtype array indicating missing values (True
        indicates missing).
    copy : bool, default False
        Whether to copy the `values` and `mask` arrays.

    Attributes
    ----------
    None

    Methods
    -------
    None

    Returns
    -------
    BooleanArray

    Examples
    --------
    Create an BooleanArray with :func:`pandas.array`:

    >>> pd.array([True, False, None], dtype="boolean")
    <BooleanArray>
    [True, False, <NA>]
    Length: 3, dtype: boolean
    """

    # The value used to fill '_data' to avoid upcasting
    _internal_fill_value = False

    def __init__(self, values: np.ndarray, mask: np.ndarray, copy: bool = False):
        if not (isinstance(values, np.ndarray) and values.dtype == np.bool_):
            raise TypeError(
                "values should be boolean numpy array. Use "
                "the 'array' function instead"
            )
        if not (isinstance(mask, np.ndarray) and mask.dtype == np.bool_):
            raise TypeError(
                "mask should be boolean numpy array. Use "
                "the 'array' function instead"
            )
        if not values.ndim == 1:
            raise ValueError("values must be a 1D array")
        if not mask.ndim == 1:
            raise ValueError("mask must be a 1D array")

        self._dtype = BooleanDtype()
        super().__init__(values, mask, copy=copy)

    @property
    def dtype(self) -> BooleanDtype:
        return self._dtype

    @classmethod
    def _from_sequence(cls, scalars, dtype=None, copy: bool = False) -> "BooleanArray":
        if dtype:
            assert dtype == "boolean"
        values, mask = coerce_to_array(scalars, copy=copy)
        return BooleanArray(values, mask)

    @classmethod
    def _from_sequence_of_strings(
        cls, strings: List[str], dtype=None, copy: bool = False
    ) -> "BooleanArray":
        def map_string(s):
            if isna(s):
                return s
            elif s in ["True", "TRUE", "true"]:
                return True
            elif s in ["False", "FALSE", "false"]:
                return False
            else:
                raise ValueError(f"{s} cannot be cast to bool")

        scalars = [map_string(x) for x in strings]
        return cls._from_sequence(scalars, dtype, copy)

    def _values_for_factorize(self) -> Tuple[np.ndarray, int]:
        data = self._data.astype("int8")
        data[self._mask] = -1
        return data, -1

    @classmethod
    def _from_factorized(cls, values, original: "BooleanArray") -> "BooleanArray":
        return cls._from_sequence(values, dtype=original.dtype)

    _HANDLED_TYPES = (np.ndarray, numbers.Number, bool, np.bool_)

    def __array_ufunc__(self, ufunc, method: str, *inputs, **kwargs):
        # For BooleanArray inputs, we apply the ufunc to ._data
        # and mask the result.
        if method == "reduce":
            # Not clear how to handle missing values in reductions. Raise.
            raise NotImplementedError("The 'reduce' method is not supported.")
        out = kwargs.get("out", ())

        for x in inputs + out:
            if not isinstance(x, self._HANDLED_TYPES + (BooleanArray,)):
                return NotImplemented

        # for binary ops, use our custom dunder methods
        result = ops.maybe_dispatch_ufunc_to_dunder_op(
            self, ufunc, method, *inputs, **kwargs
        )
        if result is not NotImplemented:
            return result

        mask = np.zeros(len(self), dtype=bool)
        inputs2 = []
        for x in inputs:
            if isinstance(x, BooleanArray):
                mask |= x._mask
                inputs2.append(x._data)
            else:
                inputs2.append(x)

        def reconstruct(x):
            # we don't worry about scalar `x` here, since we
            # raise for reduce up above.

            if is_bool_dtype(x.dtype):
                m = mask.copy()
                return BooleanArray(x, m)
            else:
                x[mask] = np.nan
            return x

        result = getattr(ufunc, method)(*inputs2, **kwargs)
        if isinstance(result, tuple):
            tuple(reconstruct(x) for x in result)
        else:
            return reconstruct(result)

    def __setitem__(self, key, value) -> None:
        _is_scalar = is_scalar(value)
        if _is_scalar:
            value = [value]
        value, mask = coerce_to_array(value)

        if _is_scalar:
            value = value[0]
            mask = mask[0]

        key = check_array_indexer(self, key)
        self._data[key] = value
        self._mask[key] = mask

    def astype(self, dtype, copy: bool = True) -> ArrayLike:
        """
        Cast to a NumPy array or ExtensionArray with 'dtype'.

        Parameters
        ----------
        dtype : str or dtype
            Typecode or data-type to which the array is cast.
        copy : bool, default True
            Whether to copy the data, even if not necessary. If False,
            a copy is made only if the old dtype does not match the
            new dtype.

        Returns
        -------
        ndarray or ExtensionArray
            NumPy ndarray, BooleanArray or IntegerArray with 'dtype' for its dtype.

        Raises
        ------
        TypeError
            if incompatible type with an BooleanDtype, equivalent of same_kind
            casting
        """
        dtype = pandas_dtype(dtype)

        if isinstance(dtype, BooleanDtype):
            values, mask = coerce_to_array(self, copy=copy)
            return BooleanArray(values, mask, copy=False)

        if is_bool_dtype(dtype):
            # astype_nansafe converts np.nan to True
            if self._hasna:
                raise ValueError("cannot convert float NaN to bool")
            else:
                return self._data.astype(dtype, copy=copy)
        if is_extension_array_dtype(dtype) and is_integer_dtype(dtype):
            from pandas.core.arrays import IntegerArray

            return IntegerArray(
                self._data.astype(dtype.numpy_dtype), self._mask.copy(), copy=False
            )
        # for integer, error if there are missing values
        if is_integer_dtype(dtype):
            if self._hasna:
                raise ValueError("cannot convert NA to integer")
        # for float dtype, ensure we use np.nan before casting (numpy cannot
        # deal with pd.NA)
        na_value = self._na_value
        if is_float_dtype(dtype):
            na_value = np.nan
        # coerce
        data = self.to_numpy(na_value=na_value)
        return astype_nansafe(data, dtype, copy=False)

    def _values_for_argsort(self) -> np.ndarray:
        """
        Return values for sorting.

        Returns
        -------
        ndarray
            The transformed values should maintain the ordering between values
            within the array.

        See Also
        --------
        ExtensionArray.argsort
        """
        data = self._data.copy()
        data[self._mask] = -1
        return data

    def any(self, skipna: bool = True, **kwargs):
        """
        Return whether any element is True.

        Returns False unless there is at least one element that is True.
        By default, NAs are skipped. If ``skipna=False`` is specified and
        missing values are present, similar :ref:`Kleene logic <boolean.kleene>`
        is used as for logical operations.

        Parameters
        ----------
        skipna : bool, default True
            Exclude NA values. If the entire array is NA and `skipna` is
            True, then the result will be False, as for an empty array.
            If `skipna` is False, the result will still be True if there is
            at least one element that is True, otherwise NA will be returned
            if there are NA's present.
        **kwargs : any, default None
            Additional keywords have no effect but might be accepted for
            compatibility with NumPy.

        Returns
        -------
        bool or :attr:`pandas.NA`

        See Also
        --------
        numpy.any : Numpy version of this method.
        BooleanArray.all : Return whether all elements are True.

        Examples
        --------
        The result indicates whether any element is True (and by default
        skips NAs):

        >>> pd.array([True, False, True]).any()
        True
        >>> pd.array([True, False, pd.NA]).any()
        True
        >>> pd.array([False, False, pd.NA]).any()
        False
        >>> pd.array([], dtype="boolean").any()
        False
        >>> pd.array([pd.NA], dtype="boolean").any()
        False

        With ``skipna=False``, the result can be NA if this is logically
        required (whether ``pd.NA`` is True or False influences the result):

        >>> pd.array([True, False, pd.NA]).any(skipna=False)
        True
        >>> pd.array([False, False, pd.NA]).any(skipna=False)
        <NA>
        """
        kwargs.pop("axis", None)
        nv.validate_any((), kwargs)

        values = self._data.copy()
        np.putmask(values, self._mask, False)
        result = values.any()
        if skipna:
            return result
        else:
            if result or len(self) == 0:
                return result
            else:
                return self.dtype.na_value

    def all(self, skipna: bool = True, **kwargs):
        """
        Return whether all elements are True.

        Returns True unless there is at least one element that is False.
        By default, NAs are skipped. If ``skipna=False`` is specified and
        missing values are present, similar :ref:`Kleene logic <boolean.kleene>`
        is used as for logical operations.

        Parameters
        ----------
        skipna : bool, default True
            Exclude NA values. If the entire array is NA and `skipna` is
            True, then the result will be True, as for an empty array.
            If `skipna` is False, the result will still be False if there is
            at least one element that is False, otherwise NA will be returned
            if there are NA's present.
        **kwargs : any, default None
            Additional keywords have no effect but might be accepted for
            compatibility with NumPy.

        Returns
        -------
        bool or :attr:`pandas.NA`

        See Also
        --------
        numpy.all : Numpy version of this method.
        BooleanArray.any : Return whether any element is True.

        Examples
        --------
        The result indicates whether any element is True (and by default
        skips NAs):

        >>> pd.array([True, True, pd.NA]).all()
        True
        >>> pd.array([True, False, pd.NA]).all()
        False
        >>> pd.array([], dtype="boolean").all()
        True
        >>> pd.array([pd.NA], dtype="boolean").all()
        True

        With ``skipna=False``, the result can be NA if this is logically
        required (whether ``pd.NA`` is True or False influences the result):

        >>> pd.array([True, True, pd.NA]).all(skipna=False)
        <NA>
        >>> pd.array([True, False, pd.NA]).all(skipna=False)
        False
        """
        kwargs.pop("axis", None)
        nv.validate_all((), kwargs)

        values = self._data.copy()
        np.putmask(values, self._mask, True)
        result = values.all()

        if skipna:
            return result
        else:
            if not result or len(self) == 0:
                return result
            else:
                return self.dtype.na_value

    @classmethod
    def _create_logical_method(cls, op):
        def logical_method(self, other):
            if isinstance(other, (ABCDataFrame, ABCSeries, ABCIndexClass)):
                # Rely on pandas to unbox and dispatch to us.
                return NotImplemented

            assert op.__name__ in {"or_", "ror_", "and_", "rand_", "xor", "rxor"}
            other = lib.item_from_zerodim(other)
            other_is_booleanarray = isinstance(other, BooleanArray)
            other_is_scalar = lib.is_scalar(other)
            mask = None

            if other_is_booleanarray:
                other, mask = other._data, other._mask
            elif is_list_like(other):
                other = np.asarray(other, dtype="bool")
                if other.ndim > 1:
                    raise NotImplementedError(
                        "can only perform ops with 1-d structures"
                    )
                other, mask = coerce_to_array(other, copy=False)
            elif isinstance(other, np.bool_):
                other = other.item()

            if other_is_scalar and not (other is libmissing.NA or lib.is_bool(other)):
                raise TypeError(
                    "'other' should be pandas.NA or a bool. "
                    f"Got {type(other).__name__} instead."
                )

            if not other_is_scalar and len(self) != len(other):
                raise ValueError("Lengths must match to compare")

            if op.__name__ in {"or_", "ror_"}:
                result, mask = ops.kleene_or(self._data, other, self._mask, mask)
            elif op.__name__ in {"and_", "rand_"}:
                result, mask = ops.kleene_and(self._data, other, self._mask, mask)
            elif op.__name__ in {"xor", "rxor"}:
                result, mask = ops.kleene_xor(self._data, other, self._mask, mask)

            return BooleanArray(result, mask)

        name = f"__{op.__name__}__"
        return set_function_name(logical_method, name, cls)

    @classmethod
    def _create_comparison_method(cls, op):
        def cmp_method(self, other):
            from pandas.arrays import IntegerArray

            if isinstance(
                other, (ABCDataFrame, ABCSeries, ABCIndexClass, IntegerArray)
            ):
                # Rely on pandas to unbox and dispatch to us.
                return NotImplemented

            other = lib.item_from_zerodim(other)
            mask = None

            if isinstance(other, BooleanArray):
                other, mask = other._data, other._mask

            elif is_list_like(other):
                other = np.asarray(other)
                if other.ndim > 1:
                    raise NotImplementedError(
                        "can only perform ops with 1-d structures"
                    )
                if len(self) != len(other):
                    raise ValueError("Lengths must match to compare")

            if other is libmissing.NA:
                # numpy does not handle pd.NA well as "other" scalar (it returns
                # a scalar False instead of an array)
                result = np.zeros_like(self._data)
                mask = np.ones_like(self._data)
            else:
                # numpy will show a DeprecationWarning on invalid elementwise
                # comparisons, this will raise in the future
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", "elementwise", FutureWarning)
                    with np.errstate(all="ignore"):
                        result = op(self._data, other)

                # nans propagate
                if mask is None:
                    mask = self._mask.copy()
                else:
                    mask = self._mask | mask

            return BooleanArray(result, mask, copy=False)

        name = f"__{op.__name__}"
        return set_function_name(cmp_method, name, cls)

    def _reduce(self, name: str, skipna: bool = True, **kwargs):

        if name in {"any", "all"}:
            return getattr(self, name)(skipna=skipna, **kwargs)

        data = self._data
        mask = self._mask

        if name == "sum":
            return masked_reductions.sum(data, mask, skipna=skipna, **kwargs)

        # coerce to a nan-aware float if needed
        if self._hasna:
            data = self.to_numpy("float64", na_value=np.nan)

        op = getattr(nanops, "nan" + name)
        result = op(data, axis=0, skipna=skipna, mask=mask, **kwargs)

        if np.isnan(result):
            return libmissing.NA

        # if we have numeric op that would result in an int, coerce to int if possible
        if name == "prod" and notna(result):
            int_result = np.int64(result)
            if int_result == result:
                result = int_result

        elif name in ["min", "max"] and notna(result):
            result = np.bool_(result)

        return result

    def _maybe_mask_result(self, result, mask, other, op_name: str):
        """
        Parameters
        ----------
        result : array-like
        mask : array-like bool
        other : scalar or array-like
        op_name : str
        """
        # if we have a float operand we are by-definition
        # a float result
        # or our op is a divide
        if (is_float_dtype(other) or is_float(other)) or (
            op_name in ["rtruediv", "truediv"]
        ):
            result[mask] = np.nan
            return result

        if is_bool_dtype(result):
            return BooleanArray(result, mask, copy=False)

        elif is_integer_dtype(result):
            from pandas.core.arrays import IntegerArray

            return IntegerArray(result, mask, copy=False)
        else:
            result[mask] = np.nan
            return result

    @classmethod
    def _create_arithmetic_method(cls, op):
        op_name = op.__name__

        def boolean_arithmetic_method(self, other):

            if isinstance(other, (ABCDataFrame, ABCSeries, ABCIndexClass)):
                # Rely on pandas to unbox and dispatch to us.
                return NotImplemented

            other = lib.item_from_zerodim(other)
            mask = None

            if isinstance(other, BooleanArray):
                other, mask = other._data, other._mask

            elif is_list_like(other):
                other = np.asarray(other)
                if other.ndim > 1:
                    raise NotImplementedError(
                        "can only perform ops with 1-d structures"
                    )
                if len(self) != len(other):
                    raise ValueError("Lengths must match")

            # nans propagate
            if mask is None:
                mask = self._mask
            else:
                mask = self._mask | mask

            with np.errstate(all="ignore"):
                result = op(self._data, other)

            # divmod returns a tuple
            if op_name == "divmod":
                div, mod = result
                return (
                    self._maybe_mask_result(div, mask, other, "floordiv"),
                    self._maybe_mask_result(mod, mask, other, "mod"),
                )

            return self._maybe_mask_result(result, mask, other, op_name)

        name = f"__{op_name}__"
        return set_function_name(boolean_arithmetic_method, name, cls)


BooleanArray._add_logical_ops()
BooleanArray._add_comparison_ops()
BooleanArray._add_arithmetic_ops()
