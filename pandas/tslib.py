# flake8: noqa

import warnings
warnings.warn("The pandas.tslib module is deprecated and will be "
              "removed in a future version.", FutureWarning, stacklevel=2)
from pandas._libs.tslibs import Timestamp, Timedelta, OutOfBoundsDatetime
from pandas._libs.tslibs.nattype import NaT, NaTType
