from transform.format import fmt


def test_thousands_and_decimal_comma():
    assert fmt(1234.5) == "1 234,5"
    assert fmt(1234567.891, 1) == "1 234 567,9"


def test_trailing_zeros_trimmed_when_decimals_unset():
    assert fmt(12.0) == "12"
    assert fmt(12.50) == "12,5"


def test_negative_uses_minus_sign_and_none_is_dash():
    assert fmt(-3.25, 2) == "−3,25"
    assert fmt(None) == "–"
    assert fmt(-0.001, 1) == "0,0"


def test_sign_flag():
    assert fmt(4.2, 1, sign=True) == "+4,2"


def test_ties_round_half_away_from_zero_on_the_decimal_value():
    assert fmt(0.25, 1) == "0,3"
    assert fmt(2.5, 0) == "3"
    assert fmt(0.125, 2) == "0,13"
    assert fmt(-0.25, 1) == "−0,3"
    assert fmt(1.005, 2) == "1,01"
