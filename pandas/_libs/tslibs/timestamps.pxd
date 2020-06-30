from cpython.datetime cimport datetime

from numpy cimport int64_t

from pandas._libs.tslibs.base cimport ABCTimestamp
from pandas._libs.tslibs.np_datetime cimport npy_datetimestruct


cdef object create_timestamp_from_ts(int64_t value,
                                     npy_datetimestruct dts,
                                     object tz, object freq, bint fold)


cdef class _Timestamp(ABCTimestamp):
    cdef readonly:
        int64_t value, nanosecond
        object freq

    cdef bint _get_start_end_field(self, str field)
    cdef _get_date_name_field(self, str field, object locale)
    cdef int64_t _maybe_convert_value_to_local(self)
    cpdef to_datetime64(self)
    cdef _assert_tzawareness_compat(_Timestamp self, datetime other)
    cpdef datetime to_pydatetime(_Timestamp self, bint warn=*)
    cdef bint _compare_outside_nanorange(_Timestamp self, datetime other,
                                         int op) except -1
