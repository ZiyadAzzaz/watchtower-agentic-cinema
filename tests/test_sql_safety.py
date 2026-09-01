import pytest

from watchtower.sql import detection_query, root_cause_query


def test_detection_query_is_bounded_and_read_only() -> None:
    query = detection_query("watchtower", 5, 60)
    assert "watchtower.telemetry_events" in query
    assert "LIMIT 200" in query
    assert "DROP" not in query


def test_root_query_rejects_injected_values() -> None:
    with pytest.raises(ValueError, match="Unsafe"):
        root_cause_query("watchtower", "aurora'; DROP TABLE x; --", "MENA", 5)


def test_query_rejects_unsafe_database_identifier() -> None:
    with pytest.raises(ValueError, match="Unsafe"):
        detection_query("watchtower; DROP", 5, 60)
