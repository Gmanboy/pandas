# cython: wraparound=False
# cython: boundscheck=False

from numpy cimport *
cimport numpy as cnp
import numpy as np

from cpython cimport *
cimport cpython

cnp.import_array()

cdef class SeriesIterator:

    def __init__(self, arr):
        pass

    def next(self):
        pass

def foo(object o):
    cdef int64_t bar = o
    return bar

def foo2():
    print sizeof(PyObject*)

def bench_dict():
    cdef:
        # Py_ssize_t i
        dict d = {}

    for i in range(1000000):
        d[i] = i

from cpython cimport PyObject

cdef extern from "numpy/arrayobject.h":
    bint PyArray_Check(PyObject*)

cimport cython

@cython.boundscheck(False)
@cython.wraparound(False)
def bench_typecheck1(ndarray[object] arr):
    cdef Py_ssize_t i, n
    n = cnp.PyArray_SIZE(arr)
    for i in range(n):
        cpython.PyFloat_Check(arr[i])

def bench_typecheck2(ndarray[object] arr):
    cdef Py_ssize_t i, n
    cdef PyObject** buf = <PyObject**> arr.data
    n = cnp.PyArray_SIZE(arr)
    for i in range(n):
        PyArray_Check(buf[i])


def foo(object _chunk, object _arr):
    cdef:
        char* dummy_buf
        ndarray arr, result, chunk

    arr = _arr
    chunk = _chunk

    dummy_buf = chunk.data
    chunk.data = arr.data

    shape = chunk.shape
    group_size = 0
    n = len(arr)

    inc = arr.dtype.itemsize

    # chunk.shape[0] = 100
    return chunk

from khash cimport *

def test(ndarray arr, Py_ssize_t size_hint):
    cdef:
        kh_pymap_t *table
        int ret
        khiter_t k
        PyObject **data
        Py_ssize_t i, n
        ndarray[Py_ssize_t] indexer

    table = kh_init_pymap()
    kh_resize_pymap(table, size_hint)

    data = <PyObject**> arr.data
    n = len(arr)

    indexer = np.empty(n, dtype=np.int_)

    for i in range(n):
        k = kh_put_pymap(table, data[i], &ret)

        # if not ret:
        #     kh_del_pymap(table, k)

        table.vals[k] = i

    for i in range(n):
        k = kh_get_pymap(table, data[i])
        indexer[i] = table.vals[k]

    kh_destroy_pymap(table)

    return indexer


from cpython cimport PyString_AsString

def test_str(ndarray arr, Py_ssize_t size_hint):
    cdef:
        kh_str_t *table
        kh_cstr_t val
        int ret
        khiter_t k
        PyObject **data
        Py_ssize_t i, n
        ndarray[Py_ssize_t] indexer

    table = kh_init_str()
    kh_resize_str(table, size_hint)

    data = <PyObject**> arr.data
    n = len(arr)

    indexer = np.empty(n, dtype=np.int_)

    for i in range(n):
        k = kh_put_str(table, PyString_AsString(<object> data[i]), &ret)

        # if not ret:
        #     kh_del_str(table, k)

        table.vals[k] = i

    # for i in range(n):
    #     k = kh_get_str(table, PyString_AsString(<object> data[i]))
    #     indexer[i] = table.vals[k]

    kh_destroy_str(table)

    return indexer

# def test2(ndarray[object] arr):
#     cdef:
#         dict table
#         object obj
#         Py_ssize_t i, loc, n
#         ndarray[Py_ssize_t] indexer

#     n = len(arr)
#     indexer = np.empty(n, dtype=np.int_)

#     table = {}
#     for i in range(n):
#         table[arr[i]] = i

#     for i in range(n):
#         indexer[i] =  table[arr[i]]

#     return indexer

from cpython cimport Py_INCREF

def obj_unique(ndarray[object] arr):
    cdef:
        kh_pyset_t *table
        # PyObject *obj
        object obj
        PyObject **data
        int ret
        khiter_t k
        Py_ssize_t i, n
        list uniques

    n = len(arr)
    uniques = []

    table = kh_init_pyset()

    data = <PyObject**> arr.data

    # size hint
    kh_resize_pyset(table, n // 10)

    for i in range(n):
        obj = arr[i]

        k = kh_get_pyset(table, <PyObject*> obj)
        if not kh_exist_pyset(table, k):
            k = kh_put_pyset(table, <PyObject*> obj, &ret)
            # uniques.append(obj)
            # Py_INCREF(<object> obj)

    kh_destroy_pyset(table)

    return None

def int64_unique(ndarray[int64_t] arr):
    cdef:
        kh_int64_t *table
        # PyObject *obj
        int64_t obj
        PyObject **data
        int ret
        khiter_t k
        Py_ssize_t i, j, n
        ndarray[int64_t] uniques

    n = len(arr)
    uniques = np.empty(n, dtype='i8')

    table = kh_init_int64()
    kh_resize_int64(table, n)

    j = 0

    for i in range(n):
        obj = arr[i]

        k = kh_get_int64(table, obj)
        if not kh_exist_int64(table, k):
            k = kh_put_int64(table, obj, &ret)
            uniques[j] = obj
            j += 1
            # Py_INCREF(<object> obj)

    kh_destroy_int64(table)

    return np.sort(uniques[:j])

from cpython cimport PyString_Check, PyString_AsString

cdef class StringHashTable:

    cdef:
        kh_str_t *table

    def __init__(self, size_hint=1):
        if size_hint is not None:
            kh_resize_str(self.table, size_hint)

    def __cinit__(self):
        self.table = kh_init_str()

    def __dealloc__(self):
        kh_destroy_str(self.table)

    cdef inline int check_type(self, object val):
        return PyString_Check(val)

    cpdef get_item(self, object val):
        cdef khiter_t k
        k = kh_get_str(self.table, PyString_AsString(val))
        if k != self.table.n_buckets:
            return self.table.vals[k]
        else:
            raise KeyError(val)

    def get_iter_test(self, object key, Py_ssize_t iterations):
        cdef Py_ssize_t i, val
        for i in range(iterations):
            k = kh_get_str(self.table, PyString_AsString(key))
            if k != self.table.n_buckets:
                val = self.table.vals[k]

    cpdef set_item(self, object key, Py_ssize_t val):
        cdef:
            khiter_t k
            int ret
            char* buf

        buf = PyString_AsString(key)

        k = kh_put_str(self.table, buf, &ret)
        self.table.keys[k] = key
        if kh_exist_str(self.table, k):
            self.table.vals[k] = val
        else:
            raise KeyError(key)

    def factorize(self, ndarray[object] values):
        cdef:
            Py_ssize_t i, n = len(values)
            ndarray[int32_t] labels = np.empty(n, dtype=np.int32)
            ndarray[int32_t] counts = np.empty(n, dtype=np.int32)
            dict reverse = {}
            Py_ssize_t idx, count = 0
            int ret
            object val
            char *buf
            khiter_t k

        for i in range(n):
            val = values[i]
            buf = PyString_AsString(val)
            k = kh_get_str(self.table, buf)
            if k != self.table.n_buckets:
                idx = self.table.vals[k]
                labels[i] = idx
                counts[idx] = counts[idx] + 1
            else:
                k = kh_put_str(self.table, buf, &ret)
                # print 'putting %s, %s' % (val, count)
                if not ret:
                    kh_del_str(self.table, k)

                self.table.vals[k] = count
                reverse[count] = val
                labels[i] = count
                counts[count] = 1
                count += 1

        # return None
        return reverse, labels, counts[:count].copy()

cdef class Int64HashTable:

    cdef:
        kh_int64_t *table

    def __init__(self, size_hint=1):
        if size_hint is not None:
            kh_resize_int64(self.table, size_hint)

    def __cinit__(self):
        self.table = kh_init_int64()

    def __dealloc__(self):
        kh_destroy_int64(self.table)

    cdef inline int check_type(self, object val):
        return PyString_Check(val)

    cpdef get_item(self, int64_t val):
        cdef khiter_t k
        k = kh_get_int64(self.table, val)
        if k != self.table.n_buckets:
            return self.table.vals[k]
        else:
            raise KeyError(val)

    def get_iter_test(self, int64_t key, Py_ssize_t iterations):
        cdef Py_ssize_t i, val
        for i in range(iterations):
            k = kh_get_int64(self.table, val)
            if k != self.table.n_buckets:
                val = self.table.vals[k]

    cpdef set_item(self, int64_t key, Py_ssize_t val):
        cdef:
            khiter_t k
            int ret

        k = kh_put_int64(self.table, key, &ret)
        self.table.keys[k] = key
        if kh_exist_int64(self.table, k):
            self.table.vals[k] = val
        else:
            raise KeyError(key)

    def map_locations(self, ndarray[int64_t] values):
        cdef:
            Py_ssize_t i, n = len(values)
            int ret
            int64_t val
            khiter_t k

        for i in range(n):
            val = values[i]
            k = kh_put_int64(self.table, val, &ret)
            # print 'putting %s, %s' % (val, count)
            self.table.vals[k] = i

    def lookup_locations(self, ndarray[int64_t] values):
        cdef:
            Py_ssize_t i, n = len(values)
            int ret
            int64_t val
            khiter_t k
            ndarray[int32_t] locs = np.empty(n, dtype='i4')

        for i in range(n):
            val = values[i]
            k = kh_get_int64(self.table, val)
            if k != self.table.n_buckets:
                locs[i] = self.table.vals[k]
            else:
                locs[i] = -1

        return locs

    def factorize(self, ndarray[int64_t] values):
        cdef:
            Py_ssize_t i, n = len(values)
            ndarray[int32_t] labels = np.empty(n, dtype=np.int32)
            ndarray[int32_t] counts = np.empty(n, dtype=np.int32)
            dict reverse = {}
            Py_ssize_t idx, count = 0
            int ret
            int64_t val
            khiter_t k

        for i in range(n):
            val = values[i]
            k = kh_get_int64(self.table, val)
            if k != self.table.n_buckets:
                idx = self.table.vals[k]
                labels[i] = idx
                counts[idx] = counts[idx] + 1
            else:
                k = kh_put_int64(self.table, val, &ret)
                if not ret:
                    kh_del_int64(self.table, k)
                self.table.vals[k] = count
                reverse[count] = val
                labels[i] = count
                counts[count] = 1
                count += 1

        # return None
        return reverse, labels, counts[:count].copy()

from libc.stdlib cimport free

cdef class PyObjectHashTable:

    cdef:
        kh_pymap_t *table

    def __init__(self, size_hint=1):
        self.table = kh_init_pymap()
        kh_resize_pymap(self.table, size_hint)

    def __dealloc__(self):
        if self.table is not NULL:
            self.destroy()

    cpdef destroy(self):
        kh_destroy_pymap(self.table)
        self.table = NULL

    cpdef get_item(self, object val):
        cdef khiter_t k
        k = kh_get_pymap(self.table, <PyObject*>val)
        if k != self.table.n_buckets:
            return self.table.vals[k]
        else:
            raise KeyError(val)

    def get_iter_test(self, object key, Py_ssize_t iterations):
        cdef Py_ssize_t i, val
        for i in range(iterations):
            k = kh_get_pymap(self.table, <PyObject*>key)
            if k != self.table.n_buckets:
                val = self.table.vals[k]

    cpdef set_item(self, object key, Py_ssize_t val):
        cdef:
            khiter_t k
            int ret
            char* buf

        k = kh_put_pymap(self.table, <PyObject*>key, &ret)
        # self.table.keys[k] = key
        if kh_exist_pymap(self.table, k):
            self.table.vals[k] = val
        else:
            raise KeyError(key)

    def map_locations(self, ndarray[object] values):
        cdef:
            Py_ssize_t i, n = len(values)
            int ret
            object val
            khiter_t k

        for i in range(n):
            val = values[i]
            k = kh_put_pymap(self.table, <PyObject*>val, &ret)
            # print 'putting %s, %s' % (val, count)
            self.table.vals[k] = i

    def lookup_locations(self, ndarray[object] values):
        cdef:
            Py_ssize_t i, n = len(values)
            int ret
            object val
            khiter_t k
            ndarray[int32_t] locs = np.empty(n, dtype='i4')

        for i in range(n):
            val = values[i]
            k = kh_get_pymap(self.table, <PyObject*>val)
            if k != self.table.n_buckets:
                locs[i] = self.table.vals[k]
            else:
                locs[i] = -1

        return locs

    def lookup_locations2(self, ndarray[object] values):
        cdef:
            Py_ssize_t i, n = len(values)
            int ret
            object val
            khiter_t k
            long hval
            ndarray[int32_t] locs = np.empty(n, dtype='i4')

        # for i in range(n):
        #     val = values[i]
            # hval = PyObject_Hash(val)
            # k = kh_get_pymap(self.table, <PyObject*>val)

        return locs

    def unique(self, ndarray[object] values):
        cdef:
            Py_ssize_t i, n = len(values)
            ndarray[int32_t] labels = np.empty(n, dtype=np.int32)
            ndarray[int32_t] counts = np.empty(n, dtype=np.int32)
            dict reverse = {}
            Py_ssize_t idx, count = 0
            int ret
            object val
            khiter_t k
            list uniques = []

        for i in range(n):
            val = values[i]
            k = kh_get_pymap(self.table, <PyObject*>val)
            if k == self.table.n_buckets:
                k = kh_put_pymap(self.table, <PyObject*>val, &ret)
                uniques.append(val)

        return uniques

    def factorize(self, ndarray[object] values):
        cdef:
            Py_ssize_t i, n = len(values)
            ndarray[int32_t] labels = np.empty(n, dtype=np.int32)
            ndarray[int32_t] counts = np.empty(n, dtype=np.int32)
            dict reverse = {}
            Py_ssize_t idx, count = 0
            int ret
            object val
            khiter_t k

        for i in range(n):
            val = values[i]
            k = kh_get_pymap(self.table, <PyObject*>val)
            if k != self.table.n_buckets:
                idx = self.table.vals[k]
                labels[i] = idx
                counts[idx] = counts[idx] + 1
            else:
                k = kh_put_pymap(self.table, <PyObject*>val, &ret)
                # print 'putting %s, %s' % (val, count)
                # if not ret:
                #     kh_del_pymap(self.table, k)

                self.table.vals[k] = count
                reverse[count] = val
                labels[i] = count
                counts[count] = 1
                count += 1

        return reverse, labels, counts[:count].copy()

def lookup_locations2(ndarray[object] values):
    cdef:
        Py_ssize_t i, n = len(values)
        int ret
        object val
        khiter_t k
        long hval
        ndarray[int32_t] locs = np.empty(n, dtype='i4')

    # for i in range(n):
    #     val = values[i]
        # hval = PyObject_Hash(val)
        # k = kh_get_pymap(self.table, <PyObject*>val)

    return locs


from skiplist cimport *

def sl_test():
    cdef int ret

    np.random.seed(12345)
    n = 100

    cdef skiplist_t* skp = skiplist_init(n)

    arr = np.random.randn(n)

    for i in range(n):
        print i
        skiplist_insert(skp, arr[i])
        # val = skiplist_get(skp, 0, &ret)
        # if ret == 0:
        #     raise ValueError('%d out of bounds' % i)

        if i >= 20:
            skiplist_remove(skp, arr[i-20])

        # skiplist_remove(skp, arr[i])
        # print 'Skiplist begin: %s' % skiplist_get(skp, 0)
        # print 'Actual begin: %s' % sorted(arr[:i+1])[0]
        data = arr[max(i-19, 0):i+1]
        print 'Skiplist middle: %s' % skiplist_get(skp, len(data) // 2, &ret)
        print 'Actual middle: %s' % sorted(data)[len(data) // 2]

    skiplist_destroy(skp)

cdef double NaN = np.NaN

def _check_minp(minp, N):
    if minp > N:
        minp = N + 1
    elif minp == 0:
        minp = 1
    elif minp < 0:
        raise ValueError('min_periods must be >= 0')
    return minp

def roll_median(ndarray[float64_t] arg, int win, int minp):
    cdef double val, res, prev
    cdef:
        int ret
        skiplist_t *sl
        Py_ssize_t midpoint, nobs = 0, i


    cdef Py_ssize_t N = len(arg)
    cdef ndarray[double_t] output = np.empty(N, dtype=float)

    sl = skiplist_init(win)

    minp = _check_minp(minp, N)

    for i from 0 <= i < minp - 1:
        val = arg[i]

        # Not NaN
        if val == val:
            nobs += 1
            skiplist_insert(sl, val)

        output[i] = NaN

    for i from minp - 1 <= i < N:
        val = arg[i]

        if i > win - 1:
            prev = arg[i - win]

            if prev == prev:
                skiplist_remove(sl, prev)
                nobs -= 1

        if val == val:
            nobs += 1
            skiplist_insert(sl, val)

        if nobs >= minp:
            midpoint = nobs / 2
            if nobs % 2:
                res = skiplist_get(sl, midpoint, &ret)
            else:
                res = (skiplist_get(sl, midpoint, &ret) +
                       skiplist_get(sl, (midpoint - 1), &ret)) / 2
        else:
            res = NaN

        output[i] = res

    skiplist_destroy(sl)

    return output

