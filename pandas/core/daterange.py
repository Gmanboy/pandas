# pylint: disable-msg=E1101,E1103

from datetime import datetime
import operator

import numpy as np

from pandas.core.index import Index
import pandas.core.datetools as datetools

#-------------------------------------------------------------------------------
# XDateRange class

class XDateRange(object):
    """
    XDateRange generates a sequence of dates corresponding to the
    specified time offset

    Notes
    -----
    If both start and end are specified, the returned dates will
    satisfy:

    start <= date <= end

    In other words, dates are constrained to lie in the specifed range
    as you would expect, though no dates which do NOT lie on the
    offset will be returned.

    XDateRange is a generator, use if you do not intend to reuse the
    date range, or if you are doing lazy iteration, or if the number
    of dates you are generating is very large. If you intend to reuse
    the range, use DateRange, which will be the list of dates
    generated by XDateRange.

    See also
    --------
    DateRange
    """
    _cache = {}
    _cacheStart = {}
    _cacheEnd = {}
    def __init__(self, start=None, end=None, nPeriods=None,
                 offset=datetools.BDay(), timeRule=None):

        if timeRule is not None:
            offset = datetools.getOffset(timeRule)

        if timeRule is None:
            if offset in datetools._offsetNames:
                timeRule = datetools._offsetNames[offset]

        start = datetools.to_datetime(start)
        end = datetools.to_datetime(end)

        if start and not offset.onOffset(start):
            start = start + offset.__class__(n=1, **offset.kwds)
        if end and not offset.onOffset(end):
            end = end - offset.__class__(n=1, **offset.kwds)
            if nPeriods == None and end < start:
                end = None
                nPeriods = 0

        if end is None:
            end = start + (nPeriods - 1) * offset

        if start is None:
            start = end - (nPeriods - 1) * offset

        self.offset = offset
        self.timeRule = timeRule
        self.start = start
        self.end = end
        self.nPeriods = nPeriods

    def __iter__(self):
        offset = self.offset
        cur = self.start
        if offset._normalizeFirst:
            cur = datetools.normalize_date(cur)
        while cur <= self.end:
            yield cur
            cur = cur + offset

#-------------------------------------------------------------------------------
# DateRange cache

CACHE_START = datetime(1950, 1, 1)
CACHE_END   = datetime(2030, 1, 1)

#-------------------------------------------------------------------------------
# DateRange class

def _bin_op(op):
    def f(self, other):
        return op(self.view(np.ndarray), other)

    return f

class DateRange(Index):
    """
    Fixed frequency date range according to input parameters.

    Input dates satisfy:
        begin <= d <= end, where d lies on the given offset

    Parameters
    ----------
    start : {datetime, None}
        left boundary for range
    end : {datetime, None}
        right boundary for range
    periods : int
        Number of periods to generate.
    offset : DateOffset, default is 1 BusinessDay
        Used to determine the dates returned
    timeRule : timeRule to use
    """
    _cache = {}
    _parent = None
    def __new__(cls, start=None, end=None, periods=None,
                offset=datetools.bday, timeRule=None, **kwds):

        # Allow us to circumvent hitting the cache
        index = kwds.get('index')
        if index is None:
            if timeRule is not None:
                offset = datetools.getOffset(timeRule)

            if timeRule is None:
                if offset in datetools._offsetNames:
                    timeRule = datetools._offsetNames[offset]

            # Cachable
            if not start:
                start = kwds.get('begin')
            if not end:
                end = kwds.get('end')
            if not periods:
                periods = kwds.get('nPeriods')

            start = datetools.to_datetime(start)
            end = datetools.to_datetime(end)

            # inside cache range
            fromInside = start is not None and start > CACHE_START
            toInside = end is not None and end < CACHE_END

            useCache = fromInside and toInside

            if (useCache and offset.isAnchored() and
                not isinstance(offset, datetools.Tick)):

                index = cls.getCachedRange(start, end, periods=periods,
                                           offset=offset, timeRule=timeRule)

            else:
                xdr = XDateRange(start=start, end=end,
                                 nPeriods=periods, offset=offset,
                                 timeRule=timeRule)

                index = np.array(list(xdr), dtype=object, copy=False)

                index = index.view(cls)
                index.offset = offset
        else:
            index = index.view(cls)

        return index

    def __reduce__(self):
        """Necessary for making this object picklable"""
        a, b, state = Index.__reduce__(self)
        aug_state = state, self.offset

        return a, b, aug_state

    def __setstate__(self, aug_state):
        """Necessary for making this object picklable"""
        state, offset = aug_state[:-1], aug_state[-1]

        self.offset = offset
        Index.__setstate__(self, *state)

    @property
    def _allDates(self):
        return True

    @classmethod
    def getCachedRange(cls, start=None, end=None, periods=None, offset=None,
                       timeRule=None):

        # HACK: fix this dependency later
        if timeRule is not None:
            offset = datetools.getOffset(timeRule)

        if offset is None:
            raise Exception('Must provide a DateOffset!')

        if offset not in cls._cache:
            xdr = XDateRange(CACHE_START, CACHE_END, offset=offset)
            arr = np.array(list(xdr), dtype=object, copy=False)

            cachedRange = DateRange.fromIndex(arr)
            cachedRange.offset = offset

            cls._cache[offset] = cachedRange
        else:
            cachedRange = cls._cache[offset]

        if start is None:
            if end is None:
                raise Exception('Must provide start or end date!')
            if periods is None:
                raise Exception('Must provide number of periods!')

            assert(isinstance(end, datetime))

            end = offset.rollback(end)

            endLoc = cachedRange.indexMap[end] + 1
            startLoc = endLoc - periods
        elif end is None:
            assert(isinstance(start, datetime))
            start = offset.rollforward(start)

            startLoc = cachedRange.indexMap[start]
            if periods is None:
                raise Exception('Must provide number of periods!')

            endLoc = startLoc + periods
        else:
            start = offset.rollforward(start)
            end = offset.rollback(end)

            startLoc = cachedRange.indexMap[start]
            endLoc = cachedRange.indexMap[end] + 1

        indexSlice = cachedRange[startLoc:endLoc]
        indexSlice._parent = cachedRange

        return indexSlice

    @classmethod
    def fromIndex(cls, index):
        index = cls(index=index)
        return index

    def __array_finalize__(self, obj):
        if self.ndim == 0: # pragma: no cover
            return self.item()

        self.offset = getattr(obj, 'offset', None)
        self._parent = getattr(obj, '_parent',  None)

    __lt__ = _bin_op(operator.lt)
    __le__ = _bin_op(operator.le)
    __gt__ = _bin_op(operator.gt)
    __ge__ = _bin_op(operator.ge)
    __eq__ = _bin_op(operator.eq)

    def __getslice__(self, i, j):
        return self.__getitem__(slice(i, j))

    def __getitem__(self, key):
        """Override numpy.ndarray's __getitem__ method to work as desired"""
        result = self.view(np.ndarray)[key]

        if isinstance(key, (int, np.int32)):
            return result
        elif isinstance(key, slice):
            newIndex = result.view(DateRange)

            if key.step is not None:
                newIndex.offset = key.step * self.offset
            else:
                newIndex.offset = self.offset

            return newIndex
        else:
            return Index(result)

    def __repr__(self):
        output = str(self.__class__) + '\n'
        output += 'offset: %s\n' % self.offset
        output += '[%s, ..., %s]\n' % (self[0], self[-1])
        output += 'length: %d' % len(self)
        return output

    __str__ = __repr__

    def shift(self, n, offset=None):
        if offset is not None and offset != self.offset:
            return Index.shift(self, n, offset)

        if n == 0:
            # immutable so OK
            return self

        start = self[0] + n * self.offset
        end = self[-1] + n * self.offset
        return DateRange(start, end, offset=self.offset)

    def union(self, other):
        if isinstance(other, DateRange) and other.offset == self.offset:
            # overlap condition
            if self[-1] >= other[0] or other[-1] >= self[0]:
                start = min(self[0], other[0])
                end = max(self[-1], other[-1])

                return DateRange(start, end, offset=self.offset)
            else:
                return Index.union(self, other)
        else:
            return Index.union(self, other)
