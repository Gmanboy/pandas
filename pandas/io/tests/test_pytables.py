import nose
import unittest
import os

import numpy as np

from pandas import (Series, DataFrame, WidePanel, LongPanel, DateRange)
from pandas.io.pytables import HDFStore
import pandas.util.testing as tm

class TesttHDFStore(unittest.TestCase):
    path = '__test__.h5'
    scratchpath = '__scratch__.h5'

    def setUp(self):
        self.store = HDFStore(self.path)

    def tearDown(self):
        self.store.close()
        os.remove(self.path)

    def test_len(self):
        self.store['a'] = tm.makeTimeSeries()
        self.store['b'] = tm.makeStringSeries()
        self.store['c'] = tm.makeDataFrame()
        self.store['d'] = tm.makeWidePanel()
        self.assertEquals(len(self.store), 4)

    def test_repr(self):
        repr(self.store)
        self.store['a'] = tm.makeTimeSeries()
        self.store['b'] = tm.makeStringSeries()
        self.store['c'] = tm.makeDataFrame()
        self.store['d'] = tm.makeWidePanel()
        repr(self.store)

    def test_reopen_handle(self):
        self.store['a'] = tm.makeTimeSeries()
        self.store.open('w', warn=False)
        self.assert_(self.store.handle.isopen)
        self.assertEquals(len(self.store), 0)

    def test_flush(self):
        self.store['a'] = tm.makeTimeSeries()
        self.store.flush()

    def test_get(self):
        self.store['a'] = tm.makeTimeSeries()
        left = self.store.get('a')
        right = self.store['a']
        tm.assert_series_equal(left, right)

        self.assertRaises(AttributeError, self.store.get, 'b')

    def test_put_corner(self):
        pass

    def test_remove(self):
        ts =tm.makeTimeSeries()
        df = tm.makeDataFrame()
        self.store['a'] = ts
        self.store['b'] = df
        self.store.remove('a')
        self.assertEquals(len(self.store), 1)
        tm.assert_frame_equal(df, self.store['b'])

        self.store.remove('b')
        self.assertEquals(len(self.store), 0)

    def test_remove_crit(self):
        wp = tm.makeWidePanel()
        self.store.put('wp', wp, table=True)
        date = wp.major_axis[len(wp.major_axis) // 2]

        crit1 = {
            'field' : 'index',
            'op' : '>',
            'value' : date
        }
        crit2 = {
            'field' : 'column',
            'value' : ['A', 'D']
        }
        self.store.remove('wp', where=[crit1])
        self.store.remove('wp', where=[crit2])
        result = self.store['wp']
        expected = wp.truncate(after=date).reindex(minor=['B', 'C'])
        tm.assert_panel_equal(result, expected)

    def test_series(self):
        s = tm.makeStringSeries()
        self._check_roundtrip(s, tm.assert_series_equal)

        ts = tm.makeTimeSeries()
        self._check_roundtrip(ts, tm.assert_series_equal)

    def test_timeseries_preepoch(self):
        dr = DateRange('1/1/1940', '1/1/1960')
        ts = Series(np.random.randn(len(dr)), index=dr)
        self._check_roundtrip(ts, tm.assert_series_equal)

    def test_frame(self):
        df = tm.makeDataFrame()
        self._check_roundtrip(df, tm.assert_frame_equal)

        tdf = tm.makeTimeDataFrame()
        self._check_roundtrip(tdf, tm.assert_frame_equal)

    def test_frame_mixed(self):
        raise nose.SkipTest('cannot handle for now')
        df = tm.makeDataFrame()
        df['nonfloat'] = 'foo'
        self._check_roundtrip(df, tm.assert_frame_equal)

    def test_frame_table(self):
        df = tm.makeDataFrame()
        self._check_roundtrip_table(df, tm.assert_frame_equal)

    def test_wide(self):
        wp = tm.makeWidePanel()
        self._check_roundtrip(wp, tm.assert_panel_equal)

    def test_wide_table(self):
        wp = tm.makeWidePanel()
        self._check_roundtrip_table(wp, tm.assert_panel_equal)

    def test_longpanel(self):
        pass

    def test_overwrite_node(self):
        self.store['a'] = tm.makeTimeDataFrame()
        ts = tm.makeTimeSeries()
        self.store['a'] = ts

        tm.assert_series_equal(self.store['a'], ts)

    def test_panel_select(self):
        wp = tm.makeWidePanel()
        self.store.put('wp', wp, table=True)
        date = wp.major_axis[len(wp.major_axis) // 2]

        crit1 = {
            'field' : 'index',
            'op' : '>=',
            'value' : date
        }
        crit2 = {
            'field' : 'column',
            'value' : ['A', 'D']
        }

        result = self.store.select('wp', [crit1, crit2])
        expected = wp.truncate(before=date).reindex(minor=['A', 'D'])
        tm.assert_panel_equal(result, expected)

    def test_frame_select(self):
        df = tm.makeTimeDataFrame()
        self.store.put('frame', df, table=True)
        date = df.index[len(df) // 2]

        crit1 = {
            'field' : 'index',
            'op' : '>=',
            'value' : date
        }
        crit2 = {
            'field' : 'column',
            'value' : ['A', 'D']
        }

        result = self.store.select('frame', [crit1, crit2])
        expected = df.ix[date:, ['A', 'D']]
        tm.assert_frame_equal(result, expected)

        # can't select if not written as table
        self.store['frame'] = df
        self.assertRaises(Exception, self.store.select,
                          'frame', [crit1, crit2])

    def _check_roundtrip(self, obj, comparator):
        store = HDFStore(self.scratchpath, 'w')
        store['obj'] = obj
        retrieved = store['obj']
        comparator(retrieved, obj)
        store.close()

    def _check_roundtrip_table(self, obj, comparator):
        store = HDFStore(self.scratchpath, 'w')
        store.put('obj', obj, table=True)
        retrieved = store['obj']
        sorted_obj = _test_sort(obj)
        comparator(retrieved, sorted_obj)
        store.close()

def _test_sort(obj):
    if isinstance(obj, DataFrame):
        return obj.reindex(sorted(obj.index))
    elif isinstance(obj, WidePanel):
        return obj.reindex(major=sorted(obj.major_axis))
    else:
        raise ValueError('type not supported here')

if __name__ == '__main__':
    import nose
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure'],
                   exit=False)

