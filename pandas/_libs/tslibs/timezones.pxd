# -*- coding: utf-8 -*-
# cython: profile=False

from numpy cimport ndarray

cdef bint is_utc(object tz)
cdef bint is_tzlocal(object tz)

cdef bint treat_tz_as_pytz(object tz)
cdef bint treat_tz_as_dateutil(object tz)

cpdef object get_timezone(object tz)
cpdef object maybe_get_tz(object tz)

cpdef get_utcoffset(tzinfo, obj)
cdef bint is_fixed_offset(object tz)

cdef object get_dst_info(object tz)
