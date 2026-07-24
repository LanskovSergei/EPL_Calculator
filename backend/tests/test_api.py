"""
Тесты HTTP-слоя (эндпоинты, CORS, обработка ошибок валидации) через
FastAPI TestClient — в отличие от test_calc.py, здесь проверяется весь
путь запроса: маршрутизация, сериализация JSON, коды ответов.
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def valid_payload() -> dict:
    return {
        "марка": "Hyundai",
        "модель": "Porter 2",
        "типТС": "грузовой",
        "видТоплива": "дизель",
        "объёмБака": 100,
        "старше10лет": False,
        "прицепГруз": False,
        "спецтехника": False,
        "периодС": "2025-06-01",
        "периодПо": "2025-06-30",
        "видСообщения": "городское",
        "одометрНаНачало": 32000,
        "остатокНаНачало": 15,
        "водители": [{"фио": "Иванов И.И.", "дни": ["2025-06-02", "2025-06-04"]}],
        "заправки": [{"дата": "2025-06-01", "время": "08:00", "объём": 40}],
    }


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_calculate_success():
    resp = client.post("/api/calculate", json=valid_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["листы"]) == 2
    assert body["предупреждения"] == []
    assert "маршрут" in body["листы"][0]


def test_calculate_validation_error_returns_422_with_readable_detail():
    payload = valid_payload()
    payload["водители"] = []
    resp = client.post("/api/calculate", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    assert isinstance(body["detail"], list)
    assert any("водител" in msg for msg in body["detail"])


def test_calculate_missing_required_field_returns_422():
    payload = valid_payload()
    del payload["периодС"]
    resp = client.post("/api/calculate", json=payload)
    assert resp.status_code == 422


def test_calculate_with_route_fields():
    payload = valid_payload()
    payload["адресСтоянки"] = "г. Москва, ул. Ленина, 1"
    payload["заправки"][0]["адрес"] = "г. Москва, АЗС Лукойл"
    resp = client.post("/api/calculate", json=payload)
    assert resp.status_code == 200
    маршрут = resp.json()["листы"][0]["маршрут"]
    assert маршрут[0] == "г. Москва, ул. Ленина, 1"
    assert any("Лукойл" in stop for stop in маршрут)


def test_cors_allows_configured_origin():
    resp = client.post(
        "/api/calculate",
        json=valid_payload(),
        headers={"Origin": "http://localhost:5173"},
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"


@pytest.mark.parametrize("field", ["марка", "модель"])
def test_calculate_accepts_empty_strings_for_optional_text_fields(field):
    """Марка/модель — не обязательны по ТЗ (справочные поля)."""
    payload = valid_payload()
    payload[field] = ""
    resp = client.post("/api/calculate", json=payload)
    assert resp.status_code == 200
