"""
Base and utility classes for tseries type pandas objects.
"""

import warnings
from datetime import datetime, timedelta

from pandas import compat
import numpy as np
from pandas.core import common as com, algorithms
from pandas.core.common import is_integer, is_float, AbstractMethodError
import pandas.tslib as tslib
import pandas.lib as lib
from pandas.core.index import Index
from pandas.util.decorators import Appender, cache_readonly
import pandas.tseries.frequencies as frequencies
import pandas.algos as _algos



class DatelikeOps(object):
    """ common ops for DatetimeIndex/PeriodIndex, but not TimedeltaIndex """

    def strftime(self, date_format):
        """
        Return an array of formatted strings specified by date_format, which
        supports the same string format as the python standard library. Details
        of the string format can be found in the `python string format doc
        <https://docs.python.org/2/library/datetime.html#strftime-and-strptime-behavior>`__

        .. versionadded:: 0.17.0

        Parameters
        ----------
        date_format : str
            date format string (e.g. "%Y-%m-%d")

        Returns
        -------
        ndarray of formatted strings
        """
        return np.asarray(self.format(date_format=date_format))

class TimelikeOps(object):
    """ common ops for TimedeltaIndex/DatetimeIndex, but not PeriodIndex """

    def round(self, freq):
        """
        Round the index to the specified freq; this is a floor type of operation

        Paramaters
        ----------
        freq : freq string/object

        Returns
        -------
        index of same type

        Raises
        ------
        ValueError if the freq cannot be converted
        """

        from pandas.tseries.frequencies import to_offset
        unit = to_offset(freq).nanos

        # round the local times
        if getattr(self,'tz',None) is not None:
            values = self.tz_localize(None).asi8
        else:
            values = self.asi8
        result = (unit*np.floor(values/unit)).astype('i8')
        attribs = self._get_attributes_dict()
        if 'freq' in attribs:
            attribs['freq'] = None
        if 'tz' in attribs:
            attribs['tz'] = None
        result = self._shallow_copy(result, **attribs)

        # reconvert to local tz
        if getattr(self,'tz',None) is not None:
            result = result.tz_localize(self.tz)
        return result

class DatetimeIndexOpsMixin(object):
    """ common ops mixin to support a unified inteface datetimelike Index """

    def __iter__(self):
        return (self._box_func(v) for v in self.asi8)

    @staticmethod
    def _join_i8_wrapper(joinf, dtype, with_indexers=True):
        """ create the join wrapper methods """

        @staticmethod
        def wrapper(left, right):
            if isinstance(left, (np.ndarray, com.ABCIndex, com.ABCSeries)):
                left = left.view('i8')
            if isinstance(right, (np.ndarray, com.ABCIndex, com.ABCSeries)):
                right = right.view('i8')
            results = joinf(left, right)
            if with_indexers:
                join_index, left_indexer, right_indexer = results
                join_index = join_index.view(dtype)
                return join_index, left_indexer, right_indexer
            return results

        return wrapper

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

    def groupby(self, f):
        objs = self.asobject.values
        return _algos.groupby_object(objs, f)

    def _format_with_header(self, header, **kwargs):
        return header + list(self._format_native_types(**kwargs))

    def __contains__(self, key):
        try:
            res = self.get_loc(key)
            return np.isscalar(res) or type(res) == slice or np.any(res)
        except (KeyError, TypeError, ValueError):
            return False

    def __getitem__(self, key):
        getitem = self._data.__getitem__
        if np.isscalar(key):
            val = getitem(key)
            return self._box_func(val)
        else:
            if com.is_bool_indexer(key):
                key = np.asarray(key)
                if key.all():
                    key = slice(0, None, None)
                else:
                    key = lib.maybe_booleans_to_slice(key.view(np.uint8))

            attribs = self._get_attributes_dict()

            freq = None
            if isinstance(key, slice):
                if self.freq is not None and key.step is not None:
                    freq = key.step * self.freq
                else:
                    freq = self.freq
            attribs['freq'] = freq

            result = getitem(key)
            if result.ndim > 1:
                return result

            return self._simple_new(result, **attribs)

    @property
    def freqstr(self):
        """ return the frequency object as a string if its set, otherwise None """
        if self.freq is None:
            return None
        return self.freq.freqstr

    @cache_readonly
    def inferred_freq(self):
        """
        Trys to return a string representing a frequency guess,
        generated by infer_freq.  Returns None if it can't autodetect the
        frequency.
        """
        try:
            return frequencies.infer_freq(self)
        except ValueError:
            return None

    # Try to run function on index first, and then on elements of index
    # Especially important for group-by functionality
    def map(self, f):
        try:
            result = f(self)
            if not isinstance(result, (np.ndarray, Index)):
                raise TypeError
            return result
        except Exception:
            return _algos.arrmap_object(self.asobject.values, f)

    def sort_values(self, return_indexer=False, ascending=True):
        """
        Return sorted copy of Index
        """
        if return_indexer:
            _as = self.argsort()
            if not ascending:
                _as = _as[::-1]
            sorted_index = self.take(_as)
            return sorted_index, _as
        else:
            sorted_values = np.sort(self.values)
            attribs = self._get_attributes_dict()
            freq = attribs['freq']
            from pandas.tseries.period import PeriodIndex
            if freq is not None and not isinstance(self, PeriodIndex):
                if freq.n > 0 and not ascending:
                    freq = freq * -1
                elif freq.n < 0 and ascending:
                    freq = freq * -1
            attribs['freq'] = freq

            if not ascending:
                sorted_values = sorted_values[::-1]

            return self._simple_new(sorted_values, **attribs)

    def take(self, indices, axis=0, allow_fill=True, fill_value=None):
        """
        Analogous to ndarray.take
        """
        indices = com._ensure_int64(indices)
        maybe_slice = lib.maybe_indices_to_slice(indices, len(self))
        if isinstance(maybe_slice, slice):
            return self[maybe_slice]
        taken = self.asi8.take(com._ensure_platform_int(indices))

        # only fill if we are passing a non-None fill_value
        if allow_fill and fill_value is not None:
            mask = indices == -1
            if mask.any():
                taken[mask] = tslib.iNaT
        return self._shallow_copy(taken, freq=None)

    def get_duplicates(self):
        values = Index.get_duplicates(self)
        return self._simple_new(values)

    @cache_readonly
    def _isnan(self):
        """ return if each value is nan"""
        return (self.asi8 == tslib.iNaT)

    @cache_readonly
    def hasnans(self):
        """ return if I have any nans; enables various perf speedups """
        return self._isnan.any()

    @property
    def asobject(self):
        from pandas.core.index import Index
        return Index(self._box_values(self.asi8), name=self.name, dtype=object)

    def _convert_tolerance(self, tolerance):
        try:
            return tslib.Timedelta(tolerance).to_timedelta64()
        except ValueError:
            raise ValueError('tolerance argument for %s must be convertible '
                             'to Timedelta: %r'
                             % (type(self).__name__, tolerance))

    def _maybe_mask_results(self, result, fill_value=None, convert=None):
        """
        Parameters
        ----------
        result : a ndarray
        convert : string/dtype or None

        Returns
        -------
        result : ndarray with values replace by the fill_value

        mask the result if needed, convert to the provided dtype if its not None

        This is an internal routine
        """

        if self.hasnans:
            mask = self.asi8 == tslib.iNaT
            if convert:
                result = result.astype(convert)
            if fill_value is None:
                fill_value = np.nan
            result[mask] = fill_value
        return result

    def tolist(self):
        """
        return a list of the underlying data
        """
        return list(self.asobject)

    def min(self, axis=None):
        """
        return the minimum value of the Index

        See also
        --------
        numpy.ndarray.min
        """
        try:
            i8 = self.asi8

            # quick check
            if len(i8) and self.is_monotonic:
                if i8[0] != tslib.iNaT:
                    return self._box_func(i8[0])

            if self.hasnans:
                mask = i8 == tslib.iNaT
                min_stamp = i8[~mask].min()
            else:
                min_stamp = i8.min()
            return self._box_func(min_stamp)
        except ValueError:
            return self._na_value

    def argmin(self, axis=None):
        """
        return a ndarray of the minimum argument indexer

        See also
        --------
        numpy.ndarray.argmin
        """

        i8 = self.asi8
        if self.hasnans:
            mask = i8 == tslib.iNaT
            if mask.all():
                return -1
            i8 = i8.copy()
            i8[mask] = np.iinfo('int64').max
        return i8.argmin()

    def max(self, axis=None):
        """
        return the maximum value of the Index

        See also
        --------
        numpy.ndarray.max
        """
        try:
            i8 = self.asi8

            # quick check
            if len(i8) and self.is_monotonic:
                if i8[-1] != tslib.iNaT:
                    return self._box_func(i8[-1])

            if self.hasnans:
                mask = i8 == tslib.iNaT
                max_stamp = i8[~mask].max()
            else:
                max_stamp = i8.max()
            return self._box_func(max_stamp)
        except ValueError:
            return self._na_value

    def argmax(self, axis=None):
        """
        return a ndarray of the maximum argument indexer

        See also
        --------
        numpy.ndarray.argmax
        """

        i8 = self.asi8
        if self.hasnans:
            mask = i8 == tslib.iNaT
            if mask.all():
                return -1
            i8 = i8.copy()
            i8[mask] = 0
        return i8.argmax()

    @property
    def _formatter_func(self):
        raise AbstractMethodError(self)

    def _format_attrs(self):
        """
        Return a list of tuples of the (attr,formatted_value)
        """
        attrs = super(DatetimeIndexOpsMixin, self)._format_attrs()
        for attrib in self._attributes:
            if attrib == 'freq':
                freq = self.freqstr
                if freq is not None:
                    freq = "'%s'" % freq
                attrs.append(('freq',freq))
        return attrs

    @cache_readonly
    def _resolution(self):
        return frequencies.Resolution.get_reso_from_freq(self.freqstr)

    @cache_readonly
    def resolution(self):
        """
        Returns day, hour, minute, second, millisecond or microsecond
        """
        return frequencies.Resolution.get_str(self._resolution)

    def _convert_scalar_indexer(self, key, kind=None):
        """
        we don't allow integer or float indexing on datetime-like when using loc

        Parameters
        ----------
        key : label of the slice bound
        kind : optional, type of the indexing operation (loc/ix/iloc/None)
        """

        if kind in ['loc'] and lib.isscalar(key) and (is_integer(key) or is_float(key)):
            self._invalid_indexer('index',key)

        return super(DatetimeIndexOpsMixin, self)._convert_scalar_indexer(key, kind=kind)

    def _add_datelike(self, other):
        raise AbstractMethodError(self)

    def _sub_datelike(self, other):
        raise AbstractMethodError(self)

    @classmethod
    def _add_datetimelike_methods(cls):
        """ add in the datetimelike methods (as we may have to override the superclass) """

        def __add__(self, other):
            from pandas.core.index import Index
            from pandas.tseries.tdi import TimedeltaIndex
            from pandas.tseries.offsets import DateOffset
            if isinstance(other, TimedeltaIndex):
                return self._add_delta(other)
            elif isinstance(self, TimedeltaIndex) and isinstance(other, Index):
                if hasattr(other,'_add_delta'):
                    return other._add_delta(self)
                raise TypeError("cannot add TimedeltaIndex and {typ}".format(typ=type(other)))
            elif isinstance(other, Index):
                warnings.warn("using '+' to provide set union with datetimelike Indexes is deprecated, "
                              "use .union()",FutureWarning, stacklevel=2)
                return self.union(other)
            elif isinstance(other, (DateOffset, timedelta, np.timedelta64, tslib.Timedelta)):
                return self._add_delta(other)
            elif com.is_integer(other):
                return self.shift(other)
            elif isinstance(other, (tslib.Timestamp, datetime)):
                return self._add_datelike(other)
            else:  # pragma: no cover
                return NotImplemented
        cls.__add__ = __add__
        cls.__radd__ = __add__

        def __sub__(self, other):
            from pandas.core.index import Index
            from pandas.tseries.tdi import TimedeltaIndex
            from pandas.tseries.offsets import DateOffset
            if isinstance(other, TimedeltaIndex):
                return self._add_delta(-other)
            elif isinstance(self, TimedeltaIndex) and isinstance(other, Index):
                if not isinstance(other, TimedeltaIndex):
                    raise TypeError("cannot subtract TimedeltaIndex and {typ}".format(typ=type(other)))
                return self._add_delta(-other)
            elif isinstance(other, Index):
                warnings.warn("using '-' to provide set differences with datetimelike Indexes is deprecated, "
                              "use .difference()",FutureWarning, stacklevel=2)
                return self.difference(other)
            elif isinstance(other, (DateOffset, timedelta, np.timedelta64, tslib.Timedelta)):
                return self._add_delta(-other)
            elif com.is_integer(other):
                return self.shift(-other)
            elif isinstance(other, (tslib.Timestamp, datetime)):
                return self._sub_datelike(other)
            else:  # pragma: no cover
                return NotImplemented
        cls.__sub__ = __sub__

        def __rsub__(self, other):
            return -(self - other)
        cls.__rsub__ = __rsub__

        cls.__iadd__ = __add__
        cls.__isub__ = __sub__

    def _add_delta(self, other):
        return NotImplemented

    def _add_delta_td(self, other):
        # add a delta of a timedeltalike
        # return the i8 result view

        inc = tslib._delta_to_nanoseconds(other)
        mask = self.asi8 == tslib.iNaT
        new_values = (self.asi8 + inc).view('i8')
        new_values[mask] = tslib.iNaT
        return new_values.view('i8')

    def _add_delta_tdi(self, other):
        # add a delta of a TimedeltaIndex
        # return the i8 result view

        # delta operation
        if not len(self) == len(other):
            raise ValueError("cannot add indices of unequal length")

        self_i8 = self.asi8
        other_i8 = other.asi8
        mask = (self_i8 == tslib.iNaT) | (other_i8 == tslib.iNaT)
        new_values = self_i8 + other_i8
        new_values[mask] = tslib.iNaT
        return new_values.view(self.dtype)

    def isin(self, values):
        """
        Compute boolean array of whether each index value is found in the
        passed set of values

        Parameters
        ----------
        values : set or sequence of values

        Returns
        -------
        is_contained : ndarray (boolean dtype)
        """
        if not isinstance(values, type(self)):
            try:
                values = type(self)(values)
            except ValueError:
                return self.asobject.isin(values)

        return algorithms.isin(self.asi8, values.asi8)

    def shift(self, n, freq=None):
        """
        Specialized shift which produces a DatetimeIndex

        Parameters
        ----------
        n : int
            Periods to shift by
        freq : DateOffset or timedelta-like, optional

        Returns
        -------
        shifted : DatetimeIndex
        """
        if freq is not None and freq != self.freq:
            if isinstance(freq, compat.string_types):
                freq = frequencies.to_offset(freq)
            offset = n * freq
            result = self + offset

            if hasattr(self, 'tz'):
                result.tz = self.tz

            return result

        if n == 0:
            # immutable so OK
            return self

        if self.freq is None:
            raise ValueError("Cannot shift with no freq")

        start = self[0] + n * self.freq
        end = self[-1] + n * self.freq
        attribs = self._get_attributes_dict()
        attribs['start'] = start
        attribs['end'] = end
        return type(self)(**attribs)

    def unique(self):
        """
        Index.unique with handling for DatetimeIndex/PeriodIndex metadata

        Returns
        -------
        result : DatetimeIndex or PeriodIndex
        """
        from pandas.core.index import Int64Index
        result = Int64Index.unique(self)
        return self._simple_new(result, name=self.name, freq=self.freq,
                                tz=getattr(self, 'tz', None))

    def repeat(self, repeats, axis=None):
        """
        Analogous to ndarray.repeat
        """
        return self._shallow_copy(self.values.repeat(repeats), freq=None)

    def summary(self, name=None):
        """
        return a summarized representation
        """
        formatter = self._formatter_func
        if len(self) > 0:
            index_summary = ', %s to %s' % (formatter(self[0]),
                                            formatter(self[-1]))
        else:
            index_summary = ''

        if name is None:
            name = type(self).__name__
        result = '%s: %s entries%s' % (com.pprint_thing(name),
                                       len(self), index_summary)
        if self.freq:
            result += '\nFreq: %s' % self.freqstr

        # display as values, not quoted
        result = result.replace("'","")
        return result
