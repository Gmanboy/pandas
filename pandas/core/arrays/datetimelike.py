# -*- coding: utf-8 -*-

import numpy as np

from pandas._libs import iNaT
from pandas._libs.tslibs.timedeltas import delta_to_nanoseconds

from pandas.tseries import frequencies

import pandas.core.common as com
from pandas.core.algorithms import checked_add_with_arr


class DatetimeLikeArrayMixin(object):
    """
    Shared Base/Mixin class for DatetimeArray, TimedeltaArray, PeriodArray

    Assumes that __new__/__init__ defines:
        _data
        _freq

    and that the inheriting class has methods:
        _validate_frequency
    """

    @property
    def _box_func(self):
        """
        box function to get object from internal representation
        """
        raise com.AbstractMethodError(self)

    def __iter__(self):
        return (self._box_func(v) for v in self.asi8)

    @property
    def values(self):
        """ return the underlying data as an ndarray """
        return self._data.view(np.ndarray)

    @property
    def asi8(self):
        # do not cache or you'll create a memory leak
        return self.values.view('i8')

    # ------------------------------------------------------------------
    # Null Handling

    @property  # NB: override with cache_readonly in immutable subclasses
    def _isnan(self):
        """ return if each value is nan"""
        return (self.asi8 == iNaT)

    @property  # NB: override with cache_readonly in immutable subclasses
    def hasnans(self):
        """ return if I have any nans; enables various perf speedups """
        return self._isnan.any()

    def _maybe_mask_results(self, result, fill_value=None, convert=None):
        """
        Parameters
        ----------
        result : a ndarray
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

    # ------------------------------------------------------------------
    # Arithmetic Methods

    def _add_datelike(self, other):
        raise TypeError("cannot add {cls} and {typ}"
                        .format(cls=type(self).__name__,
                                typ=type(other).__name__))

    def _sub_datelike(self, other):
        raise com.AbstractMethodError(self)

    def _sub_period(self, other):
        return NotImplemented

    def _add_offset(self, offset):
        raise com.AbstractMethodError(self)

    def _add_delta(self, other):
        return NotImplemented

    def _add_delta_td(self, other):
        """
        Add a delta of a timedeltalike
        return the i8 result view
        """
        inc = delta_to_nanoseconds(other)
        new_values = checked_add_with_arr(self.asi8, inc,
                                          arr_mask=self._isnan).view('i8')
        if self.hasnans:
            new_values[self._isnan] = iNaT
        return new_values.view('i8')

    def _add_delta_tdi(self, other):
        """
        Add a delta of a TimedeltaIndex
        return the i8 result view
        """
        if not len(self) == len(other):
            raise ValueError("cannot add indices of unequal length")

        self_i8 = self.asi8
        other_i8 = other.asi8
        new_values = checked_add_with_arr(self_i8, other_i8,
                                          arr_mask=self._isnan,
                                          b_mask=other._isnan)
        if self.hasnans or other.hasnans:
            mask = (self._isnan) | (other._isnan)
            new_values[mask] = iNaT
        return new_values.view('i8')
