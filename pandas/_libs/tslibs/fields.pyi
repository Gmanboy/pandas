import numpy as np

from pandas._typing import npt

def build_field_sarray(
    dtindex: npt.NDArray[np.int64],  # const int64_t[:]
) -> np.ndarray: ...
def month_position_check(fields, weekdays) -> str | None: ...
def get_date_name_field(
    dtindex: npt.NDArray[np.int64],  # const int64_t[:]
    field: str,
    locale=...,
) -> npt.NDArray[np.object_]: ...
def get_start_end_field(
    dtindex: npt.NDArray[np.int64],  # const int64_t[:]
    field: str,
    freqstr: str | None = ...,
    month_kw: int = ...,
) -> npt.NDArray[np.bool_]: ...
def get_date_field(
    dtindex: npt.NDArray[np.int64],  # const int64_t[:]
    field: str,
) -> npt.NDArray[np.int32]: ...
def get_timedelta_field(
    tdindex: np.ndarray,  # const int64_t[:]
    field: str,
) -> npt.NDArray[np.int32]: ...
def isleapyear_arr(
    years: np.ndarray,
) -> npt.NDArray[np.bool_]: ...
def build_isocalendar_sarray(
    dtindex: npt.NDArray[np.int64],  # const int64_t[:]
) -> np.ndarray: ...
def get_locale_names(name_type: str, locale: object = None): ...

class RoundTo:
    @property
    def MINUS_INFTY(self) -> int: ...
    @property
    def PLUS_INFTY(self) -> int: ...
    @property
    def NEAREST_HALF_EVEN(self) -> int: ...
    @property
    def NEAREST_HALF_PLUS_INFTY(self) -> int: ...
    @property
    def NEAREST_HALF_MINUS_INFTY(self) -> int: ...

def round_nsint64(
    values: npt.NDArray[np.int64],
    mode: RoundTo,
    nanos: int,
) -> npt.NDArray[np.int64]: ...
