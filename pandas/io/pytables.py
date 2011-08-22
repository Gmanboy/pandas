"""
High level interface to PyTables for reading and writing pandas data structures
to disk
"""

# pylint: disable-msg=E1101,W0613,W0603

from datetime import datetime
import time

import numpy as np
from pandas import (Series, TimeSeries, DataFrame, DataMatrix, WidePanel,
                    LongPanel)
from pandas.core.common import adjoin
import pandas.core.internals as internals
import pandas._tseries as _tseries

# reading and writing the full object in one go
_TYPE_MAP = {
    Series     : 'series',
    TimeSeries : 'series',
    DataFrame  : 'frame',
    WidePanel  : 'wide',
    LongPanel  : 'long'
}

_NAME_MAP = {
    'series' : 'Series',
    'time_series' : 'TimeSeries',
    'frame' : 'DataFrame',
    'frame_table' : 'DataFrame (Table)',
    'wide' : 'WidePanel',
    'wide_table' : 'WidePanel (Table)',
    'long' : 'LongPanel',

    # legacy h5 files
    'Series' : 'Series',
    'TimeSeries' : 'TimeSeries',
    'DataFrame' : 'DataFrame',
    'DataMatrix' : 'DataMatrix'
}

# legacy handlers
_LEGACY_MAP = {
    'Series' : 'legacy_series',
    'TimeSeries' : 'legacy_series',
    'DataFrame' : 'legacy_frame',
    'DataMatrix' : 'legacy_frame'
}

# oh the troubles to reduce import time
_table_mod = None
def _tables():
    global _table_mod
    if _table_mod is None:
        import tables
        _table_mod = tables
    return _table_mod

class HDFStore(object):
    """
    dict-like IO interface for storing pandas objects in PyTables
    format.

    DataFrame and WidePanel can be stored in Table format, which is slower to
    read and write but can be searched and manipulated more like an SQL
    table. See HDFStore.put for more information

    Parameters
    ----------
    path : string
        File path to HDF5 file
    mode : {'a', 'w', 'r', 'r+'}, default 'a'

        ``'r'``
            Read-only; no data can be modified.
        ``'w``'
            Write; a new file is created (an existing file with the same
            name would be deleted).
        ``'a'``
            Append; an existing file is opened for reading and writing,
            and if the file does not exist it is created.
        ``'r+'``
            It is similar to ``'a'``, but the file must already exist.
    complevel : int, 1-9, default 0
            If a complib is specified compression will be applied
            where possible
    complib : {'zlib', 'bzip2', 'lzo', 'blosc', None}, default None
            If complevel is > 0 apply compression to objects written
            in the store wherever possible
    fletcher32 : bool, default False
            If applying compression use the fletcher32 checksum

    Examples
    --------
    >>> store = HDFStore('test.h5')
    >>> store['foo'] = bar   # write to HDF5
    >>> bar = store['foo']   # retrieve
    >>> store.close()
    """
    def __init__(self, path, mode='a', complevel=0, complib=None,
                 fletcher32=False):
        try:
            import tables as _
        except ImportError: # pragma: no cover
            raise Exception('HDFStore requires PyTables')

        self.path = path
        self.mode = mode
        self.handle = None
        self.complevel = complevel
        self.complib = complib
        self.fletcher32 = fletcher32
        self.filters = None
        self.open(mode=mode, warn=False)

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.put(key, value)

    def __len__(self):
        return len(self.handle.root._v_children)

    def __repr__(self):
        output = '%s\nFile path: %s\n' % (type(self), self.path)

        if len(self) > 0:
            keys = []
            values = []
            for k, v in sorted(self.handle.root._v_children.iteritems()):
                kind = v._v_attrs.pandas_type

                keys.append(str(k))
                values.append(_NAME_MAP[kind])

            output += adjoin(5, keys, values)
        else:
            output += 'Empty'

        return output

    def open(self, mode='a', warn=True):
        """
        Open the file in the specified mode

        Parameters
        ----------
        mode : {'a', 'w', 'r', 'r+'}, default 'a'
            See HDFStore docstring or tables.openFile for info about modes
        """
        self.mode = mode
        if warn and mode == 'w': # pragma: no cover
            while True:
                response = raw_input("Re-opening as mode='w' will delete the "
                                     "current file. Continue (y/n)?")
                if response == 'y':
                    break
                elif response == 'n':
                    return
        if self.handle is not None and self.handle.isopen:
            self.handle.close()

        if self.complevel > 0 and self.complib is not None:
            self.filters = _tables().Filters(self.complevel,
                                             self.complib,
                                             fletcher32=self.fletcher32)

        self.handle = _tables().openFile(self.path, self.mode)

    def close(self):
        """
        Close the PyTables file handle
        """
        self.handle.close()

    def flush(self):
        """
        Force all buffered modifications to be written to disk
        """
        self.handle.flush()

    def get(self, key):
        """
        Retrieve pandas object stored in file

        Parameters
        ----------
        key : object

        Returns
        -------
        obj : type of object stored in file
        """
        try:
            group = getattr(self.handle.root, key)
            return self._read_group(group)
        except AttributeError:
            raise

    def select(self, key, where=None):
        """
        Retrieve pandas object stored in file, optionally based on where
        criteria

        Parameters
        ----------
        key : object
        where : list, optional

           Must be a list of dict objects of the following forms. Selection can
           be performed on the 'index' or 'column' fields.

           Comparison op
               {'field' : 'index',
                'op'    : '>=',
                'value' : value}

           Match single value
               {'field' : 'index',
                'value' : v1}

           Match a set of values
               {'field' : 'index',
                'value' : [v1, v2, v3]}

        """
        group = getattr(self.handle.root, key, None)
        if 'table' not in group._v_attrs.pandas_type:
            raise Exception('can only select on objects written as tables')
        if group is not None:
            return self._read_group(group, where)

    def put(self, key, value, table=False, append=False,
            compression=None):
        """
        Store object in HDFStore

        Parameters
        ----------
        key : object
        value : {Series, DataFrame, WidePanel, LongPanel}
        table : boolean, default False
            Write as a PyTables Table structure which may perform worse but
            allow more flexible operations like searching / selecting subsets of
            the data
        append : boolean, default False
            For table data structures, append the input data to the existing
            table
        compression : {None, 'blosc', 'lzo', 'zlib'}, default None
            Use a compression algorithm to compress the data
            If None, the compression settings specified in the ctor will
            be used.
        """
        self._write_to_group(key, value, table=table, append=append,
                             comp=compression)

    def _get_handler(self, op, kind):
        return getattr(self,'_%s_%s' % (op, kind))

    def remove(self, key, where=None):
        """
        Remove pandas object partially by specifying the where condition

        Parameters
        ----------
        key : string
            Node to remove or delete rows from
        where : list
            For Table node, delete specified rows. See HDFStore.select for more
            information

        Parameters
        ----------
        key : object
        """
        if where is None:
            self.handle.removeNode(self.handle.root, key, recursive=True)
        else:
            group = getattr(self.handle.root, key)
            self._delete_from_table(group, where)

    def append(self, key, value):
        """
        Append to Table in file. Node must already exist and be Table
        format.

        Parameters
        ----------
        key : object
        value : {Series, DataFrame, WidePanel, LongPanel}

        Notes
        -----
        Does *not* check if data being appended overlaps with existing
        data in the table, so be careful
        """
        self._write_to_group(key, value, table=True, append=True)

    def _write_to_group(self, key, value, table=False, append=False,
                        comp=None):
        root = self.handle.root
        if key not in root._v_children:
            group = self.handle.createGroup(root, key)
        else:
            group = getattr(root, key)

        kind = _TYPE_MAP[type(value)]
        if table or (append and _is_table_type(group)):
            kind = '%s_table' % kind
            handler = self._get_handler(op='write', kind=kind)
            wrapper = lambda value: handler(group, value, append=append,
                                            comp=comp)
        else:
            if append:
                raise ValueError('Can only append to Tables')
            if comp:
                raise ValueError('Compression only supported on Tables')

            handler = self._get_handler(op='write', kind=kind)
            wrapper = lambda value: handler(group, value)

        wrapper(value)
        group._v_attrs.pandas_type = kind

    def _write_series(self, group, series):
        self._write_index(group, 'index', series.index)
        self._write_array(group, 'values', series.values)

    def _write_frame(self, group, df):
        self._write_block_manager(group, df._data)

    def _read_frame(self, group, where=None):
        return DataFrame(self._read_block_manager(group))

    def _write_block_manager(self, group, data):
        if not data.is_consolidated():
            data = data.consolidate()

        group._v_attrs.ndim = data.ndim
        for i, ax in enumerate(data.axes):
            self._write_index(group, 'axis%d' % i, ax)

        # Supporting mixed-type DataFrame objects...nontrivial
        nblocks = len(data.blocks)
        group._v_attrs.nblocks = nblocks
        for i in range(nblocks):
            blk = data.blocks[i]
            self._write_index(group, 'block%d_items' % i, blk.items)
            self._write_array(group, 'block%d_values' % i, blk.values)

    def _read_block_manager(self, group):
        from pandas.core.internals import BlockManager, make_block

        ndim = group._v_attrs.ndim
        nblocks = group._v_attrs.nblocks

        axes = []
        for i in xrange(ndim):
            ax = _read_index(group, 'axis%d' % i)
            axes.append(ax)

        items = axes[0]
        blocks = []
        for i in range(group._v_attrs.nblocks):
            blk_items = _read_index(group, 'block%d_items' % i)
            values = _read_array(group, 'block%d_values' % i)
            blk = make_block(values, blk_items, items)
            blocks.append(blk)

        return BlockManager(blocks, axes)

    def _write_frame_table(self, group, df, append=False, comp=None):
        mat = df.values
        values = mat.reshape((1,) + mat.shape)

        if df._is_mixed_type:
            raise Exception('Cannot currently store mixed-type DataFrame '
                            'objects in Table format')

        self._write_table(group, items=['value'],
                          index=df.index, columns=df.columns,
                          values=values, append=append, compression=comp)

    def _write_wide(self, group, panel):
        panel._consolidate_inplace()
        self._write_block_manager(group, panel._data)

    def _read_wide(self, group, where=None):
        return WidePanel(self._read_block_manager(group))

    def _write_wide_table(self, group, panel, append=False, comp=None):
        self._write_table(group, items=panel.items, index=panel.major_axis,
                          columns=panel.minor_axis, values=panel.values,
                          append=append, compression=comp)

    def _read_wide_table(self, group, where=None):
        return self._read_panel_table(group, where)

    def _write_long(self, group, panel, append=False):
        self._write_index(group, 'major_axis', panel.major_axis)
        self._write_index(group, 'minor_axis', panel.minor_axis)
        self._write_index(group, 'items', panel.items)
        self._write_array(group, 'major_labels', panel.major_labels)
        self._write_array(group, 'minor_labels', panel.minor_labels)
        self._write_array(group, 'values', panel.values)

    def _read_long(self, group, where=None):
        from pandas.core.index import MultiIndex

        items = _read_index(group, 'items')
        major_axis = _read_index(group, 'major_axis')
        minor_axis = _read_index(group, 'minor_axis')
        major_labels = _read_array(group, 'major_labels')
        minor_labels = _read_array(group, 'minor_labels')
        values = _read_array(group, 'values')

        index = MultiIndex(levels=[major_axis, minor_axis],
                           labels=[major_labels, minor_labels])
        return LongPanel(values, index=index, columns=items)

    def _write_index(self, group, key, value):
        # don't care about type here
        converted, kind, _ = _convert_index(value)
        self._write_array(group, key, converted)
        node = getattr(group, key)
        node._v_attrs.kind = kind

    def _write_array(self, group, key, value):
        if key in group:
            self.handle.removeNode(group, key)

        if self.filters is not None:
            atom = None
            try:
                # get the atom for this datatype
                atom = _tables().Atom.from_dtype(value.dtype)
            except ValueError:
                pass

            if atom is not None:
                # create an empty chunked array and fill it from value
                ca = self.handle.createCArray(group, key, atom,
                                                value.shape,
                                                filters=self.filters)
                ca[:] = value
                return

        if value.dtype == np.object_:
            vlarr = self.handle.createVLArray(group, key,
                                              _tables().ObjectAtom())
            vlarr.append(value)
        else:
            self.handle.createArray(group, key, value)

    def _write_table(self, group, items=None, index=None, columns=None,
                     values=None, append=False, compression=None):
        """ need to check for conform to the existing table:
            e.g. columns should match """
        # create dict of types
        index_converted, index_kind, index_t = _convert_index(index)
        columns_converted, cols_kind, col_t = _convert_index(columns)

        # create the table if it doesn't exist (or get it if it does)
        if not append:
            if 'table' in group:
                self.handle.removeNode(group, 'table')

        if 'table' not in group:
            # create the table
            desc = {'index'  : index_t,
                    'column' : col_t,
                    'values' : _tables().FloatCol(shape=(len(values)))}

            options = {'name' : 'table',
                       'description' : desc}

            if compression:
                complevel = self.complevel
                if complevel is None:
                    complevel = 9
                options['filters'] = _tables().Filters(complevel=complevel,
                                                       complib=compression,
                                                       fletcher32=self.fletcher32)
            elif self.filters is not None:
                options['filters'] = self.filters

            table = self.handle.createTable(group, **options)
        else:
            # the table must already exist
            table = getattr(group, 'table', None)

        # add kinds
        table._v_attrs.index_kind = index_kind
        table._v_attrs.columns_kind = cols_kind
        table._v_attrs.fields = list(items)

        # add the rows
        try:
            for i, index in enumerate(index_converted):
                for c, col in enumerate(columns_converted):
                    v = values[:, i, c]

                    # don't store the row if all values are np.nan
                    if np.isnan(v).all():
                        continue

                    row = table.row
                    row['index'] = index
                    row['column'] = col

                    # create the values array
                    row['values'] = v
                    row.append()
            self.handle.flush()
        except (ValueError), detail: # pragma: no cover
            print "value_error in _write_table -> %s" % str(detail)
            try:
                self.handle.flush()
            except Exception:
                pass
            raise

    def _read_group(self, group, where=None):
        kind = group._v_attrs.pandas_type
        kind = _LEGACY_MAP.get(kind, kind)
        handler = self._get_handler(op='read', kind=kind)
        return handler(group, where)

    def _read_series(self, group, where=None):
        index = _read_index(group, 'index')
        values = _read_array(group, 'values')
        return Series(values, index=index)

    def _read_legacy_series(self, group, where=None):
        index = _read_index_legacy(group, 'index')
        values = _read_array(group, 'values')
        return Series(values, index=index)

    def _read_legacy_frame(self, group, where=None):
        index = _read_index_legacy(group, 'index')
        columns = _read_index_legacy(group, 'columns')
        values = _read_array(group, 'values')
        return DataFrame(values, index=index, columns=columns)

    def _read_frame_table(self, group, where=None):
        return self._read_panel_table(group, where)['value']

    def _read_panel_table(self, group, where=None):
        from pandas.core.panel import _make_long_index
        table = getattr(group, 'table')

        # create the selection
        sel = Selection(table, where)
        sel.select()
        fields = table._v_attrs.fields

        columns = _maybe_convert(sel.values['column'],
                                 table._v_attrs.columns_kind)
        index = _maybe_convert(sel.values['index'],
                               table._v_attrs.index_kind)
        # reconstruct
        long_index = _make_long_index(np.asarray(index),
                                      np.asarray(columns))
        lp = LongPanel(sel.values['values'], index=long_index,
                       columns=fields)
        lp = lp.sortlevel(level=0)
        wp = lp.to_wide()

        if sel.column_filter:
            new_minor = sorted(set(wp.minor_axis) & sel.column_filter)
            wp = wp.reindex(minor=new_minor)
        return wp

    def _delete_from_table(self, group, where = None):
        table = getattr(group, 'table')

        # create the selection
        s = Selection(table,where)
        s.select_coords()

        # delete the rows in reverse order
        l = list(s.values)
        l.reverse()
        for c in l:
            table.removeRows(c)
        self.handle.flush()
        return len(s.values)

def _convert_index(index):
    # Let's assume the index is homogeneous
    values = np.asarray(index)

    import time
    if isinstance(values[0], datetime):
        converted = np.array([time.mktime(v.timetuple())
                              for v in values], dtype=np.int64)
        return converted, 'datetime', _tables().Time64Col()
    elif isinstance(values[0], basestring):
        converted = np.array(list(values), dtype=np.str_)
        itemsize = converted.dtype.itemsize
        return converted, 'string', _tables().StringCol(itemsize)
    elif isinstance(values[0], (int, np.integer)):
        # take a guess for now, hope the values fit
        return np.asarray(values, dtype=int), 'integer', _tables().Int64Col()
    else: # pragma: no cover
        raise ValueError('unrecognized index type %s' % type(values[0]))


def _read_array(group, key):
    import tables
    node = getattr(group, key)
    data = node[:]

    if isinstance(node, tables.VLArray):
        return data[0]
    else:
        return data

def _read_index(group, key):
    node = getattr(group, key)
    data = node[:]
    kind = node._v_attrs.kind

    return _unconvert_index(data, kind)

def _unconvert_index(data, kind):
    if kind == 'datetime':
        index = np.array([datetime.fromtimestamp(v) for v in data],
                         dtype=object)
    elif kind in ('string', 'integer'):
        index = np.array(data, dtype=object)
    else: # pragma: no cover
        raise ValueError('unrecognized index type %s' % kind)
    return index

def _read_index_legacy(group, key):
    node = getattr(group, key)
    data = node[:]
    kind = node._v_attrs.kind

    return _unconvert_index_legacy(data, kind)

def _unconvert_index_legacy(data, kind, legacy=False):
    if kind == 'datetime':
        index = _tseries.array_to_datetime(data)
    elif kind in ('string', 'integer'):
        index = np.array(data, dtype=object)
    else: # pragma: no cover
        raise ValueError('unrecognized index type %s' % kind)
    return index

def _maybe_convert(values, val_kind):
    if _need_convert(val_kind):
        conv = _get_converter(val_kind)
        conv = np.frompyfunc(conv, 1, 1)
        values = conv(values)
    return values

def _get_converter(kind):
    if kind == 'datetime':
        return datetime.fromtimestamp
    else: # pragma: no cover
        raise ValueError('invalid kind %s' % kind)

def _need_convert(kind):
    if kind == 'datetime':
        return True
    return False

def _is_table_type(group):
    try:
        return 'table' in group._v_attrs.pandas_type
    except AttributeError:
        # new node, e.g.
        return False

class Selection(object):
    """
    Carries out a selection operation on a tables.Table object.

    Parameters
    ----------
    table : tables.Table
    where : list of dicts of the following form

        Comparison op
           {'field' : 'index',
            'op'    : '>=',
            'value' : value}

        Match single value
           {'field' : 'index',
            'value' : v1}

        Match a set of values
           {'field' : 'index',
            'value' : [v1, v2, v3]}
    """
    def __init__(self, table, where=None):
        self.table = table
        self.where = where
        self.column_filter = None
        self.the_condition = None
        self.conditions = []
        self.values = None
        if where:
            self.generate(where)

    def generate(self, where):
        # and condictions
        for c in where:
            op = c.get('op',None)
            value = c['value']
            field = c['field']

            if field == 'index' and isinstance(value, datetime):
                value = time.mktime(value.timetuple())
                self.conditions.append('(%s %s %s)' % (field,op,value))
            else:
                self.generate_multiple_conditions(op,value,field)

        if len(self.conditions):
            self.the_condition = '(' + ' & '.join(self.conditions) + ')'

    def generate_multiple_conditions(self, op, value, field):

        if op and op == 'in' or isinstance(value, (list, np.ndarray)):
            if len(value) <= 61:
                l = '(' + ' | '.join([ "(%s == '%s')" % (field,v)
                                       for v in value ]) + ')'
                self.conditions.append(l)
            else:
                self.column_filter = set(value)
        else:
            if op is None:
                op = '=='
            self.conditions.append('(%s %s "%s")' % (field,op,value))

    def select(self):
        """
        generate the selection
        """
        if self.the_condition:
            self.values = self.table.readWhere(self.the_condition)

        else:
            self.values = self.table.read()

    def select_coords(self):
        """
        generate the selection
        """
        self.values = self.table.getWhereList(self.the_condition)

