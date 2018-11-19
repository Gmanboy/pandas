# -*- coding: utf-8 -*-
from datetime import datetime, timedelta
import operator
import warnings

import numpy as np

from pandas._libs import lib, iNaT, NaT
from pandas._libs.tslibs import timezones
from pandas._libs.tslibs.timedeltas import delta_to_nanoseconds, Timedelta
from pandas._libs.tslibs.timestamps import maybe_integer_op_deprecated
from pandas._libs.tslibs.period import (
    Period, DIFFERENT_FREQ_INDEX, IncompatibleFrequency)

from pandas.errors import (
    AbstractMethodError, NullFrequencyError, PerformanceWarning)
from pandas import compat

from pandas.tseries import frequencies
from pandas.tseries.offsets import Tick, DateOffset

from pandas.core.dtypes.common import (
    pandas_dtype,
    needs_i8_conversion,
    is_list_like,
    is_offsetlike,
    is_extension_array_dtype,
    is_datetime64_dtype,
    is_datetime64_any_dtype,
    is_datetime64tz_dtype,
    is_float_dtype,
    is_integer_dtype,
    is_bool_dtype,
    is_period_dtype,
    is_timedelta64_dtype,
    is_object_dtype)
from pandas.core.dtypes.generic import ABCSeries, ABCDataFrame, ABCIndexClass
from pandas.core.dtypes.dtypes import DatetimeTZDtype
from pandas.core.dtypes.missing import isna

import pandas.core.common as com
from pandas.core.algorithms import checked_add_with_arr, take, unique1d

from .base import ExtensionOpsMixin
from pandas.util._decorators import deprecate_kwarg


def _make_comparison_op(cls, op):
    # TODO: share code with indexes.base version?  Main difference is that
    # the block for MultiIndex was removed here.
    def cmp_method(self, other):
        if isinstance(other, ABCDataFrame):
            return NotImplemented

        if isinstance(other, (np.ndarray, ABCIndexClass, ABCSeries)):
            if other.ndim > 0 and len(self) != len(other):
                raise ValueError('Lengths must match to compare')

        if needs_i8_conversion(self) and needs_i8_conversion(other):
            # we may need to directly compare underlying
            # representations
            return self._evaluate_compare(other, op)

        # numpy will show a DeprecationWarning on invalid elementwise
        # comparisons, this will raise in the future
        with warnings.catch_warnings(record=True):
            warnings.filterwarnings("ignore", "elementwise", FutureWarning)
            with np.errstate(all='ignore'):
                result = op(self._data, np.asarray(other))

        return result

    name = '__{name}__'.format(name=op.__name__)
    # TODO: docstring?
    return compat.set_function_name(cmp_method, name, cls)


class AttributesMixin(object):

    @property
    def _attributes(self):
        # Inheriting subclass should implement _attributes as a list of strings
        raise AbstractMethodError(self)

    @classmethod
    def _simple_new(cls, values, **kwargs):
        raise AbstractMethodError(cls)

    def _get_attributes_dict(self):
        """return an attributes dict for my class"""
        return {k: getattr(self, k, None) for k in self._attributes}


class DatetimeLikeArrayMixin(ExtensionOpsMixin, AttributesMixin):
    """
    Shared Base/Mixin class for DatetimeArray, TimedeltaArray, PeriodArray

    Assumes that __new__/__init__ defines:
        _data
        _freq

    and that the inheriting class has methods:
        _generate_range
    """

    @property
    def _box_func(self):
        """
        box function to get object from internal representation
        """
        raise AbstractMethodError(self)

    def _box_values(self, values):
        """
        apply box func to passed values
        """
        return lib.map_infer(values, self._box_func)

    def __iter__(self):
        return (self._box_func(v) for v in self.asi8)

    @property
    def asi8(self):
        # do not cache or you'll create a memory leak
        return self._data.view('i8')

    # ----------------------------------------------------------------
    # Array-Like / EA-Interface Methods

    @property
    def nbytes(self):
        return self._data.nbytes

    @property
    def shape(self):
        return (len(self),)

    @property
    def size(self):
        return np.prod(self.shape)

    def __len__(self):
        return len(self._data)

    def __getitem__(self, key):
        """
        This getitem defers to the underlying array, which by-definition can
        only handle list-likes, slices, and integer scalars
        """

        is_int = lib.is_integer(key)
        if lib.is_scalar(key) and not is_int:
            raise IndexError("only integers, slices (`:`), ellipsis (`...`), "
                             "numpy.newaxis (`None`) and integer or boolean "
                             "arrays are valid indices")

        getitem = self._data.__getitem__
        if is_int:
            val = getitem(key)
            return self._box_func(val)

        if com.is_bool_indexer(key):
            key = np.asarray(key, dtype=bool)
            if key.all():
                key = slice(0, None, None)
            else:
                key = lib.maybe_booleans_to_slice(key.view(np.uint8))

        attribs = self._get_attributes_dict()

        is_period = is_period_dtype(self)
        if is_period:
            freq = self.freq
        else:
            freq = None
            if isinstance(key, slice):
                if self.freq is not None and key.step is not None:
                    freq = key.step * self.freq
                else:
                    freq = self.freq

        attribs['freq'] = freq

        result = getitem(key)
        if result.ndim > 1:
            # To support MPL which performs slicing with 2 dim
            # even though it only has 1 dim by definition
            if is_period:
                return self._simple_new(result, **attribs)
            return result

        return self._simple_new(result, **attribs)

    def astype(self, dtype, copy=True):
        if is_object_dtype(dtype):
            return self._box_values(self.asi8)
        return super(DatetimeLikeArrayMixin, self).astype(dtype, copy)

    # ------------------------------------------------------------------
    # ExtensionArray Interface
    # TODO:
    #   * _from_sequence
    #   * argsort / _values_for_argsort
    #   * _reduce

    def unique(self):
        result = unique1d(self.asi8)
        return type(self)(result, dtype=self.dtype)

    def _validate_fill_value(self, fill_value):
        """
        If a fill_value is passed to `take` convert it to an i8 representation,
        raising ValueError if this is not possible.

        Parameters
        ----------
        fill_value : object

        Returns
        -------
        fill_value : np.int64

        Raises
        ------
        ValueError
        """
        raise AbstractMethodError(self)

    def take(self, indices, allow_fill=False, fill_value=None):
        if allow_fill:
            fill_value = self._validate_fill_value(fill_value)

        new_values = take(self.asi8,
                          indices,
                          allow_fill=allow_fill,
                          fill_value=fill_value)

        return type(self)(new_values, dtype=self.dtype)

    @classmethod
    def _concat_same_type(cls, to_concat):
        dtypes = {x.dtype for x in to_concat}
        assert len(dtypes) == 1
        dtype = list(dtypes)[0]

        values = np.concatenate([x.asi8 for x in to_concat])
        return cls(values, dtype=dtype)

    def copy(self, deep=False):
        values = self.asi8.copy()
        return type(self)(values, dtype=self.dtype, freq=self.freq)

    def _values_for_factorize(self):
        return self.asi8, iNaT

    @classmethod
    def _from_factorized(cls, values, original):
        return cls(values, dtype=original.dtype)

    # ------------------------------------------------------------------
    # Null Handling

    def isna(self):
        return self._isnan

    @property  # NB: override with cache_readonly in immutable subclasses
    def _isnan(self):
        """ return if each value is nan"""
        return (self.asi8 == iNaT)

    @property  # NB: override with cache_readonly in immutable subclasses
    def hasnans(self):
        """ return if I have any nans; enables various perf speedups """
        return bool(self._isnan.any())

    def _maybe_mask_results(self, result, fill_value=iNaT, convert=None):
        """
        Parameters
        ----------
        result : a ndarray
        fill_value : object, default iNaT
        convert : string/dtype or None

        Returns
        -------
        result : ndarray with values replace by the fill_value

        mask the result if needed, convert to the provided dtype if its not
        None

        This is an internal routine
        """

        if self.hasnans:
            if convert:
                result = result.astype(convert)
            if fill_value is None:
                fill_value = np.nan
            result[self._isnan] = fill_value
        return result

    # ------------------------------------------------------------------
    # Frequency Properties/Methods

    @property
    def freq(self):
        """Return the frequency object if it is set, otherwise None"""
        return self._freq

    @freq.setter
    def freq(self, value):
        if value is not None:
            value = frequencies.to_offset(value)
            self._validate_frequency(self, value)

        self._freq = value

    @property
    def freqstr(self):
        """
        Return the frequency object as a string if its set, otherwise None
        """
        if self.freq is None:
            return None
        return self.freq.freqstr

    @property  # NB: override with cache_readonly in immutable subclasses
    def inferred_freq(self):
        """
        Tryies to return a string representing a frequency guess,
        generated by infer_freq.  Returns None if it can't autodetect the
        frequency.
        """
        try:
            return frequencies.infer_freq(self)
        except ValueError:
            return None

    @property  # NB: override with cache_readonly in immutable subclasses
    def _resolution(self):
        return frequencies.Resolution.get_reso_from_freq(self.freqstr)

    @property  # NB: override with cache_readonly in immutable subclasses
    def resolution(self):
        """
        Returns day, hour, minute, second, millisecond or microsecond
        """
        return frequencies.Resolution.get_str(self._resolution)

    @classmethod
    def _validate_frequency(cls, index, freq, **kwargs):
        """
        Validate that a frequency is compatible with the values of a given
        Datetime Array/Index or Timedelta Array/Index

        Parameters
        ----------
        index : DatetimeIndex or TimedeltaIndex
            The index on which to determine if the given frequency is valid
        freq : DateOffset
            The frequency to validate
        """
        if is_period_dtype(cls):
            # Frequency validation is not meaningful for Period Array/Index
            return None

        inferred = index.inferred_freq
        if index.size == 0 or inferred == freq.freqstr:
            return None

        on_freq = cls._generate_range(start=index[0], end=None,
                                      periods=len(index), freq=freq, **kwargs)
        if not np.array_equal(index.asi8, on_freq.asi8):
            raise ValueError('Inferred frequency {infer} from passed values '
                             'does not conform to passed frequency {passed}'
                             .format(infer=inferred, passed=freq.freqstr))

    # ------------------------------------------------------------------
    # Arithmetic Methods

    def _add_datetimelike_scalar(self, other):
        # Overriden by TimedeltaArray
        raise TypeError("cannot add {cls} and {typ}"
                        .format(cls=type(self).__name__,
                                typ=type(other).__name__))

    _add_datetime_arraylike = _add_datetimelike_scalar

    def _sub_datetimelike_scalar(self, other):
        # Overridden by DatetimeArray
        assert other is not NaT
        raise TypeError("cannot subtract a datelike from a {cls}"
                        .format(cls=type(self).__name__))

    _sub_datetime_arraylike = _sub_datetimelike_scalar

    def _sub_period(self, other):
        # Overriden by PeriodArray
        raise TypeError("cannot subtract Period from a {cls}"
                        .format(cls=type(self).__name__))

    def _add_offset(self, offset):
        raise AbstractMethodError(self)

    def _add_delta(self, other):
        """
        Add a timedelta-like, Tick or TimedeltaIndex-like object
        to self, yielding an int64 numpy array

        Parameters
        ----------
        delta : {timedelta, np.timedelta64, Tick,
                 TimedeltaIndex, ndarray[timedelta64]}

        Returns
        -------
        result : ndarray[int64]

        Notes
        -----
        The result's name is set outside of _add_delta by the calling
        method (__add__ or __sub__), if necessary (i.e. for Indexes).
        """
        if isinstance(other, (Tick, timedelta, np.timedelta64)):
            new_values = self._add_timedeltalike_scalar(other)
        elif is_timedelta64_dtype(other):
            # ndarray[timedelta64] or TimedeltaArray/index
            new_values = self._add_delta_tdi(other)

        return new_values

    def _add_timedeltalike_scalar(self, other):
        """
        Add a delta of a timedeltalike
        return the i8 result view
        """
        if isna(other):
            # i.e np.timedelta64("NaT"), not recognized by delta_to_nanoseconds
            new_values = np.empty(len(self), dtype='i8')
            new_values[:] = iNaT
            return new_values

        inc = delta_to_nanoseconds(other)
        new_values = checked_add_with_arr(self.asi8, inc,
                                          arr_mask=self._isnan).view('i8')
        new_values = self._maybe_mask_results(new_values)
        return new_values.view('i8')

    def _add_delta_tdi(self, other):
        """
        Add a delta of a TimedeltaIndex
        return the i8 result view
        """
        if len(self) != len(other):
            raise ValueError("cannot add indices of unequal length")

        if isinstance(other, np.ndarray):
            # ndarray[timedelta64]; wrap in TimedeltaIndex for op
            from pandas import TimedeltaIndex
            other = TimedeltaIndex(other)

        self_i8 = self.asi8
        other_i8 = other.asi8
        new_values = checked_add_with_arr(self_i8, other_i8,
                                          arr_mask=self._isnan,
                                          b_mask=other._isnan)
        if self.hasnans or other.hasnans:
            mask = (self._isnan) | (other._isnan)
            new_values[mask] = iNaT
        return new_values.view('i8')

    def _add_nat(self):
        """Add pd.NaT to self"""
        if is_period_dtype(self):
            raise TypeError('Cannot add {cls} and {typ}'
                            .format(cls=type(self).__name__,
                                    typ=type(NaT).__name__))

        # GH#19124 pd.NaT is treated like a timedelta for both timedelta
        # and datetime dtypes
        result = np.zeros(len(self), dtype=np.int64)
        result.fill(iNaT)
        if is_timedelta64_dtype(self):
            return type(self)(result, freq=None)
        return type(self)(result, tz=self.tz, freq=None)

    def _sub_nat(self):
        """Subtract pd.NaT from self"""
        # GH#19124 Timedelta - datetime is not in general well-defined.
        # We make an exception for pd.NaT, which in this case quacks
        # like a timedelta.
        # For datetime64 dtypes by convention we treat NaT as a datetime, so
        # this subtraction returns a timedelta64 dtype.
        # For period dtype, timedelta64 is a close-enough return dtype.
        result = np.zeros(len(self), dtype=np.int64)
        result.fill(iNaT)
        return result.view('timedelta64[ns]')

    def _sub_period_array(self, other):
        """
        Subtract a Period Array/Index from self.  This is only valid if self
        is itself a Period Array/Index, raises otherwise.  Both objects must
        have the same frequency.

        Parameters
        ----------
        other : PeriodIndex or PeriodArray

        Returns
        -------
        result : np.ndarray[object]
            Array of DateOffset objects; nulls represented by NaT
        """
        if not is_period_dtype(self):
            raise TypeError("cannot subtract {dtype}-dtype from {cls}"
                            .format(dtype=other.dtype,
                                    cls=type(self).__name__))

        if len(self) != len(other):
            raise ValueError("cannot subtract arrays/indices of "
                             "unequal length")
        if self.freq != other.freq:
            msg = DIFFERENT_FREQ_INDEX.format(self.freqstr, other.freqstr)
            raise IncompatibleFrequency(msg)

        new_values = checked_add_with_arr(self.asi8, -other.asi8,
                                          arr_mask=self._isnan,
                                          b_mask=other._isnan)

        new_values = np.array([self.freq * x for x in new_values])
        if self.hasnans or other.hasnans:
            mask = (self._isnan) | (other._isnan)
            new_values[mask] = NaT
        return new_values

    def _addsub_int_array(self, other, op):
        """
        Add or subtract array-like of integers equivalent to applying
        `_time_shift` pointwise.

        Parameters
        ----------
        other : Index, ExtensionArray, np.ndarray
            integer-dtype
        op : {operator.add, operator.sub}

        Returns
        -------
        result : same class as self
        """
        # _addsub_int_array is overriden by PeriodArray
        assert not is_period_dtype(self)
        assert op in [operator.add, operator.sub]

        if self.freq is None:
            # GH#19123
            raise NullFrequencyError("Cannot shift with no freq")

        elif isinstance(self.freq, Tick):
            # easy case where we can convert to timedelta64 operation
            td = Timedelta(self.freq)
            return op(self, td * other)

        # We should only get here with DatetimeIndex; dispatch
        # to _addsub_offset_array
        assert not is_timedelta64_dtype(self)
        return op(self, np.array(other) * self.freq)

    def _addsub_offset_array(self, other, op):
        """
        Add or subtract array-like of DateOffset objects

        Parameters
        ----------
        other : Index, np.ndarray
            object-dtype containing pd.DateOffset objects
        op : {operator.add, operator.sub}

        Returns
        -------
        result : same class as self
        """
        assert op in [operator.add, operator.sub]
        if len(other) == 1:
            return op(self, other[0])

        warnings.warn("Adding/subtracting array of DateOffsets to "
                      "{cls} not vectorized"
                      .format(cls=type(self).__name__), PerformanceWarning)

        # For EA self.astype('O') returns a numpy array, not an Index
        left = lib.values_from_object(self.astype('O'))

        res_values = op(left, np.array(other))
        if not is_period_dtype(self):
            return type(self)(res_values, freq='infer')
        return self._from_sequence(res_values)

    @deprecate_kwarg(old_arg_name='n', new_arg_name='periods')
    def shift(self, periods, freq=None):
        """
        Shift index by desired number of time frequency increments.

        This method is for shifting the values of datetime-like indexes
        by a specified time increment a given number of times.

        Parameters
        ----------
        periods : int
            Number of periods (or increments) to shift by,
            can be positive or negative.

            .. versionchanged:: 0.24.0

        freq : pandas.DateOffset, pandas.Timedelta or string, optional
            Frequency increment to shift by.
            If None, the index is shifted by its own `freq` attribute.
            Offset aliases are valid strings, e.g., 'D', 'W', 'M' etc.

        Returns
        -------
        pandas.DatetimeIndex
            Shifted index.

        See Also
        --------
        Index.shift : Shift values of Index.
        PeriodIndex.shift : Shift values of PeriodIndex.
        """
        return self._time_shift(periods=periods, freq=freq)

    def _time_shift(self, periods, freq=None):
        """
        Shift each value by `periods`.

        Note this is different from ExtensionArray.shift, which
        shifts the *position* of each element, padding the end with
        missing values.

        Parameters
        ----------
        periods : int
            Number of periods to shift by.
        freq : pandas.DateOffset, pandas.Timedelta, or string
            Frequency increment to shift by.
        """
        if freq is not None and freq != self.freq:
            if isinstance(freq, compat.string_types):
                freq = frequencies.to_offset(freq)
            offset = periods * freq
            result = self + offset
            if hasattr(self, 'tz'):
                result._tz = self.tz
            return result

        if periods == 0:
            # immutable so OK
            return self.copy()

        if self.freq is None:
            raise NullFrequencyError("Cannot shift with no freq")

        start = self[0] + periods * self.freq
        end = self[-1] + periods * self.freq

        # Note: in the DatetimeTZ case, _generate_range will infer the
        #  appropriate timezone from `start` and `end`, so tz does not need
        #  to be passed explicitly.
        return self._generate_range(start=start, end=end, periods=None,
                                    freq=self.freq)

    @classmethod
    def _add_datetimelike_methods(cls):
        """
        add in the datetimelike methods (as we may have to override the
        superclass)
        """

        def __add__(self, other):
            other = lib.item_from_zerodim(other)
            if isinstance(other, (ABCSeries, ABCDataFrame)):
                return NotImplemented

            # scalar others
            elif other is NaT:
                result = self._add_nat()
            elif isinstance(other, (Tick, timedelta, np.timedelta64)):
                result = self._add_delta(other)
            elif isinstance(other, DateOffset):
                # specifically _not_ a Tick
                result = self._add_offset(other)
            elif isinstance(other, (datetime, np.datetime64)):
                result = self._add_datetimelike_scalar(other)
            elif lib.is_integer(other):
                # This check must come after the check for np.timedelta64
                # as is_integer returns True for these
                maybe_integer_op_deprecated(self)
                result = self._time_shift(other)

            # array-like others
            elif is_timedelta64_dtype(other):
                # TimedeltaIndex, ndarray[timedelta64]
                result = self._add_delta(other)
            elif is_offsetlike(other):
                # Array/Index of DateOffset objects
                result = self._addsub_offset_array(other, operator.add)
            elif is_datetime64_dtype(other) or is_datetime64tz_dtype(other):
                # DatetimeIndex, ndarray[datetime64]
                return self._add_datetime_arraylike(other)
            elif is_integer_dtype(other):
                maybe_integer_op_deprecated(self)
                result = self._addsub_int_array(other, operator.add)
            elif is_float_dtype(other):
                # Explicitly catch invalid dtypes
                raise TypeError("cannot add {dtype}-dtype to {cls}"
                                .format(dtype=other.dtype,
                                        cls=type(self).__name__))
            elif is_period_dtype(other):
                # if self is a TimedeltaArray and other is a PeriodArray with
                #  a timedelta-like (i.e. Tick) freq, this operation is valid.
                #  Defer to the PeriodArray implementation.
                # In remaining cases, this will end up raising TypeError.
                return NotImplemented
            elif is_extension_array_dtype(other):
                # Categorical op will raise; defer explicitly
                return NotImplemented
            else:  # pragma: no cover
                return NotImplemented

            if is_timedelta64_dtype(result) and isinstance(result, np.ndarray):
                from pandas.core.arrays import TimedeltaArrayMixin
                # TODO: infer freq?
                return TimedeltaArrayMixin(result)
            return result

        cls.__add__ = __add__

        def __radd__(self, other):
            # alias for __add__
            return self.__add__(other)
        cls.__radd__ = __radd__

        def __sub__(self, other):
            other = lib.item_from_zerodim(other)
            if isinstance(other, (ABCSeries, ABCDataFrame)):
                return NotImplemented

            # scalar others
            elif other is NaT:
                result = self._sub_nat()
            elif isinstance(other, (Tick, timedelta, np.timedelta64)):
                result = self._add_delta(-other)
            elif isinstance(other, DateOffset):
                # specifically _not_ a Tick
                result = self._add_offset(-other)
            elif isinstance(other, (datetime, np.datetime64)):
                result = self._sub_datetimelike_scalar(other)
            elif lib.is_integer(other):
                # This check must come after the check for np.timedelta64
                # as is_integer returns True for these
                maybe_integer_op_deprecated(self)
                result = self._time_shift(-other)

            elif isinstance(other, Period):
                result = self._sub_period(other)

            # array-like others
            elif is_timedelta64_dtype(other):
                # TimedeltaIndex, ndarray[timedelta64]
                result = self._add_delta(-other)
            elif is_offsetlike(other):
                # Array/Index of DateOffset objects
                result = self._addsub_offset_array(other, operator.sub)
            elif is_datetime64_dtype(other) or is_datetime64tz_dtype(other):
                # DatetimeIndex, ndarray[datetime64]
                result = self._sub_datetime_arraylike(other)
            elif is_period_dtype(other):
                # PeriodIndex
                result = self._sub_period_array(other)
            elif is_integer_dtype(other):
                maybe_integer_op_deprecated(self)
                result = self._addsub_int_array(other, operator.sub)
            elif isinstance(other, ABCIndexClass):
                raise TypeError("cannot subtract {cls} and {typ}"
                                .format(cls=type(self).__name__,
                                        typ=type(other).__name__))
            elif is_float_dtype(other):
                # Explicitly catch invalid dtypes
                raise TypeError("cannot subtract {dtype}-dtype from {cls}"
                                .format(dtype=other.dtype,
                                        cls=type(self).__name__))
            elif is_extension_array_dtype(other):
                # Categorical op will raise; defer explicitly
                return NotImplemented
            else:  # pragma: no cover
                return NotImplemented

            if is_timedelta64_dtype(result) and isinstance(result, np.ndarray):
                from pandas.core.arrays import TimedeltaArrayMixin
                # TODO: infer freq?
                return TimedeltaArrayMixin(result)
            return result

        cls.__sub__ = __sub__

        def __rsub__(self, other):
            if is_datetime64_dtype(other) and is_timedelta64_dtype(self):
                # ndarray[datetime64] cannot be subtracted from self, so
                # we need to wrap in DatetimeArray/Index and flip the operation
                if not isinstance(other, DatetimeLikeArrayMixin):
                    # Avoid down-casting DatetimeIndex
                    from pandas.core.arrays import DatetimeArrayMixin
                    other = DatetimeArrayMixin(other)
                return other - self
            elif (is_datetime64_any_dtype(self) and hasattr(other, 'dtype') and
                  not is_datetime64_any_dtype(other)):
                # GH#19959 datetime - datetime is well-defined as timedelta,
                # but any other type - datetime is not well-defined.
                raise TypeError("cannot subtract {cls} from {typ}"
                                .format(cls=type(self).__name__,
                                        typ=type(other).__name__))
            elif is_period_dtype(self) and is_timedelta64_dtype(other):
                # TODO: Can we simplify/generalize these cases at all?
                raise TypeError("cannot subtract {cls} from {dtype}"
                                .format(cls=type(self).__name__,
                                        dtype=other.dtype))
            return -(self - other)
        cls.__rsub__ = __rsub__

        def __iadd__(self, other):
            # alias for __add__
            return self.__add__(other)
        cls.__iadd__ = __iadd__

        def __isub__(self, other):
            # alias for __sub__
            return self.__sub__(other)
        cls.__isub__ = __isub__

    # --------------------------------------------------------------
    # Comparison Methods

    # Called by _add_comparison_methods defined in ExtensionOpsMixin
    _create_comparison_method = classmethod(_make_comparison_op)

    def _evaluate_compare(self, other, op):
        """
        We have been called because a comparison between
        8 aware arrays. numpy >= 1.11 will
        now warn about NaT comparisons
        """
        # Called by comparison methods when comparing datetimelike
        # with datetimelike

        if not isinstance(other, type(self)):
            # coerce to a similar object
            if not is_list_like(other):
                # scalar
                other = [other]
            elif lib.is_scalar(lib.item_from_zerodim(other)):
                # ndarray scalar
                other = [other.item()]
            other = type(self)(other)

        # compare
        result = op(self.asi8, other.asi8)

        # technically we could support bool dtyped Index
        # for now just return the indexing array directly
        mask = (self._isnan) | (other._isnan)

        filler = iNaT
        if is_bool_dtype(result):
            filler = False

        result[mask] = filler
        return result


DatetimeLikeArrayMixin._add_comparison_ops()


# -------------------------------------------------------------------
# Shared Constructor Helpers

def validate_periods(periods):
    """
    If a `periods` argument is passed to the Datetime/Timedelta Array/Index
    constructor, cast it to an integer.

    Parameters
    ----------
    periods : None, float, int

    Returns
    -------
    periods : None or int

    Raises
    ------
    TypeError
        if periods is None, float, or int
    """
    if periods is not None:
        if lib.is_float(periods):
            periods = int(periods)
        elif not lib.is_integer(periods):
            raise TypeError('periods must be a number, got {periods}'
                            .format(periods=periods))
    return periods


def validate_endpoints(closed):
    """
    Check that the `closed` argument is among [None, "left", "right"]

    Parameters
    ----------
    closed : {None, "left", "right"}

    Returns
    -------
    left_closed : bool
    right_closed : bool

    Raises
    ------
    ValueError : if argument is not among valid values
    """
    left_closed = False
    right_closed = False

    if closed is None:
        left_closed = True
        right_closed = True
    elif closed == "left":
        left_closed = True
    elif closed == "right":
        right_closed = True
    else:
        raise ValueError("Closed has to be either 'left', 'right' or None")

    return left_closed, right_closed


def maybe_infer_freq(freq):
    """
    Comparing a DateOffset to the string "infer" raises, so we need to
    be careful about comparisons.  Make a dummy variable `freq_infer` to
    signify the case where the given freq is "infer" and set freq to None
    to avoid comparison trouble later on.

    Parameters
    ----------
    freq : {DateOffset, None, str}

    Returns
    -------
    freq : {DateOffset, None}
    freq_infer : bool
    """
    freq_infer = False
    if not isinstance(freq, DateOffset):
        # if a passed freq is None, don't infer automatically
        if freq != 'infer':
            freq = frequencies.to_offset(freq)
        else:
            freq_infer = True
            freq = None
    return freq, freq_infer


def validate_tz_from_dtype(dtype, tz):
    """
    If the given dtype is a DatetimeTZDtype, extract the implied
    tzinfo object from it and check that it does not conflict with the given
    tz.

    Parameters
    ----------
    dtype : dtype, str
    tz : None, tzinfo

    Returns
    -------
    tz : consensus tzinfo

    Raises
    ------
    ValueError : on tzinfo mismatch
    """
    if dtype is not None:
        try:
            dtype = DatetimeTZDtype.construct_from_string(dtype)
            dtz = getattr(dtype, 'tz', None)
            if dtz is not None:
                if tz is not None and not timezones.tz_compare(tz, dtz):
                    raise ValueError("cannot supply both a tz and a dtype"
                                     " with a tz")
                tz = dtz
        except TypeError:
            pass
    return tz


def validate_dtype_freq(dtype, freq):
    """
    If both a dtype and a freq are available, ensure they match.  If only
    dtype is available, extract the implied freq.

    Parameters
    ----------
    dtype : dtype
    freq : DateOffset or None

    Returns
    -------
    freq : DateOffset

    Raises
    ------
    ValueError : non-period dtype
    IncompatibleFrequency : mismatch between dtype and freq
    """
    if freq is not None:
        freq = frequencies.to_offset(freq)

    if dtype is not None:
        dtype = pandas_dtype(dtype)
        if not is_period_dtype(dtype):
            raise ValueError('dtype must be PeriodDtype')
        if freq is None:
            freq = dtype.freq
        elif freq != dtype.freq:
            raise IncompatibleFrequency('specified freq and dtype '
                                        'are different')
    return freq
