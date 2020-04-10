from datetime import datetime

import numpy as np
import pytest

from pandas.compat import PY37

import pandas as pd
from pandas import (
    Categorical,
    CategoricalIndex,
    DataFrame,
    Index,
    MultiIndex,
    Series,
    qcut,
)
import pandas._testing as tm


def cartesian_product_for_groupers(result, args, names):
    """ Reindex to a cartesian production for the groupers,
    preserving the nature (Categorical) of each grouper
    """

    def f(a):
        if isinstance(a, (CategoricalIndex, Categorical)):
            categories = a.categories
            a = Categorical.from_codes(
                np.arange(len(categories)), categories=categories, ordered=a.ordered
            )
        return a

    index = MultiIndex.from_product(map(f, args), names=names)
    return result.reindex(index).sort_index()


def test_apply_use_categorical_name(df):
    cats = qcut(df.C, 4)

    def get_stats(group):
        return {
            "min": group.min(),
            "max": group.max(),
            "count": group.count(),
            "mean": group.mean(),
        }

    result = df.groupby(cats, observed=False).D.apply(get_stats)
    assert result.index.names[0] == "C"


def test_basic():

    cats = Categorical(
        ["a", "a", "a", "b", "b", "b", "c", "c", "c"],
        categories=["a", "b", "c", "d"],
        ordered=True,
    )
    data = DataFrame({"a": [1, 1, 1, 2, 2, 2, 3, 4, 5], "b": cats})

    exp_index = CategoricalIndex(list("abcd"), name="b", ordered=True)
    expected = DataFrame({"a": [1, 2, 4, np.nan]}, index=exp_index)
    result = data.groupby("b", observed=False).mean()
    tm.assert_frame_equal(result, expected)

    cat1 = Categorical(["a", "a", "b", "b"], categories=["a", "b", "z"], ordered=True)
    cat2 = Categorical(["c", "d", "c", "d"], categories=["c", "d", "y"], ordered=True)
    df = DataFrame({"A": cat1, "B": cat2, "values": [1, 2, 3, 4]})

    # single grouper
    gb = df.groupby("A", observed=False)
    exp_idx = CategoricalIndex(["a", "b", "z"], name="A", ordered=True)
    expected = DataFrame({"values": Series([3, 7, 0], index=exp_idx)})
    result = gb.sum()
    tm.assert_frame_equal(result, expected)

    # GH 8623
    x = DataFrame(
        [[1, "John P. Doe"], [2, "Jane Dove"], [1, "John P. Doe"]],
        columns=["person_id", "person_name"],
    )
    x["person_name"] = Categorical(x.person_name)

    g = x.groupby(["person_id"], observed=False)
    result = g.transform(lambda x: x)
    tm.assert_frame_equal(result, x[["person_name"]])

    result = x.drop_duplicates("person_name")
    expected = x.iloc[[0, 1]]
    tm.assert_frame_equal(result, expected)

    def f(x):
        return x.drop_duplicates("person_name").iloc[0]

    result = g.apply(f)
    expected = x.iloc[[0, 1]].copy()
    expected.index = Index([1, 2], name="person_id")
    expected["person_name"] = expected["person_name"].astype("object")
    tm.assert_frame_equal(result, expected)

    # GH 9921
    # Monotonic
    df = DataFrame({"a": [5, 15, 25]})
    c = pd.cut(df.a, bins=[0, 10, 20, 30, 40])

    result = df.a.groupby(c, observed=False).transform(sum)
    tm.assert_series_equal(result, df["a"])

    tm.assert_series_equal(
        df.a.groupby(c, observed=False).transform(lambda xs: np.sum(xs)), df["a"]
    )
    tm.assert_frame_equal(df.groupby(c, observed=False).transform(sum), df[["a"]])
    tm.assert_frame_equal(
        df.groupby(c, observed=False).transform(lambda xs: np.max(xs)), df[["a"]]
    )

    # Filter
    tm.assert_series_equal(df.a.groupby(c, observed=False).filter(np.all), df["a"])
    tm.assert_frame_equal(df.groupby(c, observed=False).filter(np.all), df)

    # Non-monotonic
    df = DataFrame({"a": [5, 15, 25, -5]})
    c = pd.cut(df.a, bins=[-10, 0, 10, 20, 30, 40])

    result = df.a.groupby(c, observed=False).transform(sum)
    tm.assert_series_equal(result, df["a"])

    tm.assert_series_equal(
        df.a.groupby(c, observed=False).transform(lambda xs: np.sum(xs)), df["a"]
    )
    tm.assert_frame_equal(df.groupby(c, observed=False).transform(sum), df[["a"]])
    tm.assert_frame_equal(
        df.groupby(c, observed=False).transform(lambda xs: np.sum(xs)), df[["a"]]
    )

    # GH 9603
    df = DataFrame({"a": [1, 0, 0, 0]})
    c = pd.cut(df.a, [0, 1, 2, 3, 4], labels=Categorical(list("abcd")))
    result = df.groupby(c, observed=False).apply(len)

    exp_index = CategoricalIndex(c.values.categories, ordered=c.values.ordered)
    expected = Series([1, 0, 0, 0], index=exp_index)
    expected.index.name = "a"
    tm.assert_series_equal(result, expected)

    # more basic
    levels = ["foo", "bar", "baz", "qux"]
    codes = np.random.randint(0, 4, size=100)

    cats = Categorical.from_codes(codes, levels, ordered=True)

    data = DataFrame(np.random.randn(100, 4))

    result = data.groupby(cats, observed=False).mean()

    expected = data.groupby(np.asarray(cats), observed=False).mean()
    exp_idx = CategoricalIndex(levels, categories=cats.categories, ordered=True)
    expected = expected.reindex(exp_idx)

    tm.assert_frame_equal(result, expected)

    grouped = data.groupby(cats, observed=False)
    desc_result = grouped.describe()

    idx = cats.codes.argsort()
    ord_labels = np.asarray(cats).take(idx)
    ord_data = data.take(idx)

    exp_cats = Categorical(
        ord_labels, ordered=True, categories=["foo", "bar", "baz", "qux"]
    )
    expected = ord_data.groupby(exp_cats, sort=False, observed=False).describe()
    tm.assert_frame_equal(desc_result, expected)

    # GH 10460
    expc = Categorical.from_codes(np.arange(4).repeat(8), levels, ordered=True)
    exp = CategoricalIndex(expc)
    tm.assert_index_equal((desc_result.stack().index.get_level_values(0)), exp)
    exp = Index(["count", "mean", "std", "min", "25%", "50%", "75%", "max"] * 4)
    tm.assert_index_equal((desc_result.stack().index.get_level_values(1)), exp)


def test_level_get_group(observed):
    # GH15155
    df = DataFrame(
        data=np.arange(2, 22, 2),
        index=MultiIndex(
            levels=[CategoricalIndex(["a", "b"]), range(10)],
            codes=[[0] * 5 + [1] * 5, range(10)],
            names=["Index1", "Index2"],
        ),
    )
    g = df.groupby(level=["Index1"], observed=observed)

    # expected should equal test.loc[["a"]]
    # GH15166
    expected = DataFrame(
        data=np.arange(2, 12, 2),
        index=MultiIndex(
            levels=[CategoricalIndex(["a", "b"]), range(5)],
            codes=[[0] * 5, range(5)],
            names=["Index1", "Index2"],
        ),
    )
    result = g.get_group("a")

    tm.assert_frame_equal(result, expected)


# GH#21636 flaky on py37; may be related to older numpy, see discussion
#  https://github.com/MacPython/pandas-wheels/pull/64
@pytest.mark.xfail(PY37, reason="Flaky, GH-27902", strict=False)
@pytest.mark.parametrize("ordered", [True, False])
def test_apply(ordered):
    # GH 10138

    dense = Categorical(list("abc"), ordered=ordered)

    # 'b' is in the categories but not in the list
    missing = Categorical(list("aaa"), categories=["a", "b"], ordered=ordered)
    values = np.arange(len(dense))
    df = DataFrame({"missing": missing, "dense": dense, "values": values})
    grouped = df.groupby(["missing", "dense"], observed=True)

    # missing category 'b' should still exist in the output index
    idx = MultiIndex.from_arrays([missing, dense], names=["missing", "dense"])
    expected = DataFrame([0, 1, 2.0], index=idx, columns=["values"])

    # GH#21636 tracking down the xfail, in some builds np.mean(df.loc[[0]])
    #  is coming back as Series([0., 1., 0.], index=["missing", "dense", "values"])
    #  when we expect Series(0., index=["values"])
    result = grouped.apply(lambda x: np.mean(x))
    tm.assert_frame_equal(result, expected)

    # we coerce back to ints
    expected = expected.astype("int")
    result = grouped.mean()
    tm.assert_frame_equal(result, expected)

    result = grouped.agg(np.mean)
    tm.assert_frame_equal(result, expected)

    # but for transform we should still get back the original index
    idx = MultiIndex.from_arrays([missing, dense], names=["missing", "dense"])
    expected = Series(1, index=idx)
    result = grouped.apply(lambda x: 1)
    tm.assert_series_equal(result, expected)


def test_observed(observed):
    # multiple groupers, don't re-expand the output space
    # of the grouper
    # gh-14942 (implement)
    # gh-10132 (back-compat)
    # gh-8138 (back-compat)
    # gh-8869

    cat1 = Categorical(["a", "a", "b", "b"], categories=["a", "b", "z"], ordered=True)
    cat2 = Categorical(["c", "d", "c", "d"], categories=["c", "d", "y"], ordered=True)
    df = DataFrame({"A": cat1, "B": cat2, "values": [1, 2, 3, 4]})
    df["C"] = ["foo", "bar"] * 2

    # multiple groupers with a non-cat
    gb = df.groupby(["A", "B", "C"], observed=observed)
    exp_index = MultiIndex.from_arrays(
        [cat1, cat2, ["foo", "bar"] * 2], names=["A", "B", "C"]
    )
    expected = DataFrame({"values": Series([1, 2, 3, 4], index=exp_index)}).sort_index()
    result = gb.sum()
    if not observed:
        expected = cartesian_product_for_groupers(
            expected, [cat1, cat2, ["foo", "bar"]], list("ABC")
        )

    tm.assert_frame_equal(result, expected)

    gb = df.groupby(["A", "B"], observed=observed)
    exp_index = MultiIndex.from_arrays([cat1, cat2], names=["A", "B"])
    expected = DataFrame({"values": [1, 2, 3, 4]}, index=exp_index)
    result = gb.sum()
    if not observed:
        expected = cartesian_product_for_groupers(expected, [cat1, cat2], list("AB"))

    tm.assert_frame_equal(result, expected)

    # https://github.com/pandas-dev/pandas/issues/8138
    d = {
        "cat": Categorical(
            ["a", "b", "a", "b"], categories=["a", "b", "c"], ordered=True
        ),
        "ints": [1, 1, 2, 2],
        "val": [10, 20, 30, 40],
    }
    df = DataFrame(d)

    # Grouping on a single column
    groups_single_key = df.groupby("cat", observed=observed)
    result = groups_single_key.mean()

    exp_index = CategoricalIndex(
        list("ab"), name="cat", categories=list("abc"), ordered=True
    )
    expected = DataFrame({"ints": [1.5, 1.5], "val": [20.0, 30]}, index=exp_index)
    if not observed:
        index = CategoricalIndex(
            list("abc"), name="cat", categories=list("abc"), ordered=True
        )
        expected = expected.reindex(index)

    tm.assert_frame_equal(result, expected)

    # Grouping on two columns
    groups_double_key = df.groupby(["cat", "ints"], observed=observed)
    result = groups_double_key.agg("mean")
    expected = DataFrame(
        {
            "val": [10, 30, 20, 40],
            "cat": Categorical(
                ["a", "a", "b", "b"], categories=["a", "b", "c"], ordered=True
            ),
            "ints": [1, 2, 1, 2],
        }
    ).set_index(["cat", "ints"])
    if not observed:
        expected = cartesian_product_for_groupers(
            expected, [df.cat.values, [1, 2]], ["cat", "ints"]
        )

    tm.assert_frame_equal(result, expected)

    # GH 10132
    for key in [("a", 1), ("b", 2), ("b", 1), ("a", 2)]:
        c, i = key
        result = groups_double_key.get_group(key)
        expected = df[(df.cat == c) & (df.ints == i)]
        tm.assert_frame_equal(result, expected)

    # gh-8869
    # with as_index
    d = {
        "foo": [10, 8, 4, 8, 4, 1, 1],
        "bar": [10, 20, 30, 40, 50, 60, 70],
        "baz": ["d", "c", "e", "a", "a", "d", "c"],
    }
    df = DataFrame(d)
    cat = pd.cut(df["foo"], np.linspace(0, 10, 3))
    df["range"] = cat
    groups = df.groupby(["range", "baz"], as_index=False, observed=observed)
    result = groups.agg("mean")

    groups2 = df.groupby(["range", "baz"], as_index=True, observed=observed)
    expected = groups2.agg("mean").reset_index()
    tm.assert_frame_equal(result, expected)


def test_observed_codes_remap(observed):
    d = {"C1": [3, 3, 4, 5], "C2": [1, 2, 3, 4], "C3": [10, 100, 200, 34]}
    df = DataFrame(d)
    values = pd.cut(df["C1"], [1, 2, 3, 6])
    values.name = "cat"
    groups_double_key = df.groupby([values, "C2"], observed=observed)

    idx = MultiIndex.from_arrays([values, [1, 2, 3, 4]], names=["cat", "C2"])
    expected = DataFrame({"C1": [3, 3, 4, 5], "C3": [10, 100, 200, 34]}, index=idx)
    if not observed:
        expected = cartesian_product_for_groupers(
            expected, [values.values, [1, 2, 3, 4]], ["cat", "C2"]
        )

    result = groups_double_key.agg("mean")
    tm.assert_frame_equal(result, expected)


def test_observed_perf():
    # we create a cartesian product, so this is
    # non-performant if we don't use observed values
    # gh-14942
    df = DataFrame(
        {
            "cat": np.random.randint(0, 255, size=30000),
            "int_id": np.random.randint(0, 255, size=30000),
            "other_id": np.random.randint(0, 10000, size=30000),
            "foo": 0,
        }
    )
    df["cat"] = df.cat.astype(str).astype("category")

    grouped = df.groupby(["cat", "int_id", "other_id"], observed=True)
    result = grouped.count()
    assert result.index.levels[0].nunique() == df.cat.nunique()
    assert result.index.levels[1].nunique() == df.int_id.nunique()
    assert result.index.levels[2].nunique() == df.other_id.nunique()


def test_observed_groups(observed):
    # gh-20583
    # test that we have the appropriate groups

    cat = Categorical(["a", "c", "a"], categories=["a", "b", "c"])
    df = DataFrame({"cat": cat, "vals": [1, 2, 3]})
    g = df.groupby("cat", observed=observed)

    result = g.groups
    if observed:
        expected = {"a": Index([0, 2], dtype="int64"), "c": Index([1], dtype="int64")}
    else:
        expected = {
            "a": Index([0, 2], dtype="int64"),
            "b": Index([], dtype="int64"),
            "c": Index([1], dtype="int64"),
        }

    tm.assert_dict_equal(result, expected)


def test_observed_groups_with_nan(observed):
    # GH 24740
    df = DataFrame(
        {
            "cat": Categorical(["a", np.nan, "a"], categories=["a", "b", "d"]),
            "vals": [1, 2, 3],
        }
    )
    g = df.groupby("cat", observed=observed)
    result = g.groups
    if observed:
        expected = {"a": Index([0, 2], dtype="int64")}
    else:
        expected = {
            "a": Index([0, 2], dtype="int64"),
            "b": Index([], dtype="int64"),
            "d": Index([], dtype="int64"),
        }
    tm.assert_dict_equal(result, expected)


def test_observed_nth():
    # GH 26385
    cat = pd.Categorical(["a", np.nan, np.nan], categories=["a", "b", "c"])
    ser = pd.Series([1, 2, 3])
    df = pd.DataFrame({"cat": cat, "ser": ser})

    result = df.groupby("cat", observed=False)["ser"].nth(0)

    index = pd.Categorical(["a", "b", "c"], categories=["a", "b", "c"])
    expected = pd.Series([1, np.nan, np.nan], index=index, name="ser")
    expected.index.name = "cat"

    tm.assert_series_equal(result, expected)


def test_dataframe_categorical_with_nan(observed):
    # GH 21151
    s1 = Categorical([np.nan, "a", np.nan, "a"], categories=["a", "b", "c"])
    s2 = Series([1, 2, 3, 4])
    df = DataFrame({"s1": s1, "s2": s2})
    result = df.groupby("s1", observed=observed).first().reset_index()
    if observed:
        expected = DataFrame(
            {"s1": Categorical(["a"], categories=["a", "b", "c"]), "s2": [2]}
        )
    else:
        expected = DataFrame(
            {
                "s1": Categorical(["a", "b", "c"], categories=["a", "b", "c"]),
                "s2": [2, np.nan, np.nan],
            }
        )
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("ordered", [True, False])
@pytest.mark.parametrize("observed", [True, False])
@pytest.mark.parametrize("sort", [True, False])
def test_dataframe_categorical_ordered_observed_sort(ordered, observed, sort):
    # GH 25871: Fix groupby sorting on ordered Categoricals
    # GH 25167: Groupby with observed=True doesn't sort

    # Build a dataframe with cat having one unobserved category ('missing'),
    # and a Series with identical values
    label = Categorical(
        ["d", "a", "b", "a", "d", "b"],
        categories=["a", "b", "missing", "d"],
        ordered=ordered,
    )
    val = Series(["d", "a", "b", "a", "d", "b"])
    df = DataFrame({"label": label, "val": val})

    # aggregate on the Categorical
    result = df.groupby("label", observed=observed, sort=sort)["val"].aggregate("first")

    # If ordering works, we expect index labels equal to aggregation results,
    # except for 'observed=False': label 'missing' has aggregation None
    label = Series(result.index.array, dtype="object")
    aggr = Series(result.array)
    if not observed:
        aggr[aggr.isna()] = "missing"
    if not all(label == aggr):
        msg = (
            f"Labels and aggregation results not consistently sorted\n"
            + "for (ordered={ordered}, observed={observed}, sort={sort})\n"
            + "Result:\n{result}"
        )
        assert False, msg


def test_datetime():
    # GH9049: ensure backward compatibility
    levels = pd.date_range("2014-01-01", periods=4)
    codes = np.random.randint(0, 4, size=100)

    cats = Categorical.from_codes(codes, levels, ordered=True)

    data = DataFrame(np.random.randn(100, 4))
    result = data.groupby(cats, observed=False).mean()

    expected = data.groupby(np.asarray(cats), observed=False).mean()
    expected = expected.reindex(levels)
    expected.index = CategoricalIndex(
        expected.index, categories=expected.index, ordered=True
    )

    tm.assert_frame_equal(result, expected)

    grouped = data.groupby(cats, observed=False)
    desc_result = grouped.describe()

    idx = cats.codes.argsort()
    ord_labels = cats.take(idx)
    ord_data = data.take(idx)
    expected = ord_data.groupby(ord_labels, observed=False).describe()
    tm.assert_frame_equal(desc_result, expected)
    tm.assert_index_equal(desc_result.index, expected.index)
    tm.assert_index_equal(
        desc_result.index.get_level_values(0), expected.index.get_level_values(0)
    )

    # GH 10460
    expc = Categorical.from_codes(np.arange(4).repeat(8), levels, ordered=True)
    exp = CategoricalIndex(expc)
    tm.assert_index_equal((desc_result.stack().index.get_level_values(0)), exp)
    exp = Index(["count", "mean", "std", "min", "25%", "50%", "75%", "max"] * 4)
    tm.assert_index_equal((desc_result.stack().index.get_level_values(1)), exp)


def test_categorical_index():

    s = np.random.RandomState(12345)
    levels = ["foo", "bar", "baz", "qux"]
    codes = s.randint(0, 4, size=20)
    cats = Categorical.from_codes(codes, levels, ordered=True)
    df = DataFrame(np.repeat(np.arange(20), 4).reshape(-1, 4), columns=list("abcd"))
    df["cats"] = cats

    # with a cat index
    result = df.set_index("cats").groupby(level=0, observed=False).sum()
    expected = df[list("abcd")].groupby(cats.codes, observed=False).sum()
    expected.index = CategoricalIndex(
        Categorical.from_codes([0, 1, 2, 3], levels, ordered=True), name="cats"
    )
    tm.assert_frame_equal(result, expected)

    # with a cat column, should produce a cat index
    result = df.groupby("cats", observed=False).sum()
    expected = df[list("abcd")].groupby(cats.codes, observed=False).sum()
    expected.index = CategoricalIndex(
        Categorical.from_codes([0, 1, 2, 3], levels, ordered=True), name="cats"
    )
    tm.assert_frame_equal(result, expected)


def test_describe_categorical_columns():
    # GH 11558
    cats = CategoricalIndex(
        ["qux", "foo", "baz", "bar"],
        categories=["foo", "bar", "baz", "qux"],
        ordered=True,
    )
    df = DataFrame(np.random.randn(20, 4), columns=cats)
    result = df.groupby([1, 2, 3, 4] * 5).describe()

    tm.assert_index_equal(result.stack().columns, cats)
    tm.assert_categorical_equal(result.stack().columns.values, cats.values)


def test_unstack_categorical():
    # GH11558 (example is taken from the original issue)
    df = DataFrame(
        {"a": range(10), "medium": ["A", "B"] * 5, "artist": list("XYXXY") * 2}
    )
    df["medium"] = df["medium"].astype("category")

    gcat = df.groupby(["artist", "medium"], observed=False)["a"].count().unstack()
    result = gcat.describe()

    exp_columns = CategoricalIndex(["A", "B"], ordered=False, name="medium")
    tm.assert_index_equal(result.columns, exp_columns)
    tm.assert_categorical_equal(result.columns.values, exp_columns.values)

    result = gcat["A"] + gcat["B"]
    expected = Series([6, 4], index=Index(["X", "Y"], name="artist"))
    tm.assert_series_equal(result, expected)


def test_bins_unequal_len():
    # GH3011
    series = Series([np.nan, np.nan, 1, 1, 2, 2, 3, 3, 4, 4])
    bins = pd.cut(series.dropna().values, 4)

    # len(bins) != len(series) here
    with pytest.raises(ValueError):
        series.groupby(bins).mean()


def test_as_index():
    # GH13204
    df = DataFrame(
        {
            "cat": Categorical([1, 2, 2], [1, 2, 3]),
            "A": [10, 11, 11],
            "B": [101, 102, 103],
        }
    )
    result = df.groupby(["cat", "A"], as_index=False, observed=True).sum()
    expected = DataFrame(
        {
            "cat": Categorical([1, 2], categories=df.cat.cat.categories),
            "A": [10, 11],
            "B": [101, 205],
        },
        columns=["cat", "A", "B"],
    )
    tm.assert_frame_equal(result, expected)

    # function grouper
    f = lambda r: df.loc[r, "A"]
    result = df.groupby(["cat", f], as_index=False, observed=True).sum()
    expected = DataFrame(
        {
            "cat": Categorical([1, 2], categories=df.cat.cat.categories),
            "A": [10, 22],
            "B": [101, 205],
        },
        columns=["cat", "A", "B"],
    )
    tm.assert_frame_equal(result, expected)

    # another not in-axis grouper (conflicting names in index)
    s = Series(["a", "b", "b"], name="cat")
    result = df.groupby(["cat", s], as_index=False, observed=True).sum()
    tm.assert_frame_equal(result, expected)

    # is original index dropped?
    group_columns = ["cat", "A"]
    expected = DataFrame(
        {
            "cat": Categorical([1, 2], categories=df.cat.cat.categories),
            "A": [10, 11],
            "B": [101, 205],
        },
        columns=["cat", "A", "B"],
    )

    for name in [None, "X", "B"]:
        df.index = Index(list("abc"), name=name)
        result = df.groupby(group_columns, as_index=False, observed=True).sum()

        tm.assert_frame_equal(result, expected)


def test_preserve_categories():
    # GH-13179
    categories = list("abc")

    # ordered=True
    df = DataFrame({"A": Categorical(list("ba"), categories=categories, ordered=True)})
    index = CategoricalIndex(categories, categories, ordered=True, name="A")
    tm.assert_index_equal(
        df.groupby("A", sort=True, observed=False).first().index, index
    )
    tm.assert_index_equal(
        df.groupby("A", sort=False, observed=False).first().index, index
    )

    # ordered=False
    df = DataFrame({"A": Categorical(list("ba"), categories=categories, ordered=False)})
    sort_index = CategoricalIndex(categories, categories, ordered=False, name="A")
    nosort_index = CategoricalIndex(list("bac"), list("bac"), ordered=False, name="A")
    tm.assert_index_equal(
        df.groupby("A", sort=True, observed=False).first().index, sort_index
    )
    tm.assert_index_equal(
        df.groupby("A", sort=False, observed=False).first().index, nosort_index
    )


def test_preserve_categorical_dtype():
    # GH13743, GH13854
    df = DataFrame(
        {
            "A": [1, 2, 1, 1, 2],
            "B": [10, 16, 22, 28, 34],
            "C1": Categorical(list("abaab"), categories=list("bac"), ordered=False),
            "C2": Categorical(list("abaab"), categories=list("bac"), ordered=True),
        }
    )
    # single grouper
    exp_full = DataFrame(
        {
            "A": [2.0, 1.0, np.nan],
            "B": [25.0, 20.0, np.nan],
            "C1": Categorical(list("bac"), categories=list("bac"), ordered=False),
            "C2": Categorical(list("bac"), categories=list("bac"), ordered=True),
        }
    )
    for col in ["C1", "C2"]:
        result1 = df.groupby(by=col, as_index=False, observed=False).mean()
        result2 = df.groupby(by=col, as_index=True, observed=False).mean().reset_index()
        expected = exp_full.reindex(columns=result1.columns)
        tm.assert_frame_equal(result1, expected)
        tm.assert_frame_equal(result2, expected)


@pytest.mark.parametrize(
    "func, values",
    [
        ("first", ["second", "first"]),
        ("last", ["fourth", "third"]),
        ("min", ["fourth", "first"]),
        ("max", ["second", "third"]),
    ],
)
def test_preserve_on_ordered_ops(func, values):
    # gh-18502
    # preserve the categoricals on ops
    c = pd.Categorical(["first", "second", "third", "fourth"], ordered=True)
    df = pd.DataFrame({"payload": [-1, -2, -1, -2], "col": c})
    g = df.groupby("payload")
    result = getattr(g, func)()
    expected = pd.DataFrame(
        {"payload": [-2, -1], "col": pd.Series(values, dtype=c.dtype)}
    ).set_index("payload")
    tm.assert_frame_equal(result, expected)


def test_categorical_no_compress():
    data = Series(np.random.randn(9))

    codes = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2])
    cats = Categorical.from_codes(codes, [0, 1, 2], ordered=True)

    result = data.groupby(cats, observed=False).mean()
    exp = data.groupby(codes, observed=False).mean()

    exp.index = CategoricalIndex(
        exp.index, categories=cats.categories, ordered=cats.ordered
    )
    tm.assert_series_equal(result, exp)

    codes = np.array([0, 0, 0, 1, 1, 1, 3, 3, 3])
    cats = Categorical.from_codes(codes, [0, 1, 2, 3], ordered=True)

    result = data.groupby(cats, observed=False).mean()
    exp = data.groupby(codes, observed=False).mean().reindex(cats.categories)
    exp.index = CategoricalIndex(
        exp.index, categories=cats.categories, ordered=cats.ordered
    )
    tm.assert_series_equal(result, exp)

    cats = Categorical(
        ["a", "a", "a", "b", "b", "b", "c", "c", "c"],
        categories=["a", "b", "c", "d"],
        ordered=True,
    )
    data = DataFrame({"a": [1, 1, 1, 2, 2, 2, 3, 4, 5], "b": cats})

    result = data.groupby("b", observed=False).mean()
    result = result["a"].values
    exp = np.array([1, 2, 4, np.nan])
    tm.assert_numpy_array_equal(result, exp)


def test_groupby_empty_with_category():
    # GH-9614
    # test fix for when group by on None resulted in
    # coercion of dtype categorical -> float
    df = pd.DataFrame(
        {"A": [None] * 3, "B": pd.Categorical(["train", "train", "test"])}
    )
    result = df.groupby("A").first()["B"]
    expected = pd.Series(
        pd.Categorical([], categories=["test", "train"]),
        index=pd.Series([], dtype="object", name="A"),
        name="B",
    )
    tm.assert_series_equal(result, expected)


def test_sort():

    # https://stackoverflow.com/questions/23814368/sorting-pandas-
    #        categorical-labels-after-groupby
    # This should result in a properly sorted Series so that the plot
    # has a sorted x axis
    # self.cat.groupby(['value_group'])['value_group'].count().plot(kind='bar')

    df = DataFrame({"value": np.random.randint(0, 10000, 100)})
    labels = [f"{i} - {i+499}" for i in range(0, 10000, 500)]
    cat_labels = Categorical(labels, labels)

    df = df.sort_values(by=["value"], ascending=True)
    df["value_group"] = pd.cut(
        df.value, range(0, 10500, 500), right=False, labels=cat_labels
    )

    res = df.groupby(["value_group"], observed=False)["value_group"].count()
    exp = res[sorted(res.index, key=lambda x: float(x.split()[0]))]
    exp.index = CategoricalIndex(exp.index, name=exp.index.name)
    tm.assert_series_equal(res, exp)


def test_sort2():
    # dataframe groupby sort was being ignored # GH 8868
    df = DataFrame(
        [
            ["(7.5, 10]", 10, 10],
            ["(7.5, 10]", 8, 20],
            ["(2.5, 5]", 5, 30],
            ["(5, 7.5]", 6, 40],
            ["(2.5, 5]", 4, 50],
            ["(0, 2.5]", 1, 60],
            ["(5, 7.5]", 7, 70],
        ],
        columns=["range", "foo", "bar"],
    )
    df["range"] = Categorical(df["range"], ordered=True)
    index = CategoricalIndex(
        ["(0, 2.5]", "(2.5, 5]", "(5, 7.5]", "(7.5, 10]"], name="range", ordered=True
    )
    expected_sort = DataFrame(
        [[1, 60], [5, 30], [6, 40], [10, 10]], columns=["foo", "bar"], index=index
    )

    col = "range"
    result_sort = df.groupby(col, sort=True, observed=False).first()
    tm.assert_frame_equal(result_sort, expected_sort)

    # when categories is ordered, group is ordered by category's order
    expected_sort = result_sort
    result_sort = df.groupby(col, sort=False, observed=False).first()
    tm.assert_frame_equal(result_sort, expected_sort)

    df["range"] = Categorical(df["range"], ordered=False)
    index = CategoricalIndex(
        ["(0, 2.5]", "(2.5, 5]", "(5, 7.5]", "(7.5, 10]"], name="range"
    )
    expected_sort = DataFrame(
        [[1, 60], [5, 30], [6, 40], [10, 10]], columns=["foo", "bar"], index=index
    )

    index = CategoricalIndex(
        ["(7.5, 10]", "(2.5, 5]", "(5, 7.5]", "(0, 2.5]"],
        categories=["(7.5, 10]", "(2.5, 5]", "(5, 7.5]", "(0, 2.5]"],
        name="range",
    )
    expected_nosort = DataFrame(
        [[10, 10], [5, 30], [6, 40], [1, 60]], index=index, columns=["foo", "bar"]
    )

    col = "range"

    # this is an unordered categorical, but we allow this ####
    result_sort = df.groupby(col, sort=True, observed=False).first()
    tm.assert_frame_equal(result_sort, expected_sort)

    result_nosort = df.groupby(col, sort=False, observed=False).first()
    tm.assert_frame_equal(result_nosort, expected_nosort)


def test_sort_datetimelike():
    # GH10505

    # use same data as test_groupby_sort_categorical, which category is
    # corresponding to datetime.month
    df = DataFrame(
        {
            "dt": [
                datetime(2011, 7, 1),
                datetime(2011, 7, 1),
                datetime(2011, 2, 1),
                datetime(2011, 5, 1),
                datetime(2011, 2, 1),
                datetime(2011, 1, 1),
                datetime(2011, 5, 1),
            ],
            "foo": [10, 8, 5, 6, 4, 1, 7],
            "bar": [10, 20, 30, 40, 50, 60, 70],
        },
        columns=["dt", "foo", "bar"],
    )

    # ordered=True
    df["dt"] = Categorical(df["dt"], ordered=True)
    index = [
        datetime(2011, 1, 1),
        datetime(2011, 2, 1),
        datetime(2011, 5, 1),
        datetime(2011, 7, 1),
    ]
    result_sort = DataFrame(
        [[1, 60], [5, 30], [6, 40], [10, 10]], columns=["foo", "bar"]
    )
    result_sort.index = CategoricalIndex(index, name="dt", ordered=True)

    index = [
        datetime(2011, 7, 1),
        datetime(2011, 2, 1),
        datetime(2011, 5, 1),
        datetime(2011, 1, 1),
    ]
    result_nosort = DataFrame(
        [[10, 10], [5, 30], [6, 40], [1, 60]], columns=["foo", "bar"]
    )
    result_nosort.index = CategoricalIndex(
        index, categories=index, name="dt", ordered=True
    )

    col = "dt"
    tm.assert_frame_equal(
        result_sort, df.groupby(col, sort=True, observed=False).first()
    )

    # when categories is ordered, group is ordered by category's order
    tm.assert_frame_equal(
        result_sort, df.groupby(col, sort=False, observed=False).first()
    )

    # ordered = False
    df["dt"] = Categorical(df["dt"], ordered=False)
    index = [
        datetime(2011, 1, 1),
        datetime(2011, 2, 1),
        datetime(2011, 5, 1),
        datetime(2011, 7, 1),
    ]
    result_sort = DataFrame(
        [[1, 60], [5, 30], [6, 40], [10, 10]], columns=["foo", "bar"]
    )
    result_sort.index = CategoricalIndex(index, name="dt")

    index = [
        datetime(2011, 7, 1),
        datetime(2011, 2, 1),
        datetime(2011, 5, 1),
        datetime(2011, 1, 1),
    ]
    result_nosort = DataFrame(
        [[10, 10], [5, 30], [6, 40], [1, 60]], columns=["foo", "bar"]
    )
    result_nosort.index = CategoricalIndex(index, categories=index, name="dt")

    col = "dt"
    tm.assert_frame_equal(
        result_sort, df.groupby(col, sort=True, observed=False).first()
    )
    tm.assert_frame_equal(
        result_nosort, df.groupby(col, sort=False, observed=False).first()
    )


def test_empty_sum():
    # https://github.com/pandas-dev/pandas/issues/18678
    df = DataFrame(
        {"A": Categorical(["a", "a", "b"], categories=["a", "b", "c"]), "B": [1, 2, 1]}
    )
    expected_idx = CategoricalIndex(["a", "b", "c"], name="A")

    # 0 by default
    result = df.groupby("A", observed=False).B.sum()
    expected = Series([3, 1, 0], expected_idx, name="B")
    tm.assert_series_equal(result, expected)

    # min_count=0
    result = df.groupby("A", observed=False).B.sum(min_count=0)
    expected = Series([3, 1, 0], expected_idx, name="B")
    tm.assert_series_equal(result, expected)

    # min_count=1
    result = df.groupby("A", observed=False).B.sum(min_count=1)
    expected = Series([3, 1, np.nan], expected_idx, name="B")
    tm.assert_series_equal(result, expected)

    # min_count>1
    result = df.groupby("A", observed=False).B.sum(min_count=2)
    expected = Series([3, np.nan, np.nan], expected_idx, name="B")
    tm.assert_series_equal(result, expected)


def test_empty_prod():
    # https://github.com/pandas-dev/pandas/issues/18678
    df = DataFrame(
        {"A": Categorical(["a", "a", "b"], categories=["a", "b", "c"]), "B": [1, 2, 1]}
    )

    expected_idx = CategoricalIndex(["a", "b", "c"], name="A")

    # 1 by default
    result = df.groupby("A", observed=False).B.prod()
    expected = Series([2, 1, 1], expected_idx, name="B")
    tm.assert_series_equal(result, expected)

    # min_count=0
    result = df.groupby("A", observed=False).B.prod(min_count=0)
    expected = Series([2, 1, 1], expected_idx, name="B")
    tm.assert_series_equal(result, expected)

    # min_count=1
    result = df.groupby("A", observed=False).B.prod(min_count=1)
    expected = Series([2, 1, np.nan], expected_idx, name="B")
    tm.assert_series_equal(result, expected)


def test_groupby_multiindex_categorical_datetime():
    # https://github.com/pandas-dev/pandas/issues/21390

    df = DataFrame(
        {
            "key1": Categorical(list("abcbabcba")),
            "key2": Categorical(
                list(pd.date_range("2018-06-01 00", freq="1T", periods=3)) * 3
            ),
            "values": np.arange(9),
        }
    )
    result = df.groupby(["key1", "key2"]).mean()

    idx = MultiIndex.from_product(
        [
            Categorical(["a", "b", "c"]),
            Categorical(pd.date_range("2018-06-01 00", freq="1T", periods=3)),
        ],
        names=["key1", "key2"],
    )
    expected = DataFrame({"values": [0, 4, 8, 3, 4, 5, 6, np.nan, 2]}, index=idx)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "as_index, expected",
    [
        (
            True,
            Series(
                index=MultiIndex.from_arrays(
                    [Series([1, 1, 2], dtype="category"), [1, 2, 2]], names=["a", "b"]
                ),
                data=[1, 2, 3],
                name="x",
            ),
        ),
        (
            False,
            DataFrame(
                {
                    "a": Series([1, 1, 2], dtype="category"),
                    "b": [1, 2, 2],
                    "x": [1, 2, 3],
                }
            ),
        ),
    ],
)
def test_groupby_agg_observed_true_single_column(as_index, expected):
    # GH-23970
    df = DataFrame(
        {"a": Series([1, 1, 2], dtype="category"), "b": [1, 2, 2], "x": [1, 2, 3]}
    )

    result = df.groupby(["a", "b"], as_index=as_index, observed=True)["x"].sum()

    tm.assert_equal(result, expected)


@pytest.mark.parametrize("fill_value", [None, np.nan, pd.NaT])
def test_shift(fill_value):
    ct = Categorical(
        ["a", "b", "c", "d"], categories=["a", "b", "c", "d"], ordered=False
    )
    expected = Categorical(
        [None, "a", "b", "c"], categories=["a", "b", "c", "d"], ordered=False
    )
    res = ct.shift(1, fill_value=fill_value)
    tm.assert_equal(res, expected)


@pytest.fixture
def df_cat(df):
    """
    DataFrame with multiple categorical columns and a column of integers.
    Shortened so as not to contain all possible combinations of categories.
    Useful for testing `observed` kwarg functionality on GroupBy objects.

    Parameters
    ----------
    df: DataFrame
        Non-categorical, longer DataFrame from another fixture, used to derive
        this one

    Returns
    -------
    df_cat: DataFrame
    """
    df_cat = df.copy()[:4]  # leave out some groups
    df_cat["A"] = df_cat["A"].astype("category")
    df_cat["B"] = df_cat["B"].astype("category")
    df_cat["C"] = Series([1, 2, 3, 4])
    df_cat = df_cat.drop(["D"], axis=1)
    return df_cat


@pytest.mark.parametrize(
    "operation, kwargs", [("agg", dict(dtype="category")), ("apply", dict())]
)
def test_seriesgroupby_observed_true(df_cat, operation, kwargs):
    # GH 24880
    index = MultiIndex.from_frame(
        DataFrame(
            {"A": ["foo", "foo", "bar", "bar"], "B": ["one", "two", "one", "three"]},
            **kwargs,
        )
    )
    expected = Series(data=[1, 3, 2, 4], index=index, name="C")
    grouped = df_cat.groupby(["A", "B"], observed=True)["C"]
    result = getattr(grouped, operation)(sum)
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("operation", ["agg", "apply"])
@pytest.mark.parametrize("observed", [False, None])
def test_seriesgroupby_observed_false_or_none(df_cat, observed, operation):
    # GH 24880
    index, _ = MultiIndex.from_product(
        [
            CategoricalIndex(["bar", "foo"], ordered=False),
            CategoricalIndex(["one", "three", "two"], ordered=False),
        ],
        names=["A", "B"],
    ).sortlevel()

    expected = Series(data=[2, 4, np.nan, 1, np.nan, 3], index=index, name="C")
    grouped = df_cat.groupby(["A", "B"], observed=observed)["C"]
    result = getattr(grouped, operation)(sum)
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    "observed, index, data",
    [
        (
            True,
            MultiIndex.from_tuples(
                [
                    ("foo", "one", "min"),
                    ("foo", "one", "max"),
                    ("foo", "two", "min"),
                    ("foo", "two", "max"),
                    ("bar", "one", "min"),
                    ("bar", "one", "max"),
                    ("bar", "three", "min"),
                    ("bar", "three", "max"),
                ],
                names=["A", "B", None],
            ),
            [1, 1, 3, 3, 2, 2, 4, 4],
        ),
        (
            False,
            MultiIndex.from_product(
                [
                    CategoricalIndex(["bar", "foo"], ordered=False),
                    CategoricalIndex(["one", "three", "two"], ordered=False),
                    Index(["min", "max"]),
                ],
                names=["A", "B", None],
            ),
            [2, 2, 4, 4, np.nan, np.nan, 1, 1, np.nan, np.nan, 3, 3],
        ),
        (
            None,
            MultiIndex.from_product(
                [
                    CategoricalIndex(["bar", "foo"], ordered=False),
                    CategoricalIndex(["one", "three", "two"], ordered=False),
                    Index(["min", "max"]),
                ],
                names=["A", "B", None],
            ),
            [2, 2, 4, 4, np.nan, np.nan, 1, 1, np.nan, np.nan, 3, 3],
        ),
    ],
)
def test_seriesgroupby_observed_apply_dict(df_cat, observed, index, data):
    # GH 24880
    expected = Series(data=data, index=index, name="C")
    result = df_cat.groupby(["A", "B"], observed=observed)["C"].apply(
        lambda x: {"min": x.min(), "max": x.max()}
    )
    tm.assert_series_equal(result, expected)


def test_groupby_categorical_series_dataframe_consistent(df_cat):
    # GH 20416
    expected = df_cat.groupby(["A", "B"])["C"].mean()
    result = df_cat.groupby(["A", "B"]).mean()["C"]
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize("code", [([1, 0, 0]), ([0, 0, 0])])
def test_groupby_categorical_axis_1(code):
    # GH 13420
    df = DataFrame({"a": [1, 2, 3, 4], "b": [-1, -2, -3, -4], "c": [5, 6, 7, 8]})
    cat = pd.Categorical.from_codes(code, categories=list("abc"))
    result = df.groupby(cat, axis=1).mean()
    expected = df.T.groupby(cat, axis=0).mean().T
    tm.assert_frame_equal(result, expected)


def test_groupby_cat_preserves_structure(observed, ordered):
    # GH 28787
    df = DataFrame(
        {"Name": Categorical(["Bob", "Greg"], ordered=ordered), "Item": [1, 2]},
        columns=["Name", "Item"],
    )
    expected = df.copy()

    result = (
        df.groupby("Name", observed=observed)
        .agg(pd.DataFrame.sum, skipna=True)
        .reset_index()
    )

    tm.assert_frame_equal(result, expected)


def test_get_nonexistent_category():
    # Accessing a Category that is not in the dataframe
    df = pd.DataFrame({"var": ["a", "a", "b", "b"], "val": range(4)})
    with pytest.raises(KeyError, match="'vau'"):
        df.groupby("var").apply(
            lambda rows: pd.DataFrame(
                {"var": [rows.iloc[-1]["var"]], "val": [rows.iloc[-1]["vau"]]}
            )
        )


def test_series_groupby_on_2_categoricals_unobserved(
    reduction_func: str, observed: bool
):
    # GH 17605

    if reduction_func == "ngroup":
        pytest.skip("ngroup is not truly a reduction")

    if reduction_func == "corrwith":  # GH 32293
        pytest.xfail("TODO: implemented SeriesGroupBy.corrwith")

    df = pd.DataFrame(
        {
            "cat_1": pd.Categorical(list("AABB"), categories=list("ABCD")),
            "cat_2": pd.Categorical(list("AB") * 2, categories=list("ABCD")),
            "value": [0.1] * 4,
        }
    )
    args = {"nth": [0]}.get(reduction_func, [])

    expected_length = 4 if observed else 16

    series_groupby = df.groupby(["cat_1", "cat_2"], observed=observed)["value"]
    agg = getattr(series_groupby, reduction_func)
    result = agg(*args)

    assert len(result) == expected_length


@pytest.mark.parametrize(
    "func, zero_or_nan",
    [
        ("all", np.NaN),
        ("any", np.NaN),
        ("count", 0),
        ("first", np.NaN),
        ("idxmax", np.NaN),
        ("idxmin", np.NaN),
        ("last", np.NaN),
        ("mad", np.NaN),
        ("max", np.NaN),
        ("mean", np.NaN),
        ("median", np.NaN),
        ("min", np.NaN),
        ("nth", np.NaN),
        ("nunique", 0),
        ("prod", np.NaN),
        ("quantile", np.NaN),
        ("sem", np.NaN),
        ("size", 0),
        ("skew", np.NaN),
        ("std", np.NaN),
        ("sum", np.NaN),
        ("var", np.NaN),
    ],
)
def test_series_groupby_on_2_categoricals_unobserved_zeroes_or_nans(func, zero_or_nan):
    # GH 17605
    # Tests whether the unobserved categories in the result contain 0 or NaN
    df = pd.DataFrame(
        {
            "cat_1": pd.Categorical(list("AABB"), categories=list("ABC")),
            "cat_2": pd.Categorical(list("AB") * 2, categories=list("ABC")),
            "value": [0.1] * 4,
        }
    )
    unobserved = [tuple("AC"), tuple("BC"), tuple("CA"), tuple("CB"), tuple("CC")]
    args = {"nth": [0]}.get(func, [])

    series_groupby = df.groupby(["cat_1", "cat_2"], observed=False)["value"]
    agg = getattr(series_groupby, func)
    result = agg(*args)

    for idx in unobserved:
        val = result.loc[idx]
        assert (pd.isna(zero_or_nan) and pd.isna(val)) or (val == zero_or_nan)

    # If we expect unobserved values to be zero, we also expect the dtype to be int
    if zero_or_nan == 0:
        assert np.issubdtype(result.dtype, np.integer)


def test_series_groupby_categorical_aggregation_getitem():
    # GH 8870
    d = {"foo": [10, 8, 4, 1], "bar": [10, 20, 30, 40], "baz": ["d", "c", "d", "c"]}
    df = pd.DataFrame(d)
    cat = pd.cut(df["foo"], np.linspace(0, 20, 5))
    df["range"] = cat
    groups = df.groupby(["range", "baz"], as_index=True, sort=True)
    result = groups["foo"].agg("mean")
    expected = groups.agg("mean")["foo"]
    tm.assert_series_equal(result, expected)


@pytest.mark.parametrize(
    "func, expected_values",
    [(pd.Series.nunique, [1, 1, 2]), (pd.Series.count, [1, 2, 2])],
)
def test_groupby_agg_categorical_columns(func, expected_values):
    # 31256
    df = pd.DataFrame(
        {
            "id": [0, 1, 2, 3, 4],
            "groups": [0, 1, 1, 2, 2],
            "value": pd.Categorical([0, 0, 0, 0, 1]),
        }
    ).set_index("id")
    result = df.groupby("groups").agg(func)

    expected = pd.DataFrame(
        {"value": expected_values}, index=pd.Index([0, 1, 2], name="groups"),
    )
    tm.assert_frame_equal(result, expected)


def test_groupby_agg_non_numeric():
    df = pd.DataFrame(
        {"A": pd.Categorical(["a", "a", "b"], categories=["a", "b", "c"])}
    )
    expected = pd.DataFrame({"A": [2, 1]}, index=[1, 2])

    result = df.groupby([1, 2, 1]).agg(pd.Series.nunique)
    tm.assert_frame_equal(result, expected)

    result = df.groupby([1, 2, 1]).nunique()
    tm.assert_frame_equal(result, expected)


def test_read_only_category_no_sort():
    # GH33410
    cats = np.array([1, 2])
    cats.flags.writeable = False
    df = DataFrame(
        {"a": [1, 3, 5, 7], "b": Categorical([1, 1, 2, 2], categories=Index(cats))}
    )
    expected = DataFrame(data={"a": [2, 6]}, index=CategoricalIndex([1, 2], name="b"))
    result = df.groupby("b", sort=False).mean()
    tm.assert_frame_equal(result, expected)
