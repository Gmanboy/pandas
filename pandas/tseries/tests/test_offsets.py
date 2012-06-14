from datetime import datetime, timedelta
import unittest
import numpy as np

from pandas.core.datetools import (
    bday, BDay, BQuarterEnd, BMonthEnd, BYearEnd, MonthEnd, MonthBegin,
    BYearBegin, QuarterBegin, BQuarterBegin, BMonthBegin,
    DateOffset, Week, YearBegin, YearEnd, Hour, Minute, Second,
    WeekOfMonth, format, ole2datetime, QuarterEnd, to_datetime, normalize_date,
    get_offset, get_offset_name, inferTimeRule, hasOffsetName,
    get_standard_freq)

from pandas.tseries.frequencies import _offset_map
from pandas.tseries.index import _to_m8
from pandas.tseries.tools import parse_time_string

from nose.tools import assert_raises

import pandas.lib as lib
from pandas.lib import Timestamp

def test_monthrange():
    import calendar
    for y in range(2000,2013):
        for m in range(1,13):
            assert lib.monthrange(y,m) == calendar.monthrange(y,m)

####
## Misc function tests
####
def test_format():
    actual = format(datetime(2008, 1, 15))
    assert actual == '20080115'

def test_ole2datetime():
    actual = ole2datetime(60000)
    assert actual == datetime(2064, 4, 8)

    assert_raises(Exception, ole2datetime, 60)

def test_to_datetime1():
    actual = to_datetime(datetime(2008, 1, 15))
    assert actual == datetime(2008, 1, 15)

    actual = to_datetime('20080115')
    assert actual == datetime(2008, 1, 15)

    # unparseable
    s = 'Month 1, 1999'
    assert to_datetime(s) == s

def test_normalize_date():
    actual = normalize_date(datetime(2007, 10, 1, 1, 12, 5, 10))
    assert actual == datetime(2007, 10, 1)

def test_to_m8():
    valb = datetime(2007, 10, 1)
    valu = _to_m8(valb)
    assert type(valu) == np.datetime64
    #assert valu == np.datetime64(datetime(2007,10,1))

#def test_datetime64_box():
#    valu = np.datetime64(datetime(2007,10,1))
#    valb = _dt_box(valu)
#    assert type(valb) == datetime
#    assert valb == datetime(2007,10,1)

#####
### DateOffset Tests
#####

class TestDateOffset(unittest.TestCase):

    def setUp(self):
        self.d = Timestamp(datetime(2008, 1, 2))

    def test_repr(self):
        repr(DateOffset())
        repr(DateOffset(2))
        repr(2 * DateOffset())
        repr(2 * DateOffset(months=2))

    def test_mul(self):
        assert DateOffset(2) == 2 * DateOffset(1)
        assert DateOffset(2) == DateOffset(1) * 2

    def test_constructor(self):

        assert((self.d + DateOffset(months=2)) == datetime(2008, 3, 2))
        assert((self.d - DateOffset(months=2)) == datetime(2007, 11, 2))

        assert((self.d + DateOffset(2)) == datetime(2008, 1, 4))

        assert not DateOffset(2).isAnchored()
        assert DateOffset(1).isAnchored()

        d = datetime(2008, 1, 31)
        assert((d + DateOffset(months=1)) == datetime(2008, 2, 29))

    def test_copy(self):
        assert(DateOffset(months=2).copy() == DateOffset(months=2))

    def test_eq(self):
        offset1 = DateOffset(days=1)
        offset2 = DateOffset(days=365)

        self.assert_(offset1 != offset2)
        self.assert_(not (offset1 == offset2))

class TestBusinessDay(unittest.TestCase):

    def setUp(self):
        self.d = datetime(2008, 1, 1)

        self.offset = BDay()
        self.offset2 = BDay(2)

    def test_repr(self):
        assert repr(self.offset) == '<1 BusinessDay>'
        assert repr(self.offset2) == '<2 BusinessDays>'

        expected = '<1 BusinessDay: offset=datetime.timedelta(1)>'
        assert repr(self.offset + timedelta(1)) == expected

    def test_with_offset(self):
        offset = self.offset + timedelta(hours=2)

        assert (self.d + offset) == datetime(2008, 1, 2, 2)

    def testEQ(self):
        self.assertEqual(self.offset2, self.offset2)

    def test_mul(self):
        pass

    def test_hash(self):
        self.assertEqual(hash(self.offset2), hash(self.offset2))

    def testCall(self):
        self.assertEqual(self.offset2(self.d), datetime(2008, 1, 3))

    def testRAdd(self):
        self.assertEqual(self.d + self.offset2, self.offset2 + self.d)

    def testSub(self):
        off = self.offset2
        self.assertRaises(Exception, off.__sub__, self.d)
        self.assertEqual(2 * off - off, off)

        self.assertEqual(self.d - self.offset2,  self.d + BDay(-2))

    def testRSub(self):
        self.assertEqual(self.d - self.offset2, (-self.offset2).apply(self.d))

    def testMult1(self):
        self.assertEqual(self.d + 10*self.offset, self.d + BDay(10))

    def testMult2(self):
        self.assertEqual(self.d + (-5*BDay(-10)),
                         self.d + BDay(50))


    def testRollback1(self):
        self.assertEqual(BDay(10).rollback(self.d), self.d)

    def testRollback2(self):
        self.assertEqual(BDay(10).rollback(datetime(2008, 1, 5)), datetime(2008, 1, 4))

    def testRollforward1(self):
        self.assertEqual(BDay(10).rollforward(self.d), self.d)

    def testRollforward2(self):
        self.assertEqual(BDay(10).rollforward(datetime(2008, 1, 5)), datetime(2008, 1, 7))

    def test_onOffset(self):
        tests = [(BDay(), datetime(2008, 1, 1), True),
                 (BDay(), datetime(2008, 1, 5), False)]

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

    def test_apply(self):
        tests = []

        tests.append((bday,
                      {datetime(2008, 1, 1): datetime(2008, 1, 2),
                       datetime(2008, 1, 4): datetime(2008, 1, 7),
                       datetime(2008, 1, 5): datetime(2008, 1, 7),
                       datetime(2008, 1, 6): datetime(2008, 1, 7),
                       datetime(2008, 1, 7): datetime(2008, 1, 8)}))

        tests.append((2*bday,
                      {datetime(2008, 1, 1): datetime(2008, 1, 3),
                       datetime(2008, 1, 4): datetime(2008, 1, 8),
                       datetime(2008, 1, 5): datetime(2008, 1, 8),
                       datetime(2008, 1, 6): datetime(2008, 1, 8),
                       datetime(2008, 1, 7): datetime(2008, 1, 9)}))

        tests.append((-bday,
                      {datetime(2008, 1, 1): datetime(2007, 12, 31),
                       datetime(2008, 1, 4): datetime(2008, 1, 3),
                       datetime(2008, 1, 5): datetime(2008, 1, 4),
                       datetime(2008, 1, 6): datetime(2008, 1, 4),
                       datetime(2008, 1, 7): datetime(2008, 1, 4),
                       datetime(2008, 1, 8): datetime(2008, 1, 7)}))

        tests.append((-2*bday,
                      {datetime(2008, 1, 1): datetime(2007, 12, 28),
                       datetime(2008, 1, 4): datetime(2008, 1, 2),
                       datetime(2008, 1, 5): datetime(2008, 1, 3),
                       datetime(2008, 1, 6): datetime(2008, 1, 3),
                       datetime(2008, 1, 7): datetime(2008, 1, 3),
                       datetime(2008, 1, 8): datetime(2008, 1, 4),
                       datetime(2008, 1, 9): datetime(2008, 1, 7)}))

        tests.append((BDay(0),
                      {datetime(2008, 1, 1): datetime(2008, 1, 1),
                       datetime(2008, 1, 4): datetime(2008, 1, 4),
                       datetime(2008, 1, 5): datetime(2008, 1, 7),
                       datetime(2008, 1, 6): datetime(2008, 1, 7),
                       datetime(2008, 1, 7): datetime(2008, 1, 7)}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

    def test_apply_corner(self):
        self.assertRaises(Exception, BDay().apply, BMonthEnd())

    def test_offsets_compare_equal(self):
        # root cause of #456
        offset1 = BDay()
        offset2 = BDay()
        self.assertFalse(offset1 != offset2)

def assertOnOffset(offset, date, expected):
    actual = offset.onOffset(date)
    assert actual == expected

class TestWeek(unittest.TestCase):
    def test_corner(self):
        self.assertRaises(Exception, Week, weekday=7)
        self.assertRaises(Exception, Week, weekday=-1)

    def test_isAnchored(self):
        self.assert_(Week(weekday=0).isAnchored())
        self.assert_(not Week().isAnchored())
        self.assert_(not Week(2, weekday=2).isAnchored())
        self.assert_(not Week(2).isAnchored())

    def test_offset(self):
        tests = []

        tests.append((Week(), # not business week
                      {datetime(2008, 1, 1): datetime(2008, 1, 8),
                       datetime(2008, 1, 4): datetime(2008, 1, 11),
                       datetime(2008, 1, 5): datetime(2008, 1, 12),
                       datetime(2008, 1, 6): datetime(2008, 1, 13),
                       datetime(2008, 1, 7): datetime(2008, 1, 14)}))

        tests.append((Week(weekday=0), # Mon
                      {datetime(2007, 12, 31): datetime(2008, 1, 7),
                       datetime(2008, 1, 4): datetime(2008, 1, 7),
                       datetime(2008, 1, 5): datetime(2008, 1, 7),
                       datetime(2008, 1, 6): datetime(2008, 1, 7),
                       datetime(2008, 1, 7): datetime(2008, 1, 14)}))

        tests.append((Week(0, weekday=0), # n=0 -> roll forward. Mon
                      {datetime(2007, 12, 31): datetime(2007, 12, 31),
                       datetime(2008, 1, 4): datetime(2008, 1, 7),
                       datetime(2008, 1, 5): datetime(2008, 1, 7),
                       datetime(2008, 1, 6): datetime(2008, 1, 7),
                       datetime(2008, 1, 7): datetime(2008, 1, 7)}))

        tests.append((Week(-2, weekday=1), # n=0 -> roll forward. Mon
                      {datetime(2010, 4, 6): datetime(2010, 3, 23),
                       datetime(2010, 4, 8): datetime(2010, 3, 30),
                       datetime(2010, 4, 5): datetime(2010, 3, 23)}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

    def test_onOffset(self):
        for weekday in range(7):
            offset = Week(weekday=weekday)

            for day in range(1, 8):
                date = datetime(2008, 1, day)

                if day % 7 == weekday:
                    expected = True
                else:
                    expected = False
            assertOnOffset(offset, date, expected)

    def test_offsets_compare_equal(self):
        # root cause of #456
        offset1 = Week()
        offset2 = Week()
        self.assertFalse(offset1 != offset2)

class TestWeekOfMonth(unittest.TestCase):

    def test_constructor(self):
        self.assertRaises(Exception, WeekOfMonth, n=0, week=1, weekday=1)
        self.assertRaises(Exception, WeekOfMonth, n=1, week=4, weekday=0)
        self.assertRaises(Exception, WeekOfMonth, n=1, week=-1, weekday=0)
        self.assertRaises(Exception, WeekOfMonth, n=1, week=0, weekday=-1)
        self.assertRaises(Exception, WeekOfMonth, n=1, week=0, weekday=7)

    def test_offset(self):
        date1 = datetime(2011, 1, 4) # 1st Tuesday of Month
        date2 = datetime(2011, 1, 11) # 2nd Tuesday of Month
        date3 = datetime(2011, 1, 18) # 3rd Tuesday of Month
        date4 = datetime(2011, 1, 25) # 4th Tuesday of Month

        # see for loop for structure
        test_cases = [
            (-2, 2, 1, date1, datetime(2010, 11, 16)),
            (-2, 2, 1, date2, datetime(2010, 11, 16)),
            (-2, 2, 1, date3, datetime(2010, 11, 16)),
            (-2, 2, 1, date4, datetime(2010, 12, 21)),

            (-1, 2, 1, date1, datetime(2010, 12, 21)),
            (-1, 2, 1, date2, datetime(2010, 12, 21)),
            (-1, 2, 1, date3, datetime(2010, 12, 21)),
            (-1, 2, 1, date4, datetime(2011, 1, 18)),

            (1, 0, 0, date1, datetime(2011, 2, 7)),
            (1, 0, 0, date2, datetime(2011, 2, 7)),
            (1, 0, 0, date3, datetime(2011, 2, 7)),
            (1, 0, 0, date4, datetime(2011, 2, 7)),
            (1, 0, 1, date1, datetime(2011, 2, 1)),
            (1, 0, 1, date2, datetime(2011, 2, 1)),
            (1, 0, 1, date3, datetime(2011, 2, 1)),
            (1, 0, 1, date4, datetime(2011, 2, 1)),
            (1, 0, 2, date1, datetime(2011, 1, 5)),
            (1, 0, 2, date2, datetime(2011, 2, 2)),
            (1, 0, 2, date3, datetime(2011, 2, 2)),
            (1, 0, 2, date4, datetime(2011, 2, 2)),

            (1, 2, 1, date1, datetime(2011, 1, 18)),
            (1, 2, 1, date2, datetime(2011, 1, 18)),
            (1, 2, 1, date3, datetime(2011, 2, 15)),
            (1, 2, 1, date4, datetime(2011, 2, 15)),

            (2, 2, 1, date1, datetime(2011, 2, 15)),
            (2, 2, 1, date2, datetime(2011, 2, 15)),
            (2, 2, 1, date3, datetime(2011, 3, 15)),
            (2, 2, 1, date4, datetime(2011, 3, 15)),
        ]

        for n, week, weekday, date, expected in test_cases:
            offset = WeekOfMonth(n, week=week, weekday=weekday)
            assertEq(offset, date, expected)

        # try subtracting
        result = datetime(2011, 2, 1) - WeekOfMonth(week=1, weekday=2)
        self.assertEqual(result, datetime(2011, 1, 12))
        result = datetime(2011, 2, 3) - WeekOfMonth(week=0, weekday=2)
        self.assertEqual(result, datetime(2011, 2, 2))

    def test_onOffset(self):
        test_cases = [
            (0, 0, datetime(2011, 2, 7), True),
            (0, 0, datetime(2011, 2, 6), False),
            (0, 0, datetime(2011, 2, 14), False),
            (1, 0, datetime(2011, 2, 14), True),
            (0, 1, datetime(2011, 2, 1), True),
            (0, 1, datetime(2011, 2, 8), False),
        ]

        for week, weekday, date, expected in test_cases:
            offset = WeekOfMonth(week=week, weekday=weekday)
            self.assert_(offset.onOffset(date) == expected)

class TestBMonthBegin(unittest.TestCase):
    def test_offset(self):
        tests = []

        tests.append((BMonthBegin(),
                     {datetime(2008, 1, 1): datetime(2008, 2, 1),
                      datetime(2008, 1, 31): datetime(2008, 2, 1),
                      datetime(2006, 12, 29): datetime(2007, 1, 1),
                      datetime(2006, 12, 31): datetime(2007, 1, 1),
                      datetime(2006, 9, 1): datetime(2006, 10, 2),
                      datetime(2007, 1, 1): datetime(2007, 2, 1),
                      datetime(2006, 12, 1): datetime(2007, 1, 1)}))

        tests.append((BMonthBegin(0),
                      {datetime(2008, 1, 1): datetime(2008, 1, 1),
                       datetime(2006, 10, 2): datetime(2006, 10, 2),
                       datetime(2008, 1, 31): datetime(2008, 2, 1),
                       datetime(2006, 12, 29): datetime(2007, 1, 1),
                       datetime(2006, 12, 31): datetime(2007, 1, 1),
                       datetime(2006, 9, 15): datetime(2006, 10, 2)}))

        tests.append((BMonthBegin(2),
                     {datetime(2008, 1, 1): datetime(2008, 3, 3),
                      datetime(2008, 1, 15): datetime(2008, 3, 3),
                      datetime(2006, 12, 29): datetime(2007, 2, 1),
                      datetime(2006, 12, 31): datetime(2007, 2, 1),
                      datetime(2007, 1, 1): datetime(2007, 3, 1),
                      datetime(2006, 11, 1): datetime(2007, 1, 1)}))

        tests.append((BMonthBegin(-1),
                     {datetime(2007, 1, 1): datetime(2006, 12, 1),
                      datetime(2008, 6, 30): datetime(2008, 6, 2),
                      datetime(2008, 6, 1): datetime(2008, 5, 1),
                      datetime(2008, 3, 10): datetime(2008, 3, 3),
                      datetime(2008, 12, 31): datetime(2008, 12, 1),
                      datetime(2006, 12, 29): datetime(2006, 12, 1),
                      datetime(2006, 12, 30): datetime(2006, 12, 1),
                      datetime(2007, 1, 1): datetime(2006, 12, 1)}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

    def test_onOffset(self):

        tests = [(BMonthBegin(), datetime(2007, 12, 31), False),
                 (BMonthBegin(), datetime(2008, 1, 1), True),
                 (BMonthBegin(), datetime(2008, 3, 3), True)]

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

    def test_offsets_compare_equal(self):
        # root cause of #456
        offset1 = BMonthBegin()
        offset2 = BMonthBegin()
        self.assertFalse(offset1 != offset2)


class TestBMonthEnd(unittest.TestCase):

    def test_offset(self):
        tests = []

        tests.append((BMonthEnd(),
                     {datetime(2008, 1, 1): datetime(2008, 1, 31),
                      datetime(2008, 1, 31): datetime(2008, 2, 29),
                      datetime(2006, 12, 29): datetime(2007, 1, 31),
                      datetime(2006, 12, 31): datetime(2007, 1, 31),
                      datetime(2007, 1, 1): datetime(2007, 1, 31),
                      datetime(2006, 12, 1): datetime(2006, 12, 29)}))

        tests.append((BMonthEnd(0),
                      {datetime(2008, 1, 1): datetime(2008, 1, 31),
                       datetime(2008, 1, 31): datetime(2008, 1, 31),
                       datetime(2006, 12, 29): datetime(2006, 12, 29),
                       datetime(2006, 12, 31): datetime(2007, 1, 31),
                       datetime(2007, 1, 1): datetime(2007, 1, 31)}))

        tests.append((BMonthEnd(2),
                     {datetime(2008, 1, 1): datetime(2008, 2, 29),
                      datetime(2008, 1, 31): datetime(2008, 3, 31),
                      datetime(2006, 12, 29): datetime(2007, 2, 28),
                      datetime(2006, 12, 31): datetime(2007, 2, 28),
                      datetime(2007, 1, 1): datetime(2007, 2, 28),
                      datetime(2006, 11, 1): datetime(2006, 12, 29)}))

        tests.append((BMonthEnd(-1),
                     {datetime(2007, 1, 1): datetime(2006, 12, 29),
                      datetime(2008, 6, 30): datetime(2008, 5, 30),
                      datetime(2008, 12, 31): datetime(2008, 11, 28),
                      datetime(2006, 12, 29): datetime(2006, 11, 30),
                      datetime(2006, 12, 30): datetime(2006, 12, 29),
                      datetime(2007, 1, 1): datetime(2006, 12, 29)}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

    def test_normalize(self):
        dt = datetime(2007, 1, 1, 3)

        result = dt + BMonthEnd()
        expected = dt.replace(hour=0) + BMonthEnd()
        self.assertEqual(result, expected)

    def test_onOffset(self):

        tests = [(BMonthEnd(), datetime(2007, 12, 31), True),
                 (BMonthEnd(), datetime(2008, 1, 1), False)]

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

    def test_offsets_compare_equal(self):
        # root cause of #456
        offset1 = BMonthEnd()
        offset2 = BMonthEnd()
        self.assertFalse(offset1 != offset2)

class TestMonthBegin(unittest.TestCase):

    def test_offset(self):
        tests = []

        #NOTE: I'm not entirely happy with the logic here for Begin -ss
        #see thread 'offset conventions' on the ML
        tests.append((MonthBegin(),
                     {datetime(2008, 1, 31): datetime(2008, 2, 1),
                      datetime(2008, 2, 1): datetime(2008, 3, 1),
                      datetime(2006, 12, 31): datetime(2007, 1, 1),
                      datetime(2006, 12, 1): datetime(2007, 1, 1),
                      datetime(2007, 1, 31): datetime(2007, 2, 1)}))

        tests.append((MonthBegin(0),
                      {datetime(2008, 1, 31): datetime(2008, 2, 1),
                       datetime(2008, 1, 1): datetime(2008, 1, 1),
                       datetime(2006, 12, 3): datetime(2007, 1, 1),
                       datetime(2007, 1, 31): datetime(2007, 2, 1)}))

        tests.append((MonthBegin(2),
                     {datetime(2008, 2, 29): datetime(2008, 4, 1),
                      datetime(2008, 1, 31): datetime(2008, 3, 1),
                      datetime(2006, 12, 31): datetime(2007, 2, 1),
                      datetime(2007, 12, 28): datetime(2008, 2, 1),
                      datetime(2007, 1, 1): datetime(2007, 3, 1),
                      datetime(2006, 11, 1): datetime(2007, 1, 1)}))

        tests.append((MonthBegin(-1),
                     {datetime(2007, 1, 1): datetime(2006, 12, 1),
                      datetime(2008, 5, 31): datetime(2008, 5, 1),
                      datetime(2008, 12, 31): datetime(2008, 12, 1),
                      datetime(2006, 12, 29): datetime(2006, 12, 1),
                      datetime(2006, 1, 2): datetime(2006, 1, 1)}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

class TestMonthEnd(unittest.TestCase):

    def test_offset(self):
        tests = []

        tests.append((MonthEnd(),
                     {datetime(2008, 1, 1): datetime(2008, 1, 31),
                      datetime(2008, 1, 31): datetime(2008, 2, 29),
                      datetime(2006, 12, 29): datetime(2006, 12, 31),
                      datetime(2006, 12, 31): datetime(2007, 1, 31),
                      datetime(2007, 1, 1): datetime(2007, 1, 31),
                      datetime(2006, 12, 1): datetime(2006, 12, 31)}))

        tests.append((MonthEnd(0),
                      {datetime(2008, 1, 1): datetime(2008, 1, 31),
                       datetime(2008, 1, 31): datetime(2008, 1, 31),
                       datetime(2006, 12, 29): datetime(2006, 12, 31),
                       datetime(2006, 12, 31): datetime(2006, 12, 31),
                       datetime(2007, 1, 1): datetime(2007, 1, 31)}))

        tests.append((MonthEnd(2),
                     {datetime(2008, 1, 1): datetime(2008, 2, 29),
                      datetime(2008, 1, 31): datetime(2008, 3, 31),
                      datetime(2006, 12, 29): datetime(2007, 1, 31),
                      datetime(2006, 12, 31): datetime(2007, 2, 28),
                      datetime(2007, 1, 1): datetime(2007, 2, 28),
                      datetime(2006, 11, 1): datetime(2006, 12, 31)}))

        tests.append((MonthEnd(-1),
                     {datetime(2007, 1, 1): datetime(2006, 12, 31),
                      datetime(2008, 6, 30): datetime(2008, 5, 31),
                      datetime(2008, 12, 31): datetime(2008, 11, 30),
                      datetime(2006, 12, 29): datetime(2006, 11, 30),
                      datetime(2006, 12, 30): datetime(2006, 11, 30),
                      datetime(2007, 1, 1): datetime(2006, 12, 31)}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

    def test_normalize(self):
        dt = datetime(2007, 1, 1, 3)

        result = dt + MonthEnd()
        expected = dt.replace(hour=0) + MonthEnd()
        self.assertEqual(result, expected)

    def test_onOffset(self):

        tests = [(MonthEnd(), datetime(2007, 12, 31), True),
                 (MonthEnd(), datetime(2008, 1, 1), False)]

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

class TestBQuarterBegin(unittest.TestCase):

    def test_isAnchored(self):
        self.assert_(BQuarterBegin(startingMonth=1).isAnchored())
        self.assert_(BQuarterBegin().isAnchored())
        self.assert_(not BQuarterBegin(2, startingMonth=1).isAnchored())

    def test_offset(self):
        tests = []

        tests.append((BQuarterBegin(startingMonth=1),
                      {datetime(2008, 1, 1): datetime(2008, 4, 1),
                       datetime(2008, 1, 31): datetime(2008, 4, 1),
                       datetime(2008, 2, 15): datetime(2008, 4, 1),
                       datetime(2008, 2, 29): datetime(2008, 4, 1),
                       datetime(2008, 3, 15): datetime(2008, 4, 1),
                       datetime(2008, 3, 31): datetime(2008, 4, 1),
                       datetime(2008, 4, 15): datetime(2008, 7, 1),
                       datetime(2007, 3, 15): datetime(2007, 4, 2),
                       datetime(2007, 2, 28): datetime(2007, 4, 2),
                       datetime(2007, 1, 1): datetime(2007, 4, 2),
                       datetime(2007, 4, 15): datetime(2007, 7, 2),
                       datetime(2007, 7, 1): datetime(2007, 7, 2),
                       datetime(2007, 4, 1): datetime(2007, 4, 2),
                       datetime(2007, 4, 2): datetime(2007, 7, 2),
                       datetime(2008, 4, 30): datetime(2008, 7, 1),}))

        tests.append((BQuarterBegin(startingMonth=2),
                      {datetime(2008, 1, 1): datetime(2008, 2, 1),
                       datetime(2008, 1, 31): datetime(2008, 2, 1),
                       datetime(2008, 1, 15): datetime(2008, 2, 1),
                       datetime(2008, 2, 29): datetime(2008, 5, 1),
                       datetime(2008, 3, 15): datetime(2008, 5, 1),
                       datetime(2008, 3, 31): datetime(2008, 5, 1),
                       datetime(2008, 4, 15): datetime(2008, 5, 1),
                       datetime(2008, 8, 15): datetime(2008, 11, 3),
                       datetime(2008, 9, 15): datetime(2008, 11, 3),
                       datetime(2008, 11, 1): datetime(2008, 11, 3),
                       datetime(2008, 4, 30): datetime(2008, 5, 1),}))

        tests.append((BQuarterBegin(startingMonth=1, n=0),
                      {datetime(2008, 1, 1): datetime(2008, 1, 1),
                       datetime(2007, 12, 31): datetime(2008, 1, 1),
                       datetime(2008, 2, 15): datetime(2008, 4, 1),
                       datetime(2008, 2, 29): datetime(2008, 4, 1),
                       datetime(2008, 1, 15): datetime(2008, 4, 1),
                       datetime(2008, 2, 27): datetime(2008, 4, 1),
                       datetime(2008, 3, 15): datetime(2008, 4, 1),
                       datetime(2007, 4, 1): datetime(2007, 4, 2),
                       datetime(2007, 4, 2): datetime(2007, 4, 2),
                       datetime(2007, 7, 1): datetime(2007, 7, 2),
                       datetime(2007, 4, 15): datetime(2007, 7, 2),
                       datetime(2007, 7, 2): datetime(2007, 7, 2),}))

        tests.append((BQuarterBegin(startingMonth=1, n=-1),
                      {datetime(2008, 1, 1): datetime(2007, 10, 1),
                       datetime(2008, 1, 31): datetime(2008, 1, 1),
                       datetime(2008, 2, 15): datetime(2008, 1, 1),
                       datetime(2008, 2, 29): datetime(2008, 1, 1),
                       datetime(2008, 3, 15): datetime(2008, 1, 1),
                       datetime(2008, 3, 31): datetime(2008, 1, 1),
                       datetime(2008, 4, 15): datetime(2008, 4, 1),
                       datetime(2007, 7, 3): datetime(2007, 7, 2),
                       datetime(2007, 4, 3): datetime(2007, 4, 2),
                       datetime(2007, 7, 2): datetime(2007, 4, 2),
                       datetime(2008, 4, 1): datetime(2008, 1, 1),}))

        tests.append((BQuarterBegin(startingMonth=1, n=2),
                      {datetime(2008, 1, 1): datetime(2008, 7, 1),
                       datetime(2008, 1, 15): datetime(2008, 7, 1),
                       datetime(2008, 2, 29): datetime(2008, 7, 1),
                       datetime(2008, 3, 15): datetime(2008, 7, 1),
                       datetime(2007, 3, 31): datetime(2007, 7, 2),
                       datetime(2007, 4, 15): datetime(2007, 10, 1),
                       datetime(2008, 4, 30): datetime(2008, 10, 1),}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

        # corner
        offset = BQuarterBegin(n=-1, startingMonth=1)
        self.assertEqual(datetime(2007, 4, 3) + offset, datetime(2007, 4, 2))

class TestBQuarterEnd(unittest.TestCase):

    def test_isAnchored(self):
        self.assert_(BQuarterEnd(startingMonth=1).isAnchored())
        self.assert_(BQuarterEnd().isAnchored())
        self.assert_(not BQuarterEnd(2, startingMonth=1).isAnchored())

    def test_offset(self):
        tests = []

        tests.append((BQuarterEnd(startingMonth=1),
                      {datetime(2008, 1, 1): datetime(2008, 1, 31),
                       datetime(2008, 1, 31): datetime(2008, 4, 30),
                       datetime(2008, 2, 15): datetime(2008, 4, 30),
                       datetime(2008, 2, 29): datetime(2008, 4, 30),
                       datetime(2008, 3, 15): datetime(2008, 4, 30),
                       datetime(2008, 3, 31): datetime(2008, 4, 30),
                       datetime(2008, 4, 15): datetime(2008, 4, 30),
                       datetime(2008, 4, 30): datetime(2008, 7, 31),}))

        tests.append((BQuarterEnd(startingMonth=2),
                      {datetime(2008, 1, 1): datetime(2008, 2, 29),
                       datetime(2008, 1, 31): datetime(2008, 2, 29),
                       datetime(2008, 2, 15): datetime(2008, 2, 29),
                       datetime(2008, 2, 29): datetime(2008, 5, 30),
                       datetime(2008, 3, 15): datetime(2008, 5, 30),
                       datetime(2008, 3, 31): datetime(2008, 5, 30),
                       datetime(2008, 4, 15): datetime(2008, 5, 30),
                       datetime(2008, 4, 30): datetime(2008, 5, 30),}))

        tests.append((BQuarterEnd(startingMonth=1, n=0),
                      {datetime(2008, 1, 1): datetime(2008, 1, 31),
                       datetime(2008, 1, 31): datetime(2008, 1, 31),
                       datetime(2008, 2, 15): datetime(2008, 4, 30),
                       datetime(2008, 2, 29): datetime(2008, 4, 30),
                       datetime(2008, 3, 15): datetime(2008, 4, 30),
                       datetime(2008, 3, 31): datetime(2008, 4, 30),
                       datetime(2008, 4, 15): datetime(2008, 4, 30),
                       datetime(2008, 4, 30): datetime(2008, 4, 30),}))

        tests.append((BQuarterEnd(startingMonth=1, n=-1),
                      {datetime(2008, 1, 1): datetime(2007, 10, 31),
                       datetime(2008, 1, 31): datetime(2007, 10, 31),
                       datetime(2008, 2, 15): datetime(2008, 1, 31),
                       datetime(2008, 2, 29): datetime(2008, 1, 31),
                       datetime(2008, 3, 15): datetime(2008, 1, 31),
                       datetime(2008, 3, 31): datetime(2008, 1, 31),
                       datetime(2008, 4, 15): datetime(2008, 1, 31),
                       datetime(2008, 4, 30): datetime(2008, 1, 31),}))

        tests.append((BQuarterEnd(startingMonth=1, n=2),
                      {datetime(2008, 1, 31): datetime(2008, 7, 31),
                       datetime(2008, 2, 15): datetime(2008, 7, 31),
                       datetime(2008, 2, 29): datetime(2008, 7, 31),
                       datetime(2008, 3, 15): datetime(2008, 7, 31),
                       datetime(2008, 3, 31): datetime(2008, 7, 31),
                       datetime(2008, 4, 15): datetime(2008, 7, 31),
                       datetime(2008, 4, 30): datetime(2008, 10, 31),}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

        # corner
        offset = BQuarterEnd(n=-1, startingMonth=1)
        self.assertEqual(datetime(2010, 1, 31) + offset, datetime(2010, 1, 29))

    def test_onOffset(self):

        tests = [(BQuarterEnd(1, startingMonth=1), datetime(2008, 1, 31), True),
                 (BQuarterEnd(1, startingMonth=1), datetime(2007, 12, 31), False),
                 (BQuarterEnd(1, startingMonth=1), datetime(2008, 2, 29), False),
                 (BQuarterEnd(1, startingMonth=1), datetime(2007, 3, 30), False),
                 (BQuarterEnd(1, startingMonth=1), datetime(2007, 3, 31), False),
                 (BQuarterEnd(1, startingMonth=1), datetime(2008, 4, 30), True),
                 (BQuarterEnd(1, startingMonth=1), datetime(2008, 5, 30), False),
                 (BQuarterEnd(1, startingMonth=1), datetime(2007, 6, 29), False),
                 (BQuarterEnd(1, startingMonth=1), datetime(2007, 6, 30), False),

                 (BQuarterEnd(1, startingMonth=2), datetime(2008, 1, 31), False),
                 (BQuarterEnd(1, startingMonth=2), datetime(2007, 12, 31), False),
                 (BQuarterEnd(1, startingMonth=2), datetime(2008, 2, 29), True),
                 (BQuarterEnd(1, startingMonth=2), datetime(2007, 3, 30), False),
                 (BQuarterEnd(1, startingMonth=2), datetime(2007, 3, 31), False),
                 (BQuarterEnd(1, startingMonth=2), datetime(2008, 4, 30), False),
                 (BQuarterEnd(1, startingMonth=2), datetime(2008, 5, 30), True),
                 (BQuarterEnd(1, startingMonth=2), datetime(2007, 6, 29), False),
                 (BQuarterEnd(1, startingMonth=2), datetime(2007, 6, 30), False),

                 (BQuarterEnd(1, startingMonth=3), datetime(2008, 1, 31), False),
                 (BQuarterEnd(1, startingMonth=3), datetime(2007, 12, 31), True),
                 (BQuarterEnd(1, startingMonth=3), datetime(2008, 2, 29), False),
                 (BQuarterEnd(1, startingMonth=3), datetime(2007, 3, 30), True),
                 (BQuarterEnd(1, startingMonth=3), datetime(2007, 3, 31), False),
                 (BQuarterEnd(1, startingMonth=3), datetime(2008, 4, 30), False),
                 (BQuarterEnd(1, startingMonth=3), datetime(2008, 5, 30), False),
                 (BQuarterEnd(1, startingMonth=3), datetime(2007, 6, 29), True),
                 (BQuarterEnd(1, startingMonth=3), datetime(2007, 6, 30), False),
             ]

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

class TestQuarterBegin(unittest.TestCase):
    def test_isAnchored(self):
        self.assert_(QuarterBegin(startingMonth=1).isAnchored())
        self.assert_(QuarterBegin().isAnchored())
        self.assert_(not QuarterBegin(2, startingMonth=1).isAnchored())

    def test_offset(self):
        tests = []

        tests.append((QuarterBegin(startingMonth=1),
                      {datetime(2007, 12, 1): datetime(2008, 1, 1),
                       datetime(2008, 1, 1): datetime(2008, 4, 1),
                       datetime(2008, 2, 15): datetime(2008, 4, 1),
                       datetime(2008, 2, 29): datetime(2008, 4, 1),
                       datetime(2008, 3, 15): datetime(2008, 4, 1),
                       datetime(2008, 3, 31): datetime(2008, 4, 1),
                       datetime(2008, 4, 15): datetime(2008, 7, 1),
                       datetime(2008, 4, 1): datetime(2008, 7, 1),}))

        tests.append((QuarterBegin(startingMonth=2),
                      {datetime(2008, 1, 1): datetime(2008, 2, 1),
                       datetime(2008, 1, 31): datetime(2008, 2, 1),
                       datetime(2008, 1, 15): datetime(2008, 2, 1),
                       datetime(2008, 2, 29): datetime(2008, 5, 1),
                       datetime(2008, 3, 15): datetime(2008, 5, 1),
                       datetime(2008, 3, 31): datetime(2008, 5, 1),
                       datetime(2008, 4, 15): datetime(2008, 5, 1),
                       datetime(2008, 4, 30): datetime(2008, 5, 1),}))

        tests.append((QuarterBegin(startingMonth=1, n=0),
                      {datetime(2008, 1, 1): datetime(2008, 1, 1),
                       datetime(2008, 12, 1): datetime(2009, 1, 1),
                       datetime(2008, 1, 1): datetime(2008, 1, 1),
                       datetime(2008, 2, 15): datetime(2008, 4, 1),
                       datetime(2008, 2, 29): datetime(2008, 4, 1),
                       datetime(2008, 3, 15): datetime(2008, 4, 1),
                       datetime(2008, 3, 31): datetime(2008, 4, 1),
                       datetime(2008, 4, 15): datetime(2008, 4, 1),
                       datetime(2008, 4, 30): datetime(2008, 4, 1),}))

        tests.append((QuarterBegin(startingMonth=1, n=-1),
                      {datetime(2008, 1, 1): datetime(2007, 10, 1),
                       datetime(2008, 1, 31): datetime(2008, 1, 1),
                       datetime(2008, 2, 15): datetime(2008, 1, 1),
                       datetime(2008, 2, 29): datetime(2008, 1, 1),
                       datetime(2008, 3, 15): datetime(2008, 1, 1),
                       datetime(2008, 3, 31): datetime(2008, 1, 1),
                       datetime(2008, 4, 15): datetime(2008, 4, 1),
                       datetime(2008, 4, 30): datetime(2008, 4, 1),
                       datetime(2008, 7, 1): datetime(2008, 4, 1)}))

        tests.append((QuarterBegin(startingMonth=1, n=2),
                      {datetime(2008, 1, 1): datetime(2008, 7, 1),
                       datetime(2008, 2, 15): datetime(2008, 7, 1),
                       datetime(2008, 2, 29): datetime(2008, 7, 1),
                       datetime(2008, 3, 15): datetime(2008, 7, 1),
                       datetime(2008, 3, 31): datetime(2008, 7, 1),
                       datetime(2008, 4, 15): datetime(2008, 10, 1),
                       datetime(2008, 4, 1): datetime(2008, 10, 1),}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

        # corner
        offset = QuarterBegin(n=-1, startingMonth=1)
        self.assertEqual(datetime(2010, 2, 1) + offset, datetime(2010, 1, 1))

class TestQuarterEnd(unittest.TestCase):

    def test_isAnchored(self):
        self.assert_(QuarterEnd(startingMonth=1).isAnchored())
        self.assert_(QuarterEnd().isAnchored())
        self.assert_(not QuarterEnd(2, startingMonth=1).isAnchored())

    def test_offset(self):
        tests = []

        tests.append((QuarterEnd(startingMonth=1),
                      {datetime(2008, 1, 1): datetime(2008, 1, 31),
                       datetime(2008, 1, 31): datetime(2008, 4, 30),
                       datetime(2008, 2, 15): datetime(2008, 4, 30),
                       datetime(2008, 2, 29): datetime(2008, 4, 30),
                       datetime(2008, 3, 15): datetime(2008, 4, 30),
                       datetime(2008, 3, 31): datetime(2008, 4, 30),
                       datetime(2008, 4, 15): datetime(2008, 4, 30),
                       datetime(2008, 4, 30): datetime(2008, 7, 31),}))

        tests.append((QuarterEnd(startingMonth=2),
                      {datetime(2008, 1, 1): datetime(2008, 2, 29),
                       datetime(2008, 1, 31): datetime(2008, 2, 29),
                       datetime(2008, 2, 15): datetime(2008, 2, 29),
                       datetime(2008, 2, 29): datetime(2008, 5, 31),
                       datetime(2008, 3, 15): datetime(2008, 5, 31),
                       datetime(2008, 3, 31): datetime(2008, 5, 31),
                       datetime(2008, 4, 15): datetime(2008, 5, 31),
                       datetime(2008, 4, 30): datetime(2008, 5, 31),}))

        tests.append((QuarterEnd(startingMonth=1, n=0),
                      {datetime(2008, 1, 1): datetime(2008, 1, 31),
                       datetime(2008, 1, 31): datetime(2008, 1, 31),
                       datetime(2008, 2, 15): datetime(2008, 4, 30),
                       datetime(2008, 2, 29): datetime(2008, 4, 30),
                       datetime(2008, 3, 15): datetime(2008, 4, 30),
                       datetime(2008, 3, 31): datetime(2008, 4, 30),
                       datetime(2008, 4, 15): datetime(2008, 4, 30),
                       datetime(2008, 4, 30): datetime(2008, 4, 30),}))

        tests.append((QuarterEnd(startingMonth=1, n=-1),
                      {datetime(2008, 1, 1): datetime(2007, 10, 31),
                       datetime(2008, 1, 31): datetime(2007, 10, 31),
                       datetime(2008, 2, 15): datetime(2008, 1, 31),
                       datetime(2008, 2, 29): datetime(2008, 1, 31),
                       datetime(2008, 3, 15): datetime(2008, 1, 31),
                       datetime(2008, 3, 31): datetime(2008, 1, 31),
                       datetime(2008, 4, 15): datetime(2008, 1, 31),
                       datetime(2008, 4, 30): datetime(2008, 1, 31),
                       datetime(2008, 7, 1): datetime(2008, 4, 30)}))

        tests.append((QuarterEnd(startingMonth=1, n=2),
                      {datetime(2008, 1, 31): datetime(2008, 7, 31),
                       datetime(2008, 2, 15): datetime(2008, 7, 31),
                       datetime(2008, 2, 29): datetime(2008, 7, 31),
                       datetime(2008, 3, 15): datetime(2008, 7, 31),
                       datetime(2008, 3, 31): datetime(2008, 7, 31),
                       datetime(2008, 4, 15): datetime(2008, 7, 31),
                       datetime(2008, 4, 30): datetime(2008, 10, 31),}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

        # corner
        offset = QuarterEnd(n=-1, startingMonth=1)
        self.assertEqual(datetime(2010, 2, 1) + offset, datetime(2010, 1, 31))

    def test_onOffset(self):

        tests = [(QuarterEnd(1, startingMonth=1), datetime(2008, 1, 31), True),
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

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

class TestBYearBegin(unittest.TestCase):
    def test_offset(self):
        tests = []

        tests.append((BYearBegin(),
            {datetime(2008, 1, 1): datetime(2009, 1, 1),
             datetime(2008, 6, 30): datetime(2009, 1, 1),
             datetime(2008, 12, 31): datetime(2009, 1, 1),
             datetime(2011, 1, 1) : datetime(2011, 1, 3),
             datetime(2011, 1, 3) : datetime(2012, 1, 2),
             datetime(2005, 12, 30) : datetime(2006, 1, 2),
             datetime(2005, 12, 31) : datetime(2006, 1, 2)
             }
            ))

        tests.append((BYearBegin(0),
                      {datetime(2008, 1, 1): datetime(2008, 1, 1),
                       datetime(2008, 6, 30): datetime(2009, 1, 1),
                       datetime(2008, 12, 31): datetime(2009, 1, 1),
                       datetime(2005, 12, 30): datetime(2006, 1, 2),
                       datetime(2005, 12, 31): datetime(2006, 1, 2),}))

        tests.append((BYearBegin(-1),
                      {datetime(2007, 1, 1): datetime(2006, 1, 2),
                       datetime(2009, 1, 4): datetime(2009, 1, 1),
                       datetime(2009, 1, 1): datetime(2008, 1, 1),
                       datetime(2008, 6, 30): datetime(2008, 1, 1),
                       datetime(2008, 12, 31): datetime(2008, 1, 1),
                       datetime(2006, 12, 29): datetime(2006, 1, 2),
                       datetime(2006, 12, 30): datetime(2006, 1, 2),
                       datetime(2006, 1, 1): datetime(2005, 1, 3),}))

        tests.append((BYearBegin(-2),
                      {datetime(2007, 1, 1): datetime(2005, 1, 3),
                       datetime(2007, 6, 30): datetime(2006, 1, 2),
                       datetime(2008, 12, 31): datetime(2007, 1, 1),}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)


class TestYearBegin(unittest.TestCase):

    def test_offset(self):
        tests = []

        tests.append((YearBegin(),
                      {datetime(2008, 1, 1): datetime(2009, 1, 1),
                       datetime(2008, 6, 30): datetime(2009, 1, 1),
                       datetime(2008, 12, 31): datetime(2009, 1, 1),
                       datetime(2005, 12, 30): datetime(2006, 1, 1),
                       datetime(2005, 12, 31): datetime(2006, 1, 1),}))

        tests.append((YearBegin(0),
                      {datetime(2008, 1, 1): datetime(2008, 1, 1),
                       datetime(2008, 6, 30): datetime(2009, 1, 1),
                       datetime(2008, 12, 31): datetime(2009, 1, 1),
                       datetime(2005, 12, 30): datetime(2006, 1, 1),
                       datetime(2005, 12, 31): datetime(2006, 1, 1),}))


        tests.append((YearBegin(-1),
                      {datetime(2007, 1, 1): datetime(2006, 1, 1),
                       datetime(2008, 6, 30): datetime(2008, 1, 1),
                       datetime(2008, 12, 31): datetime(2008, 1, 1),
                       datetime(2006, 12, 29): datetime(2006, 1, 1),
                       datetime(2006, 12, 30): datetime(2006, 1, 1),
                       datetime(2007, 1, 1): datetime(2006, 1, 1),}))

        tests.append((YearBegin(-2),
                      {datetime(2007, 1, 1): datetime(2005, 1, 1),
                       datetime(2008, 6, 30): datetime(2007, 1, 1),
                       datetime(2008, 12, 31): datetime(2007, 1, 1),}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)


    def test_onOffset(self):

        tests = [
            (YearBegin(), datetime(2007, 1, 3), False),
            (YearBegin(), datetime(2008, 1, 1), True),
            (YearBegin(), datetime(2006, 12, 31), False),
            (YearBegin(), datetime(2006, 1, 2), False),
        ]

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

class TestBYearEndLagged(unittest.TestCase):

    def test_bad_month_fail(self):
        self.assertRaises(Exception, BYearEnd, month=13)
        self.assertRaises(Exception, BYearEnd, month=0)

    def test_offset(self):
        tests = []

        tests.append((BYearEnd(month=6),
                      {datetime(2008, 1, 1): datetime(2008, 6, 30),
                      datetime(2007, 6, 30): datetime(2008, 6, 30)},
                      ))

        tests.append((BYearEnd(n=-1, month=6),
                      {datetime(2008, 1, 1): datetime(2007, 6, 29),
                      datetime(2007, 6, 30): datetime(2007, 6, 29)},
                      ))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                self.assertEqual(base + offset, expected)

    def test_roll(self):
        offset = BYearEnd(month=6)
        date = datetime(2009, 11, 30)

        self.assertEqual(offset.rollforward(date), datetime(2010, 6, 30))
        self.assertEqual(offset.rollback(date), datetime(2009, 6, 30))

    def test_onOffset(self):

        tests = [
            (BYearEnd(month=2), datetime(2007, 2, 28), True),
            (BYearEnd(month=6), datetime(2007, 6, 30), False),
        ]

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

class TestBYearEnd(unittest.TestCase):

    def test_offset(self):
        tests = []

        tests.append((BYearEnd(),
                      {datetime(2008, 1, 1): datetime(2008, 12, 31),
                       datetime(2008, 6, 30): datetime(2008, 12, 31),
                       datetime(2008, 12, 31): datetime(2009, 12, 31),
                       datetime(2005, 12, 30): datetime(2006, 12, 29),
                       datetime(2005, 12, 31): datetime(2006, 12, 29),}))

        tests.append((BYearEnd(0),
                      {datetime(2008, 1, 1): datetime(2008, 12, 31),
                       datetime(2008, 6, 30): datetime(2008, 12, 31),
                       datetime(2008, 12, 31): datetime(2008, 12, 31),
                       datetime(2005, 12, 31): datetime(2006, 12, 29),}))

        tests.append((BYearEnd(-1),
                      {datetime(2007, 1, 1): datetime(2006, 12, 29),
                       datetime(2008, 6, 30): datetime(2007, 12, 31),
                       datetime(2008, 12, 31): datetime(2007, 12, 31),
                       datetime(2006, 12, 29): datetime(2005, 12, 30),
                       datetime(2006, 12, 30): datetime(2006, 12, 29),
                       datetime(2007, 1, 1): datetime(2006, 12, 29),}))

        tests.append((BYearEnd(-2),
                      {datetime(2007, 1, 1): datetime(2005, 12, 30),
                       datetime(2008, 6, 30): datetime(2006, 12, 29),
                       datetime(2008, 12, 31): datetime(2006, 12, 29),}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

    def test_onOffset(self):

        tests = [
            (BYearEnd(), datetime(2007, 12, 31), True),
            (BYearEnd(), datetime(2008, 1, 1), False),
            (BYearEnd(), datetime(2006, 12, 31), False),
            (BYearEnd(), datetime(2006, 12, 29), True),
        ]

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

class TestYearEnd(unittest.TestCase):

    def test_offset(self):
        tests = []

        tests.append((YearEnd(),
                      {datetime(2008, 1, 1): datetime(2008, 12, 31),
                       datetime(2008, 6, 30): datetime(2008, 12, 31),
                       datetime(2008, 12, 31): datetime(2009, 12, 31),
                       datetime(2005, 12, 30): datetime(2005, 12, 31),
                       datetime(2005, 12, 31): datetime(2006, 12, 31),}))

        tests.append((YearEnd(0),
                      {datetime(2008, 1, 1): datetime(2008, 12, 31),
                       datetime(2008, 6, 30): datetime(2008, 12, 31),
                       datetime(2008, 12, 31): datetime(2008, 12, 31),
                       datetime(2005, 12, 30): datetime(2005, 12, 31),}))

        tests.append((YearEnd(-1),
                      {datetime(2007, 1, 1): datetime(2006, 12, 31),
                       datetime(2008, 6, 30): datetime(2007, 12, 31),
                       datetime(2008, 12, 31): datetime(2007, 12, 31),
                       datetime(2006, 12, 29): datetime(2005, 12, 31),
                       datetime(2006, 12, 30): datetime(2005, 12, 31),
                       datetime(2007, 1, 1): datetime(2006, 12, 31),}))

        tests.append((YearEnd(-2),
                      {datetime(2007, 1, 1): datetime(2005, 12, 31),
                       datetime(2008, 6, 30): datetime(2006, 12, 31),
                       datetime(2008, 12, 31): datetime(2006, 12, 31),}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

    def test_onOffset(self):

        tests = [
            (YearEnd(), datetime(2007, 12, 31), True),
            (YearEnd(), datetime(2008, 1, 1), False),
            (YearEnd(), datetime(2006, 12, 31), True),
            (YearEnd(), datetime(2006, 12, 29), False),
        ]

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

class TestYearEndDiffMonth(unittest.TestCase):

    def test_offset(self):
        tests = []

        tests.append((YearEnd(month=3),
                      {datetime(2008, 1, 1): datetime(2008, 3, 31),
                       datetime(2008, 2, 15): datetime(2008, 3, 31),
                       datetime(2008, 3, 31): datetime(2009, 3, 31),
                       datetime(2008, 3, 30): datetime(2008, 3, 31),
                       datetime(2005, 3, 31): datetime(2006, 3, 31),}))

        tests.append((YearEnd(0, month=3),
                      {datetime(2008, 1, 1): datetime(2008, 3, 31),
                       datetime(2008, 2, 28): datetime(2008, 3, 31),
                       datetime(2008, 3, 31): datetime(2008, 3, 31),
                       datetime(2005, 3, 30): datetime(2005, 3, 31),}))

        tests.append((YearEnd(-1, month=3),
                      {datetime(2007, 1, 1): datetime(2006, 3, 31),
                       datetime(2008, 2, 28): datetime(2007, 3, 31),
                       datetime(2008, 3, 31): datetime(2007, 3, 31),
                       datetime(2006, 3, 29): datetime(2005, 3, 31),
                       datetime(2006, 3, 30): datetime(2005, 3, 31),
                       datetime(2007, 3, 1): datetime(2006, 3, 31),}))

        tests.append((YearEnd(-2, month=3),
                      {datetime(2007, 1, 1): datetime(2005, 3, 31),
                       datetime(2008, 6, 30): datetime(2007, 3, 31),
                       datetime(2008, 3, 31): datetime(2006, 3, 31),}))

        for offset, cases in tests:
            for base, expected in cases.iteritems():
                assertEq(offset, base, expected)

    def test_onOffset(self):

        tests = [
            (YearEnd(month=3), datetime(2007, 3, 31), True),
            (YearEnd(month=3), datetime(2008, 1, 1), False),
            (YearEnd(month=3), datetime(2006, 3, 31), True),
            (YearEnd(month=3), datetime(2006, 3, 29), False),
        ]

        for offset, date, expected in tests:
            assertOnOffset(offset, date, expected)

def assertEq(offset, base, expected):
    actual = offset + base
    try:
        assert actual == expected
    except AssertionError:
        raise AssertionError("\nExpected: %s\nActual: %s\nFor Offset: %s)"
                             "\nAt Date: %s"%
                (expected, actual, offset, base))

def test_Hour():
    assertEq(Hour(), datetime(2010, 1, 1), datetime(2010, 1, 1, 1))
    assertEq(Hour(-1), datetime(2010, 1, 1, 1), datetime(2010, 1, 1))
    assertEq(2 * Hour(), datetime(2010, 1, 1), datetime(2010, 1, 1, 2))
    assertEq(-1 * Hour(), datetime(2010, 1, 1, 1), datetime(2010, 1, 1))

    assert (Hour(3) + Hour(2)) == Hour(5)
    assert (Hour(3) - Hour(2)) == Hour()

    assert(Hour(4) != Hour(1))

def test_Minute():
    assertEq(Minute(), datetime(2010, 1, 1), datetime(2010, 1, 1, 0, 1))
    assertEq(Minute(-1), datetime(2010, 1, 1, 0, 1), datetime(2010, 1, 1))
    assertEq(2 * Minute(), datetime(2010, 1, 1), datetime(2010, 1, 1, 0, 2))
    assertEq(-1 * Minute(), datetime(2010, 1, 1, 0, 1), datetime(2010, 1, 1))

    assert (Minute(3) + Minute(2)) == Minute(5)
    assert (Minute(3) - Minute(2)) == Minute()
    assert(Minute(5) != Minute())

def test_Second():
    assertEq(Second(), datetime(2010, 1, 1), datetime(2010, 1, 1, 0, 0, 1))
    assertEq(Second(-1), datetime(2010, 1, 1, 0, 0, 1), datetime(2010, 1, 1))
    assertEq(2 * Second(), datetime(2010, 1, 1), datetime(2010, 1, 1, 0, 0, 2))
    assertEq(-1 * Second(), datetime(2010, 1, 1, 0, 0, 1), datetime(2010, 1, 1))

    assert (Second(3) + Second(2)) == Second(5)
    assert (Second(3) - Second(2)) == Second()

def test_hasOffsetName():
    assert hasOffsetName(BDay())
    assert not hasOffsetName(BDay(2))

def test_get_offset_name():
    assert_raises(Exception, get_offset_name, BDay(2))

    assert get_offset_name(BDay()) == 'B'
    assert get_offset_name(BMonthEnd()) == 'BM'
    assert get_offset_name(Week(weekday=0)) == 'W-MON'
    assert get_offset_name(Week(weekday=1)) =='W-TUE'
    assert get_offset_name(Week(weekday=2)) == 'W-WED'
    assert get_offset_name(Week(weekday=3)) == 'W-THU'
    assert get_offset_name(Week(weekday=4)) == 'W-FRI'


def test_get_offset():
    assert_raises(Exception, get_offset, 'gibberish')

    assert get_offset('B') == BDay()
    assert get_offset('b') == BDay()
    assert get_offset('bm') == BMonthEnd()
    assert get_offset('Bm') == BMonthEnd()
    assert get_offset('W-MON') == Week(weekday=0)
    assert get_offset('W-TUE') == Week(weekday=1)
    assert get_offset('W-WED') == Week(weekday=2)
    assert get_offset('W-THU') == Week(weekday=3)
    assert get_offset('W-FRI') == Week(weekday=4)
    assert get_offset('w@Sat') == Week(weekday=5)

def test_parse_time_string():
    (date, parsed, reso) = parse_time_string('4Q1984')
    (date_lower, parsed_lower, reso_lower) = parse_time_string('4q1984')
    assert date == date_lower
    assert parsed == parsed_lower
    assert reso == reso_lower

def test_get_standard_freq():
    fstr = get_standard_freq('W')
    assert fstr == get_standard_freq('w')
    assert fstr == get_standard_freq('1w')
    assert fstr == get_standard_freq(('W', 1))
    assert fstr == get_standard_freq('WeEk')

    fstr = get_standard_freq('5Q')
    assert fstr == get_standard_freq('5q')
    assert fstr == get_standard_freq('5QuarTer')
    assert fstr == get_standard_freq(('q', 5))

def test_quarterly_dont_normalize():
    date = datetime(2012, 3, 31, 5, 30)

    offsets = (QuarterBegin, QuarterEnd, BQuarterEnd, BQuarterBegin)

    for klass in offsets:
        result = date + klass()
        assert(result.time() == date.time())


class TestOffsetAliases(unittest.TestCase):

    def setUp(self):
        pass

    def test_alias_equality(self):
        from pandas.tseries.frequencies import _offset_map

        for k, v in _offset_map.iteritems():
            if v is None:
                continue
            self.assertEqual(k, v.copy())

    def test_rule_code(self):
        lst = ['M', 'MS', 'BM', 'BMS', 'D', 'B', 'H', 'T', 'S', 'L', 'U']
        for k in lst:
            assert k == _offset_map[k].rule_code
            assert k == (_offset_map[k] * 3).rule_code

        suffix_lst = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN']
        base = 'W'
        for v in suffix_lst:
            alias = '-'.join([base, v])
            assert alias == _offset_map[alias].rule_code
            assert alias == (_offset_map[alias] * 5).rule_code

        suffix_lst = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG',
                      'SEP', 'OCT', 'NOV', 'DEC']
        base_lst = ['A', 'AS', 'BA', 'BAS', 'Q', 'QS', 'BQ', 'BQS']
        for base in base_lst:
            for v in suffix_lst:
                alias = '-'.join([base, v])
                assert alias == _offset_map[alias].rule_code
                assert alias == (_offset_map[alias] * 5).rule_code




if __name__ == '__main__':
    import nose
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure'],
                   exit=False)

