import os
from datetime import datetime, timedelta, date, time

import unittest
import nose

import numpy as np
from numpy.testing.decorators import slow
from numpy.testing import assert_array_equal

from pandas import Index, Series, DataFrame, isnull, notnull

from pandas.tseries.index import date_range, bdate_range
from pandas.tseries.offsets import Minute, DateOffset
from pandas.tseries.period import period_range, Period
from pandas.tseries.resample import DatetimeIndex, TimeGrouper
import pandas.tseries.offsets as offsets
import pandas.tseries.frequencies as frequencies
import pandas.tseries.converter as conv

from pandas.util.testing import assert_series_equal, assert_almost_equal
import pandas.util.testing as tm

class TestTSPlot(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import sys
        if 'IPython' in sys.modules:
            raise nose.SkipTest

        try:
            import matplotlib as mpl
            mpl.use('Agg', warn=False)
        except ImportError:
            raise nose.SkipTest

    def setUp(self):
        freq = ['S', 'T', 'H', 'D', 'W', 'M', 'Q', 'Y']
        idx = [period_range('12/31/1999', freq=x, periods=100) for x in freq]
        self.period_ser = [Series(np.random.randn(len(x)), x) for x in idx]
        self.period_df = [DataFrame(np.random.randn(len(x), 3), index=x,
                                    columns=['A', 'B', 'C'])
                                    for x in idx]

        freq = ['S', 'T', 'H', 'D', 'W', 'M', 'Q-DEC', 'A', '1B30Min']
        idx = [date_range('12/31/1999', freq=x, periods=100) for x in freq]
        self.datetime_ser = [Series(np.random.randn(len(x)), x) for x in idx]
        self.datetime_df = [DataFrame(np.random.randn(len(x), 3), index=x,
                                    columns=['A', 'B', 'C'])
                                    for x in idx]

    @slow
    def test_frame_inferred(self):
        # inferred freq
        import matplotlib.pyplot as plt
        plt.close('all')
        idx = date_range('1/1/1987', freq='MS', periods=100)
        idx = DatetimeIndex(idx.values, freq=None)
        df = DataFrame(np.random.randn(len(idx), 3), index=idx)
        df.plot()

        # axes freq
        idx = idx[0:40] + idx[45:99]
        df2 = DataFrame(np.random.randn(len(idx), 3), index=idx)
        df2.plot()
        plt.close('all')

    @slow
    def test_tsplot(self):
        from pandas.tseries.plotting import tsplot
        import matplotlib.pyplot as plt
        plt.close('all')

        ax = plt.gca()
        ts = tm.makeTimeSeries()
        plot_ax = tsplot(ts, plt.Axes.plot)
        self.assert_(plot_ax == ax)

        f = lambda *args, **kwds: tsplot(s, plt.Axes.plot, *args, **kwds)
        plt.close('all')

        for s in self.period_ser:
            _check_plot_works(f, s.index.freq, ax=ax, series=s)
            plt.close('all')
        for s in self.datetime_ser:
            _check_plot_works(f, s.index.freq.rule_code, ax=ax, series=s)
            plt.close('all')

        plt.close('all')
        ax = ts.plot(style='k')
        self.assert_((0., 0., 0.) == ax.get_lines()[0].get_color())

    @slow
    def test_high_freq(self):
        freaks = ['ms', 'us']
        for freq in freaks:
            rng = date_range('1/1/2012', periods=100000, freq=freq)
            ser = Series(np.random.randn(len(rng)), rng)
            _check_plot_works(ser.plot)

    def test_get_datevalue(self):
        from pandas.tseries.plotting import get_datevalue
        self.assert_(get_datevalue(None, 'D') is None)
        self.assert_(get_datevalue(1987, 'A') == 1987)
        self.assert_(get_datevalue(Period(1987, 'A'), 'M') ==
                     Period('1987-12', 'M').ordinal)
        self.assert_(get_datevalue('1/1/1987', 'D') ==
                     Period('1987-1-1', 'D').ordinal)

    @slow
    def test_line_plot_period_series(self):
        for s in self.period_ser:
            _check_plot_works(s.plot, s.index.freq)

    @slow
    def test_line_plot_datetime_series(self):
        for s in self.datetime_ser:
            _check_plot_works(s.plot, s.index.freq.rule_code)

    @slow
    def test_line_plot_period_frame(self):
        for df in self.period_df:
            _check_plot_works(df.plot, df.index.freq)

    @slow
    def test_line_plot_datetime_frame(self):
        for df in self.datetime_df:
            freq = df.index.to_period(df.index.freq.rule_code).freq
            _check_plot_works(df.plot, freq)

    @slow
    def test_line_plot_inferred_freq(self):
        for ser in self.datetime_ser:
            ser = Series(ser.values, Index(np.asarray(ser.index)))
            _check_plot_works(ser.plot, ser.index.inferred_freq)

            ser = ser[[0, 3, 5, 6]]
            _check_plot_works(ser.plot)

    @slow
    def test_plot_offset_freq(self):
        ser = tm.makeTimeSeries()
        _check_plot_works(ser.plot)

        dr = date_range(ser.index[0], freq='BQS', periods=10)
        ser = Series(np.random.randn(len(dr)), dr)
        _check_plot_works(ser.plot)

    @slow
    def test_plot_multiple_inferred_freq(self):
        dr = Index([datetime(2000, 1, 1),
                    datetime(2000, 1, 6),
                    datetime(2000, 1, 11)])
        ser = Series(np.random.randn(len(dr)), dr)
        _check_plot_works(ser.plot)

    @slow
    def test_uhf(self):
        import matplotlib.pyplot as plt
        fig = plt.gcf()
        plt.clf()
        fig.add_subplot(111)

        idx = date_range('2012-6-22 21:59:51.960928', freq='L', periods=500)
        df = DataFrame(np.random.randn(len(idx), 2), idx)

        ax = df.plot()
        axis = ax.get_xaxis()

        tlocs = axis.get_ticklocs()
        tlabels = axis.get_ticklabels()
        for loc, label in zip(tlocs, tlabels):
            xp = conv._from_ordinal(loc).strftime('%H:%M:%S.%f')
            rs = str(label.get_text())
            if len(rs) != 0:
                self.assert_(xp == rs)

    @slow
    def test_irreg_hf(self):
        import matplotlib.pyplot as plt
        fig = plt.gcf()
        plt.clf()
        fig.add_subplot(111)

        idx = date_range('2012-6-22 21:59:51', freq='S', periods=100)
        df = DataFrame(np.random.randn(len(idx), 2), idx)

        irreg = df.ix[[0, 1, 3, 4]]
        ax = irreg.plot()
        diffs = Series(ax.get_lines()[0].get_xydata()[:, 0]).diff()

        sec = 1. / 24 / 60 / 60
        self.assert_((np.fabs(diffs[1:] - [sec, sec*2, sec]) < 1e-8).all())

        plt.clf()
        fig.add_subplot(111)
        df2 = df.copy()
        df2.index = df.index.asobject
        ax = df2.plot()
        diffs = Series(ax.get_lines()[0].get_xydata()[:, 0]).diff()
        self.assert_((np.fabs(diffs[1:] - sec) < 1e-8).all())

    @slow
    def test_irregular_datetime64_repr_bug(self):
        import matplotlib.pyplot as plt
        ser = tm.makeTimeSeries()
        ser = ser[[0,1,2,7]]

        fig = plt.gcf()
        plt.clf()
        ax = fig.add_subplot(211)
        ret = ser.plot()
        assert(ret is not None)

        for rs, xp in zip(ax.get_lines()[0].get_xdata(), ser.index):
            assert(rs == xp)

    @slow
    def test_business_freq(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        bts = tm.makePeriodSeries()
        ax = bts.plot()
        self.assert_(ax.get_lines()[0].get_xydata()[0, 0],
                     bts.index[0].ordinal)
        idx = ax.get_lines()[0].get_xdata()
        self.assert_(idx.freqstr == 'B')

    @slow
    def test_business_freq_convert(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        n = tm.N
        tm.N = 300
        bts = tm.makeTimeSeries().asfreq('BM')
        tm.N = n
        ts = bts.to_period('M')
        ax = bts.plot()
        self.assert_(ax.get_lines()[0].get_xydata()[0, 0], ts.index[0].ordinal)
        idx = ax.get_lines()[0].get_xdata()
        self.assert_(idx.freqstr == 'M')

    @slow
    def test_dataframe(self):
        bts = DataFrame({'a': tm.makeTimeSeries()})
        ax = bts.plot()
        idx = ax.get_lines()[0].get_xdata()

    @slow
    def test_axis_limits(self):
        def _test(ax):
            xlim = ax.get_xlim()
            ax.set_xlim(xlim[0] - 5, xlim[1] + 10)
            ax.get_figure().canvas.draw()
            result = ax.get_xlim()
            self.assertEqual(result[0], xlim[0] - 5)
            self.assertEqual(result[1], xlim[1] + 10)

            # string
            expected = (Period('1/1/2000', ax.freq),
                        Period('4/1/2000', ax.freq))
            ax.set_xlim('1/1/2000', '4/1/2000')
            ax.get_figure().canvas.draw()
            result = ax.get_xlim()
            self.assertEqual(int(result[0]), expected[0].ordinal)
            self.assertEqual(int(result[1]), expected[1].ordinal)

            # datetim
            expected = (Period('1/1/2000', ax.freq),
                        Period('4/1/2000', ax.freq))
            ax.set_xlim(datetime(2000, 1, 1), datetime(2000, 4, 1))
            ax.get_figure().canvas.draw()
            result = ax.get_xlim()
            self.assertEqual(int(result[0]), expected[0].ordinal)
            self.assertEqual(int(result[1]), expected[1].ordinal)

        ser = tm.makeTimeSeries()
        ax = ser.plot()
        _test(ax)

        df = DataFrame({'a' : ser, 'b' : ser + 1})
        ax = df.plot()
        _test(ax)

        df = DataFrame({'a' : ser, 'b' : ser + 1})
        axes = df.plot(subplots=True)
        [_test(ax) for ax in axes]

    def test_get_finder(self):
        import pandas.tseries.converter as conv

        self.assertEqual(conv.get_finder('B'), conv._daily_finder)
        self.assertEqual(conv.get_finder('D'), conv._daily_finder)
        self.assertEqual(conv.get_finder('M'), conv._monthly_finder)
        self.assertEqual(conv.get_finder('Q'), conv._quarterly_finder)
        self.assertEqual(conv.get_finder('A'), conv._annual_finder)
        self.assertEqual(conv.get_finder('W'), conv._daily_finder)

    @slow
    def test_finder_daily(self):
        xp = Period('1999-1-1', freq='B').ordinal
        day_lst = [10, 40, 252, 400, 950, 2750, 10000]
        for n in day_lst:
            rng = bdate_range('1999-1-1', periods=n)
            ser = Series(np.random.randn(len(rng)), rng)
            ax = ser.plot()
            xaxis = ax.get_xaxis()
            rs = xaxis.get_majorticklocs()[0]
            self.assertEqual(xp, rs)
            (vmin, vmax) = ax.get_xlim()
            ax.set_xlim(vmin + 0.9, vmax)
            rs = xaxis.get_majorticklocs()[0]
            self.assertEqual(xp, rs)

    @slow
    def test_finder_quarterly(self):
        import matplotlib.pyplot as plt
        xp = Period('1988Q1').ordinal
        yrs = [3.5, 11]
        plt.close('all')
        for n in yrs:
            rng = period_range('1987Q2', periods=int(n * 4), freq='Q')
            ser = Series(np.random.randn(len(rng)), rng)
            ax = ser.plot()
            xaxis = ax.get_xaxis()
            rs = xaxis.get_majorticklocs()[0]
            self.assert_(rs == xp)
            (vmin, vmax) = ax.get_xlim()
            ax.set_xlim(vmin + 0.9, vmax)
            rs = xaxis.get_majorticklocs()[0]
            self.assertEqual(xp, rs)

    @slow
    def test_finder_monthly(self):
        import matplotlib.pyplot as plt
        xp = Period('1988-1').ordinal
        yrs = [1.15, 2.5, 4, 11]
        plt.close('all')
        for n in yrs:
            rng = period_range('1987Q2', periods=int(n * 12), freq='M')
            ser = Series(np.random.randn(len(rng)), rng)
            ax = ser.plot()
            xaxis = ax.get_xaxis()
            rs = xaxis.get_majorticklocs()[0]
            self.assert_(rs == xp)
            (vmin, vmax) = ax.get_xlim()
            ax.set_xlim(vmin + 0.9, vmax)
            rs = xaxis.get_majorticklocs()[0]
            self.assertEqual(xp, rs)
            plt.close('all')

    @slow
    def test_finder_monthly_long(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        rng = period_range('1988Q1', periods=24*12, freq='M')
        ser = Series(np.random.randn(len(rng)), rng)
        ax = ser.plot()
        xaxis = ax.get_xaxis()
        rs = xaxis.get_majorticklocs()[0]
        xp = Period('1989Q1', 'M').ordinal
        self.assert_(rs == xp)

    @slow
    def test_finder_annual(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        xp = [1987, 1988, 1990, 1990, 1995, 2020, 2070, 2170]
        for i, nyears in enumerate([5, 10, 19, 49, 99, 199, 599, 1001]):
            rng = period_range('1987', periods=nyears, freq='A')
            ser = Series(np.random.randn(len(rng)), rng)
            ax = ser.plot()
            xaxis = ax.get_xaxis()
            rs = xaxis.get_majorticklocs()[0]
            self.assert_(rs == Period(xp[i], freq='A').ordinal)
            plt.close('all')

    @slow
    def test_finder_minutely(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        nminutes = 50 * 24 * 60
        rng = date_range('1/1/1999', freq='Min', periods=nminutes)
        ser = Series(np.random.randn(len(rng)), rng)
        ax = ser.plot()
        xaxis = ax.get_xaxis()
        rs = xaxis.get_majorticklocs()[0]
        xp = Period('1/1/1999', freq='Min').ordinal
        self.assertEqual(rs, xp)

    @slow
    def test_finder_hourly(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        nhours = 23
        rng = date_range('1/1/1999', freq='H', periods=nhours)
        ser = Series(np.random.randn(len(rng)), rng)
        ax = ser.plot()
        xaxis = ax.get_xaxis()
        rs = xaxis.get_majorticklocs()[0]
        xp = Period('1/1/1999', freq='H').ordinal
        self.assertEqual(rs, xp)

    @slow
    def test_gaps(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        ts = tm.makeTimeSeries()
        ts[5:25] = np.nan
        ax = ts.plot()
        lines = ax.get_lines()
        self.assert_(len(lines) == 1)
        l = lines[0]
        data = l.get_xydata()
        self.assert_(isinstance(data, np.ma.core.MaskedArray))
        mask = data.mask
        self.assert_(mask[5:25, 1].all())

        # irregular
        plt.close('all')
        ts = tm.makeTimeSeries()
        ts = ts[[0, 1, 2, 5, 7, 9, 12, 15, 20]]
        ts[2:5] = np.nan
        ax = ts.plot()
        lines = ax.get_lines()
        self.assert_(len(lines) == 1)
        l = lines[0]
        data = l.get_xydata()
        self.assert_(isinstance(data, np.ma.core.MaskedArray))
        mask = data.mask
        self.assert_(mask[2:5, 1].all())

        # non-ts
        plt.close('all')
        idx = [0, 1, 2, 5, 7, 9, 12, 15, 20]
        ser = Series(np.random.randn(len(idx)), idx)
        ser[2:5] = np.nan
        ax = ser.plot()
        lines = ax.get_lines()
        self.assert_(len(lines) == 1)
        l = lines[0]
        data = l.get_xydata()
        self.assert_(isinstance(data, np.ma.core.MaskedArray))
        mask = data.mask
        self.assert_(mask[2:5, 1].all())

    @slow
    def test_secondary_y(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        ser = Series(np.random.randn(10))
        ser2 = Series(np.random.randn(10))
        ax = ser.plot(secondary_y=True)
        fig = ax.get_figure()
        axes = fig.get_axes()
        l = ax.get_lines()[0]
        xp = Series(l.get_ydata(), l.get_xdata())
        assert_series_equal(ser, xp)
        self.assert_(ax.get_yaxis().get_ticks_position() == 'right')
        self.assert_(not axes[0].get_yaxis().get_visible())

        ax2 = ser2.plot()
        self.assert_(ax2.get_yaxis().get_ticks_position() == 'left')

        plt.close('all')
        ax = ser2.plot()
        ax2 = ser.plot(secondary_y=True)
        self.assert_(ax.get_yaxis().get_visible())

        plt.close('all')

    @slow
    def test_secondary_y_ts(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        idx = date_range('1/1/2000', periods=10)
        ser = Series(np.random.randn(10), idx)
        ser2 = Series(np.random.randn(10), idx)
        ax = ser.plot(secondary_y=True)
        fig = ax.get_figure()
        axes = fig.get_axes()
        l = ax.get_lines()[0]
        xp = Series(l.get_ydata(), l.get_xdata()).to_timestamp()
        assert_series_equal(ser, xp)
        self.assert_(ax.get_yaxis().get_ticks_position() == 'right')
        self.assert_(not axes[0].get_yaxis().get_visible())

        ax2 = ser2.plot()
        self.assert_(ax2.get_yaxis().get_ticks_position() == 'left')

        plt.close('all')
        ax = ser2.plot()
        ax2 = ser.plot(secondary_y=True)
        self.assert_(ax.get_yaxis().get_visible())

    @slow
    def test_secondary_kde(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        ser = Series(np.random.randn(10))
        ax = ser.plot(secondary_y=True, kind='density')
        fig = ax.get_figure()
        axes = fig.get_axes()
        self.assert_(axes[1].get_yaxis().get_ticks_position() == 'right')

    @slow
    def test_secondary_bar(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        ser = Series(np.random.randn(10))
        ax = ser.plot(secondary_y=True, kind='bar')
        fig = ax.get_figure()
        axes = fig.get_axes()
        self.assert_(axes[1].get_yaxis().get_ticks_position() == 'right')

    @slow
    def test_secondary_frame(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        df = DataFrame(np.random.randn(5, 3), columns=['a', 'b', 'c'])
        axes = df.plot(secondary_y=['a', 'c'], subplots=True)
        self.assert_(axes[0].get_yaxis().get_ticks_position() == 'right')
        self.assert_(axes[1].get_yaxis().get_ticks_position() == 'default')
        self.assert_(axes[2].get_yaxis().get_ticks_position() == 'right')

    @slow
    def test_mixed_freq_regular_first(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        s1 = tm.makeTimeSeries()
        s2 = s1[[0, 5, 10, 11, 12, 13, 14, 15]]
        s1.plot()
        ax2 = s2.plot(style='g')
        lines = ax2.get_lines()
        idx1 = lines[0].get_xdata()
        idx2 = lines[1].get_xdata()
        self.assert_(idx1.equals(s1.index.to_period('B')))
        self.assert_(idx2.equals(s2.index.to_period('B')))
        left, right = ax2.get_xlim()
        pidx = s1.index.to_period()
        self.assert_(left == pidx[0].ordinal)
        self.assert_(right == pidx[-1].ordinal)
        plt.close('all')

    @slow
    def test_mixed_freq_irregular_first(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        s1 = tm.makeTimeSeries()
        s2 = s1[[0, 5, 10, 11, 12, 13, 14, 15]]
        s2.plot(style='g')
        ax = s1.plot()
        self.assert_(not hasattr(ax, 'freq'))
        lines = ax.get_lines()
        x1 = lines[0].get_xdata()
        assert_array_equal(x1, s2.index.asobject.values)
        x2 = lines[1].get_xdata()
        assert_array_equal(x2, s1.index.asobject.values)
        plt.close('all')

    @slow
    def test_mixed_freq_hf_first(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        idxh = date_range('1/1/1999', periods=365, freq='D')
        idxl = date_range('1/1/1999', periods=12, freq='M')
        high = Series(np.random.randn(len(idxh)), idxh)
        low = Series(np.random.randn(len(idxl)), idxl)
        high.plot()
        ax = low.plot()
        for l in ax.get_lines():
            self.assert_(l.get_xdata().freq == 'D')

    @slow
    def test_mixed_freq_lf_first(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        idxh = date_range('1/1/1999', periods=365, freq='D')
        idxl = date_range('1/1/1999', periods=12, freq='M')
        high = Series(np.random.randn(len(idxh)), idxh)
        low = Series(np.random.randn(len(idxl)), idxl)
        low.plot()
        ax = high.plot()
        for l in ax.get_lines():
            self.assert_(l.get_xdata().freq == 'M')

    @slow
    def test_mixed_freq_irreg_period(self):
        ts = tm.makeTimeSeries()
        irreg = ts[[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 15, 16, 17, 18, 29]]
        rng = period_range('1/3/2000', periods=30, freq='B')
        ps = Series(np.random.randn(len(rng)), rng)
        irreg.plot()
        ps.plot()

    @slow
    def test_to_weekly_resampling(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        idxh = date_range('1/1/1999', periods=52, freq='W')
        idxl = date_range('1/1/1999', periods=12, freq='M')
        high = Series(np.random.randn(len(idxh)), idxh)
        low = Series(np.random.randn(len(idxl)), idxl)
        high.plot()
        ax = low.plot()
        for l in ax.get_lines():
            self.assert_(l.get_xdata().freq.startswith('W'))

    @slow
    def test_from_weekly_resampling(self):
        import matplotlib.pyplot as plt
        plt.close('all')
        idxh = date_range('1/1/1999', periods=52, freq='W')
        idxl = date_range('1/1/1999', periods=12, freq='M')
        high = Series(np.random.randn(len(idxh)), idxh)
        low = Series(np.random.randn(len(idxl)), idxl)
        low.plot()
        ax = high.plot()
        for l in ax.get_lines():
            self.assert_(l.get_xdata().freq == 'M')

    @slow
    def test_irreg_dtypes(self):
        import matplotlib.pyplot as plt
        #date
        idx = [date(2000, 1, 1), date(2000, 1, 5), date(2000, 1, 20)]
        df = DataFrame(np.random.randn(len(idx), 3), Index(idx, dtype=object))
        _check_plot_works(df.plot)

        #np.datetime64
        idx = date_range('1/1/2000', periods=10)
        idx = idx[[0, 2, 5, 9]].asobject
        df = DataFrame(np.random.randn(len(idx), 3), idx)
        _check_plot_works(df.plot)

    @slow
    def test_time(self):
        import matplotlib.pyplot as plt
        plt.close('all')

        t = datetime(1, 1, 1, 3, 30, 0)
        deltas = np.random.randint(1, 20, 3).cumsum()
        ts = np.array([(t + timedelta(minutes=int(x))).time() for x in deltas])
        df = DataFrame({'a' : np.random.randn(len(ts)),
                        'b' : np.random.randn(len(ts))},
                       index=ts)
        ax = df.plot()

        # verify tick labels
        ticks = ax.get_xticks()
        labels = ax.get_xticklabels()
        for t, l in zip(ticks, labels):
            m, s = divmod(int(t), 60)
            h, m = divmod(m, 60)
            xp = l.get_text()
            if len(xp) > 0:
                rs = time(h, m, s).strftime('%H:%M:%S')
                self.assert_(xp, rs)

        # change xlim
        ax.set_xlim('1:30', '5:00')

        # check tick labels again
        ticks = ax.get_xticks()
        labels = ax.get_xticklabels()
        for t, l in zip(ticks, labels):
            m, s = divmod(int(t), 60)
            h, m = divmod(m, 60)
            xp = l.get_text()
            if len(xp) > 0:
                rs = time(h, m, s).strftime('%H:%M:%S')
                self.assert_(xp, rs)

    @slow
    def test_time_musec(self):
        import matplotlib.pyplot as plt
        plt.close('all')

        t = datetime(1, 1, 1, 3, 30, 0)
        deltas = np.random.randint(1, 20, 3).cumsum()
        ts = np.array([(t + timedelta(microseconds=int(x))).time()
                       for x in deltas])
        df = DataFrame({'a' : np.random.randn(len(ts)),
                        'b' : np.random.randn(len(ts))},
                       index=ts)
        ax = df.plot()

        # verify tick labels
        ticks = ax.get_xticks()
        labels = ax.get_xticklabels()
        for t, l in zip(ticks, labels):
            m, s = divmod(int(t), 60)
            us = int((t - int(t)) * 1e6)
            h, m = divmod(m, 60)
            xp = l.get_text()
            if len(xp) > 0:
                rs = time(h, m, s).strftime('%H:%M:%S.%f')
                self.assert_(xp, rs)

PNG_PATH = 'tmp.png'
def _check_plot_works(f, freq=None, series=None, *args, **kwargs):
    import matplotlib.pyplot as plt

    fig = plt.gcf()
    plt.clf()
    ax = fig.add_subplot(211)
    orig_ax = kwargs.pop('ax', plt.gca())
    orig_axfreq = getattr(orig_ax, 'freq', None)

    ret = f(*args, **kwargs)
    assert(ret is not None)  # do something more intelligent

    ax = kwargs.pop('ax', plt.gca())
    if series is not None:
        dfreq = series.index.freq
        if isinstance(dfreq, DateOffset):
            dfreq = dfreq.rule_code
        if orig_axfreq is None:
            assert(ax.freq == dfreq)

    if freq is not None and orig_axfreq is None:
        assert(ax.freq == freq)

    ax = fig.add_subplot(212)
    try:
        kwargs['ax'] = ax
        ret = f(*args, **kwargs)
        assert(ret is not None)  # do something more intelligent
    except Exception:
        pass
    plt.savefig(PNG_PATH)
    os.remove(PNG_PATH)

if __name__ == '__main__':
    nose.runmodule(argv=[__file__,'-vvs','-x','--pdb', '--pdb-failure'],
                   exit=False)

