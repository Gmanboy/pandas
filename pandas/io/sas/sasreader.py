"""
Read SAS sas7bdat or xport files.
"""
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Optional, Union, overload

from pandas._typing import FilePathOrBuffer, Label

from pandas.io.common import get_filepath_or_buffer, stringify_path

if TYPE_CHECKING:
    from pandas import DataFrame


# TODO(PY38): replace with Protocol in Python 3.8
class ReaderBase(metaclass=ABCMeta):
    """
    Protocol for XportReader and SAS7BDATReader classes.
    """

    @abstractmethod
    def read(self, nrows=None):
        pass

    @abstractmethod
    def close(self):
        pass


@overload
def read_sas(
    filepath_or_buffer: FilePathOrBuffer,
    format: Optional[str] = ...,
    index: Optional[Label] = ...,
    encoding: Optional[str] = ...,
    chunksize: int = ...,
    iterator: bool = ...,
) -> ReaderBase:
    ...


@overload
def read_sas(
    filepath_or_buffer: FilePathOrBuffer,
    format: Optional[str] = ...,
    index: Optional[Label] = ...,
    encoding: Optional[str] = ...,
    chunksize: None = ...,
    iterator: bool = ...,
) -> Union["DataFrame", ReaderBase]:
    ...


def read_sas(
    filepath_or_buffer: FilePathOrBuffer,
    format: Optional[str] = None,
    index: Optional[Label] = None,
    encoding: Optional[str] = None,
    chunksize: Optional[int] = None,
    iterator: bool = False,
) -> Union["DataFrame", ReaderBase]:
    """
    Read SAS files stored as either XPORT or SAS7BDAT format files.

    Parameters
    ----------
    filepath_or_buffer : str, path object or file-like object
        Any valid string path is acceptable. The string could be a URL. Valid
        URL schemes include http, ftp, s3, and file. For file URLs, a host is
        expected. A local file could be:
        ``file://localhost/path/to/table.sas``.

        If you want to pass in a path object, pandas accepts any
        ``os.PathLike``.

        By file-like object, we refer to objects with a ``read()`` method,
        such as a file handle (e.g. via builtin ``open`` function)
        or ``StringIO``.
    format : str {'xport', 'sas7bdat'} or None
        If None, file format is inferred from file extension. If 'xport' or
        'sas7bdat', uses the corresponding format.
    index : identifier of index column, defaults to None
        Identifier of column that should be used as index of the DataFrame.
    encoding : str, default is None
        Encoding for text data.  If None, text data are stored as raw bytes.
    chunksize : int
        Read file `chunksize` lines at a time, returns iterator.
    iterator : bool, defaults to False
        If True, returns an iterator for reading the file incrementally.

    Returns
    -------
    DataFrame if iterator=False and chunksize=None, else SAS7BDATReader
    or XportReader
    """
    if format is None:
        buffer_error_msg = (
            "If this is a buffer object rather "
            "than a string name, you must specify a format string"
        )
        filepath_or_buffer = stringify_path(filepath_or_buffer)
        if not isinstance(filepath_or_buffer, str):
            raise ValueError(buffer_error_msg)
        fname = filepath_or_buffer.lower()
        if fname.endswith(".xpt"):
            format = "xport"
        elif fname.endswith(".sas7bdat"):
            format = "sas7bdat"
        else:
            raise ValueError("unable to infer format of SAS file")

    ioargs = get_filepath_or_buffer(filepath_or_buffer, encoding)

    reader: ReaderBase
    if format.lower() == "xport":
        from pandas.io.sas.sas_xport import XportReader

        reader = XportReader(
            ioargs.filepath_or_buffer,
            index=index,
            encoding=ioargs.encoding,
            chunksize=chunksize,
        )
    elif format.lower() == "sas7bdat":
        from pandas.io.sas.sas7bdat import SAS7BDATReader

        reader = SAS7BDATReader(
            ioargs.filepath_or_buffer,
            index=index,
            encoding=ioargs.encoding,
            chunksize=chunksize,
        )
    else:
        raise ValueError("unknown SAS format")

    if iterator or chunksize:
        return reader

    try:
        return reader.read()
    finally:
        if ioargs.should_close:
            reader.close()
