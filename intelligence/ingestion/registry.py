from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .models import FileFamilyAdapter, FileTypeTruth, FormatSupportRecord, ProbeResult, SupportStatus

_MAGIC={
    "pdf":("255044462d",),"zip":("504b0304",),"gzip":("1f8b",),"tgz":("1f8b",),
    "bzip2":("425a68",),"xz":("fd377a585a00",),"sqlite":("53514c69746520666f726d6174203300",),
    "jpeg":("ffd8ff",),"png":("89504e470d0a1a0a",),"gif":("474946383761","474946383961"),
    "tiff":("49492a00","4d4d002a"),"bmp":("424d",),"webp":("52494646????????57454250",),
    "flac":("664c6143",),"ogg":("4f676753",),"wav":("52494646????????57415645",),
    "docx":("504b0304",),"xlsx":("504b0304",),"pptx":("504b0304",),
    "odt":("504b0304",),"ods":("504b0304",),"odp":("504b0304",),"kmz":("504b0304",),
}


def _record(
    key: str, family: str, adapter: str | None, status: SupportStatus,
    extensions: tuple[str, ...], mime_types: tuple[str, ...] = (), *,
    capabilities: tuple[str, ...] = (), locators: tuple[str, ...] = (),
    task_routes: tuple[str, ...] = (), dependencies: tuple[str, ...] = (),
    security: tuple[str, ...] = (), unsupported: tuple[str, ...] = (), priority: int = 100,
) -> FormatSupportRecord:
    return FormatSupportRecord(
        format_key=key, family=family, probe_priority=priority, adapter_id=adapter,
        adapter_version="1" if adapter else None, status=status,
        supported_extensions=extensions, supported_mime_types=mime_types,magic_signatures=_MAGIC.get(key,()),
        capability_flags=capabilities, locator_types=locators, task_routes=task_routes,
        streaming=family in {"structured_text", "email_calendar", "geospatial_database", "archives"},
        system_dependencies=dependencies, security_notes=security,
        known_unsupported_features=unsupported, fixture_ids=(f"{key}_valid", f"{key}_malformed", f"{key}_locator") if status in {SupportStatus.SUPPORTED_DETERMINISTIC,SupportStatus.SUPPORTED_WITH_OPTIONAL_SPECIALIST} else (),
    )


S=SupportStatus
FORMAT_SUPPORT_REGISTRY: tuple[FormatSupportRecord, ...] = (
    _record("json","structured_text","structured_text",S.SUPPORTED_DETERMINISTIC,(".json",),("application/json",),capabilities=("structured_records",),locators=("json_pointer","json_record"),priority=10),
    _record("ndjson","structured_text","structured_text",S.SUPPORTED_DETERMINISTIC,(".jsonl",".ndjson"),("application/x-ndjson",),capabilities=("structured_records",),locators=("json_record","json_pointer"),priority=10),
    _record("csv","structured_text","structured_text",S.SUPPORTED_DETERMINISTIC,(".csv",),("text/csv",),capabilities=("tables","structured_records"),locators=("csv_row","csv_cell"),priority=10),
    _record("tsv","structured_text","structured_text",S.SUPPORTED_DETERMINISTIC,(".tsv",),("text/tab-separated-values",),capabilities=("tables","structured_records"),locators=("csv_row","csv_cell"),priority=10),
    _record("xml","structured_text","structured_text",S.SUPPORTED_DETERMINISTIC,(".xml",),("application/xml","text/xml"),capabilities=("structured_records",),locators=("xml_element",)),
    _record("html","structured_text","structured_text",S.SUPPORTED_DETERMINISTIC,(".html",".htm"),("text/html",),capabilities=("text","metadata"),locators=("html_dom_span","text_byte_span")),
    _record("yaml","structured_text","structured_text",S.SUPPORTED_DETERMINISTIC,(".yaml",".yml"),("application/yaml","text/yaml"),capabilities=("structured_records",),locators=("text_line","text_byte_span"),dependencies=("safe YAML parser",)),
    _record("text","structured_text","structured_text",S.SUPPORTED_DETERMINISTIC,(".txt",".log"),("text/plain",),capabilities=("text",),locators=("text_line","text_byte_span")),
    _record("markdown","structured_text","structured_text",S.SUPPORTED_DETERMINISTIC,(".md",".markdown"),("text/markdown",),capabilities=("text",),locators=("text_line","text_byte_span")),
    _record("pdf","documents","documents",S.SUPPORTED_WITH_OPTIONAL_SPECIALIST,(".pdf",),("application/pdf",),capabilities=("pages","text","tables","embedded_media"),locators=("pdf_page_block","pdf_region"),task_routes=("document.ocr",)),
    _record("docx","documents","documents",S.SUPPORTED_DETERMINISTIC,(".docx",),("application/vnd.openxmlformats-officedocument.wordprocessingml.document",),capabilities=("text","tables","embedded_media"),locators=("office_paragraph","office_table_cell")),
    _record("xlsx","documents","documents",S.SUPPORTED_DETERMINISTIC,(".xlsx",),("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",),capabilities=("sheets","tables"),locators=("spreadsheet_cell",)),
    _record("pptx","documents","documents",S.SUPPORTED_DETERMINISTIC,(".pptx",),("application/vnd.openxmlformats-officedocument.presentationml.presentation",),capabilities=("slides","tables","embedded_media"),locators=("slide_shape","slide_notes")),
    _record("odt","documents","documents",S.SUPPORTED_DETERMINISTIC,(".odt",),("application/vnd.oasis.opendocument.text",),capabilities=("text","tables","embedded_media"),locators=("office_paragraph","office_table_cell")),
    _record("ods","documents","documents",S.SUPPORTED_DETERMINISTIC,(".ods",),("application/vnd.oasis.opendocument.spreadsheet",),capabilities=("sheets","tables"),locators=("spreadsheet_cell",)),
    _record("odp","documents","documents",S.SUPPORTED_DETERMINISTIC,(".odp",),("application/vnd.oasis.opendocument.presentation",),capabilities=("slides","tables","embedded_media"),locators=("slide_shape","slide_notes")),
    _record("rtf","documents","documents",S.SUPPORTED_DETERMINISTIC,(".rtf",),("application/rtf","text/rtf"),capabilities=("text",),locators=("office_paragraph",)),
    _record("eml","email_calendar","email_calendar",S.SUPPORTED_DETERMINISTIC,(".eml",),("message/rfc822",),capabilities=("text","attachments","metadata"),locators=("email_header","email_mime_part","email_attachment")),
    _record("mbox","email_calendar","email_calendar",S.SUPPORTED_DETERMINISTIC,(".mbox",),("application/mbox",),capabilities=("text","attachments","metadata"),locators=("email_header","email_mime_part","email_attachment")),
    _record("ics","email_calendar","email_calendar",S.SUPPORTED_DETERMINISTIC,(".ics",),("text/calendar",),capabilities=("structured_records","timestamps"),locators=("calendar_component",)),
    _record("vcf","email_calendar","email_calendar",S.SUPPORTED_DETERMINISTIC,(".vcf",),("text/vcard",),capabilities=("structured_records",),locators=("vcard_property",)),
    *(_record(key,"media","media",S.SUPPORTED_WITH_OPTIONAL_SPECIALIST,exts,mimes,capabilities=("metadata",flag),locators=("image_region",) if flag=="frames" else ("media_time_range",),task_routes=routes,dependencies=deps) for key,exts,mimes,flag,routes,deps in (
        ("jpeg",(".jpg",".jpeg"),("image/jpeg",),"frames",("image.origin_classification","image.ocr","image.caption","image.landmark_candidate"),()),
        ("png",(".png",),("image/png",),"frames",("image.origin_classification","image.ocr","image.caption","image.landmark_candidate"),()),
        ("webp",(".webp",),("image/webp",),"frames",("image.origin_classification","image.ocr","image.caption"),()),
        ("tiff",(".tif",".tiff"),("image/tiff",),"frames",("image.origin_classification","image.ocr","image.caption"),()),
        ("heif",(".heic",".heif"),("image/heic","image/heif"),"frames",("image.origin_classification","image.ocr","image.caption"),("platform HEIF codec",)),
        ("bmp",(".bmp",),("image/bmp",),"frames",("image.origin_classification","image.ocr"),()),
        ("gif",(".gif",),("image/gif",),"frames",("image.origin_classification","image.ocr","image.caption"),()),
        ("wav",(".wav",),("audio/wav",),"audio_stream",("speech.transcription","speech.diarisation","speech.translation"),()),
        ("mp3",(".mp3",),("audio/mpeg",),"audio_stream",("speech.transcription","speech.diarisation","speech.translation"),()),
        ("m4a",(".m4a",".aac"),("audio/mp4","audio/aac"),"audio_stream",("speech.transcription","speech.diarisation","speech.translation"),()),
        ("flac",(".flac",),("audio/flac",),"audio_stream",("speech.transcription","speech.diarisation","speech.translation"),()),
        ("ogg",(".ogg",".opus"),("audio/ogg","audio/opus"),"audio_stream",("speech.transcription","speech.diarisation","speech.translation"),()),
        ("mp4",(".mp4",),("video/mp4",),"frames",("speech.transcription","image.caption"),("ffprobe",)),
        ("mov",(".mov",),("video/quicktime",),"frames",("speech.transcription","image.caption"),("ffprobe",)),
        ("mkv",(".mkv",),("video/x-matroska",),"frames",("speech.transcription","image.caption"),("ffprobe",)),
        ("webm",(".webm",),("video/webm",),"frames",("speech.transcription","image.caption"),("ffprobe",)),
    )),
    _record("srt","media","media",S.SUPPORTED_DETERMINISTIC,(".srt",),("application/x-subrip",),capabilities=("timestamps","text"),locators=("subtitle_cue",)),
    _record("webvtt","media","media",S.SUPPORTED_DETERMINISTIC,(".vtt",),("text/vtt",),capabilities=("timestamps","text"),locators=("subtitle_cue",)),
    _record("geojson","geospatial_database","geospatial_database",S.SUPPORTED_DETERMINISTIC,(".geojson",),("application/geo+json",),capabilities=("coordinates","structured_records"),locators=("geospatial_feature",)),
    _record("kml","geospatial_database","geospatial_database",S.SUPPORTED_DETERMINISTIC,(".kml",),("application/vnd.google-earth.kml+xml",),capabilities=("coordinates","structured_records"),locators=("geospatial_feature",)),
    _record("kmz","geospatial_database","geospatial_database",S.SUPPORTED_DETERMINISTIC,(".kmz",),("application/vnd.google-earth.kmz",),capabilities=("coordinates","archive_members"),locators=("archive_member","geospatial_feature")),
    _record("gpx","geospatial_database","geospatial_database",S.SUPPORTED_DETERMINISTIC,(".gpx",),("application/gpx+xml",),capabilities=("coordinates","timestamps"),locators=("geospatial_feature",)),
    _record("sqlite","geospatial_database","geospatial_database",S.SUPPORTED_DETERMINISTIC,(".sqlite",".sqlite3",".db"),("application/vnd.sqlite3",),capabilities=("database_tables","structured_records"),locators=("database_table_row","database_cell"),security=("read-only URI; no extensions, triggers, or user code",)),
    *(_record(key,"archives","archives",S.SUPPORTED_DETERMINISTIC,exts,mimes,capabilities=("archive_members",),locators=("archive_member",),security=("global depth, member, expansion and byte limits",),priority=5) for key,exts,mimes in (
        ("zip",(".zip",),("application/zip",)),("tar",(".tar",),("application/x-tar",)),("tgz",(".tar.gz",".tgz"),("application/gzip",)),("gzip",(".gz",),("application/gzip",)),("bzip2",(".bz2",),("application/x-bzip2",)),("xz",(".xz",),("application/x-xz",)),
    )),
    *(_record(key,family,None,S.METADATA_ONLY,exts,dependencies=deps,unsupported=("requires reviewed optional read-only adapter",)) for key,family,exts,deps in (
        ("7z","archives",(".7z",),("7zip",)),("rar","archives",(".rar",),("unrar",)),("doc","documents",(".doc",),("constrained converter",)),("xls","documents",(".xls",),("constrained converter",)),("ppt","documents",(".ppt",),("constrained converter",)),("xlsb","documents",(".xlsb",),("optional XLSB parser",)),("msg","email_calendar",(".msg",),("optional MSG parser",)),("pst","email_calendar",(".pst",),("optional PST parser",)),("geopackage","geospatial_database",(".gpkg",),()),("shapefile","geospatial_database",(".shp",),()),("gml","geospatial_database",(".gml",),()),("geotiff","geospatial_database",(".geotiff",),()),("plist","geospatial_database",(".plist",),()),("har","geospatial_database",(".har",),()),("leveldb","geospatial_database",(".ldb",),()),("avro","structured_text",(".avro",),()),("parquet","structured_text",(".parquet",),()),
    )),
    *(_record(key,"unsupported",None,S.UNSUPPORTED,exts,unsupported=(reason,)) for key,exts,reason in (
        ("ost",(".ost",),"proprietary mailbox store"),("protobuf",(".pb",),"descriptor/schema required"),("disk_image",(".iso",".dmg",".img"),"disk images are not mounted"),("unknown_binary",(),"unknown binary content is catalogued and quarantined"),
    )),
)

FORMATS_BY_KEY={record.format_key:record for record in FORMAT_SUPPORT_REGISTRY}
FORMAT_KEY_ALIASES={"tar.gz":"tgz","tar_gz":"tgz","jsonl":"ndjson","jpg":"jpeg","vtt":"webvtt"}

def _support_for(key:str,default:FormatSupportRecord|None=None)->FormatSupportRecord|None:
    return FORMATS_BY_KEY.get(FORMAT_KEY_ALIASES.get(key.lower(),key.lower()),default)


@dataclass(frozen=True)
class DispatchDecision:
    adapter: FileFamilyAdapter | None
    support: FormatSupportRecord | None
    status: str
    reason: str
    probes: tuple[ProbeResult, ...] = ()


class FileWorkflowRegistry:
    def __init__(self, adapters: Iterable[FileFamilyAdapter] = ()):
        self._adapters={adapter.adapter_id:adapter for adapter in adapters}

    @property
    def support(self) -> tuple[FormatSupportRecord, ...]:
        return FORMAT_SUPPORT_REGISTRY

    def dispatch(self, path: str, truth: FileTypeTruth) -> DispatchDecision:
        if not truth.detected_format:
            # Extension/MIME metadata may nominate bounded probe candidates but
            # never selects an adapter by itself. A deterministic adapter probe
            # must accept, and exactly one detected format must result.
            candidate_keys={item.candidate_format.lower() for item in truth.evidence if item.candidate_format}
            candidates=[FORMATS_BY_KEY[key] for key in candidate_keys if key in FORMATS_BY_KEY]
            probes: list[tuple[FileFamilyAdapter,FormatSupportRecord,ProbeResult]]=[]
            seen_adapters: set[str]=set()
            for support in sorted(candidates,key=lambda item:item.probe_priority):
                if not support.adapter_id or support.adapter_id in seen_adapters:
                    continue
                seen_adapters.add(support.adapter_id)
                adapter=self._adapters.get(support.adapter_id)
                if adapter:
                    probe=adapter.probe(path,truth)
                    if probe.accepted:
                        resolved=_support_for(probe.detected_format or support.format_key,support)
                        probes.append((adapter,resolved,probe))
            detected={probe.detected_format or support.format_key for _,support,probe in probes}
            if len(probes)==1 and len(detected)==1:
                adapter,support,probe=probes[0]
                return DispatchDecision(adapter,support,"selected",probe.reason,(probe,))
            if probes:
                return DispatchDecision(None,None,"ambiguous","multiple deterministic probes accepted",tuple(item[2] for item in probes))
            return DispatchDecision(None,None,"ambiguous" if truth.status.value=="AMBIGUOUS" else "unsupported",truth.reason)
        support=_support_for(truth.detected_format)
        if not support:
            return DispatchDecision(None,None,"unsupported",f"uncatalogued format: {truth.detected_format}")
        if support.status in {S.UNSUPPORTED,S.QUARANTINED,S.METADATA_ONLY} or not support.adapter_id:
            return DispatchDecision(None,support,support.status.value.lower(),"no approved executable adapter")
        adapter=self._adapters.get(support.adapter_id)
        if not adapter:
            return DispatchDecision(None,support,"unavailable",f"adapter {support.adapter_id} is not installed")
        probe=adapter.probe(path,truth)
        if not probe.accepted:
            return DispatchDecision(None,support,"ambiguous",probe.reason,(probe,))
        resolved=_support_for(probe.detected_format or support.format_key,support)
        return DispatchDecision(adapter,resolved,"selected",probe.reason,(probe,))


def build_default_registry() -> FileWorkflowRegistry:
    """Build the installed deterministic registry without provider adapters."""
    from .adapters import ArchiveAdapter,DocumentsAdapter,EmailCalendarAdapter,GeospatialDatabaseAdapter,MediaAdapter,StructuredTextAdapter
    return FileWorkflowRegistry([StructuredTextAdapter(),DocumentsAdapter(),EmailCalendarAdapter(),GeospatialDatabaseAdapter(),ArchiveAdapter(),MediaAdapter()])
