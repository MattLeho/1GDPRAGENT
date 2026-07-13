"""Deterministic geospatial and read-only SQLite extraction.

The adapter reports source structure and resolvable observations only.  It does
not infer the significance of a coordinate or execute database-owned code.
"""
from __future__ import annotations

import json
import sqlite3
import urllib.parse
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Iterator
from xml.etree import ElementTree as ET

from ..models import (
    EvidenceLocatorValue,
    ExtractionContext,
    ExtractionResult,
    ExtractionUnit,
    FileTypeTruth,
    ProbeResult,
    QuarantineStatus,
)


_SQLITE_HEADER = b"SQLite format 3\x00"
_XML_PROBE_BYTES = 64 * 1024
_DEFAULT_MAX_FEATURES = 100_000
_DEFAULT_SAMPLE_ROWS = 25
_DEFAULT_ROW_COUNT_LIMIT = 100_000
_DEFAULT_BATCH_SIZE = 128


def _locator(locator_type: str, **locator: Any) -> EvidenceLocatorValue:
    return EvidenceLocatorValue(locator_type=locator_type, locator=locator)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _coordinates(value: Any) -> Iterator[tuple[float, float, float | None]]:
    if isinstance(value, dict):
        yield from _coordinates(value.get("coordinates"))
        yield from _coordinates(value.get("geometries"))
        return
    if isinstance(value, (list, tuple)):
        if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
            yield float(value[0]), float(value[1]), (float(value[2]) if len(value) > 2 and isinstance(value[2], (int, float)) else None)
        else:
            for child in value:
                yield from _coordinates(child)


def _bbox(points: Iterable[tuple[float, float, float | None]]) -> list[float] | None:
    values = list(points)
    if not values:
        return None
    xs, ys = [item[0] for item in values], [item[1] for item in values]
    return [min(xs), min(ys), max(xs), max(ys)]


def _xml_root(raw: bytes) -> ET.Element:
    if b"<!DOCTYPE" in raw[:_XML_PROBE_BYTES].upper() or b"<!ENTITY" in raw[:_XML_PROBE_BYTES].upper():
        raise ValueError("DTD and entity declarations are not permitted")
    return ET.fromstring(raw)


def _sqlite_uri(path: str) -> str:
    # sqlite URI paths require forward slashes and percent escaping.  mode=ro
    # prevents writes; immutable avoids journal/WAL creation and side effects.
    absolute = Path(path).resolve().as_posix()
    return f"file:{urllib.parse.quote(absolute, safe='/:')}?mode=ro&immutable=1"


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


class GeospatialDatabaseAdapter:
    adapter_id = "geospatial_database"
    adapter_version = "1.0.0"
    family = "geospatial_database"
    supported_mime_types = frozenset({
        "application/geo+json", "application/vnd.google-earth.kml+xml",
        "application/vnd.google-earth.kmz", "application/gpx+xml",
        "application/vnd.sqlite3", "application/x-sqlite3",
    })
    supported_extensions = frozenset({".geojson", ".kml", ".kmz", ".gpx", ".sqlite", ".sqlite3", ".db"})
    supports_streaming = True
    supports_nested_members = True
    locator_types = frozenset({"geospatial_feature", "database_table_row", "database_cell"})
    capability_flags = frozenset({"geospatial", "structured_records", "metadata", "timestamps", "tables"})

    def probe(self, path: str, truth: FileTypeTruth) -> ProbeResult:
        try:
            with open(path, "rb") as stream:
                sample = stream.read(_XML_PROBE_BYTES)
            if sample.startswith(_SQLITE_HEADER):
                return ProbeResult(accepted=True, confidence=1.0, detected_format="sqlite", reason="SQLite header")
            if sample.startswith(b"PK\x03\x04"):
                with zipfile.ZipFile(path) as archive:
                    names = [name for name in archive.namelist() if name.lower().endswith(".kml")]
                    if names:
                        return ProbeResult(accepted=True, confidence=1.0, detected_format="kmz", reason="ZIP contains KML member")
            stripped = sample.lstrip()
            if stripped.startswith((b"{", b"[")):
                value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
                kind = value.get("type") if isinstance(value, dict) else None
                if kind in {"FeatureCollection", "Feature", "Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon", "GeometryCollection"}:
                    return ProbeResult(accepted=True, confidence=0.98, detected_format="geojson", reason=f"GeoJSON {kind}")
            root = _xml_root(Path(path).read_bytes())
            root_name = _local_name(root.tag).lower()
            if root_name == "kml":
                return ProbeResult(accepted=True, confidence=1.0, detected_format="kml", reason="KML root element")
            if root_name == "gpx":
                return ProbeResult(accepted=True, confidence=1.0, detected_format="gpx", reason="GPX root element")
        except (OSError, ValueError, json.JSONDecodeError, ET.ParseError, zipfile.BadZipFile, KeyError) as exc:
            return ProbeResult(accepted=False, confidence=0.0, reason=f"probe rejected content: {exc}")
        return ProbeResult(accepted=False, confidence=0.0, reason="no supported geospatial or SQLite signature")

    def extract(self, path: str, context: ExtractionContext) -> ExtractionResult:
        detected = self._format(path, context)
        try:
            if detected == "geojson":
                units, metadata, warnings = self._geojson(path, context)
            elif detected in {"kml", "kmz"}:
                units, metadata, warnings = self._kml(path, detected, context)
            elif detected == "gpx":
                units, metadata, warnings = self._gpx(path, context)
            elif detected == "sqlite":
                units, metadata, warnings = self._sqlite(path, context)
            else:
                raise ValueError(f"unsupported detected format: {detected}")
            quarantine = QuarantineStatus.NONE
        except Exception as exc:
            units, metadata, warnings = [], {}, [f"{detected} extraction failed: {type(exc).__name__}: {exc}"]
            quarantine = QuarantineStatus.CORRUPT
        return ExtractionResult(
            artifact_id=context.artifact_id, adapter_id=self.adapter_id,
            adapter_version=self.adapter_version, family=self.family,
            detected_format=detected, metadata=metadata, units=tuple(units),
            warnings=tuple(warnings), quarantine_status=quarantine,
        )

    def _format(self, path: str, context: ExtractionContext) -> str:
        configured = str(context.configuration.get("detected_format", "")).lower()
        if configured in {"geojson", "kml", "kmz", "gpx", "sqlite"}:
            return configured
        with open(path, "rb") as stream:
            sample = stream.read(_XML_PROBE_BYTES)
        if sample.startswith(_SQLITE_HEADER):
            return "sqlite"
        suffix = Path(path).suffix.lower()
        return {".geojson": "geojson", ".kml": "kml", ".kmz": "kmz", ".gpx": "gpx"}.get(suffix, "sqlite")

    def _geojson(self, path: str, context: ExtractionContext):
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
        maximum = int(context.configuration.get("max_features", _DEFAULT_MAX_FEATURES))
        if isinstance(value, dict) and value.get("type") == "FeatureCollection":
            features = value.get("features") or []
            crs = value.get("crs")
        elif isinstance(value, dict) and value.get("type") == "Feature":
            features, crs = [value], value.get("crs")
        elif isinstance(value, dict):
            features, crs = [{"type": "Feature", "geometry": value, "properties": {}}], value.get("crs")
        else:
            raise ValueError("GeoJSON top level must be an object")
        units: list[ExtractionUnit] = []
        types: Counter[str] = Counter()
        all_points: list[tuple[float, float, float | None]] = []
        for index, feature in enumerate(features[:maximum]):
            geometry = feature.get("geometry") or {}
            geometry_type = geometry.get("type", "null")
            points = list(_coordinates(geometry.get("coordinates")))
            all_points.extend(points)
            types[geometry_type] += 1
            payload = {
                "feature_id": feature.get("id"), "geometry_type": geometry_type,
                "bounding_box": feature.get("bbox") or _bbox(points),
                "properties": feature.get("properties") or {},
                "elevations": [point[2] for point in points],
                "timestamps": _geojson_timestamps(feature.get("properties") or {}),
            }
            locator={"feature":index}
            units.append(ExtractionUnit(
                unit_id=f"geojson-feature-{index}", unit_type="geospatial_feature", ordinal=len(units),
                structured_payload=payload,
                evidence_locator=_locator("geospatial_feature",**locator),
                metadata={"format":"geojson","json_pointer":f"/features/{index}","coordinate_count":len(points)},
            ))
        warnings = [f"feature limit {maximum} reached"] if len(features) > maximum else []
        return units, {
            "crs": crs, "feature_count": len(features), "extracted_feature_count": len(units),
            "geometry_types": dict(types), "bounding_box": value.get("bbox") or _bbox(all_points),
        }, warnings

    def _kml(self, path: str, detected: str, context: ExtractionContext):
        member = None
        if detected == "kmz":
            maximum_member = int(context.configuration.get("max_kmz_member_bytes", 64 * 1024 * 1024))
            with zipfile.ZipFile(path) as archive:
                candidates = [info for info in archive.infolist() if info.filename.lower().endswith(".kml") and not info.is_dir()]
                if not candidates:
                    raise ValueError("KMZ has no KML member")
                info = candidates[0]
                if info.file_size > maximum_member:
                    raise ValueError("KML member exceeds configured size limit")
                member, raw = info.filename, archive.read(info)
        else:
            raw = Path(path).read_bytes()
        root = _xml_root(raw)
        maximum = int(context.configuration.get("max_features", _DEFAULT_MAX_FEATURES))
        placemarks = [element for element in root.iter() if _local_name(element.tag) == "Placemark"]
        units: list[ExtractionUnit] = []
        all_points: list[tuple[float, float, float | None]] = []
        types: Counter[str] = Counter()
        for index, placemark in enumerate(placemarks[:maximum]):
            geometry = next((element for element in placemark.iter() if _local_name(element.tag) in {"Point", "LineString", "LinearRing", "Polygon", "MultiGeometry", "Track", "MultiTrack"}), None)
            geometry_type = _local_name(geometry.tag) if geometry is not None else "none"
            points: list[tuple[float, float, float | None]] = []
            timestamps: list[str] = []
            for node in placemark.iter():
                if _local_name(node.tag) == "coordinates" and node.text:
                    for token in node.text.split():
                        parts = token.split(",")
                        if len(parts) >= 2:
                            points.append((float(parts[0]), float(parts[1]), float(parts[2]) if len(parts) > 2 and parts[2] else None))
                elif _local_name(node.tag) == "coord" and node.text:
                    parts = node.text.split()
                    if len(parts) >= 2:
                        points.append((float(parts[0]), float(parts[1]), float(parts[2]) if len(parts) > 2 else None))
                elif _local_name(node.tag) == "when" and node.text:
                    timestamps.append(node.text.strip())
            all_points.extend(points)
            types[geometry_type] += 1
            properties: dict[str, Any] = {}
            for node in placemark:
                name = _local_name(node.tag)
                if name in {"name", "description"} and node.text:
                    properties[name] = node.text
            for data in placemark.iter():
                if _local_name(data.tag) == "Data" and data.get("name"):
                    child = next((item for item in data if _local_name(item.tag) == "value"), None)
                    properties[data.get("name")] = child.text if child is not None else None
            locator={"feature":index}
            units.append(ExtractionUnit(
                unit_id=f"{detected}-feature-{index}", unit_type="geospatial_feature", ordinal=len(units),
                structured_payload={"geometry_type": geometry_type, "bounding_box": _bbox(points), "properties": properties, "coordinates": points, "timestamps": timestamps, "elevations": [point[2] for point in points]},
                evidence_locator=_locator("geospatial_feature", **locator),
                metadata={"format":detected,"placemark":index,"member":member,"coordinate_count":len(points)},
            ))
        warnings = [f"feature limit {maximum} reached"] if len(placemarks) > maximum else []
        return units, {"crs": "EPSG:4326", "feature_count": len(placemarks), "geometry_types": dict(types), "bounding_box": _bbox(all_points), **({"kml_member": member} if member else {})}, warnings

    def _gpx(self, path: str, context: ExtractionContext):
        root = _xml_root(Path(path).read_bytes())
        maximum = int(context.configuration.get("max_features", _DEFAULT_MAX_FEATURES))
        features: list[tuple[str, int, int | None, list[ET.Element]]] = []
        for kind in ("wpt", "rte", "trk"):
            for index, element in enumerate(item for item in root if _local_name(item.tag) == kind):
                if kind == "trk":
                    segments = [item for item in element if _local_name(item.tag) == "trkseg"]
                    for segment_index, segment in enumerate(segments):
                        features.append((kind, index, segment_index, [item for item in segment if _local_name(item.tag) == "trkpt"]))
                elif kind == "rte":
                    features.append((kind, index, None, [item for item in element if _local_name(item.tag) == "rtept"]))
                else:
                    features.append((kind, index, None, [element]))
        units: list[ExtractionUnit] = []
        all_points: list[tuple[float, float, float | None]] = []
        for feature_index, (kind, index, segment, nodes) in enumerate(features[:maximum]):
            points, timestamps = [], []
            for node in nodes:
                elevation_node = next((child for child in node if _local_name(child.tag) == "ele"), None)
                time_node = next((child for child in node if _local_name(child.tag) == "time"), None)
                elevation = float(elevation_node.text) if elevation_node is not None and elevation_node.text else None
                points.append((float(node.attrib["lon"]), float(node.attrib["lat"]), elevation))
                timestamps.append(time_node.text if time_node is not None else None)
            all_points.extend(points)
            locator={"feature":feature_index}
            if segment is not None:
                locator["segment"] = segment
            units.append(ExtractionUnit(
                unit_id=f"gpx-feature-{feature_index}", unit_type="geospatial_feature", ordinal=len(units),
                structured_payload={"geometry_type": "Point" if kind == "wpt" else "LineString", "bounding_box": _bbox(points), "coordinates": points, "timestamps": timestamps, "elevations": [p[2] for p in points]},
                evidence_locator=_locator("geospatial_feature", **locator),
                metadata={"format":"gpx","feature_type":kind,"feature_index":index,"coordinate_count":len(points)},
            ))
        creator = root.attrib.get("creator")
        warnings = [f"feature limit {maximum} reached"] if len(features) > maximum else []
        return units, {"crs": "EPSG:4326", "feature_count": len(features), "bounding_box": _bbox(all_points), "creator": creator}, warnings

    def _sqlite(self, path: str, context: ExtractionContext):
        sample_limit = max(0, int(context.configuration.get("sample_rows_per_table", _DEFAULT_SAMPLE_ROWS)))
        count_limit = max(0, int(context.configuration.get("row_count_limit", _DEFAULT_ROW_COUNT_LIMIT)))
        batch_size = max(1, int(context.configuration.get("batch_size", _DEFAULT_BATCH_SIZE)))
        connection = sqlite3.connect(_sqlite_uri(path), uri=True)
        connection.row_factory = sqlite3.Row
        try:
            connection.enable_load_extension(False)
            connection.execute("PRAGMA query_only=ON")
            connection.execute("PRAGMA trusted_schema=OFF")
            connection.execute("PRAGMA foreign_keys=OFF")
            objects = connection.execute(
                "SELECT name, type, sql FROM sqlite_schema WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' ORDER BY type,name"
            ).fetchall()
            inventory: list[dict[str, Any]] = []
            units: list[ExtractionUnit] = []
            warnings: list[str] = []
            for object_row in objects:
                name, object_type = object_row["name"], object_row["type"]
                quoted = _quote_identifier(name)
                is_virtual = bool(object_row["sql"] and str(object_row["sql"]).lstrip().upper().startswith("CREATE VIRTUAL TABLE"))
                columns = [dict(row) for row in connection.execute(f"PRAGMA table_info({quoted})").fetchall()]
                indexes = []
                foreign_keys = []
                if object_type == "table" and not is_virtual:
                    for row in connection.execute(f"PRAGMA index_list({quoted})").fetchall():
                        indexes.append(dict(row))
                    foreign_keys = [dict(row) for row in connection.execute(f"PRAGMA foreign_key_list({quoted})").fetchall()]
                    cursor = connection.execute(f"SELECT 1 FROM {quoted} LIMIT ?", (count_limit + 1,))
                    bounded_count = len(cursor.fetchall())
                    row_count = min(bounded_count, count_limit)
                    count_exact = bounded_count <= count_limit
                else:
                    row_count, count_exact = None, False
                inventory.append({
                    "name": name, "type": object_type, "sql": object_row["sql"],
                    "virtual": is_virtual,
                    "columns": columns, "indexes": indexes, "foreign_keys": foreign_keys,
                    "row_count": row_count, "row_count_exact": count_exact,
                })
                # Views are inventoried but never selected: evaluating one can invoke
                # schema-owned expressions or extension functions.
                if object_type != "table" or is_virtual or sample_limit == 0:
                    continue
                try:
                    sample_cursor = connection.execute(f"SELECT rowid AS __source_rowid__, * FROM {quoted} LIMIT ?", (sample_limit,))
                    has_rowid = True
                except sqlite3.DatabaseError:
                    sample_cursor = connection.execute(f"SELECT * FROM {quoted} LIMIT ?", (sample_limit,))
                    has_rowid = False
                sampled = 0
                while sampled < sample_limit:
                    batch = sample_cursor.fetchmany(min(batch_size, sample_limit - sampled))
                    if not batch:
                        break
                    for row in batch:
                        values = dict(row)
                        source_rowid = values.pop("__source_rowid__", None) if has_rowid else None
                        primary_keys=[column["name"] for column in sorted(columns,key=lambda item:item["pk"] or 9999) if column["pk"]]
                        if source_rowid is not None:
                            row_key={"rowid":source_rowid}
                        elif primary_keys:
                            row_key={key:values[key] for key in primary_keys}
                        else:
                            row_key={key:value for key,value in values.items()}
                        row_locator={"table":name,"row_key":row_key}
                        row_id = f"sqlite-{len(units)}-row"
                        units.append(ExtractionUnit(
                            unit_id=row_id, unit_type="database_table_row", ordinal=len(units),
                            structured_payload={key: _sqlite_value(value) for key, value in values.items()},
                            evidence_locator=_locator("database_table_row", **row_locator),
                        ))
                        for column, value in values.items():
                            units.append(ExtractionUnit(
                                unit_id=f"sqlite-{len(units)}-cell", unit_type="database_cell", ordinal=len(units),
                                value=_sqlite_value(value) if value is not None else None,
                                text="null" if value is None else None, parent_unit_id=row_id,
                                evidence_locator=_locator("database_cell", **row_locator, column=column),
                            ))
                        sampled += 1
            header = Path(path).read_bytes()[:100]
            metadata = {
                "sqlite_header": header[:16].decode("ascii", errors="replace"),
                "sqlite_library_version": sqlite3.sqlite_version,
                "page_size": int.from_bytes(header[16:18], "big") if len(header) >= 18 else None,
                "objects": inventory, "object_count": len(inventory),
                "sampling": {"rows_per_table": sample_limit, "row_count_limit": count_limit, "batch_size": batch_size},
                "read_only": True, "immutable": True,
            }
            return units, metadata, warnings
        finally:
            connection.close()


def _sqlite_value(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"type": "blob", "size": len(value), "hex_prefix": value[:32].hex()}
    return value


def _geojson_timestamps(properties: dict[str, Any]) -> list[Any]:
    for key in ("coordTimes", "timestamps", "times", "time"):
        if key in properties:
            value = properties[key]
            return value if isinstance(value, list) else [value]
    return []
