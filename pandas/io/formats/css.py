"""
Utilities for interpreting CSS from Stylers for formatting non-HTML outputs.
"""

import re
from typing import Optional
import warnings


class CSSWarning(UserWarning):
    """
    This CSS syntax cannot currently be parsed.
    """

    pass


def _side_expander(prop_fmt: str):
    def expand(self, prop, value: str):
        tokens = value.split()
        try:
            mapping = self.SIDE_SHORTHANDS[len(tokens)]
        except KeyError:
            warnings.warn(f'Could not expand "{prop}: {value}"', CSSWarning)
            return
        for key, idx in zip(self.SIDES, mapping):
            yield prop_fmt.format(key), tokens[idx]

    return expand


class CSSResolver:
    """
    A callable for parsing and resolving CSS to atomic properties.
    """

    def __call__(self, declarations_str, inherited=None):
        """
        The given declarations to atomic properties.

        Parameters
        ----------
        declarations_str : str
            A list of CSS declarations
        inherited : dict, optional
            Atomic properties indicating the inherited style context in which
            declarations_str is to be resolved. ``inherited`` should already
            be resolved, i.e. valid output of this method.

        Returns
        -------
        dict
            Atomic CSS 2.2 properties.

        Examples
        --------
        >>> resolve = CSSResolver()
        >>> inherited = {'font-family': 'serif', 'font-weight': 'bold'}
        >>> out = resolve('''
        ...               border-color: BLUE RED;
        ...               font-size: 1em;
        ...               font-size: 2em;
        ...               font-weight: normal;
        ...               font-weight: inherit;
        ...               ''', inherited)
        >>> sorted(out.items())  # doctest: +NORMALIZE_WHITESPACE
        [('border-bottom-color', 'blue'),
         ('border-left-color', 'red'),
         ('border-right-color', 'red'),
         ('border-top-color', 'blue'),
         ('font-family', 'serif'),
         ('font-size', '24pt'),
         ('font-weight', 'bold')]
        """
        props = dict(self.atomize(self.parse(declarations_str)))
        if inherited is None:
            inherited = {}

        # 1. resolve inherited, initial
        for prop, val in inherited.items():
            if prop not in props:
                props[prop] = val

        for prop, val in list(props.items()):
            if val == "inherit":
                val = inherited.get(prop, "initial")
            if val == "initial":
                val = None

            if val is None:
                # we do not define a complete initial stylesheet
                del props[prop]
            else:
                props[prop] = val

        # 2. resolve relative font size
        font_size: Optional[float]
        if props.get("font-size"):
            if "font-size" in inherited:
                em_pt = inherited["font-size"]
                assert em_pt[-2:] == "pt"
                em_pt = float(em_pt[:-2])
            else:
                em_pt = None
            props["font-size"] = self.size_to_pt(
                props["font-size"], em_pt, conversions=self.FONT_SIZE_RATIOS
            )

            font_size = float(props["font-size"][:-2])
        else:
            font_size = None

        # 3. TODO: resolve other font-relative units
        for side in self.SIDES:
            prop = f"border-{side}-width"
            if prop in props:
                props[prop] = self.size_to_pt(
                    props[prop], em_pt=font_size, conversions=self.BORDER_WIDTH_RATIOS
                )
            for prop in [f"margin-{side}", f"padding-{side}"]:
                if prop in props:
                    # TODO: support %
                    props[prop] = self.size_to_pt(
                        props[prop], em_pt=font_size, conversions=self.MARGIN_RATIOS
                    )

        return props

    UNIT_RATIOS = {
        "rem": ("pt", 12),
        "ex": ("em", 0.5),
        # 'ch':
        "px": ("pt", 0.75),
        "pc": ("pt", 12),
        "in": ("pt", 72),
        "cm": ("in", 1 / 2.54),
        "mm": ("in", 1 / 25.4),
        "q": ("mm", 0.25),
        "!!default": ("em", 0),
    }

    FONT_SIZE_RATIOS = UNIT_RATIOS.copy()
    FONT_SIZE_RATIOS.update(
        {
            "%": ("em", 0.01),
            "xx-small": ("rem", 0.5),
            "x-small": ("rem", 0.625),
            "small": ("rem", 0.8),
            "medium": ("rem", 1),
            "large": ("rem", 1.125),
            "x-large": ("rem", 1.5),
            "xx-large": ("rem", 2),
            "smaller": ("em", 1 / 1.2),
            "larger": ("em", 1.2),
            "!!default": ("em", 1),
        }
    )

    MARGIN_RATIOS = UNIT_RATIOS.copy()
    MARGIN_RATIOS.update({"none": ("pt", 0)})

    BORDER_WIDTH_RATIOS = UNIT_RATIOS.copy()
    BORDER_WIDTH_RATIOS.update(
        {
            "none": ("pt", 0),
            "thick": ("px", 4),
            "medium": ("px", 2),
            "thin": ("px", 1),
            # Default: medium only if solid
        }
    )

    def size_to_pt(self, in_val, em_pt=None, conversions=UNIT_RATIOS):
        def _error():
            warnings.warn(f"Unhandled size: {repr(in_val)}", CSSWarning)
            return self.size_to_pt("1!!default", conversions=conversions)

        match = re.match(r"^(\S*?)([a-zA-Z%!].*)", in_val)
        if match is None:
            return _error()

        val, unit = match.groups()
        if val == "":
            # hack for 'large' etc.
            val = 1
        else:
            try:
                val = float(val)
            except ValueError:
                return _error()

        while unit != "pt":
            if unit == "em":
                if em_pt is None:
                    unit = "rem"
                else:
                    val *= em_pt
                    unit = "pt"
                continue

            try:
                unit, mul = conversions[unit]
            except KeyError:
                return _error()
            val *= mul

        val = round(val, 5)
        if int(val) == val:
            size_fmt = f"{int(val):d}pt"
        else:
            size_fmt = f"{val:f}pt"
        return size_fmt

    def atomize(self, declarations):
        for prop, value in declarations:
            attr = "expand_" + prop.replace("-", "_")
            try:
                expand = getattr(self, attr)
            except AttributeError:
                yield prop, value
            else:
                for prop, value in expand(prop, value):
                    yield prop, value

    SIDE_SHORTHANDS = {
        1: [0, 0, 0, 0],
        2: [0, 1, 0, 1],
        3: [0, 1, 2, 1],
        4: [0, 1, 2, 3],
    }
    SIDES = ("top", "right", "bottom", "left")

    expand_border_color = _side_expander("border-{:s}-color")
    expand_border_style = _side_expander("border-{:s}-style")
    expand_border_width = _side_expander("border-{:s}-width")
    expand_margin = _side_expander("margin-{:s}")
    expand_padding = _side_expander("padding-{:s}")

    def parse(self, declarations_str: str):
        """
        Generates (prop, value) pairs from declarations.

        In a future version may generate parsed tokens from tinycss/tinycss2

        Parameters
        ----------
        declarations_str : str
        """
        for decl in declarations_str.split(";"):
            if not decl.strip():
                continue
            prop, sep, val = decl.partition(":")
            prop = prop.strip().lower()
            # TODO: don't lowercase case sensitive parts of values (strings)
            val = val.strip().lower()
            if sep:
                yield prop, val
            else:
                warnings.warn(
                    f"Ill-formatted attribute: expected a colon in {repr(decl)}",
                    CSSWarning,
                )
