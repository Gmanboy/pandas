from datetime import date, datetime, timedelta
from functools import partial
from io import BytesIO
import os

import numpy as np
from numpy import nan
import pytest

from pandas.compat import PY36
import pandas.util._test_decorators as td

import pandas as pd
from pandas import DataFrame, Index, MultiIndex, get_option, set_option
import pandas.util.testing as tm
from pandas.util.testing import ensure_clean, makeCustomDataframe as mkdf

from pandas.io.excel import (
    ExcelFile,
    ExcelWriter,
    _OpenpyxlWriter,
    _XlsxWriter,
    _XlwtWriter,
    register_writer,
)


@td.skip_if_no("xlrd")
@pytest.mark.parametrize("ext", [".xls", ".xlsx", ".xlsm"])
class TestRoundTrip:
    @td.skip_if_no("xlwt")
    @td.skip_if_no("openpyxl")
    @pytest.mark.parametrize(
        "header,expected",
        [(None, DataFrame([np.nan] * 4)), (0, DataFrame({"Unnamed: 0": [np.nan] * 3}))],
    )
    def test_read_one_empty_col_no_header(self, ext, header, expected):
        # xref gh-12292
        filename = "no_header"
        df = pd.DataFrame([["", 1, 100], ["", 2, 200], ["", 3, 300], ["", 4, 400]])

        with ensure_clean(ext) as path:
            df.to_excel(path, filename, index=False, header=False)
            result = pd.read_excel(path, filename, usecols=[0], header=header)

        tm.assert_frame_equal(result, expected)

    @td.skip_if_no("xlwt")
    @td.skip_if_no("openpyxl")
    @pytest.mark.parametrize(
        "header,expected",
        [(None, DataFrame([0] + [np.nan] * 4)), (0, DataFrame([np.nan] * 4))],
    )
    def test_read_one_empty_col_with_header(self, ext, header, expected):
        filename = "with_header"
        df = pd.DataFrame([["", 1, 100], ["", 2, 200], ["", 3, 300], ["", 4, 400]])

        with ensure_clean(ext) as path:
            df.to_excel(path, "with_header", index=False, header=True)
            result = pd.read_excel(path, filename, usecols=[0], header=header)

        tm.assert_frame_equal(result, expected)

    @td.skip_if_no("openpyxl")
    @td.skip_if_no("xlwt")
    def test_set_column_names_in_parameter(self, ext):
        # GH 12870 : pass down column names associated with
        # keyword argument names
        refdf = pd.DataFrame([[1, "foo"], [2, "bar"], [3, "baz"]], columns=["a", "b"])

        with ensure_clean(ext) as pth:
            with ExcelWriter(pth) as writer:
                refdf.to_excel(writer, "Data_no_head", header=False, index=False)
                refdf.to_excel(writer, "Data_with_head", index=False)

            refdf.columns = ["A", "B"]

            with ExcelFile(pth) as reader:
                xlsdf_no_head = pd.read_excel(
                    reader, "Data_no_head", header=None, names=["A", "B"]
                )
                xlsdf_with_head = pd.read_excel(
                    reader, "Data_with_head", index_col=None, names=["A", "B"]
                )

            tm.assert_frame_equal(xlsdf_no_head, refdf)
            tm.assert_frame_equal(xlsdf_with_head, refdf)

    @td.skip_if_no("xlwt")
    @td.skip_if_no("openpyxl")
    def test_creating_and_reading_multiple_sheets(self, ext):
        # see gh-9450
        #
        # Test reading multiple sheets, from a runtime
        # created Excel file with multiple sheets.
        def tdf(col_sheet_name):
            d, i = [11, 22, 33], [1, 2, 3]
            return DataFrame(d, i, columns=[col_sheet_name])

        sheets = ["AAA", "BBB", "CCC"]

        dfs = [tdf(s) for s in sheets]
        dfs = dict(zip(sheets, dfs))

        with ensure_clean(ext) as pth:
            with ExcelWriter(pth) as ew:
                for sheetname, df in dfs.items():
                    df.to_excel(ew, sheetname)

            dfs_returned = pd.read_excel(pth, sheet_name=sheets, index_col=0)

            for s in sheets:
                tm.assert_frame_equal(dfs[s], dfs_returned[s])

    @td.skip_if_no("xlsxwriter")
    def test_read_excel_multiindex_empty_level(self, ext):
        # see gh-12453
        with ensure_clean(ext) as path:
            df = DataFrame(
                {
                    ("One", "x"): {0: 1},
                    ("Two", "X"): {0: 3},
                    ("Two", "Y"): {0: 7},
                    ("Zero", ""): {0: 0},
                }
            )

            expected = DataFrame(
                {
                    ("One", "x"): {0: 1},
                    ("Two", "X"): {0: 3},
                    ("Two", "Y"): {0: 7},
                    ("Zero", "Unnamed: 4_level_1"): {0: 0},
                }
            )

            df.to_excel(path)
            actual = pd.read_excel(path, header=[0, 1], index_col=0)
            tm.assert_frame_equal(actual, expected)

            df = pd.DataFrame(
                {
                    ("Beg", ""): {0: 0},
                    ("Middle", "x"): {0: 1},
                    ("Tail", "X"): {0: 3},
                    ("Tail", "Y"): {0: 7},
                }
            )

            expected = pd.DataFrame(
                {
                    ("Beg", "Unnamed: 1_level_1"): {0: 0},
                    ("Middle", "x"): {0: 1},
                    ("Tail", "X"): {0: 3},
                    ("Tail", "Y"): {0: 7},
                }
            )

            df.to_excel(path)
            actual = pd.read_excel(path, header=[0, 1], index_col=0)
            tm.assert_frame_equal(actual, expected)

    @td.skip_if_no("xlsxwriter")
    @pytest.mark.parametrize("c_idx_names", [True, False])
    @pytest.mark.parametrize("r_idx_names", [True, False])
    @pytest.mark.parametrize("c_idx_levels", [1, 3])
    @pytest.mark.parametrize("r_idx_levels", [1, 3])
    def test_excel_multindex_roundtrip(
        self, ext, c_idx_names, r_idx_names, c_idx_levels, r_idx_levels
    ):
        # see gh-4679
        with ensure_clean(ext) as pth:
            if c_idx_levels == 1 and c_idx_names:
                pytest.skip(
                    "Column index name cannot be serialized unless it's a MultiIndex"
                )

            # Empty name case current read in as
            # unnamed levels, not Nones.
            check_names = r_idx_names or r_idx_levels <= 1

            df = mkdf(5, 5, c_idx_names, r_idx_names, c_idx_levels, r_idx_levels)
            df.to_excel(pth)

            act = pd.read_excel(
                pth,
                index_col=list(range(r_idx_levels)),
                header=list(range(c_idx_levels)),
            )
            tm.assert_frame_equal(df, act, check_names=check_names)

            df.iloc[0, :] = np.nan
            df.to_excel(pth)

            act = pd.read_excel(
                pth,
                index_col=list(range(r_idx_levels)),
                header=list(range(c_idx_levels)),
            )
            tm.assert_frame_equal(df, act, check_names=check_names)

            df.iloc[-1, :] = np.nan
            df.to_excel(pth)
            act = pd.read_excel(
                pth,
                index_col=list(range(r_idx_levels)),
                header=list(range(c_idx_levels)),
            )
            tm.assert_frame_equal(df, act, check_names=check_names)

    @td.skip_if_no("xlwt")
    @td.skip_if_no("openpyxl")
    def test_read_excel_parse_dates(self, ext):
        # see gh-11544, gh-12051
        df = DataFrame(
            {"col": [1, 2, 3], "date_strings": pd.date_range("2012-01-01", periods=3)}
        )
        df2 = df.copy()
        df2["date_strings"] = df2["date_strings"].dt.strftime("%m/%d/%Y")

        with ensure_clean(ext) as pth:
            df2.to_excel(pth)

            res = pd.read_excel(pth, index_col=0)
            tm.assert_frame_equal(df2, res)

            res = pd.read_excel(pth, parse_dates=["date_strings"], index_col=0)
            tm.assert_frame_equal(df, res)

            date_parser = lambda x: pd.datetime.strptime(x, "%m/%d/%Y")
            res = pd.read_excel(
                pth, parse_dates=["date_strings"], date_parser=date_parser, index_col=0
            )
            tm.assert_frame_equal(df, res)


class _WriterBase:
    @pytest.fixture(autouse=True)
    def set_engine_and_path(self, engine, ext):
        """Fixture to set engine and open file for use in each test case

        Rather than requiring `engine=...` to be provided explicitly as an
        argument in each test, this fixture sets a global option to dictate
        which engine should be used to write Excel files. After executing
        the test it rolls back said change to the global option.

        It also uses a context manager to open a temporary excel file for
        the function to write to, accessible via `self.path`

        Notes
        -----
        This fixture will run as part of each test method defined in the
        class and any subclasses, on account of the `autouse=True`
        argument
        """
        option_name = "io.excel.{ext}.writer".format(ext=ext.strip("."))
        prev_engine = get_option(option_name)
        set_option(option_name, engine)
        with ensure_clean(ext) as path:
            self.path = path
            yield
        set_option(option_name, prev_engine)  # Roll back option change


@td.skip_if_no("xlrd")
@pytest.mark.parametrize(
    "engine,ext",
    [
        pytest.param("openpyxl", ".xlsx", marks=td.skip_if_no("openpyxl")),
        pytest.param("openpyxl", ".xlsm", marks=td.skip_if_no("openpyxl")),
        pytest.param("xlwt", ".xls", marks=td.skip_if_no("xlwt")),
        pytest.param("xlsxwriter", ".xlsx", marks=td.skip_if_no("xlsxwriter")),
    ],
)
class TestExcelWriter(_WriterBase):
    # Base class for test cases to run with different Excel writers.

    def test_excel_sheet_size(self, engine, ext):

        # GH 26080
        breaking_row_count = 2 ** 20 + 1
        breaking_col_count = 2 ** 14 + 1
        # purposely using two arrays to prevent memory issues while testing
        row_arr = np.zeros(shape=(breaking_row_count, 1))
        col_arr = np.zeros(shape=(1, breaking_col_count))
        row_df = pd.DataFrame(row_arr)
        col_df = pd.DataFrame(col_arr)

        msg = "sheet is too large"
        with pytest.raises(ValueError, match=msg):
            row_df.to_excel(self.path)

        with pytest.raises(ValueError, match=msg):
            col_df.to_excel(self.path)

    def test_excel_sheet_by_name_raise(self, engine, ext):
        import xlrd

        gt = DataFrame(np.random.randn(10, 2))
        gt.to_excel(self.path)

        xl = ExcelFile(self.path)
        df = pd.read_excel(xl, 0, index_col=0)

        tm.assert_frame_equal(gt, df)

        with pytest.raises(xlrd.XLRDError):
            pd.read_excel(xl, "0")

    def test_excel_writer_context_manager(self, frame, engine, ext):
        with ExcelWriter(self.path) as writer:
            frame.to_excel(writer, "Data1")
            frame2 = frame.copy()
            frame2.columns = frame.columns[::-1]
            frame2.to_excel(writer, "Data2")

        with ExcelFile(self.path) as reader:
            found_df = pd.read_excel(reader, "Data1", index_col=0)
            found_df2 = pd.read_excel(reader, "Data2", index_col=0)

            tm.assert_frame_equal(found_df, frame)
            tm.assert_frame_equal(found_df2, frame2)

    def test_roundtrip(self, engine, ext, frame):
        frame = frame.copy()
        frame["A"][:5] = nan

        frame.to_excel(self.path, "test1")
        frame.to_excel(self.path, "test1", columns=["A", "B"])
        frame.to_excel(self.path, "test1", header=False)
        frame.to_excel(self.path, "test1", index=False)

        # test roundtrip
        frame.to_excel(self.path, "test1")
        recons = pd.read_excel(self.path, "test1", index_col=0)
        tm.assert_frame_equal(frame, recons)

        frame.to_excel(self.path, "test1", index=False)
        recons = pd.read_excel(self.path, "test1", index_col=None)
        recons.index = frame.index
        tm.assert_frame_equal(frame, recons)

        frame.to_excel(self.path, "test1", na_rep="NA")
        recons = pd.read_excel(self.path, "test1", index_col=0, na_values=["NA"])
        tm.assert_frame_equal(frame, recons)

        # GH 3611
        frame.to_excel(self.path, "test1", na_rep="88")
        recons = pd.read_excel(self.path, "test1", index_col=0, na_values=["88"])
        tm.assert_frame_equal(frame, recons)

        frame.to_excel(self.path, "test1", na_rep="88")
        recons = pd.read_excel(self.path, "test1", index_col=0, na_values=[88, 88.0])
        tm.assert_frame_equal(frame, recons)

        # GH 6573
        frame.to_excel(self.path, "Sheet1")
        recons = pd.read_excel(self.path, index_col=0)
        tm.assert_frame_equal(frame, recons)

        frame.to_excel(self.path, "0")
        recons = pd.read_excel(self.path, index_col=0)
        tm.assert_frame_equal(frame, recons)

        # GH 8825 Pandas Series should provide to_excel method
        s = frame["A"]
        s.to_excel(self.path)
        recons = pd.read_excel(self.path, index_col=0)
        tm.assert_frame_equal(s.to_frame(), recons)

    def test_mixed(self, engine, ext, frame):
        mixed_frame = frame.copy()
        mixed_frame["foo"] = "bar"

        mixed_frame.to_excel(self.path, "test1")
        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=0)
        tm.assert_frame_equal(mixed_frame, recons)

    def test_ts_frame(self, tsframe, engine, ext):
        df = tsframe

        df.to_excel(self.path, "test1")
        reader = ExcelFile(self.path)

        recons = pd.read_excel(reader, "test1", index_col=0)
        tm.assert_frame_equal(df, recons)

    def test_basics_with_nan(self, engine, ext, frame):
        frame = frame.copy()
        frame["A"][:5] = nan
        frame.to_excel(self.path, "test1")
        frame.to_excel(self.path, "test1", columns=["A", "B"])
        frame.to_excel(self.path, "test1", header=False)
        frame.to_excel(self.path, "test1", index=False)

    @pytest.mark.parametrize("np_type", [np.int8, np.int16, np.int32, np.int64])
    def test_int_types(self, engine, ext, np_type):
        # Test np.int values read come back as int
        # (rather than float which is Excel's format).
        df = DataFrame(np.random.randint(-10, 10, size=(10, 2)), dtype=np_type)
        df.to_excel(self.path, "test1")

        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=0)

        int_frame = df.astype(np.int64)
        tm.assert_frame_equal(int_frame, recons)

        recons2 = pd.read_excel(self.path, "test1", index_col=0)
        tm.assert_frame_equal(int_frame, recons2)

        # Test with convert_float=False comes back as float.
        float_frame = df.astype(float)
        recons = pd.read_excel(self.path, "test1", convert_float=False, index_col=0)
        tm.assert_frame_equal(
            recons, float_frame, check_index_type=False, check_column_type=False
        )

    @pytest.mark.parametrize("np_type", [np.float16, np.float32, np.float64])
    def test_float_types(self, engine, ext, np_type):
        # Test np.float values read come back as float.
        df = DataFrame(np.random.random_sample(10), dtype=np_type)
        df.to_excel(self.path, "test1")

        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=0).astype(np_type)

        tm.assert_frame_equal(df, recons, check_dtype=False)

    @pytest.mark.parametrize("np_type", [np.bool8, np.bool_])
    def test_bool_types(self, engine, ext, np_type):
        # Test np.bool values read come back as float.
        df = DataFrame([1, 0, True, False], dtype=np_type)
        df.to_excel(self.path, "test1")

        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=0).astype(np_type)

        tm.assert_frame_equal(df, recons)

    def test_inf_roundtrip(self, engine, ext):
        df = DataFrame([(1, np.inf), (2, 3), (5, -np.inf)])
        df.to_excel(self.path, "test1")

        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=0)

        tm.assert_frame_equal(df, recons)

    def test_sheets(self, engine, ext, frame, tsframe):
        frame = frame.copy()
        frame["A"][:5] = nan

        frame.to_excel(self.path, "test1")
        frame.to_excel(self.path, "test1", columns=["A", "B"])
        frame.to_excel(self.path, "test1", header=False)
        frame.to_excel(self.path, "test1", index=False)

        # Test writing to separate sheets
        writer = ExcelWriter(self.path)
        frame.to_excel(writer, "test1")
        tsframe.to_excel(writer, "test2")
        writer.save()
        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=0)
        tm.assert_frame_equal(frame, recons)
        recons = pd.read_excel(reader, "test2", index_col=0)
        tm.assert_frame_equal(tsframe, recons)
        assert 2 == len(reader.sheet_names)
        assert "test1" == reader.sheet_names[0]
        assert "test2" == reader.sheet_names[1]

    def test_colaliases(self, engine, ext, frame):
        frame = frame.copy()
        frame["A"][:5] = nan

        frame.to_excel(self.path, "test1")
        frame.to_excel(self.path, "test1", columns=["A", "B"])
        frame.to_excel(self.path, "test1", header=False)
        frame.to_excel(self.path, "test1", index=False)

        # column aliases
        col_aliases = Index(["AA", "X", "Y", "Z"])
        frame.to_excel(self.path, "test1", header=col_aliases)
        reader = ExcelFile(self.path)
        rs = pd.read_excel(reader, "test1", index_col=0)
        xp = frame.copy()
        xp.columns = col_aliases
        tm.assert_frame_equal(xp, rs)

    def test_roundtrip_indexlabels(self, merge_cells, engine, ext, frame):
        frame = frame.copy()
        frame["A"][:5] = nan

        frame.to_excel(self.path, "test1")
        frame.to_excel(self.path, "test1", columns=["A", "B"])
        frame.to_excel(self.path, "test1", header=False)
        frame.to_excel(self.path, "test1", index=False)

        # test index_label
        df = DataFrame(np.random.randn(10, 2)) >= 0
        df.to_excel(self.path, "test1", index_label=["test"], merge_cells=merge_cells)
        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=0).astype(np.int64)
        df.index.names = ["test"]
        assert df.index.names == recons.index.names

        df = DataFrame(np.random.randn(10, 2)) >= 0
        df.to_excel(
            self.path,
            "test1",
            index_label=["test", "dummy", "dummy2"],
            merge_cells=merge_cells,
        )
        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=0).astype(np.int64)
        df.index.names = ["test"]
        assert df.index.names == recons.index.names

        df = DataFrame(np.random.randn(10, 2)) >= 0
        df.to_excel(self.path, "test1", index_label="test", merge_cells=merge_cells)
        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=0).astype(np.int64)
        df.index.names = ["test"]
        tm.assert_frame_equal(df, recons.astype(bool))

        frame.to_excel(
            self.path,
            "test1",
            columns=["A", "B", "C", "D"],
            index=False,
            merge_cells=merge_cells,
        )
        # take 'A' and 'B' as indexes (same row as cols 'C', 'D')
        df = frame.copy()
        df = df.set_index(["A", "B"])

        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=[0, 1])
        tm.assert_frame_equal(df, recons, check_less_precise=True)

    def test_excel_roundtrip_indexname(self, merge_cells, engine, ext):
        df = DataFrame(np.random.randn(10, 4))
        df.index.name = "foo"

        df.to_excel(self.path, merge_cells=merge_cells)

        xf = ExcelFile(self.path)
        result = pd.read_excel(xf, xf.sheet_names[0], index_col=0)

        tm.assert_frame_equal(result, df)
        assert result.index.name == "foo"

    def test_excel_roundtrip_datetime(self, merge_cells, tsframe, engine, ext):
        # datetime.date, not sure what to test here exactly
        tsf = tsframe.copy()

        tsf.index = [x.date() for x in tsframe.index]
        tsf.to_excel(self.path, "test1", merge_cells=merge_cells)

        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=0)

        tm.assert_frame_equal(tsframe, recons)

    def test_excel_date_datetime_format(self, engine, ext):
        # see gh-4133
        #
        # Excel output format strings
        df = DataFrame(
            [
                [date(2014, 1, 31), date(1999, 9, 24)],
                [datetime(1998, 5, 26, 23, 33, 4), datetime(2014, 2, 28, 13, 5, 13)],
            ],
            index=["DATE", "DATETIME"],
            columns=["X", "Y"],
        )
        df_expected = DataFrame(
            [
                [datetime(2014, 1, 31), datetime(1999, 9, 24)],
                [datetime(1998, 5, 26, 23, 33, 4), datetime(2014, 2, 28, 13, 5, 13)],
            ],
            index=["DATE", "DATETIME"],
            columns=["X", "Y"],
        )

        with ensure_clean(ext) as filename2:
            writer1 = ExcelWriter(self.path)
            writer2 = ExcelWriter(
                filename2,
                date_format="DD.MM.YYYY",
                datetime_format="DD.MM.YYYY HH-MM-SS",
            )

            df.to_excel(writer1, "test1")
            df.to_excel(writer2, "test1")

            writer1.close()
            writer2.close()

            reader1 = ExcelFile(self.path)
            reader2 = ExcelFile(filename2)

            rs1 = pd.read_excel(reader1, "test1", index_col=0)
            rs2 = pd.read_excel(reader2, "test1", index_col=0)

            tm.assert_frame_equal(rs1, rs2)

            # Since the reader returns a datetime object for dates,
            # we need to use df_expected to check the result.
            tm.assert_frame_equal(rs2, df_expected)

    def test_to_excel_interval_no_labels(self, engine, ext):
        # see gh-19242
        #
        # Test writing Interval without labels.
        df = DataFrame(np.random.randint(-10, 10, size=(20, 1)), dtype=np.int64)
        expected = df.copy()

        df["new"] = pd.cut(df[0], 10)
        expected["new"] = pd.cut(expected[0], 10).astype(str)

        df.to_excel(self.path, "test1")
        reader = ExcelFile(self.path)

        recons = pd.read_excel(reader, "test1", index_col=0)
        tm.assert_frame_equal(expected, recons)

    def test_to_excel_interval_labels(self, engine, ext):
        # see gh-19242
        #
        # Test writing Interval with labels.
        df = DataFrame(np.random.randint(-10, 10, size=(20, 1)), dtype=np.int64)
        expected = df.copy()
        intervals = pd.cut(
            df[0], 10, labels=["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
        )
        df["new"] = intervals
        expected["new"] = pd.Series(list(intervals))

        df.to_excel(self.path, "test1")
        reader = ExcelFile(self.path)

        recons = pd.read_excel(reader, "test1", index_col=0)
        tm.assert_frame_equal(expected, recons)

    def test_to_excel_timedelta(self, engine, ext):
        # see gh-19242, gh-9155
        #
        # Test writing timedelta to xls.
        df = DataFrame(
            np.random.randint(-10, 10, size=(20, 1)), columns=["A"], dtype=np.int64
        )
        expected = df.copy()

        df["new"] = df["A"].apply(lambda x: timedelta(seconds=x))
        expected["new"] = expected["A"].apply(
            lambda x: timedelta(seconds=x).total_seconds() / float(86400)
        )

        df.to_excel(self.path, "test1")
        reader = ExcelFile(self.path)

        recons = pd.read_excel(reader, "test1", index_col=0)
        tm.assert_frame_equal(expected, recons)

    def test_to_excel_periodindex(self, engine, ext, tsframe):
        xp = tsframe.resample("M", kind="period").mean()

        xp.to_excel(self.path, "sht1")

        reader = ExcelFile(self.path)
        rs = pd.read_excel(reader, "sht1", index_col=0)
        tm.assert_frame_equal(xp, rs.to_period("M"))

    def test_to_excel_multiindex(self, merge_cells, engine, ext, frame):
        arrays = np.arange(len(frame.index) * 2).reshape(2, -1)
        new_index = MultiIndex.from_arrays(arrays, names=["first", "second"])
        frame.index = new_index

        frame.to_excel(self.path, "test1", header=False)
        frame.to_excel(self.path, "test1", columns=["A", "B"])

        # round trip
        frame.to_excel(self.path, "test1", merge_cells=merge_cells)
        reader = ExcelFile(self.path)
        df = pd.read_excel(reader, "test1", index_col=[0, 1])
        tm.assert_frame_equal(frame, df)

    # GH13511
    def test_to_excel_multiindex_nan_label(self, merge_cells, engine, ext):
        df = pd.DataFrame(
            {"A": [None, 2, 3], "B": [10, 20, 30], "C": np.random.sample(3)}
        )
        df = df.set_index(["A", "B"])

        df.to_excel(self.path, merge_cells=merge_cells)
        df1 = pd.read_excel(self.path, index_col=[0, 1])
        tm.assert_frame_equal(df, df1)

    # Test for Issue 11328. If column indices are integers, make
    # sure they are handled correctly for either setting of
    # merge_cells
    def test_to_excel_multiindex_cols(self, merge_cells, engine, ext, frame):
        arrays = np.arange(len(frame.index) * 2).reshape(2, -1)
        new_index = MultiIndex.from_arrays(arrays, names=["first", "second"])
        frame.index = new_index

        new_cols_index = MultiIndex.from_tuples([(40, 1), (40, 2), (50, 1), (50, 2)])
        frame.columns = new_cols_index
        header = [0, 1]
        if not merge_cells:
            header = 0

        # round trip
        frame.to_excel(self.path, "test1", merge_cells=merge_cells)
        reader = ExcelFile(self.path)
        df = pd.read_excel(reader, "test1", header=header, index_col=[0, 1])
        if not merge_cells:
            fm = frame.columns.format(sparsify=False, adjoin=False, names=False)
            frame.columns = [".".join(map(str, q)) for q in zip(*fm)]
        tm.assert_frame_equal(frame, df)

    def test_to_excel_multiindex_dates(self, merge_cells, engine, ext, tsframe):
        # try multiindex with dates
        new_index = [tsframe.index, np.arange(len(tsframe.index))]
        tsframe.index = MultiIndex.from_arrays(new_index)

        tsframe.index.names = ["time", "foo"]
        tsframe.to_excel(self.path, "test1", merge_cells=merge_cells)
        reader = ExcelFile(self.path)
        recons = pd.read_excel(reader, "test1", index_col=[0, 1])

        tm.assert_frame_equal(tsframe, recons)
        assert recons.index.names == ("time", "foo")

    def test_to_excel_multiindex_no_write_index(self, engine, ext):
        # Test writing and re-reading a MI without the index. GH 5616.

        # Initial non-MI frame.
        frame1 = DataFrame({"a": [10, 20], "b": [30, 40], "c": [50, 60]})

        # Add a MI.
        frame2 = frame1.copy()
        multi_index = MultiIndex.from_tuples([(70, 80), (90, 100)])
        frame2.index = multi_index

        # Write out to Excel without the index.
        frame2.to_excel(self.path, "test1", index=False)

        # Read it back in.
        reader = ExcelFile(self.path)
        frame3 = pd.read_excel(reader, "test1")

        # Test that it is the same as the initial frame.
        tm.assert_frame_equal(frame1, frame3)

    def test_to_excel_float_format(self, engine, ext):
        df = DataFrame(
            [[0.123456, 0.234567, 0.567567], [12.32112, 123123.2, 321321.2]],
            index=["A", "B"],
            columns=["X", "Y", "Z"],
        )
        df.to_excel(self.path, "test1", float_format="%.2f")

        reader = ExcelFile(self.path)
        result = pd.read_excel(reader, "test1", index_col=0)

        expected = DataFrame(
            [[0.12, 0.23, 0.57], [12.32, 123123.20, 321321.20]],
            index=["A", "B"],
            columns=["X", "Y", "Z"],
        )
        tm.assert_frame_equal(result, expected)

    def test_to_excel_output_encoding(self, engine, ext):
        # Avoid mixed inferred_type.
        df = DataFrame(
            [["\u0192", "\u0193", "\u0194"], ["\u0195", "\u0196", "\u0197"]],
            index=["A\u0192", "B"],
            columns=["X\u0193", "Y", "Z"],
        )

        with ensure_clean("__tmp_to_excel_float_format__." + ext) as filename:
            df.to_excel(filename, sheet_name="TestSheet", encoding="utf8")
            result = pd.read_excel(filename, "TestSheet", encoding="utf8", index_col=0)
            tm.assert_frame_equal(result, df)

    def test_to_excel_unicode_filename(self, engine, ext):
        with ensure_clean("\u0192u." + ext) as filename:
            try:
                f = open(filename, "wb")
            except UnicodeEncodeError:
                pytest.skip("No unicode file names on this system")
            else:
                f.close()

            df = DataFrame(
                [[0.123456, 0.234567, 0.567567], [12.32112, 123123.2, 321321.2]],
                index=["A", "B"],
                columns=["X", "Y", "Z"],
            )
            df.to_excel(filename, "test1", float_format="%.2f")

            reader = ExcelFile(filename)
            result = pd.read_excel(reader, "test1", index_col=0)

            expected = DataFrame(
                [[0.12, 0.23, 0.57], [12.32, 123123.20, 321321.20]],
                index=["A", "B"],
                columns=["X", "Y", "Z"],
            )
            tm.assert_frame_equal(result, expected)

    # def test_to_excel_header_styling_xls(self, engine, ext):

    #     import StringIO
    #     s = StringIO(
    #     """Date,ticker,type,value
    #     2001-01-01,x,close,12.2
    #     2001-01-01,x,open ,12.1
    #     2001-01-01,y,close,12.2
    #     2001-01-01,y,open ,12.1
    #     2001-02-01,x,close,12.2
    #     2001-02-01,x,open ,12.1
    #     2001-02-01,y,close,12.2
    #     2001-02-01,y,open ,12.1
    #     2001-03-01,x,close,12.2
    #     2001-03-01,x,open ,12.1
    #     2001-03-01,y,close,12.2
    #     2001-03-01,y,open ,12.1""")
    #     df = read_csv(s, parse_dates=["Date"])
    #     pdf = df.pivot_table(values="value", rows=["ticker"],
    #                                          cols=["Date", "type"])

    #     try:
    #         import xlwt
    #         import xlrd
    #     except ImportError:
    #         pytest.skip

    #     filename = '__tmp_to_excel_header_styling_xls__.xls'
    #     pdf.to_excel(filename, 'test1')

    #     wbk = xlrd.open_workbook(filename,
    #                              formatting_info=True)
    #     assert ["test1"] == wbk.sheet_names()
    #     ws = wbk.sheet_by_name('test1')
    #     assert [(0, 1, 5, 7), (0, 1, 3, 5), (0, 1, 1, 3)] == ws.merged_cells
    #     for i in range(0, 2):
    #         for j in range(0, 7):
    #             xfx = ws.cell_xf_index(0, 0)
    #             cell_xf = wbk.xf_list[xfx]
    #             font = wbk.font_list
    #             assert 1 == font[cell_xf.font_index].bold
    #             assert 1 == cell_xf.border.top_line_style
    #             assert 1 == cell_xf.border.right_line_style
    #             assert 1 == cell_xf.border.bottom_line_style
    #             assert 1 == cell_xf.border.left_line_style
    #             assert 2 == cell_xf.alignment.hor_align
    #     os.remove(filename)
    # def test_to_excel_header_styling_xlsx(self, engine, ext):
    #     import StringIO
    #     s = StringIO(
    #     """Date,ticker,type,value
    #     2001-01-01,x,close,12.2
    #     2001-01-01,x,open ,12.1
    #     2001-01-01,y,close,12.2
    #     2001-01-01,y,open ,12.1
    #     2001-02-01,x,close,12.2
    #     2001-02-01,x,open ,12.1
    #     2001-02-01,y,close,12.2
    #     2001-02-01,y,open ,12.1
    #     2001-03-01,x,close,12.2
    #     2001-03-01,x,open ,12.1
    #     2001-03-01,y,close,12.2
    #     2001-03-01,y,open ,12.1""")
    #     df = read_csv(s, parse_dates=["Date"])
    #     pdf = df.pivot_table(values="value", rows=["ticker"],
    #                                          cols=["Date", "type"])
    #     try:
    #         import openpyxl
    #         from openpyxl.cell import get_column_letter
    #     except ImportError:
    #         pytest.skip
    #     if openpyxl.__version__ < '1.6.1':
    #         pytest.skip
    #     # test xlsx_styling
    #     filename = '__tmp_to_excel_header_styling_xlsx__.xlsx'
    #     pdf.to_excel(filename, 'test1')
    #     wbk = openpyxl.load_workbook(filename)
    #     assert ["test1"] == wbk.get_sheet_names()
    #     ws = wbk.get_sheet_by_name('test1')
    #     xlsaddrs = ["%s2" % chr(i) for i in range(ord('A'), ord('H'))]
    #     xlsaddrs += ["A%s" % i for i in range(1, 6)]
    #     xlsaddrs += ["B1", "D1", "F1"]
    #     for xlsaddr in xlsaddrs:
    #         cell = ws.cell(xlsaddr)
    #         assert cell.style.font.bold
    #         assert (openpyxl.style.Border.BORDER_THIN ==
    #                 cell.style.borders.top.border_style)
    #         assert (openpyxl.style.Border.BORDER_THIN ==
    #                 cell.style.borders.right.border_style)
    #         assert (openpyxl.style.Border.BORDER_THIN ==
    #                 cell.style.borders.bottom.border_style)
    #         assert (openpyxl.style.Border.BORDER_THIN ==
    #                 cell.style.borders.left.border_style)
    #         assert (openpyxl.style.Alignment.HORIZONTAL_CENTER ==
    #                 cell.style.alignment.horizontal)
    #     mergedcells_addrs = ["C1", "E1", "G1"]
    #     for maddr in mergedcells_addrs:
    #         assert ws.cell(maddr).merged
    #     os.remove(filename)

    @pytest.mark.parametrize("use_headers", [True, False])
    @pytest.mark.parametrize("r_idx_nlevels", [1, 2, 3])
    @pytest.mark.parametrize("c_idx_nlevels", [1, 2, 3])
    def test_excel_010_hemstring(
        self, merge_cells, engine, ext, c_idx_nlevels, r_idx_nlevels, use_headers
    ):
        def roundtrip(data, header=True, parser_hdr=0, index=True):
            data.to_excel(
                self.path, header=header, merge_cells=merge_cells, index=index
            )

            xf = ExcelFile(self.path)
            return pd.read_excel(xf, xf.sheet_names[0], header=parser_hdr)

        # Basic test.
        parser_header = 0 if use_headers else None
        res = roundtrip(DataFrame([0]), use_headers, parser_header)

        assert res.shape == (1, 2)
        assert res.iloc[0, 0] is not np.nan

        # More complex tests with multi-index.
        nrows = 5
        ncols = 3

        from pandas.util.testing import makeCustomDataframe as mkdf

        # ensure limited functionality in 0.10
        # override of gh-2370 until sorted out in 0.11

        df = mkdf(
            nrows, ncols, r_idx_nlevels=r_idx_nlevels, c_idx_nlevels=c_idx_nlevels
        )

        # This if will be removed once multi-column Excel writing
        # is implemented. For now fixing gh-9794.
        if c_idx_nlevels > 1:
            with pytest.raises(NotImplementedError):
                roundtrip(df, use_headers, index=False)
        else:
            res = roundtrip(df, use_headers)

            if use_headers:
                assert res.shape == (nrows, ncols + r_idx_nlevels)
            else:
                # First row taken as columns.
                assert res.shape == (nrows - 1, ncols + r_idx_nlevels)

            # No NaNs.
            for r in range(len(res.index)):
                for c in range(len(res.columns)):
                    assert res.iloc[r, c] is not np.nan

    def test_duplicated_columns(self, engine, ext):
        # see gh-5235
        df = DataFrame([[1, 2, 3], [1, 2, 3], [1, 2, 3]], columns=["A", "B", "B"])
        df.to_excel(self.path, "test1")
        expected = DataFrame(
            [[1, 2, 3], [1, 2, 3], [1, 2, 3]], columns=["A", "B", "B.1"]
        )

        # By default, we mangle.
        result = pd.read_excel(self.path, "test1", index_col=0)
        tm.assert_frame_equal(result, expected)

        # Explicitly, we pass in the parameter.
        result = pd.read_excel(self.path, "test1", index_col=0, mangle_dupe_cols=True)
        tm.assert_frame_equal(result, expected)

        # see gh-11007, gh-10970
        df = DataFrame([[1, 2, 3, 4], [5, 6, 7, 8]], columns=["A", "B", "A", "B"])
        df.to_excel(self.path, "test1")

        result = pd.read_excel(self.path, "test1", index_col=0)
        expected = DataFrame(
            [[1, 2, 3, 4], [5, 6, 7, 8]], columns=["A", "B", "A.1", "B.1"]
        )
        tm.assert_frame_equal(result, expected)

        # see gh-10982
        df.to_excel(self.path, "test1", index=False, header=False)
        result = pd.read_excel(self.path, "test1", header=None)

        expected = DataFrame([[1, 2, 3, 4], [5, 6, 7, 8]])
        tm.assert_frame_equal(result, expected)

        msg = "Setting mangle_dupe_cols=False is not supported yet"
        with pytest.raises(ValueError, match=msg):
            pd.read_excel(self.path, "test1", header=None, mangle_dupe_cols=False)

    def test_swapped_columns(self, engine, ext):
        # Test for issue #5427.
        write_frame = DataFrame({"A": [1, 1, 1], "B": [2, 2, 2]})
        write_frame.to_excel(self.path, "test1", columns=["B", "A"])

        read_frame = pd.read_excel(self.path, "test1", header=0)

        tm.assert_series_equal(write_frame["A"], read_frame["A"])
        tm.assert_series_equal(write_frame["B"], read_frame["B"])

    def test_invalid_columns(self, engine, ext):
        # see gh-10982
        write_frame = DataFrame({"A": [1, 1, 1], "B": [2, 2, 2]})

        with tm.assert_produces_warning(FutureWarning, check_stacklevel=False):
            write_frame.to_excel(self.path, "test1", columns=["B", "C"])

        expected = write_frame.reindex(columns=["B", "C"])
        read_frame = pd.read_excel(self.path, "test1", index_col=0)
        tm.assert_frame_equal(expected, read_frame)

        with pytest.raises(KeyError):
            write_frame.to_excel(self.path, "test1", columns=["C", "D"])

    def test_comment_arg(self, engine, ext):
        # see gh-18735
        #
        # Test the comment argument functionality to pd.read_excel.

        # Create file to read in.
        df = DataFrame({"A": ["one", "#one", "one"], "B": ["two", "two", "#two"]})
        df.to_excel(self.path, "test_c")

        # Read file without comment arg.
        result1 = pd.read_excel(self.path, "test_c", index_col=0)

        result1.iloc[1, 0] = None
        result1.iloc[1, 1] = None
        result1.iloc[2, 1] = None

        result2 = pd.read_excel(self.path, "test_c", comment="#", index_col=0)
        tm.assert_frame_equal(result1, result2)

    def test_comment_default(self, engine, ext):
        # Re issue #18735
        # Test the comment argument default to pd.read_excel

        # Create file to read in
        df = DataFrame({"A": ["one", "#one", "one"], "B": ["two", "two", "#two"]})
        df.to_excel(self.path, "test_c")

        # Read file with default and explicit comment=None
        result1 = pd.read_excel(self.path, "test_c")
        result2 = pd.read_excel(self.path, "test_c", comment=None)
        tm.assert_frame_equal(result1, result2)

    def test_comment_used(self, engine, ext):
        # see gh-18735
        #
        # Test the comment argument is working as expected when used.

        # Create file to read in.
        df = DataFrame({"A": ["one", "#one", "one"], "B": ["two", "two", "#two"]})
        df.to_excel(self.path, "test_c")

        # Test read_frame_comment against manually produced expected output.
        expected = DataFrame({"A": ["one", None, "one"], "B": ["two", None, None]})
        result = pd.read_excel(self.path, "test_c", comment="#", index_col=0)
        tm.assert_frame_equal(result, expected)

    def test_comment_empty_line(self, engine, ext):
        # Re issue #18735
        # Test that pd.read_excel ignores commented lines at the end of file

        df = DataFrame({"a": ["1", "#2"], "b": ["2", "3"]})
        df.to_excel(self.path, index=False)

        # Test that all-comment lines at EoF are ignored
        expected = DataFrame({"a": [1], "b": [2]})
        result = pd.read_excel(self.path, comment="#")
        tm.assert_frame_equal(result, expected)

    def test_datetimes(self, engine, ext):

        # Test writing and reading datetimes. For issue #9139. (xref #9185)
        datetimes = [
            datetime(2013, 1, 13, 1, 2, 3),
            datetime(2013, 1, 13, 2, 45, 56),
            datetime(2013, 1, 13, 4, 29, 49),
            datetime(2013, 1, 13, 6, 13, 42),
            datetime(2013, 1, 13, 7, 57, 35),
            datetime(2013, 1, 13, 9, 41, 28),
            datetime(2013, 1, 13, 11, 25, 21),
            datetime(2013, 1, 13, 13, 9, 14),
            datetime(2013, 1, 13, 14, 53, 7),
            datetime(2013, 1, 13, 16, 37, 0),
            datetime(2013, 1, 13, 18, 20, 52),
        ]

        write_frame = DataFrame({"A": datetimes})
        write_frame.to_excel(self.path, "Sheet1")
        read_frame = pd.read_excel(self.path, "Sheet1", header=0)

        tm.assert_series_equal(write_frame["A"], read_frame["A"])

    def test_bytes_io(self, engine, ext):
        # see gh-7074
        bio = BytesIO()
        df = DataFrame(np.random.randn(10, 2))

        # Pass engine explicitly, as there is no file path to infer from.
        writer = ExcelWriter(bio, engine=engine)
        df.to_excel(writer)
        writer.save()

        bio.seek(0)
        reread_df = pd.read_excel(bio, index_col=0)
        tm.assert_frame_equal(df, reread_df)

    def test_write_lists_dict(self, engine, ext):
        # see gh-8188.
        df = DataFrame(
            {
                "mixed": ["a", ["b", "c"], {"d": "e", "f": 2}],
                "numeric": [1, 2, 3.0],
                "str": ["apple", "banana", "cherry"],
            }
        )
        df.to_excel(self.path, "Sheet1")
        read = pd.read_excel(self.path, "Sheet1", header=0, index_col=0)

        expected = df.copy()
        expected.mixed = expected.mixed.apply(str)
        expected.numeric = expected.numeric.astype("int64")

        tm.assert_frame_equal(read, expected)

    def test_true_and_false_value_options(self, engine, ext):
        # see gh-13347
        df = pd.DataFrame([["foo", "bar"]], columns=["col1", "col2"])
        expected = df.replace({"foo": True, "bar": False})

        df.to_excel(self.path)
        read_frame = pd.read_excel(
            self.path, true_values=["foo"], false_values=["bar"], index_col=0
        )
        tm.assert_frame_equal(read_frame, expected)

    def test_freeze_panes(self, engine, ext):
        # see gh-15160
        expected = DataFrame([[1, 2], [3, 4]], columns=["col1", "col2"])
        expected.to_excel(self.path, "Sheet1", freeze_panes=(1, 1))

        result = pd.read_excel(self.path, index_col=0)
        tm.assert_frame_equal(result, expected)

    def test_path_path_lib(self, engine, ext):
        df = tm.makeDataFrame()
        writer = partial(df.to_excel, engine=engine)

        reader = partial(pd.read_excel, index_col=0)
        result = tm.round_trip_pathlib(writer, reader, path="foo.{ext}".format(ext=ext))
        tm.assert_frame_equal(result, df)

    def test_path_local_path(self, engine, ext):
        df = tm.makeDataFrame()
        writer = partial(df.to_excel, engine=engine)

        reader = partial(pd.read_excel, index_col=0)
        result = tm.round_trip_pathlib(writer, reader, path="foo.{ext}".format(ext=ext))
        tm.assert_frame_equal(result, df)

    def test_merged_cell_custom_objects(self, engine, merge_cells, ext):
        # see GH-27006
        mi = MultiIndex.from_tuples(
            [
                (pd.Period("2018"), pd.Period("2018Q1")),
                (pd.Period("2018"), pd.Period("2018Q2")),
            ]
        )
        expected = DataFrame(np.ones((2, 2)), columns=mi)
        expected.to_excel(self.path)
        result = pd.read_excel(
            self.path, header=[0, 1], index_col=0, convert_float=False
        )
        # need to convert PeriodIndexes to standard Indexes for assert equal
        expected.columns.set_levels(
            [[str(i) for i in mi.levels[0]], [str(i) for i in mi.levels[1]]],
            level=[0, 1],
            inplace=True,
        )
        expected.index = expected.index.astype(np.float64)
        tm.assert_frame_equal(expected, result)

    @pytest.mark.parametrize("dtype", [None, object])
    def test_raise_when_saving_timezones(self, engine, ext, dtype, tz_aware_fixture):
        # GH 27008, GH 7056
        tz = tz_aware_fixture
        data = pd.Timestamp("2019", tz=tz)
        df = DataFrame([data], dtype=dtype)
        with pytest.raises(ValueError, match="Excel does not support"):
            df.to_excel(self.path)

        data = data.to_pydatetime()
        df = DataFrame([data], dtype=dtype)
        with pytest.raises(ValueError, match="Excel does not support"):
            df.to_excel(self.path)


class TestExcelWriterEngineTests:
    @pytest.mark.parametrize(
        "klass,ext",
        [
            pytest.param(_XlsxWriter, ".xlsx", marks=td.skip_if_no("xlsxwriter")),
            pytest.param(_OpenpyxlWriter, ".xlsx", marks=td.skip_if_no("openpyxl")),
            pytest.param(_XlwtWriter, ".xls", marks=td.skip_if_no("xlwt")),
        ],
    )
    def test_ExcelWriter_dispatch(self, klass, ext):
        with ensure_clean(ext) as path:
            writer = ExcelWriter(path)
            if ext == ".xlsx" and td.safe_import("xlsxwriter"):
                # xlsxwriter has preference over openpyxl if both installed
                assert isinstance(writer, _XlsxWriter)
            else:
                assert isinstance(writer, klass)

    def test_ExcelWriter_dispatch_raises(self):
        with pytest.raises(ValueError, match="No engine"):
            ExcelWriter("nothing")

    def test_register_writer(self):
        # some awkward mocking to test out dispatch and such actually works
        called_save = []
        called_write_cells = []

        class DummyClass(ExcelWriter):
            called_save = False
            called_write_cells = False
            supported_extensions = ["xlsx", "xls"]
            engine = "dummy"

            def save(self):
                called_save.append(True)

            def write_cells(self, *args, **kwargs):
                called_write_cells.append(True)

        def check_called(func):
            func()
            assert len(called_save) >= 1
            assert len(called_write_cells) >= 1
            del called_save[:]
            del called_write_cells[:]

        with pd.option_context("io.excel.xlsx.writer", "dummy"):
            register_writer(DummyClass)
            writer = ExcelWriter("something.xlsx")
            assert isinstance(writer, DummyClass)
            df = tm.makeCustomDataframe(1, 1)
            check_called(lambda: df.to_excel("something.xlsx"))
            check_called(lambda: df.to_excel("something.xls", engine="dummy"))


@td.skip_if_no("xlrd")
@td.skip_if_no("openpyxl")
@pytest.mark.skipif(not PY36, reason="requires fspath")
class TestFSPath:
    def test_excelfile_fspath(self):
        with tm.ensure_clean("foo.xlsx") as path:
            df = DataFrame({"A": [1, 2]})
            df.to_excel(path)
            xl = ExcelFile(path)
            result = os.fspath(xl)
            assert result == path

    def test_excelwriter_fspath(self):
        with tm.ensure_clean("foo.xlsx") as path:
            writer = ExcelWriter(path)
            assert os.fspath(writer) == str(path)
