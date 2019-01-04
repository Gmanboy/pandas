#!/usr/bin/env python
# coding: utf-8

import os
import warnings

import numpy as np
from numpy import random
import pytest

from pandas.compat import iteritems, zip
from pandas.util._decorators import cache_readonly
import pandas.util._test_decorators as td

from pandas.core.dtypes.api import is_list_like

from pandas import DataFrame, Series
import pandas.util.testing as tm
from pandas.util.testing import (
    assert_is_valid_plot_return_object, ensure_clean)

import pandas.plotting as plotting
from pandas.plotting._tools import _flatten


"""
This is a common base class used for various plotting tests
"""


def _skip_if_no_scipy_gaussian_kde():
    try:
        from scipy.stats import gaussian_kde  # noqa
    except ImportError:
        pytest.skip("scipy version doesn't support gaussian_kde")


def _ok_for_gaussian_kde(kind):
    if kind in ['kde', 'density']:
        try:
            from scipy.stats import gaussian_kde  # noqa
        except ImportError:
            return False

    return True


@td.skip_if_no_mpl
class TestPlotBase(object):

    def setup_method(self, method):

        import matplotlib as mpl
        mpl.rcdefaults()

        self.mpl_ge_2_0_1 = plotting._compat._mpl_ge_2_0_1()
        self.mpl_ge_2_1_0 = plotting._compat._mpl_ge_2_1_0()
        self.mpl_ge_2_2_0 = plotting._compat._mpl_ge_2_2_0()
        self.mpl_ge_2_2_2 = plotting._compat._mpl_ge_2_2_2()
        self.mpl_ge_3_0_0 = plotting._compat._mpl_ge_3_0_0()

        self.bp_n_objects = 7
        self.polycollection_factor = 2
        self.default_figsize = (6.4, 4.8)
        self.default_tick_position = 'left'

        n = 100
        with tm.RNGContext(42):
            gender = np.random.choice(['Male', 'Female'], size=n)
            classroom = np.random.choice(['A', 'B', 'C'], size=n)

            self.hist_df = DataFrame({'gender': gender,
                                      'classroom': classroom,
                                      'height': random.normal(66, 4, size=n),
                                      'weight': random.normal(161, 32, size=n),
                                      'category': random.randint(4, size=n)})

        self.tdf = tm.makeTimeDataFrame()
        self.hexbin_df = DataFrame({"A": np.random.uniform(size=20),
                                    "B": np.random.uniform(size=20),
                                    "C": np.arange(20) + np.random.uniform(
                                        size=20)})

    def teardown_method(self, method):
        tm.close()

    @cache_readonly
    def plt(self):
        import matplotlib.pyplot as plt
        return plt

    @cache_readonly
    def colorconverter(self):
        import matplotlib.colors as colors
        return colors.colorConverter

    def _check_legend_labels(self, axes, labels=None, visible=True):
        """
        Check each axes has expected legend labels

        Parameters
        ----------
        axes : matplotlib Axes object, or its list-like
        labels : list-like
            expected legend labels
        visible : bool
            expected legend visibility. labels are checked only when visible is
            True
        """

        if visible and (labels is None):
            raise ValueError('labels must be specified when visible is True')
        axes = self._flatten_visible(axes)
        for ax in axes:
            if visible:
                assert ax.get_legend() is not None
                self._check_text_labels(ax.get_legend().get_texts(), labels)
            else:
                assert ax.get_legend() is None

    def _check_data(self, xp, rs):
        """
        Check each axes has identical lines

        Parameters
        ----------
        xp : matplotlib Axes object
        rs : matplotlib Axes object
        """
        xp_lines = xp.get_lines()
        rs_lines = rs.get_lines()

        def check_line(xpl, rsl):
            xpdata = xpl.get_xydata()
            rsdata = rsl.get_xydata()
            tm.assert_almost_equal(xpdata, rsdata)

        assert len(xp_lines) == len(rs_lines)
        [check_line(xpl, rsl) for xpl, rsl in zip(xp_lines, rs_lines)]
        tm.close()

    def _check_visible(self, collections, visible=True):
        """
        Check each artist is visible or not

        Parameters
        ----------
        collections : matplotlib Artist or its list-like
            target Artist or its list or collection
        visible : bool
            expected visibility
        """
        from matplotlib.collections import Collection
        if not isinstance(collections,
                          Collection) and not is_list_like(collections):
            collections = [collections]

        for patch in collections:
            assert patch.get_visible() == visible

    def _get_colors_mapped(self, series, colors):
        unique = series.unique()
        # unique and colors length can be differed
        # depending on slice value
        mapped = dict(zip(unique, colors))
        return [mapped[v] for v in series.values]

    def _check_colors(self, collections, linecolors=None, facecolors=None,
                      mapping=None):
        """
        Check each artist has expected line colors and face colors

        Parameters
        ----------
        collections : list-like
            list or collection of target artist
        linecolors : list-like which has the same length as collections
            list of expected line colors
        facecolors : list-like which has the same length as collections
            list of expected face colors
        mapping : Series
            Series used for color grouping key
            used for andrew_curves, parallel_coordinates, radviz test
        """

        from matplotlib.lines import Line2D
        from matplotlib.collections import (
            Collection, PolyCollection, LineCollection
        )
        conv = self.colorconverter
        if linecolors is not None:

            if mapping is not None:
                linecolors = self._get_colors_mapped(mapping, linecolors)
                linecolors = linecolors[:len(collections)]

            assert len(collections) == len(linecolors)
            for patch, color in zip(collections, linecolors):
                if isinstance(patch, Line2D):
                    result = patch.get_color()
                    # Line2D may contains string color expression
                    result = conv.to_rgba(result)
                elif isinstance(patch, (PolyCollection, LineCollection)):
                    result = tuple(patch.get_edgecolor()[0])
                else:
                    result = patch.get_edgecolor()

                expected = conv.to_rgba(color)
                assert result == expected

        if facecolors is not None:

            if mapping is not None:
                facecolors = self._get_colors_mapped(mapping, facecolors)
                facecolors = facecolors[:len(collections)]

            assert len(collections) == len(facecolors)
            for patch, color in zip(collections, facecolors):
                if isinstance(patch, Collection):
                    # returned as list of np.array
                    result = patch.get_facecolor()[0]
                else:
                    result = patch.get_facecolor()

                if isinstance(result, np.ndarray):
                    result = tuple(result)

                expected = conv.to_rgba(color)
                assert result == expected

    def _check_text_labels(self, texts, expected):
        """
        Check each text has expected labels

        Parameters
        ----------
        texts : matplotlib Text object, or its list-like
            target text, or its list
        expected : str or list-like which has the same length as texts
            expected text label, or its list
        """
        if not is_list_like(texts):
            assert texts.get_text() == expected
        else:
            labels = [t.get_text() for t in texts]
            assert len(labels) == len(expected)
            for label, e in zip(labels, expected):
                assert label == e

    def _check_ticks_props(self, axes, xlabelsize=None, xrot=None,
                           ylabelsize=None, yrot=None):
        """
        Check each axes has expected tick properties

        Parameters
        ----------
        axes : matplotlib Axes object, or its list-like
        xlabelsize : number
            expected xticks font size
        xrot : number
            expected xticks rotation
        ylabelsize : number
            expected yticks font size
        yrot : number
            expected yticks rotation
        """
        from matplotlib.ticker import NullFormatter
        axes = self._flatten_visible(axes)
        for ax in axes:
            if xlabelsize or xrot:
                if isinstance(ax.xaxis.get_minor_formatter(), NullFormatter):
                    # If minor ticks has NullFormatter, rot / fontsize are not
                    # retained
                    labels = ax.get_xticklabels()
                else:
                    labels = ax.get_xticklabels() + ax.get_xticklabels(
                        minor=True)

                for label in labels:
                    if xlabelsize is not None:
                        tm.assert_almost_equal(label.get_fontsize(),
                                               xlabelsize)
                    if xrot is not None:
                        tm.assert_almost_equal(label.get_rotation(), xrot)

            if ylabelsize or yrot:
                if isinstance(ax.yaxis.get_minor_formatter(), NullFormatter):
                    labels = ax.get_yticklabels()
                else:
                    labels = ax.get_yticklabels() + ax.get_yticklabels(
                        minor=True)

                for label in labels:
                    if ylabelsize is not None:
                        tm.assert_almost_equal(label.get_fontsize(),
                                               ylabelsize)
                    if yrot is not None:
                        tm.assert_almost_equal(label.get_rotation(), yrot)

    def _check_ax_scales(self, axes, xaxis='linear', yaxis='linear'):
        """
        Check each axes has expected scales

        Parameters
        ----------
        axes : matplotlib Axes object, or its list-like
        xaxis : {'linear', 'log'}
            expected xaxis scale
        yaxis :  {'linear', 'log'}
            expected yaxis scale
        """
        axes = self._flatten_visible(axes)
        for ax in axes:
            assert ax.xaxis.get_scale() == xaxis
            assert ax.yaxis.get_scale() == yaxis

    def _check_axes_shape(self, axes, axes_num=None, layout=None,
                          figsize=None):
        """
        Check expected number of axes is drawn in expected layout

        Parameters
        ----------
        axes : matplotlib Axes object, or its list-like
        axes_num : number
            expected number of axes. Unnecessary axes should be set to
            invisible.
        layout :  tuple
            expected layout, (expected number of rows , columns)
        figsize : tuple
            expected figsize. default is matplotlib default
        """
        if figsize is None:
            figsize = self.default_figsize
        visible_axes = self._flatten_visible(axes)

        if axes_num is not None:
            assert len(visible_axes) == axes_num
            for ax in visible_axes:
                # check something drawn on visible axes
                assert len(ax.get_children()) > 0

        if layout is not None:
            result = self._get_axes_layout(_flatten(axes))
            assert result == layout

        tm.assert_numpy_array_equal(
            visible_axes[0].figure.get_size_inches(),
            np.array(figsize, dtype=np.float64))

    def _get_axes_layout(self, axes):
        x_set = set()
        y_set = set()
        for ax in axes:
            # check axes coordinates to estimate layout
            points = ax.get_position().get_points()
            x_set.add(points[0][0])
            y_set.add(points[0][1])
        return (len(y_set), len(x_set))

    def _flatten_visible(self, axes):
        """
        Flatten axes, and filter only visible

        Parameters
        ----------
        axes : matplotlib Axes object, or its list-like

        """
        axes = _flatten(axes)
        axes = [ax for ax in axes if ax.get_visible()]
        return axes

    def _check_has_errorbars(self, axes, xerr=0, yerr=0):
        """
        Check axes has expected number of errorbars

        Parameters
        ----------
        axes : matplotlib Axes object, or its list-like
        xerr : number
            expected number of x errorbar
        yerr : number
            expected number of y errorbar
        """
        axes = self._flatten_visible(axes)
        for ax in axes:
            containers = ax.containers
            xerr_count = 0
            yerr_count = 0
            for c in containers:
                has_xerr = getattr(c, 'has_xerr', False)
                has_yerr = getattr(c, 'has_yerr', False)
                if has_xerr:
                    xerr_count += 1
                if has_yerr:
                    yerr_count += 1
            assert xerr == xerr_count
            assert yerr == yerr_count

    def _check_box_return_type(self, returned, return_type, expected_keys=None,
                               check_ax_title=True):
        """
        Check box returned type is correct

        Parameters
        ----------
        returned : object to be tested, returned from boxplot
        return_type : str
            return_type passed to boxplot
        expected_keys : list-like, optional
            group labels in subplot case. If not passed,
            the function checks assuming boxplot uses single ax
        check_ax_title : bool
            Whether to check the ax.title is the same as expected_key
            Intended to be checked by calling from ``boxplot``.
            Normal ``plot`` doesn't attach ``ax.title``, it must be disabled.
        """
        from matplotlib.axes import Axes
        types = {'dict': dict, 'axes': Axes, 'both': tuple}
        if expected_keys is None:
            # should be fixed when the returning default is changed
            if return_type is None:
                return_type = 'dict'

            assert isinstance(returned, types[return_type])
            if return_type == 'both':
                assert isinstance(returned.ax, Axes)
                assert isinstance(returned.lines, dict)
        else:
            # should be fixed when the returning default is changed
            if return_type is None:
                for r in self._flatten_visible(returned):
                    assert isinstance(r, Axes)
                return

            assert isinstance(returned, Series)

            assert sorted(returned.keys()) == sorted(expected_keys)
            for key, value in iteritems(returned):
                assert isinstance(value, types[return_type])
                # check returned dict has correct mapping
                if return_type == 'axes':
                    if check_ax_title:
                        assert value.get_title() == key
                elif return_type == 'both':
                    if check_ax_title:
                        assert value.ax.get_title() == key
                    assert isinstance(value.ax, Axes)
                    assert isinstance(value.lines, dict)
                elif return_type == 'dict':
                    line = value['medians'][0]
                    axes = line.axes
                    if check_ax_title:
                        assert axes.get_title() == key
                else:
                    raise AssertionError

    def _check_grid_settings(self, obj, kinds, kws={}):
        # Make sure plot defaults to rcParams['axes.grid'] setting, GH 9792

        import matplotlib as mpl

        def is_grid_on():
            xoff = all(not g.gridOn
                       for g in self.plt.gca().xaxis.get_major_ticks())
            yoff = all(not g.gridOn
                       for g in self.plt.gca().yaxis.get_major_ticks())
            return not (xoff and yoff)

        spndx = 1
        for kind in kinds:
            if not _ok_for_gaussian_kde(kind):
                continue

            self.plt.subplot(1, 4 * len(kinds), spndx)
            spndx += 1
            mpl.rc('axes', grid=False)
            obj.plot(kind=kind, **kws)
            assert not is_grid_on()

            self.plt.subplot(1, 4 * len(kinds), spndx)
            spndx += 1
            mpl.rc('axes', grid=True)
            obj.plot(kind=kind, grid=False, **kws)
            assert not is_grid_on()

            if kind != 'pie':
                self.plt.subplot(1, 4 * len(kinds), spndx)
                spndx += 1
                mpl.rc('axes', grid=True)
                obj.plot(kind=kind, **kws)
                assert is_grid_on()

                self.plt.subplot(1, 4 * len(kinds), spndx)
                spndx += 1
                mpl.rc('axes', grid=False)
                obj.plot(kind=kind, grid=True, **kws)
                assert is_grid_on()

    def _unpack_cycler(self, rcParams, field='color'):
        """
        Auxiliary function for correctly unpacking cycler after MPL >= 1.5
        """
        return [v[field] for v in rcParams['axes.prop_cycle']]


def _check_plot_works(f, filterwarnings='always', **kwargs):
    import matplotlib.pyplot as plt
    ret = None
    with warnings.catch_warnings():
        warnings.simplefilter(filterwarnings)
        try:
            try:
                fig = kwargs['figure']
            except KeyError:
                fig = plt.gcf()

            plt.clf()

            ax = kwargs.get('ax', fig.add_subplot(211))  # noqa
            ret = f(**kwargs)

            assert_is_valid_plot_return_object(ret)

            try:
                kwargs['ax'] = fig.add_subplot(212)
                ret = f(**kwargs)
            except Exception:
                pass
            else:
                assert_is_valid_plot_return_object(ret)

            with ensure_clean(return_filelike=True) as path:
                plt.savefig(path)
        finally:
            tm.close(fig)

        return ret


def curpath():
    pth, _ = os.path.split(os.path.abspath(__file__))
    return pth
