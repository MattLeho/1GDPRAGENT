from uuid import uuid4
import io
import tarfile

from ingestion.models import ExtractionContext
from ingestion.processor import LocalFileProcessor


def context(path):
    return ExtractionContext(artifact_id=uuid4(),analysis_run_id=uuid4(),export_snapshot_id=uuid4(),source_path=str(path))


def test_processor_selects_probe_not_extension_and_fingerprints(tmp_path):
    source=tmp_path/"events.json"; source.write_text('[{"x":1},{"x":2}]',encoding="utf-8")
    result=LocalFileProcessor().process(source,context(source),declared_mime="application/json")
    assert result.dispatch.status=="selected"
    assert result.extraction and len(result.extraction.units)==2
    assert result.fingerprint and result.fingerprint.family=="json"
    assert result.raw_sha256 and result.canonical_sha256


def test_processor_catalogues_unknown_binary_without_adapter(tmp_path):
    source=tmp_path/"payload.bin"; source.write_bytes(b"\x00\x01unknown")
    result=LocalFileProcessor().process(source,context(source))
    assert result.dispatch.status=="unsupported"
    assert result.extraction is None
    assert result.canonical_sha256 is None


def test_processor_distinguishes_tar_gzip_from_single_stream_gzip(tmp_path):
    source=tmp_path/"export.tar.gz"
    with tarfile.open(source,"w:gz") as archive:
        payload=b"{}"; info=tarfile.TarInfo("record.json"); info.size=len(payload); archive.addfile(info,io.BytesIO(payload))
    result=LocalFileProcessor().process(source,context(source))
    assert result.dispatch.status=="selected"
    assert result.dispatch.support and result.dispatch.support.format_key=="tgz"
    assert result.extraction and result.extraction.detected_format=="tar.gz"
