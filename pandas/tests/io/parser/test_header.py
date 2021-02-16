"""
Tests that the file header is properly handled or inferred
during parsing for all of the parsers defined in parsers.py
"""

from collections import namedtuple
from io import StringIO

import numpy as np
import pytest

from pandas.errors import ParserError

from pandas import (
    DataFrame,
    Index,
    MultiIndex,
)
import pandas._testing as tm


def test_read_with_bad_header(all_parsers):
    parser = all_parsers
    msg = r"but only \d+ lines in file"

    with pytest.raises(ValueError, match=msg):
        s = StringIO(",,")
        parser.read_csv(s, header=[10])


def test_negative_header(all_parsers):
    # see gh-27779
    parser = all_parsers
    data = """1,2,3,4,5
6,7,8,9,10
11,12,13,14,15
"""
    with pytest.raises(
        ValueError,
        match="Passing negative integer to header is invalid. "
        "For no header, use header=None instead",
    ):
        parser.read_csv(StringIO(data), header=-1)


@pytest.mark.parametrize("header", [([-1, 2, 4]), ([-5, 0])])
def test_negative_multi_index_header(all_parsers, header):
    # see gh-27779
    parser = all_parsers
    data = """1,2,3,4,5
        6,7,8,9,10
        11,12,13,14,15
        """
    with pytest.raises(
        ValueError, match="cannot specify multi-index header with negative integers"
    ):
        parser.read_csv(StringIO(data), header=header)


@pytest.mark.parametrize("header", [True, False])
def test_bool_header_arg(all_parsers, header):
    # see gh-6114
    parser = all_parsers
    data = """\
MyColumn
a
b
a
b"""
    msg = "Passing a bool to header is invalid"
    with pytest.raises(TypeError, match=msg):
        parser.read_csv(StringIO(data), header=header)


def test_no_header_prefix(all_parsers):
    parser = all_parsers
    data = """1,2,3,4,5
6,7,8,9,10
11,12,13,14,15
"""
    result = parser.read_csv(StringIO(data), prefix="Field", header=None)
    expected = DataFrame(
        [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10], [11, 12, 13, 14, 15]],
        columns=["Field0", "Field1", "Field2", "Field3", "Field4"],
    )
    tm.assert_frame_equal(result, expected)


def test_header_with_index_col(all_parsers):
    parser = all_parsers
    data = """foo,1,2,3
bar,4,5,6
baz,7,8,9
"""
    names = ["A", "B", "C"]
    result = parser.read_csv(StringIO(data), names=names)

    expected = DataFrame(
        [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
        index=["foo", "bar", "baz"],
        columns=["A", "B", "C"],
    )
    tm.assert_frame_equal(result, expected)


def test_header_not_first_line(all_parsers):
    parser = all_parsers
    data = """got,to,ignore,this,line
got,to,ignore,this,line
index,A,B,C,D
foo,2,3,4,5
bar,7,8,9,10
baz,12,13,14,15
"""
    data2 = """index,A,B,C,D
foo,2,3,4,5
bar,7,8,9,10
baz,12,13,14,15
"""

    result = parser.read_csv(StringIO(data), header=2, index_col=0)
    expected = parser.read_csv(StringIO(data2), header=0, index_col=0)
    tm.assert_frame_equal(result, expected)


def test_header_multi_index(all_parsers):
    parser = all_parsers
    expected = tm.makeCustomDataframe(5, 3, r_idx_nlevels=2, c_idx_nlevels=4)

    data = """\
C0,,C_l0_g0,C_l0_g1,C_l0_g2

C1,,C_l1_g0,C_l1_g1,C_l1_g2
C2,,C_l2_g0,C_l2_g1,C_l2_g2
C3,,C_l3_g0,C_l3_g1,C_l3_g2
R0,R1,,,
R_l0_g0,R_l1_g0,R0C0,R0C1,R0C2
R_l0_g1,R_l1_g1,R1C0,R1C1,R1C2
R_l0_g2,R_l1_g2,R2C0,R2C1,R2C2
R_l0_g3,R_l1_g3,R3C0,R3C1,R3C2
R_l0_g4,R_l1_g4,R4C0,R4C1,R4C2
"""
    result = parser.read_csv(StringIO(data), header=[0, 1, 2, 3], index_col=[0, 1])
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "kwargs,msg",
    [
        (
            {"index_col": ["foo", "bar"]},
            (
                "index_col must only contain "
                "row numbers when specifying "
                "a multi-index header"
            ),
        ),
        (
            {"index_col": [0, 1], "names": ["foo", "bar"]},
            ("cannot specify names when specifying a multi-index header"),
        ),
        (
            {"index_col": [0, 1], "usecols": ["foo", "bar"]},
            ("cannot specify usecols when specifying a multi-index header"),
        ),
    ],
)
def test_header_multi_index_invalid(all_parsers, kwargs, msg):
    data = """\
C0,,C_l0_g0,C_l0_g1,C_l0_g2

C1,,C_l1_g0,C_l1_g1,C_l1_g2
C2,,C_l2_g0,C_l2_g1,C_l2_g2
C3,,C_l3_g0,C_l3_g1,C_l3_g2
R0,R1,,,
R_l0_g0,R_l1_g0,R0C0,R0C1,R0C2
R_l0_g1,R_l1_g1,R1C0,R1C1,R1C2
R_l0_g2,R_l1_g2,R2C0,R2C1,R2C2
R_l0_g3,R_l1_g3,R3C0,R3C1,R3C2
R_l0_g4,R_l1_g4,R4C0,R4C1,R4C2
"""
    parser = all_parsers

    with pytest.raises(ValueError, match=msg):
        parser.read_csv(StringIO(data), header=[0, 1, 2, 3], **kwargs)


_TestTuple = namedtuple("_TestTuple", ["first", "second"])


@pytest.mark.parametrize(
    "kwargs",
    [
        {"header": [0, 1]},
        {
            "skiprows": 3,
            "names": [
                ("a", "q"),
                ("a", "r"),
                ("a", "s"),
                ("b", "t"),
                ("c", "u"),
                ("c", "v"),
            ],
        },
        {
            "skiprows": 3,
            "names": [
                _TestTuple("a", "q"),
                _TestTuple("a", "r"),
                _TestTuple("a", "s"),
                _TestTuple("b", "t"),
                _TestTuple("c", "u"),
                _TestTuple("c", "v"),
            ],
        },
    ],
)
def test_header_multi_index_common_format1(all_parsers, kwargs):
    parser = all_parsers
    expected = DataFrame(
        [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]],
        index=["one", "two"],
        columns=MultiIndex.from_tuples(
            [("a", "q"), ("a", "r"), ("a", "s"), ("b", "t"), ("c", "u"), ("c", "v")]
        ),
    )
    data = """,a,a,a,b,c,c
,q,r,s,t,u,v
,,,,,,
one,1,2,3,4,5,6
two,7,8,9,10,11,12"""

    result = parser.read_csv(StringIO(data), index_col=0, **kwargs)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"header": [0, 1]},
        {
            "skiprows": 2,
            "names": [
                ("a", "q"),
                ("a", "r"),
                ("a", "s"),
                ("b", "t"),
                ("c", "u"),
                ("c", "v"),
            ],
        },
        {
            "skiprows": 2,
            "names": [
                _TestTuple("a", "q"),
                _TestTuple("a", "r"),
                _TestTuple("a", "s"),
                _TestTuple("b", "t"),
                _TestTuple("c", "u"),
                _TestTuple("c", "v"),
            ],
        },
    ],
)
def test_header_multi_index_common_format2(all_parsers, kwargs):
    parser = all_parsers
    expected = DataFrame(
        [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]],
        index=["one", "two"],
        columns=MultiIndex.from_tuples(
            [("a", "q"), ("a", "r"), ("a", "s"), ("b", "t"), ("c", "u"), ("c", "v")]
        ),
    )
    data = """,a,a,a,b,c,c
,q,r,s,t,u,v
one,1,2,3,4,5,6
two,7,8,9,10,11,12"""

    result = parser.read_csv(StringIO(data), index_col=0, **kwargs)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"header": [0, 1]},
        {
            "skiprows": 2,
            "names": [
                ("a", "q"),
                ("a", "r"),
                ("a", "s"),
                ("b", "t"),
                ("c", "u"),
                ("c", "v"),
            ],
        },
        {
            "skiprows": 2,
            "names": [
                _TestTuple("a", "q"),
                _TestTuple("a", "r"),
                _TestTuple("a", "s"),
                _TestTuple("b", "t"),
                _TestTuple("c", "u"),
                _TestTuple("c", "v"),
            ],
        },
    ],
)
def test_header_multi_index_common_format3(all_parsers, kwargs):
    parser = all_parsers
    expected = DataFrame(
        [[1, 2, 3, 4, 5, 6], [7, 8, 9, 10, 11, 12]],
        index=["one", "two"],
        columns=MultiIndex.from_tuples(
            [("a", "q"), ("a", "r"), ("a", "s"), ("b", "t"), ("c", "u"), ("c", "v")]
        ),
    )
    expected = expected.reset_index(drop=True)
    data = """a,a,a,b,c,c
q,r,s,t,u,v
1,2,3,4,5,6
7,8,9,10,11,12"""

    result = parser.read_csv(StringIO(data), index_col=None, **kwargs)
    tm.assert_frame_equal(result, expected)


def test_header_multi_index_common_format_malformed1(all_parsers):
    parser = all_parsers
    expected = DataFrame(
        np.array([[2, 3, 4, 5, 6], [8, 9, 10, 11, 12]], dtype="int64"),
        index=Index([1, 7]),
        columns=MultiIndex(
            levels=[["a", "b", "c"], ["r", "s", "t", "u", "v"]],
            codes=[[0, 0, 1, 2, 2], [0, 1, 2, 3, 4]],
            names=["a", "q"],
        ),
    )
    data = """a,a,a,b,c,c
q,r,s,t,u,v
1,2,3,4,5,6
7,8,9,10,11,12"""

    result = parser.read_csv(StringIO(data), header=[0, 1], index_col=0)
    tm.assert_frame_equal(expected, result)


def test_header_multi_index_common_format_malformed2(all_parsers):
    parser = all_parsers
    expected = DataFrame(
        np.array([[2, 3, 4, 5, 6], [8, 9, 10, 11, 12]], dtype="int64"),
        index=Index([1, 7]),
        columns=MultiIndex(
            levels=[["a", "b", "c"], ["r", "s", "t", "u", "v"]],
            codes=[[0, 0, 1, 2, 2], [0, 1, 2, 3, 4]],
            names=[None, "q"],
        ),
    )

    data = """,a,a,b,c,c
q,r,s,t,u,v
1,2,3,4,5,6
7,8,9,10,11,12"""

    result = parser.read_csv(StringIO(data), header=[0, 1], index_col=0)
    tm.assert_frame_equal(expected, result)


def test_header_multi_index_common_format_malformed3(all_parsers):
    parser = all_parsers
    expected = DataFrame(
        np.array([[3, 4, 5, 6], [9, 10, 11, 12]], dtype="int64"),
        index=MultiIndex(levels=[[1, 7], [2, 8]], codes=[[0, 1], [0, 1]]),
        columns=MultiIndex(
            levels=[["a", "b", "c"], ["s", "t", "u", "v"]],
            codes=[[0, 1, 2, 2], [0, 1, 2, 3]],
            names=[None, "q"],
        ),
    )
    data = """,a,a,b,c,c
q,r,s,t,u,v
1,2,3,4,5,6
7,8,9,10,11,12"""

    result = parser.read_csv(StringIO(data), header=[0, 1], index_col=[0, 1])
    tm.assert_frame_equal(expected, result)


@pytest.mark.parametrize(
    "data,header", [("1,2,3\n4,5,6", None), ("foo,bar,baz\n1,2,3\n4,5,6", 0)]
)
def test_header_names_backward_compat(all_parsers, data, header):
    # see gh-2539
    parser = all_parsers
    expected = parser.read_csv(StringIO("1,2,3\n4,5,6"), names=["a", "b", "c"])

    result = parser.read_csv(StringIO(data), names=["a", "b", "c"], header=header)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("kwargs", [{}, {"index_col": False}])
def test_read_only_header_no_rows(all_parsers, kwargs):
    # See gh-7773
    parser = all_parsers
    expected = DataFrame(columns=["a", "b", "c"])

    result = parser.read_csv(StringIO("a,b,c"), **kwargs)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "kwargs,names",
    [
        ({}, [0, 1, 2, 3, 4]),
        ({"prefix": "X"}, ["X0", "X1", "X2", "X3", "X4"]),
        (
            {"names": ["foo", "bar", "baz", "quux", "panda"]},
            ["foo", "bar", "baz", "quux", "panda"],
        ),
    ],
)
def test_no_header(all_parsers, kwargs, names):
    parser = all_parsers
    data = """1,2,3,4,5
6,7,8,9,10
11,12,13,14,15
"""
    expected = DataFrame(
        [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10], [11, 12, 13, 14, 15]], columns=names
    )
    result = parser.read_csv(StringIO(data), header=None, **kwargs)
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("header", [["a", "b"], "string_header"])
def test_non_int_header(all_parsers, header):
    # see gh-16338
    msg = "header must be integer or list of integers"
    data = """1,2\n3,4"""
    parser = all_parsers

    with pytest.raises(ValueError, match=msg):
        parser.read_csv(StringIO(data), header=header)


def test_singleton_header(all_parsers):
    # see gh-7757
    data = """a,b,c\n0,1,2\n1,2,3"""
    parser = all_parsers

    expected = DataFrame({"a": [0, 1], "b": [1, 2], "c": [2, 3]})
    result = parser.read_csv(StringIO(data), header=[0])
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize(
    "data,expected",
    [
        (
            "A,A,A,B\none,one,one,two\n0,40,34,0.1",
            DataFrame(
                [[0, 40, 34, 0.1]],
                columns=MultiIndex.from_tuples(
                    [("A", "one"), ("A", "one.1"), ("A", "one.2"), ("B", "two")]
                ),
            ),
        ),
        (
            "A,A,A,B\none,one,one.1,two\n0,40,34,0.1",
            DataFrame(
                [[0, 40, 34, 0.1]],
                columns=MultiIndex.from_tuples(
                    [("A", "one"), ("A", "one.1"), ("A", "one.1.1"), ("B", "two")]
                ),
            ),
        ),
        (
            "A,A,A,B,B\none,one,one.1,two,two\n0,40,34,0.1,0.1",
            DataFrame(
                [[0, 40, 34, 0.1, 0.1]],
                columns=MultiIndex.from_tuples(
                    [
                        ("A", "one"),
                        ("A", "one.1"),
                        ("A", "one.1.1"),
                        ("B", "two"),
                        ("B", "two.1"),
                    ]
                ),
            ),
        ),
    ],
)
def test_mangles_multi_index(all_parsers, data, expected):
    # see gh-18062
    parser = all_parsers

    result = parser.read_csv(StringIO(data), header=[0, 1])
    tm.assert_frame_equal(result, expected)


@pytest.mark.parametrize("index_col", [None, [0]])
@pytest.mark.parametrize(
    "columns", [None, (["", "Unnamed"]), (["Unnamed", ""]), (["Unnamed", "NotUnnamed"])]
)
def test_multi_index_unnamed(all_parsers, index_col, columns):
    # see gh-23687
    #
    # When specifying a multi-index header, make sure that
    # we don't error just because one of the rows in our header
    # has ALL column names containing the string "Unnamed". The
    # correct condition to check is whether the row contains
    # ALL columns that did not have names (and instead were given
    # placeholder ones).
    parser = all_parsers
    header = [0, 1]

    if index_col is None:
        data = ",".join(columns or ["", ""]) + "\n0,1\n2,3\n4,5\n"
    else:
        data = ",".join([""] + (columns or ["", ""])) + "\n,0,1\n0,2,3\n1,4,5\n"

    if columns is None:
        msg = (
            r"Passed header=\[0,1\] are too "
            r"many rows for this multi_index of columns"
        )
        with pytest.raises(ParserError, match=msg):
            parser.read_csv(StringIO(data), header=header, index_col=index_col)
    else:
        result = parser.read_csv(StringIO(data), header=header, index_col=index_col)
        exp_columns = []

        for i, col in enumerate(columns):
            if not col:  # Unnamed.
                col = f"Unnamed: {i if index_col is None else i + 1}_level_0"

            exp_columns.append(col)

        columns = MultiIndex.from_tuples(zip(exp_columns, ["0", "1"]))
        expected = DataFrame([[2, 3], [4, 5]], columns=columns)
        tm.assert_frame_equal(result, expected)


def test_read_csv_multiindex_columns(all_parsers):
    # GH#6051
    parser = all_parsers

    s1 = "Male, Male, Male, Female, Female\nR, R, L, R, R\n.86, .67, .88, .78, .81"
    s2 = (
        "Male, Male, Male, Female, Female\n"
        "R, R, L, R, R\n"
        ".86, .67, .88, .78, .81\n"
        ".86, .67, .88, .78, .82"
    )

    mi = MultiIndex.from_tuples(
        [
            ("Male", "R"),
            (" Male", " R"),
            (" Male", " L"),
            (" Female", " R"),
            (" Female", " R.1"),
        ]
    )
    expected = DataFrame(
        [[0.86, 0.67, 0.88, 0.78, 0.81], [0.86, 0.67, 0.88, 0.78, 0.82]], columns=mi
    )

    df1 = parser.read_csv(StringIO(s1), header=[0, 1])
    tm.assert_frame_equal(df1, expected.iloc[:1])
    df2 = parser.read_csv(StringIO(s2), header=[0, 1])
    tm.assert_frame_equal(df2, expected)
