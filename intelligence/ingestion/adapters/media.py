from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
import tempfile
import wave
from fractions import Fraction
from pathlib import Path
from typing import Any

from ..models import (
    EvidenceLocatorValue,
    ExtractionContext,
    ExtractionResult,
    ExtractionUnit,
    FileTypeTruth,
    ProbeResult,
    QuarantineStatus,
)


_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".heif", ".bmp", ".gif"}
_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
_VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}
_SUBTITLE_EXTENSIONS = {".srt", ".vtt"}
_FORMAT_BY_EXTENSION = {
    ".jpg": "jpeg", ".jpeg": "jpeg", ".png": "png", ".webp": "webp",
    ".tif": "tiff", ".tiff": "tiff", ".heic": "heif", ".heif": "heif",
    ".bmp": "bmp", ".gif": "gif", ".wav": "wav", ".mp3": "mp3",
    ".m4a": "m4a", ".aac": "m4a", ".flac": "flac", ".ogg": "ogg",
    ".opus": "ogg", ".mp4": "mp4", ".mov": "mov", ".mkv": "mkv",
    ".webm": "webm", ".srt": "srt", ".vtt": "webvtt",
}
_EXIF_TAGS = {
    271: "make", 272: "model", 305: "software", 306: "datetime",
    36867: "datetime_original", 36868: "datetime_digitized",
    36880: "offset_time", 36881: "offset_time_original", 36882: "offset_time_digitized",
    42033: "body_serial_number", 42035: "lens_make", 42036: "lens_model",
}
_TIMING_RE = re.compile(
    r"^\s*(?P<start>\d{1,2}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*"
    r"(?P<end>\d{1,2}:\d{2}:\d{2}[,.]\d{3})(?:\s+(?P<settings>.*))?$"
)
_FFPROBE_OUTPUT_LIMIT = 2 * 1024 * 1024


def _locator(locator_type: str, **locator: Any) -> EvidenceLocatorValue:
    return EvidenceLocatorValue(locator_type=locator_type, locator=locator)


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return {"byte_length": len(value), "hex_prefix": value[:32].hex()}
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json_value(item) for item in value]
    try:
        numerator = value.numerator
        denominator = value.denominator
        return float(numerator) / float(denominator) if denominator else None
    except (AttributeError, TypeError, ValueError, ZeroDivisionError):
        return str(value)


def _ratio(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def _gps_coordinate(values: Any, reference: Any) -> float | None:
    if not isinstance(values, (tuple, list)) or len(values) != 3:
        return None
    coordinate = _ratio(values[0]) + _ratio(values[1]) / 60 + _ratio(values[2]) / 3600
    if str(reference).upper() in {"S", "W"}:
        coordinate *= -1
    return round(coordinate, 8)


def _extract_gps(exif: Any) -> dict[str, Any] | None:
    try:
        gps = exif.get_ifd(34853)
    except (AttributeError, KeyError, TypeError, ValueError):
        gps = exif.get(34853) if exif else None
    if not isinstance(gps, dict) or not gps:
        return None
    latitude = _gps_coordinate(gps.get(2), gps.get(1))
    longitude = _gps_coordinate(gps.get(4), gps.get(3))
    result: dict[str, Any] = {"raw": {str(key): _json_value(value) for key, value in gps.items()}}
    if latitude is not None and longitude is not None:
        result.update(latitude=latitude, longitude=longitude)
    if 6 in gps:
        altitude = _ratio(gps[6])
        if int(_ratio(gps.get(5, 0))) == 1:
            altitude *= -1
        result["altitude_metres"] = altitude
    return result


def _dhash(image: Any) -> str:
    from PIL import Image

    resampling = getattr(Image, "Resampling", Image).LANCZOS
    resized = image.convert("L").resize((9, 8), resampling)
    pixel_source = getattr(resized, "get_flattened_data", resized.getdata)
    pixels = list(pixel_source())
    bits = 0
    for row in range(8):
        for column in range(8):
            bits = (bits << 1) | int(pixels[row * 9 + column] > pixels[row * 9 + column + 1])
    return f"{bits:016x}"


def _register_heif() -> bool:
    try:
        from pillow_heif import register_heif_opener
    except ImportError:
        return False
    register_heif_opener()
    return True


def _parse_time(value: str) -> int:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)


def _fraction(value: Any) -> float | None:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        result = float(Fraction(str(value)))
        return round(result, 6) if math.isfinite(result) else None
    except (ValueError, ZeroDivisionError):
        return None


class MediaAdapter:
    adapter_id = "media"
    adapter_version = "1.0.0"
    family = "media"
    supported_mime_types = frozenset({
        "image/jpeg", "image/png", "image/webp", "image/tiff", "image/heic", "image/heif",
        "image/bmp", "image/gif", "audio/wav", "audio/mpeg", "audio/mp4", "audio/aac",
        "audio/flac", "audio/ogg", "audio/opus", "video/mp4", "video/quicktime",
        "video/x-matroska", "video/webm", "application/x-subrip", "text/vtt",
    })
    supported_extensions = frozenset(_FORMAT_BY_EXTENSION)
    supports_streaming = False
    supports_nested_members = False
    locator_types = frozenset({"image_region", "media_time_range", "video_frame", "subtitle_cue"})
    capability_flags = frozenset({"metadata", "timestamps", "coordinates", "frames", "audio_stream"})

    def probe(self, path: str, truth: FileTypeTruth) -> ProbeResult:
        extension = Path(path).suffix.lower()
        try:
            sample = Path(path).read_bytes()[:64]
        except OSError as exc:
            return ProbeResult(accepted=False, confidence=0.0, reason=f"unreadable: {exc}")
        detected = self._signature_format(sample, extension)
        if detected:
            return ProbeResult(accepted=True, confidence=0.98, detected_format=detected, reason="recognised media signature")
        if extension in _SUBTITLE_EXTENSIONS:
            try:
                text = Path(path).read_text(encoding="utf-8-sig", errors="strict")[:65536]
            except (OSError, UnicodeDecodeError) as exc:
                return ProbeResult(accepted=False, confidence=0.0, reason=f"subtitle unreadable: {exc}")
            is_vtt = text.lstrip().startswith("WEBVTT")
            has_timing = any(_TIMING_RE.match(line) for line in text.splitlines())
            if is_vtt or has_timing:
                return ProbeResult(accepted=True, confidence=0.95, detected_format="webvtt" if is_vtt else "srt", reason="timed-text syntax")
        if extension in _AUDIO_EXTENSIONS:
            try:
                from mutagen import File as MutagenFile
                media=MutagenFile(path)
                if media is not None and getattr(media,"info",None) is not None:
                    return ProbeResult(accepted=True,confidence=0.85,detected_format=_FORMAT_BY_EXTENSION[extension],reason="bounded audio parser probe")
            except Exception:
                pass
        if extension in self.supported_extensions:
            return ProbeResult(accepted=False,confidence=0.0,detected_format=_FORMAT_BY_EXTENSION[extension],reason="extension is uncorroborated by a media parser or signature")
        return ProbeResult(accepted=False, confidence=0.0, reason="not a supported media family")

    @staticmethod
    def _signature_format(sample: bytes, extension: str) -> str | None:
        if sample.startswith(b"\xff\xd8\xff"): return "jpeg"
        if sample.startswith(b"\x89PNG\r\n\x1a\n"): return "png"
        if sample.startswith((b"II*\x00", b"MM\x00*")): return "tiff"
        if sample.startswith(b"BM"): return "bmp"
        if sample.startswith((b"GIF87a", b"GIF89a")): return "gif"
        if sample.startswith(b"fLaC"): return "flac"
        if sample.startswith(b"OggS"): return "ogg"
        if sample.startswith(b"ID3") or (len(sample) > 1 and sample[0] == 0xFF and sample[1] & 0xE0 == 0xE0): return "mp3"
        if sample.startswith(b"RIFF") and sample[8:12] == b"WAVE": return "wav"
        if sample.startswith(b"RIFF") and sample[8:12] == b"WEBP": return "webp"
        if sample.startswith(b"\x1aE\xdf\xa3"): return "webm" if extension == ".webm" else "mkv"
        if len(sample) >= 12 and sample[4:8] == b"ftyp":
            brand = sample[8:12]
            if brand in {b"heic", b"heix", b"hevc", b"hevx", b"mif1", b"msf1"}: return "heif"
            if extension in {".m4a", ".aac"} or brand in {b"M4A ", b"M4B "}: return "m4a"
            return "mov" if extension == ".mov" or brand == b"qt  " else "mp4"
        return None

    def extract(self, path: str, context: ExtractionContext) -> ExtractionResult:
        probe = self.probe(path, FileTypeTruth(status="UNKNOWN", evidence=(), reason="adapter extraction"))
        detected = probe.detected_format or _FORMAT_BY_EXTENSION.get(Path(path).suffix.lower(), "unknown")
        if detected in {"jpeg", "png", "webp", "tiff", "heif", "bmp", "gif"}:
            return self._extract_image(path, context, detected)
        if detected in {"wav", "mp3", "m4a", "flac", "ogg"}:
            return self._extract_audio(path, context, detected)
        if detected in {"mp4", "mov", "mkv", "webm"}:
            return self._extract_video(path, context, detected)
        if detected in {"srt", "webvtt"}:
            return self._extract_subtitles(path, context, detected)
        return ExtractionResult(
            artifact_id=context.artifact_id, adapter_id=self.adapter_id, adapter_version=self.adapter_version,
            family=self.family, detected_format=detected, warnings=("unsupported media format",),
            quarantine_status=QuarantineStatus.UNSUPPORTED,
        )

    def _extract_image(self, path: str, context: ExtractionContext, detected: str) -> ExtractionResult:
        warnings: list[str] = []
        if detected == "heif" and not _register_heif():
            return ExtractionResult(
                artifact_id=context.artifact_id, adapter_id=self.adapter_id, adapter_version=self.adapter_version,
                family=self.family, detected_format=detected,
                warnings=("HEIF metadata extraction requires an optional platform/Pillow HEIF codec",),
                quarantine_status=QuarantineStatus.UNSUPPORTED,
            )
        try:
            from PIL import Image
            with Image.open(path) as image:
                image.load()
                exif = image.getexif()
                raw_exif = {str(tag): _json_value(value) for tag, value in exif.items()}
                selected = {_EXIF_TAGS[tag]: _json_value(exif[tag]) for tag in _EXIF_TAGS if tag in exif}
                gps = _extract_gps(exif)
                metadata: dict[str, Any] = {
                    "format": image.format or detected.upper(), "width": image.width, "height": image.height,
                    "mode": image.mode, "frame_count": int(getattr(image, "n_frames", 1)),
                    "animated": bool(getattr(image, "is_animated", False)), "exif": raw_exif,
                    "capture_timestamp": selected.get("datetime_original") or selected.get("datetime_digitized") or selected.get("datetime"),
                    "timezone": selected.get("offset_time_original") or selected.get("offset_time_digitized") or selected.get("offset_time"),
                    "device": {key: selected[key] for key in ("make", "model", "body_serial_number", "lens_make", "lens_model") if key in selected},
                    "software": selected.get("software"), "gps": gps,
                    "perceptual_hash": {"algorithm": "dhash64", "value": _dhash(image)},
                }
                metadata = {key: value for key, value in metadata.items() if value is not None}
                unit = ExtractionUnit(
                    unit_id="image:0", unit_type="image_metadata", ordinal=0, structured_payload=metadata,
                    metadata={"metadata_only": True},
                    evidence_locator=_locator("image_region", x=0, y=0, width=image.width, height=image.height),
                )
        except Exception as exc:
            return ExtractionResult(
                artifact_id=context.artifact_id, adapter_id=self.adapter_id, adapter_version=self.adapter_version,
                family=self.family, detected_format=detected, warnings=(f"image codec could not decode metadata: {exc}",),
                quarantine_status=QuarantineStatus.CORRUPT,
            )
        if not metadata.get("exif"):
            warnings.append("image has no EXIF metadata; no capture time, device, software, or GPS can be established")
        return ExtractionResult(
            artifact_id=context.artifact_id, adapter_id=self.adapter_id, adapter_version=self.adapter_version,
            family=self.family, detected_format=detected, metadata=metadata, units=(unit,), warnings=tuple(warnings),
        )

    def _extract_audio(self, path: str, context: ExtractionContext, detected: str) -> ExtractionResult:
        warnings: list[str] = []
        metadata: dict[str, Any] = {"container": detected}
        try:
            from mutagen import File as MutagenFile
            media = MutagenFile(path, easy=False)
        except Exception as exc:
            media = None
            warnings.append(f"mutagen metadata parser failed: {exc}")
        if media is not None and getattr(media, "info", None) is not None:
            info = media.info
            info_type = type(info).__name__
            lowered_info_type = info_type.lower()
            codec = next(
                (name for marker, name in (
                    ("opus", "opus"), ("vorbis", "vorbis"), ("aac", "aac"),
                    ("mp3", "mp3"), ("mpeg", "mp3"), ("flac", "flac"), ("wave", "pcm"),
                ) if marker in lowered_info_type),
                detected,
            )
            metadata.update({
                "codec": codec, "codec_info_type": info_type,
                "duration_ms": round(float(getattr(info, "length", 0)) * 1000),
                "channels": getattr(info, "channels", None), "sample_rate": getattr(info, "sample_rate", None),
                "bitrate": getattr(info, "bitrate", None),
            })
            tags = getattr(media, "tags", None)
            metadata["tags"] = {str(key): _json_value(value) for key, value in tags.items()} if tags else {}
        if detected == "wav" and not metadata.get("duration_ms"):
            try:
                with wave.open(path, "rb") as audio:
                    rate = audio.getframerate()
                    metadata.update(
                        codec=f"pcm_s{audio.getsampwidth() * 8}le", channels=audio.getnchannels(), sample_rate=rate,
                        duration_ms=round(audio.getnframes() / rate * 1000) if rate else 0, tags={},
                    )
            except (OSError, wave.Error) as exc:
                warnings.append(f"WAV header could not be decoded: {exc}")
        metadata = {key: value for key, value in metadata.items() if value is not None}
        duration = int(metadata.get("duration_ms", 0))
        units: tuple[ExtractionUnit, ...] = ()
        status = QuarantineStatus.NONE
        if duration > 0:
            units = (ExtractionUnit(
                unit_id="audio:0", unit_type="audio_stream", ordinal=0, structured_payload=metadata,
                evidence_locator=_locator("media_time_range", start_ms=0, end_ms=duration),
            ),)
        else:
            warnings.append("audio duration is unavailable; no resolvable time-range unit was emitted")
            status = QuarantineStatus.CORRUPT
        return ExtractionResult(
            artifact_id=context.artifact_id, adapter_id=self.adapter_id, adapter_version=self.adapter_version,
            family=self.family, detected_format=detected, metadata=metadata, units=units,
            warnings=tuple(warnings), quarantine_status=status,
        )

    def _ffprobe(self, path: str, timeout_seconds: float) -> tuple[dict[str, Any] | None, str | None]:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None, "ffprobe is not installed; video stream metadata and frame candidates are unavailable"
        command = [
            ffprobe, "-v", "error", "-show_entries",
            "format=format_name,duration:format_tags=creation_time,location,location-eng,encoder,major_brand:"
            "stream=index,codec_type,codec_name,width,height,avg_frame_rate,r_frame_rate,duration,channels,sample_rate:"
            "stream_tags=language,title,creation_time,location,location-eng",
            "-of", "json", path,
        ]
        try:
            with tempfile.TemporaryFile() as output:
                subprocess.run(command, stdout=output, stderr=subprocess.DEVNULL, timeout=timeout_seconds, check=True)
                size = output.tell()
                if size > _FFPROBE_OUTPUT_LIMIT:
                    return None, f"ffprobe output exceeded the {_FFPROBE_OUTPUT_LIMIT}-byte safety limit"
                output.seek(0)
                return json.loads(output.read().decode("utf-8")), None
        except subprocess.TimeoutExpired:
            return None, f"ffprobe exceeded the {timeout_seconds:g}-second safety timeout"
        except (OSError, subprocess.CalledProcessError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return None, f"ffprobe could not inspect the video: {exc}"

    def _extract_video(self, path: str, context: ExtractionContext, detected: str) -> ExtractionResult:
        configured_timeout = context.configuration.get("ffprobe_timeout_seconds", 15)
        try:
            timeout = min(max(float(configured_timeout), 1.0), 60.0)
        except (TypeError, ValueError):
            timeout = 15.0
        document, limitation = self._ffprobe(path, timeout)
        if document is None:
            return ExtractionResult(
                artifact_id=context.artifact_id, adapter_id=self.adapter_id, adapter_version=self.adapter_version,
                family=self.family, detected_format=detected, metadata={"container": detected, "ffprobe_available": False},
                warnings=(limitation or "ffprobe limitation",), quarantine_status=QuarantineStatus.UNSUPPORTED,
            )
        format_data = document.get("format") or {}
        streams = document.get("streams") or []
        duration_ms = round(float(format_data.get("duration", 0) or 0) * 1000)
        video_streams: list[dict[str, Any]] = []
        audio_streams: list[dict[str, Any]] = []
        subtitle_streams: list[dict[str, Any]] = []
        for stream in streams:
            item = {str(key): _json_value(value) for key, value in stream.items()}
            if item.get("codec_type") == "video":
                item["average_frame_rate"] = _fraction(item.get("avg_frame_rate"))
                item["real_frame_rate"] = _fraction(item.get("r_frame_rate"))
                item["variable_frame_rate_candidate"] = (
                    item["average_frame_rate"] is not None and item["real_frame_rate"] is not None
                    and item["average_frame_rate"] != item["real_frame_rate"]
                )
                video_streams.append(item)
            elif item.get("codec_type") == "audio":
                audio_streams.append(item)
            elif item.get("codec_type") == "subtitle":
                subtitle_streams.append(item)
        tags = {str(key): _json_value(value) for key, value in (format_data.get("tags") or {}).items()}
        metadata = {
            "container": format_data.get("format_name") or detected, "duration_ms": duration_ms,
            "creation_time": tags.get("creation_time"),
            "gps": tags.get("location") or tags.get("location-eng"), "tags": tags,
            "video_streams": video_streams, "audio_streams": audio_streams,
            "subtitle_streams": subtitle_streams, "ffprobe_available": True,
        }
        try:
            requested = int(context.configuration.get("video_frame_sample_count", 5))
        except (TypeError, ValueError):
            requested = 5
        sample_count = min(max(requested, 0), 20)
        timestamps = [] if duration_ms <= 0 or sample_count == 0 else sorted({
            min(duration_ms - 1, round(index * duration_ms / sample_count)) for index in range(sample_count)
        })
        units: list[ExtractionUnit] = []
        for ordinal, timestamp in enumerate(timestamps):
            units.append(ExtractionUnit(
                unit_id=f"video-frame:{ordinal}", unit_type="video_frame_candidate", ordinal=ordinal,
                value=timestamp, metadata={"strategy": "uniform", "analysis_performed": False},
                evidence_locator=_locator("video_frame", timestamp_ms=timestamp),
            ))
        for stream in audio_streams:
            if duration_ms > 0:
                units.append(ExtractionUnit(
                    unit_id=f"video-audio:{stream.get('index')}", unit_type="audio_stream_metadata", ordinal=len(units),
                    structured_payload=stream,
                    evidence_locator=_locator("media_time_range", start_ms=0, end_ms=duration_ms),
                ))
        for stream in subtitle_streams:
            if duration_ms > 0:
                units.append(ExtractionUnit(
                    unit_id=f"video-subtitle:{stream.get('index')}", unit_type="subtitle_stream_metadata", ordinal=len(units),
                    structured_payload=stream,
                    evidence_locator=_locator("media_time_range", start_ms=0, end_ms=duration_ms),
                ))
        warnings = []
        if not video_streams:
            warnings.append("ffprobe found no video stream")
        if duration_ms <= 0:
            warnings.append("video duration is unavailable; no deterministic frame candidates were emitted")
        return ExtractionResult(
            artifact_id=context.artifact_id, adapter_id=self.adapter_id, adapter_version=self.adapter_version,
            family=self.family, detected_format=detected, metadata=metadata, units=tuple(units), warnings=tuple(warnings),
        )

    def _extract_subtitles(self, path: str, context: ExtractionContext, detected: str) -> ExtractionResult:
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as exc:
            return ExtractionResult(
                artifact_id=context.artifact_id, adapter_id=self.adapter_id, adapter_version=self.adapter_version,
                family=self.family, detected_format=detected, warnings=(f"subtitle is not valid UTF-8 text: {exc}",),
                quarantine_status=QuarantineStatus.CORRUPT,
            )
        blocks = [block for block in re.split(r"\r?\n\s*\r?\n", text.strip()) if block.strip()]
        units: list[ExtractionUnit] = []
        warnings: list[str] = []
        for block in blocks:
            lines = block.splitlines()
            timing_index = next((index for index, line in enumerate(lines[:2]) if _TIMING_RE.match(line)), None)
            if timing_index is None:
                if not lines[0].strip().startswith(("WEBVTT", "NOTE", "STYLE", "REGION")):
                    warnings.append(f"ignored subtitle block without valid timing at block {blocks.index(block) + 1}")
                continue
            match = _TIMING_RE.match(lines[timing_index])
            assert match is not None
            start_ms, end_ms = _parse_time(match.group("start")), _parse_time(match.group("end"))
            if end_ms <= start_ms:
                warnings.append(f"ignored subtitle cue whose end does not follow its start at block {blocks.index(block) + 1}")
                continue
            cue = len(units) + 1
            identifier = lines[0].strip() if timing_index == 1 else None
            cue_text = "\n".join(lines[timing_index + 1:])
            units.append(ExtractionUnit(
                unit_id=f"subtitle:{cue}", unit_type="subtitle_cue", ordinal=cue - 1, text=cue_text,
                metadata={"identifier": identifier, "settings": match.group("settings")},
                evidence_locator=_locator("subtitle_cue", cue=cue, start_ms=start_ms, end_ms=end_ms),
            ))
        status = QuarantineStatus.NONE if units else QuarantineStatus.CORRUPT
        if not units:
            warnings.append("no valid timed subtitle cues were found")
        metadata = {"cue_count": len(units), "format": detected, "encoding": "utf-8-sig"}
        return ExtractionResult(
            artifact_id=context.artifact_id, adapter_id=self.adapter_id, adapter_version=self.adapter_version,
            family=self.family, detected_format=detected, metadata=metadata, units=tuple(units),
            warnings=tuple(warnings), quarantine_status=status,
        )
