import json
import sqlite3
import io
import gzip
import tarfile
import zipfile
from pathlib import Path

from evidence.locators import resolve_locator


def test_json_record_text_and_xml_locators_resolve_exact_units():
    assert resolve_locator(b'{"x":1}\n{"x":2}\n',"json_record",{"record":1,"pointer":"/x"})==b"2"
    assert resolve_locator(b"alpha\nbeta\n","text_line",{"line":2})==b"beta"
    assert resolve_locator(b"abcdef","text_byte_span",{"byte_start":1,"byte_end":4})==b"bcd"
    assert resolve_locator(b"<root><item code='x'>value</item></root>","xml_element",{"xpath":"./item","attribute":"code"})==b"x"


def test_email_calendar_vcard_and_subtitle_locators_resolve():
    eml=(b"From: sender@example.test\r\nSubject: Test\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nBody")
    assert resolve_locator(eml,"email_header",{"message":0,"header":"Subject","occurrence":0})==b"Test"
    assert resolve_locator(eml,"email_mime_part",{"message":0,"part":"0"})==b"Body"
    ics=b"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:event-1\r\nSUMMARY:Review\r\nDTSTART:20250101T120000Z\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    assert resolve_locator(ics,"calendar_component",{"component":"VEVENT","uid":"event-1","property":"SUMMARY"})==b"Review"
    vcf=b"BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Example Person\r\nEMAIL:test@example.test\r\nEND:VCARD\r\n"
    assert resolve_locator(vcf,"vcard_property",{"card":0,"property":"EMAIL","occurrence":0})==b"test@example.test"
    srt=b"1\n00:00:00,000 --> 00:00:01,000\nHello\n\n2\n00:00:01,000 --> 00:00:02,000\nWorld\n"
    assert b"Hello" in resolve_locator(srt,"subtitle_cue",{"cue":1,"start_ms":0,"end_ms":1000})


def test_geospatial_and_sqlite_locators_resolve(tmp_path):
    geo=json.dumps({"type":"FeatureCollection","features":[{"type":"Feature","id":"a","properties":{"name":"Place"},"geometry":None}]}).encode()
    assert json.loads(resolve_locator(geo,"geospatial_feature",{"feature":"a"}))["properties"]["name"]=="Place"
    database=tmp_path/"fixture.sqlite"
    connection=sqlite3.connect(database); connection.execute("CREATE TABLE events(id INTEGER PRIMARY KEY,value TEXT)"); connection.execute("INSERT INTO events VALUES(1,'x')"); connection.commit(); connection.close()
    content=database.read_bytes()
    assert json.loads(resolve_locator(content,"database_cell",{"table":"events","row_key":{"id":1},"column":"value"}))=="x"


def test_archive_member_locator_resolves_duplicates_nested_tar_and_gzip():
    outer=io.BytesIO(); inner=io.BytesIO()
    with zipfile.ZipFile(inner,"w") as archive: archive.writestr("record.json",b"{}")
    with zipfile.ZipFile(outer,"w") as archive:
        archive.writestr("same.txt",b"one"); archive.writestr("same.txt",b"two"); archive.writestr("inner.zip",inner.getvalue())
    assert resolve_locator(outer.getvalue(),"archive_member",{"member_path":"same.txt","member_ordinal":1})==b"two"
    assert resolve_locator(outer.getvalue(),"archive_member",{"member_path":"record.json","nested_member_chain":["inner.zip"]})==b"{}"
    tar_buffer=io.BytesIO()
    with tarfile.open(fileobj=tar_buffer,mode="w") as archive:
        info=tarfile.TarInfo("a.txt"); info.size=1; archive.addfile(info,io.BytesIO(b"a"))
    assert resolve_locator(tar_buffer.getvalue(),"archive_member",{"member_path":"a.txt","member_ordinal":0})==b"a"
    compressed=gzip.compress(b"payload")
    assert resolve_locator(compressed,"archive_member",{"member_path":"data"})==b"payload"
