""" manage PyTables query interface via Expressions """

import ast
from functools import partial
from typing import Any, Dict, Optional, Tuple

import numpy as np

from pandas._libs.tslibs import Timedelta, Timestamp
from pandas.compat.chainmap import DeepChainMap

from pandas.core.dtypes.common import is_list_like

import pandas as pd
import pandas.core.common as com
from pandas.core.computation import expr, ops, scope as _scope
from pandas.core.computation.common import _ensure_decoded
from pandas.core.computation.expr import BaseExprVisitor
from pandas.core.computation.ops import UndefinedVariableError, is_term

from pandas.io.formats.printing import pprint_thing, pprint_thing_encoded


class PyTablesScope(_scope.Scope):
    __slots__ = ("queryables",)

    queryables: Dict[str, Any]

    def __init__(
        self,
        level: int,
        global_dict=None,
        local_dict=None,
        queryables: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(level + 1, global_dict=global_dict, local_dict=local_dict)
        self.queryables = queryables or dict()


class Term(ops.Term):
    env: PyTablesScope

    def __new__(cls, name, env, side=None, encoding=None):
        klass = Constant if not isinstance(name, str) else cls
        return object.__new__(klass)

    def __init__(self, name, env: PyTablesScope, side=None, encoding=None):
        super().__init__(name, env, side=side, encoding=encoding)

    def _resolve_name(self):
        # must be a queryables
        if self.side == "left":
            # Note: The behavior of __new__ ensures that self.name is a str here
            if self.name not in self.env.queryables:
                raise NameError("name {name!r} is not defined".format(name=self.name))
            return self.name

        # resolve the rhs (and allow it to be None)
        try:
            return self.env.resolve(self.name, is_local=False)
        except UndefinedVariableError:
            return self.name

    # read-only property overwriting read/write property
    @property  # type: ignore
    def value(self):
        return self._value


class Constant(Term):
    def __init__(self, value, env: PyTablesScope, side=None, encoding=None):
        assert isinstance(env, PyTablesScope), type(env)
        super().__init__(value, env, side=side, encoding=encoding)

    def _resolve_name(self):
        return self._name


class BinOp(ops.BinOp):

    _max_selectors = 31

    op: str
    queryables: Dict[str, Any]

    def __init__(self, op: str, lhs, rhs, queryables: Dict[str, Any], encoding):
        super().__init__(op, lhs, rhs)
        self.queryables = queryables
        self.encoding = encoding
        self.condition = None

    def _disallow_scalar_only_bool_ops(self):
        pass

    def prune(self, klass):
        def pr(left, right):
            """ create and return a new specialized BinOp from myself """

            if left is None:
                return right
            elif right is None:
                return left

            k = klass
            if isinstance(left, ConditionBinOp):
                if isinstance(right, ConditionBinOp):
                    k = JointConditionBinOp
                elif isinstance(left, k):
                    return left
                elif isinstance(right, k):
                    return right

            elif isinstance(left, FilterBinOp):
                if isinstance(right, FilterBinOp):
                    k = JointFilterBinOp
                elif isinstance(left, k):
                    return left
                elif isinstance(right, k):
                    return right

            return k(
                self.op, left, right, queryables=self.queryables, encoding=self.encoding
            ).evaluate()

        left, right = self.lhs, self.rhs

        if is_term(left) and is_term(right):
            res = pr(left.value, right.value)
        elif not is_term(left) and is_term(right):
            res = pr(left.prune(klass), right.value)
        elif is_term(left) and not is_term(right):
            res = pr(left.value, right.prune(klass))
        elif not (is_term(left) or is_term(right)):
            res = pr(left.prune(klass), right.prune(klass))

        return res

    def conform(self, rhs):
        """ inplace conform rhs """
        if not is_list_like(rhs):
            rhs = [rhs]
        if isinstance(rhs, np.ndarray):
            rhs = rhs.ravel()
        return rhs

    @property
    def is_valid(self) -> bool:
        """ return True if this is a valid field """
        return self.lhs in self.queryables

    @property
    def is_in_table(self) -> bool:
        """ return True if this is a valid column name for generation (e.g. an
        actual column in the table) """
        return self.queryables.get(self.lhs) is not None

    @property
    def kind(self):
        """ the kind of my field """
        return getattr(self.queryables.get(self.lhs), "kind", None)

    @property
    def meta(self):
        """ the meta of my field """
        return getattr(self.queryables.get(self.lhs), "meta", None)

    @property
    def metadata(self):
        """ the metadata of my field """
        return getattr(self.queryables.get(self.lhs), "metadata", None)

    def generate(self, v) -> str:
        """ create and return the op string for this TermValue """
        val = v.tostring(self.encoding)
        return "({lhs} {op} {val})".format(lhs=self.lhs, op=self.op, val=val)

    def convert_value(self, v) -> "TermValue":
        """ convert the expression that is in the term to something that is
        accepted by pytables """

        def stringify(value):
            if self.encoding is not None:
                encoder = partial(pprint_thing_encoded, encoding=self.encoding)
            else:
                encoder = pprint_thing
            return encoder(value)

        kind = _ensure_decoded(self.kind)
        meta = _ensure_decoded(self.meta)
        if kind == "datetime64" or kind == "datetime":
            if isinstance(v, (int, float)):
                v = stringify(v)
            v = _ensure_decoded(v)
            v = Timestamp(v)
            if v.tz is not None:
                v = v.tz_convert("UTC")
            return TermValue(v, v.value, kind)
        elif kind == "timedelta64" or kind == "timedelta":
            v = Timedelta(v, unit="s").value
            return TermValue(int(v), v, kind)
        elif meta == "category":
            metadata = com.values_from_object(self.metadata)
            result = metadata.searchsorted(v, side="left")

            # result returns 0 if v is first element or if v is not in metadata
            # check that metadata contains v
            if not result and v not in metadata:
                result = -1
            return TermValue(result, result, "integer")
        elif kind == "integer":
            v = int(float(v))
            return TermValue(v, v, kind)
        elif kind == "float":
            v = float(v)
            return TermValue(v, v, kind)
        elif kind == "bool":
            if isinstance(v, str):
                v = not v.strip().lower() in [
                    "false",
                    "f",
                    "no",
                    "n",
                    "none",
                    "0",
                    "[]",
                    "{}",
                    "",
                ]
            else:
                v = bool(v)
            return TermValue(v, v, kind)
        elif isinstance(v, str):
            # string quoting
            return TermValue(v, stringify(v), "string")
        else:
            raise TypeError(
                "Cannot compare {v} of type {typ} to {kind} column".format(
                    v=v, typ=type(v), kind=kind
                )
            )

    def convert_values(self):
        pass


class FilterBinOp(BinOp):
    filter: Optional[Tuple[Any, Any, pd.Index]] = None

    def __repr__(self) -> str:
        if self.filter is None:
            return "Filter: Not Initialized"
        return pprint_thing(
            "[Filter : [{lhs}] -> [{op}]".format(lhs=self.filter[0], op=self.filter[1])
        )

    def invert(self):
        """ invert the filter """
        if self.filter is not None:
            f = list(self.filter)
            f[1] = self.generate_filter_op(invert=True)
            self.filter = tuple(f)
        return self

    def format(self):
        """ return the actual filter format """
        return [self.filter]

    def evaluate(self):

        if not self.is_valid:
            raise ValueError("query term is not valid [{slf}]".format(slf=self))

        rhs = self.conform(self.rhs)
        values = list(rhs)

        if self.is_in_table:

            # if too many values to create the expression, use a filter instead
            if self.op in ["==", "!="] and len(values) > self._max_selectors:

                filter_op = self.generate_filter_op()
                self.filter = (self.lhs, filter_op, pd.Index(values))

                return self
            return None

        # equality conditions
        if self.op in ["==", "!="]:

            filter_op = self.generate_filter_op()
            self.filter = (self.lhs, filter_op, pd.Index(values))

        else:
            raise TypeError(
                "passing a filterable condition to a non-table "
                "indexer [{slf}]".format(slf=self)
            )

        return self

    def generate_filter_op(self, invert: bool = False):
        if (self.op == "!=" and not invert) or (self.op == "==" and invert):
            return lambda axis, vals: ~axis.isin(vals)
        else:
            return lambda axis, vals: axis.isin(vals)


class JointFilterBinOp(FilterBinOp):
    def format(self):
        raise NotImplementedError("unable to collapse Joint Filters")

    def evaluate(self):
        return self


class ConditionBinOp(BinOp):
    def __repr__(self) -> str:
        return pprint_thing("[Condition : [{cond}]]".format(cond=self.condition))

    def invert(self):
        """ invert the condition """
        # if self.condition is not None:
        #    self.condition = "~(%s)" % self.condition
        # return self
        raise NotImplementedError(
            "cannot use an invert condition when passing to numexpr"
        )

    def format(self):
        """ return the actual ne format """
        return self.condition

    def evaluate(self):

        if not self.is_valid:
            raise ValueError("query term is not valid [{slf}]".format(slf=self))

        # convert values if we are in the table
        if not self.is_in_table:
            return None

        rhs = self.conform(self.rhs)
        values = [self.convert_value(v) for v in rhs]

        # equality conditions
        if self.op in ["==", "!="]:

            # too many values to create the expression?
            if len(values) <= self._max_selectors:
                vs = [self.generate(v) for v in values]
                self.condition = "({cond})".format(cond=" | ".join(vs))

            # use a filter after reading
            else:
                return None
        else:
            self.condition = self.generate(values[0])

        return self


class JointConditionBinOp(ConditionBinOp):
    def evaluate(self):
        self.condition = "({lhs} {op} {rhs})".format(
            lhs=self.lhs.condition, op=self.op, rhs=self.rhs.condition
        )
        return self


class UnaryOp(ops.UnaryOp):
    def prune(self, klass):

        if self.op != "~":
            raise NotImplementedError("UnaryOp only support invert type ops")

        operand = self.operand
        operand = operand.prune(klass)

        if operand is not None:
            if issubclass(klass, ConditionBinOp):
                if operand.condition is not None:
                    return operand.invert()
            elif issubclass(klass, FilterBinOp):
                if operand.filter is not None:
                    return operand.invert()

        return None


class PyTablesExprVisitor(BaseExprVisitor):
    const_type = Constant
    term_type = Term

    def __init__(self, env, engine, parser, **kwargs):
        super().__init__(env, engine, parser)
        for bin_op in self.binary_ops:
            bin_node = self.binary_op_nodes_map[bin_op]
            setattr(
                self,
                "visit_{node}".format(node=bin_node),
                lambda node, bin_op=bin_op: partial(BinOp, bin_op, **kwargs),
            )

    def visit_UnaryOp(self, node, **kwargs):
        if isinstance(node.op, (ast.Not, ast.Invert)):
            return UnaryOp("~", self.visit(node.operand))
        elif isinstance(node.op, ast.USub):
            return self.const_type(-self.visit(node.operand).value, self.env)
        elif isinstance(node.op, ast.UAdd):
            raise NotImplementedError("Unary addition not supported")

    def visit_Index(self, node, **kwargs):
        return self.visit(node.value).value

    def visit_Assign(self, node, **kwargs):
        cmpr = ast.Compare(
            ops=[ast.Eq()], left=node.targets[0], comparators=[node.value]
        )
        return self.visit(cmpr)

    def visit_Subscript(self, node, **kwargs):
        # only allow simple subscripts

        value = self.visit(node.value)
        slobj = self.visit(node.slice)
        try:
            value = value.value
        except AttributeError:
            pass

        try:
            return self.const_type(value[slobj], self.env)
        except TypeError:
            raise ValueError(
                "cannot subscript {value!r} with "
                "{slobj!r}".format(value=value, slobj=slobj)
            )

    def visit_Attribute(self, node, **kwargs):
        attr = node.attr
        value = node.value

        ctx = node.ctx.__class__
        if ctx == ast.Load:
            # resolve the value
            resolved = self.visit(value)

            # try to get the value to see if we are another expression
            try:
                resolved = resolved.value
            except (AttributeError):
                pass

            try:
                return self.term_type(getattr(resolved, attr), self.env)
            except AttributeError:

                # something like datetime.datetime where scope is overridden
                if isinstance(value, ast.Name) and value.id == attr:
                    return resolved

        raise ValueError("Invalid Attribute context {name}".format(name=ctx.__name__))

    def translate_In(self, op):
        return ast.Eq() if isinstance(op, ast.In) else op

    def _rewrite_membership_op(self, node, left, right):
        return self.visit(node.op), node.op, left, right


def _validate_where(w):
    """
    Validate that the where statement is of the right type.

    The type may either be String, Expr, or list-like of Exprs.

    Parameters
    ----------
    w : String term expression, Expr, or list-like of Exprs.

    Returns
    -------
    where : The original where clause if the check was successful.

    Raises
    ------
    TypeError : An invalid data type was passed in for w (e.g. dict).
    """

    if not (isinstance(w, (PyTablesExpr, str)) or is_list_like(w)):
        raise TypeError(
            "where must be passed as a string, PyTablesExpr, "
            "or list-like of PyTablesExpr"
        )

    return w


class PyTablesExpr(expr.Expr):
    """
    Hold a pytables-like expression, comprised of possibly multiple 'terms'.

    Parameters
    ----------
    where : string term expression, PyTablesExpr, or list-like of PyTablesExprs
    queryables : a "kinds" map (dict of column name -> kind), or None if column
        is non-indexable
    encoding : an encoding that will encode the query terms

    Returns
    -------
    a PyTablesExpr object

    Examples
    --------

    'index>=date'
    "columns=['A', 'D']"
    'columns=A'
    'columns==A'
    "~(columns=['A','B'])"
    'index>df.index[3] & string="bar"'
    '(index>df.index[3] & index<=df.index[6]) | string="bar"'
    "ts>=Timestamp('2012-02-01')"
    "major_axis>=20130101"
    """

    _visitor: Optional[PyTablesExprVisitor]
    env: PyTablesScope

    def __init__(
        self,
        where,
        queryables: Optional[Dict[str, Any]] = None,
        encoding=None,
        scope_level: int = 0,
    ):

        where = _validate_where(where)

        self.encoding = encoding
        self.condition = None
        self.filter = None
        self.terms = None
        self._visitor = None

        # capture the environment if needed
        local_dict = DeepChainMap()

        if isinstance(where, PyTablesExpr):
            local_dict = where.env.scope
            _where = where.expr

        elif isinstance(where, (list, tuple)):
            where = list(where)
            for idx, w in enumerate(where):
                if isinstance(w, PyTablesExpr):
                    local_dict = w.env.scope
                else:
                    w = _validate_where(w)
                    where[idx] = w
            _where = " & ".join(map("({})".format, com.flatten(where)))
        else:
            _where = where

        self.expr = _where
        self.env = PyTablesScope(scope_level + 1, local_dict=local_dict)

        if queryables is not None and isinstance(self.expr, str):
            self.env.queryables.update(queryables)
            self._visitor = PyTablesExprVisitor(
                self.env,
                queryables=queryables,
                parser="pytables",
                engine="pytables",
                encoding=encoding,
            )
            self.terms = self.parse()

    def __repr__(self) -> str:
        if self.terms is not None:
            return pprint_thing(self.terms)
        return pprint_thing(self.expr)

    def evaluate(self):
        """ create and return the numexpr condition and filter """

        try:
            self.condition = self.terms.prune(ConditionBinOp)
        except AttributeError:
            raise ValueError(
                "cannot process expression [{expr}], [{slf}] "
                "is not a valid condition".format(expr=self.expr, slf=self)
            )
        try:
            self.filter = self.terms.prune(FilterBinOp)
        except AttributeError:
            raise ValueError(
                "cannot process expression [{expr}], [{slf}] "
                "is not a valid filter".format(expr=self.expr, slf=self)
            )

        return self.condition, self.filter


class TermValue:
    """ hold a term value the we use to construct a condition/filter """

    def __init__(self, value, converted, kind: str):
        assert isinstance(kind, str), kind
        self.value = value
        self.converted = converted
        self.kind = kind

    def tostring(self, encoding) -> str:
        """ quote the string if not encoded
            else encode and return """
        if self.kind == "string":
            if encoding is not None:
                return str(self.converted)
            return '"{converted}"'.format(converted=self.converted)
        elif self.kind == "float":
            # python 2 str(float) is not always
            # round-trippable so use repr()
            return repr(self.converted)
        return str(self.converted)


def maybe_expression(s) -> bool:
    """ loose checking if s is a pytables-acceptable expression """
    if not isinstance(s, str):
        return False
    ops = PyTablesExprVisitor.binary_ops + PyTablesExprVisitor.unary_ops + ("=",)

    # make sure we have an op at least
    return any(op in s for op in ops)
