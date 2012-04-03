# pylint: disable=E1101,E1103

from pandas.core.index import DatetimeIndex, Index
import pandas.core.datetools as datetools


#-----------------------------------------------------------------------------
# DateRange class

class DateRange(Index):

    offset = tzinfo = None

    def __new__(cls, start=None, end=None, periods=None,
                offset=datetools.bday, time_rule=None,
                tzinfo=None, name=None, **kwds):

        import warnings
        warnings.warn("DateRange is deprecated, use DatetimeIndex instead",
                       FutureWarning)

        # use old mapping
        if time_rule is not None:
            offset = datetools._offsetMap[time_rule]
        elif 'timeRule' in kwds and kwds['timeRule'] is not None:
            offset = datetools._offsetMap[kwds['timeRule']]

        return DatetimeIndex(start=start, end=end,
                             periods=periods, offset=offset,
                             tzinfo=tzinfo, name=name, _deprecated=True,
                             **kwds)

    def __setstate__(self, aug_state):
        """Necessary for making this object picklable"""
        index_state = aug_state[:1]
        offset = aug_state[1]

        # for backwards compatibility
        if len(aug_state) > 2:
            tzinfo = aug_state[2]
        else: # pragma: no cover
            tzinfo = None

        self.offset = offset
        self.tzinfo = tzinfo
        Index.__setstate__(self, *index_state)

def date_range(start=None, end=None, periods=None, freq='D', tz=None):
    """
    Return a fixed frequency datetime index, with day (calendar) as the default
    frequency


    Parameters
    ----------
    start :
    end :

    Returns
    -------

    """
    return DatetimeIndex(start=start, end=end, periods=periods,
                         freq=freq, tz=tz)


def bdate_range(start=None, end=None, periods=None, freq='B', tz=None):
    """
    Return a fixed frequency datetime index, with business day as the default
    frequency

    Parameters
    ----------


    Returns
    -------
    date_range : DatetimeIndex

    """

    return DatetimeIndex(start=start, end=end, periods=periods,
                         freq=freq, tz=tz)
