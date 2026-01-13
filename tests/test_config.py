from app.config import parse_tiers


def test_parse_tiers():
    assert parse_tiers("") == {}
    assert parse_tiers("A=10") == {"A": 10}
    assert parse_tiers("A=10,B=20") == {"A": 10, "B": 20}
