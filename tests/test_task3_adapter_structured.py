from __future__ import annotations

import json
from uuid import uuid4

from ingestion.adapters import StructuredTextAdapter
from ingestion.models import (
    ExtractionContext, FileTypeEvidence, FileTypeTruth, FileTypeTruthValue,
    QuarantineStatus,
)


def _context(path, detected_format=None, **configuration):
    if detected_format:
        configuration["detected_format"] = detected_format
    return ExtractionContext(
        artifact_id=uuid4(), analysis_run_id=uuid4(), export_snapshot_id=uuid4(),
        source_path=str(path), configuration=configuration,
    )


def _truth(format_key):
    return FileTypeTruth(
        status=FileTypeTruthValue.MATCH, detected_format=format_key,
        evidence=(FileTypeEvidence(source="parser_probe", candidate_format=format_key),),
        reason="fixture",
    )


def test_large_json_array_is_streamed_as_bounded_records(tmp_path):
    path = tmp_path / "large.json"
    with path.open("w", encoding="utf-8") as stream:
        stream.write("[")
        for index in range(20_000):
            if index:
                stream.write(",")
            json.dump({"index": index, "value": "x" * 8}, stream)
        stream.write("]")

    result = StructuredTextAdapter().extract(str(path), _context(path, max_units=1250))

    assert result.quarantine_status is QuarantineStatus.NONE
    assert len(result.units) == 1250
    assert result.units[-1].structured_payload["index"] == 1249
    assert result.units[-1].evidence_locator.locator=={"record":1249,"pointer":""}
    assert any("unit limit" in warning for warning in result.warnings)


def test_malformed_ndjson_line_remains_visible(tmp_path):
    path = tmp_path / "records.ndjson"
    path.write_text('{"ok": 1}\n{"broken":\n{"ok": 2}\n', encoding="utf-8")

    result = StructuredTextAdapter().extract(str(path), _context(path))

    assert len(result.units) == 3
    malformed = result.units[1]
    assert malformed.unit_type == "malformed_record"
    assert malformed.text == '{"broken":'
    assert malformed.metadata["malformed"] is True
    assert malformed.evidence_locator.locator_type == "text_line"
    assert malformed.evidence_locator.locator["line"] == 2
    assert any("line 2" in warning for warning in result.warnings)


def test_bom_and_legacy_single_byte_encoding_preserve_line_byte_spans(tmp_path):
    bom_path = tmp_path / "bom.txt"
    bom_path.write_bytes(b"\xef\xbb\xbfalpha\r\nbeta\n")
    result = StructuredTextAdapter().extract(str(bom_path), _context(bom_path))
    assert result.metadata["encoding"] == "utf-8"
    assert result.metadata["bom_bytes"] == 3
    assert result.units[0].evidence_locator.locator=={"line":1}
    assert result.units[0].metadata=={"byte_start":3,"byte_end":10}

    legacy_path = tmp_path / "legacy.log"
    legacy_path.write_bytes("café\nnext".encode("cp1252"))
    legacy = StructuredTextAdapter().extract(str(legacy_path), _context(legacy_path))
    assert legacy.metadata["encoding"] == "cp1252"
    assert legacy.units[0].text == "café"
    assert legacy.units[0].metadata["byte_end"] == 5


def test_quoted_csv_newline_has_one_logical_row_and_cell_locators(tmp_path):
    path = tmp_path / "quoted.csv"
    path.write_bytes(b'id,note\n1,"first line\nsecond line"\n2,plain\n')

    result = StructuredTextAdapter().extract(str(path), _context(path))
    rows = [unit for unit in result.units if unit.unit_type == "row"]
    cells = [unit for unit in result.units if unit.unit_type == "cell"]

    assert len(rows) == 3
    assert rows[1].structured_payload == ["1", "first line\nsecond line"]
    assert rows[1].metadata["physical_line_start"] == 2
    assert rows[1].metadata["physical_line_end"] == 3
    note = next(unit for unit in cells if unit.evidence_locator.locator["row"] == 2
                and unit.evidence_locator.locator["column"] == 1)
    assert note.parent_unit_id == rows[1].unit_id
    assert note.evidence_locator.locator_type == "csv_cell"


def test_malformed_html_is_recovered_with_stable_dom_locator(tmp_path):
    path = tmp_path / "broken.html"
    path.write_text("<html><body><section><p>Hello</section><p>World</body>", encoding="utf-8")

    result = StructuredTextAdapter().extract(str(path), _context(path))

    assert result.quarantine_status is QuarantineStatus.NONE
    assert [unit.text for unit in result.units] == ["Hello", "World"]
    assert all(unit.evidence_locator.locator_type == "html_dom_span" for unit in result.units)
    assert "p:nth-of-type(1)" in result.units[0].evidence_locator.locator["selector"]
    assert any("malformed HTML" in warning for warning in result.warnings)


def test_probe_accepts_valid_content_rejects_binary_and_reports_partial_ndjson(tmp_path):
    adapter = StructuredTextAdapter()
    valid = tmp_path / "records.jsonl"
    valid.write_text('{"a": 1}\nnot-json\n', encoding="utf-8")
    probe = adapter.probe(str(valid), _truth("ndjson"))
    assert probe.accepted and probe.confidence == 0.8
    assert "1/2" in probe.reason

    binary = tmp_path / "fake.txt"
    binary.write_bytes(b"text\x00binary")
    rejected = adapter.probe(str(binary), _truth("text"))
    assert not rejected.accepted
    assert "NUL" in rejected.reason


def test_xml_yaml_markdown_and_json_units_use_canonical_locator_vocabulary(tmp_path):
    adapter = StructuredTextAdapter()
    xml = tmp_path / "sample.xml"
    xml.write_text('<root><item id="7">value</item></root>', encoding="utf-8")
    xml_result = adapter.extract(str(xml), _context(xml))
    attribute = next(unit for unit in xml_result.units if unit.unit_type == "attribute")
    assert attribute.evidence_locator.locator_type == "xml_element"
    assert attribute.evidence_locator.locator["attribute"] == "id"
    assert attribute.evidence_locator.locator["xpath"] == "/root[1]/item[1]"

    yaml_path = tmp_path / "safe.yaml"
    yaml_path.write_text("items:\n  - one\n", encoding="utf-8")
    yaml_result = adapter.extract(str(yaml_path), _context(yaml_path))
    assert yaml_result.units[0].evidence_locator.locator_type == "text_byte_span"

    markdown = tmp_path / "note.md"
    markdown.write_text("# Heading\nBody\n", encoding="utf-8")
    md_result = adapter.extract(str(markdown), _context(markdown))
    assert [unit.evidence_locator.locator_type for unit in md_result.units] == [
        "text_line", "text_line"
    ]

    object_path = tmp_path / "object.json"
    object_path.write_text('{"a": 1}', encoding="utf-8")
    json_result = adapter.extract(str(object_path), _context(object_path))
    assert json_result.units[0].evidence_locator.locator_type == "json_pointer"
    assert json_result.units[0].evidence_locator.locator["pointer"] == ""


def test_yaml_safe_load_rejects_python_object_construction(tmp_path):
    path = tmp_path / "unsafe.yaml"
    path.write_text("!!python/object/apply:os.system ['echo unsafe']", encoding="utf-8")
    result = StructuredTextAdapter().extract(str(path), _context(path))
    assert result.quarantine_status is QuarantineStatus.CORRUPT
    assert result.units == ()
    assert any("ConstructorError" in warning for warning in result.warnings)
