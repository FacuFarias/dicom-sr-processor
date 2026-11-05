from core.fingerprint import build_fingerprint
from core.parser_loader import load_parsers


def test_load_parsers_discovers_example_parser():
    parser_names = [parser.__class__.__name__ for parser in load_parsers()]
    assert "ExampleParser" in parser_names


def test_fingerprint_placeholder_returns_unknown():
    fingerprint = build_fingerprint({"any": "metadata"})
    assert fingerprint["manufacturer"] == "unknown"
    assert fingerprint["institution_name"] == "unknown"
    assert fingerprint["manufacturer_model_name"] == "unknown"
    assert fingerprint["sop_class_uid"] == "unknown"
    assert fingerprint["parser_key"] == "unknown|unknown|unknown|unknown"
