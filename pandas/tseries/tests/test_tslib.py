import nose
import datetime
import numpy as np
from distutils.version import LooseVersion

import pandas as pd
import pandas.util.testing as tm
from pandas import tslib, lib, compat
from pandas.tseries import offsets, tools
from pandas.tseries.frequencies import get_freq
from pandas.tseries.index import date_range, DatetimeIndex
from pandas.util.testing import _skip_if_has_locale
from pandas._period import period_ordinal, period_asfreq
from pandas.compat.numpy import np_array_datetime64_compat
from pandas.core.api import Timestamp, to_datetime, Index, Series


class TestTsUtil(tm.TestCase):

    def test_try_parse_dates(self):
        from dateutil.parser import parse
        arr = np.array(['5/1/2000', '6/1/2000', '7/1/2000'], dtype=object)

        result = lib.try_parse_dates(arr, dayfirst=True)
        expected = [parse(d, dayfirst=True) for d in arr]
        self.assertTrue(np.array_equal(result, expected))

    def test_min_valid(self):
        # Ensure that Timestamp.min is a valid Timestamp
        Timestamp(Timestamp.min)

    def test_max_valid(self):
        # Ensure that Timestamp.max is a valid Timestamp
        Timestamp(Timestamp.max)

    def test_to_datetime_bijective(self):
        # Ensure that converting to datetime and back only loses precision
        # by going from nanoseconds to microseconds.
        exp_warning = None if Timestamp.max.nanosecond == 0 else UserWarning
        with tm.assert_produces_warning(exp_warning, check_stacklevel=False):
            self.assertEqual(
                Timestamp(Timestamp.max.to_pydatetime()).value / 1000,
                Timestamp.max.value / 1000)

        exp_warning = None if Timestamp.min.nanosecond == 0 else UserWarning
        with tm.assert_produces_warning(exp_warning, check_stacklevel=False):
            self.assertEqual(
                Timestamp(Timestamp.min.to_pydatetime()).value / 1000,
                Timestamp.min.value / 1000)


class TestDatetimeParsingWrappers(tm.TestCase):
    def test_does_not_convert_mixed_integer(self):
        bad_date_strings = ('-50000', '999', '123.1234', 'm', 'T')

        for bad_date_string in bad_date_strings:
            self.assertFalse(tslib._does_string_look_like_datetime(
                bad_date_string))

        good_date_strings = ('2012-01-01',
                             '01/01/2012',
                             'Mon Sep 16, 2013',
                             '01012012',
                             '0101',
                             '1-1', )

        for good_date_string in good_date_strings:
            self.assertTrue(tslib._does_string_look_like_datetime(
                good_date_string))

    def test_parsers(self):

        # https://github.com/dateutil/dateutil/issues/217
        import dateutil
        yearfirst = dateutil.__version__ >= LooseVersion('2.5.0')

        cases = {'2011-01-01': datetime.datetime(2011, 1, 1),
                 '2Q2005': datetime.datetime(2005, 4, 1),
                 '2Q05': datetime.datetime(2005, 4, 1),
                 '2005Q1': datetime.datetime(2005, 1, 1),
                 '05Q1': datetime.datetime(2005, 1, 1),
                 '2011Q3': datetime.datetime(2011, 7, 1),
                 '11Q3': datetime.datetime(2011, 7, 1),
                 '3Q2011': datetime.datetime(2011, 7, 1),
                 '3Q11': datetime.datetime(2011, 7, 1),

                 # quarterly without space
                 '2000Q4': datetime.datetime(2000, 10, 1),
                 '00Q4': datetime.datetime(2000, 10, 1),
                 '4Q2000': datetime.datetime(2000, 10, 1),
                 '4Q00': datetime.datetime(2000, 10, 1),
                 '2000q4': datetime.datetime(2000, 10, 1),
                 '2000-Q4': datetime.datetime(2000, 10, 1),
                 '00-Q4': datetime.datetime(2000, 10, 1),
                 '4Q-2000': datetime.datetime(2000, 10, 1),
                 '4Q-00': datetime.datetime(2000, 10, 1),
                 '00q4': datetime.datetime(2000, 10, 1),
                 '2005': datetime.datetime(2005, 1, 1),
                 '2005-11': datetime.datetime(2005, 11, 1),
                 '2005 11': datetime.datetime(2005, 11, 1),
                 '11-2005': datetime.datetime(2005, 11, 1),
                 '11 2005': datetime.datetime(2005, 11, 1),
                 '200511': datetime.datetime(2020, 5, 11),
                 '20051109': datetime.datetime(2005, 11, 9),
                 '20051109 10:15': datetime.datetime(2005, 11, 9, 10, 15),
                 '20051109 08H': datetime.datetime(2005, 11, 9, 8, 0),
                 '2005-11-09 10:15': datetime.datetime(2005, 11, 9, 10, 15),
                 '2005-11-09 08H': datetime.datetime(2005, 11, 9, 8, 0),
                 '2005/11/09 10:15': datetime.datetime(2005, 11, 9, 10, 15),
                 '2005/11/09 08H': datetime.datetime(2005, 11, 9, 8, 0),
                 "Thu Sep 25 10:36:28 2003": datetime.datetime(2003, 9, 25, 10,
                                                               36, 28),
                 "Thu Sep 25 2003": datetime.datetime(2003, 9, 25),
                 "Sep 25 2003": datetime.datetime(2003, 9, 25),
                 "January 1 2014": datetime.datetime(2014, 1, 1),

                 # GH 10537
                 '2014-06': datetime.datetime(2014, 6, 1),
                 '06-2014': datetime.datetime(2014, 6, 1),
                 '2014-6': datetime.datetime(2014, 6, 1),
                 '6-2014': datetime.datetime(2014, 6, 1),

                 '20010101 12': datetime.datetime(2001, 1, 1, 12),
                 '20010101 1234': datetime.datetime(2001, 1, 1, 12, 34),
                 '20010101 123456': datetime.datetime(2001, 1, 1, 12, 34, 56),
                 }

        for date_str, expected in compat.iteritems(cases):
            result1, _, _ = tools.parse_time_string(date_str,
                                                    yearfirst=yearfirst)
            result2 = to_datetime(date_str, yearfirst=yearfirst)
            result3 = to_datetime([date_str], yearfirst=yearfirst)
            # result5 is used below
            result4 = to_datetime(np.array([date_str], dtype=object),
                                  yearfirst=yearfirst)
            result6 = DatetimeIndex([date_str], yearfirst=yearfirst)
            # result7 is used below
            result8 = DatetimeIndex(Index([date_str]), yearfirst=yearfirst)
            result9 = DatetimeIndex(Series([date_str]), yearfirst=yearfirst)

            for res in [result1, result2]:
                self.assertEqual(res, expected)
            for res in [result3, result4, result6, result8, result9]:
                exp = DatetimeIndex([pd.Timestamp(expected)])
                tm.assert_index_equal(res, exp)

            # these really need to have yearfist, but we don't support
            if not yearfirst:
                result5 = Timestamp(date_str)
                self.assertEqual(result5, expected)
                result7 = date_range(date_str, freq='S', periods=1,
                                     yearfirst=yearfirst)
                self.assertEqual(result7, expected)

        # NaT
        result1, _, _ = tools.parse_time_string('NaT')
        result2 = to_datetime('NaT')
        result3 = Timestamp('NaT')
        result4 = DatetimeIndex(['NaT'])[0]
        self.assertTrue(result1 is tslib.NaT)
        self.assertTrue(result1 is tslib.NaT)
        self.assertTrue(result1 is tslib.NaT)
        self.assertTrue(result1 is tslib.NaT)

    def test_parsers_quarter_invalid(self):

        cases = ['2Q 2005', '2Q-200A', '2Q-200', '22Q2005', '6Q-20', '2Q200.']
        for case in cases:
            self.assertRaises(ValueError, tools.parse_time_string, case)

    def test_parsers_dayfirst_yearfirst(self):
        tm._skip_if_no_dateutil()

        # OK
        # 2.5.1 10-11-12   [dayfirst=0, yearfirst=0] -> 2012-10-11 00:00:00
        # 2.5.2 10-11-12   [dayfirst=0, yearfirst=1] -> 2012-10-11 00:00:00
        # 2.5.3 10-11-12   [dayfirst=0, yearfirst=0] -> 2012-10-11 00:00:00

        # OK
        # 2.5.1 10-11-12   [dayfirst=0, yearfirst=1] -> 2010-11-12 00:00:00
        # 2.5.2 10-11-12   [dayfirst=0, yearfirst=1] -> 2010-11-12 00:00:00
        # 2.5.3 10-11-12   [dayfirst=0, yearfirst=1] -> 2010-11-12 00:00:00

        # bug fix in 2.5.2
        # 2.5.1 10-11-12   [dayfirst=1, yearfirst=1] -> 2010-11-12 00:00:00
        # 2.5.2 10-11-12   [dayfirst=1, yearfirst=1] -> 2010-12-11 00:00:00
        # 2.5.3 10-11-12   [dayfirst=1, yearfirst=1] -> 2010-12-11 00:00:00

        # OK
        # 2.5.1 10-11-12   [dayfirst=1, yearfirst=0] -> 2012-11-10 00:00:00
        # 2.5.2 10-11-12   [dayfirst=1, yearfirst=0] -> 2012-11-10 00:00:00
        # 2.5.3 10-11-12   [dayfirst=1, yearfirst=0] -> 2012-11-10 00:00:00

        # OK
        # 2.5.1 20/12/21   [dayfirst=0, yearfirst=0] -> 2021-12-20 00:00:00
        # 2.5.2 20/12/21   [dayfirst=0, yearfirst=0] -> 2021-12-20 00:00:00
        # 2.5.3 20/12/21   [dayfirst=0, yearfirst=0] -> 2021-12-20 00:00:00

        # OK
        # 2.5.1 20/12/21   [dayfirst=0, yearfirst=1] -> 2020-12-21 00:00:00
        # 2.5.2 20/12/21   [dayfirst=0, yearfirst=1] -> 2020-12-21 00:00:00
        # 2.5.3 20/12/21   [dayfirst=0, yearfirst=1] -> 2020-12-21 00:00:00

        # revert of bug in 2.5.2
        # 2.5.1 20/12/21   [dayfirst=1, yearfirst=1] -> 2020-12-21 00:00:00
        # 2.5.2 20/12/21   [dayfirst=1, yearfirst=1] -> month must be in 1..12
        # 2.5.3 20/12/21   [dayfirst=1, yearfirst=1] -> 2020-12-21 00:00:00

        # OK
        # 2.5.1 20/12/21   [dayfirst=1, yearfirst=0] -> 2021-12-20 00:00:00
        # 2.5.2 20/12/21   [dayfirst=1, yearfirst=0] -> 2021-12-20 00:00:00
        # 2.5.3 20/12/21   [dayfirst=1, yearfirst=0] -> 2021-12-20 00:00:00

        import dateutil
        is_lt_253 = dateutil.__version__ < LooseVersion('2.5.3')

        # str : dayfirst, yearfirst, expected
        cases = {'10-11-12': [(False, False,
                               datetime.datetime(2012, 10, 11)),
                              (True, False,
                               datetime.datetime(2012, 11, 10)),
                              (False, True,
                               datetime.datetime(2010, 11, 12)),
                              (True, True,
                               datetime.datetime(2010, 12, 11))],
                 '20/12/21': [(False, False,
                               datetime.datetime(2021, 12, 20)),
                              (True, False,
                               datetime.datetime(2021, 12, 20)),
                              (False, True,
                               datetime.datetime(2020, 12, 21)),
                              (True, True,
                               datetime.datetime(2020, 12, 21))]}

        from dateutil.parser import parse
        for date_str, values in compat.iteritems(cases):
            for dayfirst, yearfirst, expected in values:

                # odd comparisons across version
                # let's just skip
                if dayfirst and yearfirst and is_lt_253:
                    continue

                # compare with dateutil result
                dateutil_result = parse(date_str, dayfirst=dayfirst,
                                        yearfirst=yearfirst)
                self.assertEqual(dateutil_result, expected)

                result1, _, _ = tools.parse_time_string(date_str,
                                                        dayfirst=dayfirst,
                                                        yearfirst=yearfirst)

                # we don't support dayfirst/yearfirst here:
                if not dayfirst and not yearfirst:
                    result2 = Timestamp(date_str)
                    self.assertEqual(result2, expected)

                result3 = to_datetime(date_str, dayfirst=dayfirst,
                                      yearfirst=yearfirst)

                result4 = DatetimeIndex([date_str], dayfirst=dayfirst,
                                        yearfirst=yearfirst)[0]

                self.assertEqual(result1, expected)
                self.assertEqual(result3, expected)
                self.assertEqual(result4, expected)

    def test_parsers_timestring(self):
        tm._skip_if_no_dateutil()
        from dateutil.parser import parse

        # must be the same as dateutil result
        cases = {'10:15': (parse('10:15'), datetime.datetime(1, 1, 1, 10, 15)),
                 '9:05': (parse('9:05'), datetime.datetime(1, 1, 1, 9, 5))}

        for date_str, (exp_now, exp_def) in compat.iteritems(cases):
            result1, _, _ = tools.parse_time_string(date_str)
            result2 = to_datetime(date_str)
            result3 = to_datetime([date_str])
            result4 = Timestamp(date_str)
            result5 = DatetimeIndex([date_str])[0]
            # parse time string return time string based on default date
            # others are not, and can't be changed because it is used in
            # time series plot
            self.assertEqual(result1, exp_def)
            self.assertEqual(result2, exp_now)
            self.assertEqual(result3, exp_now)
            self.assertEqual(result4, exp_now)
            self.assertEqual(result5, exp_now)

    def test_parsers_time(self):
        # GH11818
        _skip_if_has_locale()
        strings = ["14:15", "1415", "2:15pm", "0215pm", "14:15:00", "141500",
                   "2:15:00pm", "021500pm", datetime.time(14, 15)]
        expected = datetime.time(14, 15)

        for time_string in strings:
            self.assertEqual(tools.to_time(time_string), expected)

        new_string = "14.15"
        self.assertRaises(ValueError, tools.to_time, new_string)
        self.assertEqual(tools.to_time(new_string, format="%H.%M"), expected)

        arg = ["14:15", "20:20"]
        expected_arr = [datetime.time(14, 15), datetime.time(20, 20)]
        self.assertEqual(tools.to_time(arg), expected_arr)
        self.assertEqual(tools.to_time(arg, format="%H:%M"), expected_arr)
        self.assertEqual(tools.to_time(arg, infer_time_format=True),
                         expected_arr)
        self.assertEqual(tools.to_time(arg, format="%I:%M%p", errors="coerce"),
                         [None, None])

        res = tools.to_time(arg, format="%I:%M%p", errors="ignore")
        self.assert_numpy_array_equal(res, np.array(arg, dtype=np.object_))

        with tm.assertRaises(ValueError):
            tools.to_time(arg, format="%I:%M%p", errors="raise")

        self.assert_series_equal(tools.to_time(Series(arg, name="test")),
                                 Series(expected_arr, name="test"))

        res = tools.to_time(np.array(arg))
        self.assertIsInstance(res, list)
        self.assert_equal(res, expected_arr)

    def test_parsers_monthfreq(self):
        cases = {'201101': datetime.datetime(2011, 1, 1, 0, 0),
                 '200005': datetime.datetime(2000, 5, 1, 0, 0)}

        for date_str, expected in compat.iteritems(cases):
            result1, _, _ = tools.parse_time_string(date_str, freq='M')
            self.assertEqual(result1, expected)

    def test_parsers_quarterly_with_freq(self):
        msg = ('Incorrect quarterly string is given, quarter '
               'must be between 1 and 4: 2013Q5')
        with tm.assertRaisesRegexp(tslib.DateParseError, msg):
            tools.parse_time_string('2013Q5')

        # GH 5418
        msg = ('Unable to retrieve month information from given freq: '
               'INVLD-L-DEC-SAT')
        with tm.assertRaisesRegexp(tslib.DateParseError, msg):
            tools.parse_time_string('2013Q1', freq='INVLD-L-DEC-SAT')

        cases = {('2013Q2', None): datetime.datetime(2013, 4, 1),
                 ('2013Q2', 'A-APR'): datetime.datetime(2012, 8, 1),
                 ('2013-Q2', 'A-DEC'): datetime.datetime(2013, 4, 1)}

        for (date_str, freq), exp in compat.iteritems(cases):
            result, _, _ = tools.parse_time_string(date_str, freq=freq)
            self.assertEqual(result, exp)

    def test_parsers_timezone_minute_offsets_roundtrip(self):
        # GH11708
        base = to_datetime("2013-01-01 00:00:00")
        dt_strings = [
            ('2013-01-01 05:45+0545',
             "Asia/Katmandu",
             "Timestamp('2013-01-01 05:45:00+0545', tz='Asia/Katmandu')"),
            ('2013-01-01 05:30+0530',
             "Asia/Kolkata",
             "Timestamp('2013-01-01 05:30:00+0530', tz='Asia/Kolkata')")
        ]

        for dt_string, tz, dt_string_repr in dt_strings:
            dt_time = to_datetime(dt_string)
            self.assertEqual(base, dt_time)
            converted_time = dt_time.tz_localize('UTC').tz_convert(tz)
            self.assertEqual(dt_string_repr, repr(converted_time))

    def test_parsers_iso8601(self):
        # GH 12060
        # test only the iso parser - flexibility to different
        # separators and leadings 0s
        # Timestamp construction falls back to dateutil
        cases = {'2011-01-02': datetime.datetime(2011, 1, 2),
                 '2011-1-2': datetime.datetime(2011, 1, 2),
                 '2011-01': datetime.datetime(2011, 1, 1),
                 '2011-1': datetime.datetime(2011, 1, 1),
                 '2011 01 02': datetime.datetime(2011, 1, 2),
                 '2011.01.02': datetime.datetime(2011, 1, 2),
                 '2011/01/02': datetime.datetime(2011, 1, 2),
                 '2011\\01\\02': datetime.datetime(2011, 1, 2),
                 '2013-01-01 05:30:00': datetime.datetime(2013, 1, 1, 5, 30),
                 '2013-1-1 5:30:00': datetime.datetime(2013, 1, 1, 5, 30)}
        for date_str, exp in compat.iteritems(cases):
            actual = tslib._test_parse_iso8601(date_str)
            self.assertEqual(actual, exp)

        # seperators must all match - YYYYMM not valid
        invalid_cases = ['2011-01/02', '2011^11^11',
                         '201401', '201111', '200101',
                         # mixed separated and unseparated
                         '2005-0101', '200501-01',
                         '20010101 12:3456', '20010101 1234:56',
                         # HHMMSS must have two digits in each component
                         # if unseparated
                         '20010101 1', '20010101 123', '20010101 12345',
                         '20010101 12345Z',
                         # wrong separator for HHMMSS
                         '2001-01-01 12-34-56']
        for date_str in invalid_cases:
            with tm.assertRaises(ValueError):
                tslib._test_parse_iso8601(date_str)
                # If no ValueError raised, let me know which case failed.
                raise Exception(date_str)


class TestArrayToDatetime(tm.TestCase):
    def test_parsing_valid_dates(self):
        arr = np.array(['01-01-2013', '01-02-2013'], dtype=object)
        self.assert_numpy_array_equal(
            tslib.array_to_datetime(arr),
            np_array_datetime64_compat(
                [
                    '2013-01-01T00:00:00.000000000-0000',
                    '2013-01-02T00:00:00.000000000-0000'
                ],
                dtype='M8[ns]'
            )
        )

        arr = np.array(['Mon Sep 16 2013', 'Tue Sep 17 2013'], dtype=object)
        self.assert_numpy_array_equal(
            tslib.array_to_datetime(arr),
            np_array_datetime64_compat(
                [
                    '2013-09-16T00:00:00.000000000-0000',
                    '2013-09-17T00:00:00.000000000-0000'
                ],
                dtype='M8[ns]'
            )
        )

    def test_number_looking_strings_not_into_datetime(self):
        # #4601
        # These strings don't look like datetimes so they shouldn't be
        # attempted to be converted
        arr = np.array(['-352.737091', '183.575577'], dtype=object)
        self.assert_numpy_array_equal(
            tslib.array_to_datetime(arr, errors='ignore'), arr)

        arr = np.array(['1', '2', '3', '4', '5'], dtype=object)
        self.assert_numpy_array_equal(
            tslib.array_to_datetime(arr, errors='ignore'), arr)

    def test_coercing_dates_outside_of_datetime64_ns_bounds(self):
        invalid_dates = [
            datetime.date(1000, 1, 1),
            datetime.datetime(1000, 1, 1),
            '1000-01-01',
            'Jan 1, 1000',
            np.datetime64('1000-01-01'),
        ]

        for invalid_date in invalid_dates:
            self.assertRaises(ValueError,
                              tslib.array_to_datetime,
                              np.array(
                                  [invalid_date], dtype='object'),
                              errors='raise', )
            self.assert_numpy_array_equal(
                tslib.array_to_datetime(
                    np.array([invalid_date], dtype='object'),
                    errors='coerce'),
                np.array([tslib.iNaT], dtype='M8[ns]')
            )

        arr = np.array(['1/1/1000', '1/1/2000'], dtype=object)
        self.assert_numpy_array_equal(
            tslib.array_to_datetime(arr, errors='coerce'),
            np_array_datetime64_compat(
                [
                    tslib.iNaT,
                    '2000-01-01T00:00:00.000000000-0000'
                ],
                dtype='M8[ns]'
            )
        )

    def test_coerce_of_invalid_datetimes(self):
        arr = np.array(['01-01-2013', 'not_a_date', '1'], dtype=object)

        # Without coercing, the presence of any invalid dates prevents
        # any values from being converted
        self.assert_numpy_array_equal(
            tslib.array_to_datetime(arr, errors='ignore'), arr)

        # With coercing, the invalid dates becomes iNaT
        self.assert_numpy_array_equal(
            tslib.array_to_datetime(arr, errors='coerce'),
            np_array_datetime64_compat(
                [
                    '2013-01-01T00:00:00.000000000-0000',
                    tslib.iNaT,
                    tslib.iNaT
                ],
                dtype='M8[ns]'
            )
        )

    def test_parsing_timezone_offsets(self):
        # All of these datetime strings with offsets are equivalent
        # to the same datetime after the timezone offset is added
        dt_strings = [
            '01-01-2013 08:00:00+08:00',
            '2013-01-01T08:00:00.000000000+0800',
            '2012-12-31T16:00:00.000000000-0800',
            '12-31-2012 23:00:00-01:00'
        ]

        expected_output = tslib.array_to_datetime(np.array(
            ['01-01-2013 00:00:00'], dtype=object))

        for dt_string in dt_strings:
            self.assert_numpy_array_equal(
                tslib.array_to_datetime(
                    np.array([dt_string], dtype=object)
                ),
                expected_output
            )


class TestTslib(tm.TestCase):
    def test_intraday_conversion_factors(self):
        self.assertEqual(period_asfreq(
            1, get_freq('D'), get_freq('H'), False), 24)
        self.assertEqual(period_asfreq(
            1, get_freq('D'), get_freq('T'), False), 1440)
        self.assertEqual(period_asfreq(
            1, get_freq('D'), get_freq('S'), False), 86400)
        self.assertEqual(period_asfreq(1, get_freq(
            'D'), get_freq('L'), False), 86400000)
        self.assertEqual(period_asfreq(1, get_freq(
            'D'), get_freq('U'), False), 86400000000)
        self.assertEqual(period_asfreq(1, get_freq(
            'D'), get_freq('N'), False), 86400000000000)

        self.assertEqual(period_asfreq(
            1, get_freq('H'), get_freq('T'), False), 60)
        self.assertEqual(period_asfreq(
            1, get_freq('H'), get_freq('S'), False), 3600)
        self.assertEqual(period_asfreq(1, get_freq('H'),
                                       get_freq('L'), False), 3600000)
        self.assertEqual(period_asfreq(1, get_freq(
            'H'), get_freq('U'), False), 3600000000)
        self.assertEqual(period_asfreq(1, get_freq(
            'H'), get_freq('N'), False), 3600000000000)

        self.assertEqual(period_asfreq(
            1, get_freq('T'), get_freq('S'), False), 60)
        self.assertEqual(period_asfreq(
            1, get_freq('T'), get_freq('L'), False), 60000)
        self.assertEqual(period_asfreq(1, get_freq(
            'T'), get_freq('U'), False), 60000000)
        self.assertEqual(period_asfreq(1, get_freq(
            'T'), get_freq('N'), False), 60000000000)

        self.assertEqual(period_asfreq(
            1, get_freq('S'), get_freq('L'), False), 1000)
        self.assertEqual(period_asfreq(1, get_freq('S'),
                                       get_freq('U'), False), 1000000)
        self.assertEqual(period_asfreq(1, get_freq(
            'S'), get_freq('N'), False), 1000000000)

        self.assertEqual(period_asfreq(
            1, get_freq('L'), get_freq('U'), False), 1000)
        self.assertEqual(period_asfreq(1, get_freq('L'),
                                       get_freq('N'), False), 1000000)

        self.assertEqual(period_asfreq(
            1, get_freq('U'), get_freq('N'), False), 1000)

    def test_period_ordinal_start_values(self):
        # information for 1.1.1970
        self.assertEqual(0, period_ordinal(1970, 1, 1, 0, 0, 0, 0, 0,
                                           get_freq('A')))
        self.assertEqual(0, period_ordinal(1970, 1, 1, 0, 0, 0, 0, 0,
                                           get_freq('M')))
        self.assertEqual(1, period_ordinal(1970, 1, 1, 0, 0, 0, 0, 0,
                                           get_freq('W')))
        self.assertEqual(0, period_ordinal(1970, 1, 1, 0, 0, 0, 0, 0,
                                           get_freq('D')))
        self.assertEqual(0, period_ordinal(1970, 1, 1, 0, 0, 0, 0, 0,
                                           get_freq('B')))

    def test_period_ordinal_week(self):
        self.assertEqual(1, period_ordinal(1970, 1, 4, 0, 0, 0, 0, 0,
                                           get_freq('W')))
        self.assertEqual(2, period_ordinal(1970, 1, 5, 0, 0, 0, 0, 0,
                                           get_freq('W')))

        self.assertEqual(2284, period_ordinal(2013, 10, 6, 0, 0, 0, 0, 0,
                                              get_freq('W')))
        self.assertEqual(2285, period_ordinal(2013, 10, 7, 0, 0, 0, 0, 0,
                                              get_freq('W')))

    def test_period_ordinal_business_day(self):
        # Thursday
        self.assertEqual(11415, period_ordinal(2013, 10, 3, 0, 0, 0, 0, 0,
                                               get_freq('B')))
        # Friday
        self.assertEqual(11416, period_ordinal(2013, 10, 4, 0, 0, 0, 0, 0,
                                               get_freq('B')))
        # Saturday
        self.assertEqual(11417, period_ordinal(2013, 10, 5, 0, 0, 0, 0, 0,
                                               get_freq('B')))
        # Sunday
        self.assertEqual(11417, period_ordinal(2013, 10, 6, 0, 0, 0, 0, 0,
                                               get_freq('B')))
        # Monday
        self.assertEqual(11417, period_ordinal(2013, 10, 7, 0, 0, 0, 0, 0,
                                               get_freq('B')))
        # Tuesday
        self.assertEqual(11418, period_ordinal(2013, 10, 8, 0, 0, 0, 0, 0,
                                               get_freq('B')))

    def test_tslib_tz_convert(self):
        def compare_utc_to_local(tz_didx, utc_didx):
            f = lambda x: tslib.tz_convert_single(x, 'UTC', tz_didx.tz)
            result = tslib.tz_convert(tz_didx.asi8, 'UTC', tz_didx.tz)
            result_single = np.vectorize(f)(tz_didx.asi8)
            self.assert_numpy_array_equal(result, result_single)

        def compare_local_to_utc(tz_didx, utc_didx):
            f = lambda x: tslib.tz_convert_single(x, tz_didx.tz, 'UTC')
            result = tslib.tz_convert(utc_didx.asi8, tz_didx.tz, 'UTC')
            result_single = np.vectorize(f)(utc_didx.asi8)
            self.assert_numpy_array_equal(result, result_single)

        for tz in ['UTC', 'Asia/Tokyo', 'US/Eastern', 'Europe/Moscow']:
            # US: 2014-03-09 - 2014-11-11
            # MOSCOW: 2014-10-26  /  2014-12-31
            tz_didx = date_range('2014-03-01', '2015-01-10', freq='H', tz=tz)
            utc_didx = date_range('2014-03-01', '2015-01-10', freq='H')
            compare_utc_to_local(tz_didx, utc_didx)
            # local tz to UTC can be differ in hourly (or higher) freqs because
            # of DST
            compare_local_to_utc(tz_didx, utc_didx)

            tz_didx = date_range('2000-01-01', '2020-01-01', freq='D', tz=tz)
            utc_didx = date_range('2000-01-01', '2020-01-01', freq='D')
            compare_utc_to_local(tz_didx, utc_didx)
            compare_local_to_utc(tz_didx, utc_didx)

            tz_didx = date_range('2000-01-01', '2100-01-01', freq='A', tz=tz)
            utc_didx = date_range('2000-01-01', '2100-01-01', freq='A')
            compare_utc_to_local(tz_didx, utc_didx)
            compare_local_to_utc(tz_didx, utc_didx)

        # Check empty array
        result = tslib.tz_convert(np.array([], dtype=np.int64),
                                  tslib.maybe_get_tz('US/Eastern'),
                                  tslib.maybe_get_tz('Asia/Tokyo'))
        self.assert_numpy_array_equal(result, np.array([], dtype=np.int64))

        # Check all-NaT array
        result = tslib.tz_convert(np.array([tslib.iNaT], dtype=np.int64),
                                  tslib.maybe_get_tz('US/Eastern'),
                                  tslib.maybe_get_tz('Asia/Tokyo'))
        self.assert_numpy_array_equal(result, np.array(
            [tslib.iNaT], dtype=np.int64))

    def test_shift_months(self):
        s = DatetimeIndex([Timestamp('2000-01-05 00:15:00'), Timestamp(
            '2000-01-31 00:23:00'), Timestamp('2000-01-01'), Timestamp(
                '2000-02-29'), Timestamp('2000-12-31')])
        for years in [-1, 0, 1]:
            for months in [-2, 0, 2]:
                actual = DatetimeIndex(tslib.shift_months(s.asi8, years * 12 +
                                                          months))
                expected = DatetimeIndex([x + offsets.DateOffset(
                    years=years, months=months) for x in s])
                tm.assert_index_equal(actual, expected)

    def test_round(self):
        stamp = Timestamp('2000-01-05 05:09:15.13')

        def _check_round(freq, expected):
            result = stamp.round(freq=freq)
            self.assertEqual(result, expected)

        for freq, expected in [('D', Timestamp('2000-01-05 00:00:00')),
                               ('H', Timestamp('2000-01-05 05:00:00')),
                               ('S', Timestamp('2000-01-05 05:09:15'))]:
            _check_round(freq, expected)

        msg = pd.tseries.frequencies._INVALID_FREQ_ERROR
        with self.assertRaisesRegexp(ValueError, msg):
            stamp.round('foo')


if __name__ == '__main__':
    nose.runmodule(argv=[__file__, '-vvs', '-x', '--pdb', '--pdb-failure'],
                   exit=False)
