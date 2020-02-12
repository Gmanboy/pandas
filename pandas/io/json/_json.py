from collections import abc
import functools
from io import StringIO
from itertools import islice
import os
from typing import Any, Callable, Optional, Type

import numpy as np

import pandas._libs.json as json
from pandas._libs.tslibs import iNaT
from pandas._typing import JSONSerializable
from pandas.errors import AbstractMethodError
from pandas.util._decorators import deprecate_kwarg

from pandas.core.dtypes.common import ensure_str, is_period_dtype

from pandas import DataFrame, MultiIndex, Series, isna, to_datetime
from pandas.core.construction import create_series_with_explicit_dtype
from pandas.core.reshape.concat import concat

from pandas.io.common import get_filepath_or_buffer, get_handle, infer_compression
from pandas.io.json._normalize import convert_to_line_delimits
from pandas.io.json._table_schema import build_table_schema, parse_table_schema
from pandas.io.parsers import _validate_integer

loads = json.loads
dumps = json.dumps

TABLE_SCHEMA_VERSION = "0.20.0"


# interface to/from
def to_json(
    path_or_buf,
    obj,
    orient: Optional[str] = None,
    date_format: str = "epoch",
    double_precision: int = 10,
    force_ascii: bool = True,
    date_unit: str = "ms",
    default_handler: Optional[Callable[[Any], JSONSerializable]] = None,
    lines: bool = False,
    compression: Optional[str] = "infer",
    index: bool = True,
    indent: int = 0,
):

    if not index and orient not in ["split", "table"]:
        raise ValueError(
            "'index=False' is only valid when 'orient' is 'split' or 'table'"
        )

    if path_or_buf is not None:
        path_or_buf, _, _, _ = get_filepath_or_buffer(
            path_or_buf, compression=compression, mode="w"
        )

    if lines and orient != "records":
        raise ValueError("'lines' keyword only valid when 'orient' is records")

    if orient == "table" and isinstance(obj, Series):
        obj = obj.to_frame(name=obj.name or "values")

    writer: Type["Writer"]
    if orient == "table" and isinstance(obj, DataFrame):
        writer = JSONTableWriter
    elif isinstance(obj, Series):
        writer = SeriesWriter
    elif isinstance(obj, DataFrame):
        writer = FrameWriter
    else:
        raise NotImplementedError("'obj' should be a Series or a DataFrame")

    s = writer(
        obj,
        orient=orient,
        date_format=date_format,
        double_precision=double_precision,
        ensure_ascii=force_ascii,
        date_unit=date_unit,
        default_handler=default_handler,
        index=index,
        indent=indent,
    ).write()

    if lines:
        s = convert_to_line_delimits(s)

    if isinstance(path_or_buf, str):
        fh, handles = get_handle(path_or_buf, "w", compression=compression)
        try:
            fh.write(s)
        finally:
            fh.close()
    elif path_or_buf is None:
        return s
    else:
        path_or_buf.write(s)


class Writer:
    def __init__(
        self,
        obj,
        orient: Optional[str],
        date_format: str,
        double_precision: int,
        ensure_ascii: bool,
        date_unit: str,
        index: bool,
        default_handler: Optional[Callable[[Any], JSONSerializable]] = None,
        indent: int = 0,
    ):
        self.obj = obj

        if orient is None:
            orient = self._default_orient  # type: ignore

        self.orient = orient
        self.date_format = date_format
        self.double_precision = double_precision
        self.ensure_ascii = ensure_ascii
        self.date_unit = date_unit
        self.default_handler = default_handler
        self.index = index
        self.indent = indent

        self.is_copy = None
        self._format_axes()

    def _format_axes(self):
        raise AbstractMethodError(self)

    def write(self):
        return self._write(
            self.obj,
            self.orient,
            self.double_precision,
            self.ensure_ascii,
            self.date_unit,
            self.date_format == "iso",
            self.default_handler,
            self.indent,
        )

    def _write(
        self,
        obj,
        orient: Optional[str],
        double_precision: int,
        ensure_ascii: bool,
        date_unit: str,
        iso_dates: bool,
        default_handler: Optional[Callable[[Any], JSONSerializable]],
        indent: int,
    ):
        return dumps(
            obj,
            orient=orient,
            double_precision=double_precision,
            ensure_ascii=ensure_ascii,
            date_unit=date_unit,
            iso_dates=iso_dates,
            default_handler=default_handler,
            indent=indent,
        )


class SeriesWriter(Writer):
    _default_orient = "index"

    def _format_axes(self):
        if not self.obj.index.is_unique and self.orient == "index":
            raise ValueError(f"Series index must be unique for orient='{self.orient}'")

    def _write(
        self,
        obj,
        orient: Optional[str],
        double_precision: int,
        ensure_ascii: bool,
        date_unit: str,
        iso_dates: bool,
        default_handler: Optional[Callable[[Any], JSONSerializable]],
        indent: int,
    ):
        if not self.index and orient == "split":
            obj = {"name": obj.name, "data": obj.values}
        return super()._write(
            obj,
            orient,
            double_precision,
            ensure_ascii,
            date_unit,
            iso_dates,
            default_handler,
            indent,
        )


class FrameWriter(Writer):
    _default_orient = "columns"

    def _format_axes(self):
        """
        Try to format axes if they are datelike.
        """
        if not self.obj.index.is_unique and self.orient in ("index", "columns"):
            raise ValueError(
                f"DataFrame index must be unique for orient='{self.orient}'."
            )
        if not self.obj.columns.is_unique and self.orient in (
            "index",
            "columns",
            "records",
        ):
            raise ValueError(
                f"DataFrame columns must be unique for orient='{self.orient}'."
            )

    def _write(
        self,
        obj,
        orient: Optional[str],
        double_precision: int,
        ensure_ascii: bool,
        date_unit: str,
        iso_dates: bool,
        default_handler: Optional[Callable[[Any], JSONSerializable]],
        indent: int,
    ):
        if not self.index and orient == "split":
            obj = obj.to_dict(orient="split")
            del obj["index"]
        return super()._write(
            obj,
            orient,
            double_precision,
            ensure_ascii,
            date_unit,
            iso_dates,
            default_handler,
            indent,
        )


class JSONTableWriter(FrameWriter):
    _default_orient = "records"

    def __init__(
        self,
        obj,
        orient: Optional[str],
        date_format: str,
        double_precision: int,
        ensure_ascii: bool,
        date_unit: str,
        index: bool,
        default_handler: Optional[Callable[[Any], JSONSerializable]] = None,
        indent: int = 0,
    ):
        """
        Adds a `schema` attribute with the Table Schema, resets
        the index (can't do in caller, because the schema inference needs
        to know what the index is, forces orient to records, and forces
        date_format to 'iso'.
        """
        super().__init__(
            obj,
            orient,
            date_format,
            double_precision,
            ensure_ascii,
            date_unit,
            index,
            default_handler=default_handler,
            indent=indent,
        )

        if date_format != "iso":
            msg = (
                "Trying to write with `orient='table'` and "
                f"`date_format='{date_format}'`. Table Schema requires dates "
                "to be formatted with `date_format='iso'`"
            )
            raise ValueError(msg)

        self.schema = build_table_schema(obj, index=self.index)

        # NotImplemented on a column MultiIndex
        if obj.ndim == 2 and isinstance(obj.columns, MultiIndex):
            raise NotImplementedError("orient='table' is not supported for MultiIndex")

        # TODO: Do this timedelta properly in objToJSON.c See GH #15137
        if (
            (obj.ndim == 1)
            and (obj.name in set(obj.index.names))
            or len(obj.columns & obj.index.names)
        ):
            msg = "Overlapping names between the index and columns"
            raise ValueError(msg)

        obj = obj.copy()
        timedeltas = obj.select_dtypes(include=["timedelta"]).columns
        if len(timedeltas):
            obj[timedeltas] = obj[timedeltas].applymap(lambda x: x.isoformat())
        # Convert PeriodIndex to datetimes before serializing
        if is_period_dtype(obj.index):
            obj.index = obj.index.to_timestamp()

        # exclude index from obj if index=False
        if not self.index:
            self.obj = obj.reset_index(drop=True)
        else:
            self.obj = obj.reset_index(drop=False)
        self.date_format = "iso"
        self.orient = "records"
        self.index = index

    def _write(
        self,
        obj,
        orient,
        double_precision,
        ensure_ascii,
        date_unit,
        iso_dates,
        default_handler,
        indent,
    ):
        table_obj = {"schema": self.schema, "data": obj}
        serialized = super()._write(
            table_obj,
            orient,
            double_precision,
            ensure_ascii,
            date_unit,
            iso_dates,
            default_handler,
            indent,
        )

        return serialized


@deprecate_kwarg(old_arg_name="numpy", new_arg_name=None)
def read_json(
    path_or_buf=None,
    orient=None,
    typ="frame",
    dtype=None,
    convert_axes=None,
    convert_dates=True,
    keep_default_dates=True,
    numpy=False,
    precise_float=False,
    date_unit=None,
    encoding=None,
    lines=False,
    chunksize=None,
    compression="infer",
):
    """
    Convert a JSON string to pandas object.

    Parameters
    ----------
    path_or_buf : a valid JSON str, path object or file-like object
        Any valid string path is acceptable. The string could be a URL. Valid
        URL schemes include http, ftp, s3, and file. For file URLs, a host is
        expected. A local file could be:
        ``file://localhost/path/to/table.json``.

        If you want to pass in a path object, pandas accepts any
        ``os.PathLike``.

        By file-like object, we refer to objects with a ``read()`` method,
        such as a file handler (e.g. via builtin ``open`` function)
        or ``StringIO``.
    orient : str
        Indication of expected JSON string format.
        Compatible JSON strings can be produced by ``to_json()`` with a
        corresponding orient value.
        The set of possible orients is:

        - ``'split'`` : dict like
          ``{index -> [index], columns -> [columns], data -> [values]}``
        - ``'records'`` : list like
          ``[{column -> value}, ... , {column -> value}]``
        - ``'index'`` : dict like ``{index -> {column -> value}}``
        - ``'columns'`` : dict like ``{column -> {index -> value}}``
        - ``'values'`` : just the values array

        The allowed and default values depend on the value
        of the `typ` parameter.

        * when ``typ == 'series'``,

          - allowed orients are ``{'split','records','index'}``
          - default is ``'index'``
          - The Series index must be unique for orient ``'index'``.

        * when ``typ == 'frame'``,

          - allowed orients are ``{'split','records','index',
            'columns','values', 'table'}``
          - default is ``'columns'``
          - The DataFrame index must be unique for orients ``'index'`` and
            ``'columns'``.
          - The DataFrame columns must be unique for orients ``'index'``,
            ``'columns'``, and ``'records'``.

        .. versionadded:: 0.23.0
           'table' as an allowed value for the ``orient`` argument

    typ : {'frame', 'series'}, default 'frame'
        The type of object to recover.

    dtype : bool or dict, default None
        If True, infer dtypes; if a dict of column to dtype, then use those;
        if False, then don't infer dtypes at all, applies only to the data.

        For all ``orient`` values except ``'table'``, default is True.

        .. versionchanged:: 0.25.0

           Not applicable for ``orient='table'``.

    convert_axes : bool, default None
        Try to convert the axes to the proper dtypes.

        For all ``orient`` values except ``'table'``, default is True.

        .. versionchanged:: 0.25.0

           Not applicable for ``orient='table'``.

    convert_dates : bool or list of str, default True
        If True then default datelike columns may be converted (depending on
        keep_default_dates).
        If False, no dates will be converted.
        If a list of column names, then those columns will be converted and
        default datelike columns may also be converted (depending on
        keep_default_dates).

    keep_default_dates : bool, default True
        If parsing dates (convert_dates is not False), then try to parse the
        default datelike columns.
        A column label is datelike if

        * it ends with ``'_at'``,

        * it ends with ``'_time'``,

        * it begins with ``'timestamp'``,

        * it is ``'modified'``, or

        * it is ``'date'``.

    numpy : bool, default False
        Direct decoding to numpy arrays. Supports numeric data only, but
        non-numeric column and index labels are supported. Note also that the
        JSON ordering MUST be the same for each term if numpy=True.

        .. deprecated:: 1.0.0

    precise_float : bool, default False
        Set to enable usage of higher precision (strtod) function when
        decoding string to double values. Default (False) is to use fast but
        less precise builtin functionality.

    date_unit : str, default None
        The timestamp unit to detect if converting dates. The default behaviour
        is to try and detect the correct precision, but if this is not desired
        then pass one of 's', 'ms', 'us' or 'ns' to force parsing only seconds,
        milliseconds, microseconds or nanoseconds respectively.

    encoding : str, default is 'utf-8'
        The encoding to use to decode py3 bytes.

    lines : bool, default False
        Read the file as a json object per line.

    chunksize : int, optional
        Return JsonReader object for iteration.
        See the `line-delimited json docs
        <https://pandas.pydata.org/pandas-docs/stable/user_guide/io.html#line-delimited-json>`_
        for more information on ``chunksize``.
        This can only be passed if `lines=True`.
        If this is None, the file will be read into memory all at once.

        .. versionadded:: 0.21.0

    compression : {'infer', 'gzip', 'bz2', 'zip', 'xz', None}, default 'infer'
        For on-the-fly decompression of on-disk data. If 'infer', then use
        gzip, bz2, zip or xz if path_or_buf is a string ending in
        '.gz', '.bz2', '.zip', or 'xz', respectively, and no decompression
        otherwise. If using 'zip', the ZIP file must contain only one data
        file to be read in. Set to None for no decompression.

        .. versionadded:: 0.21.0

    Returns
    -------
    Series or DataFrame
        The type returned depends on the value of `typ`.

    See Also
    --------
    DataFrame.to_json : Convert a DataFrame to a JSON string.
    Series.to_json : Convert a Series to a JSON string.

    Notes
    -----
    Specific to ``orient='table'``, if a :class:`DataFrame` with a literal
    :class:`Index` name of `index` gets written with :func:`to_json`, the
    subsequent read operation will incorrectly set the :class:`Index` name to
    ``None``. This is because `index` is also used by :func:`DataFrame.to_json`
    to denote a missing :class:`Index` name, and the subsequent
    :func:`read_json` operation cannot distinguish between the two. The same
    limitation is encountered with a :class:`MultiIndex` and any names
    beginning with ``'level_'``.

    Examples
    --------

    >>> df = pd.DataFrame([['a', 'b'], ['c', 'd']],
    ...                   index=['row 1', 'row 2'],
    ...                   columns=['col 1', 'col 2'])

    Encoding/decoding a Dataframe using ``'split'`` formatted JSON:

    >>> df.to_json(orient='split')
    '{"columns":["col 1","col 2"],
      "index":["row 1","row 2"],
      "data":[["a","b"],["c","d"]]}'
    >>> pd.read_json(_, orient='split')
          col 1 col 2
    row 1     a     b
    row 2     c     d

    Encoding/decoding a Dataframe using ``'index'`` formatted JSON:

    >>> df.to_json(orient='index')
    '{"row 1":{"col 1":"a","col 2":"b"},"row 2":{"col 1":"c","col 2":"d"}}'
    >>> pd.read_json(_, orient='index')
          col 1 col 2
    row 1     a     b
    row 2     c     d

    Encoding/decoding a Dataframe using ``'records'`` formatted JSON.
    Note that index labels are not preserved with this encoding.

    >>> df.to_json(orient='records')
    '[{"col 1":"a","col 2":"b"},{"col 1":"c","col 2":"d"}]'
    >>> pd.read_json(_, orient='records')
      col 1 col 2
    0     a     b
    1     c     d

    Encoding with Table Schema

    >>> df.to_json(orient='table')
    '{"schema": {"fields": [{"name": "index", "type": "string"},
                            {"name": "col 1", "type": "string"},
                            {"name": "col 2", "type": "string"}],
                    "primaryKey": "index",
                    "pandas_version": "0.20.0"},
        "data": [{"index": "row 1", "col 1": "a", "col 2": "b"},
                {"index": "row 2", "col 1": "c", "col 2": "d"}]}'
    """
    if orient == "table" and dtype:
        raise ValueError("cannot pass both dtype and orient='table'")
    if orient == "table" and convert_axes:
        raise ValueError("cannot pass both convert_axes and orient='table'")

    if dtype is None and orient != "table":
        dtype = True
    if convert_axes is None and orient != "table":
        convert_axes = True
    if encoding is None:
        encoding = "utf-8"

    compression = infer_compression(path_or_buf, compression)
    filepath_or_buffer, _, compression, should_close = get_filepath_or_buffer(
        path_or_buf, encoding=encoding, compression=compression
    )

    json_reader = JsonReader(
        filepath_or_buffer,
        orient=orient,
        typ=typ,
        dtype=dtype,
        convert_axes=convert_axes,
        convert_dates=convert_dates,
        keep_default_dates=keep_default_dates,
        numpy=numpy,
        precise_float=precise_float,
        date_unit=date_unit,
        encoding=encoding,
        lines=lines,
        chunksize=chunksize,
        compression=compression,
    )

    if chunksize:
        return json_reader

    result = json_reader.read()
    if should_close:
        filepath_or_buffer.close()

    return result


class JsonReader(abc.Iterator):
    """
    JsonReader provides an interface for reading in a JSON file.

    If initialized with ``lines=True`` and ``chunksize``, can be iterated over
    ``chunksize`` lines at a time. Otherwise, calling ``read`` reads in the
    whole document.
    """

    def __init__(
        self,
        filepath_or_buffer,
        orient,
        typ,
        dtype,
        convert_axes,
        convert_dates,
        keep_default_dates,
        numpy,
        precise_float,
        date_unit,
        encoding,
        lines,
        chunksize,
        compression,
    ):

        self.path_or_buf = filepath_or_buffer
        self.orient = orient
        self.typ = typ
        self.dtype = dtype
        self.convert_axes = convert_axes
        self.convert_dates = convert_dates
        self.keep_default_dates = keep_default_dates
        self.numpy = numpy
        self.precise_float = precise_float
        self.date_unit = date_unit
        self.encoding = encoding
        self.compression = compression
        self.lines = lines
        self.chunksize = chunksize
        self.nrows_seen = 0
        self.should_close = False

        if self.chunksize is not None:
            self.chunksize = _validate_integer("chunksize", self.chunksize, 1)
            if not self.lines:
                raise ValueError("chunksize can only be passed if lines=True")

        data = self._get_data_from_filepath(filepath_or_buffer)
        self.data = self._preprocess_data(data)

    def _preprocess_data(self, data):
        """
        At this point, the data either has a `read` attribute (e.g. a file
        object or a StringIO) or is a string that is a JSON document.

        If self.chunksize, we prepare the data for the `__next__` method.
        Otherwise, we read it into memory for the `read` method.
        """
        if hasattr(data, "read") and not self.chunksize:
            data = data.read()
        if not hasattr(data, "read") and self.chunksize:
            data = StringIO(data)

        return data

    def _get_data_from_filepath(self, filepath_or_buffer):
        """
        The function read_json accepts three input types:
            1. filepath (string-like)
            2. file-like object (e.g. open file object, StringIO)
            3. JSON string

        This method turns (1) into (2) to simplify the rest of the processing.
        It returns input types (2) and (3) unchanged.
        """
        data = filepath_or_buffer

        exists = False
        if isinstance(data, str):
            try:
                exists = os.path.exists(filepath_or_buffer)
            # gh-5874: if the filepath is too long will raise here
            except (TypeError, ValueError):
                pass

        if exists or self.compression is not None:
            data, _ = get_handle(
                filepath_or_buffer,
                "r",
                encoding=self.encoding,
                compression=self.compression,
            )
            self.should_close = True
            self.open_stream = data

        return data

    def _combine_lines(self, lines) -> str:
        """
        Combines a list of JSON objects into one JSON object.
        """
        lines = filter(None, map(lambda x: x.strip(), lines))
        return "[" + ",".join(lines) + "]"

    def read(self):
        """
        Read the whole JSON input into a pandas object.
        """
        if self.lines and self.chunksize:
            obj = concat(self)
        elif self.lines:
            data = ensure_str(self.data)
            obj = self._get_object_parser(self._combine_lines(data.split("\n")))
        else:
            obj = self._get_object_parser(self.data)
        self.close()
        return obj

    def _get_object_parser(self, json):
        """
        Parses a json document into a pandas object.
        """
        typ = self.typ
        dtype = self.dtype
        kwargs = {
            "orient": self.orient,
            "dtype": self.dtype,
            "convert_axes": self.convert_axes,
            "convert_dates": self.convert_dates,
            "keep_default_dates": self.keep_default_dates,
            "numpy": self.numpy,
            "precise_float": self.precise_float,
            "date_unit": self.date_unit,
        }
        obj = None
        if typ == "frame":
            obj = FrameParser(json, **kwargs).parse()

        if typ == "series" or obj is None:
            if not isinstance(dtype, bool):
                kwargs["dtype"] = dtype
            obj = SeriesParser(json, **kwargs).parse()

        return obj

    def close(self):
        """
        If we opened a stream earlier, in _get_data_from_filepath, we should
        close it.

        If an open stream or file was passed, we leave it open.
        """
        if self.should_close:
            try:
                self.open_stream.close()
            except (IOError, AttributeError):
                pass

    def __next__(self):
        lines = list(islice(self.data, self.chunksize))
        if lines:
            lines_json = self._combine_lines(lines)
            obj = self._get_object_parser(lines_json)

            # Make sure that the returned objects have the right index.
            obj.index = range(self.nrows_seen, self.nrows_seen + len(obj))
            self.nrows_seen += len(obj)

            return obj

        self.close()
        raise StopIteration


class Parser:

    _STAMP_UNITS = ("s", "ms", "us", "ns")
    _MIN_STAMPS = {
        "s": 31536000,
        "ms": 31536000000,
        "us": 31536000000000,
        "ns": 31536000000000000,
    }

    def __init__(
        self,
        json,
        orient,
        dtype=None,
        convert_axes=True,
        convert_dates=True,
        keep_default_dates=False,
        numpy=False,
        precise_float=False,
        date_unit=None,
    ):
        self.json = json

        if orient is None:
            orient = self._default_orient
        self.orient = orient

        self.dtype = dtype

        if orient == "split":
            numpy = False

        if date_unit is not None:
            date_unit = date_unit.lower()
            if date_unit not in self._STAMP_UNITS:
                raise ValueError(f"date_unit must be one of {self._STAMP_UNITS}")
            self.min_stamp = self._MIN_STAMPS[date_unit]
        else:
            self.min_stamp = self._MIN_STAMPS["s"]

        self.numpy = numpy
        self.precise_float = precise_float
        self.convert_axes = convert_axes
        self.convert_dates = convert_dates
        self.date_unit = date_unit
        self.keep_default_dates = keep_default_dates
        self.obj = None

    def check_keys_split(self, decoded):
        """
        Checks that dict has only the appropriate keys for orient='split'.
        """
        bad_keys = set(decoded.keys()).difference(set(self._split_keys))
        if bad_keys:
            bad_keys = ", ".join(bad_keys)
            raise ValueError(f"JSON data had unexpected key(s): {bad_keys}")

    def parse(self):

        # try numpy
        numpy = self.numpy
        if numpy:
            self._parse_numpy()

        else:
            self._parse_no_numpy()

        if self.obj is None:
            return None
        if self.convert_axes:
            self._convert_axes()
        self._try_convert_types()
        return self.obj

    def _convert_axes(self):
        """
        Try to convert axes.
        """
        for axis in self.obj._AXIS_NUMBERS.keys():
            new_axis, result = self._try_convert_data(
                axis, self.obj._get_axis(axis), use_dtypes=False, convert_dates=True
            )
            if result:
                setattr(self.obj, axis, new_axis)

    def _try_convert_types(self):
        raise AbstractMethodError(self)

    def _try_convert_data(self, name, data, use_dtypes=True, convert_dates=True):
        """
        Try to parse a ndarray like into a column by inferring dtype.
        """
        # don't try to coerce, unless a force conversion
        if use_dtypes:
            if not self.dtype:
                return data, False
            elif self.dtype is True:
                pass
            else:
                # dtype to force
                dtype = (
                    self.dtype.get(name) if isinstance(self.dtype, dict) else self.dtype
                )
                if dtype is not None:
                    try:
                        dtype = np.dtype(dtype)
                        return data.astype(dtype), True
                    except (TypeError, ValueError):
                        return data, False

        if convert_dates:
            new_data, result = self._try_convert_to_date(data)
            if result:
                return new_data, True

        result = False

        if data.dtype == "object":

            # try float
            try:
                data = data.astype("float64")
                result = True
            except (TypeError, ValueError):
                pass

        if data.dtype.kind == "f":

            if data.dtype != "float64":

                # coerce floats to 64
                try:
                    data = data.astype("float64")
                    result = True
                except (TypeError, ValueError):
                    pass

        # don't coerce 0-len data
        if len(data) and (data.dtype == "float" or data.dtype == "object"):

            # coerce ints if we can
            try:
                new_data = data.astype("int64")
                if (new_data == data).all():
                    data = new_data
                    result = True
            except (TypeError, ValueError, OverflowError):
                pass

        # coerce ints to 64
        if data.dtype == "int":

            # coerce floats to 64
            try:
                data = data.astype("int64")
                result = True
            except (TypeError, ValueError):
                pass

        return data, result

    def _try_convert_to_date(self, data):
        """
        Try to parse a ndarray like into a date column.

        Try to coerce object in epoch/iso formats and integer/float in epoch
        formats. Return a boolean if parsing was successful.
        """
        # no conversion on empty
        if not len(data):
            return data, False

        new_data = data
        if new_data.dtype == "object":
            try:
                new_data = data.astype("int64")
            except (TypeError, ValueError, OverflowError):
                pass

        # ignore numbers that are out of range
        if issubclass(new_data.dtype.type, np.number):
            in_range = (
                isna(new_data.values)
                | (new_data > self.min_stamp)
                | (new_data.values == iNaT)
            )
            if not in_range.all():
                return data, False

        date_units = (self.date_unit,) if self.date_unit else self._STAMP_UNITS
        for date_unit in date_units:
            try:
                new_data = to_datetime(new_data, errors="raise", unit=date_unit)
            except (ValueError, OverflowError):
                continue
            return new_data, True
        return data, False

    def _try_convert_dates(self):
        raise AbstractMethodError(self)


class SeriesParser(Parser):
    _default_orient = "index"
    _split_keys = ("name", "index", "data")

    def _parse_no_numpy(self):
        data = loads(self.json, precise_float=self.precise_float)

        if self.orient == "split":
            decoded = {str(k): v for k, v in data.items()}
            self.check_keys_split(decoded)
            self.obj = create_series_with_explicit_dtype(**decoded)
        else:
            self.obj = create_series_with_explicit_dtype(data, dtype_if_empty=object)

    def _parse_numpy(self):
        load_kwargs = {
            "dtype": None,
            "numpy": True,
            "precise_float": self.precise_float,
        }
        if self.orient in ["columns", "index"]:
            load_kwargs["labelled"] = True
        loads_ = functools.partial(loads, **load_kwargs)
        data = loads_(self.json)

        if self.orient == "split":
            decoded = {str(k): v for k, v in data.items()}
            self.check_keys_split(decoded)
            self.obj = create_series_with_explicit_dtype(**decoded)
        elif self.orient in ["columns", "index"]:
            self.obj = create_series_with_explicit_dtype(*data, dtype_if_empty=object)
        else:
            self.obj = create_series_with_explicit_dtype(data, dtype_if_empty=object)

    def _try_convert_types(self):
        if self.obj is None:
            return
        obj, result = self._try_convert_data(
            "data", self.obj, convert_dates=self.convert_dates
        )
        if result:
            self.obj = obj


class FrameParser(Parser):
    _default_orient = "columns"
    _split_keys = ("columns", "index", "data")

    def _parse_numpy(self):

        json = self.json
        orient = self.orient

        if orient == "columns":
            args = loads(
                json,
                dtype=None,
                numpy=True,
                labelled=True,
                precise_float=self.precise_float,
            )
            if len(args):
                args = (args[0].T, args[2], args[1])
            self.obj = DataFrame(*args)
        elif orient == "split":
            decoded = loads(
                json, dtype=None, numpy=True, precise_float=self.precise_float
            )
            decoded = {str(k): v for k, v in decoded.items()}
            self.check_keys_split(decoded)
            self.obj = DataFrame(**decoded)
        elif orient == "values":
            self.obj = DataFrame(
                loads(json, dtype=None, numpy=True, precise_float=self.precise_float)
            )
        else:
            self.obj = DataFrame(
                *loads(
                    json,
                    dtype=None,
                    numpy=True,
                    labelled=True,
                    precise_float=self.precise_float,
                )
            )

    def _parse_no_numpy(self):

        json = self.json
        orient = self.orient

        if orient == "columns":
            self.obj = DataFrame(
                loads(json, precise_float=self.precise_float), dtype=None
            )
        elif orient == "split":
            decoded = {
                str(k): v
                for k, v in loads(json, precise_float=self.precise_float).items()
            }
            self.check_keys_split(decoded)
            self.obj = DataFrame(dtype=None, **decoded)
        elif orient == "index":
            self.obj = DataFrame.from_dict(
                loads(json, precise_float=self.precise_float),
                dtype=None,
                orient="index",
            )
        elif orient == "table":
            self.obj = parse_table_schema(json, precise_float=self.precise_float)
        else:
            self.obj = DataFrame(
                loads(json, precise_float=self.precise_float), dtype=None
            )

    def _process_converter(self, f, filt=None):
        """
        Take a conversion function and possibly recreate the frame.
        """
        if filt is None:
            filt = lambda col, c: True

        needs_new_obj = False
        new_obj = dict()
        for i, (col, c) in enumerate(self.obj.items()):
            if filt(col, c):
                new_data, result = f(col, c)
                if result:
                    c = new_data
                    needs_new_obj = True
            new_obj[i] = c

        if needs_new_obj:

            # possibly handle dup columns
            new_obj = DataFrame(new_obj, index=self.obj.index)
            new_obj.columns = self.obj.columns
            self.obj = new_obj

    def _try_convert_types(self):
        if self.obj is None:
            return
        if self.convert_dates:
            self._try_convert_dates()

        self._process_converter(
            lambda col, c: self._try_convert_data(col, c, convert_dates=False)
        )

    def _try_convert_dates(self):
        if self.obj is None:
            return

        # our columns to parse
        convert_dates = self.convert_dates
        if convert_dates is True:
            convert_dates = []
        convert_dates = set(convert_dates)

        def is_ok(col) -> bool:
            """
            Return if this col is ok to try for a date parse.
            """
            if not isinstance(col, str):
                return False

            col_lower = col.lower()
            if (
                col_lower.endswith("_at")
                or col_lower.endswith("_time")
                or col_lower == "modified"
                or col_lower == "date"
                or col_lower == "datetime"
                or col_lower.startswith("timestamp")
            ):
                return True
            return False

        self._process_converter(
            lambda col, c: self._try_convert_to_date(c),
            lambda col, c: (
                (self.keep_default_dates and is_ok(col)) or col in convert_dates
            ),
        )
