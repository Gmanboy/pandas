import numbers
from typing import TYPE_CHECKING, List, Optional, Tuple, Type, Union
import warnings

import numpy as np

from pandas._libs import lib, missing as libmissing
from pandas._typing import ArrayLike, DtypeObj
from pandas.compat import set_function_name
from pandas.compat.numpy import function as nv
from pandas.util._decorators import cache_readonly

from pandas.core.dtypes.cast import astype_nansafe
from pandas.core.dtypes.common import (
    is_bool_dtype,
    is_datetime64_dtype,
    is_float,
    is_float_dtype,
    is_integer,
    is_integer_dtype,
    is_list_like,
    is_object_dtype,
    pandas_dtype,
)
from pandas.core.dtypes.dtypes import register_extension_dtype
from pandas.core.dtypes.missing import isna

from pandas.core import nanops, ops
from pandas.core.array_algos import masked_reductions
from pandas.core.ops import invalid_comparison
from pandas.core.ops.common import unpack_zerodim_and_defer
from pandas.core.tools.numeric import to_numeric

from .masked import BaseMaskedArray, BaseMaskedDtype

if TYPE_CHECKING:
    import pyarrow


class FloatingDtype(BaseMaskedDtype):
    """
    An ExtensionDtype to hold a single size of floating dtype.

    These specific implementations are subclasses of the non-public
    FloatingDtype. For example we have Float32Dtype to represent float32.

    The attributes name & type are set when these subclasses are created.
    """

    def __repr__(self) -> str:
        return f"{self.name}Dtype()"

    @property
    def _is_numeric(self) -> bool:
        return True

    @classmethod
    def construct_array_type(cls) -> Type["FloatingArray"]:
        """
        Return the array type associated with this dtype.

        Returns
        -------
        type
        """
        return FloatingArray

    def _get_common_dtype(self, dtypes: List[DtypeObj]) -> Optional[DtypeObj]:
        # for now only handle other floating types
        if not all(isinstance(t, FloatingDtype) for t in dtypes):
            return None
        np_dtype = np.find_common_type(
            [t.numpy_dtype for t in dtypes], []  # type: ignore[union-attr]
        )
        if np.issubdtype(np_dtype, np.floating):
            return FLOAT_STR_TO_DTYPE[str(np_dtype)]
        return None

    def __from_arrow__(
        self, array: Union["pyarrow.Array", "pyarrow.ChunkedArray"]
    ) -> "FloatingArray":
        """
        Construct FloatingArray from pyarrow Array/ChunkedArray.
        """
        import pyarrow

        from pandas.core.arrays._arrow_utils import pyarrow_array_to_numpy_and_mask

        pyarrow_type = pyarrow.from_numpy_dtype(self.type)
        if not array.type.equals(pyarrow_type):
            array = array.cast(pyarrow_type)

        if isinstance(array, pyarrow.Array):
            chunks = [array]
        else:
            # pyarrow.ChunkedArray
            chunks = array.chunks

        results = []
        for arr in chunks:
            data, mask = pyarrow_array_to_numpy_and_mask(arr, dtype=self.type)
            float_arr = FloatingArray(data.copy(), ~mask, copy=False)
            results.append(float_arr)

        return FloatingArray._concat_same_type(results)


def coerce_to_array(
    values, dtype=None, mask=None, copy: bool = False
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Coerce the input values array to numpy arrays with a mask.

    Parameters
    ----------
    values : 1D list-like
    dtype : float dtype
    mask : bool 1D array, optional
    copy : bool, default False
        if True, copy the input

    Returns
    -------
    tuple of (values, mask)
    """
    # if values is floating numpy array, preserve it's dtype
    if dtype is None and hasattr(values, "dtype"):
        if is_float_dtype(values.dtype):
            dtype = values.dtype

    if dtype is not None:
        if isinstance(dtype, str) and dtype.startswith("Float"):
            # Avoid DeprecationWarning from NumPy about np.dtype("Float64")
            # https://github.com/numpy/numpy/pull/7476
            dtype = dtype.lower()

        if not issubclass(type(dtype), FloatingDtype):
            try:
                dtype = FLOAT_STR_TO_DTYPE[str(np.dtype(dtype))]
            except KeyError as err:
                raise ValueError(f"invalid dtype specified {dtype}") from err

    if isinstance(values, FloatingArray):
        values, mask = values._data, values._mask
        if dtype is not None:
            values = values.astype(dtype.numpy_dtype, copy=False)

        if copy:
            values = values.copy()
            mask = mask.copy()
        return values, mask

    values = np.array(values, copy=copy)
    if is_object_dtype(values):
        inferred_type = lib.infer_dtype(values, skipna=True)
        if inferred_type == "empty":
            values = np.empty(len(values))
            values.fill(np.nan)
        elif inferred_type not in [
            "floating",
            "integer",
            "mixed-integer",
            "integer-na",
            "mixed-integer-float",
        ]:
            raise TypeError(f"{values.dtype} cannot be converted to a FloatingDtype")

    elif is_bool_dtype(values) and is_float_dtype(dtype):
        values = np.array(values, dtype=float, copy=copy)

    elif not (is_integer_dtype(values) or is_float_dtype(values)):
        raise TypeError(f"{values.dtype} cannot be converted to a FloatingDtype")

    if mask is None:
        mask = isna(values)
    else:
        assert len(mask) == len(values)

    if not values.ndim == 1:
        raise TypeError("values must be a 1D list-like")
    if not mask.ndim == 1:
        raise TypeError("mask must be a 1D list-like")

    # infer dtype if needed
    if dtype is None:
        dtype = np.dtype("float64")
    else:
        dtype = dtype.type

    # if we are float, let's make sure that we can
    # safely cast

    # we copy as need to coerce here
    # TODO should this be a safe cast?
    if mask.any():
        values = values.copy()
        values[mask] = np.nan
        values = values.astype(dtype, copy=False)  # , casting="safe")
    else:
        values = values.astype(dtype, copy=False)  # , casting="safe")

    return values, mask


class FloatingArray(BaseMaskedArray):
    """
    Array of floating (optional missing) values.

    .. versionadded:: 1.2.0

    .. warning::

       FloatingArray is currently experimental, and its API or internal
       implementation may change without warning. Expecially the behaviour
       regarding NaN (distinct from NA missing values) is subject to change.

    We represent a FloatingArray with 2 numpy arrays:

    - data: contains a numpy float array of the appropriate dtype
    - mask: a boolean array holding a mask on the data, True is missing

    To construct an FloatingArray from generic array-like input, use
    :func:`pandas.array` with one of the float dtypes (see examples).

    See :ref:`integer_na` for more.

    Parameters
    ----------
    values : numpy.ndarray
        A 1-d float-dtype array.
    mask : numpy.ndarray
        A 1-d boolean-dtype array indicating missing values.
    copy : bool, default False
        Whether to copy the `values` and `mask`.

    Attributes
    ----------
    None

    Methods
    -------
    None

    Returns
    -------
    FloatingArray

    Examples
    --------
    Create an FloatingArray with :func:`pandas.array`:

    >>> pd.array([0.1, None, 0.3], dtype=pd.Float32Dtype())
    <FloatingArray>
    [0.1, <NA>, 0.3]
    Length: 3, dtype: Float32

    String aliases for the dtypes are also available. They are capitalized.

    >>> pd.array([0.1, None, 0.3], dtype="Float32")
    <FloatingArray>
    [0.1, <NA>, 0.3]
    Length: 3, dtype: Float32
    """

    # The value used to fill '_data' to avoid upcasting
    _internal_fill_value = 0.0

    @cache_readonly
    def dtype(self) -> FloatingDtype:
        return FLOAT_STR_TO_DTYPE[str(self._data.dtype)]

    def __init__(self, values: np.ndarray, mask: np.ndarray, copy: bool = False):
        if not (isinstance(values, np.ndarray) and values.dtype.kind == "f"):
            raise TypeError(
                "values should be floating numpy array. Use "
                "the 'pd.array' function instead"
            )
        super().__init__(values, mask, copy=copy)

    @classmethod
    def _from_sequence(cls, scalars, dtype=None, copy: bool = False) -> "FloatingArray":
        values, mask = coerce_to_array(scalars, dtype=dtype, copy=copy)
        return FloatingArray(values, mask)

    @classmethod
    def _from_sequence_of_strings(
        cls, strings, dtype=None, copy: bool = False
    ) -> "FloatingArray":
        scalars = to_numeric(strings, errors="raise")
        return cls._from_sequence(scalars, dtype, copy)

    _HANDLED_TYPES = (np.ndarray, numbers.Number)

    def __array_ufunc__(self, ufunc, method: str, *inputs, **kwargs):
        # For FloatingArray inputs, we apply the ufunc to ._data
        # and mask the result.
        if method == "reduce":
            # Not clear how to handle missing values in reductions. Raise.
            raise NotImplementedError("The 'reduce' method is not supported.")
        out = kwargs.get("out", ())

        for x in inputs + out:
            if not isinstance(x, self._HANDLED_TYPES + (FloatingArray,)):
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
            if isinstance(x, FloatingArray):
                mask |= x._mask
                inputs2.append(x._data)
            else:
                inputs2.append(x)

        def reconstruct(x):
            # we don't worry about scalar `x` here, since we
            # raise for reduce up above.

            # TODO
            if is_float_dtype(x.dtype):
                m = mask.copy()
                return FloatingArray(x, m)
            else:
                x[mask] = np.nan
            return x

        result = getattr(ufunc, method)(*inputs2, **kwargs)
        if isinstance(result, tuple):
            tuple(reconstruct(x) for x in result)
        else:
            return reconstruct(result)

    def _coerce_to_array(self, value) -> Tuple[np.ndarray, np.ndarray]:
        return coerce_to_array(value, dtype=self.dtype)

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
            NumPy ndarray, or BooleanArray, IntegerArray or FloatingArray with
            'dtype' for its dtype.

        Raises
        ------
        TypeError
            if incompatible type with an FloatingDtype, equivalent of same_kind
            casting
        """
        from pandas.core.arrays.string_ import StringArray, StringDtype

        dtype = pandas_dtype(dtype)

        # if the dtype is exactly the same, we can fastpath
        if self.dtype == dtype:
            # return the same object for copy=False
            return self.copy() if copy else self
        # if we are astyping to another nullable masked dtype, we can fastpath
        if isinstance(dtype, BaseMaskedDtype):
            # TODO deal with NaNs
            data = self._data.astype(dtype.numpy_dtype, copy=copy)
            # mask is copied depending on whether the data was copied, and
            # not directly depending on the `copy` keyword
            mask = self._mask if data is self._data else self._mask.copy()
            return dtype.construct_array_type()(data, mask, copy=False)
        elif isinstance(dtype, StringDtype):
            return StringArray._from_sequence(self, copy=False)

        # coerce
        if is_float_dtype(dtype):
            # In astype, we consider dtype=float to also mean na_value=np.nan
            kwargs = dict(na_value=np.nan)
        elif is_datetime64_dtype(dtype):
            kwargs = dict(na_value=np.datetime64("NaT"))
        else:
            kwargs = {}

        data = self.to_numpy(dtype=dtype, **kwargs)
        return astype_nansafe(data, dtype, copy=False)

    def _values_for_argsort(self) -> np.ndarray:
        return self._data

    @classmethod
    def _create_comparison_method(cls, op):
        op_name = op.__name__

        @unpack_zerodim_and_defer(op.__name__)
        def cmp_method(self, other):
            from pandas.arrays import BooleanArray, IntegerArray

            mask = None

            if isinstance(other, (BooleanArray, IntegerArray, FloatingArray)):
                other, mask = other._data, other._mask

            elif is_list_like(other):
                other = np.asarray(other)
                if other.ndim > 1:
                    raise NotImplementedError(
                        "can only perform ops with 1-d structures"
                    )

            if other is libmissing.NA:
                # numpy does not handle pd.NA well as "other" scalar (it returns
                # a scalar False instead of an array)
                # This may be fixed by NA.__array_ufunc__. Revisit this check
                # once that's implemented.
                result = np.zeros(self._data.shape, dtype="bool")
                mask = np.ones(self._data.shape, dtype="bool")
            else:
                with warnings.catch_warnings():
                    # numpy may show a FutureWarning:
                    #     elementwise comparison failed; returning scalar instead,
                    #     but in the future will perform elementwise comparison
                    # before returning NotImplemented. We fall back to the correct
                    # behavior today, so that should be fine to ignore.
                    warnings.filterwarnings("ignore", "elementwise", FutureWarning)
                    with np.errstate(all="ignore"):
                        method = getattr(self._data, f"__{op_name}__")
                        result = method(other)

                    if result is NotImplemented:
                        result = invalid_comparison(self._data, other, op)

            # nans propagate
            if mask is None:
                mask = self._mask.copy()
            else:
                mask = self._mask | mask

            return BooleanArray(result, mask)

        name = f"__{op.__name__}__"
        return set_function_name(cmp_method, name, cls)

    def _reduce(self, name: str, skipna: bool = True, **kwargs):
        data = self._data
        mask = self._mask

        if name in {"sum", "prod", "min", "max"}:
            op = getattr(masked_reductions, name)
            return op(data, mask, skipna=skipna, **kwargs)

        # coerce to a nan-aware float if needed
        # (we explicitly use NaN within reductions)
        if self._hasna:
            data = self.to_numpy("float64", na_value=np.nan)

        op = getattr(nanops, "nan" + name)
        result = op(data, axis=0, skipna=skipna, mask=mask, **kwargs)

        if np.isnan(result):
            return libmissing.NA

        return result

    def sum(self, skipna=True, min_count=0, **kwargs):
        nv.validate_sum((), kwargs)
        result = masked_reductions.sum(
            values=self._data, mask=self._mask, skipna=skipna, min_count=min_count
        )
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
        # TODO are there cases we don't end up with float?
        # if we have a float operand we are by-definition
        # a float result
        # or our op is a divide
        # if (is_float_dtype(other) or is_float(other)) or (
        #     op_name in ["rtruediv", "truediv"]
        # ):
        #     result[mask] = np.nan
        #     return result

        return type(self)(result, mask, copy=False)

    @classmethod
    def _create_arithmetic_method(cls, op):
        op_name = op.__name__

        @unpack_zerodim_and_defer(op.__name__)
        def floating_arithmetic_method(self, other):
            from pandas.arrays import IntegerArray

            omask = None

            if getattr(other, "ndim", 0) > 1:
                raise NotImplementedError("can only perform ops with 1-d structures")

            if isinstance(other, (IntegerArray, FloatingArray)):
                other, omask = other._data, other._mask

            elif is_list_like(other):
                other = np.asarray(other)
                if other.ndim > 1:
                    raise NotImplementedError(
                        "can only perform ops with 1-d structures"
                    )
                if len(self) != len(other):
                    raise ValueError("Lengths must match")
                if not (is_float_dtype(other) or is_integer_dtype(other)):
                    raise TypeError("can only perform ops with numeric values")

            else:
                if not (is_float(other) or is_integer(other) or other is libmissing.NA):
                    raise TypeError("can only perform ops with numeric values")

            if omask is None:
                mask = self._mask.copy()
                if other is libmissing.NA:
                    mask |= True
            else:
                mask = self._mask | omask

            if op_name == "pow":
                # 1 ** x is 1.
                mask = np.where((self._data == 1) & ~self._mask, False, mask)
                # x ** 0 is 1.
                if omask is not None:
                    mask = np.where((other == 0) & ~omask, False, mask)
                elif other is not libmissing.NA:
                    mask = np.where(other == 0, False, mask)

            elif op_name == "rpow":
                # 1 ** x is 1.
                if omask is not None:
                    mask = np.where((other == 1) & ~omask, False, mask)
                elif other is not libmissing.NA:
                    mask = np.where(other == 1, False, mask)
                # x ** 0 is 1.
                mask = np.where((self._data == 0) & ~self._mask, False, mask)

            if other is libmissing.NA:
                result = np.ones_like(self._data)
            else:
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

        name = f"__{op.__name__}__"
        return set_function_name(floating_arithmetic_method, name, cls)


FloatingArray._add_arithmetic_ops()
FloatingArray._add_comparison_ops()


_dtype_docstring = """
An ExtensionDtype for {dtype} data.

This dtype uses ``pd.NA`` as missing value indicator.

Attributes
----------
None

Methods
-------
None
"""

# create the Dtype


@register_extension_dtype
class Float32Dtype(FloatingDtype):
    type = np.float32
    name = "Float32"
    __doc__ = _dtype_docstring.format(dtype="float32")


@register_extension_dtype
class Float64Dtype(FloatingDtype):
    type = np.float64
    name = "Float64"
    __doc__ = _dtype_docstring.format(dtype="float64")


FLOAT_STR_TO_DTYPE = {
    "float32": Float32Dtype(),
    "float64": Float64Dtype(),
}
