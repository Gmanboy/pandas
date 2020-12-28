from copy import deepcopy
import inspect
import pydoc

import numpy as np
import pytest

import pandas.util._test_decorators as td
from pandas.util._test_decorators import async_mark, skip_if_no

import pandas as pd
from pandas import DataFrame, Series, date_range, timedelta_range
import pandas._testing as tm


class TestDataFrameMisc:
    def test_getitem_pop_assign_name(self, float_frame):
        s = float_frame["A"]
        assert s.name == "A"

        s = float_frame.pop("A")
        assert s.name == "A"

        s = float_frame.loc[:, "B"]
        assert s.name == "B"

        s2 = s.loc[:]
        assert s2.name == "B"

    def test_get_axis(self, float_frame):
        f = float_frame
        assert f._get_axis_number(0) == 0
        assert f._get_axis_number(1) == 1
        assert f._get_axis_number("index") == 0
        assert f._get_axis_number("rows") == 0
        assert f._get_axis_number("columns") == 1

        assert f._get_axis_name(0) == "index"
        assert f._get_axis_name(1) == "columns"
        assert f._get_axis_name("index") == "index"
        assert f._get_axis_name("rows") == "index"
        assert f._get_axis_name("columns") == "columns"

        assert f._get_axis(0) is f.index
        assert f._get_axis(1) is f.columns

        with pytest.raises(ValueError, match="No axis named"):
            f._get_axis_number(2)

        with pytest.raises(ValueError, match="No axis.*foo"):
            f._get_axis_name("foo")

        with pytest.raises(ValueError, match="No axis.*None"):
            f._get_axis_name(None)

        with pytest.raises(ValueError, match="No axis named"):
            f._get_axis_number(None)

    def test_column_contains_raises(self, float_frame):
        with pytest.raises(TypeError, match="unhashable type: 'Index'"):
            float_frame.columns in float_frame

    def test_tab_completion(self):
        # DataFrame whose columns are identifiers shall have them in __dir__.
        df = DataFrame([list("abcd"), list("efgh")], columns=list("ABCD"))
        for key in list("ABCD"):
            assert key in dir(df)
        assert isinstance(df.__getitem__("A"), pd.Series)

        # DataFrame whose first-level columns are identifiers shall have
        # them in __dir__.
        df = DataFrame(
            [list("abcd"), list("efgh")],
            columns=pd.MultiIndex.from_tuples(list(zip("ABCD", "EFGH"))),
        )
        for key in list("ABCD"):
            assert key in dir(df)
        for key in list("EFGH"):
            assert key not in dir(df)
        assert isinstance(df.__getitem__("A"), pd.DataFrame)

    def test_not_hashable(self):
        empty_frame = DataFrame()

        df = DataFrame([1])
        msg = "'DataFrame' objects are mutable, thus they cannot be hashed"
        with pytest.raises(TypeError, match=msg):
            hash(df)
        with pytest.raises(TypeError, match=msg):
            hash(empty_frame)

    def test_column_name_contains_unicode_surrogate(self):
        # GH 25509
        colname = "\ud83d"
        df = DataFrame({colname: []})
        # this should not crash
        assert colname not in dir(df)
        assert df.columns[0] == colname

    def test_new_empty_index(self):
        df1 = DataFrame(np.random.randn(0, 3))
        df2 = DataFrame(np.random.randn(0, 3))
        df1.index.name = "foo"
        assert df2.index.name is None

    def test_get_agg_axis(self, float_frame):
        cols = float_frame._get_agg_axis(0)
        assert cols is float_frame.columns

        idx = float_frame._get_agg_axis(1)
        assert idx is float_frame.index

        msg = r"Axis must be 0 or 1 \(got 2\)"
        with pytest.raises(ValueError, match=msg):
            float_frame._get_agg_axis(2)

    def test_empty(self, float_frame, float_string_frame):
        empty_frame = DataFrame()
        assert empty_frame.empty

        assert not float_frame.empty
        assert not float_string_frame.empty

        # corner case
        df = DataFrame({"A": [1.0, 2.0, 3.0], "B": ["a", "b", "c"]}, index=np.arange(3))
        del df["A"]
        assert not df.empty

    def test_len(self, float_frame):
        assert len(float_frame) == len(float_frame.index)

        # single block corner case
        arr = float_frame[["A", "B"]].values
        expected = float_frame.reindex(columns=["A", "B"]).values
        tm.assert_almost_equal(arr, expected)

    def test_axis_aliases(self, float_frame):
        f = float_frame

        # reg name
        expected = f.sum(axis=0)
        result = f.sum(axis="index")
        tm.assert_series_equal(result, expected)

        expected = f.sum(axis=1)
        result = f.sum(axis="columns")
        tm.assert_series_equal(result, expected)

    def test_class_axis(self):
        # GH 18147
        # no exception and no empty docstring
        assert pydoc.getdoc(DataFrame.index)
        assert pydoc.getdoc(DataFrame.columns)

    def test_series_put_names(self, float_string_frame):
        series = float_string_frame._series
        for k, v in series.items():
            assert v.name == k

    def test_empty_nonzero(self):
        df = DataFrame([1, 2, 3])
        assert not df.empty
        df = DataFrame(index=[1], columns=[1])
        assert not df.empty
        df = DataFrame(index=["a", "b"], columns=["c", "d"]).dropna()
        assert df.empty
        assert df.T.empty
        empty_frames = [
            DataFrame(),
            DataFrame(index=[1]),
            DataFrame(columns=[1]),
            DataFrame({1: []}),
        ]
        for df in empty_frames:
            assert df.empty
            assert df.T.empty

    def test_with_datetimelikes(self):

        df = DataFrame(
            {
                "A": date_range("20130101", periods=10),
                "B": timedelta_range("1 day", periods=10),
            }
        )
        t = df.T

        result = t.dtypes.value_counts()
        expected = Series({np.dtype("object"): 10})
        tm.assert_series_equal(result, expected)

    def test_deepcopy(self, float_frame):
        cp = deepcopy(float_frame)
        series = cp["A"]
        series[:] = 10
        for idx, value in series.items():
            assert float_frame["A"][idx] != value

    def test_inplace_return_self(self):
        # GH 1893

        data = DataFrame(
            {"a": ["foo", "bar", "baz", "qux"], "b": [0, 0, 1, 1], "c": [1, 2, 3, 4]}
        )

        def _check_f(base, f):
            result = f(base)
            assert result is None

        # -----DataFrame-----

        # set_index
        f = lambda x: x.set_index("a", inplace=True)
        _check_f(data.copy(), f)

        # reset_index
        f = lambda x: x.reset_index(inplace=True)
        _check_f(data.set_index("a"), f)

        # drop_duplicates
        f = lambda x: x.drop_duplicates(inplace=True)
        _check_f(data.copy(), f)

        # sort
        f = lambda x: x.sort_values("b", inplace=True)
        _check_f(data.copy(), f)

        # sort_index
        f = lambda x: x.sort_index(inplace=True)
        _check_f(data.copy(), f)

        # fillna
        f = lambda x: x.fillna(0, inplace=True)
        _check_f(data.copy(), f)

        # replace
        f = lambda x: x.replace(1, 0, inplace=True)
        _check_f(data.copy(), f)

        # rename
        f = lambda x: x.rename({1: "foo"}, inplace=True)
        _check_f(data.copy(), f)

        # -----Series-----
        d = data.copy()["c"]

        # reset_index
        f = lambda x: x.reset_index(inplace=True, drop=True)
        _check_f(data.set_index("a")["c"], f)

        # fillna
        f = lambda x: x.fillna(0, inplace=True)
        _check_f(d.copy(), f)

        # replace
        f = lambda x: x.replace(1, 0, inplace=True)
        _check_f(d.copy(), f)

        # rename
        f = lambda x: x.rename({1: "foo"}, inplace=True)
        _check_f(d.copy(), f)

    @async_mark()
    @td.check_file_leaks
    async def test_tab_complete_warning(self, ip, frame_or_series):
        # GH 16409
        pytest.importorskip("IPython", minversion="6.0.0")
        from IPython.core.completer import provisionalcompleter

        if frame_or_series is DataFrame:
            code = "from pandas import DataFrame; obj = DataFrame()"
        else:
            code = "from pandas import Series; obj = Series(dtype=object)"

        await ip.run_code(code)

        # TODO: remove it when Ipython updates
        # GH 33567, jedi version raises Deprecation warning in Ipython
        import jedi

        if jedi.__version__ < "0.17.0":
            warning = tm.assert_produces_warning(None)
        else:
            warning = tm.assert_produces_warning(
                DeprecationWarning, check_stacklevel=False
            )
        with warning:
            with provisionalcompleter("ignore"):
                list(ip.Completer.completions("obj.", 1))

    def test_attrs(self):
        df = DataFrame({"A": [2, 3]})
        assert df.attrs == {}
        df.attrs["version"] = 1

        result = df.rename(columns=str)
        assert result.attrs == {"version": 1}

    @pytest.mark.parametrize("allows_duplicate_labels", [True, False, None])
    def test_set_flags(self, allows_duplicate_labels, frame_or_series):
        obj = DataFrame({"A": [1, 2]})
        key = (0, 0)
        if frame_or_series is Series:
            obj = obj["A"]
            key = 0

        result = obj.set_flags(allows_duplicate_labels=allows_duplicate_labels)

        if allows_duplicate_labels is None:
            # We don't update when it's not provided
            assert result.flags.allows_duplicate_labels is True
        else:
            assert result.flags.allows_duplicate_labels is allows_duplicate_labels

        # We made a copy
        assert obj is not result

        # We didn't mutate obj
        assert obj.flags.allows_duplicate_labels is True

        # But we didn't copy data
        result.iloc[key] = 0
        assert obj.iloc[key] == 0

        # Now we do copy.
        result = obj.set_flags(
            copy=True, allows_duplicate_labels=allows_duplicate_labels
        )
        result.iloc[key] = 10
        assert obj.iloc[key] == 0

    def test_constructor_expanddim_lookup(self):
        # GH#33628 accessing _constructor_expanddim should not
        #  raise NotImplementedError
        df = DataFrame()

        with pytest.raises(NotImplementedError, match="Not supported for DataFrames!"):
            df._constructor_expanddim(np.arange(27).reshape(3, 3, 3))

    @skip_if_no("jinja2")
    def test_inspect_getmembers(self):
        # GH38740
        df = DataFrame()
        with tm.assert_produces_warning(None):
            inspect.getmembers(df)
