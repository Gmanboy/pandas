from cStringIO import StringIO

take_1d_template = """@cython.wraparound(False)
@cython.boundscheck(False)
def take_1d_%(name)s(ndarray[%(c_type)s] values, ndarray[int32_t] indexer,
                     out=None):
    cdef:
        Py_ssize_t i, n, idx
        ndarray[%(c_type)s] outbuf

    n = len(indexer)

    if out is None:
        outbuf = np.empty(n, dtype=values.dtype)
    else:
        outbuf = out

    for i from 0 <= i < n:
        idx = indexer[i]
        if idx == -1:
            %(na_action)s
        else:
            outbuf[i] = values[idx]

"""

take_2d_axis0_template = """@cython.wraparound(False)
@cython.boundscheck(False)
def take_2d_axis0_%(name)s(ndarray[%(c_type)s, ndim=2] values,
                           ndarray[int32_t] indexer,
                           out=None):
    cdef:
        Py_ssize_t i, j, k, n, idx
        ndarray[%(c_type)s, ndim=2] outbuf

    n = len(indexer)
    k = values.shape[1]

    if out is None:
        outbuf = np.empty((n, k), dtype=values.dtype)
    else:
        outbuf = out

    for i from 0 <= i < n:
        idx = indexer[i]

        if idx == -1:
            for j from 0 <= j < k:
                %(na_action)s
        else:
            for j from 0 <= j < k:
                outbuf[i, j] = values[idx, j]

"""

take_2d_axis1_template = """@cython.wraparound(False)
@cython.boundscheck(False)
def take_2d_axis1_%(name)s(ndarray[%(c_type)s, ndim=2] values,
                           ndarray[int32_t] indexer,
                           out=None):
    cdef:
        Py_ssize_t i, j, k, n, idx
        ndarray[%(c_type)s, ndim=2] outbuf

    n = len(values)
    k = len(indexer)

    if out is None:
        outbuf = np.empty((n, k), dtype=values.dtype)
    else:
        outbuf = out

    for j from 0 <= j < k:
        idx = indexer[j]

        if idx == -1:
            for i from 0 <= i < n:
                %(na_action)s
        else:
            for i from 0 <= i < n:
                outbuf[i, j] = values[i, idx]

"""

set_na = "outbuf[i] = NaN"
set_na_2d = "outbuf[i, j] = NaN"
raise_on_na = "raise ValueError('No NA values allowed')"

merge_indexer_template = """@cython.wraparound(False)
@cython.boundscheck(False)
def merge_indexer_%(name)s(ndarray[%(c_type)s] values, dict oldMap):
    cdef int i, j, length, newLength
    cdef %(c_type)s idx
    cdef ndarray[int32_t] fill_vec

    newLength = len(values)
    fill_vec = np.empty(newLength, dtype=np.int32)
    for i from 0 <= i < newLength:
        idx = values[i]
        if idx in oldMap:
            fill_vec[i] = oldMap[idx]
        else:
            fill_vec[i] = -1

    return fill_vec

"""

backfill_template = """@cython.boundscheck(False)
@cython.wraparound(False)
def backfill_%(name)s(ndarray[%(c_type)s] oldIndex,
                      ndarray[%(c_type)s] newIndex,
                      dict oldMap, dict newMap):
    '''
    Backfilling logic for generating fill vector

    Diagram of what's going on

    Old      New    Fill vector    Mask
             .        0               1
             .        0               1
             .        0               1
    A        A        0               1
             .        1               1
             .        1               1
             .        1               1
             .        1               1
             .        1               1
    B        B        1               1
             .        2               1
             .        2               1
             .        2               1
    C        C        2               1
             .                        0
             .                        0
    D
    '''
    cdef int i, j, oldLength, newLength, curLoc
    cdef ndarray[int32_t, ndim=1] fill_vec
    cdef int newPos, oldPos
    cdef %(c_type)s prevOld, curOld

    oldLength = len(oldIndex)
    newLength = len(newIndex)

    fill_vec = np.empty(len(newIndex), dtype = np.int32)
    fill_vec.fill(-1)

    oldPos = oldLength - 1
    newPos = newLength - 1

    if newIndex[0] > oldIndex[oldLength - 1]:
        return fill_vec

    while newPos >= 0:
        curOld = oldIndex[oldPos]

        while newIndex[newPos] > curOld:
            newPos -= 1
            if newPos < 0:
                break

        curLoc = oldMap[curOld]

        if oldPos == 0:
            if newIndex[newPos] <= curOld:
                fill_vec[:newPos + 1] = curLoc
            break
        else:
            prevOld = oldIndex[oldPos - 1]

            while newIndex[newPos] > prevOld:
                fill_vec[newPos] = curLoc

                newPos -= 1
                if newPos < 0:
                    break
        oldPos -= 1

    return fill_vec

"""

pad_template = """@cython.boundscheck(False)
@cython.wraparound(False)
def pad_%(name)s(ndarray[%(c_type)s] oldIndex,
                 ndarray[%(c_type)s] newIndex,
                 dict oldMap, dict newMap):
    '''
    Padding logic for generating fill vector

    Diagram of what's going on

    Old      New    Fill vector    Mask
             .                        0
             .                        0
             .                        0
    A        A        0               1
             .        0               1
             .        0               1
             .        0               1
             .        0               1
             .        0               1
    B        B        1               1
             .        1               1
             .        1               1
             .        1               1
    C        C        2               1
    '''
    cdef int i, j, oldLength, newLength, curLoc
    cdef ndarray[int32_t, ndim=1] fill_vec
    cdef int newPos, oldPos
    cdef %(c_type)s prevOld, curOld

    oldLength = len(oldIndex)
    newLength = len(newIndex)

    fill_vec = np.empty(len(newIndex), dtype = np.int32)
    fill_vec.fill(-1)

    oldPos = 0
    newPos = 0

    if newIndex[newLength - 1] < oldIndex[0]:
        return fill_vec

    while newPos < newLength:
        curOld = oldIndex[oldPos]

        while newIndex[newPos] < curOld:
            newPos += 1
            if newPos > newLength - 1:
                break

        curLoc = oldMap[curOld]

        if oldPos == oldLength - 1:
            if newIndex[newPos] >= curOld:
                fill_vec[newPos:] = curLoc
            break
        else:
            nextOld = oldIndex[oldPos + 1]
            done = 0

            while newIndex[newPos] < nextOld:
                fill_vec[newPos] = curLoc
                newPos += 1

                if newPos > newLength - 1:
                    done = 1
                    break

            if done:
                break

        oldPos += 1

    return fill_vec

"""

is_monotonic_template = """@cython.boundscheck(False)
@cython.wraparound(False)
def is_monotonic_%(name)s(ndarray[%(c_type)s] arr):
    cdef:
        Py_ssize_t i, n
        %(c_type)s prev, cur

    n = len(arr)

    if n < 2:
        return True

    prev = arr[0]
    for i from 1 <= i < n:
        cur = arr[i]
        if cur < prev:
            return False
        prev = cur
    return True

"""

map_indices_template = """@cython.wraparound(False)
@cython.boundscheck(False)
cpdef map_indices_%(name)s(ndarray[%(c_type)s] index):
    '''
    Produce a dict mapping the values of the input array to their respective
    locations.

    Example:
        array(['hi', 'there']) --> {'hi' : 0 , 'there' : 1}

    Better to do this with Cython because of the enormous speed boost.
    '''
    cdef Py_ssize_t i, length
    cdef dict result = {}

    length = len(index)

    for i from 0 <= i < length:
        result[index[i]] = i

    return result

"""

# name, ctype, capable of holding NA
function_list = [
    ('float64', 'float64_t', True),
    ('object', 'object', True),
    ('int32', 'int32_t', False),
    ('int64', 'int64_t', False),
    ('bool', 'uint8_t', False)
]

def generate_from_template(template, ndim=1):
    output = StringIO()
    for name, c_type, can_hold_na in function_list:
        if ndim == 1:
            na_action = set_na if can_hold_na else raise_on_na
        elif ndim == 2:
            na_action = set_na_2d if can_hold_na else raise_on_na
        func = template % {'name' : name, 'c_type' : c_type,
                           'na_action' : na_action}
        output.write(func)
    return output.getvalue()

def generate_take_cython_file(path='generated.pyx'):
    with open(path, 'w') as f:
        print >> f, generate_from_template(map_indices_template)
        print >> f, generate_from_template(merge_indexer_template)
        print >> f, generate_from_template(pad_template)
        print >> f, generate_from_template(backfill_template)
        print >> f, generate_from_template(take_1d_template)
        print >> f, generate_from_template(take_2d_axis0_template, ndim=2)
        print >> f, generate_from_template(take_2d_axis1_template, ndim=2)
        print >> f, generate_from_template(is_monotonic_template)

if __name__ == '__main__':
    generate_take_cython_file()
