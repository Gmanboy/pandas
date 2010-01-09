# pylint: disable-msg=E1101,E1103
# pylint: disable-msg=W0212,W0703,W0231,W0622

from cStringIO import StringIO
import sys

from numpy import NaN
import numpy as np

from pandas.core.common import _pfixed, _pickle_array, _unpickle_array
from pandas.core.frame import DataFrame
from pandas.core.index import Index, NULL_INDEX
from pandas.core.series import Series
from pandas.lib.tseries import isnull, notnull
import pandas.core.datetools as datetools
import pandas.lib.tseries as tseries

#-------------------------------------------------------------------------------
# DataMatrix class

class DataMatrix(DataFrame):
    """
    Matrix version of DataFrame, optimized for cross-section operations,
    numerical computation, and other operations that do not require the
    frame to change size.

    Parameters
    ----------
    data : numpy ndarray or dict of Series
        Constructor can understand various kinds of inputs
    index : Index or array-like
        Index to use for resulting frame (optional if provided dict of Series)
    columns : Index or array-like
    dtype : dtype, default=float
        Data type to use

    Notes
    -----
    Transposing is much faster in this regime, as is calling getXS, so please
    take note of this.
    """
    objects = None
    def __init__(self, data=None, index=None, columns=None, dtype=None,
                 objects=None):

        def handleDict(data, index, columns, objects, dtype):
            """
            Segregate Series based on type and coerce into matrices.

            Needs to handle a lot of exceptional cases.
            """
            if len(data) == 0:
                if index is None:
                    index = NULL_INDEX
                values = np.empty((len(index), 0), dtype=dtype)
                columns = NULL_INDEX
            else:
                if index is None:
                    s = data.values()[0]
                    if isinstance(s, Series):
                        index = s.index
                    else:
                        index = Index(np.arange(len(s)))

                if columns is not None:
                    if len(columns) != len(data):
                        raise Exception('Supplied columns does not match dict!')

                if not isinstance(index, Index):
                    index = Index(index)

                objectDict = {}
                if objects is not None and isinstance(objects, dict):
                    objectDict.update(objects)

                valueDict = {}
                for k, v in data.iteritems():
                    # Forces homogoneity
                    if isinstance(v, Series):
                        v = v.reindex(index)
                    else:
                        assert(len(v) == len(index))
                        v = Series(v, index=index)

                    if issubclass(v.dtype.type, (np.bool_, float, int)):
                        valueDict[k] = v
                    else:
                        objectDict[k] = v

                if columns is None:
                    columns = Index(sorted(valueDict))
                    objectColumns = Index(sorted(objectDict))
                else:
                    objectColumns = Index([c for c in columns if c in objectDict])
                    columns = Index([c for c in columns if c in valueDict])

                if len(valueDict) == 0:
                    dtype = np.object_
                    valueDict = objectDict
                    columns = objectColumns
                else:
                    dtype = np.float_
                    if len(objectDict) > 0:
                        new_objects = DataMatrix(objectDict,
                                                 dtype=np.object_,
                                                 index=index,
                                                 columns=objectColumns)
                        if isinstance(objects, DataMatrix):
                            objects = objects.leftJoin(new_objects)
                        else:
                            objects = new_objects

                values = np.empty((len(index), len(columns)), dtype=dtype)

                for i, col in enumerate(columns):
                    values[:, i] = valueDict[col]

            return index, columns, values, objects

        if isinstance(data, dict):
            index, columns, values, objects = handleDict(data, index,
                                                         columns, objects,
                                                         dtype)
        elif isinstance(data, np.ndarray):
            if data.ndim == 1:
                N = data.shape[0]
                if N == 0:
                    data = data.reshape((data.shape[0], 0))
                else:
                    data = data.reshape((data.shape[0], 1))

            if issubclass(data.dtype.type, (np.str_, np.object_)):
                values = np.asarray(data, dtype=object)
            else:
                # We're allowing things to be boolean
                values = np.asarray(data)

        elif data is None:
            if index is None:
                N = 0
                index = NULL_INDEX
            else:
                N = len(index)

            if columns is None:
                K = 0
                columns = NULL_INDEX
            else:
                K = len(columns)

            values = np.empty((N, K), dtype=dtype)
            values[:] = NaN

        else:
            raise Exception('DataMatrix constructor not properly called!')

        if objects is not None:
            if isinstance(objects, DataMatrix):
                if objects.index is not index:
                    self.objects = objects.reindex(index)
            else:
                objects = DataMatrix(objects, index=index)

        self.values = values
        self.index = index
        self.columns = columns
        self.objects = objects

    def __getstate__(self):
        if self.objects is not None:
            objects = self.objects._matrix_state(pickle_index=False)
        else:
            objects = None

        state = self._matrix_state()

        return (state, objects)

    def _matrix_state(self, pickle_index=True):
        columns = _pickle_array(self.columns)
        index = _pickle_array(self.index) if pickle_index else None

        return self.values, index, columns

    def __setstate__(self, state):
        (vals, idx, cols), object_state = state

        self.values = vals
        self.index = _unpickle_array(idx)
        self.columns = _unpickle_array(cols)

        if object_state:
            ovals, _, ocols = object_state
            self.objects = DataMatrix(_unpickle_array(ovals),
                                      index=self.index,
                                      columns=_unpickle_array(ocols))
        else:
            self.objects = None

    # Because of DataFrame property
    values = None
#-------------------------------------------------------------------------------
# Alternate constructors

    @classmethod
    def fromDict(cls, inputDict=None, castFloat=True, **kwds):
        """
        Convert a two-level tree representation of a series or time series
        to a DataMatrix.

        tree is structured as:
            {'col1' : {
                idx1 : value1,
                ...
                idxn : valueN
                    },
            ...}
        e.g. tree['returns'][curDate] --> return value for curDate

        Parameters
        ----------
        input : dict object
            Keys become column names of returned frame
        kwds : optionally provide arguments as keywords

        Examples
        --------
        df1 = DataMatrix.fromDict(myDict)
        df2 = DataMatrix.fromDict(A=seriesA, B=seriesB)
        """
        if inputDict is None:
            inputDict = {}
        else:
            if not hasattr(inputDict, 'iteritems'):
                raise Exception('Input must be a dict or dict-like!')
            inputDict = inputDict.copy()

        inputDict.update(kwds)

        # Get set of indices
        indices = set([])
        for branch in inputDict.values():
            indices = indices | set(branch.keys())

        index = Index(sorted(indices))
        # Convert to Series
        series = {}
        for col, mapping in inputDict.iteritems():
            if not isinstance(mapping, Series):
                mapping = Series.fromDict(mapping, castFloat=castFloat)
            series[col] = mapping.reindex(index)

        return DataMatrix(series, index=index)

    @classmethod
    def fromMatrix(cls, mat, colNames, rowNames):
        """
        Compatibility method for operations in DataFrame that use
        fromMatrix.

        Parameters
        ----------
        mat : ndarray
            Dimension T x N
        colNames : iterable
            Dimension N
        rowNames : iterable
            Dimension T

        Returns
        -------
        DataMatrix

        See also
        --------
        DataFrame.fromMatrix
        """
        rows, cols = mat.shape
        try:
            assert(rows == len(rowNames))
            assert(cols == len(colNames))
        except AssertionError:
            raise Exception('Dimensions do not match: %s, %s, %s' %
                            (mat.shape, len(rowNames), len(colNames)))

        index = Index(rowNames)
        colIndex = Index(colNames)

        return DataMatrix(mat, index=index, columns=colIndex)

#-------------------------------------------------------------------------------
# Outputting

    def toCSV(self, path, nanRep='', writeMode='wb', index=True,
              header=True, cols=None, verbose=False):
        """
        Write the DataMatrix to a CSV file

        Parameters
        ----------
        path : string
            Output file path
        nanRep : string, default=''
            Appearance of NaN values in output
        index : boolean, default=True
            Prints index if True
        header : boolean, default=True
            Prints header if True
        cols : list of strings
            Prints the values in order specified by cols.
            By default, prints all columns in lexicographical order.
        """
        f = open(path, writeMode)

        if cols is None:
            cols = self.cols()
        series = self._series

        if header:
            if index:
                f.write(',')
            f.write(','.join([str(c) for c in cols]))
            f.write('\n')

        for idx in self.index:
            if index:
                f.write(str(idx) + ',')

            for col in cols:
                val = series[col][idx]
                if isnull(val):
                    val = nanRep
                else:
                    val = str(val)
                f.write(val + ',')
            f.write('\n')

        f.close()

        if verbose: # pragma: no cover
            print 'CSV file written successfully: %s' % path

    def toString(self, buffer=sys.stdout, verbose=False,
                 columns=None, colSpace=15, formatters=None,
                 float_format=None):
        """
        Output a string version of this DataMatrix
        """
        formatters = formatters or {}

        if columns is None:
            columns = self.columns
            values = self.values
            if self.objects:
                columns = list(columns) + list(self.objects.columns)
                values = np.column_stack((values.astype(object),
                                          self.objects.values))
        else:
            columns = [c for c in columns if c in self]
            values = self.asMatrix(columns)

        ident = lambda x: x

        idxSpace = max([len(str(idx)) for idx in self.index]) + 4

        if len(self.cols()) == 0:
            buffer.write('DataMatrix is empty!\n')
            buffer.write(self.index.__repr__())
        else:
            buffer.write(_pfixed('', idxSpace))
            for h in columns:
                buffer.write(_pfixed(h, colSpace))
            buffer.write('\n')

            for i, idx in enumerate(self.index):
                buffer.write(_pfixed(idx, idxSpace))
                for j, col in enumerate(columns):
                    formatter = formatters.get(col, ident)
                    buffer.write(_pfixed(formatter(values[i, j]), colSpace,
                                         float_format=float_format))
                buffer.write('\n')

    def info(self, buffer=sys.stdout):
        """
        Concise summary of a DataMatrix, used in __repr__ when very large.
        """
        print >> buffer, 'Index: %s entries' % len(self.index),
        if len(self.index) > 0:
            print >> buffer, ', %s to %s' % (self.index[0], self.index[-1])
        else:
            print >> buffer, ''

        if len(self.columns) == 0:
            print >> buffer, 'DataMatrix is empty!'
            print >> buffer, repr(self.index)
            return

        print >> buffer, 'Data columns:'
        space = max([len(str(k)) for k in self.cols()]) + 4

        counts = self.apply(notnull).sum(0)
        if self.objects is not None:
            counts = counts.append(self.objects.apply(notnull).sum(0))

        columns = []
        for j, col in enumerate(self.columns):
            columns.append('%s%d  non-null values' %
                           (_pfixed(col, space), counts[j]))

        if self.objects is not None and len(self.objects.columns) > 0:
            n = len(self.objects.index)
            for col in self.objects:
                line = '%s%d  non-null values' % (_pfixed(col, space), n)
                columns.append(line)

        columns.sort()

        dtypeLine = ''

        nf = len(self.columns)
        df = self.values.dtype
        if self.objects is not None:
            no = len(self.objects.columns)
            do = self.objects.values.dtype
            dtypeLine = '\ndtypes: %s(%d), %s(%d)' % (df, nf, do, no)
        else:
            dtypeLine = '\ndtype: %s(%d)' % (df, nf)

        buffer.write('\n'.join(columns) + dtypeLine)

#-------------------------------------------------------------------------------
# Properties for index and columns

    _columns = None
    def _get_columns(self):
        return self._columns

    def _set_columns(self, cols):
        if cols is None:
            if self.values is not None and self.values.shape[1] > 0:
                raise Exception('Columns cannot be None here!')
            else:
                self._columns = NULL_INDEX
                return

        if len(cols) != self.values.shape[1]:
            raise Exception('Columns length %d did not match values %d!' %
                            (len(cols), self.values.shape[1]))

        if not isinstance(cols, Index):
            cols = Index(cols)

        self._columns = cols

    columns = property(fget=_get_columns, fset=_set_columns)

    def _set_index(self, index):
        if index is None:
            if self.values is not None and self.values.shape[0] > 0:
                raise Exception('Index cannot be None here!')
            else:
                self._index = NULL_INDEX
                return

        if len(index) > 0:
            if len(index) != self.values.shape[0]:
                raise Exception('Index length %d did not match values %d!' %
                                (len(index), self.values.shape[0]))

        if not isinstance(index, Index):
            index = Index(index)

        self._index = index

        if self.objects is not None:
            self.objects._index = index

    def _get_index(self):
        return self._index

    index = property(fget=_get_index, fset=_set_index)

#-------------------------------------------------------------------------------
# "Magic methods"

    def __nonzero__(self):
        N, K = self.values.shape
        if N == 0 or K == 0:
            if self.objects is None:
                return False
            else:
                return self.objects.__nonzero__()
        else:
            return True

    def __neg__(self):
        mycopy = self.copy()
        mycopy.values = -mycopy.values
        return mycopy

    def __repr__(self):
        """Return a string representation for a particular DataMatrix"""
        buffer = StringIO()

        if self.values is None or len(self.columns) == 0:
            buffer.write('Empty DataMatrix\nIndex: %s' % repr(self.index))
        elif 0 < len(self.index) < 500 and self.values.shape[1] < 10:
            self.toString(buffer=buffer)
        else:
            print >> buffer, str(self.__class__)
            self.info(buffer=buffer)

        return buffer.getvalue()

    def __getitem__(self, item):
        """
        Retrieve column, slice, or subset from DataMatrix.

        Possible inputs
        ---------------
        single value : retrieve a column as a Series
        slice : reindex to indices specified by slice
        boolean vector : like slice but more general, reindex to indices
          where the input vector is True

        Examples
        --------
        column = dm['A']

        dmSlice = dm[:20] # First 20 rows

        dmSelect = dm[dm.count(axis=1) > 10]

        Note
        ----
        This is a magic method. Do NOT call explicity.
        """
        if isinstance(item, slice):
            indexRange = self.index[item]
            return self.reindex(indexRange)

        elif isinstance(item, np.ndarray):
            if len(item) != len(self.index):
                raise Exception('Item wrong length %d instead of %d!' %
                                (len(item), len(self.index)))
            newIndex = self.index[item]
            return self.reindex(newIndex)
        else:
            if self.objects is not None and item in self.objects:
                return self.objects[item]
            else:
                return self._getSeries(item)

    _dataTypes = [np.float_, np.bool_, np.int_]
    def __setitem__(self, key, value):
        """
        Add series to DataMatrix in specified column.

        If series is a numpy-array (not a Series/TimeSeries), it must be the
        same length as the DataMatrix's index or an error will be thrown.

        Series/TimeSeries will be conformed to the DataMatrix's index to
        ensure homogeneity.
        """
        import bisect

        isObject = False
        if hasattr(value, '__iter__'):
            if isinstance(value, Series):
                value = np.asarray(value.reindex(self.index))

            else:
                assert(len(value) == len(self.index))

                if not isinstance(value, np.ndarray):
                    value = np.array(value)
                    if value.dtype.type == np.str_:
                        value = np.array(value, dtype=object)
        else:
            try:
                value = np.repeat(value, len(self.index))
            except Exception:
                raise Exception('Could not put %s in the matrix!' % value)

        if value.dtype not in self._dataTypes:
            isObject = True

        if len(self.columns) == 0:
            if isObject:
                if self.objects is None:
                    self.objects = DataMatrix({key : value},
                                              index=self.index)
                else:
                    self.objects[key] = value
            else:
                self.values = value.reshape((len(value), 1)).copy()
                self.columns = Index([key])
            return

        if self.values.dtype == np.object_:
            if key in self.columns:
                loc = self.columns.indexMap[key]
                self.values[:, loc] = value
            elif len(self.columns) == 0:
                self.values = value.reshape((len(value), 1)).copy()
                self.columns = Index([key])
            else:
                try:
                    loc = bisect.bisect_right(self.columns, key)
                except TypeError:
                    loc = len(self.columns)

                if loc == self.values.shape[1]:
                    newValues = np.c_[self.values, value]
                    newColumns = Index(np.concatenate((self.columns, [key])))
                elif loc == 0:
                    newValues = np.c_[value, self.values]
                    newColumns = Index(np.concatenate(([key], self.columns)))
                else:
                    newValues = np.c_[self.values[:, :loc], value,
                                      self.values[:, loc:]]
                    toConcat = (self.columns[:loc], [key], self.columns[loc:])
                    newColumns = Index(np.concatenate(toConcat))
                self.values = newValues
                self.columns = newColumns
        else:
            if key in self.columns:
                loc = self.columns.indexMap[key]
                self.values[:, loc] = value
            elif isObject:
                if self.objects is None:
                    self.objects = DataMatrix({key : value},
                                              index=self.index)
                else:
                    self.objects[key] = value
            elif len(self.columns) == 0:
                self.values = value.reshape((len(value), 1)).astype(np.float)
                self.columns = Index([key])
            else:
                try:
                    loc = bisect.bisect_right(self.columns, key)
                except TypeError:
                    loc = len(self.columns)

                if loc == self.values.shape[1]:
                    newValues = np.c_[self.values, value]
                    newColumns = Index(np.concatenate((self.columns, [key])))
                elif loc == 0:
                    newValues = np.c_[value, self.values]
                    newColumns = Index(np.concatenate(([key], self.columns)))
                else:
                    newValues = np.c_[self.values[:, :loc], value,
                                      self.values[:, loc:]]
                    toConcat = (self.columns[:loc], [key], self.columns[loc:])
                    newColumns = Index(np.concatenate(toConcat))
                self.values = newValues
                self.columns = newColumns

    def __delitem__(self, key):
        """
        Delete column from DataMatrix
        """
        if key in self.columns:
            loc = self.columns.indexMap[key]
            T, N = self.values.shape
            if loc == N:
                newValues = self.values[:, :loc]
                newColumns = self.columns[:loc]
            else:
                newValues = np.c_[self.values[:, :loc], self.values[:, loc+1:]]
                newColumns = Index(np.concatenate((self.columns[:loc],
                                                   self.columns[loc+1:])))
            self.values = newValues
            self.columns = newColumns

        if self.objects is not None and key in self.objects:
            del self.objects[key]

    def __iter__(self):
        """Iterate over columns of the frame."""
        return iter(self.columns)

    def __contains__(self, key):
        """True if DataMatrix has this column"""
        hasCol = key in self.columns
        if hasCol:
            return True
        else:
            if self.objects is not None and key in self.objects:
                return True
            return False

    def iteritems(self):
        return self._series.iteritems()

#-------------------------------------------------------------------------------
# Helper methods

    # For DataFrame compatibility
    def _getSeries(self, item=None, loc=None):
        if loc is None:
            try:
                loc = self.columns.indexMap[item]
            except KeyError:
                raise Exception('%s not here!' % item)
        return Series(self.values[:, loc], index=self.index)

    def _getSeriesDict(self):
        series = {}
        for i, col in enumerate(self.columns):
            series[col] = self._getSeries(loc=i)
        if self.objects is not None:
            for i, col in enumerate(self.objects.columns):
                series[col] = self.objects._getSeries(loc=i)

        return series
    _series = property(_getSeriesDict)

    def _firstTimeWithNValues(self):
        # Need to test this!
        N = len(self._series)
        selector = (self.count(1) == N)
        if not selector.any():
            raise Exception('No time has %d values!' % N)

        return self.index[selector][0]

    def _combineFrame(self, other, func):
        """
        Methodology, briefly
        - Really concerned here about speed, space

        - Get new index
        - Reindex to new index
        - Determine newColumns and commonColumns
        - Add common columns over all (new) indices
        - Fill to new set of columns

        Could probably deal with some Cython action in here at some point
        """
        if self.index.equals(other.index):
            newIndex = self.index
            myReindex = self
            hisReindex = other
        else:
            newIndex = self.index.union(other.index)
            myReindex = self.reindex(newIndex)
            hisReindex = other.reindex(newIndex)

        if not self and not other:
            return DataMatrix(index=newIndex)
        elif not self:
            return other * NaN
        elif not other:
            return self * NaN

        myValues = myReindex.values
        if self.columns.equals(other.columns):
            newCols = self.columns
            commonCols = self.columns
        else:
            newCols = self.columns.union(other.columns)
            commonCols = self.columns.intersection(other.columns)
        hisValues = hisReindex.values
        hisCols = hisReindex.columns

        if len(newCols) == len(commonCols):
            resultMatrix = func(myValues, hisValues)
        else:
            T, N = len(newIndex), len(newCols)
            resultMatrix = np.empty((T, N), dtype=self.values.dtype)
            resultMatrix.fill(NaN)

            myIndexer = [self.columns.indexMap[idx] for idx in commonCols]
            hisIndexer =  [hisCols.indexMap[idx] for idx in commonCols]
            resultIndexer = [newCols.indexMap[idx] for idx in commonCols]

            resultMatrix[:, resultIndexer] = func(myValues[:, myIndexer],
                                                  hisValues[:, hisIndexer])

        # TODO: deal with objects
        return DataMatrix(resultMatrix, index=newIndex, columns=newCols)

    def _combineSeries(self, other, func):
        newIndex = self.index
        newCols = self.columns
        if self.index._allDates and other.index._allDates:
            # Operate row-wise
            if self.index.equals(other.index):
                newIndex = self.index
            else:
                newIndex = self.index + other.index

            if not self:
                return DataMatrix(index=newIndex)

            other = other.reindex(newIndex).view(np.ndarray)
            myReindex = self.reindex(newIndex)
            resultMatrix = func(myReindex.values.T, other).T
        else:
            if len(other) == 0:
                return self * NaN

            newCols = self.columns.union(other.index)

            # Operate column-wise
            this = self.reindex(columns=newCols)
            other = other.reindex(newCols).values()

            resultMatrix = func(this.values, other)

        # TODO: deal with objects
        return DataMatrix(resultMatrix, index=newIndex, columns=newCols)

    def _combineFunc(self, other, func):
        """
        Combine DataMatrix objects with other Series- or DataFrame-like objects

        This is the core method used for the overloaded arithmetic methods

        Result hierarchy
        ----------------
        DataMatrix + DataFrame --> DataMatrix
        DataMatrix + DataMatrix --> DataMatrix
        DataMatrix + Series --> DataMatrix
        DataMatrix + constant --> DataMatrix

        The reason for 'upcasting' the result is that if addition succeed,
        we can assume that the input DataFrame was homogeneous.
        """
        newIndex = self.index
        if isinstance(other, DataFrame):
            return self._combineFrame(other, func)

        elif isinstance(other, Series):
            return self._combineSeries(other, func)

        else:
            if not self:
                return self

            # Constant of some kind
            newCols = self.columns
            try:
                resultMatrix = func(self.values, other)
            except Exception:
                raise Exception('Bad operator value: %s' % other)

        # TODO: deal with objects
        return DataMatrix(resultMatrix, index=newIndex, columns=newCols)

#-------------------------------------------------------------------------------
# Public methods

    def asMatrix(self, columns=None):
        """
        Convert the DataMatrix to its Numpy-array matrix representation

        Columns are presented in sorted order unless a specific list
        of columns is provided.

        Parameters
        ----------
        columns : list-like
            columns to use in producing matrix, must all be contained

        Returns
        -------
        ndarray
        """
        if columns is None:
            values = self.values.copy()

            if self.objects:
                values = np.column_stack((values, self.objects.values))

            return values
        else:
            if not isinstance(columns, Index):
                columns = Index(columns)

            values = self.values
            order = self.columns

            if self.objects:
                idxMap = self.objects.columns.indexMap
                indexer = [idxMap[col] for col in columns if col in idxMap]

                obj_values = self.objects.values.take(indexer, axis=1)

                values = np.column_stack((values, obj_values))
                order = Index(np.concatenate((order, self.objects.columns)))

                # now put in the right order

            values = _reorder_columns(values, order, columns)

            return values

    def cols(self):
        """Return sorted list of frame's columns"""
        if self.objects is not None and len(self.objects.columns) > 0:
            return list(self.columns.union(self.objects.columns))
        else:
            return list(self.columns)

    def copy(self):
        """
        Make a copy of this DataMatrix
        """
        if self.objects:
            objects = self.objects.copy()
        else:
            objects = None

        return DataMatrix(self.values.copy(), index=self.index,
                          columns=self.columns, objects=objects)

    def cumsum(self, axis=0):
        """
        Return DataMatrix of cumulative sums over requested axis.

        Parameters
        ----------
        axis : {0, 1}
            0 for row-wise, 1 for column-wise

        Returns
        -------
        y : DataMatrix
        """
        y = np.array(self.values, subok=True)
        if not issubclass(y.dtype.type, np.int_):
            y[np.isnan(self.values)] = 0
        theSum = y.cumsum(axis)

        return DataMatrix(theSum, index=self.index,
                          columns=self.columns, objects=self.objects)

    def dropEmptyRows(self, specificColumns=None):
        """
        Return DataMatrix with rows omitted containing ALL NaN values
        for optionally specified set of columns.

        Parameters
        ----------
        specificColumns : list-like, optional keyword
            Columns to consider in removing NaN values. As a typical
            application, you might provide the list of the columns involved in
            a regression to exclude all the missing data in one shot.

        Returns
        -------
        DataMatrix with rows containing any NaN values deleted
        """
        if specificColumns:
            theCount = self.filterItems(specificColumns).count(axis=1)
        else:
            theCount = self.count(axis=1)

        return self.reindex(self.index[theCount > 0])

    def dropIncompleteRows(self, specificColumns=None, minObs=None):
        """
        Return DataFrame with rows omitted containing ANY NaN values for
        optionally specified set of columns.

        Parameters
        ----------
        minObs : int or None (default)
           Instead of requiring all the columns to have observations, require
           only minObs observations
        specificColumns : list-like, optional keyword
            Columns to consider in removing NaN values. As a typical
            application, you might provide the list of the columns involved in
            a regression to exlude all the missing data in one shot.

        Returns
        -------
        This DataFrame with rows containing any NaN values deleted
        """
        T, N = self.values.shape
        if specificColumns:
            cols = self.columns.intersection(specificColumns)
            theCount = self.filterItems(cols).count(axis=1)
            N = len(cols)
        else:
            theCount = self.count(axis=1)

        if minObs is None:
            minObs = N

        return self.reindex(self.index[theCount >= minObs])

    def fill(self, value=None, method='pad'):
        """
        Fill NaN values using the specified method.

        Member Series / TimeSeries are filled separately.

        Parameters
        ----------
        value : any kind (should be same type as array)
            Value to use to fill holes (e.g. 0)

        method : {'backfill', 'pad', None}
            Method to use for filling holes in new inde

        Returns
        -------
        DataMatrix with NaN's filled

        See also
        --------
        reindex, asfreq
        """
        if value is None:
            result = {}
            for col in self._series:
                series = self._series[col]
                filledSeries = series.fill(method=method, value=value)

                result[col] = filledSeries
            return DataMatrix(result, index=self.index, objects=self.objects)
        else:
            gotFloat = isinstance(value, (int, float))
            if gotFloat and self.values.dtype == np.float64:
                # Float type values
                if len(self.columns) == 0:
                    return self

                vals = self.values.copy()
                vals.flat[isnull(vals.ravel())] = value

                objectsToUse = None

                if self.objects is not None:
                    objectsToUse = self.objects.copy()

                return DataMatrix(vals, index=self.index, columns=self.columns,
                                  objects=objectsToUse)

            else:
                # Object type values
                if len(self.columns) == 0:
                    return self

                # XXX

                myCopy = self.copy()
                vals = myCopy.values
                vals = self.values.copy()
                vals.flat[isnull(vals.ravel())] = value

                return myCopy

    def getXS(self, key):
        """
        Returns a row from the DataMatrix as a Series object.

        Parameters
        ----------
        key : some index contained in the index

        Returns
        -------
        Series
        """
        if key not in self.index:
            raise Exception('No cross-section for %s' % key)

        loc = self.index.indexMap[key]
        theSlice = self.values[loc, :].copy()
        xsIndex = self.columns

        result = Series(theSlice, index=xsIndex)

        if self.objects is not None and len(self.objects.columns) > 0:
            result = result.append(self.objects.getXS(key))

        return result

    def merge(self, otherFrame, on=None):
        """
        Merge DataFrame or DataMatrix with this one on some many-to-one index

        Parameters
        ----------
        otherFrame : DataFrame
            Index should be similar to one of the columns in this one
        on : string
            Column name to use

        Examples
        --------
        This frame         Other frame
            c1                 q1
        a   1              0   v1
        b   0              1   v2
        c   1
        d   0
        """
        if len(otherFrame.index) == 0:
            return self

        if on not in self:
            raise Exception('%s column not contained in this frame!' % on)

        otherM = otherFrame.asMatrix()
        indexMap = otherFrame.index.indexMap

        fillVec, mask = tseries.getMergeVec(self[on], indexMap)

        tmpMatrix = otherM.take(fillVec, axis=0)
        tmpMatrix[-mask] = NaN

        seriesDict = dict((col, tmpMatrix[:, j])
                           for j, col in enumerate(otherFrame.columns))

        if getattr(otherFrame, 'objects'):
            objects = otherFrame.objects

            objM = objects.asMatrix()

            tmpMat = objM.take(fillVec, axis=0)
            tmpMat[-mask] = NaN
            objDict = dict((col, tmpMat[:, j])
                           for j, col in enumerate(objects.columns))

            seriesDict.update(objDict)

        filledFrame = DataFrame(data=seriesDict, index=self.index)

        return self.leftJoin(filledFrame)

    def _reindex_index(self, index, method):
        if index is self.index:
            return self.copy()

        if len(index) == 0:
            return DataMatrix(index=NULL_INDEX)

        if not isinstance(index, Index):
            index = Index(index)

        if len(self.index) == 0:
            return DataMatrix(index=index, columns=self.columns)

        fillVec, mask = tseries.getFillVec(self.index, index,
                                           self.index.indexMap,
                                           index.indexMap, method)

        tmpMatrix = self.values.take(fillVec, axis=0)
        tmpMatrix[-mask] = NaN

        if self.objects is not None and len(self.objects.columns) > 0:
            newObjects = self.objects.reindex(index)
        else:
            newObjects = None

        return DataMatrix(tmpMatrix, index=index,
                          columns=self.columns,
                          objects=newObjects)

    def _reindex_columns(self, columns):
        if len(columns) == 0:
            return DataMatrix(index=self.index)

        if not isinstance(columns, Index):
            columns = Index(columns)

        indexer, mask = tseries.getFillVec(self.columns, columns,
                                           self.columns.indexMap,
                                           columns.indexMap, '')

        newValues = self.values.take(indexer, axis=1)
        newValues[:, -mask] = NaN

        return DataMatrix(newValues, index=self.index, columns=columns,
                          objects=self.objects)

    @property
    def T(self):
        """
        Returns a DataMatrix with the rows/columns switched.
        """
        if self.objects is not None:
            objectsT = self.objects.values.T
            valuesT = self.values.T
            newValues = np.concatenate((valuesT, objectsT), axis=0)
            newIndex = Index(np.concatenate((self.columns,
                                             self.objects.columns)))

            return DataMatrix(newValues, index=newIndex, columns=self.index)
        else:
            return DataMatrix(data=self.values.T, index=self.columns,
                              columns=self.index)

    def shift(self, periods, offset=None, timeRule=None):
        """
        Shift the underlying series of the DataMatrix and Series objects within
        by given number (positive or negative) of periods.

        Parameters
        ----------
        periods : int (+ or -)
            Number of periods to move
        offset : DateOffset, optional
            Increment to use from datetools module
        timeRule : string
            Time rule to use by name

        Returns
        -------
        DataMatrix
        """
        if periods == 0:
            return self

        if timeRule is not None and offset is None:
            offset = datetools.getOffset(timeRule)

        N = len(self)

        if offset is None:
            newIndex = self.index
            indexer = np.zeros(N, dtype=int)
            if periods > 0:
                indexer[periods:] = np.arange(N - periods)
                newValues = self.values.take(indexer, axis=0)
                newValues[:periods] = NaN
            else:
                indexer[:periods] = np.arange(-periods, N)
                newValues = self.values.take(indexer, axis=0)
                newValues[periods:] = NaN
        else:
            offset = periods * offset
            newIndex = Index([x + offset for x in self.index])
            newValues = self.values.copy()

        if self.objects is not None:
            pass

        return DataMatrix(data=newValues, index=newIndex, columns=self.columns)

    def apply(self, func, axis=0):
        """
        Applies func to columns (Series) of this DataMatrix and returns either
        a DataMatrix (if the function produces another series) or a Series
        indexed on the column names of the DataFrame if the function produces
        a value.

        Parameters
        ----------
        func : function
            Function to apply to each column

        Examples
        --------

            >>> df.apply(numpy.sqrt) --> DataMatrix
            >>> df.apply(numpy.sum) --> Series

        N.B.: Do NOT use functions that might toy with the index.
        """
        if not len(self.cols()):
            return self

        results = {}

        if isinstance(func, np.ufunc):
            results = func(self.values)
        else:
            if axis == 0:
                target = self
            elif axis == 1:
                target = self.T

            results = dict([(k, func(target[k])) for k in target.columns])

        if isinstance(results, np.ndarray):
            return DataMatrix(data=results, index=self.index,
                              columns=self.columns, objects=self.objects)

        elif isinstance(results, dict):
            if isinstance(results.values()[0], np.ndarray):
                return DataMatrix(results, index=self.index,
                                  columns=self.columns,
                                  objects=self.objects)
            else:
                return Series.fromDict(results)
        else:
            raise Exception('Should not reach here')

    def applymap(self, func):
        """
        Apply a function to a DataMatrix that is intended to operate
        elementwise, i.e. like doing
            map(func, series) for each series in the DataMatrix

        Parameters
        ----------
        func : function
            Python function, returns a single value from a single value

        Note : try to avoid using this function if you can, very slow.
        """
        npfunc = np.frompyfunc(func, 1, 1)
        results = npfunc(self.values)
        try:
            results = results.astype(self.values.dtype)
        except Exception:
            return DataFrame.fromMatrix(results, self.columns, self.index)
        return DataMatrix(data=results, index=self.index, columns=self.columns)

    def append(self, otherFrame):
        if not otherFrame:
            return self
        if not self:
            return otherFrame
        if (isinstance(otherFrame, DataMatrix) and
            list(self.columns) == list(otherFrame.columns)):

            idx = Index(np.concatenate([self.index, otherFrame.index]))
            mat = np.vstack((self.values, otherFrame.values))
            dm = DataMatrix(mat, idx, self.columns)
            if otherFrame.objects is None:
                dm.objects = self.objects
            elif self.objects is None:
                dm.objects = otherFrame.objects
            else:
                dm.objects = self.objects.append(otherFrame.objects)
            return dm
        else:
            return super(DataMatrix, self).append(otherFrame)

    # TODO, works though.
    def outerJoin(self, *frames):
        """
        Form union of input frames.

        Columns must not overlap. Returns a copy.

        Parameters
        ----------
        *frames : list-like
            List of frames (DataMatrix or DataFrame) as function arguments

        Returns
        -------
        DataMatrix
        """
        mergedSeries = self._series.copy()

        unionIndex = self.index
        for frame in frames:
            unionIndex  = unionIndex + frame.index

        for frame in frames:
            for col, series in frame.iteritems():
                if col in mergedSeries:
                    raise Exception('Overlapping columns!')
                mergedSeries[col] = series

        return DataMatrix.fromDict(mergedSeries)

    def leftJoin(self, *frames):
        """
        Insert columns of input DataFrames / dicts into this one.

        Columns must not overlap. Returns a copy.

        Parameters
        ----------
        *frames : list-like
            List of frames (DataMatrix or DataFrame) as function arguments

        Returns
        -------
        DataMatrix
        """

        unionCols = set(self.columns)
        frames = list(frames)

        for frame in frames:
            cols = set(frame.columns)
            if any(unionCols & cols):
                raise Exception('Overlapping columns!')
            unionCols |= cols

        seriesDict = self._series

        for frame in frames:
            frame = frame.reindex(self.index)
            seriesDict.update(frame._series)

        return DataMatrix(seriesDict, index=self.index)

def _reorder_columns(mat, current, desired):
    fillVec, mask = tseries.getFillVec(current, desired, current.indexMap,
                                       desired.indexMap, '')

    fillVec = fillVec[mask]

    return mat.take(fillVec, axis=1)
