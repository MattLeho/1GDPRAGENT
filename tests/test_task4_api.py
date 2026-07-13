from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi import FastAPI

from api.insights import insight_request,router
from insights.models import PeriodGranularity, TemporalMode


NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_api_query_contract_supports_period_point_and_compare():
    period = insight_request("subject", TemporalMode.PERIOD, PeriodGranularity.MONTH, NOW, NOW.replace(month=2), None, None, None)
    assert period.period.mode is TemporalMode.PERIOD and period.comparison is None
    point = insight_request("subject", TemporalMode.POINT_IN_TIME, PeriodGranularity.DAY, None, None, NOW, None, None)
    assert point.period.point_at == NOW
    compare = insight_request(
        "subject",TemporalMode.COMPARE,PeriodGranularity.MONTH,NOW.replace(month=2),NOW.replace(month=3),None,NOW,NOW.replace(month=2),
    )
    assert compare.comparison and compare.comparison.current == compare.period


def test_api_query_contract_rejects_incomplete_compare():
    with pytest.raises(HTTPException) as error:
        insight_request("subject",TemporalMode.COMPARE,PeriodGranularity.MONTH,NOW,NOW.replace(month=2),None,None,None)
    assert error.value.status_code == 422


def test_personal_insights_openapi_has_typed_response_contracts():
    app=FastAPI();app.include_router(router)
    schema=app.openapi()
    expected=("overview","interests","search","ai-conversations","places","changes","context")
    for module in expected:
        response=schema["paths"][f"/insights/{module}"]["get"]["responses"]["200"]
        assert "schema" in response["content"]["application/json"]
    assert schema["paths"]["/insights/evidence/{insight_id}"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
