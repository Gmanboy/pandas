#
# pandas documentation build configuration file, created by
#
# This file is execfile()d with the current directory set to its containing
# dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.

from datetime import datetime
import importlib
import inspect
import logging
import os
import sys

import jinja2
from numpydoc.docscrape import NumpyDocString
from sphinx.ext.autosummary import _import_by_name

logger = logging.getLogger(__name__)

# https://github.com/sphinx-doc/sphinx/pull/2325/files
# Workaround for sphinx-build recursion limit overflow:
# pickle.dump(doctree, f, pickle.HIGHEST_PROTOCOL)
#  RuntimeError: maximum recursion depth exceeded while pickling an object
#
# Python's default allowed recursion depth is 1000.
sys.setrecursionlimit(5000)

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
# sys.path.append(os.path.abspath('.'))
sys.path.insert(0, os.path.abspath("../sphinxext"))
sys.path.extend(
    [
        # numpy standard doc extensions
        os.path.join(os.path.dirname(__file__), "..", "../..", "sphinxext")
    ]
)

# -- General configuration -----------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
# sphinxext.

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.extlinks",
    "sphinx.ext.todo",
    "numpydoc",  # handle NumPy documentation formatted docstrings
    "IPython.sphinxext.ipython_directive",
    "IPython.sphinxext.ipython_console_highlighting",
    "matplotlib.sphinxext.plot_directive",
    "sphinx.ext.intersphinx",
    "sphinx.ext.coverage",
    "sphinx.ext.mathjax",
    "sphinx.ext.ifconfig",
    "sphinx.ext.linkcode",
    "nbsphinx",
    "contributors",  # custom pandas extension
]

exclude_patterns = ["**.ipynb_checkpoints"]
try:
    import nbconvert
except ImportError:
    logger.warn("nbconvert not installed. Skipping notebooks.")
    exclude_patterns.append("**/*.ipynb")
else:
    try:
        nbconvert.utils.pandoc.get_pandoc_version()
    except nbconvert.utils.pandoc.PandocMissing:
        logger.warn("Pandoc not installed. Skipping notebooks.")
        exclude_patterns.append("**/*.ipynb")

# sphinx_pattern can be '-api' to exclude the API pages,
# the path to a file, or a Python object
# (e.g. '10min.rst' or 'pandas.DataFrame.head')
source_path = os.path.dirname(os.path.abspath(__file__))
pattern = os.environ.get("SPHINX_PATTERN")
if pattern:
    for dirname, dirs, fnames in os.walk(source_path):
        for fname in fnames:
            if os.path.splitext(fname)[-1] in (".rst", ".ipynb"):
                fname = os.path.relpath(os.path.join(dirname, fname), source_path)

                if fname == "index.rst" and os.path.abspath(dirname) == source_path:
                    continue
                elif pattern == "-api" and dirname == "reference":
                    exclude_patterns.append(fname)
                elif pattern != "-api" and fname != pattern:
                    exclude_patterns.append(fname)

with open(os.path.join(source_path, "index.rst.template")) as f:
    t = jinja2.Template(f.read())
with open(os.path.join(source_path, "index.rst"), "w") as f:
    f.write(
        t.render(
            include_api=pattern is None,
            single_doc=(pattern if pattern is not None and pattern != "-api" else None),
        )
    )
autosummary_generate = True if pattern is None else ["index"]
autodoc_typehints = "none"

# numpydoc
numpydoc_attributes_as_param_list = False

# matplotlib plot directive
plot_include_source = True
plot_formats = [("png", 90)]
plot_html_show_formats = False
plot_html_show_source_link = False
plot_pre_code = """import numpy as np
import pandas as pd"""

# nbsphinx do not use requirejs (breaks bootstrap)
nbsphinx_requirejs_path = ""

# Add any paths that contain templates here, relative to this directory.
templates_path = ["../_templates"]

# The suffix of source filenames.
source_suffix = [".rst"]

# The encoding of source files.
source_encoding = "utf-8"

# The master toctree document.
master_doc = "index"

# General information about the project.
project = "pandas"
copyright = f"2008-{datetime.now().year}, the pandas development team"

# The version info for the project you're documenting, acts as replacement for
# |version| and |release|, also used in various other places throughout the
# built documents.
#
# The short X.Y version.
import pandas  # noqa: E402 isort:skip

# version = '%s r%s' % (pandas.__version__, svn_version())
version = str(pandas.__version__)

# The full version, including alpha/beta/rc tags.
release = version

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
# language = None

# There are two options for replacing |today|: either, you set today to some
# non-false value, then it is used:
# today = ''
# Else, today_fmt is used as the format for a strftime call.
# today_fmt = '%B %d, %Y'

# List of documents that shouldn't be included in the build.
# unused_docs = []

# List of directories, relative to source directory, that shouldn't be searched
# for source files.
exclude_trees = []

# The reST default role (used for this markup: `text`) to use for all
# documents. default_role = None

# If true, '()' will be appended to :func: etc. cross-reference text.
# add_function_parentheses = True

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
# add_module_names = True

# If true, sectionauthor and moduleauthor directives will be shown in the
# output. They are ignored by default.
# show_authors = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# A list of ignored prefixes for module index sorting.
# modindex_common_prefix = []


# -- Options for HTML output ---------------------------------------------

# The theme to use for HTML and HTML Help pages.  Major themes that come with
# Sphinx are currently 'default' and 'sphinxdoc'.
html_theme = "pydata_sphinx_theme"

# The style sheet to use for HTML and HTML Help pages. A file of that name
# must exist either in Sphinx' static/ path, or in one of the custom paths
# given in html_static_path.
# html_style = 'statsmodels.css'

# Theme options are theme-specific and customize the look and feel of a theme
# further.  For a list of options available for each theme, see the
# documentation.
html_theme_options = {
    "external_links": [],
    "github_url": "https://github.com/pandas-dev/pandas",
    "twitter_url": "https://twitter.com/pandas_dev",
    "google_analytics_id": "UA-27880019-2",
}

# Add any paths that contain custom themes here, relative to this directory.
# html_theme_path = ["themes"]

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
# html_title = None

# A shorter title for the navigation bar.  Default is the same as html_title.
# html_short_title = None

# The name of an image file (relative to this directory) to place at the top
# of the sidebar.
html_logo = "../../web/pandas/static/img/pandas.svg"

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ["_static"]

html_css_files = [
    "css/getting_started.css",
    "css/pandas.css",
]

# The name of an image file (within the static path) to use as favicon of the
# docs.  This file should be a Windows icon file (.ico) being 16x16 or 32x32
# pixels large.
html_favicon = "../../web/pandas/static/img/favicon.ico"

# If not '', a 'Last updated on:' timestamp is inserted at every page bottom,
# using the given strftime format.
# html_last_updated_fmt = '%b %d, %Y'

# If true, SmartyPants will be used to convert quotes and dashes to
# typographically correct entities.
# html_use_smartypants = True

# Custom sidebar templates, maps document names to template names.
# html_sidebars = {}

# Additional templates that should be rendered to pages, maps page names to
# template names.

# Add redirect for previously existing API pages
# each item is like `(from_old, to_new)`
# To redirect a class and all its methods, see below
# https://github.com/pandas-dev/pandas/issues/16186

moved_api_pages = [
    ("pandas.core.common.isnull", "pandas.isna"),
    ("pandas.core.common.notnull", "pandas.notna"),
    ("pandas.core.reshape.get_dummies", "pandas.get_dummies"),
    ("pandas.tools.merge.concat", "pandas.concat"),
    ("pandas.tools.merge.merge", "pandas.merge"),
    ("pandas.tools.pivot.pivot_table", "pandas.pivot_table"),
    ("pandas.tseries.tools.to_datetime", "pandas.to_datetime"),
    ("pandas.io.clipboard.read_clipboard", "pandas.read_clipboard"),
    ("pandas.io.excel.ExcelFile.parse", "pandas.ExcelFile.parse"),
    ("pandas.io.excel.read_excel", "pandas.read_excel"),
    ("pandas.io.gbq.read_gbq", "pandas.read_gbq"),
    ("pandas.io.html.read_html", "pandas.read_html"),
    ("pandas.io.json.read_json", "pandas.read_json"),
    ("pandas.io.parsers.read_csv", "pandas.read_csv"),
    ("pandas.io.parsers.read_fwf", "pandas.read_fwf"),
    ("pandas.io.parsers.read_table", "pandas.read_table"),
    ("pandas.io.pickle.read_pickle", "pandas.read_pickle"),
    ("pandas.io.pytables.HDFStore.append", "pandas.HDFStore.append"),
    ("pandas.io.pytables.HDFStore.get", "pandas.HDFStore.get"),
    ("pandas.io.pytables.HDFStore.put", "pandas.HDFStore.put"),
    ("pandas.io.pytables.HDFStore.select", "pandas.HDFStore.select"),
    ("pandas.io.pytables.read_hdf", "pandas.read_hdf"),
    ("pandas.io.sql.read_sql", "pandas.read_sql"),
    ("pandas.io.sql.read_frame", "pandas.read_frame"),
    ("pandas.io.sql.write_frame", "pandas.write_frame"),
    ("pandas.io.stata.read_stata", "pandas.read_stata"),
]

# Again, tuples of (from_old, to_new)
moved_classes = [
    ("pandas.tseries.resample.Resampler", "pandas.core.resample.Resampler"),
    ("pandas.formats.style.Styler", "pandas.io.formats.style.Styler"),
]

for old, new in moved_classes:
    # the class itself...
    moved_api_pages.append((old, new))

    mod, classname = new.rsplit(".", 1)
    klass = getattr(importlib.import_module(mod), classname)
    methods = [
        x for x in dir(klass) if not x.startswith("_") or x in ("__iter__", "__array__")
    ]

    for method in methods:
        # ... and each of its public methods
        moved_api_pages.append((f"{old}.{method}", f"{new}.{method}",))

if pattern is None:
    html_additional_pages = {
        "generated/" + page[0]: "api_redirect.html" for page in moved_api_pages
    }


header = f"""\
.. currentmodule:: pandas

.. ipython:: python
   :suppress:

   import numpy as np
   import pandas as pd

   np.random.seed(123456)
   np.set_printoptions(precision=4, suppress=True)
   pd.options.display.max_rows = 15

   import os
   os.chdir(r'{os.path.dirname(os.path.dirname(__file__))}')
"""


html_context = {
    "redirects": {old: new for old, new in moved_api_pages},
    "header": header,
}

# If false, no module index is generated.
html_use_modindex = True

# If false, no index is generated.
# html_use_index = True

# If true, the index is split into individual pages for each letter.
# html_split_index = False

# If true, links to the reST sources are added to the pages.
# html_show_sourcelink = True

# If true, an OpenSearch description file will be output, and all pages will
# contain a <link> tag referring to it.  The value of this option must be the
# base URL from which the finished HTML is served.
# html_use_opensearch = ''

# If nonempty, this is the file name suffix for HTML files (e.g. ".xhtml").
# html_file_suffix = ''

# Output file base name for HTML help builder.
htmlhelp_basename = "pandas"

# -- Options for nbsphinx ------------------------------------------------

nbsphinx_allow_errors = True

# -- Options for LaTeX output --------------------------------------------

latex_elements = {}

# The paper size ('letter' or 'a4').
# latex_paper_size = 'letter'

# The font size ('10pt', '11pt' or '12pt').
# latex_font_size = '10pt'

# Grouping the document tree into LaTeX files. List of tuples (source start
# file, target name, title, author, documentclass [howto/manual]).
latex_documents = [
    (
        "index",
        "pandas.tex",
        "pandas: powerful Python data analysis toolkit",
        "Wes McKinney and the Pandas Development Team",
        "manual",
    )
]

# The name of an image file (relative to this directory) to place at the top of
# the title page.
# latex_logo = None

# For "manual" documents, if this is true, then toplevel headings are parts,
# not chapters.
# latex_use_parts = False

# Additional stuff for the LaTeX preamble.
# latex_preamble = ''

# Documents to append as an appendix to all manuals.
# latex_appendices = []

# If false, no module index is generated.
# latex_use_modindex = True


if pattern is None:
    intersphinx_mapping = {
        "dateutil": ("https://dateutil.readthedocs.io/en/latest/", None),
        "matplotlib": ("https://matplotlib.org/", None),
        "numpy": ("https://docs.scipy.org/doc/numpy/", None),
        "pandas-gbq": ("https://pandas-gbq.readthedocs.io/en/latest/", None),
        "py": ("https://pylib.readthedocs.io/en/latest/", None),
        "python": ("https://docs.python.org/3/", None),
        "scipy": ("https://docs.scipy.org/doc/scipy/reference/", None),
        "statsmodels": ("https://www.statsmodels.org/devel/", None),
        "pyarrow": ("https://arrow.apache.org/docs/", None),
    }

# extlinks alias
extlinks = {
    "issue": ("https://github.com/pandas-dev/pandas/issues/%s", "GH"),
    "wiki": ("https://github.com/pandas-dev/pandas/wiki/%s", "wiki "),
}


ipython_warning_is_error = False
ipython_exec_lines = [
    "import numpy as np",
    "import pandas as pd",
    # This ensures correct rendering on system with console encoding != utf8
    # (windows). It forces pandas to encode its output reprs using utf8
    # wherever the docs are built. The docs' target is the browser, not
    # the console, so this is fine.
    'pd.options.display.encoding="utf8"',
]


# Add custom Documenter to handle attributes/methods of an AccessorProperty
# eg pandas.Series.str and pandas.Series.dt (see GH9322)

import sphinx  # noqa: E402 isort:skip
from sphinx.util import rpartition  # noqa: E402 isort:skip
from sphinx.ext.autodoc import (  # noqa: E402 isort:skip
    AttributeDocumenter,
    Documenter,
    MethodDocumenter,
)
from sphinx.ext.autosummary import Autosummary  # noqa: E402 isort:skip


class AccessorDocumenter(MethodDocumenter):
    """
    Specialized Documenter subclass for accessors.
    """

    objtype = "accessor"
    directivetype = "method"

    # lower than MethodDocumenter so this is not chosen for normal methods
    priority = 0.6

    def format_signature(self):
        # this method gives an error/warning for the accessors, therefore
        # overriding it (accessor has no arguments)
        return ""


class AccessorLevelDocumenter(Documenter):
    """
    Specialized Documenter subclass for objects on accessor level (methods,
    attributes).
    """

    # This is the simple straightforward version
    # modname is None, base the last elements (eg 'hour')
    # and path the part before (eg 'Series.dt')
    # def resolve_name(self, modname, parents, path, base):
    #     modname = 'pandas'
    #     mod_cls = path.rstrip('.')
    #     mod_cls = mod_cls.split('.')
    #
    #     return modname, mod_cls + [base]
    def resolve_name(self, modname, parents, path, base):
        if modname is None:
            if path:
                mod_cls = path.rstrip(".")
            else:
                mod_cls = None
                # if documenting a class-level object without path,
                # there must be a current class, either from a parent
                # auto directive ...
                mod_cls = self.env.temp_data.get("autodoc:class")
                # ... or from a class directive
                if mod_cls is None:
                    mod_cls = self.env.temp_data.get("py:class")
                # ... if still None, there's no way to know
                if mod_cls is None:
                    return None, []
            # HACK: this is added in comparison to ClassLevelDocumenter
            # mod_cls still exists of class.accessor, so an extra
            # rpartition is needed
            modname, accessor = rpartition(mod_cls, ".")
            modname, cls = rpartition(modname, ".")
            parents = [cls, accessor]
            # if the module name is still missing, get it like above
            if not modname:
                modname = self.env.temp_data.get("autodoc:module")
            if not modname:
                if sphinx.__version__ > "1.3":
                    modname = self.env.ref_context.get("py:module")
                else:
                    modname = self.env.temp_data.get("py:module")
            # ... else, it stays None, which means invalid
        return modname, parents + [base]


class AccessorAttributeDocumenter(AccessorLevelDocumenter, AttributeDocumenter):
    objtype = "accessorattribute"
    directivetype = "attribute"

    # lower than AttributeDocumenter so this is not chosen for normal
    # attributes
    priority = 0.6


class AccessorMethodDocumenter(AccessorLevelDocumenter, MethodDocumenter):
    objtype = "accessormethod"
    directivetype = "method"

    # lower than MethodDocumenter so this is not chosen for normal methods
    priority = 0.6


class AccessorCallableDocumenter(AccessorLevelDocumenter, MethodDocumenter):
    """
    This documenter lets us removes .__call__ from the method signature for
    callable accessors like Series.plot
    """

    objtype = "accessorcallable"
    directivetype = "method"

    # lower than MethodDocumenter; otherwise the doc build prints warnings
    priority = 0.5

    def format_name(self):
        return MethodDocumenter.format_name(self).rstrip(".__call__")


class PandasAutosummary(Autosummary):
    """
    This alternative autosummary class lets us override the table summary for
    Series.plot and DataFrame.plot in the API docs.
    """

    def _replace_pandas_items(self, display_name, sig, summary, real_name):
        # this a hack: ideally we should extract the signature from the
        # .__call__ method instead of hard coding this
        if display_name == "DataFrame.plot":
            sig = "([x, y, kind, ax, ....])"
            summary = "DataFrame plotting accessor and method"
        elif display_name == "Series.plot":
            sig = "([kind, ax, figsize, ....])"
            summary = "Series plotting accessor and method"
        return (display_name, sig, summary, real_name)

    @staticmethod
    def _is_deprecated(real_name):
        try:
            obj, parent, modname = _import_by_name(real_name)
        except ImportError:
            return False
        doc = NumpyDocString(obj.__doc__ or "")
        summary = "".join(doc["Summary"] + doc["Extended Summary"])
        return ".. deprecated::" in summary

    def _add_deprecation_prefixes(self, items):
        for item in items:
            display_name, sig, summary, real_name = item
            if self._is_deprecated(real_name):
                summary = f"(DEPRECATED) {summary}"
            yield display_name, sig, summary, real_name

    def get_items(self, names):
        items = Autosummary.get_items(self, names)
        items = [self._replace_pandas_items(*item) for item in items]
        items = list(self._add_deprecation_prefixes(items))
        return items


# based on numpy doc/source/conf.py
def linkcode_resolve(domain, info):
    """
    Determine the URL corresponding to Python object
    """
    if domain != "py":
        return None

    modname = info["module"]
    fullname = info["fullname"]

    submod = sys.modules.get(modname)
    if submod is None:
        return None

    obj = submod
    for part in fullname.split("."):
        try:
            obj = getattr(obj, part)
        except AttributeError:
            return None

    try:
        fn = inspect.getsourcefile(inspect.unwrap(obj))
    except TypeError:
        fn = None
    if not fn:
        return None

    try:
        source, lineno = inspect.getsourcelines(obj)
    except OSError:
        lineno = None

    if lineno:
        linespec = f"#L{lineno}-L{lineno + len(source) - 1}"
    else:
        linespec = ""

    fn = os.path.relpath(fn, start=os.path.dirname(pandas.__file__))

    if "+" in pandas.__version__:
        return f"https://github.com/pandas-dev/pandas/blob/master/pandas/{fn}{linespec}"
    else:
        return (
            f"https://github.com/pandas-dev/pandas/blob/"
            f"v{pandas.__version__}/pandas/{fn}{linespec}"
        )


# remove the docstring of the flags attribute (inherited from numpy ndarray)
# because these give doc build errors (see GH issue 5331)
def remove_flags_docstring(app, what, name, obj, options, lines):
    if what == "attribute" and name.endswith(".flags"):
        del lines[:]


def process_class_docstrings(app, what, name, obj, options, lines):
    """
    For those classes for which we use ::

    :template: autosummary/class_without_autosummary.rst

    the documented attributes/methods have to be listed in the class
    docstring. However, if one of those lists is empty, we use 'None',
    which then generates warnings in sphinx / ugly html output.
    This "autodoc-process-docstring" event connector removes that part
    from the processed docstring.

    """
    if what == "class":
        joined = "\n".join(lines)

        templates = [
            """.. rubric:: Attributes

.. autosummary::
   :toctree:

   None
""",
            """.. rubric:: Methods

.. autosummary::
   :toctree:

   None
""",
        ]

        for template in templates:
            if template in joined:
                joined = joined.replace(template, "")
        lines[:] = joined.split("\n")


suppress_warnings = [
    # We "overwrite" autosummary with our PandasAutosummary, but
    # still want the regular autosummary setup to run. So we just
    # suppress this warning.
    "app.add_directive"
]
if pattern:
    # When building a single document we don't want to warn because references
    # to other documents are unknown, as it's expected
    suppress_warnings.append("ref.ref")


def rstjinja(app, docname, source):
    """
    Render our pages as a jinja template for fancy templating goodness.
    """
    # https://www.ericholscher.com/blog/2016/jul/25/integrating-jinja-rst-sphinx/
    # Make sure we're outputting HTML
    if app.builder.format != "html":
        return
    src = source[0]
    rendered = app.builder.templates.render_string(src, app.config.html_context)
    source[0] = rendered


def setup(app):
    app.connect("source-read", rstjinja)
    app.connect("autodoc-process-docstring", remove_flags_docstring)
    app.connect("autodoc-process-docstring", process_class_docstrings)
    app.add_autodocumenter(AccessorDocumenter)
    app.add_autodocumenter(AccessorAttributeDocumenter)
    app.add_autodocumenter(AccessorMethodDocumenter)
    app.add_autodocumenter(AccessorCallableDocumenter)
    app.add_directive("autosummary", PandasAutosummary)
