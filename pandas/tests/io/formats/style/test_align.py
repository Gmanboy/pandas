import numpy as np
import pytest

from pandas import DataFrame

pytest.importorskip("jinja2")


def bar_grad(a=None, b=None, c=None, d=None):
    """Used in multiple tests to simplify formatting of expected result"""
    ret = [("width", "10em")]
    if all(x is None for x in [a, b, c, d]):
        return ret
    return ret + [
        (
            "background",
            f"linear-gradient(90deg,{','.join([x for x in [a, b, c, d] if x])})",
        )
    ]


def no_bar():
    return bar_grad()


def bar_to(x):
    return bar_grad(f" #d65f5f {x:.1f}%", f" transparent {x:.1f}%")


def bar_from_to(x, y):
    return bar_grad(
        f" transparent {x:.1f}%",
        f" #d65f5f {x:.1f}%",
        f" #d65f5f {y:.1f}%",
        f" transparent {y:.1f}%",
    )


class TestStylerBarAlign:
    def test_bar_align_left(self):
        df = DataFrame({"A": [0, 1, 2]})
        result = df.style.bar(align="left")._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (1, 0): bar_grad(" #d65f5f 50.0%", " transparent 50.0%"),
            (2, 0): bar_grad(" #d65f5f 100.0%", " transparent 100.0%"),
        }
        assert result == expected

        result = df.style.bar(color="red", width=50, align="left")._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (1, 0): bar_grad(" red 25.0%", " transparent 25.0%"),
            (2, 0): bar_grad(" red 50.0%", " transparent 50.0%"),
        }
        assert result == expected

        df["C"] = ["a"] * len(df)
        result = df.style.bar(color="red", width=50, align="left")._compute().ctx
        assert result == expected
        df["C"] = df["C"].astype("category")
        result = df.style.bar(color="red", width=50, align="left")._compute().ctx
        assert result == expected

    def test_bar_align_left_0points(self):
        df = DataFrame([[1, 2, 3], [4, 5, 6], [7, 8, 9]])
        result = df.style.bar(align="left")._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (0, 1): bar_grad(),
            (0, 2): bar_grad(),
            (1, 0): bar_grad(" #d65f5f 50.0%", " transparent 50.0%"),
            (1, 1): bar_grad(" #d65f5f 50.0%", " transparent 50.0%"),
            (1, 2): bar_grad(" #d65f5f 50.0%", " transparent 50.0%"),
            (2, 0): bar_grad(" #d65f5f 100.0%", " transparent 100.0%"),
            (2, 1): bar_grad(" #d65f5f 100.0%", " transparent 100.0%"),
            (2, 2): bar_grad(" #d65f5f 100.0%", " transparent 100.0%"),
        }
        assert result == expected

        result = df.style.bar(axis=1, align="left")._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (0, 1): bar_grad(" #d65f5f 50.0%", " transparent 50.0%"),
            (0, 2): bar_grad(" #d65f5f 100.0%", " transparent 100.0%"),
            (1, 0): bar_grad(),
            (1, 1): bar_grad(" #d65f5f 50.0%", " transparent 50.0%"),
            (1, 2): bar_grad(" #d65f5f 100.0%", " transparent 100.0%"),
            (2, 0): bar_grad(),
            (2, 1): bar_grad(" #d65f5f 50.0%", " transparent 50.0%"),
            (2, 2): bar_grad(" #d65f5f 100.0%", " transparent 100.0%"),
        }
        assert result == expected

    def test_bar_align_mid_pos_and_neg(self):
        df = DataFrame({"A": [-10, 0, 20, 90]})
        result = df.style.bar(align="mid", color=["#d65f5f", "#5fba7d"])._compute().ctx
        expected = {
            (0, 0): bar_grad(
                " #d65f5f 10.0%",
                " transparent 10.0%",
            ),
            (1, 0): bar_grad(),
            (2, 0): bar_grad(
                " transparent 10.0%",
                " #5fba7d 10.0%",
                " #5fba7d 30.0%",
                " transparent 30.0%",
            ),
            (3, 0): bar_grad(
                " transparent 10.0%",
                " #5fba7d 10.0%",
                " #5fba7d 100.0%",
                " transparent 100.0%",
            ),
        }
        assert result == expected

    def test_bar_align_mid_all_pos(self):
        df = DataFrame({"A": [10, 20, 50, 100]})

        result = df.style.bar(align="mid", color=["#d65f5f", "#5fba7d"])._compute().ctx

        expected = {
            (0, 0): bar_grad(
                " #5fba7d 10.0%",
                " transparent 10.0%",
            ),
            (1, 0): bar_grad(
                " #5fba7d 20.0%",
                " transparent 20.0%",
            ),
            (2, 0): bar_grad(
                " #5fba7d 50.0%",
                " transparent 50.0%",
            ),
            (3, 0): bar_grad(
                " #5fba7d 100.0%",
                " transparent 100.0%",
            ),
        }

        assert result == expected

    def test_bar_align_mid_all_neg(self):
        df = DataFrame({"A": [-100, -60, -30, -20]})

        result = df.style.bar(align="mid", color=["#d65f5f", "#5fba7d"])._compute().ctx

        expected = {
            (0, 0): bar_grad(
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
            (1, 0): bar_grad(
                " transparent 40.0%",
                " #d65f5f 40.0%",
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
            (2, 0): bar_grad(
                " transparent 70.0%",
                " #d65f5f 70.0%",
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
            (3, 0): bar_grad(
                " transparent 80.0%",
                " #d65f5f 80.0%",
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
        }
        assert result == expected

    def test_bar_align_zero_pos_and_neg(self):
        # See https://github.com/pandas-dev/pandas/pull/14757
        df = DataFrame({"A": [-10, 0, 20, 90]})

        result = (
            df.style.bar(align="zero", color=["#d65f5f", "#5fba7d"], width=90)
            ._compute()
            .ctx
        )
        expected = {
            (0, 0): bar_grad(
                " transparent 40.0%",
                " #d65f5f 40.0%",
                " #d65f5f 45.0%",
                " transparent 45.0%",
            ),
            (1, 0): bar_grad(),
            (2, 0): bar_grad(
                " transparent 45.0%",
                " #5fba7d 45.0%",
                " #5fba7d 55.0%",
                " transparent 55.0%",
            ),
            (3, 0): bar_grad(
                " transparent 45.0%",
                " #5fba7d 45.0%",
                " #5fba7d 90.0%",
                " transparent 90.0%",
            ),
        }
        assert result == expected

    def test_bar_align_left_axis_none(self):
        df = DataFrame({"A": [0, 1], "B": [2, 4]})
        result = df.style.bar(axis=None, align="left")._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (1, 0): bar_grad(
                " #d65f5f 25.0%",
                " transparent 25.0%",
            ),
            (0, 1): bar_grad(
                " #d65f5f 50.0%",
                " transparent 50.0%",
            ),
            (1, 1): bar_grad(
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
        }
        assert result == expected

    def test_bar_align_zero_axis_none(self):
        df = DataFrame({"A": [0, 1], "B": [-2, 4]})
        result = df.style.bar(align="zero", axis=None)._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (1, 0): bar_grad(
                " transparent 50.0%",
                " #d65f5f 50.0%",
                " #d65f5f 62.5%",
                " transparent 62.5%",
            ),
            (0, 1): bar_grad(
                " transparent 25.0%",
                " #d65f5f 25.0%",
                " #d65f5f 50.0%",
                " transparent 50.0%",
            ),
            (1, 1): bar_grad(
                " transparent 50.0%",
                " #d65f5f 50.0%",
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
        }
        assert result == expected

    def test_bar_align_mid_axis_none(self):
        df = DataFrame({"A": [0, 1], "B": [-2, 4]})
        result = df.style.bar(align="mid", axis=None)._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (1, 0): bar_grad(
                " transparent 33.3%",
                " #d65f5f 33.3%",
                " #d65f5f 50.0%",
                " transparent 50.0%",
            ),
            (0, 1): bar_grad(
                " #d65f5f 33.3%",
                " transparent 33.3%",
            ),
            (1, 1): bar_grad(
                " transparent 33.3%",
                " #d65f5f 33.3%",
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
        }
        assert result == expected

    def test_bar_align_mid_vmin(self):
        df = DataFrame({"A": [0, 1], "B": [-2, 4]})
        result = df.style.bar(align="mid", axis=None, vmin=-6)._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (1, 0): bar_grad(
                " transparent 60.0%",
                " #d65f5f 60.0%",
                " #d65f5f 70.0%",
                " transparent 70.0%",
            ),
            (0, 1): bar_grad(
                " transparent 40.0%",
                " #d65f5f 40.0%",
                " #d65f5f 60.0%",
                " transparent 60.0%",
            ),
            (1, 1): bar_grad(
                " transparent 60.0%",
                " #d65f5f 60.0%",
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
        }
        assert result == expected

    def test_bar_align_mid_vmax(self):
        df = DataFrame({"A": [0, 1], "B": [-2, 4]})
        result = df.style.bar(align="mid", axis=None, vmax=8)._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (1, 0): bar_grad(
                " transparent 20.0%",
                " #d65f5f 20.0%",
                " #d65f5f 30.0%",
                " transparent 30.0%",
            ),
            (0, 1): bar_grad(
                " #d65f5f 20.0%",
                " transparent 20.0%",
            ),
            (1, 1): bar_grad(
                " transparent 20.0%",
                " #d65f5f 20.0%",
                " #d65f5f 60.0%",
                " transparent 60.0%",
            ),
        }
        assert result == expected

    def test_bar_align_mid_vmin_vmax_wide(self):
        df = DataFrame({"A": [0, 1], "B": [-2, 4]})
        result = df.style.bar(align="mid", axis=None, vmin=-3, vmax=7)._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (1, 0): bar_grad(
                " transparent 30.0%",
                " #d65f5f 30.0%",
                " #d65f5f 40.0%",
                " transparent 40.0%",
            ),
            (0, 1): bar_grad(
                " transparent 10.0%",
                " #d65f5f 10.0%",
                " #d65f5f 30.0%",
                " transparent 30.0%",
            ),
            (1, 1): bar_grad(
                " transparent 30.0%",
                " #d65f5f 30.0%",
                " #d65f5f 70.0%",
                " transparent 70.0%",
            ),
        }
        assert result == expected

    def test_bar_align_mid_vmin_vmax_clipping(self):
        df = DataFrame({"A": [0, 1], "B": [-2, 4]})
        result = df.style.bar(align="mid", axis=None, vmin=-1, vmax=3)._compute().ctx
        expected = {
            (0, 0): bar_grad(),
            (1, 0): bar_grad(
                " transparent 25.0%",
                " #d65f5f 25.0%",
                " #d65f5f 50.0%",
                " transparent 50.0%",
            ),
            (0, 1): bar_grad(" #d65f5f 25.0%", " transparent 25.0%"),
            (1, 1): bar_grad(
                " transparent 25.0%",
                " #d65f5f 25.0%",
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
        }
        assert result == expected

    def test_bar_align_mid_nans(self):
        df = DataFrame({"A": [1, None], "B": [-1, 3]})
        result = df.style.bar(align="mid", axis=None)._compute().ctx
        expected = {
            (0, 0): bar_grad(
                " transparent 25.0%",
                " #d65f5f 25.0%",
                " #d65f5f 50.0%",
                " transparent 50.0%",
            ),
            (0, 1): bar_grad(" #d65f5f 25.0%", " transparent 25.0%"),
            (1, 0): bar_grad(),
            (1, 1): bar_grad(
                " transparent 25.0%",
                " #d65f5f 25.0%",
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
        }
        assert result == expected

    def test_bar_align_zero_nans(self):
        df = DataFrame({"A": [1, None], "B": [-1, 2]})
        result = df.style.bar(align="zero", axis=None)._compute().ctx
        expected = {
            (0, 0): bar_grad(
                " transparent 50.0%",
                " #d65f5f 50.0%",
                " #d65f5f 75.0%",
                " transparent 75.0%",
            ),
            (0, 1): bar_grad(
                " transparent 25.0%",
                " #d65f5f 25.0%",
                " #d65f5f 50.0%",
                " transparent 50.0%",
            ),
            (1, 0): bar_grad(),
            (1, 1): bar_grad(
                " transparent 50.0%",
                " #d65f5f 50.0%",
                " #d65f5f 100.0%",
                " transparent 100.0%",
            ),
        }
        assert result == expected

    def test_bar_bad_align_raises(self):
        df = DataFrame({"A": [-100, -60, -30, -20]})
        msg = "`align` should be in {'left', 'right', 'mid', 'mean', 'zero'} or"
        with pytest.raises(ValueError, match=msg):
            df.style.bar(align="poorly", color=["#d65f5f", "#5fba7d"]).render()


@pytest.mark.parametrize(
    "align, exp",
    [
        ("left", [no_bar(), bar_to(50), bar_to(100)]),
        ("right", [bar_to(100), bar_from_to(50, 100), no_bar()]),
        ("mid", [bar_to(33.33), bar_to(66.66), bar_to(100)]),
        ("zero", [bar_from_to(50, 66.7), bar_from_to(50, 83.3), bar_from_to(50, 100)]),
        ("mean", [bar_to(50), no_bar(), bar_from_to(50, 100)]),
        (2.0, [bar_to(50), no_bar(), bar_from_to(50, 100)]),
        (np.median, [bar_to(50), no_bar(), bar_from_to(50, 100)]),
    ],
)
def test_bar_align_positive_cases(align, exp):
    # test different align cases for all positive values
    data = DataFrame([[1], [2], [3]])
    result = data.style.bar(align=align)._compute().ctx
    expected = {(0, 0): exp[0], (1, 0): exp[1], (2, 0): exp[2]}
    assert result == expected


@pytest.mark.parametrize(
    "align, exp",
    [
        ("left", [bar_to(100), bar_to(50), no_bar()]),
        ("right", [no_bar(), bar_from_to(50, 100), bar_to(100)]),
        ("mid", [bar_from_to(66.66, 100), bar_from_to(33.33, 100), bar_to(100)]),
        ("zero", [bar_from_to(33.33, 50), bar_from_to(16.66, 50), bar_to(50)]),
        ("mean", [bar_from_to(50, 100), no_bar(), bar_to(50)]),
        (-2.0, [bar_from_to(50, 100), no_bar(), bar_to(50)]),
        (np.median, [bar_from_to(50, 100), no_bar(), bar_to(50)]),
    ],
)
def test_bar_align_negative_cases(align, exp):
    # test different align cases for all negative values
    data = DataFrame([[-1], [-2], [-3]])
    result = data.style.bar(align=align)._compute().ctx
    expected = {(0, 0): exp[0], (1, 0): exp[1], (2, 0): exp[2]}
    assert result == expected


@pytest.mark.parametrize(
    "align, exp",
    [
        ("left", [no_bar(), bar_to(80), bar_to(100)]),
        ("right", [bar_to(100), bar_from_to(80, 100), no_bar()]),
        ("mid", [bar_to(60), bar_from_to(60, 80), bar_from_to(60, 100)]),
        ("zero", [bar_to(50), bar_from_to(50, 66.66), bar_from_to(50, 83.33)]),
        ("mean", [bar_to(50), bar_from_to(50, 66.66), bar_from_to(50, 83.33)]),
        (-0.0, [bar_to(50), bar_from_to(50, 66.66), bar_from_to(50, 83.33)]),
        (np.median, [bar_to(50), no_bar(), bar_from_to(50, 62.5)]),
    ],
)
def test_bar_align_mixed_cases(align, exp):
    # test different align cases for mixed positive and negative values
    data = DataFrame([[-3], [1], [2]])
    result = data.style.bar(align=align)._compute().ctx
    expected = {(0, 0): exp[0], (1, 0): exp[1], (2, 0): exp[2]}
    assert result == expected
