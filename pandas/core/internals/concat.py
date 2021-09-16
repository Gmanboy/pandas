from __future__ import annotations

import itertools
from typing import (
    TYPE_CHECKING,
    Sequence,
    cast,
)

import numpy as np

from pandas._libs import (
    NaT,
    internals as libinternals,
)
from pandas._typing import (
    ArrayLike,
    DtypeObj,
    Manager,
    Shape,
)
from pandas.util._decorators import cache_readonly

from pandas.core.dtypes.cast import (
    ensure_dtype_can_hold_na,
    find_common_type,
)
from pandas.core.dtypes.common import (
    is_1d_only_ea_dtype,
    is_1d_only_ea_obj,
    is_datetime64tz_dtype,
    is_dtype_equal,
)
from pandas.core.dtypes.concat import (
    cast_to_common_type,
    concat_compat,
)
from pandas.core.dtypes.dtypes import ExtensionDtype

import pandas.core.algorithms as algos
from pandas.core.arrays import (
    DatetimeArray,
    ExtensionArray,
)
from pandas.core.construction import ensure_wrapped_if_datetimelike
from pandas.core.internals.array_manager import (
    ArrayManager,
    NullArrayProxy,
)
from pandas.core.internals.blocks import (
    ensure_block_shape,
    new_block,
)
from pandas.core.internals.managers import BlockManager

if TYPE_CHECKING:
    from pandas import Index
    from pandas.core.internals.blocks import Block


def _concatenate_array_managers(
    mgrs_indexers, axes: list[Index], concat_axis: int, copy: bool
) -> Manager:
    """
    Concatenate array managers into one.

    Parameters
    ----------
    mgrs_indexers : list of (ArrayManager, {axis: indexer,...}) tuples
    axes : list of Index
    concat_axis : int
    copy : bool

    Returns
    -------
    ArrayManager
    """
    # reindex all arrays
    mgrs = []
    for mgr, indexers in mgrs_indexers:
        for ax, indexer in indexers.items():
            mgr = mgr.reindex_indexer(
                axes[ax], indexer, axis=ax, allow_dups=True, use_na_proxy=True
            )
        mgrs.append(mgr)

    if concat_axis == 1:
        # concatting along the rows -> concat the reindexed arrays
        # TODO(ArrayManager) doesn't yet preserve the correct dtype
        arrays = [
            concat_arrays([mgrs[i].arrays[j] for i in range(len(mgrs))])
            for j in range(len(mgrs[0].arrays))
        ]
    else:
        # concatting along the columns -> combine reindexed arrays in a single manager
        assert concat_axis == 0
        arrays = list(itertools.chain.from_iterable([mgr.arrays for mgr in mgrs]))
        if copy:
            arrays = [x.copy() for x in arrays]

    new_mgr = ArrayManager(arrays, [axes[1], axes[0]], verify_integrity=False)
    return new_mgr


def concat_arrays(to_concat: list) -> ArrayLike:
    """
    Alternative for concat_compat but specialized for use in the ArrayManager.

    Differences: only deals with 1D arrays (no axis keyword), assumes
    ensure_wrapped_if_datetimelike and does not skip empty arrays to determine
    the dtype.
    In addition ensures that all NullArrayProxies get replaced with actual
    arrays.

    Parameters
    ----------
    to_concat : list of arrays

    Returns
    -------
    np.ndarray or ExtensionArray
    """
    # ignore the all-NA proxies to determine the resulting dtype
    to_concat_no_proxy = [x for x in to_concat if not isinstance(x, NullArrayProxy)]

    dtypes = {x.dtype for x in to_concat_no_proxy}
    single_dtype = len(dtypes) == 1

    if single_dtype:
        target_dtype = to_concat_no_proxy[0].dtype
    elif all(x.kind in ["i", "u", "b"] and isinstance(x, np.dtype) for x in dtypes):
        # GH#42092
        target_dtype = np.find_common_type(list(dtypes), [])
    else:
        target_dtype = find_common_type([arr.dtype for arr in to_concat_no_proxy])

    if target_dtype.kind in ["m", "M"]:
        # for datetimelike use DatetimeArray/TimedeltaArray concatenation
        # don't use arr.astype(target_dtype, copy=False), because that doesn't
        # work for DatetimeArray/TimedeltaArray (returns ndarray)
        to_concat = [
            arr.to_array(target_dtype) if isinstance(arr, NullArrayProxy) else arr
            for arr in to_concat
        ]
        return type(to_concat_no_proxy[0])._concat_same_type(to_concat, axis=0)

    to_concat = [
        arr.to_array(target_dtype)
        if isinstance(arr, NullArrayProxy)
        else cast_to_common_type(arr, target_dtype)
        for arr in to_concat
    ]

    if isinstance(to_concat[0], ExtensionArray):
        cls = type(to_concat[0])
        return cls._concat_same_type(to_concat)

    result = np.concatenate(to_concat)

    # TODO decide on exact behaviour (we shouldn't do this only for empty result)
    # see https://github.com/pandas-dev/pandas/issues/39817
    if len(result) == 0:
        # all empties -> check for bool to not coerce to float
        kinds = {obj.dtype.kind for obj in to_concat_no_proxy}
        if len(kinds) != 1:
            if "b" in kinds:
                result = result.astype(object)
    return result


def concatenate_managers(
    mgrs_indexers, axes: list[Index], concat_axis: int, copy: bool
) -> Manager:
    """
    Concatenate block managers into one.

    Parameters
    ----------
    mgrs_indexers : list of (BlockManager, {axis: indexer,...}) tuples
    axes : list of Index
    concat_axis : int
    copy : bool

    Returns
    -------
    BlockManager
    """
    # TODO(ArrayManager) this assumes that all managers are of the same type
    if isinstance(mgrs_indexers[0][0], ArrayManager):
        return _concatenate_array_managers(mgrs_indexers, axes, concat_axis, copy)

    mgrs_indexers = _maybe_reindex_columns_na_proxy(axes, mgrs_indexers)

    concat_plans = [
        _get_mgr_concatenation_plan(mgr, indexers) for mgr, indexers in mgrs_indexers
    ]
    concat_plan = _combine_concat_plans(concat_plans, concat_axis)
    blocks = []

    for placement, join_units in concat_plan:
        unit = join_units[0]
        blk = unit.block

        if len(join_units) == 1 and not join_units[0].indexers:
            values = blk.values
            if copy:
                values = values.copy()
            else:
                values = values.view()
            fastpath = True
        elif _is_uniform_join_units(join_units):
            vals = [ju.block.values for ju in join_units]

            if not blk.is_extension:
                # _is_uniform_join_units ensures a single dtype, so
                #  we can use np.concatenate, which is more performant
                #  than concat_compat
                values = np.concatenate(vals, axis=blk.ndim - 1)
            else:
                # TODO(EA2D): special-casing not needed with 2D EAs
                values = concat_compat(vals, axis=1)
                values = ensure_block_shape(values, blk.ndim)

            values = ensure_wrapped_if_datetimelike(values)

            fastpath = blk.values.dtype == values.dtype
        else:
            values = _concatenate_join_units(join_units, concat_axis, copy=copy)
            fastpath = False

        if fastpath:
            b = blk.make_block_same_class(values, placement=placement)
        else:
            b = new_block(values, placement=placement, ndim=len(axes))

        blocks.append(b)

    return BlockManager(tuple(blocks), axes)


def _maybe_reindex_columns_na_proxy(
    axes: list[Index], mgrs_indexers: list[tuple[BlockManager, dict[int, np.ndarray]]]
) -> list[tuple[BlockManager, dict[int, np.ndarray]]]:
    """
    Reindex along columns so that all of the BlockManagers being concatenated
    have matching columns.

    Columns added in this reindexing have dtype=np.void, indicating they
    should be ignored when choosing a column's final dtype.
    """
    new_mgrs_indexers = []
    for mgr, indexers in mgrs_indexers:
        # We only reindex for axis=0 (i.e. columns), as this can be done cheaply
        if 0 in indexers:
            new_mgr = mgr.reindex_indexer(
                axes[0],
                indexers[0],
                axis=0,
                copy=False,
                only_slice=True,
                allow_dups=True,
                use_na_proxy=True,
            )
            new_indexers = indexers.copy()
            del new_indexers[0]
            new_mgrs_indexers.append((new_mgr, new_indexers))
        else:
            new_mgrs_indexers.append((mgr, indexers))

    return new_mgrs_indexers


def _get_mgr_concatenation_plan(mgr: BlockManager, indexers: dict[int, np.ndarray]):
    """
    Construct concatenation plan for given block manager and indexers.

    Parameters
    ----------
    mgr : BlockManager
    indexers : dict of {axis: indexer}

    Returns
    -------
    plan : list of (BlockPlacement, JoinUnit) tuples

    """
    # Calculate post-reindex shape , save for item axis which will be separate
    # for each block anyway.
    mgr_shape_list = list(mgr.shape)
    for ax, indexer in indexers.items():
        mgr_shape_list[ax] = len(indexer)
    mgr_shape = tuple(mgr_shape_list)

    assert 0 not in indexers

    if mgr.is_single_block:
        blk = mgr.blocks[0]
        return [(blk.mgr_locs, JoinUnit(blk, mgr_shape, indexers))]

    blknos = mgr.blknos
    blklocs = mgr.blklocs

    plan = []
    for blkno, placements in libinternals.get_blkno_placements(blknos, group=False):

        assert placements.is_slice_like
        assert blkno != -1

        join_unit_indexers = indexers.copy()

        shape_list = list(mgr_shape)
        shape_list[0] = len(placements)
        shape = tuple(shape_list)

        blk = mgr.blocks[blkno]
        ax0_blk_indexer = blklocs[placements.indexer]

        unit_no_ax0_reindexing = (
            len(placements) == len(blk.mgr_locs)
            and
            # Fastpath detection of join unit not
            # needing to reindex its block: no ax0
            # reindexing took place and block
            # placement was sequential before.
            (
                (blk.mgr_locs.is_slice_like and blk.mgr_locs.as_slice.step == 1)
                or
                # Slow-ish detection: all indexer locs
                # are sequential (and length match is
                # checked above).
                (np.diff(ax0_blk_indexer) == 1).all()
            )
        )

        if not unit_no_ax0_reindexing:
            # create block from subset of columns
            blk = blk.getitem_block(ax0_blk_indexer)

        # Assertions disabled for performance
        # assert blk._mgr_locs.as_slice == placements.as_slice
        # assert blk.shape[0] == shape[0]
        unit = JoinUnit(blk, shape, join_unit_indexers)

        plan.append((placements, unit))

    return plan


class JoinUnit:
    def __init__(self, block: Block, shape: Shape, indexers=None):
        # Passing shape explicitly is required for cases when block is None.
        # Note: block is None implies indexers is None, but not vice-versa
        if indexers is None:
            indexers = {}
        # we should *never* have `0 in indexers`
        self.block = block
        self.indexers = indexers
        self.shape = shape

    def __repr__(self) -> str:
        return f"{type(self).__name__}({repr(self.block)}, {self.indexers})"

    @cache_readonly
    def needs_filling(self) -> bool:
        for indexer in self.indexers.values():
            # FIXME: cache results of indexer == -1 checks.
            if (indexer == -1).any():
                return True

        return False

    @cache_readonly
    def dtype(self):
        blk = self.block
        if blk.values.dtype.kind == "V":
            raise AssertionError("Block is None, no dtype")

        if not self.needs_filling:
            return blk.dtype
        return ensure_dtype_can_hold_na(blk.dtype)

    @cache_readonly
    def is_na(self) -> bool:
        blk = self.block
        if blk.dtype.kind == "V":
            return True
        return False

    def get_reindexed_values(self, empty_dtype: DtypeObj) -> ArrayLike:
        values: ArrayLike

        if self.is_na:
            return make_na_array(empty_dtype, self.shape)

        else:

            if (not self.indexers) and (not self.block._can_consolidate):
                # preserve these for validation in concat_compat
                return self.block.values

            # No dtype upcasting is done here, it will be performed during
            # concatenation itself.
            values = self.block.values

        if not self.indexers:
            # If there's no indexing to be done, we want to signal outside
            # code that this array must be copied explicitly.  This is done
            # by returning a view and checking `retval.base`.
            values = values.view()

        else:
            for ax, indexer in self.indexers.items():
                values = algos.take_nd(values, indexer, axis=ax)

        return values


def make_na_array(dtype: DtypeObj, shape: Shape) -> ArrayLike:
    """
    Construct an np.ndarray or ExtensionArray of the given dtype and shape
    holding all-NA values.
    """
    if is_datetime64tz_dtype(dtype):
        # NaT here is analogous to dtype.na_value below
        i8values = np.full(shape, NaT.value)
        return DatetimeArray(i8values, dtype=dtype)

    elif is_1d_only_ea_dtype(dtype):
        dtype = cast(ExtensionDtype, dtype)
        cls = dtype.construct_array_type()

        missing_arr = cls._from_sequence([], dtype=dtype)
        nrows = shape[-1]
        taker = -1 * np.ones((nrows,), dtype=np.intp)
        return missing_arr.take(taker, allow_fill=True, fill_value=dtype.na_value)
    elif isinstance(dtype, ExtensionDtype):
        # TODO: no tests get here, a handful would if we disabled
        #  the dt64tz special-case above (which is faster)
        cls = dtype.construct_array_type()
        missing_arr = cls._empty(shape=shape, dtype=dtype)
        missing_arr[:] = dtype.na_value
        return missing_arr
    else:
        # NB: we should never get here with dtype integer or bool;
        #  if we did, the missing_arr.fill would cast to gibberish
        missing_arr = np.empty(shape, dtype=dtype)
        fill_value = _dtype_to_na_value(dtype)
        missing_arr.fill(fill_value)
        return missing_arr


def _concatenate_join_units(
    join_units: list[JoinUnit], concat_axis: int, copy: bool
) -> ArrayLike:
    """
    Concatenate values from several join units along selected axis.
    """
    if concat_axis == 0 and len(join_units) > 1:
        # Concatenating join units along ax0 is handled in _merge_blocks.
        raise AssertionError("Concatenating join units along axis0")

    empty_dtype = _get_empty_dtype(join_units)

    to_concat = [ju.get_reindexed_values(empty_dtype=empty_dtype) for ju in join_units]

    if len(to_concat) == 1:
        # Only one block, nothing to concatenate.
        concat_values = to_concat[0]
        if copy:
            if isinstance(concat_values, np.ndarray):
                # non-reindexed (=not yet copied) arrays are made into a view
                # in JoinUnit.get_reindexed_values
                if concat_values.base is not None:
                    concat_values = concat_values.copy()
            else:
                concat_values = concat_values.copy()

    elif any(is_1d_only_ea_obj(t) for t in to_concat):
        # TODO(EA2D): special case not needed if all EAs used HybridBlocks
        # NB: we are still assuming here that Hybrid blocks have shape (1, N)
        # concatting with at least one EA means we are concatting a single column
        # the non-EA values are 2D arrays with shape (1, n)

        # error: No overload variant of "__getitem__" of "ExtensionArray" matches
        # argument type "Tuple[int, slice]"
        to_concat = [
            t if is_1d_only_ea_obj(t) else t[0, :]  # type: ignore[call-overload]
            for t in to_concat
        ]
        concat_values = concat_compat(to_concat, axis=0, ea_compat_axis=True)
        concat_values = ensure_block_shape(concat_values, 2)

    else:
        concat_values = concat_compat(to_concat, axis=concat_axis)

    return concat_values


def _dtype_to_na_value(dtype: DtypeObj):
    """
    Find the NA value to go with this dtype.
    """
    if isinstance(dtype, ExtensionDtype):
        return dtype.na_value
    elif dtype.kind in ["m", "M"]:
        return dtype.type("NaT")
    elif dtype.kind in ["f", "c"]:
        return dtype.type("NaN")
    elif dtype.kind == "b":
        # different from missing.na_value_for_dtype
        return None
    elif dtype.kind in ["i", "u"]:
        return np.nan
    elif dtype.kind == "O":
        return np.nan
    raise NotImplementedError


def _get_empty_dtype(join_units: Sequence[JoinUnit]) -> DtypeObj:
    """
    Return dtype and N/A values to use when concatenating specified units.

    Returned N/A value may be None which means there was no casting involved.

    Returns
    -------
    dtype
    """
    if len(join_units) == 1:
        blk = join_units[0].block
        return blk.dtype

    if _is_uniform_reindex(join_units):
        # FIXME: integrate property
        empty_dtype = join_units[0].block.dtype
        return empty_dtype

    has_none_blocks = any(unit.is_na for unit in join_units)

    dtypes = [unit.dtype for unit in join_units if not unit.is_na]

    dtype = find_common_type(dtypes)
    if has_none_blocks:
        dtype = ensure_dtype_can_hold_na(dtype)
    return dtype


def _is_uniform_join_units(join_units: list[JoinUnit]) -> bool:
    """
    Check if the join units consist of blocks of uniform type that can
    be concatenated using Block.concat_same_type instead of the generic
    _concatenate_join_units (which uses `concat_compat`).

    """
    first = join_units[0].block
    if first.dtype.kind == "V":
        return False
    return (
        # exclude cases where a) ju.block is None or b) we have e.g. Int64+int64
        all(type(ju.block) is type(first) for ju in join_units)
        and
        # e.g. DatetimeLikeBlock can be dt64 or td64, but these are not uniform
        all(
            is_dtype_equal(ju.block.dtype, first.dtype)
            # GH#42092 we only want the dtype_equal check for non-numeric blocks
            #  (for now, may change but that would need a deprecation)
            or ju.block.dtype.kind in ["b", "i", "u"]
            for ju in join_units
        )
        and
        # no blocks that would get missing values (can lead to type upcasts)
        # unless we're an extension dtype.
        all(not ju.is_na or ju.block.is_extension for ju in join_units)
        and
        # no blocks with indexers (as then the dimensions do not fit)
        all(not ju.indexers for ju in join_units)
        and
        # only use this path when there is something to concatenate
        len(join_units) > 1
    )


def _is_uniform_reindex(join_units) -> bool:
    return (
        # TODO: should this be ju.block._can_hold_na?
        all(ju.block.is_extension for ju in join_units)
        and len({ju.block.dtype.name for ju in join_units}) == 1
    )


def _trim_join_unit(join_unit: JoinUnit, length: int) -> JoinUnit:
    """
    Reduce join_unit's shape along item axis to length.

    Extra items that didn't fit are returned as a separate block.
    """
    assert 0 not in join_unit.indexers
    extra_indexers = join_unit.indexers

    extra_block = join_unit.block.getitem_block(slice(length, None))
    join_unit.block = join_unit.block.getitem_block(slice(length))

    extra_shape = (join_unit.shape[0] - length,) + join_unit.shape[1:]
    join_unit.shape = (length,) + join_unit.shape[1:]

    return JoinUnit(block=extra_block, indexers=extra_indexers, shape=extra_shape)


def _combine_concat_plans(plans, concat_axis: int):
    """
    Combine multiple concatenation plans into one.

    existing_plan is updated in-place.
    """
    if len(plans) == 1:
        for p in plans[0]:
            yield p[0], [p[1]]

    elif concat_axis == 0:
        offset = 0
        for plan in plans:
            last_plc = None

            for plc, unit in plan:
                yield plc.add(offset), [unit]
                last_plc = plc

            if last_plc is not None:
                offset += last_plc.as_slice.stop

    else:
        # singleton list so we can modify it as a side-effect within _next_or_none
        num_ended = [0]

        def _next_or_none(seq):
            retval = next(seq, None)
            if retval is None:
                num_ended[0] += 1
            return retval

        plans = list(map(iter, plans))
        next_items = list(map(_next_or_none, plans))

        while num_ended[0] != len(next_items):
            if num_ended[0] > 0:
                raise ValueError("Plan shapes are not aligned")

            placements, units = zip(*next_items)

            lengths = list(map(len, placements))
            min_len, max_len = min(lengths), max(lengths)

            if min_len == max_len:
                yield placements[0], units
                next_items[:] = map(_next_or_none, plans)
            else:
                yielded_placement = None
                yielded_units = [None] * len(next_items)
                for i, (plc, unit) in enumerate(next_items):
                    yielded_units[i] = unit
                    if len(plc) > min_len:
                        # _trim_join_unit updates unit in place, so only
                        # placement needs to be sliced to skip min_len.
                        next_items[i] = (plc[min_len:], _trim_join_unit(unit, min_len))
                    else:
                        yielded_placement = plc
                        next_items[i] = _next_or_none(plans[i])

                yield yielded_placement, yielded_units
