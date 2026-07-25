"""
Тесты app/receipt_validation.py — парсинг QR и обращение к сервису
проверки чеков на моках httpx. Реальный токен ОФД не нужен.
"""
from datetime import datetime

import httpx
import pytest

from app import receipt_validation as rv


@pytest.fixture(autouse=True)
def _reset_state(monkeypatch):
    monkeypatch.delenv("OFD_CHECK_TOKEN", raising=False)
    rv.validate_receipt.cache_clear()
    yield
    rv.validate_receipt.cache_clear()


def _mock_client(json_body: dict, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_body)

    return httpx.Client(transport=httpx.MockTransport(handler))


# ------- parse_qr -------


def test_parse_qr_standard_format():
    qr = "t=20250601T0800&s=1234.56&fn=9287440300123456&i=45678&fp=1234567890&n=1"
    req = rv.parse_qr(qr)
    assert req.дата == datetime(2025, 6, 1, 8, 0)
    assert req.сумма == pytest.approx(1234.56)
    assert req.фн == "9287440300123456"
    assert req.фд == "45678"
    assert req.фп == "1234567890"
    assert req.типОперации == 1


def test_parse_qr_with_seconds():
    qr = "t=20250601T080030&s=100&fn=1&i=2&fp=3"
    req = rv.parse_qr(qr)
    assert req.дата == datetime(2025, 6, 1, 8, 0, 30)


def test_parse_qr_strips_leading_question_mark():
    qr = "?t=20250601T0800&s=100&fn=1&i=2&fp=3"
    req = rv.parse_qr(qr)
    assert req.фн == "1"


def test_parse_qr_missing_field_raises():
    with pytest.raises(rv.ReceiptParseError):
        rv.parse_qr("t=20250601T0800&s=100&fn=1&i=2")  # нет fp


def test_parse_qr_bad_date_raises():
    with pytest.raises(rv.ReceiptParseError):
        rv.parse_qr("t=not-a-date&s=100&fn=1&i=2&fp=3")


def test_parse_qr_bad_amount_raises():
    with pytest.raises(rv.ReceiptParseError):
        rv.parse_qr("t=20250601T0800&s=not-a-number&fn=1&i=2&fp=3")


# ------- is_configured / validate_receipt -------


def _sample_req() -> rv.РеквизитыЧека:
    return rv.parse_qr("t=20250601T0800&s=1234.56&fn=9287440300123456&i=45678&fp=1234567890&n=1")


def test_not_configured_without_token():
    assert rv.is_configured() is False
    assert rv.validate_receipt(_sample_req()) is None


def test_validate_receipt_found(monkeypatch):
    monkeypatch.setenv("OFD_CHECK_TOKEN", "test-token")
    rv.set_client(_mock_client({"code": 1, "data": {"items": []}}))

    result = rv.validate_receipt(_sample_req())
    assert result is not None
    assert result.найден is True


def test_validate_receipt_not_found(monkeypatch):
    monkeypatch.setenv("OFD_CHECK_TOKEN", "test-token")
    rv.set_client(_mock_client({"code": 0}))

    result = rv.validate_receipt(_sample_req())
    assert result is not None
    assert result.найден is False


def test_validate_receipt_http_error_raises(monkeypatch):
    monkeypatch.setenv("OFD_CHECK_TOKEN", "test-token")
    rv.set_client(_mock_client({"error": "forbidden"}, status_code=403))

    with pytest.raises(rv.ReceiptValidationError):
        rv.validate_receipt(_sample_req())


# ------- extract_fuel_volume_liters -------


def test_extract_fuel_volume_from_items():
    payload = {
        "items": [
            {"name": "АИ-95", "quantity": 30.5},
            {"name": "Кофе", "quantity": 1},
        ]
    }
    assert rv.extract_fuel_volume_liters(payload) == pytest.approx(30.5)


def test_extract_fuel_volume_none_when_no_fuel_item():
    payload = {"items": [{"name": "Кофе", "quantity": 1}]}
    assert rv.extract_fuel_volume_liters(payload) is None


def test_extract_fuel_volume_none_when_no_items():
    assert rv.extract_fuel_volume_liters({}) is None
