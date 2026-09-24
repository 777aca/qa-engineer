import json
from unittest.mock import Mock

import pytest
import api_smoke
from data_contract import DataError


@pytest.mark.parametrize("cases", [[], [{"path": "https://outside.test"}], [{"path": "/ok", "timeout": -1}], [{"path": "/ok", "expect_json": []}], [{"path": "/ok", "timeout": float("inf")}], [{"path": "/ok", "expect_status": "200"}]])
def test_invalid_api_plan_rejected(tmp_path, cases):
    file = tmp_path / "api.json"
    file.write_text(json.dumps({"base_url": "http://localhost", "cases": cases}), encoding="utf-8")
    with pytest.raises(DataError):
        api_smoke.load_config(str(file))


def test_missing_auth_is_not_sent_as_anonymous(monkeypatch):
    monkeypatch.delenv("QA_FAKE_TOKEN", raising=False)
    with pytest.raises(DataError):
        api_smoke.build_headers({"type": "bearer", "token_env": "QA_FAKE_TOKEN"})


def test_http_success_still_requires_business_assertion(monkeypatch):
    response = Mock(status_code=200)
    response.json.return_value = {"code": 1}
    monkeypatch.setattr(api_smoke.requests, "request", Mock(return_value=response))
    result = api_smoke.run_case("http://localhost", {}, 5, {"path": "/test", "expect_json": {"code": 0}})
    assert not result.passed
