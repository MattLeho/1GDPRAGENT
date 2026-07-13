import asyncio

from api.bulk_ingestion import support_catalogue


def test_support_api_is_machine_readable_and_surfaces_unsupported():
    payload=asyncio.run(support_catalogue())
    formats={item["format_key"]:item for item in payload["formats"]}
    assert payload["registry_version"]=="task3a-1"
    assert formats["json"]["status"]=="SUPPORTED_DETERMINISTIC"
    assert formats["unknown_binary"]["status"]=="UNSUPPORTED"
    assert formats["pdf"]["task_routes"]==["document.ocr"]
