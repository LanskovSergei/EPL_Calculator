"""Тесты app/act.py и app/integration_1c.py — сборка Акта и синхронизация 1С на моках."""
from datetime import date

import httpx
import pytest

from app import integration_1c as onec
from app.act import build_act
from app.calc import calculate
from app.schemas import (
    Водитель,
    Заправка,
    ВидСообщения,
    ВидТоплива,
    ТипТС,
    ВходныеДанные,
    ЗапросСинхронизации1С,
    ДанныеОрганизации,
    ДанныеТСДокумент,
)


def make_calc_input(**overrides) -> ВходныеДанные:
    base = dict(
        марка="Hyundai",
        модель="Porter 2",
        типТС=ТипТС.грузовой,
        видТоплива=ВидТоплива.дизель,
        объёмБака=100,
        старше10лет=False,
        прицепГруз=False,
        спецтехника=False,
        периодС=date(2025, 6, 1),
        периодПо=date(2025, 6, 30),
        видСообщения=ВидСообщения.городское,
        одометрНаНачало=32000,
        остатокНаНачало=15,
        водители=[Водитель(фио="Иванов И.И.", дни=[date(2025, 6, 2), date(2025, 6, 4)])],
        заправки=[Заправка(дата=date(2025, 6, 1), время="08:00", объём=40)],
    )
    base.update(overrides)
    return ВходныеДанные(**base)


def make_sync_request(**overrides) -> ЗапросСинхронизации1С:
    base = dict(
        расчёт=make_calc_input(),
        организация=ДанныеОрганизации(наименование='ООО "Дубрава"', инн="7701234567"),
        тс=ДанныеТСДокумент(тип="грузовой фургон", госномер="А900ТТ178"),
    )
    base.update(overrides)
    return ЗапросСинхронизации1С(**base)


# ------- build_act -------


def test_build_act_aggregates_totals():
    req = make_sync_request()
    result = calculate(req.расчёт)
    act = build_act(req, result)

    assert act.госномер == "А900ТТ178"
    assert len(act.строки) == len(result.листы)
    assert act.итогоПробегКм == pytest.approx(sum(л.пробег for л in result.листы), abs=0.01)
    assert act.итогоРасходФактЛ == pytest.approx(sum(л.расходФакт for л in result.листы), abs=0.01)
    assert act.итогоЭкономияЛ == pytest.approx(
        act.итогоРасходНормаЛ - act.итогоРасходФактЛ, abs=0.01
    )


def test_build_act_line_matches_list():
    req = make_sync_request()
    result = calculate(req.расчёт)
    act = build_act(req, result)

    first_line = act.строки[0]
    first_list = result.листы[0]
    assert first_line.номерПЛ == first_list.номер
    assert first_line.водитель == first_list.водитель
    assert first_line.пробег == first_list.пробег


# ------- integration_1c: конфигурация -------


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    for var in ["ONE_C_BASE_URL", "ONE_C_ENTITY", "ONE_C_USERNAME", "ONE_C_PASSWORD"]:
        monkeypatch.delenv(var, raising=False)
    yield


def _mock_client(json_body: dict, status_code: int = 200) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json=json_body)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_not_configured_without_base_url():
    assert onec.is_configured() is False
    req = make_sync_request()
    result = calculate(req.расчёт)
    act = build_act(req, result)
    assert onec.sync_act(act) is None


def test_act_to_1c_payload_shape():
    req = make_sync_request()
    result = calculate(req.расчёт)
    act = build_act(req, result)
    payload = onec.act_to_1c_payload(act)

    assert payload["ТС_ГосНомер"] == "А900ТТ178"
    assert payload["Организация"] == 'ООО "Дубрава"'
    assert isinstance(payload["ТабличнаяЧасть"], list)
    assert len(payload["ТабличнаяЧасть"]) == len(act.строки)
    assert payload["ТабличнаяЧасть"][0]["НомерПЛ"] == act.строки[0].номерПЛ


def test_sync_act_success(monkeypatch):
    monkeypatch.setenv("ONE_C_BASE_URL", "https://1c.example.local/odata/standard.odata")
    onec.set_client(_mock_client({"Ref_Key": "abc-123"}))

    req = make_sync_request()
    result = calculate(req.расчёт)
    act = build_act(req, result)

    response = onec.sync_act(act)
    assert response is not None
    assert response.успех is True
    assert response.идДокумента == "abc-123"


def test_sync_act_http_error_raises(monkeypatch):
    monkeypatch.setenv("ONE_C_BASE_URL", "https://1c.example.local/odata/standard.odata")
    onec.set_client(_mock_client({"error": "unauthorized"}, status_code=401))

    req = make_sync_request()
    result = calculate(req.расчёт)
    act = build_act(req, result)

    with pytest.raises(onec.OneCIntegrationError):
        onec.sync_act(act)
