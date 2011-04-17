from numpy cimport ndarray, int32_t, float64_t
cimport numpy as np

cimport cython

import numpy as np
import sys

ctypedef Py_ssize_t pyst

#-------------------------------------------------------------------------------
# Preamble stuff

cdef inline int int_max(int a, int b): return a if a >= b else b
cdef inline int int_min(int a, int b): return a if a <= b else b

cdef float64_t __add(float64_t a, float64_t b):
    return a + b
cdef float64_t __sub(float64_t a, float64_t b):
    return a - b
cdef float64_t __div(float64_t a, float64_t b):
    return a / b
cdef float64_t __mul(float64_t a, float64_t b):
    return a * b
cdef float64_t __eq(float64_t a, float64_t b):
    return a == b
cdef float64_t __ne(float64_t a, float64_t b):
    return a != b
cdef float64_t __lt(float64_t a, float64_t b):
    return a < b
cdef float64_t __gt(float64_t a, float64_t b):
    return a > b
cdef float64_t __pow(float64_t a, float64_t b):
    return a ** b

ctypedef float64_t (* double_func)(float64_t a, float64_t b)

#-------------------------------------------------------------------------------

cdef class SparseIndex:
    pass

cdef class DenseIndex(SparseIndex):

    cdef readonly:
        pyst length, npoints
        ndarray indices

    cdef:
        int32_t* indp

    def __init__(self, pyst length, indices):
        self.length = length
        self.indices = np.ascontiguousarray(indices, dtype=np.int32)

        self.indp = <int32_t*> self.indices.data

    def __repr__(self):
        output = 'sparse.DenseIndex\n'
        output += 'Indices: %s\n' % repr(self.indices)
        return output

    def to_dense(self):
        return self

    def to_block(self):
        pass

    cpdef intersect(self, SparseIndex):
        pass

#-------------------------------------------------------------------------------
# BlockIndex

cdef class BlockIndex(SparseIndex):
    '''

    '''

    cdef readonly:
        pyst nblocks, npoints, length
        ndarray blocs, blengths

    cdef:
        int32_t* locbuf, *lenbuf

    def __init__(self, length, blocs, blengths):

        self.blocs = np.ascontiguousarray(blocs, dtype=np.int32)
        self.blengths = np.ascontiguousarray(blengths, dtype=np.int32)

        # in case we need
        self.locbuf = <int32_t*> self.blocs.data
        self.lenbuf = <int32_t*> self.blengths.data

        self.length = length
        self.nblocks = len(self.blocs)
        self.npoints = self.blengths.sum()

        # self.block_start = blocs
        # self.block_end = blocs + blengths

        self.check_integrity()

    def __repr__(self):
        output = 'sparse.BlockIndex\n'
        output += 'Block locations: %s\n' % repr(self.blocs)
        output += 'Block lengths: %s\n' % repr(self.blengths)

        return output

    cpdef check_integrity(self):
        '''
        Check:
        - Locations are in ascending order
        - No overlapping blocks
        - Blocks to not start after end of index, nor extend beyond end
        '''
        cdef:
            pyst i
            ndarray[int32_t, ndim=1] blocs, blengths

        blocs = self.blocs
        blengths = self.blengths

        if len(blocs) != len(blengths):
            raise ValueError('block bound arrays must be same length')

        for i from 0 <= i < self.nblocks:
            if i > 0:
                if blocs[i] <= blocs[i-1]:
                    raise ValueError('Locations not in ascending order')

            if i < self.nblocks - 1:
                if blocs[i] + blengths[i] > blocs[i + 1]:
                    raise ValueError('Block %d overlaps' % i)
            else:
                if blocs[i] + blengths[i] > self.length:
                    raise ValueError('Block %d extends beyond end' % i)

            # no zero-length blocks
            if self.blengths[i] == 0:
                raise ValueError('Zero-length block %d' % i)

    def to_block(self):
        return self

    def to_dense(self):
        cdef:
            pyst i = 0, j, b
            int32_t offset
            ndarray[int32_t, ndim=1] indices

        indices = np.empty(self.npoints, dtype=np.int32)

        for b from 0 <= b < self.nblocks:
            offset = self.locbuf[b]

            for j from 0 <= j < self.lenbuf[b]:
                indices[i] = offset + j
                i += 1

        return DenseIndex(self.length, indices)

    cpdef BlockIndex intersect(self, BlockIndex other):
        return block_intersect(self, other)

cdef BlockIndex block_intersect(BlockIndex x, BlockIndex y):
    cdef:
        pyst out_length
        ndarray[int32_t, ndim=1] xloc, xlen, yloc, ylen

        list out_blocs = []
        list out_blengths = []

        pyst xi = 0, yi = 0
        int32_t cur_loc, cur_length, xend, yend, diff

    # unwise? should enforce same length?
    out_length = int_max(x.length, y.length)

    xloc = x.blocs
    xlen = x.blengths
    yloc = y.blocs
    ylen = y.blengths

    while True:
        # we are done (or possibly never began)
        if xi >= x.nblocks or yi >= y.nblocks:
            break

        # completely symmetric...would like to avoid code dup but oh well
        if xloc[xi] >= yloc[yi]:
            cur_loc = xloc[xi]
            diff = xloc[xi] - yloc[yi]

            if ylen[yi] - diff <= 0:
                # have to skip this block
                yi += 1
                continue

            if ylen[yi] - diff < xlen[xi]:
                # take end of y block, move onward
                cur_length = ylen[yi] - diff
                yi += 1
            else:
                # take end of x block
                cur_length = xlen[xi]
                xi += 1

        else: # xloc[xi] < yloc[yi]
            cur_loc = yloc[yi]
            diff = yloc[yi] - xloc[xi]

            if xlen[xi] - diff <= 0:
                # have to skip this block
                xi += 1
                continue

            if xlen[xi] - diff < ylen[yi]:
                # take end of x block, move onward
                cur_length = xlen[xi] - diff
                xi += 1
            else:
                # take end of y block
                cur_length = ylen[yi]
                yi += 1

        out_blocs.append(cur_loc)
        out_blengths.append(cur_length)

    return BlockIndex(x.length, out_blocs, out_blengths)

#-------------------------------------------------------------------------------
# SparseVector

cdef class SparseVector:
    '''
    Data structure for storing sparse representation of floating point data

    Parameters
    ----------
    '''

    cdef readonly:
        pyst length
        ndarray values

    cdef public:
        SparseIndex index
        object fill_value

    cdef:
        float64_t* vbuf

    def __init__(self, ndarray values, SparseIndex index, fill_value=None):
        self.values = np.ascontiguousarray(values, dtype=np.float64)
        self.vbuf = <float64_t*> self.values.data

        self.length = len(values)
        self.fill_value = fill_value

    def __repr__(self):
        # just for devel...
        output = 'sparse.SparseVector\n'
        output += 'Values: %s\n' % repr(self.values)
        output += '%s\n' % repr(self.index)
        return output

    cpdef reindex(self):
        pass

    def __add__(self, other):
        return self.add(other)
    def __sub__(self, other):
        return self.sub(other)
    def __mul__(self, other):
        return self.mul(other)
    def __div__(self, other):
        return self.div(other)

    cpdef add(self, other):
        return self._combine_vector(other, __add)

    cpdef sub(self, other):
        return self._combine_vector(other, __sub)

    cpdef mul(self, other):
        return self._combine_vector(other, __mul)

    cpdef div(self, other):
        return self._combine_vector(other, __div)

    cdef SparseVector _combine_scalar(self, float64_t other, object op):
        new_values = op(self.values, other)
        return SparseVector(new_values, self.index)

    cdef SparseVector _combine_vector(self, SparseVector other, double_func op):
        if isinstance(self.index, BlockIndex):
            return block_op(self, other, op)
        elif isinstance(self.index, DenseIndex):
            return dense_op(self, other, op)

# faster to convert everything to dense?

cdef SparseVector block_op(SparseVector x, SparseVector y, double_func op):
    cdef:
        BlockIndex xindex, yindex, out_index
        int xi = 0, yi = 0, out_i = 0 # fp buf indices
        int xbp, ybp, obp # block positions
        pyst xblock = 0, yblock = 0, outblock = 0 # block numbers

        SparseVector out

    xindex = x.index.to_block()
    yindex = y.index.to_block()

    # need to do this first to know size of result array
    out_index = x.index.intersect(y.index).to_block()

    outarr = np.empty(out_index.npoints, dtype=np.float64)
    out = SparseVector(outarr, out_index)

    # walk the two SparseVectors, adding matched locations...
    for out_i from 0 <= out_i < out.length:

        # I have a feeling this is inefficient

        # walk x
        while xindex.locp[xblock] + xbp < out_index.locp[outblock] + obp:
            xbp += 1
            xi += 1
            if xbp == xindex.lenp[xblock]:
                xblock += 1
                xbp = 0

        # walk y
        while yindex.locp[yblock] + ybp < out_index.locp[outblock] + obp:
            ybp += 1
            yi += 1
            if ybp == yindex.lenp[yblock]:
                yblock += 1
                ybp = 0

        out.vbuf[out_i] = op(x.vbuf[xi], y.vbuf[yi])

        # advance. strikes me as too complicated
        xi += 1
        yi += 1

        xbp += 1
        if xbp == xindex.lenp[xblock]:
            xblock += 1
            xbp = 0

        ybp += 1
        if ybp == yindex.lenp[yblock]:
            yblock += 1
            ybp = 0

        obp += 1
        if obp == out_index.lenp[oblock]:
            oblock += 1
            obp = 0

    return out

cdef SparseVector dense_op(SparseVector x, SparseVector y, double_func op):
    cdef:
        DenseIndex xindex, yindex, out_index
        int xi = 0, yi = 0, out_i = 0 # fp buf indices

        SparseVector out

    xindex = x.index.to_dense()
    yindex = y.index.to_dense()

    # need to do this first to know size of result array
    out_index = x.index.intersect(y.index).to_dense()
    outarr = np.empty(out_index.npoints, dtype=np.float64)
    out = SparseVector(outarr, out_index)

    # walk the two SparseVectors, adding matched locations...
    for out_i from 0 <= out_i < out.length:

        # walk x
        while xindex.indp[xi] < out_index.indp[out_i]:
            xi += 1

        # walk y
        while yindex.indp[yi] < out_index.indp[out_i]:
            yi += 1

        out.vbuf[out_i] = op(x.vbuf[xi], y.vbuf[yi])

        # advance
        xi += 1
        yi += 1

    return out
