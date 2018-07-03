# -*- coding: utf-8 -*-
import numpy as np
import pandas as pd
import pandas.util.testing as tm
import pytest
from pandas import CategoricalIndex, DataFrame, Index, MultiIndex, RangeIndex
from pandas.compat import lrange
from pandas.errors import PerformanceWarning, UnsortedIndexError


def test_sortlevel(idx):
    import random

    tuples = list(idx)
    random.shuffle(tuples)

    index = MultiIndex.from_tuples(tuples)

    sorted_idx, _ = index.sortlevel(0)
    expected = MultiIndex.from_tuples(sorted(tuples))
    assert sorted_idx.equals(expected)

    sorted_idx, _ = index.sortlevel(0, ascending=False)
    assert sorted_idx.equals(expected[::-1])

    sorted_idx, _ = index.sortlevel(1)
    by1 = sorted(tuples, key=lambda x: (x[1], x[0]))
    expected = MultiIndex.from_tuples(by1)
    assert sorted_idx.equals(expected)

    sorted_idx, _ = index.sortlevel(1, ascending=False)
    assert sorted_idx.equals(expected[::-1])


def test_sortlevel_not_sort_remaining():
    mi = MultiIndex.from_tuples([[1, 1, 3], [1, 1, 1]], names=list('ABC'))
    sorted_idx, _ = mi.sortlevel('A', sort_remaining=False)
    assert sorted_idx.equals(mi)


def test_sortlevel_deterministic():
    tuples = [('bar', 'one'), ('foo', 'two'), ('qux', 'two'),
              ('foo', 'one'), ('baz', 'two'), ('qux', 'one')]

    index = MultiIndex.from_tuples(tuples)

    sorted_idx, _ = index.sortlevel(0)
    expected = MultiIndex.from_tuples(sorted(tuples))
    assert sorted_idx.equals(expected)

    sorted_idx, _ = index.sortlevel(0, ascending=False)
    assert sorted_idx.equals(expected[::-1])

    sorted_idx, _ = index.sortlevel(1)
    by1 = sorted(tuples, key=lambda x: (x[1], x[0]))
    expected = MultiIndex.from_tuples(by1)
    assert sorted_idx.equals(expected)

    sorted_idx, _ = index.sortlevel(1, ascending=False)
    assert sorted_idx.equals(expected[::-1])


def test_sort(indices):
    pytest.raises(TypeError, indices.sort)


def test_numpy_argsort(idx):
    result = np.argsort(idx)
    expected = idx.argsort()
    tm.assert_numpy_array_equal(result, expected)

    # these are the only two types that perform
    # pandas compatibility input validation - the
    # rest already perform separate (or no) such
    # validation via their 'values' attribute as
    # defined in pandas.core.indexes/base.py - they
    # cannot be changed at the moment due to
    # backwards compatibility concerns
    if isinstance(type(idx), (CategoricalIndex, RangeIndex)):
        msg = "the 'axis' parameter is not supported"
        tm.assert_raises_regex(ValueError, msg,
                               np.argsort, idx, axis=1)

        msg = "the 'kind' parameter is not supported"
        tm.assert_raises_regex(ValueError, msg, np.argsort,
                               idx, kind='mergesort')

        msg = "the 'order' parameter is not supported"
        tm.assert_raises_regex(ValueError, msg, np.argsort,
                               idx, order=('a', 'b'))


def test_unsortedindex():
    # GH 11897
    mi = pd.MultiIndex.from_tuples([('z', 'a'), ('x', 'a'), ('y', 'b'),
                                    ('x', 'b'), ('y', 'a'), ('z', 'b')],
                                   names=['one', 'two'])
    df = pd.DataFrame([[i, 10 * i] for i in lrange(6)], index=mi,
                      columns=['one', 'two'])

    # GH 16734: not sorted, but no real slicing
    result = df.loc(axis=0)['z', 'a']
    expected = df.iloc[0]
    tm.assert_series_equal(result, expected)

    with pytest.raises(UnsortedIndexError):
        df.loc(axis=0)['z', slice('a')]
    df.sort_index(inplace=True)
    assert len(df.loc(axis=0)['z', :]) == 2

    with pytest.raises(KeyError):
        df.loc(axis=0)['q', :]


def test_unsortedindex_doc_examples():
    # http://pandas.pydata.org/pandas-docs/stable/advanced.html#sorting-a-multiindex  # noqa
    dfm = DataFrame({'jim': [0, 0, 1, 1],
                     'joe': ['x', 'x', 'z', 'y'],
                     'jolie': np.random.rand(4)})

    dfm = dfm.set_index(['jim', 'joe'])
    with tm.assert_produces_warning(PerformanceWarning):
        dfm.loc[(1, 'z')]

    with pytest.raises(UnsortedIndexError):
        dfm.loc[(0, 'y'):(1, 'z')]

    assert not dfm.index.is_lexsorted()
    assert dfm.index.lexsort_depth == 1

    # sort it
    dfm = dfm.sort_index()
    dfm.loc[(1, 'z')]
    dfm.loc[(0, 'y'):(1, 'z')]

    assert dfm.index.is_lexsorted()
    assert dfm.index.lexsort_depth == 2


def test_reconstruct_sort():

    # starts off lexsorted & monotonic
    mi = MultiIndex.from_arrays([
        ['A', 'A', 'B', 'B', 'B'], [1, 2, 1, 2, 3]
    ])
    assert mi.is_lexsorted()
    assert mi.is_monotonic

    recons = mi._sort_levels_monotonic()
    assert recons.is_lexsorted()
    assert recons.is_monotonic
    assert mi is recons

    assert mi.equals(recons)
    assert Index(mi.values).equals(Index(recons.values))

    # cannot convert to lexsorted
    mi = pd.MultiIndex.from_tuples([('z', 'a'), ('x', 'a'), ('y', 'b'),
                                    ('x', 'b'), ('y', 'a'), ('z', 'b')],
                                   names=['one', 'two'])
    assert not mi.is_lexsorted()
    assert not mi.is_monotonic

    recons = mi._sort_levels_monotonic()
    assert not recons.is_lexsorted()
    assert not recons.is_monotonic

    assert mi.equals(recons)
    assert Index(mi.values).equals(Index(recons.values))

    # cannot convert to lexsorted
    mi = MultiIndex(levels=[['b', 'd', 'a'], [1, 2, 3]],
                    labels=[[0, 1, 0, 2], [2, 0, 0, 1]],
                    names=['col1', 'col2'])
    assert not mi.is_lexsorted()
    assert not mi.is_monotonic

    recons = mi._sort_levels_monotonic()
    assert not recons.is_lexsorted()
    assert not recons.is_monotonic

    assert mi.equals(recons)
    assert Index(mi.values).equals(Index(recons.values))


def test_reconstruct_remove_unused():
    # xref to GH 2770
    df = DataFrame([['deleteMe', 1, 9],
                    ['keepMe', 2, 9],
                    ['keepMeToo', 3, 9]],
                   columns=['first', 'second', 'third'])
    df2 = df.set_index(['first', 'second'], drop=False)
    df2 = df2[df2['first'] != 'deleteMe']

    # removed levels are there
    expected = MultiIndex(levels=[['deleteMe', 'keepMe', 'keepMeToo'],
                                  [1, 2, 3]],
                          labels=[[1, 2], [1, 2]],
                          names=['first', 'second'])
    result = df2.index
    tm.assert_index_equal(result, expected)

    expected = MultiIndex(levels=[['keepMe', 'keepMeToo'],
                                  [2, 3]],
                          labels=[[0, 1], [0, 1]],
                          names=['first', 'second'])
    result = df2.index.remove_unused_levels()
    tm.assert_index_equal(result, expected)

    # idempotent
    result2 = result.remove_unused_levels()
    tm.assert_index_equal(result2, expected)
    assert result2.is_(result)


@pytest.mark.parametrize('first_type,second_type', [
    ('int64', 'int64'),
    ('datetime64[D]', 'str')])
def test_remove_unused_levels_large(first_type, second_type):
    # GH16556

    # because tests should be deterministic (and this test in particular
    # checks that levels are removed, which is not the case for every
    # random input):
    rng = np.random.RandomState(4)  # seed is arbitrary value that works

    size = 1 << 16
    df = DataFrame(dict(
        first=rng.randint(0, 1 << 13, size).astype(first_type),
        second=rng.randint(0, 1 << 10, size).astype(second_type),
        third=rng.rand(size)))
    df = df.groupby(['first', 'second']).sum()
    df = df[df.third < 0.1]

    result = df.index.remove_unused_levels()
    assert len(result.levels[0]) < len(df.index.levels[0])
    assert len(result.levels[1]) < len(df.index.levels[1])
    assert result.equals(df.index)

    expected = df.reset_index().set_index(['first', 'second']).index
    tm.assert_index_equal(result, expected)


@pytest.mark.parametrize('level0', [['a', 'd', 'b'],
                                    ['a', 'd', 'b', 'unused']])
@pytest.mark.parametrize('level1', [['w', 'x', 'y', 'z'],
                                    ['w', 'x', 'y', 'z', 'unused']])
def test_remove_unused_nan(level0, level1):
    # GH 18417
    mi = pd.MultiIndex(levels=[level0, level1],
                       labels=[[0, 2, -1, 1, -1], [0, 1, 2, 3, 2]])

    result = mi.remove_unused_levels()
    tm.assert_index_equal(result, mi)
    for level in 0, 1:
        assert('unused' not in result.levels[level])
