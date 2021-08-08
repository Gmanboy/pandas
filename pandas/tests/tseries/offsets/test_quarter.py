"""
Tests for the following offsets:
- QuarterBegin
- QuarterEnd
"""
from datetime import datetime

import pytest

from pandas.tests.tseries.offsets.common import (
    Base,
    assert_is_on_offset,
    assert_offset_equal,
)

from pandas.tseries.offsets import (
    QuarterBegin,
    QuarterEnd,
)


def test_quarterly_dont_normalize():
    date = datetime(2012, 3, 31, 5, 30)

    offsets = (QuarterBegin, QuarterEnd)

    for klass in offsets:
        result = date + klass()
        assert result.time() == date.time()


@pytest.mark.parametrize("offset", [QuarterBegin(), QuarterEnd()])
def test_on_offset(offset):
    dates = [
        datetime(2016, m, d)
        for m in [10, 11, 12]
        for d in [1, 2, 3, 28, 29, 30, 31]
        if not (m == 11 and d == 31)
    ]
    for date in dates:
        res = offset.is_on_offset(date)
        slow_version = date == (date + offset) - offset
        assert res == slow_version


class TestQuarterBegin(Base):
    def test_repr(self):
        expected = "<QuarterBegin: startingMonth=3>"
        assert repr(QuarterBegin()) == expected
        expected = "<QuarterBegin: startingMonth=3>"
        assert repr(QuarterBegin(startingMonth=3)) == expected
        expected = "<QuarterBegin: startingMonth=1>"
        assert repr(QuarterBegin(startingMonth=1)) == expected

    def test_is_anchored(self):
        assert QuarterBegin(startingMonth=1).is_anchored()
        assert QuarterBegin().is_anchored()
        assert not QuarterBegin(2, startingMonth=1).is_anchored()

    def test_offset_corner_case(self):
        # corner
        offset = QuarterBegin(n=-1, startingMonth=1)
        assert datetime(2010, 2, 1) + offset == datetime(2010, 1, 1)

    offset_cases = []
    offset_cases.append(
        (
            QuarterBegin(startingMonth=1),
            {
                datetime(2007, 12, 1): datetime(2008, 1, 1),
                datetime(2008, 1, 1): datetime(2008, 4, 1),
                datetime(2008, 2, 15): datetime(2008, 4, 1),
                datetime(2008, 2, 29): datetime(2008, 4, 1),
                datetime(2008, 3, 15): datetime(2008, 4, 1),
                datetime(2008, 3, 31): datetime(2008, 4, 1),
                datetime(2008, 4, 15): datetime(2008, 7, 1),
                datetime(2008, 4, 1): datetime(2008, 7, 1),
            },
        )
    )

    offset_cases.append(
        (
            QuarterBegin(startingMonth=2),
            {
                datetime(2008, 1, 1): datetime(2008, 2, 1),
                datetime(2008, 1, 31): datetime(2008, 2, 1),
                datetime(2008, 1, 15): datetime(2008, 2, 1),
                datetime(2008, 2, 29): datetime(2008, 5, 1),
                datetime(2008, 3, 15): datetime(2008, 5, 1),
                datetime(2008, 3, 31): datetime(2008, 5, 1),
                datetime(2008, 4, 15): datetime(2008, 5, 1),
                datetime(2008, 4, 30): datetime(2008, 5, 1),
            },
        )
    )

    offset_cases.append(
        (
            QuarterBegin(startingMonth=1, n=0),
            {
                datetime(2008, 1, 1): datetime(2008, 1, 1),
                datetime(2008, 12, 1): datetime(2009, 1, 1),
                datetime(2008, 1, 1): datetime(2008, 1, 1),
                datetime(2008, 2, 15): datetime(2008, 4, 1),
                datetime(2008, 2, 29): datetime(2008, 4, 1),
                datetime(2008, 3, 15): datetime(2008, 4, 1),
                datetime(2008, 3, 31): datetime(2008, 4, 1),
                datetime(2008, 4, 15): datetime(2008, 7, 1),
                datetime(2008, 4, 30): datetime(2008, 7, 1),
            },
        )
    )

    offset_cases.append(
        (
            QuarterBegin(startingMonth=1, n=-1),
            {
                datetime(2008, 1, 1): datetime(2007, 10, 1),
                datetime(2008, 1, 31): datetime(2008, 1, 1),
                datetime(2008, 2, 15): datetime(2008, 1, 1),
                datetime(2008, 2, 29): datetime(2008, 1, 1),
                datetime(2008, 3, 15): datetime(2008, 1, 1),
                datetime(2008, 3, 31): datetime(2008, 1, 1),
                datetime(2008, 4, 15): datetime(2008, 4, 1),
                datetime(2008, 4, 30): datetime(2008, 4, 1),
                datetime(2008, 7, 1): datetime(2008, 4, 1),
            },
        )
    )

    offset_cases.append(
        (
            QuarterBegin(startingMonth=1, n=2),
            {
                datetime(2008, 1, 1): datetime(2008, 7, 1),
                datetime(2008, 2, 15): datetime(2008, 7, 1),
                datetime(2008, 2, 29): datetime(2008, 7, 1),
                datetime(2008, 3, 15): datetime(2008, 7, 1),
                datetime(2008, 3, 31): datetime(2008, 7, 1),
                datetime(2008, 4, 15): datetime(2008, 10, 1),
                datetime(2008, 4, 1): datetime(2008, 10, 1),
            },
        )
    )

    @pytest.mark.parametrize("case", offset_cases)
    def test_offset(self, case):
        offset, cases = case
        for base, expected in cases.items():
            assert_offset_equal(offset, base, expected)


class TestQuarterEnd(Base):
    _offset = QuarterEnd

    def test_repr(self):
        expected = "<QuarterEnd: startingMonth=3>"
        assert repr(QuarterEnd()) == expected
        expected = "<QuarterEnd: startingMonth=3>"
        assert repr(QuarterEnd(startingMonth=3)) == expected
        expected = "<QuarterEnd: startingMonth=1>"
        assert repr(QuarterEnd(startingMonth=1)) == expected

    def test_is_anchored(self):
        assert QuarterEnd(startingMonth=1).is_anchored()
        assert QuarterEnd().is_anchored()
        assert not QuarterEnd(2, startingMonth=1).is_anchored()

    def test_offset_corner_case(self):
        # corner
        offset = QuarterEnd(n=-1, startingMonth=1)
        assert datetime(2010, 2, 1) + offset == datetime(2010, 1, 31)

    offset_cases = []
    offset_cases.append(
        (
            QuarterEnd(startingMonth=1),
            {
                datetime(2008, 1, 1): datetime(2008, 1, 31),
                datetime(2008, 1, 31): datetime(2008, 4, 30),
                datetime(2008, 2, 15): datetime(2008, 4, 30),
                datetime(2008, 2, 29): datetime(2008, 4, 30),
                datetime(2008, 3, 15): datetime(2008, 4, 30),
                datetime(2008, 3, 31): datetime(2008, 4, 30),
                datetime(2008, 4, 15): datetime(2008, 4, 30),
                datetime(2008, 4, 30): datetime(2008, 7, 31),
            },
        )
    )

    offset_cases.append(
        (
            QuarterEnd(startingMonth=2),
            {
                datetime(2008, 1, 1): datetime(2008, 2, 29),
                datetime(2008, 1, 31): datetime(2008, 2, 29),
                datetime(2008, 2, 15): datetime(2008, 2, 29),
                datetime(2008, 2, 29): datetime(2008, 5, 31),
                datetime(2008, 3, 15): datetime(2008, 5, 31),
                datetime(2008, 3, 31): datetime(2008, 5, 31),
                datetime(2008, 4, 15): datetime(2008, 5, 31),
                datetime(2008, 4, 30): datetime(2008, 5, 31),
            },
        )
    )

    offset_cases.append(
        (
            QuarterEnd(startingMonth=1, n=0),
            {
                datetime(2008, 1, 1): datetime(2008, 1, 31),
                datetime(2008, 1, 31): datetime(2008, 1, 31),
                datetime(2008, 2, 15): datetime(2008, 4, 30),
                datetime(2008, 2, 29): datetime(2008, 4, 30),
                datetime(2008, 3, 15): datetime(2008, 4, 30),
                datetime(2008, 3, 31): datetime(2008, 4, 30),
                datetime(2008, 4, 15): datetime(2008, 4, 30),
                datetime(2008, 4, 30): datetime(2008, 4, 30),
            },
        )
    )

    offset_cases.append(
        (
            QuarterEnd(startingMonth=1, n=-1),
            {
                datetime(2008, 1, 1): datetime(2007, 10, 31),
                datetime(2008, 1, 31): datetime(2007, 10, 31),
                datetime(2008, 2, 15): datetime(2008, 1, 31),
                datetime(2008, 2, 29): datetime(2008, 1, 31),
                datetime(2008, 3, 15): datetime(2008, 1, 31),
                datetime(2008, 3, 31): datetime(2008, 1, 31),
                datetime(2008, 4, 15): datetime(2008, 1, 31),
                datetime(2008, 4, 30): datetime(2008, 1, 31),
                datetime(2008, 7, 1): datetime(2008, 4, 30),
            },
        )
    )

    offset_cases.append(
        (
            QuarterEnd(startingMonth=1, n=2),
            {
                datetime(2008, 1, 31): datetime(2008, 7, 31),
                datetime(2008, 2, 15): datetime(2008, 7, 31),
                datetime(2008, 2, 29): datetime(2008, 7, 31),
                datetime(2008, 3, 15): datetime(2008, 7, 31),
                datetime(2008, 3, 31): datetime(2008, 7, 31),
                datetime(2008, 4, 15): datetime(2008, 7, 31),
                datetime(2008, 4, 30): datetime(2008, 10, 31),
            },
        )
    )

    @pytest.mark.parametrize("case", offset_cases)
    def test_offset(self, case):
        offset, cases = case
        for base, expected in cases.items():
            assert_offset_equal(offset, base, expected)

    on_offset_cases = [
        (QuarterEnd(1, startingMonth=1), datetime(2008, 1, 31), True),
        (QuarterEnd(1, startingMonth=1), datetime(2007, 12, 31), False),
        (QuarterEnd(1, startingMonth=1), datetime(2008, 2, 29), False),
        (QuarterEnd(1, startingMonth=1), datetime(2007, 3, 30), False),
        (QuarterEnd(1, startingMonth=1), datetime(2007, 3, 31), False),
        (QuarterEnd(1, startingMonth=1), datetime(2008, 4, 30), True),
        (QuarterEnd(1, startingMonth=1), datetime(2008, 5, 30), False),
        (QuarterEnd(1, startingMonth=1), datetime(2008, 5, 31), False),
        (QuarterEnd(1, startingMonth=1), datetime(2007, 6, 29), False),
        (QuarterEnd(1, startingMonth=1), datetime(2007, 6, 30), False),
        (QuarterEnd(1, startingMonth=2), datetime(2008, 1, 31), False),
        (QuarterEnd(1, startingMonth=2), datetime(2007, 12, 31), False),
        (QuarterEnd(1, startingMonth=2), datetime(2008, 2, 29), True),
        (QuarterEnd(1, startingMonth=2), datetime(2007, 3, 30), False),
        (QuarterEnd(1, startingMonth=2), datetime(2007, 3, 31), False),
        (QuarterEnd(1, startingMonth=2), datetime(2008, 4, 30), False),
        (QuarterEnd(1, startingMonth=2), datetime(2008, 5, 30), False),
        (QuarterEnd(1, startingMonth=2), datetime(2008, 5, 31), True),
        (QuarterEnd(1, startingMonth=2), datetime(2007, 6, 29), False),
        (QuarterEnd(1, startingMonth=2), datetime(2007, 6, 30), False),
        (QuarterEnd(1, startingMonth=3), datetime(2008, 1, 31), False),
        (QuarterEnd(1, startingMonth=3), datetime(2007, 12, 31), True),
        (QuarterEnd(1, startingMonth=3), datetime(2008, 2, 29), False),
        (QuarterEnd(1, startingMonth=3), datetime(2007, 3, 30), False),
        (QuarterEnd(1, startingMonth=3), datetime(2007, 3, 31), True),
        (QuarterEnd(1, startingMonth=3), datetime(2008, 4, 30), False),
        (QuarterEnd(1, startingMonth=3), datetime(2008, 5, 30), False),
        (QuarterEnd(1, startingMonth=3), datetime(2008, 5, 31), False),
        (QuarterEnd(1, startingMonth=3), datetime(2007, 6, 29), False),
        (QuarterEnd(1, startingMonth=3), datetime(2007, 6, 30), True),
    ]

    @pytest.mark.parametrize("case", on_offset_cases)
    def test_is_on_offset(self, case):
        offset, dt, expected = case
        assert_is_on_offset(offset, dt, expected)
