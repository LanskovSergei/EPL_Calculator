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


def form3_payload() -> dict:
    return {
        "расчёт": {**valid_payload(), "типТС": "легковой"},
        "организация": {"наименование": "ООО Ромашка", "инн": "7701234567"},
        "тс": {"тип": "легковой", "госномер": "А123ВС777"},
        "водитель": {"фио": "Иванов И.И.", "удостоверение": "77 АБ 123456"},
    }


def test_form3_excel_endpoint_returns_xlsx():
    resp = client.post("/api/form3/excel", json=form3_payload())
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(resp.content) > 0


def test_form3_pdf_endpoint_returns_pdf():
    resp = client.post("/api/form3/pdf", json=form3_payload())
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_form3_rejects_грузовой_via_endpoint():
    payload = form3_payload()
    payload["расчёт"]["типТС"] = "грузовой"
    resp = client.post("/api/form3/excel", json=payload)
    assert resp.status_code == 422


def form4c_payload() -> dict:
    return {
        "расчёт": {**valid_payload(), "типТС": "грузовой"},
        "организация": {"наименование": "ООО Дубрава", "инн": "7701234567"},
        "тс": {"тип": "грузовой фургон", "госномер": "А900ТТ178"},
        "водитель": {"фио": "Иванов И.И.", "удостоверение": "78 АБ 654321"},
        "прицепы": [{"маркаМодель": "СЗАП 8357", "госномер": "АК123178"}],
        "ездки": [
            {
                "пунктПогрузки": "г. Санкт-Петербург, ул. Заводская, 12",
                "пунктРазгрузки": "г. Санкт-Петербург, ул. Весенняя, 58",
                "наименованиеГруза": "Мебель",
                "номерТТН": "9332",
            }
        ],
    }


def test_form4c_excel_endpoint_returns_xlsx():
    resp = client.post("/api/form4c/excel", json=form4c_payload())
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )


def test_form4c_pdf_endpoint_returns_pdf():
    resp = client.post("/api/form4c/pdf", json=form4c_payload())
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_form4c_rejects_легковой_via_endpoint():
    payload = form4c_payload()
    payload["расчёт"]["типТС"] = "легковой"
    resp = client.post("/api/form4c/excel", json=payload)
    assert resp.status_code == 422


def sync_1c_payload() -> dict:
    return {
        "расчёт": {**valid_payload(), "типТС": "грузовой"},
        "организация": {"наименование": "ООО Дубрава", "инн": "7701234567"},
        "тс": {"тип": "грузовой фургон", "госномер": "А900ТТ178"},
    }


def test_act_endpoint_returns_summary():
    resp = client.post("/api/act", json=sync_1c_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["госномер"] == "А900ТТ178"
    assert len(body["строки"]) >= 1


def test_1c_sync_endpoint_without_config_returns_not_synced(monkeypatch):
    monkeypatch.delenv("ONE_C_BASE_URL", raising=False)
    resp = client.post("/api/1c/sync", json=sync_1c_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert body["synced"] is False
    assert "акт" in body
