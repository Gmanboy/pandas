from copy import deepcopy
from datetime import datetime
import unittest

from numpy.random import randn
import numpy as np

from pandas.core.api import Series, DataMatrix
import pandas.core.tests.test_frame as test_frame
import pandas.core.tests.common as common

#-------------------------------------------------------------------------------
# DataMatrix test cases

class TestDataMatrix(test_frame.TestDataFrame):
    klass = DataMatrix

    def test_more_constructor(self):
        arr = randn(10)
        dm = self.klass(arr, columns=['A'], index=np.arange(10))
        self.assertEqual(dm.values.ndim, 2)

        arr = randn(0)
        dm = self.klass(arr)
        self.assertEqual(dm.values.ndim, 2)
        self.assertEqual(dm.values.ndim, 2)

        # no data specified
        dm = self.klass(columns=['A', 'B'], index=np.arange(10))
        self.assertEqual(dm.values.shape, (10, 2))

        dm = self.klass(columns=['A', 'B'])
        self.assertEqual(dm.values.shape, (0, 2))

        dm = self.klass(index=np.arange(10))
        self.assertEqual(dm.values.shape, (10, 0))

        # corner, silly
        self.assertRaises(Exception, self.klass, (1, 2, 3))

    def test_copy(self):
        # copy objects
        copy = self.mixed_frame.copy()
        self.assert_(copy.objects is not self.mixed_frame.objects)

    def test_combineFirst_mixed(self):
        a = Series(['a','b'], index=range(2))
        b = Series(range(2), index=range(2))
        f = DataMatrix.fromDict({'A' : a, 'B' : b})

        a = Series(['a','b'], index=range(5, 7))
        b = Series(range(2), index=range(5, 7))
        g = DataMatrix.fromDict({'A' : a, 'B' : b})

        combined = f.combineFirst(g)

    def test_setitem_corner(self):
        # corner case
        df = self.klass({'B' : [1., 2., 3.],
                         'C' : ['a', 'b', 'c']},
                        index=np.arange(3))
        del df['B']
        df['B'] = [1., 2., 3.]
        self.assert_('B' in df)
        self.assertEqual(len(df.columns), 1)

        df['A'] = 'beginning'
        df['E'] = 'foo'
        df['D'] = 'bar'
        df[datetime.now()] = 'date'
        df[datetime.now()] = 5.

    def test_more_fromDict(self):
        pass

    def test_fill_corner(self):
        self.mixed_frame['foo'][5:20] = np.NaN
        self.mixed_frame['A'][-10:] = np.NaN

        obj_result = self.mixed_frame.objects.fill(value=0)

        del self.mixed_frame['foo']

        # XXX
        obj_result = self.mixed_frame.objects.fill(value=0)


if __name__ == '__main__':
    unittest.main()
