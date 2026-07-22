"""
Юнит-тесты для backend/app/calc.py (неделя 2 плана: «Тестирование и отладка формул»).

Запуск:
    cd backend
    pytest -v
"""
from datetime import date

import pytest
from pydantic import ValidationError

from app.calc import (
    MIN_CLOSING_FUEL,
    MAX_DAILY_KM,
    build_shifts,
    calculate,
    compute_consumption,
)
from app.schemas import (
    Водитель,
    Заправка,
    ВидСообщения,
    ВидТоплива,
    ТипТС,
    ВходныеДанные,
)


def make_input(**overrides) -> ВходныеДанные:
    """Базовый валидный набор входных данных с возможностью переопределить поля."""
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
        водители=[
            Водитель(фио="Иванов И.И.", дни=[date(2025, 6, 2), date(2025, 6, 4)]),
        ],
        заправки=[Заправка(дата=date(2025, 6, 1), время="08:00", объём=40)],
    )
    base.update(overrides)
    return ВходныеДанные(**base)


# ------- compute_consumption: коэффициенты -------


def test_consumption_no_extra_coeff_in_summer():
    inp = make_input(периодС=date(2025, 6, 1))  # июнь — не зима
    res = compute_consumption(inp, date(2025, 6, 1))
    assert not any(a.name == "Зима" for a in res.applied)


def _period_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end_day = 28  # безопасно для любого месяца, включая февраль
    return start, date(year, month, end_day)


def test_consumption_winter_coefficient():
    start, end = _period_bounds(2025, 1)
    inp = make_input(
        периодС=start,
        периодПо=end,
        водители=[Водитель(фио="А", дни=[start])],
        заправки=[Заправка(дата=start, время="08:00", объём=40)],
    )
    res = compute_consumption(inp, start)
    winter = next(a for a in res.applied if a.name == "Зима")
    assert winter.value == pytest.approx(0.10)


@pytest.mark.parametrize("month", [11, 12, 1, 2, 3])
def test_consumption_winter_months_range(month):
    start, end = _period_bounds(2025, month)
    inp = make_input(
        периодС=start,
        периодПо=end,
        водители=[Водитель(фио="А", дни=[start])],
        заправки=[Заправка(дата=start, время="08:00", объём=40)],
    )
    res = compute_consumption(inp, start)
    assert any(a.name == "Зима" for a in res.applied)


@pytest.mark.parametrize("month", [4, 5, 6, 7, 8, 9, 10])
def test_consumption_summer_months_range(month):
    start, end = _period_bounds(2025, month)
    inp = make_input(
        периодС=start,
        периодПо=end,
        водители=[Водитель(фио="А", дни=[start])],
        заправки=[Заправка(дата=start, время="08:00", объём=40)],
    )
    res = compute_consumption(inp, start)
    assert not any(a.name == "Зима" for a in res.applied)


def test_consumption_age_coefficient():
    inp = make_input(старше10лет=True)
    res = compute_consumption(inp, inp.периодС)
    coeff = next(a for a in res.applied if "Возраст" in a.name)
    assert coeff.value == pytest.approx(0.05)


def test_consumption_trailer_coefficient():
    inp = make_input(прицепГруз=True)
    res = compute_consumption(inp, inp.периодС)
    coeff = next(a for a in res.applied if "Прицеп" in a.name)
    assert coeff.value == pytest.approx(0.10)


def test_consumption_intercity_no_коэффициент_сообщения():
    """Междугородное/международное — коэффициент вида сообщения = 0 по ТЗ."""
    inp = make_input(
        видСообщения=ВидСообщения.междугородное,
        срокРейсаДней=3,
    )
    res = compute_consumption(inp, inp.периодС)
    assert not any("Вид сообщения" in a.name for a in res.applied)


def test_consumption_stacks_multiple_coefficients():
    inp = make_input(старше10лет=True, прицепГруз=True, периодС=date(2025, 1, 1))
    res = compute_consumption(inp, date(2025, 1, 1))
    names = {a.name for a in res.applied}
    assert {"Зима", "Возраст > 10 лет", "Прицеп/груз", "Вид сообщения: городское"} <= names
    # база 9 (дизель) * (1 + 0.10 + 0.05 + 0.10 + 0.10) = 9 * 1.35 = 12.15
    assert res.effective == pytest.approx(12.15, abs=0.01)


def test_consumption_manual_base_overrides_default():
    inp = make_input(среднийРасход=20)
    res = compute_consumption(inp, inp.периодС)
    assert res.base == 20


def test_consumption_спецтехника_ignores_all_coefficients():
    inp = make_input(спецтехника=True, среднийРасход=35, старше10лет=True, прицепГруз=True)
    res = compute_consumption(inp, date(2025, 1, 1))  # даже зимой
    assert res.applied == []
    assert res.effective == 35


# ------- Валидация схемы -------


def test_спецтехника_requires_manual_consumption():
    with pytest.raises(ValidationError):
        make_input(спецтехника=True, среднийРасход=None)


def test_period_end_before_start_rejected():
    with pytest.raises(ValidationError):
        make_input(периодС=date(2025, 6, 30), периодПо=date(2025, 6, 1))


def test_no_drivers_rejected():
    with pytest.raises(ValidationError):
        make_input(водители=[])


def test_intercity_requires_trip_length():
    with pytest.raises(ValidationError):
        make_input(видСообщения=ВидСообщения.междугородное, срокРейсаДней=None)


def test_refuel_outside_period_rejected():
    with pytest.raises(ValidationError):
        make_input(заправки=[Заправка(дата=date(2025, 7, 15), объём=40)])


# ------- build_shifts -------


def test_build_shifts_one_per_working_day():
    inp = make_input(
        водители=[Водитель(фио="А", дни=[date(2025, 6, 2), date(2025, 6, 4)])]
    )
    shifts = build_shifts(inp)
    assert [s.start for s in shifts] == [date(2025, 6, 2), date(2025, 6, 4)]
    assert all(s.days == 1 for s in shifts)


def test_build_shifts_round_robin_between_drivers():
    inp = make_input(
        водители=[
            Водитель(фио="Иванов", дни=[date(2025, 6, 2), date(2025, 6, 3)]),
            Водитель(фио="Петров", дни=[date(2025, 6, 2), date(2025, 6, 3)]),
        ]
    )
    shifts = build_shifts(inp)
    drivers = [s.driver for s in shifts]
    # оба дня доступны обоим водителям -> должны чередоваться, а не всегда один
    assert drivers[0] != drivers[1]


def test_build_shifts_multiday_trip_groups_days():
    inp = make_input(
        видСообщения=ВидСообщения.междугородное,
        срокРейсаДней=3,
        водители=[
            Водитель(
                фио="А",
                дни=[date(2025, 6, 2), date(2025, 6, 3), date(2025, 6, 4)],
            )
        ],
    )
    shifts = build_shifts(inp)
    assert len(shifts) == 1
    assert shifts[0].days == 3
    assert shifts[0].start == date(2025, 6, 2)


# ------- calculate: интеграционные сценарии -------


def test_calculate_basic_scenario_produces_lists():
    inp = make_input()
    res = calculate(inp)
    assert len(res.листы) == 2
    assert res.листы[0].номер == 1
    assert res.листы[0].остатокЗакрытие >= MIN_CLOSING_FUEL - 0.01


def test_calculate_no_working_days_warns_and_returns_empty():
    inp = make_input(водители=[Водитель(фио="А", дни=[])])
    res = calculate(inp)
    assert res.листы == []
    assert any("рабочего дня" in w for w in res.предупреждения)


def test_calculate_respects_daily_mileage_limit_truck():
    """Много топлива на 1 смену — пробег не должен превышать 250 км (грузовой)."""
    inp = make_input(
        типТС=ТипТС.грузовой,
        остатокНаНачало=90,
        объёмБака=100,
        заправки=[],
        водители=[Водитель(фио="А", дни=[date(2025, 6, 2)])],
    )
    res = calculate(inp)
    assert len(res.листы) == 1
    assert res.листы[0].пробег <= MAX_DAILY_KM[ТипТС.грузовой] + 0.5


def test_calculate_respects_daily_mileage_limit_car():
    inp = make_input(
        типТС=ТипТС.легковой,
        видТоплива=ВидТоплива.бензин,
        остатокНаНачало=90,
        объёмБака=100,
        заправки=[],
        водители=[Водитель(фио="А", дни=[date(2025, 6, 2)])],
    )
    res = calculate(inp)
    assert res.листы[0].пробег <= MAX_DAILY_KM[ТипТС.легковой] + 0.5


def test_calculate_closing_fuel_never_below_minimum():
    inp = make_input()
    res = calculate(inp)
    for пл in res.листы:
        assert пл.остатокЗакрытие >= MIN_CLOSING_FUEL - 0.01


def test_calculate_refuel_capped_by_tank_capacity_warns():
    inp = make_input(
        объёмБака=50,
        остатокНаНачало=40,
        заправки=[Заправка(дата=date(2025, 6, 1), время="08:00", объём=30)],
    )
    res = calculate(inp)
    assert any("объём бака" in w for w in res.предупреждения)


def test_calculate_odometer_defaults_to_2500_when_unknown():
    inp = make_input(одометрНаНачало=None)
    res = calculate(inp)
    assert res.листы[0].одометрВыдача == 2500.0
    assert any("2500" in w for w in res.предупреждения)


def test_calculate_odometer_progresses_between_lists():
    inp = make_input()
    res = calculate(inp)
    assert res.листы[1].одометрВыдача == res.листы[0].одометрЗакрытие


def test_calculate_multiday_trip_single_list_covers_all_days():
    inp = make_input(
        видСообщения=ВидСообщения.междугородное,
        срокРейсаДней=3,
        остатокНаНачало=200,
        объёмБака=300,
        заправки=[],
        водители=[
            Водитель(
                фио="Дальнобойщик",
                дни=[date(2025, 6, 2), date(2025, 6, 3), date(2025, 6, 4)],
            )
        ],
    )
    res = calculate(inp)
    assert len(res.листы) == 1
    # суточный лимит * дни рейса
    assert res.листы[0].пробег <= MAX_DAILY_KM[ТипТС.грузовой] * 3 + 0.5


# ------- Маршрут (Шаг 2.1, MVP-алгоритм) -------


def test_route_includes_stanция_and_azs_addresses_in_order():
    inp = make_input(
        адресСтоянки="г. Москва, ул. Ленина, 1",
        водители=[Водитель(фио="А", дни=[date(2025, 6, 2)])],
        заправки=[
            Заправка(
                дата=date(2025, 6, 1),
                время="08:00",
                объём=40,
                адрес="г. Москва, АЗС Лукойл, Кутузовский пр-т",
            )
        ],
    )
    res = calculate(inp)
    маршрут = res.листы[0].маршрут
    assert маршрут[0] == "г. Москва, ул. Ленина, 1"
    assert маршрут[-1] == "г. Москва, ул. Ленина, 1"
    assert any("Кутузовский" in stop for stop in маршрут)


def test_route_empty_without_адрес_стоянки_and_without_azs_addresses():
    inp = make_input(
        водители=[Водитель(фио="А", дни=[date(2025, 6, 2)])],
        заправки=[Заправка(дата=date(2025, 6, 1), время="08:00", объём=40)],  # без адреса
    )
    res = calculate(inp)
    assert res.листы[0].маршрут == []


def test_route_field_optional_backward_compatible():
    """Неделя 1: если адреса не заданы вовсе — расчёт как раньше, поле просто пустое."""
    inp = make_input()
    res = calculate(inp)
    assert all(isinstance(пл.маршрут, list) for пл in res.листы)
