from intelligence.ingestion.file_types import classify_file_type
from intelligence.ingestion.fingerprints import (
    html_structure_fingerprint, json_structure_fingerprint,
    tabular_structure_fingerprint, xml_structure_fingerprint,
)
from intelligence.ingestion.hashing import canonical_hash, raw_sha256
from intelligence.ingestion.models import FileTypeTruthValue


def test_json_canonical_hash_reorders_objects_but_not_arrays():
    assert canonical_hash(b'{"a":1,"b":2}', "json") == canonical_hash(b'{"b":2,"a":1}', "json")
    assert canonical_hash(b'{"a":[1,2]}', "json") != canonical_hash(b'{"a":[2,1]}', "json")


def test_delimited_canonical_hash_normalises_line_endings():
    assert canonical_hash(b"a,b\r\n1,2\r\n", "csv") == canonical_hash(b"a,b\n1,2\n", "csv")


def test_raw_hash_is_byte_semantics_and_duplicate_bytes_reuse_identity():
    one = b"identical source bytes"
    assert raw_sha256(one) == raw_sha256(bytes(one))
    assert raw_sha256(one) != raw_sha256(one + b"\n")


def test_html_and_xml_canonical_hashes_ignore_attribute_order():
    assert canonical_hash(b'<p a="1" b="2">x</p>', "html") == canonical_hash(b'<p b="2" a="1">x</p>', "html")
    assert canonical_hash(b'<r a="1" b="2"><x/></r>', "xml") == canonical_hash(b'<r b="2" a="1"><x></x></r>', "xml")


def test_signature_mime_extension_match_and_mismatch():
    matched = classify_file_type("report.pdf", declared_mime="application/pdf", data=b"%PDF-1.7\n")
    assert matched.status == FileTypeTruthValue.MATCH
    assert matched.detected_format == "pdf"
    mismatch = classify_file_type("report.json", declared_mime="application/json", data=b"%PDF-1.7\n")
    assert mismatch.status == FileTypeTruthValue.MISMATCH
    assert mismatch.detected_format == "pdf"


def test_unknown_extension_is_not_treated_as_truth():
    truth = classify_file_type("payload.unknown", data=b"arbitrary bytes")
    assert truth.status == FileTypeTruthValue.UNKNOWN
    assert truth.detected_format is None


def test_json_fingerprint_is_stable_and_structural():
    left = json_structure_fingerprint([{"b": 2, "a": [1]}, {"a": [2], "b": 3, "c": True}])
    right = json_structure_fingerprint([{"a": [1], "b": 2}, {"c": True, "b": 3, "a": [2]}])
    assert left.fingerprint_id == right.fingerprint_id
    assert left.canonical_shape["top_level_type"] == "array"
    assert left.canonical_shape["array_depth"] == 2
    assert "$[].a[]" in left.canonical_shape["key_paths"]
    assert left.canonical_shape["top_level_field_frequencies"]["c"]["present"] == 1


def test_tabular_and_markup_fingerprints_capture_structure():
    table = tabular_structure_fingerprint("id,active\n1,true\n2,false\n")
    assert table.canonical_shape["columns"] == ["id", "active"]
    assert table.canonical_shape["column_type_distribution"]["id"] == {"integer": 2}
    html = html_structure_fingerprint("<html><body><p class='x'>a</p></body></html>")
    assert html.canonical_shape["max_depth"] == 3
    xml = xml_structure_fingerprint("<root><item code='x'/></root>")
    assert xml.canonical_shape["attributes_by_element"]["item"] == ["code"]
