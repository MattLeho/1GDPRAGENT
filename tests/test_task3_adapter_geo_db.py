from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from ingestion.adapters.geospatial_database import GeospatialDatabaseAdapter
from ingestion.models import ExtractionContext, FileTypeTruth, FileTypeTruthValue


def _context(path: Path, **configuration) -> ExtractionContext:
    return ExtractionContext(
        artifact_id=uuid4(), analysis_run_id=uuid4(), export_snapshot_id=uuid4(),
        source_path=str(path), configuration=configuration,
    )


def _truth(detected_format: str) -> FileTypeTruth:
    return FileTypeTruth(status=FileTypeTruthValue.MATCH, detected_format=detected_format, evidence=(), reason="test")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_geojson_extracts_properties_bbox_crs_and_feature_locators(tmp_path: Path):
    path = tmp_path / "places.geojson"
    path.write_text(json.dumps({
        "type": "FeatureCollection", "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "features": [
            {"type": "Feature", "id": "a", "properties": {"label": "first"}, "geometry": {"type": "Point", "coordinates": [-1.2, 51.4]}},
            {"type": "Feature", "properties": {"label": "second"}, "geometry": {"type": "LineString", "coordinates": [[-1.0, 51.0], [0.5, 52.0]]}},
        ],
    }), encoding="utf-8")
    adapter = GeospatialDatabaseAdapter()

    assert adapter.probe(str(path), _truth("geojson")).accepted
    result = adapter.extract(str(path), _context(path))

    assert result.quarantine_status.value == "none"
    assert result.metadata["feature_count"] == 2
    assert result.metadata["bounding_box"] == [-1.2, 51.0, 0.5, 52.0]
    assert result.metadata["crs"]["properties"]["name"] == "EPSG:4326"
    assert result.units[0].structured_payload["properties"] == {"label": "first"}
    assert all(unit.evidence_locator.locator_type == "geospatial_feature" for unit in result.units)
    assert result.units[1].evidence_locator.locator=={"feature":1}
    assert result.units[1].metadata["json_pointer"]=="/features/1"


def test_kml_and_gpx_have_member_segment_and_track_evidence(tmp_path: Path):
    kml = tmp_path / "route.kml"
    kml.write_text("""<?xml version='1.0'?>
      <kml xmlns='http://www.opengis.net/kml/2.2'><Document><Placemark>
      <name>route</name><LineString><coordinates>-1,51,3 0,52,4</coordinates></LineString>
      </Placemark></Document></kml>""", encoding="utf-8")
    gpx = tmp_path / "track.gpx"
    gpx.write_text("""<?xml version='1.0'?>
      <gpx version='1.1' creator='fixture' xmlns='http://www.topografix.com/GPX/1/1'>
      <trk><trkseg><trkpt lat='51' lon='-1'><ele>10</ele><time>2025-01-01T12:00:00Z</time></trkpt>
      <trkpt lat='52' lon='0'><ele>20</ele><time>2025-01-01T12:01:00Z</time></trkpt></trkseg></trk></gpx>""", encoding="utf-8")
    adapter = GeospatialDatabaseAdapter()

    kml_result = adapter.extract(str(kml), _context(kml))
    gpx_result = adapter.extract(str(gpx), _context(gpx))

    assert kml_result.units[0].structured_payload["geometry_type"] == "LineString"
    assert kml_result.units[0].evidence_locator.locator=={"feature":0}
    assert kml_result.units[0].metadata["placemark"]==0
    assert kml_result.units[0].metadata["coordinate_count"]==2
    track = gpx_result.units[0]
    assert track.evidence_locator.locator["segment"] == 0
    assert track.structured_payload["timestamps"] == ["2025-01-01T12:00:00Z", "2025-01-01T12:01:00Z"]
    assert track.structured_payload["elevations"] == [10.0, 20.0]
    assert "HOME" not in repr(kml_result).upper()
    assert "HOME" not in repr(gpx_result).upper()


def test_sqlite_is_immutable_trigger_is_not_run_and_locators_resolve(tmp_path: Path):
    path = tmp_path / "source.sqlite"
    connection = sqlite3.connect(path)
    connection.executescript("""
      CREATE TABLE audit(message TEXT);
      CREATE TABLE records(id INTEGER PRIMARY KEY, label TEXT, parent_id INTEGER REFERENCES records(id));
      CREATE INDEX records_label_idx ON records(label);
      CREATE TRIGGER records_read_trap AFTER UPDATE ON records BEGIN INSERT INTO audit VALUES ('triggered'); END;
      INSERT INTO records(label) VALUES ('one'), ('two');
      CREATE VIEW record_view AS SELECT * FROM records;
    """)
    connection.commit()
    connection.close()
    before = _digest(path)
    adapter = GeospatialDatabaseAdapter()

    assert adapter.probe(str(path), _truth("sqlite")).detected_format == "sqlite"
    result = adapter.extract(str(path), _context(path, sample_rows_per_table=2, row_count_limit=10, batch_size=1))

    assert _digest(path) == before
    check = sqlite3.connect(path)
    assert check.execute("SELECT COUNT(*) FROM audit").fetchone()[0] == 0
    check.close()
    assert result.metadata["read_only"] is True and result.metadata["immutable"] is True
    objects = {item["name"]: item for item in result.metadata["objects"]}
    assert objects["record_view"]["type"] == "view"
    assert objects["records"]["row_count"] == 2 and objects["records"]["row_count_exact"] is True
    assert objects["records"]["indexes"] and objects["records"]["foreign_keys"]
    locator_types = {unit.evidence_locator.locator_type for unit in result.units}
    assert {"database_table_row", "database_cell"} <= locator_types
    assert any(unit.evidence_locator.locator.get("column") == "label" for unit in result.units)
    assert all("row_key" in unit.evidence_locator.locator for unit in result.units)


def test_sqlite_large_table_count_and_samples_are_bounded(tmp_path: Path):
    path = tmp_path / "large.db"
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE events(value INTEGER)")
    # The acceptance corpus requires a million-row SQLite source. A recursive
    # CTE creates it quickly without materialising one million Python tuples.
    connection.execute("""WITH RECURSIVE values_fixture(value) AS (
        SELECT 0 UNION ALL SELECT value + 1 FROM values_fixture WHERE value < 999999
    ) INSERT INTO events SELECT value FROM values_fixture""")
    connection.commit()
    connection.close()
    adapter = GeospatialDatabaseAdapter()

    result = adapter.extract(str(path), _context(path, sample_rows_per_table=3, row_count_limit=100, batch_size=2))
    table = next(item for item in result.metadata["objects"] if item["name"] == "events")

    assert table["row_count"] == 100
    assert table["row_count_exact"] is False
    rows = [unit for unit in result.units if unit.unit_type == "database_table_row"]
    assert len(rows) == 3
    assert [unit.structured_payload["value"] for unit in rows] == [0, 1, 2]
