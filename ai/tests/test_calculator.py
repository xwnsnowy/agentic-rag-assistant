"""Unit tests for the calculator tool's AST whitelist (app/tools.py).

Pure: the calculator never touches the network or DB. The point of the
whitelist is that we evaluate a tiny arithmetic AST ourselves and never call
Python's eval(), so injection-shaped input degrades to a clean error string
(which ToolNode hands back to the agent) instead of executing anything.
"""

from app.tools import calculator


def calc(expression: str) -> str:
    return calculator.invoke({"expression": expression})


def test_valid_arithmetic():
    assert calc("2 * (3 + 4) ** 2") == "98"
    assert calc("7 / 2") == "3.5"
    assert calc("7 // 2") == "3"
    assert calc("10 % 3") == "1"
    assert calc("-5 + 2") == "-3"
    assert calc("1.5 + 2.5") == "4.0"


def test_rejects_dunder_import():
    # ast.Call is not in the whitelist, so this degrades to the error string
    # (the raw input is echoed back inside it, but never executed).
    out = calc('__import__("os").system("echo pwned")')
    assert out.startswith("Could not evaluate expression")


def test_rejects_bare_names():
    assert calc("x + 1").startswith("Could not evaluate expression")


def test_rejects_attribute_access():
    assert calc("(1).__class__").startswith("Could not evaluate expression")


def test_rejects_string_constants():
    # Only int/float Constants are whitelisted — strings fail even where Python
    # could evaluate them ('a' * 3), closing the door on string-building tricks.
    assert calc("'a' * 3").startswith("Could not evaluate expression")
    assert calc("'abc'").startswith("Could not evaluate expression")


def test_rejects_function_calls_and_statements():
    assert calc("print(1)").startswith("Could not evaluate expression")
    assert calc("import os").startswith("Could not evaluate expression")  # not an expression


def test_division_by_zero_returns_clean_message():
    out = calc("1 / 0")
    assert out == "Could not evaluate expression: '1 / 0'"  # message, not a raise
