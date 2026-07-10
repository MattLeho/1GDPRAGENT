import hashlib
import io
import json
import zipfile
import wave

import pytest

from evidence.locators import LocatorResolutionError, resolve_locator, verify_locator
from extraction.grounded_extractor import GroundedExtractor


def test_json_csv_text_html_and_archive_locators_resolve():
    assert resolve_locator(b'{"profile":{"ageSegment":"25-34"}}',"json_pointer",{"pointer":"/profile/ageSegment"})==b'"25-34"'
    csv_bytes=b"name,deviceId\nAlice,123\nBob,456\n"
    assert resolve_locator(csv_bytes,"csv_cell",{"row":2,"column":"deviceId"})==b"123"
    text=b"prefix exact quoted evidence suffix"
    assert resolve_locator(text,"text_span",{"byte_start":7,"byte_end":28})==b"exact quoted evidence"
    html=b"<main><p>controller assigned category</p></main>"
    assert resolve_locator(html,"html_dom_span",{"selector":"main p","text_start":0,"text_end":19})==b"controller assigned"
    archive=io.BytesIO()
    with zipfile.ZipFile(archive,"w") as bundle: bundle.writestr("export/data.json",b"{}")
    assert resolve_locator(archive.getvalue(),"archive_member",{"member_path":"export/data.json"})==b"{}"


def test_invalid_json_pointer_is_rejected():
    with pytest.raises(LocatorResolutionError):
        resolve_locator(b'{"profile":{}}',"json_pointer",{"pointer":"/profile/missing"})


def test_incorrect_exact_text_span_is_not_verified():
    content=b"the source says alpha, not beta"
    expected=hashlib.sha256(b"beta").hexdigest()
    assert not verify_locator(content,"text_span",{"byte_start":16,"byte_end":21},expected)


def test_locator_shapes_are_strict():
    with pytest.raises(LocatorResolutionError):
        resolve_locator(b"a,b\n1,2", "csv_cell", {"row":0,"column":"a"})


def test_media_time_range_is_checked_against_decodable_duration():
    audio=io.BytesIO()
    with wave.open(audio,"wb") as wav:
        wav.setnchannels(1);wav.setsampwidth(2);wav.setframerate(8000);wav.writeframes(b"\0\0"*8000)
    assert resolve_locator(audio.getvalue(),"media_time_range",{"start_ms":100,"end_ms":900})
    with pytest.raises(LocatorResolutionError):
        resolve_locator(audio.getvalue(),"media_time_range",{"start_ms":900,"end_ms":1500})


def test_image_region_must_fit_inside_decodable_image():
    from PIL import Image
    image=io.BytesIO();Image.new("RGB",(10,10),"white").save(image,format="PNG")
    assert resolve_locator(image.getvalue(),"image_region",{"x":1,"y":1,"width":5,"height":5})
    with pytest.raises(LocatorResolutionError):
        resolve_locator(image.getvalue(),"image_region",{"x":9,"y":9,"width":5,"height":5})


@pytest.mark.asyncio
async def test_gemini_estimated_offset_cannot_substitute_for_missing_exact_quote():
    class FakeClient:
        async def extract_json(self,prompt):
            return [{"class":"personal_data","text":"fabricated quote","start_offset":4,"attributes":{}}]
    extractor=GroundedExtractor(FakeClient())
    entities=await extractor._extract_with_gemini("the real source text",extractor._default_gdpr_task(),"fixture")
    assert entities==[]
