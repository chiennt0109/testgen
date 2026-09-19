"""Safe evaluation of simple variable-dependent arithmetic constraints."""
from __future__ import annotations
import ast
import operator
from typing import Any


class ConstraintError(ValueError):
    """Raised when a constraint is unsafe or impossible."""


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.FloorDiv: operator.floordiv, ast.Div: operator.truediv,
        ast.Mod: operator.mod, ast.Pow: operator.pow, ast.USub: operator.neg,
        ast.UAdd: operator.pos}


def evaluate(value: Any, context: dict[str, Any]) -> int | float:
    """Evaluate literals and a deliberately small arithmetic expression grammar."""
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ConstraintError(f"Invalid expression: {value!r}")
    node = ast.parse(value, mode="eval").body

    def visit(item: ast.AST) -> int | float:
        if isinstance(item, ast.Constant) and isinstance(item.value, (int, float)):
            return item.value
        if isinstance(item, ast.Name):
            if item.id not in context or not isinstance(context[item.id], (int, float)):
                raise ConstraintError(f"Unknown numeric variable: {item.id}")
            return context[item.id]
        if isinstance(item, ast.BinOp) and type(item.op) in _OPS:
            return _OPS[type(item.op)](visit(item.left), visit(item.right))
        if isinstance(item, ast.UnaryOp) and type(item.op) in _OPS:
            return _OPS[type(item.op)](visit(item.operand))
        raise ConstraintError("Only numbers, variables and + - * / // % ** are allowed")

    try:
        result = visit(node)
    except (ArithmeticError, SyntaxError) as exc:
        raise ConstraintError(str(exc)) from exc
    if abs(result) > 10**18:
        raise ConstraintError("Expression result exceeds supported range")
    return result


def bounds(spec: dict[str, Any], context: dict[str, Any], defaults: tuple[int, int] = (0, 100)) -> tuple[int, int]:
    """Resolve and validate inclusive integer bounds."""
    low = int(evaluate(spec.get("min", defaults[0]), context))
    high = int(evaluate(spec.get("max", defaults[1]), context))
    if low > high:
        raise ConstraintError(f"Empty range [{low}, {high}]")
    return low, high
