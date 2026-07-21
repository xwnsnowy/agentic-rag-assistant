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


# --- exponentiation bound ----------------------------------------------------
# ast.Pow is whitelisted, but Python ints are arbitrary-precision: without a
# magnitude guard, "9**9**9**9" makes the tool compute a number with hundreds
# of millions of digits — a CPU denial-of-service inside an agent turn. The
# guard estimates the result's bit length (|exp| * log2|base|) BEFORE
# computing, so rejection cost does not depend on the requested size.


def test_ordinary_exponentiation_still_works():
    assert calc("2**16") == "65536"
    assert calc("1.5**3") == "3.375"
    assert calc("2 * (3 + 4) ** 2") == "98"
    assert calc("(-2)**10") == "1024"
    assert calc("0.5**2000") == "0.0"  # |base| <= 1 can never explode
    assert calc("1**999999999") == "1"
    # The documented cap (~1000 bits): 2**1000 is the largest power of two allowed.
    assert calc("2**1000") == str(2**1000)


def test_oversized_exponentiation_is_rejected_with_reason():
    out = calc("9**999999")
    assert out.startswith("Could not evaluate expression")
    assert "too large" in out
    # Nested towers are caught at the first oversized intermediate step.
    assert "too large" in calc("2**500**2")


def test_oversized_exponentiation_rejects_fast():
    # The guard must trigger BEFORE any big-int work happens. If it ever
    # regressed to computing first, this would hang for (astronomically) longer
    # than the suite timeout — 9**9**9**9's intermediate alone is ~1.9e8 digits.
    import time

    t0 = time.perf_counter()
    out = calc("9**9**9**9")
    elapsed = time.perf_counter() - t0
    assert "too large" in out
    assert elapsed < 1.0  # microseconds in practice; 1s is a generous ceiling
