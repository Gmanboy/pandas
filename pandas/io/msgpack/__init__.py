# coding: utf-8

from collections import namedtuple

from pandas.io.msgpack.exceptions import *  # noqa
from pandas.io.msgpack._version import version  # noqa


class ExtType(namedtuple("ExtType", "code data")):
    """ExtType represents ext type in msgpack."""

    def __new__(cls, code, data):
        if not isinstance(code, int):
            raise TypeError("code must be int")
        if not isinstance(data, bytes):
            raise TypeError("data must be bytes")
        if not 0 <= code <= 127:
            raise ValueError("code must be 0~127")
        return super().__new__(cls, code, data)


import os  # noqa

from pandas.io.msgpack._packer import Packer  # noqa
from pandas.io.msgpack._unpacker import unpack, unpackb, Unpacker  # noqa


def pack(o, stream, **kwargs):
    """
    Pack object `o` and write it to `stream`

    See :class:`Packer` for options.
    """
    packer = Packer(**kwargs)
    stream.write(packer.pack(o))


def packb(o, **kwargs):
    """
    Pack object `o` and return packed bytes

    See :class:`Packer` for options.
    """
    return Packer(**kwargs).pack(o)


# alias for compatibility to simplejson/marshal/pickle.
load = unpack
loads = unpackb

dump = pack
dumps = packb
