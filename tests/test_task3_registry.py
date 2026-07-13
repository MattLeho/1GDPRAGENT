from ingestion.models import FileTypeEvidence, FileTypeTruth, FileTypeTruthValue, ProbeResult, SupportStatus
from ingestion.registry import FORMAT_SUPPORT_REGISTRY, FORMATS_BY_KEY, FileWorkflowRegistry


def test_p0_registry_covers_required_families_and_never_hides_p2():
    keys={r.format_key for r in FORMAT_SUPPORT_REGISTRY}
    assert {"zip","tar","tgz","gzip","bzip2","xz","json","ndjson","csv","tsv","xml","html","yaml","text","markdown","pdf","docx","xlsx","pptx","odt","ods","odp","rtf","eml","mbox","ics","vcf","jpeg","png","webp","tiff","heif","bmp","gif","wav","mp3","m4a","flac","ogg","mp4","mov","mkv","webm","srt","webvtt","geojson","kml","kmz","gpx","sqlite"} <= keys
    assert FORMATS_BY_KEY["unknown_binary"].status is SupportStatus.UNSUPPORTED
    assert FORMATS_BY_KEY["ost"].status is SupportStatus.UNSUPPORTED


def test_supported_formats_declare_locator_and_fixture_contracts():
    executable={SupportStatus.SUPPORTED_DETERMINISTIC,SupportStatus.SUPPORTED_WITH_OPTIONAL_SPECIALIST}
    for record in FORMAT_SUPPORT_REGISTRY:
        if record.status in executable:
            assert record.adapter_id
            assert record.locator_types
            assert len(record.fixture_ids)>=3


def test_dispatcher_keeps_unknown_and_missing_adapter_visible():
    registry=FileWorkflowRegistry()
    unknown=FileTypeTruth(status=FileTypeTruthValue.UNKNOWN,evidence=(FileTypeEvidence(source="extension",value=".x"),),reason="no evidence")
    assert registry.dispatch("x",unknown).status=="unsupported"
    known=FileTypeTruth(status=FileTypeTruthValue.MATCH,detected_format="json",detected_mime="application/json",evidence=(FileTypeEvidence(source="signature",candidate_format="json"),),reason="agreed")
    decision=registry.dispatch("x.json",known)
    assert decision.status=="unavailable"
    assert decision.support and decision.support.format_key=="json"


def test_extension_can_only_nominate_an_adapter_probe(tmp_path):
    class Adapter:
        adapter_id="structured_text"; adapter_version="1"; family="structured_text"
        supported_mime_types=frozenset(); supported_extensions=frozenset({".json"})
        supports_streaming=True; supports_nested_members=False
        locator_types=frozenset({"json_pointer"}); capability_flags=frozenset({"structured_records"})
        def probe(self,path,truth): return ProbeResult(accepted=True,confidence=1,detected_format="json",reason="JSON parsed")
        def extract(self,path,context): raise AssertionError("not part of dispatch")
    truth=FileTypeTruth(status=FileTypeTruthValue.UNKNOWN,evidence=(FileTypeEvidence(source="extension",value=".json",candidate_format="json"),),reason="extension only")
    decision=FileWorkflowRegistry([Adapter()]).dispatch(str(tmp_path/"x.json"),truth)
    assert decision.status=="selected"
    assert decision.reason=="JSON parsed"
