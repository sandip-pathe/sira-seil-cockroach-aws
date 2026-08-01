"""Constrained, deterministic three-valued rule grammar."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from .enums import RuleOperator, TruthValue
from .errors import DomainValidationError

_FIELD_PATH = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)*$")


def resolve_field(context: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    """Resolve an approved dotted taxonomy path without executing code."""

    if not isinstance(path, str) or not _FIELD_PATH.fullmatch(path):
        raise DomainValidationError("rule field must be a valid dotted path")
    current: Any = context
    for segment in path.split("."):
        if not segment or segment.startswith("_"):
            raise DomainValidationError("private or empty field path segments are prohibited")
        if isinstance(current, Mapping) and segment in current:
            current = current[segment]
        else:
            return False, None
    return True, current


def _as_decimal(value: Any) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise InvalidOperation
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, str)):
        return Decimal(value)
    raise InvalidOperation


def _as_date(value: Any) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise ValueError


def _collection(value: Any) -> bool:
    return isinstance(value, (Sequence, set, frozenset)) and not isinstance(
        value, (str, bytes, bytearray)
    )


def _strict_equal(left: Any, right: Any) -> bool:
    # Python treats True == 1 and False == 0. That coercion is unsafe for typed
    # policy fields, so booleans compare only with booleans.
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    return bool(left == right)


@dataclass(frozen=True, slots=True)
class RuleCondition:
    field: str
    operator: RuleOperator
    value: Any = None

    def __post_init__(self) -> None:
        if not isinstance(self.operator, RuleOperator):
            try:
                object.__setattr__(self, "operator", RuleOperator(self.operator))
            except (TypeError, ValueError) as exc:
                raise DomainValidationError("unsupported rule operator") from exc
        # Validate the path without requiring a value to be present.
        resolve_field({}, self.field)
        if self.operator in {RuleOperator.IN, RuleOperator.NOT_IN, RuleOperator.CONTAINS_ALL}:
            if not _collection(self.value):
                raise DomainValidationError(f"{self.operator.value} requires a list-like value")
        if self.operator is RuleOperator.EXISTS and not isinstance(self.value, bool):
            raise DomainValidationError("exists requires a boolean expected value")

    def evaluate(self, context: Mapping[str, Any]) -> RuleEvaluation:
        found, actual = resolve_field(context, self.field)
        if self.operator is RuleOperator.EXISTS:
            matched = (found and actual is not None) == self.value
            return RuleEvaluation(TruthValue.TRUE if matched else TruthValue.FALSE)
        if not found or actual is None:
            return RuleEvaluation(TruthValue.UNRESOLVED, (self.field,))

        try:
            matched = self._compare(actual)
        except (InvalidOperation, TypeError, ValueError):
            return RuleEvaluation(TruthValue.UNRESOLVED, (self.field,))
        return RuleEvaluation(TruthValue.TRUE if matched else TruthValue.FALSE)

    def _compare(self, actual: Any) -> bool:
        op = self.operator
        expected = self.value
        if op is RuleOperator.EQ:
            return _strict_equal(actual, expected)
        if op is RuleOperator.NEQ:
            return not _strict_equal(actual, expected)
        if op is RuleOperator.IN:
            return any(_strict_equal(actual, item) for item in expected)
        if op is RuleOperator.NOT_IN:
            return not any(_strict_equal(actual, item) for item in expected)
        if op is RuleOperator.CONTAINS:
            return expected in actual
        if op is RuleOperator.CONTAINS_ALL:
            if not _collection(actual):
                raise TypeError
            return all(
                any(_strict_equal(item, actual_item) for actual_item in actual) for item in expected
            )
        if op in {RuleOperator.GTE, RuleOperator.LTE, RuleOperator.GT, RuleOperator.LT}:
            left, right = _as_decimal(actual), _as_decimal(expected)
            return {
                RuleOperator.GTE: left >= right,
                RuleOperator.LTE: left <= right,
                RuleOperator.GT: left > right,
                RuleOperator.LT: left < right,
            }[op]
        if op in {
            RuleOperator.DATE_BEFORE,
            RuleOperator.DATE_ON_OR_BEFORE,
            RuleOperator.DATE_AFTER,
            RuleOperator.DATE_ON_OR_AFTER,
        }:
            left_date, right_date = _as_date(actual), _as_date(expected)
            return {
                RuleOperator.DATE_BEFORE: left_date < right_date,
                RuleOperator.DATE_ON_OR_BEFORE: left_date <= right_date,
                RuleOperator.DATE_AFTER: left_date > right_date,
                RuleOperator.DATE_ON_OR_AFTER: left_date >= right_date,
            }[op]
        raise DomainValidationError(f"unsupported operator: {op}")


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    value: TruthValue
    unresolved_fields: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RuleExpression:
    conditions: tuple[RuleCondition, ...]
    mode: Literal["all", "any"] = "all"

    def __post_init__(self) -> None:
        object.__setattr__(self, "conditions", tuple(self.conditions))
        if not self.conditions:
            raise DomainValidationError("a rule expression needs at least one condition")
        if self.mode not in {"all", "any"}:
            raise DomainValidationError("rule expression mode must be all or any")

    def evaluate(self, context: Mapping[str, Any]) -> RuleEvaluation:
        results = tuple(condition.evaluate(context) for condition in self.conditions)
        unresolved = tuple(
            sorted({field for result in results for field in result.unresolved_fields})
        )
        values = {result.value for result in results}
        if self.mode == "all":
            if TruthValue.FALSE in values:
                return RuleEvaluation(TruthValue.FALSE, unresolved)
            if TruthValue.UNRESOLVED in values:
                return RuleEvaluation(TruthValue.UNRESOLVED, unresolved)
            return RuleEvaluation(TruthValue.TRUE)
        if TruthValue.TRUE in values:
            return RuleEvaluation(TruthValue.TRUE, unresolved)
        if TruthValue.UNRESOLVED in values:
            return RuleEvaluation(TruthValue.UNRESOLVED, unresolved)
        return RuleEvaluation(TruthValue.FALSE)
