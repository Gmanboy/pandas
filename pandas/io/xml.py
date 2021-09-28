"""
:mod:`pandas.io.xml` is a module for reading XML.
"""

from __future__ import annotations

import io

from pandas._typing import (
    Buffer,
    CompressionOptions,
    FilePathOrBuffer,
    StorageOptions,
)
from pandas.compat._optional import import_optional_dependency
from pandas.errors import (
    AbstractMethodError,
    ParserError,
)
from pandas.util._decorators import doc

from pandas.core.dtypes.common import is_list_like

from pandas.core.frame import DataFrame
from pandas.core.shared_docs import _shared_docs

from pandas.io.common import (
    file_exists,
    get_handle,
    is_fsspec_url,
    is_url,
    stringify_path,
)
from pandas.io.parsers import TextParser


class _XMLFrameParser:
    """
    Internal subclass to parse XML into DataFrames.

    Parameters
    ----------
    path_or_buffer : a valid JSON str, path object or file-like object
        Any valid string path is acceptable. The string could be a URL. Valid
        URL schemes include http, ftp, s3, and file.

    xpath : str or regex
        The XPath expression to parse required set of nodes for
        migration to `Data Frame`. `etree` supports limited XPath.

    namespacess : dict
        The namespaces defined in XML document (`xmlns:namespace='URI')
        as dicts with key being namespace and value the URI.

    elems_only : bool
        Parse only the child elements at the specified `xpath`.

    attrs_only : bool
        Parse only the attributes at the specified `xpath`.

    names : list
        Column names for Data Frame of parsed XML data.

    encoding : str
        Encoding of xml object or document.

    stylesheet : str or file-like
        URL, file, file-like object, or a raw string containing XSLT,
        `etree` does not support XSLT but retained for consistency.

    compression : {'infer', 'gzip', 'bz2', 'zip', 'xz', None}, default 'infer'
        Compression type for on-the-fly decompression of on-disk data.
        If 'infer', then use extension for gzip, bz2, zip or xz.

    storage_options : dict, optional
        Extra options that make sense for a particular storage connection,
        e.g. host, port, username, password, etc.,

    See also
    --------
    pandas.io.xml._EtreeFrameParser
    pandas.io.xml._LxmlFrameParser

    Notes
    -----
    To subclass this class effectively you must override the following methods:`
        * :func:`parse_data`
        * :func:`_parse_nodes`
        * :func:`_parse_doc`
        * :func:`_validate_names`
        * :func:`_validate_path`


    See each method's respective documentation for details on their
    functionality.
    """

    def __init__(
        self,
        path_or_buffer,
        xpath,
        namespaces,
        elems_only,
        attrs_only,
        names,
        encoding,
        stylesheet,
        compression,
        storage_options,
    ) -> None:
        self.path_or_buffer = path_or_buffer
        self.xpath = xpath
        self.namespaces = namespaces
        self.elems_only = elems_only
        self.attrs_only = attrs_only
        self.names = names
        self.encoding = encoding
        self.stylesheet = stylesheet
        self.is_style = None
        self.compression = compression
        self.storage_options = storage_options

    def parse_data(self) -> list[dict[str, str | None]]:
        """
        Parse xml data.

        This method will call the other internal methods to
        validate xpath, names, parse and return specific nodes.
        """

        raise AbstractMethodError(self)

    def _parse_nodes(self) -> list[dict[str, str | None]]:
        """
        Parse xml nodes.

        This method will parse the children and attributes of elements
        in xpath, conditionally for only elements, only attributes
        or both while optionally renaming node names.

        Raises
        ------
        ValueError
            * If only elements and only attributes are specified.

        Notes
        -----
        Namespace URIs will be removed from return node values.Also,
        elements with missing children or attributes compared to siblings
        will have optional keys filled withi None values.
        """

        raise AbstractMethodError(self)

    def _validate_path(self) -> None:
        """
        Validate xpath.

        This method checks for syntax, evaluation, or empty nodes return.

        Raises
        ------
        SyntaxError
            * If xpah is not supported or issues with namespaces.

        ValueError
            * If xpah does not return any nodes.
        """

        raise AbstractMethodError(self)

    def _validate_names(self) -> None:
        """
        Validate names.

        This method will check if names is a list-like and aligns
        with length of parse nodes.

        Raises
        ------
        ValueError
            * If value is not a list and less then length of nodes.
        """
        raise AbstractMethodError(self)

    def _parse_doc(self, raw_doc) -> bytes:
        """
        Build tree from path_or_buffer.

        This method will parse XML object into tree
        either from string/bytes or file location.
        """
        raise AbstractMethodError(self)


class _EtreeFrameParser(_XMLFrameParser):
    """
    Internal class to parse XML into DataFrames with the Python
    standard library XML module: `xml.etree.ElementTree`.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def parse_data(self) -> list[dict[str, str | None]]:
        from xml.etree.ElementTree import XML

        if self.stylesheet is not None:
            raise ValueError(
                "To use stylesheet, you need lxml installed and selected as parser."
            )

        self.xml_doc = XML(self._parse_doc(self.path_or_buffer))

        self._validate_path()
        self._validate_names()

        return self._parse_nodes()

    def _parse_nodes(self) -> list[dict[str, str | None]]:
        elems = self.xml_doc.findall(self.xpath, namespaces=self.namespaces)
        dicts: list[dict[str, str | None]]

        if self.elems_only and self.attrs_only:
            raise ValueError("Either element or attributes can be parsed not both.")
        elif self.elems_only:
            if self.names:
                dicts = [
                    {
                        **(
                            {el.tag: el.text.strip()}
                            if el.text and not el.text.isspace()
                            else {}
                        ),
                        **{
                            nm: ch.text.strip() if ch.text else None
                            for nm, ch in zip(self.names, el.findall("*"))
                        },
                    }
                    for el in elems
                ]
            else:
                dicts = [
                    {
                        ch.tag: ch.text.strip() if ch.text else None
                        for ch in el.findall("*")
                    }
                    for el in elems
                ]

        elif self.attrs_only:
            dicts = [
                {k: v.strip() if v else None for k, v in el.attrib.items()}
                for el in elems
            ]

        else:
            if self.names:
                dicts = [
                    {
                        **el.attrib,
                        **(
                            {el.tag: el.text.strip()}
                            if el.text and not el.text.isspace()
                            else {}
                        ),
                        **{
                            nm: ch.text.strip() if ch.text else None
                            for nm, ch in zip(self.names, el.findall("*"))
                        },
                    }
                    for el in elems
                ]

            else:
                dicts = [
                    {
                        **el.attrib,
                        **(
                            {el.tag: el.text.strip()}
                            if el.text and not el.text.isspace()
                            else {}
                        ),
                        **{
                            ch.tag: ch.text.strip() if ch.text else None
                            for ch in el.findall("*")
                        },
                    }
                    for el in elems
                ]

        dicts = [
            {k.split("}")[1] if "}" in k else k: v for k, v in d.items()} for d in dicts
        ]

        keys = list(dict.fromkeys([k for d in dicts for k in d.keys()]))
        dicts = [{k: d[k] if k in d.keys() else None for k in keys} for d in dicts]

        if self.names:
            dicts = [{nm: v for nm, v in zip(self.names, d.values())} for d in dicts]

        return dicts

    def _validate_path(self) -> None:
        """
        Notes
        -----
        `etree` supports limited XPath. If user attempts a more complex
        expression syntax error will raise.
        """

        msg = (
            "xpath does not return any nodes. "
            "If document uses namespaces denoted with "
            "xmlns, be sure to define namespaces and "
            "use them in xpath."
        )
        try:
            elems = self.xml_doc.find(self.xpath, namespaces=self.namespaces)
            if elems is None:
                raise ValueError(msg)

            if elems is not None and elems.find("*") is None and elems.attrib is None:
                raise ValueError(msg)

        except (KeyError, SyntaxError):
            raise SyntaxError(
                "You have used an incorrect or unsupported XPath "
                "expression for etree library or you used an "
                "undeclared namespace prefix."
            )

    def _validate_names(self) -> None:
        if self.names:
            parent = self.xml_doc.find(self.xpath, namespaces=self.namespaces)
            children = parent.findall("*") if parent else []

            if is_list_like(self.names):
                if len(self.names) < len(children):
                    raise ValueError(
                        "names does not match length of child elements in xpath."
                    )
            else:
                raise TypeError(
                    f"{type(self.names).__name__} is not a valid type for names"
                )

    def _parse_doc(self, raw_doc) -> bytes:
        from xml.etree.ElementTree import (
            XMLParser,
            parse,
            tostring,
        )

        handle_data = get_data_from_filepath(
            filepath_or_buffer=raw_doc,
            encoding=self.encoding,
            compression=self.compression,
            storage_options=self.storage_options,
        )

        with preprocess_data(handle_data) as xml_data:
            curr_parser = XMLParser(encoding=self.encoding)
            r = parse(xml_data, parser=curr_parser)

        return tostring(r.getroot())


class _LxmlFrameParser(_XMLFrameParser):
    """
    Internal class to parse XML into DataFrames with third-party
    full-featured XML library, `lxml`, that supports
    XPath 1.0 and XSLT 1.0.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

    def parse_data(self) -> list[dict[str, str | None]]:
        """
        Parse xml data.

        This method will call the other internal methods to
        validate xpath, names, optionally parse and run XSLT,
        and parse original or transformed XML and return specific nodes.
        """
        from lxml.etree import XML

        self.xml_doc = XML(self._parse_doc(self.path_or_buffer))

        if self.stylesheet is not None:
            self.xsl_doc = XML(self._parse_doc(self.stylesheet))
            self.xml_doc = XML(self._transform_doc())

        self._validate_path()
        self._validate_names()

        return self._parse_nodes()

    def _parse_nodes(self) -> list[dict[str, str | None]]:
        elems = self.xml_doc.xpath(self.xpath, namespaces=self.namespaces)
        dicts: list[dict[str, str | None]]

        if self.elems_only and self.attrs_only:
            raise ValueError("Either element or attributes can be parsed not both.")

        elif self.elems_only:
            if self.names:
                dicts = [
                    {
                        **(
                            {el.tag: el.text.strip()}
                            if el.text and not el.text.isspace()
                            else {}
                        ),
                        **{
                            nm: ch.text.strip() if ch.text else None
                            for nm, ch in zip(self.names, el.xpath("*"))
                        },
                    }
                    for el in elems
                ]
            else:
                dicts = [
                    {
                        ch.tag: ch.text.strip() if ch.text else None
                        for ch in el.xpath("*")
                    }
                    for el in elems
                ]

        elif self.attrs_only:
            dicts = [el.attrib for el in elems]

        else:
            if self.names:
                dicts = [
                    {
                        **el.attrib,
                        **(
                            {el.tag: el.text.strip()}
                            if el.text and not el.text.isspace()
                            else {}
                        ),
                        **{
                            nm: ch.text.strip() if ch.text else None
                            for nm, ch in zip(self.names, el.xpath("*"))
                        },
                    }
                    for el in elems
                ]
            else:
                dicts = [
                    {
                        **el.attrib,
                        **(
                            {el.tag: el.text.strip()}
                            if el.text and not el.text.isspace()
                            else {}
                        ),
                        **{
                            ch.tag: ch.text.strip() if ch.text else None
                            for ch in el.xpath("*")
                        },
                    }
                    for el in elems
                ]

        if self.namespaces or "}" in list(dicts[0].keys())[0]:
            dicts = [
                {k.split("}")[1] if "}" in k else k: v for k, v in d.items()}
                for d in dicts
            ]

        keys = list(dict.fromkeys([k for d in dicts for k in d.keys()]))
        dicts = [{k: d[k] if k in d.keys() else None for k in keys} for d in dicts]

        if self.names:
            dicts = [{nm: v for nm, v in zip(self.names, d.values())} for d in dicts]

        return dicts

    def _validate_path(self) -> None:

        msg = (
            "xpath does not return any nodes. "
            "Be sure row level nodes are in xpath. "
            "If document uses namespaces denoted with "
            "xmlns, be sure to define namespaces and "
            "use them in xpath."
        )

        elems = self.xml_doc.xpath(self.xpath, namespaces=self.namespaces)
        children = self.xml_doc.xpath(self.xpath + "/*", namespaces=self.namespaces)
        attrs = self.xml_doc.xpath(self.xpath + "/@*", namespaces=self.namespaces)

        if elems == []:
            raise ValueError(msg)

        if elems != [] and attrs == [] and children == []:
            raise ValueError(msg)

    def _validate_names(self) -> None:
        """
        Validate names.

        This method will check if names is a list and aligns with
        length of parse nodes.

        Raises
        ------
        ValueError
            * If value is not a list and less then length of nodes.
        """
        if self.names:
            children = self.xml_doc.xpath(
                self.xpath + "[1]/*", namespaces=self.namespaces
            )

            if is_list_like(self.names):
                if len(self.names) < len(children):
                    raise ValueError(
                        "names does not match length of child elements in xpath."
                    )
            else:
                raise TypeError(
                    f"{type(self.names).__name__} is not a valid type for names"
                )

    def _parse_doc(self, raw_doc) -> bytes:
        from lxml.etree import (
            XMLParser,
            fromstring,
            parse,
            tostring,
        )

        handle_data = get_data_from_filepath(
            filepath_or_buffer=raw_doc,
            encoding=self.encoding,
            compression=self.compression,
            storage_options=self.storage_options,
        )

        with preprocess_data(handle_data) as xml_data:
            curr_parser = XMLParser(encoding=self.encoding)

            if isinstance(xml_data, io.StringIO):
                doc = fromstring(
                    xml_data.getvalue().encode(self.encoding), parser=curr_parser
                )
            else:
                doc = parse(xml_data, parser=curr_parser)

        return tostring(doc)

    def _transform_doc(self) -> bytes:
        """
        Transform original tree using stylesheet.

        This method will transform original xml using XSLT script into
        am ideally flatter xml document for easier parsing and migration
        to Data Frame.
        """
        from lxml.etree import XSLT

        transformer = XSLT(self.xsl_doc)
        new_doc = transformer(self.xml_doc)

        return bytes(new_doc)


def get_data_from_filepath(
    filepath_or_buffer,
    encoding,
    compression,
    storage_options,
) -> str | bytes | Buffer:
    """
    Extract raw XML data.

    The method accepts three input types:
        1. filepath (string-like)
        2. file-like object (e.g. open file object, StringIO)
        3. XML string or bytes

    This method turns (1) into (2) to simplify the rest of the processing.
    It returns input types (2) and (3) unchanged.
    """
    filepath_or_buffer = stringify_path(filepath_or_buffer)

    if (
        isinstance(filepath_or_buffer, str)
        and not filepath_or_buffer.startswith(("<?xml", "<"))
    ) and (
        not isinstance(filepath_or_buffer, str)
        or is_url(filepath_or_buffer)
        or is_fsspec_url(filepath_or_buffer)
        or file_exists(filepath_or_buffer)
    ):
        with get_handle(
            filepath_or_buffer,
            "r",
            encoding=encoding,
            compression=compression,
            storage_options=storage_options,
        ) as handle_obj:
            filepath_or_buffer = (
                handle_obj.handle.read()
                if hasattr(handle_obj.handle, "read")
                else handle_obj.handle
            )

    return filepath_or_buffer


def preprocess_data(data) -> io.StringIO | io.BytesIO:
    """
    Convert extracted raw data.

    This method will return underlying data of extracted XML content.
    The data either has a `read` attribute (e.g. a file object or a
    StringIO/BytesIO) or is a string or bytes that is an XML document.
    """

    if isinstance(data, str):
        data = io.StringIO(data)

    elif isinstance(data, bytes):
        data = io.BytesIO(data)

    return data


def _data_to_frame(data, **kwargs) -> DataFrame:
    """
    Convert parsed data to Data Frame.

    This method will bind xml dictionary data of keys and values
    into named columns of Data Frame using the built-in TextParser
    class that build Data Frame and infers specific dtypes.
    """

    tags = next(iter(data))
    nodes = [list(d.values()) for d in data]

    try:
        with TextParser(nodes, names=tags, **kwargs) as tp:
            return tp.read()
    except ParserError:
        raise ParserError(
            "XML document may be too complex for import. "
            "Try to flatten document and use distinct "
            "element and attribute names."
        )


def _parse(
    path_or_buffer,
    xpath,
    namespaces,
    elems_only,
    attrs_only,
    names,
    encoding,
    parser,
    stylesheet,
    compression,
    storage_options,
    **kwargs,
) -> DataFrame:
    """
    Call internal parsers.

    This method will conditionally call internal parsers:
    LxmlFrameParser and/or EtreeParser.

    Raises
    ------
    ImportError
        * If lxml is not installed if selected as parser.

    ValueError
        * If parser is not lxml or etree.
    """

    lxml = import_optional_dependency("lxml.etree", errors="ignore")

    p: _EtreeFrameParser | _LxmlFrameParser

    if parser == "lxml":
        if lxml is not None:
            p = _LxmlFrameParser(
                path_or_buffer,
                xpath,
                namespaces,
                elems_only,
                attrs_only,
                names,
                encoding,
                stylesheet,
                compression,
                storage_options,
            )
        else:
            raise ImportError("lxml not found, please install or use the etree parser.")

    elif parser == "etree":
        p = _EtreeFrameParser(
            path_or_buffer,
            xpath,
            namespaces,
            elems_only,
            attrs_only,
            names,
            encoding,
            stylesheet,
            compression,
            storage_options,
        )
    else:
        raise ValueError("Values for parser can only be lxml or etree.")

    data_dicts = p.parse_data()

    return _data_to_frame(data=data_dicts, **kwargs)


@doc(storage_options=_shared_docs["storage_options"])
def read_xml(
    path_or_buffer: FilePathOrBuffer,
    xpath: str | None = "./*",
    namespaces: dict | list[dict] | None = None,
    elems_only: bool | None = False,
    attrs_only: bool | None = False,
    names: list[str] | None = None,
    encoding: str | None = "utf-8",
    parser: str | None = "lxml",
    stylesheet: FilePathOrBuffer | None = None,
    compression: CompressionOptions = "infer",
    storage_options: StorageOptions = None,
) -> DataFrame:
    r"""
    Read XML document into a ``DataFrame`` object.

    .. versionadded:: 1.3.0

    Parameters
    ----------
    path_or_buffer : str, path object, or file-like object
        Any valid XML string or path is acceptable. The string could be a URL.
        Valid URL schemes include http, ftp, s3, and file.

    xpath : str, optional, default './\*'
        The XPath to parse required set of nodes for migration to DataFrame.
        XPath should return a collection of elements and not a single
        element. Note: The ``etree`` parser supports limited XPath
        expressions. For more complex XPath, use ``lxml`` which requires
        installation.

    namespaces : dict, optional
        The namespaces defined in XML document as dicts with key being
        namespace prefix and value the URI. There is no need to include all
        namespaces in XML, only the ones used in ``xpath`` expression.
        Note: if XML document uses default namespace denoted as
        `xmlns='<URI>'` without a prefix, you must assign any temporary
        namespace prefix such as 'doc' to the URI in order to parse
        underlying nodes and/or attributes. For example, ::

            namespaces = {{"doc": "https://example.com"}}

    elems_only : bool, optional, default False
        Parse only the child elements at the specified ``xpath``. By default,
        all child elements and non-empty text nodes are returned.

    attrs_only :  bool, optional, default False
        Parse only the attributes at the specified ``xpath``.
        By default, all attributes are returned.

    names :  list-like, optional
        Column names for DataFrame of parsed XML data. Use this parameter to
        rename original element names and distinguish same named elements.

    encoding : str, optional, default 'utf-8'
        Encoding of XML document.

    parser : {{'lxml','etree'}}, default 'lxml'
        Parser module to use for retrieval of data. Only 'lxml' and
        'etree' are supported. With 'lxml' more complex XPath searches
        and ability to use XSLT stylesheet are supported.

    stylesheet : str, path object or file-like object
        A URL, file-like object, or a raw string containing an XSLT script.
        This stylesheet should flatten complex, deeply nested XML documents
        for easier parsing. To use this feature you must have ``lxml`` module
        installed and specify 'lxml' as ``parser``. The ``xpath`` must
        reference nodes of transformed XML document generated after XSLT
        transformation and not the original XML document. Only XSLT 1.0
        scripts and not later versions is currently supported.

    compression : {{'infer', 'gzip', 'bz2', 'zip', 'xz', None}}, default 'infer'
        For on-the-fly decompression of on-disk data. If 'infer', then use
        gzip, bz2, zip or xz if path_or_buffer is a string ending in
        '.gz', '.bz2', '.zip', or 'xz', respectively, and no decompression
        otherwise. If using 'zip', the ZIP file must contain only one data
        file to be read in. Set to None for no decompression.

    {storage_options}

    Returns
    -------
    df
        A DataFrame.

    See Also
    --------
    read_json : Convert a JSON string to pandas object.
    read_html : Read HTML tables into a list of DataFrame objects.

    Notes
    -----
    This method is best designed to import shallow XML documents in
    following format which is the ideal fit for the two-dimensions of a
    ``DataFrame`` (row by column). ::

            <root>
                <row>
                  <column1>data</column1>
                  <column2>data</column2>
                  <column3>data</column3>
                  ...
               </row>
               <row>
                  ...
               </row>
               ...
            </root>

    As a file format, XML documents can be designed any way including
    layout of elements and attributes as long as it conforms to W3C
    specifications. Therefore, this method is a convenience handler for
    a specific flatter design and not all possible XML structures.

    However, for more complex XML documents, ``stylesheet`` allows you to
    temporarily redesign original document with XSLT (a special purpose
    language) for a flatter version for migration to a DataFrame.

    This function will *always* return a single :class:`DataFrame` or raise
    exceptions due to issues with XML document, ``xpath``, or other
    parameters.

    Examples
    --------
    >>> xml = '''<?xml version='1.0' encoding='utf-8'?>
    ... <data xmlns="http://example.com">
    ...  <row>
    ...    <shape>square</shape>
    ...    <degrees>360</degrees>
    ...    <sides>4.0</sides>
    ...  </row>
    ...  <row>
    ...    <shape>circle</shape>
    ...    <degrees>360</degrees>
    ...    <sides/>
    ...  </row>
    ...  <row>
    ...    <shape>triangle</shape>
    ...    <degrees>180</degrees>
    ...    <sides>3.0</sides>
    ...  </row>
    ... </data>'''

    >>> df = pd.read_xml(xml)
    >>> df
          shape  degrees  sides
    0    square      360    4.0
    1    circle      360    NaN
    2  triangle      180    3.0

    >>> xml = '''<?xml version='1.0' encoding='utf-8'?>
    ... <data>
    ...   <row shape="square" degrees="360" sides="4.0"/>
    ...   <row shape="circle" degrees="360"/>
    ...   <row shape="triangle" degrees="180" sides="3.0"/>
    ... </data>'''

    >>> df = pd.read_xml(xml, xpath=".//row")
    >>> df
          shape  degrees  sides
    0    square      360    4.0
    1    circle      360    NaN
    2  triangle      180    3.0

    >>> xml = '''<?xml version='1.0' encoding='utf-8'?>
    ... <doc:data xmlns:doc="https://example.com">
    ...   <doc:row>
    ...     <doc:shape>square</doc:shape>
    ...     <doc:degrees>360</doc:degrees>
    ...     <doc:sides>4.0</doc:sides>
    ...   </doc:row>
    ...   <doc:row>
    ...     <doc:shape>circle</doc:shape>
    ...     <doc:degrees>360</doc:degrees>
    ...     <doc:sides/>
    ...   </doc:row>
    ...   <doc:row>
    ...     <doc:shape>triangle</doc:shape>
    ...     <doc:degrees>180</doc:degrees>
    ...     <doc:sides>3.0</doc:sides>
    ...   </doc:row>
    ... </doc:data>'''

    >>> df = pd.read_xml(xml,
    ...                  xpath="//doc:row",
    ...                  namespaces={{"doc": "https://example.com"}})
    >>> df
          shape  degrees  sides
    0    square      360    4.0
    1    circle      360    NaN
    2  triangle      180    3.0
    """

    return _parse(
        path_or_buffer=path_or_buffer,
        xpath=xpath,
        namespaces=namespaces,
        elems_only=elems_only,
        attrs_only=attrs_only,
        names=names,
        encoding=encoding,
        parser=parser,
        stylesheet=stylesheet,
        compression=compression,
        storage_options=storage_options,
    )
