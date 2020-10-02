"""
Tests for CategoricalIndex.__repr__ and related methods.
"""
import pandas._config.config as cf

import pandas as pd


class TestCategoricalIndexRepr:
    def test_string_categorical_index_repr(self):
        # short
        idx = pd.CategoricalIndex(["a", "bb", "ccc"])
        expected = """CategoricalIndex(['a', 'bb', 'ccc'], categories=['a', 'bb', 'ccc'], ordered=False, dtype='category')"""  # noqa
        assert repr(idx) == expected

        # multiple lines
        idx = pd.CategoricalIndex(["a", "bb", "ccc"] * 10)
        expected = """CategoricalIndex(['a', 'bb', 'ccc', 'a', 'bb', 'ccc', 'a', 'bb', 'ccc', 'a',
                  'bb', 'ccc', 'a', 'bb', 'ccc', 'a', 'bb', 'ccc', 'a', 'bb',
                  'ccc', 'a', 'bb', 'ccc', 'a', 'bb', 'ccc', 'a', 'bb', 'ccc'],
                 categories=['a', 'bb', 'ccc'], ordered=False, dtype='category')"""

        assert repr(idx) == expected

        # truncated
        idx = pd.CategoricalIndex(["a", "bb", "ccc"] * 100)
        expected = """CategoricalIndex(['a', 'bb', 'ccc', 'a', 'bb', 'ccc', 'a', 'bb', 'ccc', 'a',
                  ...
                  'ccc', 'a', 'bb', 'ccc', 'a', 'bb', 'ccc', 'a', 'bb', 'ccc'],
                 categories=['a', 'bb', 'ccc'], ordered=False, dtype='category', length=300)"""  # noqa

        assert repr(idx) == expected

        # larger categories
        idx = pd.CategoricalIndex(list("abcdefghijklmmo"))
        expected = """CategoricalIndex(['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l',
                  'm', 'm', 'o'],
                 categories=['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', ...], ordered=False, dtype='category')"""  # noqa

        assert repr(idx) == expected

        # short
        idx = pd.CategoricalIndex(["あ", "いい", "ううう"])
        expected = """CategoricalIndex(['あ', 'いい', 'ううう'], categories=['あ', 'いい', 'ううう'], ordered=False, dtype='category')"""  # noqa
        assert repr(idx) == expected

        # multiple lines
        idx = pd.CategoricalIndex(["あ", "いい", "ううう"] * 10)
        expected = """CategoricalIndex(['あ', 'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ',
                  'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい',
                  'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう'],
                 categories=['あ', 'いい', 'ううう'], ordered=False, dtype='category')"""

        assert repr(idx) == expected

        # truncated
        idx = pd.CategoricalIndex(["あ", "いい", "ううう"] * 100)
        expected = """CategoricalIndex(['あ', 'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ',
                  ...
                  'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう'],
                 categories=['あ', 'いい', 'ううう'], ordered=False, dtype='category', length=300)"""  # noqa

        assert repr(idx) == expected

        # larger categories
        idx = pd.CategoricalIndex(list("あいうえおかきくけこさしすせそ"))
        expected = """CategoricalIndex(['あ', 'い', 'う', 'え', 'お', 'か', 'き', 'く', 'け', 'こ', 'さ', 'し',
                  'す', 'せ', 'そ'],
                 categories=['あ', 'い', 'う', 'え', 'お', 'か', 'き', 'く', ...], ordered=False, dtype='category')"""  # noqa

        assert repr(idx) == expected

        # Emable Unicode option -----------------------------------------
        with cf.option_context("display.unicode.east_asian_width", True):

            # short
            idx = pd.CategoricalIndex(["あ", "いい", "ううう"])
            expected = """CategoricalIndex(['あ', 'いい', 'ううう'], categories=['あ', 'いい', 'ううう'], ordered=False, dtype='category')"""  # noqa
            assert repr(idx) == expected

            # multiple lines
            idx = pd.CategoricalIndex(["あ", "いい", "ううう"] * 10)
            expected = """CategoricalIndex(['あ', 'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい',
                  'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう',
                  'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい',
                  'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう'],
                 categories=['あ', 'いい', 'ううう'], ordered=False, dtype='category')"""

            assert repr(idx) == expected

            # truncated
            idx = pd.CategoricalIndex(["あ", "いい", "ううう"] * 100)
            expected = """CategoricalIndex(['あ', 'いい', 'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい',
                  'ううう', 'あ',
                  ...
                  'ううう', 'あ', 'いい', 'ううう', 'あ', 'いい', 'ううう',
                  'あ', 'いい', 'ううう'],
                 categories=['あ', 'いい', 'ううう'], ordered=False, dtype='category', length=300)"""  # noqa

            assert repr(idx) == expected

            # larger categories
            idx = pd.CategoricalIndex(list("あいうえおかきくけこさしすせそ"))
            expected = """CategoricalIndex(['あ', 'い', 'う', 'え', 'お', 'か', 'き', 'く', 'け', 'こ',
                  'さ', 'し', 'す', 'せ', 'そ'],
                 categories=['あ', 'い', 'う', 'え', 'お', 'か', 'き', 'く', ...], ordered=False, dtype='category')"""  # noqa

            assert repr(idx) == expected
