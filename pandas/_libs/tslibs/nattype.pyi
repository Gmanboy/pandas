
from datetime import datetime

import numpy as np

NaT: NaTType
iNaT: int
nat_strings: set[str]

def is_null_datetimelike(val: object, inat_is_null: bool = ...) -> bool: ...

class NaTType(datetime):
    value: np.int64

    def asm8(self) -> np.datetime64: ...
    def to_datetime64(self) -> np.datetime64: ...
    def to_numpy(self, dtype=..., copy: bool = ...) -> np.datetime64: ...

    @property
    def is_leap_year(self) -> bool: ...
    @property
    def is_month_start(self) -> bool: ...
    @property
    def is_quarter_start(self) -> bool: ...
    @property
    def is_year_start(self) -> bool: ...
    @property
    def is_month_end(self) -> bool: ...
    @property
    def is_quarter_end(self) -> bool: ...
    @property
    def is_year_end(self) -> bool: ...

    @property
    def day_of_year(self) -> float: ...
    @property
    def dayofyear(self) -> float: ...
    @property
    def days_in_month(self) -> float: ...
    @property
    def daysinmonth(self) -> float: ...
    @property
    def day_of_week(self) -> float: ...
    @property
    def dayofweek(self) -> float: ...
    @property
    def week(self) -> float: ...
    @property
    def weekofyear(self) -> float: ...

    def day_name(self) -> float: ...
    def month_name(self) -> float: ...

    # error: Return type "float" of "weekday" incompatible with return
    # type "int" in supertype "date"
    def weekday(self) -> float: ...  # type: ignore[override]

    # error: Return type "float" of "isoweekday" incompatible with return
    # type "int" in supertype "date"
    def isoweekday(self) -> float: ...  # type: ignore[override]

    def total_seconds(self) -> float: ...

    # error: Signature of "today" incompatible with supertype "datetime"
    def today(self, *args, **kwargs) -> NaTType: ...  # type: ignore[override]
    # error: Signature of "today" incompatible with supertype "datetime"
    def now(self, *args, **kwargs) -> NaTType: ...  # type: ignore[override]

    def to_pydatetime(self) -> NaTType: ...
    def date(self) -> NaTType: ...

    def round(self) -> NaTType: ...
    def floor(self) -> NaTType: ...
    def ceil(self) -> NaTType: ...

    def tz_convert(self) -> NaTType: ...
    def tz_localize(self) -> NaTType: ...

    def replace(self, *args, **kwargs) -> NaTType: ...

    # error: Return type "float" of "year" incompatible with return
    # type "int" in supertype "date"
    @property
    def year(self) -> float: ...  # type: ignore[override]

    @property
    def quarter(self) -> float: ...

    # error: Return type "float" of "month" incompatible with return
    # type "int" in supertype "date"
    @property
    def month(self) -> float: ...  # type: ignore[override]

    # error: Return type "float" of "day" incompatible with return
    # type "int" in supertype "date"
    @property
    def day(self) -> float: ...  # type: ignore[override]

    # error: Return type "float" of "hour" incompatible with return
    # type "int" in supertype "date"
    @property
    def hour(self) -> float: ...  # type: ignore[override]

    # error: Return type "float" of "minute" incompatible with return
    # type "int" in supertype "date"
    @property
    def minute(self) -> float: ...  # type: ignore[override]

    # error: Return type "float" of "second" incompatible with return
    # type "int" in supertype "date"
    @property
    def second(self) -> float: ...  # type: ignore[override]

    @property
    def millisecond(self) -> float: ...

    # error: Return type "float" of "microsecond" incompatible with return
    # type "int" in supertype "date"
    @property
    def microsecond(self) -> float: ...  # type: ignore[override]

    @property
    def nanosecond(self) -> float: ...

    # inject Timedelta properties
    @property
    def days(self) -> float: ...
    @property
    def microseconds(self) -> float: ...
    @property
    def nanoseconds(self) -> float: ...

    # inject Period properties
    @property
    def qyear(self) -> float: ...
