"""Deterministic single-file integration for the Wave 1 ingestion gate."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .file_types import classify_file_type
from .fingerprints import fingerprint_html,fingerprint_json,fingerprint_tabular,fingerprint_xml
from .hashing import CANONICAL_HASH_REGISTRY,raw_file_sha256
from .models import ExtractionContext,ExtractionResult,FileTypeTruth,StructureFingerprint
from .registry import DispatchDecision,FileWorkflowRegistry,build_default_registry


@dataclass(frozen=True)
class ProcessedFile:
    path: Path
    raw_sha256: str
    canonical_sha256: str | None
    truth: FileTypeTruth
    dispatch: DispatchDecision
    extraction: ExtractionResult | None
    fingerprint: StructureFingerprint | None


class LocalFileProcessor:
    def __init__(self,registry:FileWorkflowRegistry|None=None,*,sample_bytes:int=64*1024,canonical_limit_bytes:int=128*1024*1024):
        self.registry=registry or build_default_registry()
        self.sample_bytes=sample_bytes
        self.canonical_limit_bytes=canonical_limit_bytes

    def process(self,path:str|Path,context:ExtractionContext,*,declared_mime:str|None=None)->ProcessedFile:
        source=Path(path)
        with source.open("rb") as stream: sample=stream.read(self.sample_bytes)
        truth=classify_file_type(source,declared_mime=declared_mime,data=sample)
        decision=self.registry.dispatch(str(source),truth)
        extraction=decision.adapter.extract(str(source),context) if decision.adapter else None
        detected=(extraction.detected_format if extraction else truth.detected_format)
        canonical=None
        if detected in CANONICAL_HASH_REGISTRY.formats() and source.stat().st_size<=self.canonical_limit_bytes:
            canonical=CANONICAL_HASH_REGISTRY.hash(detected,source.read_bytes())
        fingerprint=self._fingerprint(source,detected,extraction)
        return ProcessedFile(source,raw_file_sha256(source),canonical,truth,decision,extraction,fingerprint)

    def _fingerprint(self,path:Path,detected:str|None,extraction:ExtractionResult|None)->StructureFingerprint|None:
        if detected=="json":
            values=[unit.structured_payload if unit.structured_payload is not None else unit.value for unit in (extraction.units[:1000] if extraction else ()) if unit.unit_type=="record"]
            shaped=(values[0] if extraction and extraction.metadata.get("top_level_type")=="object" and len(values)==1 else values)
            return fingerprint_json(shaped if values else path.read_bytes())
        if detected in {"csv","tsv","delimited"} and extraction:
            rows=[unit.structured_payload for unit in extraction.units if unit.unit_type=="row"][:1000]
            return fingerprint_tabular(rows,delimiter="\t" if detected=="tsv" else ",",has_header=True) if rows else None
        if detected=="html" and path.stat().st_size<=self.canonical_limit_bytes: return fingerprint_html(path.read_bytes())
        if detected=="xml" and path.stat().st_size<=self.canonical_limit_bytes: return fingerprint_xml(path.read_bytes())
        return None
