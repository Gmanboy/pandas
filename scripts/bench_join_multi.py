from pandas import *

import numpy as np
from six.moves import zip
from pandas.util.testing import rands
from pandas.util.py3compat import range
import pandas.lib as lib

N = 100000

key1 = [rands(10) for _ in range(N)]
key2 = [rands(10) for _ in range(N)]

zipped = list(zip(key1, key2))


def _zip(*args):
    arr = np.empty(N, dtype=object)
    arr[:] = list(zip(*args))
    return arr


def _zip2(*args):
    return lib.list_to_object_array(list(zip(*args)))

index = MultiIndex.from_arrays([key1, key2])
to_join = DataFrame({'j1': np.random.randn(100000)}, index=index)

data = DataFrame({'A': np.random.randn(500000),
                  'key1': np.repeat(key1, 5),
                  'key2': np.repeat(key2, 5)})

# data.join(to_join, on=['key1', 'key2'])
