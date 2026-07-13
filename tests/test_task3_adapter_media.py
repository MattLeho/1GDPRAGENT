from __future__ import annotations

import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path
from uuid import uuid4

import pytest
from PIL import Image

from evidence.locators import resolve_locator
from ingestion.adapters.media import MediaAdapter, _extract_gps
from ingestion.models import ExtractionContext, FileTypeTruth, FileTypeTruthValue, QuarantineStatus


def _context(path: Path, **configuration: object) -> ExtractionContext:
    return ExtractionContext(
        artifact_id=uuid4(), analysis_run_id=uuid4(), export_snapshot_id=uuid4(),
        source_path=str(path), configuration=configuration,
    )


def _truth() -> FileTypeTruth:
    return FileTypeTruth(status=FileTypeTruthValue.UNKNOWN, evidence=(), reason="test")


class _SyntheticGpsExif(dict):
    def get_ifd(self, tag: int):
        assert tag == 34853
        return {
            1: "N", 2: (51, 30, 0), 3: "W", 4: (0, 7, 30),
            5: 0, 6: 35,
        }


def test_synthetic_exif_gps_is_converted_without_claiming_presence():
    gps = _extract_gps(_SyntheticGpsExif())

    assert gps is not None
    assert gps["latitude"] == 51.5
    assert gps["longitude"] == -0.125
    assert gps["altitude_metres"] == 35
    assert set(gps) == {"raw", "latitude", "longitude", "altitude_metres"}


def test_no_exif_screenshot_emits_metadata_only_full_image_locator(tmp_path: Path):
    path = tmp_path / "screenshot.png"
    Image.new("RGB", (32, 18), "navy").save(path)

    adapter = MediaAdapter()
    assert adapter.probe(str(path), _truth()).detected_format == "png"
    result = adapter.extract(str(path), _context(path))

    assert result.metadata["width"] == 32
    assert result.metadata["height"] == 18
    assert result.metadata["frame_count"] == 1
    assert result.metadata["exif"] == {}
    assert "capture_timestamp" not in result.metadata
    assert "gps" not in result.metadata
    assert result.metadata["perceptual_hash"]["algorithm"] == "dhash64"
    assert result.units[0].metadata == {"metadata_only": True}
    assert result.units[0].evidence_locator.locator == {"x": 0, "y": 0, "width": 32, "height": 18}
    assert resolve_locator(path.read_bytes(), "image_region", result.units[0].evidence_locator.locator).startswith(b"\x89PNG")
    assert any("no EXIF" in warning for warning in result.warnings)


def test_edited_jpeg_preserves_capture_timezone_device_and_software(tmp_path: Path):
    path = tmp_path / "edited.jpg"
    exif = Image.Exif()
    exif[271] = "Example Camera Co"
    exif[272] = "Camera One"
    exif[305] = "Pixel Editor 9"
    exif[36867] = "2024:03:10 12:34:56"
    exif[36881] = "+01:00"
    Image.new("RGB", (20, 10), "orange").save(path, exif=exif)

    result = MediaAdapter().extract(str(path), _context(path))

    assert result.metadata["capture_timestamp"] == "2024:03:10 12:34:56"
    assert result.metadata["timezone"] == "+01:00"
    assert result.metadata["device"] == {"make": "Example Camera Co", "model": "Camera One"}
    assert result.metadata["software"] == "Pixel Editor 9"
    assert result.quarantine_status is QuarantineStatus.NONE


def test_animated_gif_reports_frame_count(tmp_path: Path):
    path = tmp_path / "animated.gif"
    frames = [Image.new("RGB", (8, 8), colour) for colour in ("red", "green", "blue")]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=100, loop=0)

    result = MediaAdapter().extract(str(path), _context(path))

    assert result.metadata["animated"] is True
    assert result.metadata["frame_count"] == 3


def test_wav_metadata_and_resolvable_media_time_range(tmp_path: Path):
    path = tmp_path / "tone.wav"
    rate = 8000
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        samples = [int(5000 * math.sin(2 * math.pi * 440 * index / rate)) for index in range(rate)]
        output.writeframes(b"".join(struct.pack("<h", sample) for sample in samples))

    result = MediaAdapter().extract(str(path), _context(path))

    assert result.metadata["channels"] == 1
    assert result.metadata["sample_rate"] == rate
    assert 995 <= result.metadata["duration_ms"] <= 1005
    locator = result.units[0].evidence_locator
    assert locator.locator_type == "media_time_range"
    assert resolve_locator(path.read_bytes(), locator.locator_type, locator.locator)


def test_srt_extracts_timed_cues_with_exact_locators(tmp_path: Path):
    path = tmp_path / "captions.srt"
    path.write_text(
        "1\n00:00:00,500 --> 00:00:02,000\nFirst line\n\n"
        "2\n00:00:02,250 --> 00:00:03,000\nSecond\nline\n",
        encoding="utf-8", newline="",
    )

    result = MediaAdapter().extract(str(path), _context(path))

    assert [unit.text for unit in result.units] == ["First line", "Second\nline"]
    assert [unit.evidence_locator.locator for unit in result.units] == [
        {"cue": 1, "start_ms": 500, "end_ms": 2000},
        {"cue": 2, "start_ms": 2250, "end_ms": 3000},
    ]
    assert b"First line" in resolve_locator(path.read_bytes(), "subtitle_cue", result.units[0].evidence_locator.locator)


def test_webvtt_preserves_identifier_and_settings(tmp_path: Path):
    path = tmp_path / "captions.vtt"
    path.write_text(
        "WEBVTT\n\n"
        "intro\n00:00:00.000 --> 00:00:01.500 align:start position:10%\nHello <b>world</b>\n\n"
        "00:00:02.000 --> 00:00:03.000\nAgain\n",
        encoding="utf-8", newline="",
    )

    result = MediaAdapter().extract(str(path), _context(path))

    assert result.detected_format == "webvtt"
    assert result.metadata["cue_count"] == 2
    assert result.units[0].metadata == {"identifier": "intro", "settings": "align:start position:10%"}
    assert result.units[0].evidence_locator.locator == {"cue": 1, "start_ms": 0, "end_ms": 1500}
    assert b"Hello" in resolve_locator(path.read_bytes(),"subtitle_cue",result.units[0].evidence_locator.locator)


def test_missing_ffprobe_surfaces_optional_limitation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "video.mp4"
    path.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 32)
    monkeypatch.setattr(shutil, "which", lambda name: None)

    result = MediaAdapter().extract(str(path), _context(path))

    assert result.metadata["ffprobe_available"] is False
    assert result.quarantine_status is QuarantineStatus.UNSUPPORTED
    assert "not installed" in result.warnings[0]


def test_media_extension_alone_never_accepts_content(tmp_path:Path):
    path=tmp_path/"fake.jpg"; path.write_bytes(b"not an image")
    probe=MediaAdapter().probe(str(path),_truth())
    assert not probe.accepted
    assert "uncorroborated" in probe.reason


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="FFmpeg tools are optional")
def test_video_ffprobe_multiple_streams_and_selective_frames(tmp_path: Path):
    ffmpeg = shutil.which("ffmpeg")
    path = tmp_path / "multi.mkv"
    subprocess.run(
        [
            ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=black:s=160x90:d=2:r=24",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
            "-f", "lavfi", "-i", "sine=frequency=880:duration=2",
            "-map", "0:v", "-map", "1:a", "-map", "2:a", "-c:v", "libx264", "-c:a", "aac",
            "-metadata", "creation_time=2024-01-02T03:04:05Z", str(path),
        ],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
    )

    result = MediaAdapter().extract(str(path), _context(path, video_frame_sample_count=4))

    assert result.metadata["ffprobe_available"] is True
    assert len(result.metadata["video_streams"]) == 1
    assert len(result.metadata["audio_streams"]) == 2
    assert result.metadata["video_streams"][0]["width"] == 160
    assert result.metadata["video_streams"][0]["height"] == 90
    frames = [unit for unit in result.units if unit.unit_type == "video_frame_candidate"]
    assert len(frames) == 4
    assert all(unit.metadata == {"strategy": "uniform", "analysis_performed": False} for unit in frames)
    assert all(unit.evidence_locator.locator_type == "video_frame" for unit in frames)
    assert len([unit for unit in result.units if unit.unit_type == "audio_stream_metadata"]) == 2
