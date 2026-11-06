import pytest
from marshmallow import ValidationError
from backend.mobile_schemas import (
    ObjectUpdateSchema,
    BatchUpdateSchema,
    PresenceSchema,
    sanitize_string_field,
)


def test_sanitize_string_field():
    assert sanitize_string_field("Normal text") == "Normal text"
    assert sanitize_string_field("=cmd|'/C calc'!A0") == "'=cmd|'/C calc'!A0"
    assert sanitize_string_field("+SUM(A1:A10)") == "'+SUM(A1:A10)"
    assert sanitize_string_field("-123") == "'-123"
    assert sanitize_string_field("@SUM") == "'@SUM"
    assert sanitize_string_field(None) == ""


def test_object_update_schema_id_normalization():
    schema = ObjectUpdateSchema()

    # Using 'id'
    res1 = schema.load({"id": " 42 ", "observation": {"Genus": "Pinus"}})
    assert res1["oid"] == "42"
    assert res1["observation"]["Genus"] == "Pinus"

    # Using 'oid'
    res2 = schema.load({"oid": "100", "updates": {"Notes": "Test note"}})
    assert res2["oid"] == "100"
    assert res2["observation"]["Notes"] == "Test note"

    # Formula injection in observation values is sanitized
    res3 = schema.load({"id": "1", "observation": {"Species": "=2+2"}})
    assert res3["observation"]["Species"] == "'=2+2"


def test_batch_update_schema():
    schema = BatchUpdateSchema()

    valid_payload = {
        "updates": [
            {"id": "1", "observation": {"Genus": "Pinus"}},
            {"oid": "2", "reviewed": True},
        ]
    }
    loaded = schema.load(valid_payload)
    assert len(loaded["updates"]) == 2
    assert loaded["updates"][0]["oid"] == "1"
    assert loaded["updates"][1]["oid"] == "2"


def test_presence_schema():
    schema = PresenceSchema()
    assert schema.load({"oid": "  55  "})["oid"] == "55"
    assert schema.load({"id": "99"})["oid"] == "99"
