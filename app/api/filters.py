"""Predicate engines for Zoho `criteria` search syntax and COQL WHERE clauses."""

import re
from collections.abc import Callable
from typing import Any

from app.schemas.zoho import ZohoAPIError

Predicate = Callable[[dict[str, Any]], bool]


def field_value(payload: dict[str, Any], field: str) -> Any:
    value = payload.get(field)
    if isinstance(value, dict):
        return value.get("id")
    return value


def _display_value(payload: dict[str, Any], field: str) -> Any:
    value = payload.get(field)
    if isinstance(value, dict):
        return value.get("name")
    return value


def _as_number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare(left: Any, op: str, right: Any) -> bool:
    if op in {"=", "equals"}:
        return _eq(left, right)
    if op in {"!=", "not_equal"}:
        return not _eq(left, right)

    if op in {">", ">=", "<", "<=", "greater_than", "greater_equal", "less_than", "less_equal"}:
        ln, rn = _as_number(left), _as_number(right)
        if ln is None or rn is None:
            ln, rn = str(left or ""), str(right or "")  # type: ignore[assignment]
        if op in {">", "greater_than"}:
            return ln > rn  # type: ignore[operator]
        if op in {">=", "greater_equal"}:
            return ln >= rn  # type: ignore[operator]
        if op in {"<", "less_than"}:
            return ln < rn  # type: ignore[operator]
        return ln <= rn  # type: ignore[operator]

    text = str(left or "").lower()
    needle = str(right or "").lower()
    if op in {"starts_with"}:
        return text.startswith(needle)
    if op in {"ends_with"}:
        return text.endswith(needle)
    if op in {"contains", "like"}:
        return needle.strip("%") in text
    if op in {"not like", "not_contains"}:
        return needle.strip("%") not in text
    if op == "in":
        values = right if isinstance(right, (list, tuple)) else [right]
        return any(_eq(left, item) for item in values)
    if op == "is null":
        return left in (None, "")
    if op == "is not null":
        return left not in (None, "")

    raise ZohoAPIError("INVALID_QUERY_PARAM", f"unsupported operator: {op}", {"operator": op})


def _eq(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return str(left).lower() == str(right).lower()
    ln, rn = _as_number(left), _as_number(right)
    if ln is not None and rn is not None:
        return ln == rn
    return str(left or "").lower() == str(right or "").lower()


def _leaf_predicate(field: str, op: str, raw: Any) -> Predicate:
    def predicate(payload: dict[str, Any]) -> bool:
        if _compare(field_value(payload, field), op, raw):
            return True
        # lookups are matchable by display name too, like the real API
        display = _display_value(payload, field)
        if display is not None and display != field_value(payload, field):
            return _compare(display, op, raw)
        return False

    return predicate


def _combine(parts: list[Predicate], operators: list[str]) -> Predicate:
    def predicate(payload: dict[str, Any]) -> bool:
        result = parts[0](payload)
        for op, part in zip(operators, parts[1:], strict=True):
            if op == "and":
                result = result and part(payload)
            else:
                result = result or part(payload)
        return result

    return predicate


def _split_top_level(expr: str) -> tuple[list[str], list[str]]:
    """Split on top-level and/or, returning (segments, operators)."""
    segments: list[str] = []
    operators: list[str] = []
    depth = 0
    current = ""
    index = 0

    while index < len(expr):
        char = expr[index]
        if char == "(":
            depth += 1
            current += char
        elif char == ")":
            depth -= 1
            current += char
        elif depth == 0:
            lowered = expr[index:].lower()
            prev_char = expr[index - 1] if index > 0 else ""
            next_char = expr[index + 3] if index + 3 < len(expr) else ""
            if (
                lowered.startswith("and")
                and not current.strip().endswith(":")
                and prev_char in (")", " ")
                and next_char in ("(", " ")
            ):
                segments.append(current)
                operators.append("and")
                current = ""
                index += 3
                continue
            next_char_or = expr[index + 2] if index + 2 < len(expr) else ""
            if (
                lowered.startswith("or")
                and prev_char in (")", " ")
                and next_char_or in ("(", " ")
            ):
                segments.append(current)
                operators.append("or")
                current = ""
                index += 2
                continue
            current += char
        else:
            current += char
        index += 1

    segments.append(current)
    return [s.strip() for s in segments if s.strip()], operators


def _strip_wrapping_parens(expr: str) -> str:
    expr = expr.strip()
    while expr.startswith("(") and expr.endswith(")"):
        depth = 0
        balanced = True
        for position, char in enumerate(expr):
            depth += 1 if char == "(" else -1 if char == ")" else 0
            if depth == 0 and position < len(expr) - 1:
                balanced = False
                break
        if not balanced:
            break
        expr = expr[1:-1].strip()
    return expr


CRITERIA_LEAF = re.compile(r"^\s*([\w.]+)\s*:\s*([a-z_]+)\s*:\s*(.*?)\s*$", re.IGNORECASE)


def parse_criteria(criteria: str) -> Predicate:
    """Parse Zoho search criteria, e.g. `((Status:equals:Open)and(Priority:equals:High))`."""
    expr = _strip_wrapping_parens(criteria)
    if not expr:
        raise ZohoAPIError("INVALID_QUERY_PARAM", "criteria is empty", {"parameter": "criteria"})

    segments, operators = _split_top_level(expr)
    if len(segments) > 1:
        return _combine([parse_criteria(segment) for segment in segments], operators)

    inner = _strip_wrapping_parens(segments[0])
    if inner != segments[0]:
        nested_segments, nested_ops = _split_top_level(inner)
        if len(nested_segments) > 1:
            return _combine([parse_criteria(s) for s in nested_segments], nested_ops)

    match = CRITERIA_LEAF.match(inner)
    if not match:
        raise ZohoAPIError(
            "INVALID_QUERY_PARAM",
            "criteria must look like (Field:operator:value)",
            {"parameter": "criteria", "given": criteria},
        )

    field, op, value = match.group(1), match.group(2).lower(), match.group(3)
    if op == "in":
        parsed: Any = [v.strip() for v in value.split(",") if v.strip()]
    else:
        parsed = value
    return _leaf_predicate(field, op, parsed)


COQL_LEAF = re.compile(
    r"^\s*([\w.]+)\s*(=|!=|>=|<=|>|<|not\s+like|like|not\s+in|in|is\s+not\s+null|is\s+null)\s*(.*?)\s*$",
    re.IGNORECASE,
)


def _parse_coql_value(raw: str) -> Any:
    raw = raw.strip()
    if not raw:
        return None
    if raw.startswith("(") and raw.endswith(")"):
        return [_parse_coql_value(part) for part in raw[1:-1].split(",")]
    if (raw.startswith("'") and raw.endswith("'")) or (raw.startswith('"') and raw.endswith('"')):
        return raw[1:-1]
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    if raw.lower() == "null":
        return None
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        return raw


def parse_coql_where(clause: str) -> Predicate:
    expr = _strip_wrapping_parens(clause)
    if not expr:
        return lambda _payload: True

    segments, operators = _split_top_level(expr)
    if len(segments) > 1:
        return _combine([parse_coql_where(segment) for segment in segments], operators)

    inner = _strip_wrapping_parens(segments[0])
    if inner != segments[0]:
        nested_segments, nested_ops = _split_top_level(inner)
        if len(nested_segments) > 1:
            return _combine([parse_coql_where(s) for s in nested_segments], nested_ops)

    match = COQL_LEAF.match(inner)
    if not match:
        raise ZohoAPIError(
            "INVALID_QUERY",
            "unable to parse the WHERE clause",
            {"clause": clause},
        )

    field = match.group(1)
    op = re.sub(r"\s+", " ", match.group(2).strip().lower())
    value = _parse_coql_value(match.group(3))
    if op == "not in":
        values = value if isinstance(value, list) else [value]
        leaf = _leaf_predicate(field, "in", values)
        return lambda payload: not leaf(payload)
    return _leaf_predicate(field, op, value)
