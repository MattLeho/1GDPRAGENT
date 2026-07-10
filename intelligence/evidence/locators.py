from __future__ import annotations

import csv
import hashlib
import io
import json
import zipfile
from typing import Any

from bs4 import BeautifulSoup

from .models import (
    ArchiveMemberLocator, CsvCellLocator, CsvRowLocator, HtmlDomSpanLocator,
    ImageRegionLocator, JsonPointerLocator, LocatorType, MediaTimeRangeLocator,
    TextSpanLocator,
)


class LocatorResolutionError(ValueError):
    pass


def _json_pointer(document: Any, pointer: str) -> Any:
    current = document
    if pointer == "": return current
    for token in pointer.split("/")[1:]:
        token = token.replace("~1", "/").replace("~0", "~")
        try:
            current = current[int(token)] if isinstance(current, list) else current[token]
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise LocatorResolutionError(f"JSON Pointer does not resolve: {pointer}") from exc
    return current


def resolve_locator(content: bytes, locator_type: LocatorType | str, locator: dict[str, Any]) -> bytes:
    try: kind = LocatorType(locator_type)
    except ValueError as exc: raise LocatorResolutionError(f"unsupported locator type: {locator_type}") from exc

    try:
        if kind is LocatorType.JSON_POINTER:
            model=JsonPointerLocator.model_validate(locator)
            value=_json_pointer(json.loads(content.decode("utf-8")),model.pointer)
            return json.dumps(value,sort_keys=True,separators=(",",":"),ensure_ascii=False).encode()
        if kind in (LocatorType.CSV_ROW,LocatorType.CSV_CELL):
            rows=list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
            if kind is LocatorType.CSV_ROW:
                model=CsvRowLocator.model_validate(locator)
                if model.row>len(rows): raise LocatorResolutionError("CSV row is outside the artifact")
                return json.dumps(rows[model.row-1],ensure_ascii=False,separators=(",",":")).encode()
            model=CsvCellLocator.model_validate(locator)
            if model.row>len(rows): raise LocatorResolutionError("CSV row is outside the artifact")
            idx=model.column if isinstance(model.column,int) else (rows[0].index(model.column) if rows else -1)
            if idx<0 or idx>=len(rows[model.row-1]): raise LocatorResolutionError("CSV column is outside the artifact")
            return rows[model.row-1][idx].encode()
        if kind is LocatorType.TEXT_SPAN:
            model=TextSpanLocator.model_validate(locator)
            if model.byte_end>len(content): raise LocatorResolutionError("text span is outside the artifact")
            return content[model.byte_start:model.byte_end]
        if kind is LocatorType.HTML_DOM_SPAN:
            model=HtmlDomSpanLocator.model_validate(locator)
            node=BeautifulSoup(content,"html.parser").select_one(model.selector)
            if node is None: raise LocatorResolutionError("HTML selector does not resolve")
            text=node.get_text()
            start=model.text_start or 0; end=model.text_end if model.text_end is not None else len(text)
            if end>len(text) or end<=start: raise LocatorResolutionError("HTML text span is outside the selected node")
            return text[start:end].encode()
        if kind is LocatorType.ARCHIVE_MEMBER:
            model=ArchiveMemberLocator.model_validate(locator)
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                try: return archive.read(model.member_path)
                except KeyError as exc: raise LocatorResolutionError("archive member does not exist") from exc
        if kind is LocatorType.IMAGE_REGION:
            model=ImageRegionLocator.model_validate(locator)
            try:
                from PIL import Image
                image=Image.open(io.BytesIO(content)); x2=model.x+model.width; y2=model.y+model.height
                if x2>image.width or y2>image.height: raise LocatorResolutionError("image region is outside the image")
                output=io.BytesIO(); image.crop((model.x,model.y,x2,y2)).save(output,format="PNG"); return output.getvalue()
            except LocatorResolutionError: raise
            except Exception as exc: raise LocatorResolutionError("image region cannot be resolved") from exc
        if kind is LocatorType.MEDIA_TIME_RANGE:
            model=MediaTimeRangeLocator.model_validate(locator)
            from mutagen import File as MutagenFile
            media=MutagenFile(io.BytesIO(content))
            duration_ms=int(media.info.length*1000) if media and getattr(media,"info",None) and getattr(media.info,"length",None) else 0
            if duration_ms<=0 and content[:4]==b"RIFF" and content[8:12]==b"WAVE":
                import wave
                with wave.open(io.BytesIO(content),"rb") as wav:
                    duration_ms=int(wav.getnframes()/wav.getframerate()*1000)
            if duration_ms<=0 or model.end_ms>duration_ms:
                raise LocatorResolutionError("media time range is outside the decodable artifact")
            # Byte-accurate slicing is codec-specific; this proof binds the
            # verified time range to the immutable content hash and duration.
            return hashlib.sha256(content).digest()+f":{model.start_ms}:{model.end_ms}".encode()
    except LocatorResolutionError: raise
    except Exception as exc: raise LocatorResolutionError(f"invalid {kind.value} locator") from exc
    raise LocatorResolutionError(f"unsupported locator type: {kind.value}")


def verify_locator(content: bytes, locator_type: LocatorType | str, locator: dict[str, Any], expected_hash: str) -> bool:
    resolved=resolve_locator(content,locator_type,locator)
    return hashlib.sha256(resolved).hexdigest()==expected_hash.lower()
