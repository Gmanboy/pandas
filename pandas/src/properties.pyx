from cpython cimport PyDict_Contains, PyDict_GetItem, PyDict_GetItem

cdef class cache_readonly(object):

    cdef readonly:
        object fget, name

    def __init__(self, func):
        self.fget = func
        self.name = func.__name__

    def __get__(self, obj, type):
        if obj is None:
            return self.fget

        # Get the cache or set a default one if needed

        cache = getattr(obj, '_cache', None)
        if cache is None:
            cache = obj._cache = {}

        if PyDict_Contains(cache, self.name):
            # not necessary to Py_INCREF
            val = <object> PyDict_GetItem(cache, self.name)
            return val
        else:
            val = self.fget(obj)
            PyDict_SetItem(cache, self.name, val)
            return val

cdef class AxisProperty(object):
    cdef:
        Py_ssize_t axis

    def __init__(self, axis=0):
        self.axis = axis

    def __get__(self, obj, type):
        cdef list axes = obj._data.axes
        return axes[self.axis]

    def __set__(self, obj, value):
        obj._set_axis(self.axis, value)
