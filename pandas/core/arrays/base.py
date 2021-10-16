"""
An interface for extending pandas with custom arrays.

.. warning::

   This is an experimental API and subject to breaking changes
   without warning.
"""
from __future__ import annotations

import operator
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Iterator,
    Literal,
    Sequence,
    TypeVar,
    cast,
    overload,
)

import numpy as np

from pandas._libs import lib
from pandas._typing import (
    ArrayLike,
    AstypeArg,
    Dtype,
    FillnaOptions,
    PositionalIndexer,
    ScalarIndexer,
    SequenceIndexer,
    Shape,
    TakeIndexer,
    npt,
)
from pandas.compat import set_function_name
from pandas.compat.numpy import function as nv
from pandas.errors import AbstractMethodError
from pandas.util._decorators import (
    Appender,
    Substitution,
    cache_readonly,
)
from pandas.util._validators import (
    validate_bool_kwarg,
    validate_fillna_kwargs,
)

from pandas.core.dtypes.cast import maybe_cast_to_extension_array
from pandas.core.dtypes.common import (
    is_dtype_equal,
    is_list_like,
    is_scalar,
    pandas_dtype,
)
from pandas.core.dtypes.dtypes import ExtensionDtype
from pandas.core.dtypes.generic import (
    ABCDataFrame,
    ABCIndex,
    ABCSeries,
)
from pandas.core.dtypes.missing import isna

from pandas.core import (
    arraylike,
    missing,
    ops,
)
from pandas.core.algorithms import (
    factorize_array,
    isin,
    unique,
)
from pandas.core.sorting import (
    nargminmax,
    nargsort,
)

if TYPE_CHECKING:

    class ExtensionArraySupportsAnyAll("ExtensionArray"):
        def any(self, *, skipna: bool = True) -> bool:
            pass

        def all(self, *, skipna: bool = True) -> bool:
            pass

    from pandas._typing import (
        NumpySorter,
        NumpyValueArrayLike,
    )


_extension_array_shared_docs: dict[str, str] = {}

ExtensionArrayT = TypeVar("ExtensionArrayT", bound="ExtensionArray")


class ExtensionArray:
    """
    Abstract base class for custom 1-D array types.

    pandas will recognize instances of this class as proper arrays
    with a custom type and will not attempt to coerce them to objects. They
    may be stored directly inside a :class:`DataFrame` or :class:`Series`.

    Attributes
    ----------
    dtype
    nbytes
    ndim
    shape

    Methods
    -------
    argsort
    astype
    copy
    dropna
    factorize
    fillna
    equals
    isin
    isna
    ravel
    repeat
    searchsorted
    shift
    take
    tolist
    unique
    view
    _concat_same_type
    _formatter
    _from_factorized
    _from_sequence
    _from_sequence_of_strings
    _reduce
    _values_for_argsort
    _values_for_factorize

    Notes
    -----
    The interface includes the following abstract methods that must be
    implemented by subclasses:

    * _from_sequence
    * _from_factorized
    * __getitem__
    * __len__
    * __eq__
    * dtype
    * nbytes
    * isna
    * take
    * copy
    * _concat_same_type

    A default repr displaying the type, (truncated) data, length,
    and dtype is provided. It can be customized or replaced by
    by overriding:

    * __repr__ : A default repr for the ExtensionArray.
    * _formatter : Print scalars inside a Series or DataFrame.

    Some methods require casting the ExtensionArray to an ndarray of Python
    objects with ``self.astype(object)``, which may be expensive. When
    performance is a concern, we highly recommend overriding the following
    methods:

    * fillna
    * dropna
    * unique
    * factorize / _values_for_factorize
    * argsort / _values_for_argsort
    * searchsorted

    The remaining methods implemented on this class should be performant,
    as they only compose abstract methods. Still, a more efficient
    implementation may be available, and these methods can be overridden.

    One can implement methods to handle array reductions.

    * _reduce

    One can implement methods to handle parsing from strings that will be used
    in methods such as ``pandas.io.parsers.read_csv``.

    * _from_sequence_of_strings

    This class does not inherit from 'abc.ABCMeta' for performance reasons.
    Methods and properties required by the interface raise
    ``pandas.errors.AbstractMethodError`` and no ``register`` method is
    provided for registering virtual subclasses.

    ExtensionArrays are limited to 1 dimension.

    They may be backed by none, one, or many NumPy arrays. For example,
    ``pandas.Categorical`` is an extension array backed by two arrays,
    one for codes and one for categories. An array of IPv6 address may
    be backed by a NumPy structured array with two fields, one for the
    lower 64 bits and one for the upper 64 bits. Or they may be backed
    by some other storage type, like Python lists. Pandas makes no
    assumptions on how the data are stored, just that it can be converted
    to a NumPy array.
    The ExtensionArray interface does not impose any rules on how this data
    is stored. However, currently, the backing data cannot be stored in
    attributes called ``.values`` or ``._values`` to ensure full compatibility
    with pandas internals. But other names as ``.data``, ``._data``,
    ``._items``, ... can be freely used.

    If implementing NumPy's ``__array_ufunc__`` interface, pandas expects
    that

    1. You defer by returning ``NotImplemented`` when any Series are present
       in `inputs`. Pandas will extract the arrays and call the ufunc again.
    2. You define a ``_HANDLED_TYPES`` tuple as an attribute on the class.
       Pandas inspect this to determine whether the ufunc is valid for the
       types present.

    See :ref:`extending.extension.ufunc` for more.

    By default, ExtensionArrays are not hashable.  Immutable subclasses may
    override this behavior.
    """

    # '_typ' is for pandas.core.dtypes.generic.ABCExtensionArray.
    # Don't override this.
    _typ = "extension"

    # ------------------------------------------------------------------------
    # Constructors
    # ------------------------------------------------------------------------

    @classmethod
    def _from_sequence(cls, scalars, *, dtype: Dtype | None = None, copy=False):
        """
        Construct a new ExtensionArray from a sequence of scalars.

        Parameters
        ----------
        scalars : Sequence
            Each element will be an instance of the scalar type for this
            array, ``cls.dtype.type`` or be converted into this type in this method.
        dtype : dtype, optional
            Construct for this particular dtype. This should be a Dtype
            compatible with the ExtensionArray.
        copy : bool, default False
            If True, copy the underlying data.

        Returns
        -------
        ExtensionArray
        """
        raise AbstractMethodError(cls)

    @classmethod
    def _from_sequence_of_strings(
        cls, strings, *, dtype: Dtype | None = None, copy=False
    ):
        """
        Construct a new ExtensionArray from a sequence of strings.

        Parameters
        ----------
        strings : Sequence
            Each element will be an instance of the scalar type for this
            array, ``cls.dtype.type``.
        dtype : dtype, optional
            Construct for this particular dtype. This should be a Dtype
            compatible with the ExtensionArray.
        copy : bool, default False
            If True, copy the underlying data.

        Returns
        -------
        ExtensionArray
        """
        raise AbstractMethodError(cls)

    @classmethod
    def _from_factorized(cls, values, original):
        """
        Reconstruct an ExtensionArray after factorization.

        Parameters
        ----------
        values : ndarray
            An integer ndarray with the factorized values.
        original : ExtensionArray
            The original ExtensionArray that factorize was called on.

        See Also
        --------
        factorize : Top-level factorize method that dispatches here.
        ExtensionArray.factorize : Encode the extension array as an enumerated type.
        """
        raise AbstractMethodError(cls)

    # ------------------------------------------------------------------------
    # Must be a Sequence
    # ------------------------------------------------------------------------
    @overload
    def __getitem__(self, item: ScalarIndexer) -> Any:
        ...

    @overload
    def __getitem__(self: ExtensionArrayT, item: SequenceIndexer) -> ExtensionArrayT:
        ...

    def __getitem__(
        self: ExtensionArrayT, item: PositionalIndexer
    ) -> ExtensionArrayT | Any:
        """
        Select a subset of self.

        Parameters
        ----------
        item : int, slice, or ndarray
            * int: The position in 'self' to get.

            * slice: A slice object, where 'start', 'stop', and 'step' are
              integers or None

            * ndarray: A 1-d boolean NumPy ndarray the same length as 'self'

            * list[int]:  A list of int

        Returns
        -------
        item : scalar or ExtensionArray

        Notes
        -----
        For scalar ``item``, return a scalar value suitable for the array's
        type. This should be an instance of ``self.dtype.type``.

        For slice ``key``, return an instance of ``ExtensionArray``, even
        if the slice is length 0 or 1.

        For a boolean mask, return an instance of ``ExtensionArray``, filtered
        to the values where ``item`` is True.
        """
        raise AbstractMethodError(self)

    def __setitem__(self, key: int | slice | np.ndarray, value: Any) -> None:
        """
        Set one or more values inplace.

        This method is not required to satisfy the pandas extension array
        interface.

        Parameters
        ----------
        key : int, ndarray, or slice
            When called from, e.g. ``Series.__setitem__``, ``key`` will be
            one of

            * scalar int
            * ndarray of integers.
            * boolean ndarray
            * slice object

        value : ExtensionDtype.type, Sequence[ExtensionDtype.type], or object
            value or values to be set of ``key``.

        Returns
        -------
        None
        """
        # Some notes to the ExtensionArray implementor who may have ended up
        # here. While this method is not required for the interface, if you
        # *do* choose to implement __setitem__, then some semantics should be
        # observed:
        #
        # * Setting multiple values : ExtensionArrays should support setting
        #   multiple values at once, 'key' will be a sequence of integers and
        #  'value' will be a same-length sequence.
        #
        # * Broadcasting : For a sequence 'key' and a scalar 'value',
        #   each position in 'key' should be set to 'value'.
        #
        # * Coercion : Most users will expect basic coercion to work. For
        #   example, a string like '2018-01-01' is coerced to a datetime
        #   when setting on a datetime64ns array. In general, if the
        #   __init__ method coerces that value, then so should __setitem__
        # Note, also, that Series/DataFrame.where internally use __setitem__
        # on a copy of the data.
        raise NotImplementedError(f"{type(self)} does not implement __setitem__.")

    def __len__(self) -> int:
        """
        Length of this array

        Returns
        -------
        length : int
        """
        raise AbstractMethodError(self)

    def __iter__(self) -> Iterator[Any]:
        """
        Iterate over elements of the array.
        """
        # This needs to be implemented so that pandas recognizes extension
        # arrays as list-like. The default implementation makes successive
        # calls to ``__getitem__``, which may be slower than necessary.
        for i in range(len(self)):
            yield self[i]

    def __contains__(self, item: object) -> bool | np.bool_:
        """
        Return for `item in self`.
        """
        # GH37867
        # comparisons of any item to pd.NA always return pd.NA, so e.g. "a" in [pd.NA]
        # would raise a TypeError. The implementation below works around that.
        if is_scalar(item) and isna(item):
            if not self._can_hold_na:
                return False
            elif item is self.dtype.na_value or isinstance(item, self.dtype.type):
                return self.isna().any()
            else:
                return False
        else:
            # error: Item "ExtensionArray" of "Union[ExtensionArray, ndarray]" has no
            # attribute "any"
            return (item == self).any()  # type: ignore[union-attr]

    # error: Signature of "__eq__" incompatible with supertype "object"
    def __eq__(self, other: Any) -> ArrayLike:  # type: ignore[override]
        """
        Return for `self == other` (element-wise equality).
        """
        # Implementer note: this should return a boolean numpy ndarray or
        # a boolean ExtensionArray.
        # When `other` is one of Series, Index, or DataFrame, this method should
        # return NotImplemented (to ensure that those objects are responsible for
        # first unpacking the arrays, and then dispatch the operation to the
        # underlying arrays)
        raise AbstractMethodError(self)

    # error: Signature of "__ne__" incompatible with supertype "object"
    def __ne__(self, other: Any) -> ArrayLike:  # type: ignore[override]
        """
        Return for `self != other` (element-wise in-equality).
        """
        return ~(self == other)

    def to_numpy(
        self,
        dtype: npt.DTypeLike | None = None,
        copy: bool = False,
        na_value=lib.no_default,
    ) -> np.ndarray:
        """
        Convert to a NumPy ndarray.

        .. versionadded:: 1.0.0

        This is similar to :meth:`numpy.asarray`, but may provide additional control
        over how the conversion is done.

        Parameters
        ----------
        dtype : str or numpy.dtype, optional
            The dtype to pass to :meth:`numpy.asarray`.
        copy : bool, default False
            Whether to ensure that the returned value is a not a view on
            another array. Note that ``copy=False`` does not *ensure* that
            ``to_numpy()`` is no-copy. Rather, ``copy=True`` ensure that
            a copy is made, even if not strictly necessary.
        na_value : Any, optional
            The value to use for missing values. The default value depends
            on `dtype` and the type of the array.

        Returns
        -------
        numpy.ndarray
        """
        result = np.asarray(self, dtype=dtype)
        if copy or na_value is not lib.no_default:
            result = result.copy()
        if na_value is not lib.no_default:
            result[self.isna()] = na_value
        return result

    # ------------------------------------------------------------------------
    # Required attributes
    # ------------------------------------------------------------------------

    @property
    def dtype(self) -> ExtensionDtype:
        """
        An instance of 'ExtensionDtype'.
        """
        raise AbstractMethodError(self)

    @property
    def shape(self) -> Shape:
        """
        Return a tuple of the array dimensions.
        """
        return (len(self),)

    @property
    def size(self) -> int:
        """
        The number of elements in the array.
        """
        return np.prod(self.shape)

    @property
    def ndim(self) -> int:
        """
        Extension Arrays are only allowed to be 1-dimensional.
        """
        return 1

    @property
    def nbytes(self) -> int:
        """
        The number of bytes needed to store this object in memory.
        """
        # If this is expensive to compute, return an approximate lower bound
        # on the number of bytes needed.
        raise AbstractMethodError(self)

    # ------------------------------------------------------------------------
    # Additional Methods
    # ------------------------------------------------------------------------

    @overload
    def astype(self, dtype: npt.DTypeLike, copy: bool = ...) -> np.ndarray:
        ...

    @overload
    def astype(self, dtype: ExtensionDtype, copy: bool = ...) -> ExtensionArray:
        ...

    @overload
    def astype(self, dtype: AstypeArg, copy: bool = ...) -> ArrayLike:
        ...

    def astype(self, dtype: AstypeArg, copy: bool = True) -> ArrayLike:
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
        array : np.ndarray or ExtensionArray
            An ExtensionArray if dtype is StringDtype,
            or same as that of underlying array.
            Otherwise a NumPy ndarray with 'dtype' for its dtype.
        """
        from pandas.core.arrays.string_ import StringDtype

        dtype = pandas_dtype(dtype)
        if is_dtype_equal(dtype, self.dtype):
            if not copy:
                return self
            else:
                return self.copy()

        # FIXME: Really hard-code here?
        if isinstance(dtype, StringDtype):
            # allow conversion to StringArrays
            return dtype.construct_array_type()._from_sequence(self, copy=False)

        # error: Argument "dtype" to "array" has incompatible type
        # "Union[ExtensionDtype, dtype[Any]]"; expected "Union[dtype[Any], None, type,
        # _SupportsDType, str, Union[Tuple[Any, int], Tuple[Any, Union[int,
        # Sequence[int]]], List[Any], _DTypeDict, Tuple[Any, Any]]]"
        return np.array(self, dtype=dtype, copy=copy)  # type: ignore[arg-type]

    def isna(self) -> np.ndarray | ExtensionArraySupportsAnyAll:
        """
        A 1-D array indicating if each value is missing.

        Returns
        -------
        na_values : Union[np.ndarray, ExtensionArray]
            In most cases, this should return a NumPy ndarray. For
            exceptional cases like ``SparseArray``, where returning
            an ndarray would be expensive, an ExtensionArray may be
            returned.

        Notes
        -----
        If returning an ExtensionArray, then

        * ``na_values._is_boolean`` should be True
        * `na_values` should implement :func:`ExtensionArray._reduce`
        * ``na_values.any`` and ``na_values.all`` should be implemented
        """
        raise AbstractMethodError(self)

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
        ExtensionArray.argsort : Return the indices that would sort this array.
        """
        # Note: this is used in `ExtensionArray.argsort`.
        return np.array(self)

    def argsort(
        self,
        ascending: bool = True,
        kind: str = "quicksort",
        na_position: str = "last",
        *args,
        **kwargs,
    ) -> np.ndarray:
        """
        Return the indices that would sort this array.

        Parameters
        ----------
        ascending : bool, default True
            Whether the indices should result in an ascending
            or descending sort.
        kind : {'quicksort', 'mergesort', 'heapsort', 'stable'}, optional
            Sorting algorithm.
        *args, **kwargs:
            Passed through to :func:`numpy.argsort`.

        Returns
        -------
        np.ndarray[np.intp]
            Array of indices that sort ``self``. If NaN values are contained,
            NaN values are placed at the end.

        See Also
        --------
        numpy.argsort : Sorting implementation used internally.
        """
        # Implementor note: You have two places to override the behavior of
        # argsort.
        # 1. _values_for_argsort : construct the values passed to np.argsort
        # 2. argsort : total control over sorting.
        ascending = nv.validate_argsort_with_ascending(ascending, args, kwargs)

        values = self._values_for_argsort()
        return nargsort(
            values,
            kind=kind,
            ascending=ascending,
            na_position=na_position,
            mask=np.asarray(self.isna()),
        )

    def argmin(self, skipna: bool = True) -> int:
        """
        Return the index of minimum value.

        In case of multiple occurrences of the minimum value, the index
        corresponding to the first occurrence is returned.

        Parameters
        ----------
        skipna : bool, default True

        Returns
        -------
        int

        See Also
        --------
        ExtensionArray.argmax
        """
        validate_bool_kwarg(skipna, "skipna")
        if not skipna and self.isna().any():
            raise NotImplementedError
        return nargminmax(self, "argmin")

    def argmax(self, skipna: bool = True) -> int:
        """
        Return the index of maximum value.

        In case of multiple occurrences of the maximum value, the index
        corresponding to the first occurrence is returned.

        Parameters
        ----------
        skipna : bool, default True

        Returns
        -------
        int

        See Also
        --------
        ExtensionArray.argmin
        """
        validate_bool_kwarg(skipna, "skipna")
        if not skipna and self.isna().any():
            raise NotImplementedError
        return nargminmax(self, "argmax")

    def fillna(
        self,
        value: object | ArrayLike | None = None,
        method: FillnaOptions | None = None,
        limit: int | None = None,
    ):
        """
        Fill NA/NaN values using the specified method.

        Parameters
        ----------
        value : scalar, array-like
            If a scalar value is passed it is used to fill all missing values.
            Alternatively, an array-like 'value' can be given. It's expected
            that the array-like have the same length as 'self'.
        method : {'backfill', 'bfill', 'pad', 'ffill', None}, default None
            Method to use for filling holes in reindexed Series
            pad / ffill: propagate last valid observation forward to next valid
            backfill / bfill: use NEXT valid observation to fill gap.
        limit : int, default None
            If method is specified, this is the maximum number of consecutive
            NaN values to forward/backward fill. In other words, if there is
            a gap with more than this number of consecutive NaNs, it will only
            be partially filled. If method is not specified, this is the
            maximum number of entries along the entire axis where NaNs will be
            filled.

        Returns
        -------
        ExtensionArray
            With NA/NaN filled.
        """
        value, method = validate_fillna_kwargs(value, method)

        mask = self.isna()
        # error: Argument 2 to "check_value_size" has incompatible type
        # "ExtensionArray"; expected "ndarray"
        value = missing.check_value_size(
            value, mask, len(self)  # type: ignore[arg-type]
        )

        if mask.any():
            if method is not None:
                func = missing.get_fill_func(method)
                new_values, _ = func(self.astype(object), limit=limit, mask=mask)
                new_values = self._from_sequence(new_values, dtype=self.dtype)
            else:
                # fill with value
                new_values = self.copy()
                new_values[mask] = value
        else:
            new_values = self.copy()
        return new_values

    def dropna(self: ExtensionArrayT) -> ExtensionArrayT:
        """
        Return ExtensionArray without NA values.

        Returns
        -------
        valid : ExtensionArray
        """
        # error: Unsupported operand type for ~ ("ExtensionArray")
        return self[~self.isna()]  # type: ignore[operator]

    def shift(self, periods: int = 1, fill_value: object = None) -> ExtensionArray:
        """
        Shift values by desired number.

        Newly introduced missing values are filled with
        ``self.dtype.na_value``.

        Parameters
        ----------
        periods : int, default 1
            The number of periods to shift. Negative values are allowed
            for shifting backwards.

        fill_value : object, optional
            The scalar value to use for newly introduced missing values.
            The default is ``self.dtype.na_value``.

        Returns
        -------
        ExtensionArray
            Shifted.

        Notes
        -----
        If ``self`` is empty or ``periods`` is 0, a copy of ``self`` is
        returned.

        If ``periods > len(self)``, then an array of size
        len(self) is returned, with all values filled with
        ``self.dtype.na_value``.
        """
        # Note: this implementation assumes that `self.dtype.na_value` can be
        # stored in an instance of your ExtensionArray with `self.dtype`.
        if not len(self) or periods == 0:
            return self.copy()

        if isna(fill_value):
            fill_value = self.dtype.na_value

        empty = self._from_sequence(
            [fill_value] * min(abs(periods), len(self)), dtype=self.dtype
        )
        if periods > 0:
            a = empty
            b = self[:-periods]
        else:
            a = self[abs(periods) :]
            b = empty
        return self._concat_same_type([a, b])

    def unique(self: ExtensionArrayT) -> ExtensionArrayT:
        """
        Compute the ExtensionArray of unique values.

        Returns
        -------
        uniques : ExtensionArray
        """
        uniques = unique(self.astype(object))
        return self._from_sequence(uniques, dtype=self.dtype)

    def searchsorted(
        self,
        value: NumpyValueArrayLike | ExtensionArray,
        side: Literal["left", "right"] = "left",
        sorter: NumpySorter = None,
    ) -> npt.NDArray[np.intp] | np.intp:
        """
        Find indices where elements should be inserted to maintain order.

        Find the indices into a sorted array `self` (a) such that, if the
        corresponding elements in `value` were inserted before the indices,
        the order of `self` would be preserved.

        Assuming that `self` is sorted:

        ======  ================================
        `side`  returned index `i` satisfies
        ======  ================================
        left    ``self[i-1] < value <= self[i]``
        right   ``self[i-1] <= value < self[i]``
        ======  ================================

        Parameters
        ----------
        value : array-like, list or scalar
            Value(s) to insert into `self`.
        side : {'left', 'right'}, optional
            If 'left', the index of the first suitable location found is given.
            If 'right', return the last such index.  If there is no suitable
            index, return either 0 or N (where N is the length of `self`).
        sorter : 1-D array-like, optional
            Optional array of integer indices that sort array a into ascending
            order. They are typically the result of argsort.

        Returns
        -------
        array of ints or int
            If value is array-like, array of insertion points.
            If value is scalar, a single integer.

        See Also
        --------
        numpy.searchsorted : Similar method from NumPy.
        """
        # Note: the base tests provided by pandas only test the basics.
        # We do not test
        # 1. Values outside the range of the `data_for_sorting` fixture
        # 2. Values between the values in the `data_for_sorting` fixture
        # 3. Missing values.
        arr = self.astype(object)
        if isinstance(value, ExtensionArray):
            value = value.astype(object)
        return arr.searchsorted(value, side=side, sorter=sorter)

    def equals(self, other: object) -> bool:
        """
        Return if another array is equivalent to this array.

        Equivalent means that both arrays have the same shape and dtype, and
        all values compare equal. Missing values in the same location are
        considered equal (in contrast with normal equality).

        Parameters
        ----------
        other : ExtensionArray
            Array to compare to this Array.

        Returns
        -------
        boolean
            Whether the arrays are equivalent.
        """
        if type(self) != type(other):
            return False
        other = cast(ExtensionArray, other)
        if not is_dtype_equal(self.dtype, other.dtype):
            return False
        elif len(self) != len(other):
            return False
        else:
            equal_values = self == other
            if isinstance(equal_values, ExtensionArray):
                # boolean array with NA -> fill with False
                equal_values = equal_values.fillna(False)
            # error: Unsupported left operand type for & ("ExtensionArray")
            equal_na = self.isna() & other.isna()  # type: ignore[operator]
            return bool((equal_values | equal_na).all())

    def isin(self, values) -> np.ndarray:
        """
        Pointwise comparison for set containment in the given values.

        Roughly equivalent to `np.array([x in values for x in self])`

        Parameters
        ----------
        values : Sequence

        Returns
        -------
        np.ndarray[bool]
        """
        return isin(np.asarray(self), values)

    def _values_for_factorize(self) -> tuple[np.ndarray, Any]:
        """
        Return an array and missing value suitable for factorization.

        Returns
        -------
        values : ndarray

            An array suitable for factorization. This should maintain order
            and be a supported dtype (Float64, Int64, UInt64, String, Object).
            By default, the extension array is cast to object dtype.
        na_value : object
            The value in `values` to consider missing. This will be treated
            as NA in the factorization routines, so it will be coded as
            `na_sentinel` and not included in `uniques`. By default,
            ``np.nan`` is used.

        Notes
        -----
        The values returned by this method are also used in
        :func:`pandas.util.hash_pandas_object`.
        """
        return self.astype(object), np.nan

    def factorize(self, na_sentinel: int = -1) -> tuple[np.ndarray, ExtensionArray]:
        """
        Encode the extension array as an enumerated type.

        Parameters
        ----------
        na_sentinel : int, default -1
            Value to use in the `codes` array to indicate missing values.

        Returns
        -------
        codes : ndarray
            An integer NumPy array that's an indexer into the original
            ExtensionArray.
        uniques : ExtensionArray
            An ExtensionArray containing the unique values of `self`.

            .. note::

               uniques will *not* contain an entry for the NA value of
               the ExtensionArray if there are any missing values present
               in `self`.

        See Also
        --------
        factorize : Top-level factorize method that dispatches here.

        Notes
        -----
        :meth:`pandas.factorize` offers a `sort` keyword as well.
        """
        # Implementer note: There are two ways to override the behavior of
        # pandas.factorize
        # 1. _values_for_factorize and _from_factorize.
        #    Specify the values passed to pandas' internal factorization
        #    routines, and how to convert from those values back to the
        #    original ExtensionArray.
        # 2. ExtensionArray.factorize.
        #    Complete control over factorization.
        arr, na_value = self._values_for_factorize()

        codes, uniques = factorize_array(
            arr, na_sentinel=na_sentinel, na_value=na_value
        )

        uniques = self._from_factorized(uniques, self)
        # error: Incompatible return value type (got "Tuple[ndarray, ndarray]",
        # expected "Tuple[ndarray, ExtensionArray]")
        return codes, uniques  # type: ignore[return-value]

    _extension_array_shared_docs[
        "repeat"
    ] = """
        Repeat elements of a %(klass)s.

        Returns a new %(klass)s where each element of the current %(klass)s
        is repeated consecutively a given number of times.

        Parameters
        ----------
        repeats : int or array of ints
            The number of repetitions for each element. This should be a
            non-negative integer. Repeating 0 times will return an empty
            %(klass)s.
        axis : None
            Must be ``None``. Has no effect but is accepted for compatibility
            with numpy.

        Returns
        -------
        repeated_array : %(klass)s
            Newly created %(klass)s with repeated elements.

        See Also
        --------
        Series.repeat : Equivalent function for Series.
        Index.repeat : Equivalent function for Index.
        numpy.repeat : Similar method for :class:`numpy.ndarray`.
        ExtensionArray.take : Take arbitrary positions.

        Examples
        --------
        >>> cat = pd.Categorical(['a', 'b', 'c'])
        >>> cat
        ['a', 'b', 'c']
        Categories (3, object): ['a', 'b', 'c']
        >>> cat.repeat(2)
        ['a', 'a', 'b', 'b', 'c', 'c']
        Categories (3, object): ['a', 'b', 'c']
        >>> cat.repeat([1, 2, 3])
        ['a', 'b', 'b', 'c', 'c', 'c']
        Categories (3, object): ['a', 'b', 'c']
        """

    @Substitution(klass="ExtensionArray")
    @Appender(_extension_array_shared_docs["repeat"])
    def repeat(self, repeats: int | Sequence[int], axis: int | None = None):
        nv.validate_repeat((), {"axis": axis})
        ind = np.arange(len(self)).repeat(repeats)
        return self.take(ind)

    # ------------------------------------------------------------------------
    # Indexing methods
    # ------------------------------------------------------------------------

    def take(
        self: ExtensionArrayT,
        indices: TakeIndexer,
        *,
        allow_fill: bool = False,
        fill_value: Any = None,
    ) -> ExtensionArrayT:
        """
        Take elements from an array.

        Parameters
        ----------
        indices : sequence of int or one-dimensional np.ndarray of int
            Indices to be taken.
        allow_fill : bool, default False
            How to handle negative values in `indices`.

            * False: negative values in `indices` indicate positional indices
              from the right (the default). This is similar to
              :func:`numpy.take`.

            * True: negative values in `indices` indicate
              missing values. These values are set to `fill_value`. Any other
              other negative values raise a ``ValueError``.

        fill_value : any, optional
            Fill value to use for NA-indices when `allow_fill` is True.
            This may be ``None``, in which case the default NA value for
            the type, ``self.dtype.na_value``, is used.

            For many ExtensionArrays, there will be two representations of
            `fill_value`: a user-facing "boxed" scalar, and a low-level
            physical NA value. `fill_value` should be the user-facing version,
            and the implementation should handle translating that to the
            physical version for processing the take if necessary.

        Returns
        -------
        ExtensionArray

        Raises
        ------
        IndexError
            When the indices are out of bounds for the array.
        ValueError
            When `indices` contains negative values other than ``-1``
            and `allow_fill` is True.

        See Also
        --------
        numpy.take : Take elements from an array along an axis.
        api.extensions.take : Take elements from an array.

        Notes
        -----
        ExtensionArray.take is called by ``Series.__getitem__``, ``.loc``,
        ``iloc``, when `indices` is a sequence of values. Additionally,
        it's called by :meth:`Series.reindex`, or any other method
        that causes realignment, with a `fill_value`.

        Examples
        --------
        Here's an example implementation, which relies on casting the
        extension array to object dtype. This uses the helper method
        :func:`pandas.api.extensions.take`.

        .. code-block:: python

           def take(self, indices, allow_fill=False, fill_value=None):
               from pandas.core.algorithms import take

               # If the ExtensionArray is backed by an ndarray, then
               # just pass that here instead of coercing to object.
               data = self.astype(object)

               if allow_fill and fill_value is None:
                   fill_value = self.dtype.na_value

               # fill value should always be translated from the scalar
               # type for the array, to the physical storage type for
               # the data, before passing to take.

               result = take(data, indices, fill_value=fill_value,
                             allow_fill=allow_fill)
               return self._from_sequence(result, dtype=self.dtype)
        """
        # Implementer note: The `fill_value` parameter should be a user-facing
        # value, an instance of self.dtype.type. When passed `fill_value=None`,
        # the default of `self.dtype.na_value` should be used.
        # This may differ from the physical storage type your ExtensionArray
        # uses. In this case, your implementation is responsible for casting
        # the user-facing type to the storage type, before using
        # pandas.api.extensions.take
        raise AbstractMethodError(self)

    def copy(self: ExtensionArrayT) -> ExtensionArrayT:
        """
        Return a copy of the array.

        Returns
        -------
        ExtensionArray
        """
        raise AbstractMethodError(self)

    def view(self, dtype: Dtype | None = None) -> ArrayLike:
        """
        Return a view on the array.

        Parameters
        ----------
        dtype : str, np.dtype, or ExtensionDtype, optional
            Default None.

        Returns
        -------
        ExtensionArray or np.ndarray
            A view on the :class:`ExtensionArray`'s data.
        """
        # NB:
        # - This must return a *new* object referencing the same data, not self.
        # - The only case that *must* be implemented is with dtype=None,
        #   giving a view with the same dtype as self.
        if dtype is not None:
            raise NotImplementedError(dtype)
        return self[:]

    # ------------------------------------------------------------------------
    # Printing
    # ------------------------------------------------------------------------

    def __repr__(self) -> str:
        if self.ndim > 1:
            return self._repr_2d()

        from pandas.io.formats.printing import format_object_summary

        # the short repr has no trailing newline, while the truncated
        # repr does. So we include a newline in our template, and strip
        # any trailing newlines from format_object_summary
        data = format_object_summary(
            self, self._formatter(), indent_for_name=False
        ).rstrip(", \n")
        class_name = f"<{type(self).__name__}>\n"
        return f"{class_name}{data}\nLength: {len(self)}, dtype: {self.dtype}"

    def _repr_2d(self) -> str:
        from pandas.io.formats.printing import format_object_summary

        # the short repr has no trailing newline, while the truncated
        # repr does. So we include a newline in our template, and strip
        # any trailing newlines from format_object_summary
        lines = [
            format_object_summary(x, self._formatter(), indent_for_name=False).rstrip(
                ", \n"
            )
            for x in self
        ]
        data = ",\n".join(lines)
        class_name = f"<{type(self).__name__}>"
        return f"{class_name}\n[\n{data}\n]\nShape: {self.shape}, dtype: {self.dtype}"

    def _formatter(self, boxed: bool = False) -> Callable[[Any], str | None]:
        """
        Formatting function for scalar values.

        This is used in the default '__repr__'. The returned formatting
        function receives instances of your scalar type.

        Parameters
        ----------
        boxed : bool, default False
            An indicated for whether or not your array is being printed
            within a Series, DataFrame, or Index (True), or just by
            itself (False). This may be useful if you want scalar values
            to appear differently within a Series versus on its own (e.g.
            quoted or not).

        Returns
        -------
        Callable[[Any], str]
            A callable that gets instances of the scalar type and
            returns a string. By default, :func:`repr` is used
            when ``boxed=False`` and :func:`str` is used when
            ``boxed=True``.
        """
        if boxed:
            return str
        return repr

    # ------------------------------------------------------------------------
    # Reshaping
    # ------------------------------------------------------------------------

    def transpose(self, *axes: int) -> ExtensionArray:
        """
        Return a transposed view on this array.

        Because ExtensionArrays are always 1D, this is a no-op.  It is included
        for compatibility with np.ndarray.
        """
        return self[:]

    @property
    def T(self) -> ExtensionArray:
        return self.transpose()

    def ravel(self, order: Literal["C", "F", "A", "K"] | None = "C") -> ExtensionArray:
        """
        Return a flattened view on this array.

        Parameters
        ----------
        order : {None, 'C', 'F', 'A', 'K'}, default 'C'

        Returns
        -------
        ExtensionArray

        Notes
        -----
        - Because ExtensionArrays are 1D-only, this is a no-op.
        - The "order" argument is ignored, is for compatibility with NumPy.
        """
        return self

    @classmethod
    def _concat_same_type(
        cls: type[ExtensionArrayT], to_concat: Sequence[ExtensionArrayT]
    ) -> ExtensionArrayT:
        """
        Concatenate multiple array of this dtype.

        Parameters
        ----------
        to_concat : sequence of this type

        Returns
        -------
        ExtensionArray
        """
        # Implementer note: this method will only be called with a sequence of
        # ExtensionArrays of this class and with the same dtype as self. This
        # should allow "easy" concatenation (no upcasting needed), and result
        # in a new ExtensionArray of the same dtype.
        # Note: this strict behaviour is only guaranteed starting with pandas 1.1
        raise AbstractMethodError(cls)

    # The _can_hold_na attribute is set to True so that pandas internals
    # will use the ExtensionDtype.na_value as the NA value in operations
    # such as take(), reindex(), shift(), etc.  In addition, those results
    # will then be of the ExtensionArray subclass rather than an array
    # of objects
    @cache_readonly
    def _can_hold_na(self) -> bool:
        return self.dtype._can_hold_na

    def _reduce(self, name: str, *, skipna: bool = True, **kwargs):
        """
        Return a scalar result of performing the reduction operation.

        Parameters
        ----------
        name : str
            Name of the function, supported values are:
            { any, all, min, max, sum, mean, median, prod,
            std, var, sem, kurt, skew }.
        skipna : bool, default True
            If True, skip NaN values.
        **kwargs
            Additional keyword arguments passed to the reduction function.
            Currently, `ddof` is the only supported kwarg.

        Returns
        -------
        scalar

        Raises
        ------
        TypeError : subclass does not define reductions
        """
        raise TypeError(f"cannot perform {name} with type {self.dtype}")

    # https://github.com/python/typeshed/issues/2148#issuecomment-520783318
    # Incompatible types in assignment (expression has type "None", base class
    # "object" defined the type as "Callable[[object], int]")
    __hash__: None  # type: ignore[assignment]

    # ------------------------------------------------------------------------
    # Non-Optimized Default Methods

    def tolist(self) -> list:
        """
        Return a list of the values.

        These are each a scalar type, which is a Python scalar
        (for str, int, float) or a pandas scalar
        (for Timestamp/Timedelta/Interval/Period)

        Returns
        -------
        list
        """
        if self.ndim > 1:
            return [x.tolist() for x in self]
        return list(self)

    def delete(self: ExtensionArrayT, loc: PositionalIndexer) -> ExtensionArrayT:
        indexer = np.delete(np.arange(len(self)), loc)
        return self.take(indexer)

    @classmethod
    def _empty(cls, shape: Shape, dtype: ExtensionDtype):
        """
        Create an ExtensionArray with the given shape and dtype.
        """
        obj = cls._from_sequence([], dtype=dtype)

        taker = np.broadcast_to(np.intp(-1), shape)
        result = obj.take(taker, allow_fill=True)
        if not isinstance(result, cls) or dtype != result.dtype:
            raise NotImplementedError(
                f"Default 'empty' implementation is invalid for dtype='{dtype}'"
            )
        return result

    def __array_ufunc__(self, ufunc: np.ufunc, method: str, *inputs, **kwargs):
        if any(
            isinstance(other, (ABCSeries, ABCIndex, ABCDataFrame)) for other in inputs
        ):
            return NotImplemented

        result = arraylike.maybe_dispatch_ufunc_to_dunder_op(
            self, ufunc, method, *inputs, **kwargs
        )
        if result is not NotImplemented:
            return result

        if "out" in kwargs:
            return arraylike.dispatch_ufunc_with_out(
                self, ufunc, method, *inputs, **kwargs
            )

        return arraylike.default_array_ufunc(self, ufunc, method, *inputs, **kwargs)


class ExtensionOpsMixin:
    """
    A base class for linking the operators to their dunder names.

    .. note::

       You may want to set ``__array_priority__`` if you want your
       implementation to be called when involved in binary operations
       with NumPy arrays.
    """

    @classmethod
    def _create_arithmetic_method(cls, op):
        raise AbstractMethodError(cls)

    @classmethod
    def _add_arithmetic_ops(cls):
        setattr(cls, "__add__", cls._create_arithmetic_method(operator.add))
        setattr(cls, "__radd__", cls._create_arithmetic_method(ops.radd))
        setattr(cls, "__sub__", cls._create_arithmetic_method(operator.sub))
        setattr(cls, "__rsub__", cls._create_arithmetic_method(ops.rsub))
        setattr(cls, "__mul__", cls._create_arithmetic_method(operator.mul))
        setattr(cls, "__rmul__", cls._create_arithmetic_method(ops.rmul))
        setattr(cls, "__pow__", cls._create_arithmetic_method(operator.pow))
        setattr(cls, "__rpow__", cls._create_arithmetic_method(ops.rpow))
        setattr(cls, "__mod__", cls._create_arithmetic_method(operator.mod))
        setattr(cls, "__rmod__", cls._create_arithmetic_method(ops.rmod))
        setattr(cls, "__floordiv__", cls._create_arithmetic_method(operator.floordiv))
        setattr(cls, "__rfloordiv__", cls._create_arithmetic_method(ops.rfloordiv))
        setattr(cls, "__truediv__", cls._create_arithmetic_method(operator.truediv))
        setattr(cls, "__rtruediv__", cls._create_arithmetic_method(ops.rtruediv))
        setattr(cls, "__divmod__", cls._create_arithmetic_method(divmod))
        setattr(cls, "__rdivmod__", cls._create_arithmetic_method(ops.rdivmod))

    @classmethod
    def _create_comparison_method(cls, op):
        raise AbstractMethodError(cls)

    @classmethod
    def _add_comparison_ops(cls):
        setattr(cls, "__eq__", cls._create_comparison_method(operator.eq))
        setattr(cls, "__ne__", cls._create_comparison_method(operator.ne))
        setattr(cls, "__lt__", cls._create_comparison_method(operator.lt))
        setattr(cls, "__gt__", cls._create_comparison_method(operator.gt))
        setattr(cls, "__le__", cls._create_comparison_method(operator.le))
        setattr(cls, "__ge__", cls._create_comparison_method(operator.ge))

    @classmethod
    def _create_logical_method(cls, op):
        raise AbstractMethodError(cls)

    @classmethod
    def _add_logical_ops(cls):
        setattr(cls, "__and__", cls._create_logical_method(operator.and_))
        setattr(cls, "__rand__", cls._create_logical_method(ops.rand_))
        setattr(cls, "__or__", cls._create_logical_method(operator.or_))
        setattr(cls, "__ror__", cls._create_logical_method(ops.ror_))
        setattr(cls, "__xor__", cls._create_logical_method(operator.xor))
        setattr(cls, "__rxor__", cls._create_logical_method(ops.rxor))


class ExtensionScalarOpsMixin(ExtensionOpsMixin):
    """
    A mixin for defining  ops on an ExtensionArray.

    It is assumed that the underlying scalar objects have the operators
    already defined.

    Notes
    -----
    If you have defined a subclass MyExtensionArray(ExtensionArray), then
    use MyExtensionArray(ExtensionArray, ExtensionScalarOpsMixin) to
    get the arithmetic operators.  After the definition of MyExtensionArray,
    insert the lines

    MyExtensionArray._add_arithmetic_ops()
    MyExtensionArray._add_comparison_ops()

    to link the operators to your class.

    .. note::

       You may want to set ``__array_priority__`` if you want your
       implementation to be called when involved in binary operations
       with NumPy arrays.
    """

    @classmethod
    def _create_method(cls, op, coerce_to_dtype=True, result_dtype=None):
        """
        A class method that returns a method that will correspond to an
        operator for an ExtensionArray subclass, by dispatching to the
        relevant operator defined on the individual elements of the
        ExtensionArray.

        Parameters
        ----------
        op : function
            An operator that takes arguments op(a, b)
        coerce_to_dtype : bool, default True
            boolean indicating whether to attempt to convert
            the result to the underlying ExtensionArray dtype.
            If it's not possible to create a new ExtensionArray with the
            values, an ndarray is returned instead.

        Returns
        -------
        Callable[[Any, Any], Union[ndarray, ExtensionArray]]
            A method that can be bound to a class. When used, the method
            receives the two arguments, one of which is the instance of
            this class, and should return an ExtensionArray or an ndarray.

            Returning an ndarray may be necessary when the result of the
            `op` cannot be stored in the ExtensionArray. The dtype of the
            ndarray uses NumPy's normal inference rules.

        Examples
        --------
        Given an ExtensionArray subclass called MyExtensionArray, use

            __add__ = cls._create_method(operator.add)

        in the class definition of MyExtensionArray to create the operator
        for addition, that will be based on the operator implementation
        of the underlying elements of the ExtensionArray
        """

        def _binop(self, other):
            def convert_values(param):
                if isinstance(param, ExtensionArray) or is_list_like(param):
                    ovalues = param
                else:  # Assume its an object
                    ovalues = [param] * len(self)
                return ovalues

            if isinstance(other, (ABCSeries, ABCIndex, ABCDataFrame)):
                # rely on pandas to unbox and dispatch to us
                return NotImplemented

            lvalues = self
            rvalues = convert_values(other)

            # If the operator is not defined for the underlying objects,
            # a TypeError should be raised
            res = [op(a, b) for (a, b) in zip(lvalues, rvalues)]

            def _maybe_convert(arr):
                if coerce_to_dtype:
                    # https://github.com/pandas-dev/pandas/issues/22850
                    # We catch all regular exceptions here, and fall back
                    # to an ndarray.
                    res = maybe_cast_to_extension_array(type(self), arr)
                    if not isinstance(res, type(self)):
                        # exception raised in _from_sequence; ensure we have ndarray
                        res = np.asarray(arr)
                else:
                    res = np.asarray(arr, dtype=result_dtype)
                return res

            if op.__name__ in {"divmod", "rdivmod"}:
                a, b = zip(*res)
                return _maybe_convert(a), _maybe_convert(b)

            return _maybe_convert(res)

        op_name = f"__{op.__name__}__"
        return set_function_name(_binop, op_name, cls)

    @classmethod
    def _create_arithmetic_method(cls, op):
        return cls._create_method(op)

    @classmethod
    def _create_comparison_method(cls, op):
        return cls._create_method(op, coerce_to_dtype=False, result_dtype=bool)
