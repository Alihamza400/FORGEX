from forge.tools.builtins.calculator import calculator


def test_basic_addition():
    assert calculator("2 + 2") == "4"
def test_complex_expression():
    result = calculator("(3 + 5) * 2 - 4 / 2")
    assert float(result) == 14.0
def test_division():
    assert calculator("10 / 3") == str(10 / 3)
def test_division_by_zero():
    result = calculator("1 / 0")
    assert "Error" in result
def test_power():
    assert calculator("2 ** 10") == "1024"
def test_modulo():
    assert calculator("17 % 5") == "2"
def test_negative():
    assert calculator("-5 + 3") == "-2"
def test_invalid_expression():
    result = calculator("abc + def")
    assert "Error" in result
def test_empty_expression():
    result = calculator("")
    assert "Error" in result
