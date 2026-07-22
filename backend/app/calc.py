"""
Калькулятор ГСМ — движок расчёта пробега (Шаг 1.1, MVP).

Портировано 1:1 с src/calc.ts фронтенда, чтобы бэкенд и фронт считали
одинаково (фронт использует этот же движок как fallback/офлайн-режим,
бэкенд — как источник истины для эндпоинта /api/calculate).

Основная формула (ТЗ, раздел «Модель калькуляции»):
    Пробег в день (км) = затраты ГСМ в день (л) * 100 / средний расход (л/100км)

Коэффициенты надбавок ориентированы на Распоряжение Минтранса России
от 14.03.2008 № АМ-23-р (ред. от 30.09.2021).
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import List

from .schemas import (
    ВходныеДанные,
    ВидСообщения,
    ВидТоплива,
    ТипТС,
    ПримененныйКоэффициент,
    ПутевойЛист,
    РезультатРасчёта,
    СводкаРасхода,
)

# ------- Константы и справочные значения -------

# Ограничения пробега за сутки (ТЗ: «предел разумного пробега»).
MAX_DAILY_KM = {
    ТипТС.легковой: 300,
    ТипТС.грузовой: 250,
}

# Минимальный остаток топлива на закрытии ПЛ (ТЗ).
MIN_CLOSING_FUEL = 10.0  # литров

# Базовый расход по умолчанию, если пользователь не задал средний расход.
DEFAULT_BASE_CONSUMPTION = {
    ВидТоплива.бензин: 11.0,
    ВидТоплива.дизель: 9.0,
}

# Коэффициенты надбавок (усреднённые для MVP; на шаге 1.2/2.x заменяются
# справочником по моделям — см. АМ-23-р, приложения 2–4).
COEFF_ЗИМА = 0.10
COEFF_СТАРШЕ_10_ЛЕТ = 0.05
COEFF_ПРИЦЕП_ГРУЗ = 0.10
COEFF_СООБЩЕНИЕ = {
    ВидСообщения.городское: 0.10,
    ВидСообщения.пригородное: 0.05,
    ВидСообщения.междугородное: 0.0,
    ВидСообщения.международное: 0.0,
}

# Средняя скорость для оценки времени в пути (км/ч) по виду сообщения.
AVG_SPEED = {
    ВидСообщения.городское: 25,
    ВидСообщения.пригородное: 45,
    ВидСообщения.междугородное: 65,
    ВидСообщения.международное: 65,
}

DEFAULT_DEPART_HOUR = 8  # 08:00
DEFAULT_START_ODO = 2500.0  # ТЗ: одометр неизвестен → старт от 2500 км


def _round(n: float, digits: int = 0) -> float:
    p = 10**digits
    return round(n * p) / p


def _is_winter_month(month_index0: int) -> bool:
    """Зимний месяц (ноябрь–март) — грубая эвристика сезона. month_index0: 0=янв."""
    return month_index0 >= 10 or month_index0 <= 2


def _format_dt(d: datetime) -> str:
    return d.strftime("%d.%m.%Y %H:%M")


class _Shift:
    __slots__ = ("start", "days", "driver")

    def __init__(self, start: date, days: int, driver: str):
        self.start = start
        self.days = days
        self.driver = driver


# ------- Эффективный расход топлива -------


def compute_consumption(inp: ВходныеДанные, period_start: date) -> СводкаРасхода:
    # Спецтехника: коэффициенты не применяются, средний расход обязателен.
    if inp.спецтехника:
        base = inp.среднийРасход or 0.0
        return СводкаРасхода(
            effective=base,
            base=base,
            applied=[],
            note="Спецтехника: коэффициенты не применяются, задан ручной расход.",
        )

    manual = inp.среднийРасход or 0.0
    base = manual if manual > 0 else DEFAULT_BASE_CONSUMPTION.get(inp.видТоплива, 10.0)

    applied: List[ПримененныйКоэффициент] = []
    multiplier = 1.0

    if _is_winter_month(period_start.month - 1):
        multiplier += COEFF_ЗИМА
        applied.append(ПримененныйКоэффициент(name="Зима", value=COEFF_ЗИМА))
    if inp.старше10лет:
        multiplier += COEFF_СТАРШЕ_10_ЛЕТ
        applied.append(
            ПримененныйКоэффициент(name="Возраст > 10 лет", value=COEFF_СТАРШЕ_10_ЛЕТ)
        )
    if inp.прицепГруз:
        multiplier += COEFF_ПРИЦЕП_ГРУЗ
        applied.append(
            ПримененныйКоэффициент(name="Прицеп/груз", value=COEFF_ПРИЦЕП_ГРУЗ)
        )
    comm_coeff = COEFF_СООБЩЕНИЕ.get(inp.видСообщения, 0.0)
    if comm_coeff > 0:
        multiplier += comm_coeff
        applied.append(
            ПримененныйКоэффициент(
                name=f"Вид сообщения: {inp.видСообщения.value}", value=comm_coeff
            )
        )

    return СводкаРасхода(
        effective=_round(base * multiplier, 2),
        base=base,
        applied=applied,
        note=(
            "База — ручной средний расход, применены коэффициенты."
            if manual > 0
            else f"База — норматив по умолчанию для «{inp.видТоплива.value}», применены коэффициенты."
        ),
    )


# ------- Генерация смен -------


def build_shifts(inp: ВходныеДанные) -> List[_Shift]:
    drivers = inp.водители
    multi_day = inp.видСообщения in (
        ВидСообщения.междугородное,
        ВидСообщения.международное,
    )
    trip_days = max(1, inp.срокРейсаДней or 1) if multi_day else 1

    # Карта: дата -> индексы водителей, отметивших день
    date_map: dict[date, List[int]] = {}
    for idx, drv in enumerate(drivers):
        for d in drv.дни:
            date_map.setdefault(d, []).append(idx)

    sorted_dates = sorted(date_map.keys())
    shifts: List[_Shift] = []
    rr = 0  # round-robin для балансировки водителей

    if not multi_day:
        for d in sorted_dates:
            available = date_map[d]
            driver_idx = available[rr % len(available)]
            rr += 1
            shifts.append(
                _Shift(
                    start=d,
                    days=1,
                    driver=drivers[driver_idx].фио or f"Водитель {driver_idx + 1}",
                )
            )
    else:
        used: set[date] = set()
        for d in sorted_dates:
            if d in used:
                continue
            available = date_map[d]
            driver_idx = available[rr % len(available)]
            rr += 1
            for i in range(trip_days):
                used.add(d + timedelta(days=i))
            shifts.append(
                _Shift(
                    start=d,
                    days=trip_days,
                    driver=drivers[driver_idx].фио or f"Водитель {driver_idx + 1}",
                )
            )

    shifts.sort(key=lambda s: s.start)
    return shifts


# ------- Основной расчёт -------


def calculate(inp: ВходныеДанные) -> РезультатРасчёта:
    warnings: List[str] = []
    period_start = inp.периодС

    consumption = compute_consumption(inp, period_start)
    c = consumption.effective  # л/100км
    if not c or c <= 0:
        warnings.append(
            "Не удалось определить средний расход. Укажите «Средний расход» вручную."
        )
        return РезультатРасчёта(листы=[], предупреждения=warnings, расход=consumption)

    tank_volume = inp.объёмБака or 0.0
    if tank_volume <= 0:
        warnings.append("Не задан объём бака ТС.")

    max_daily_km = MAX_DAILY_KM.get(inp.типТС, MAX_DAILY_KM[ТипТС.легковой])

    shifts = build_shifts(inp)
    if not shifts:
        warnings.append("Не отмечено ни одного рабочего дня в календарях водителей.")
        return РезультатРасчёта(листы=[], предупреждения=warnings, расход=consumption)

    # Заправки, отсортированные по дате/времени
    refuels = sorted(
        (
            {
                "when": datetime.combine(r.дата, r.время or time(0, 0)),
                "volume": r.объём,
                "applied": False,
            }
            for r in inp.заправки
            if r.объём > 0
        ),
        key=lambda r: r["when"],
    )

    tank = inp.остатокНаНачало or 0.0
    if tank_volume > 0 and tank > tank_volume:
        warnings.append(
            "Начальный остаток топлива больше объёма бака — ограничено объёмом бака."
        )
        tank = tank_volume

    odo_known = inp.одометрНаНачало is not None
    odo = inp.одометрНаНачало if odo_known else DEFAULT_START_ODO
    if not odo_known:
        warnings.append(
            "Показания одометра на начало не заданы — расчёт начат с 2500 км (по ТЗ)."
        )

    total_fuel = tank + sum(r["volume"] for r in refuels)
    remaining_burnable = max(0.0, total_fuel - MIN_CLOSING_FUEL)

    листы: List[ПутевойЛист] = []

    for i, shift in enumerate(shifts):
        shifts_left = len(shifts) - i

        # Применяем заправки до конца этой смены
        shift_end_date = shift.start + timedelta(days=shift.days - 1)
        shift_end_boundary = datetime.combine(shift_end_date, time(23, 59))
        for r in refuels:
            if not r["applied"] and r["when"] <= shift_end_boundary:
                room = tank_volume - tank if tank_volume > 0 else r["volume"]
                add = min(r["volume"], max(0.0, room)) if tank_volume > 0 else r["volume"]
                if tank_volume > 0 and add < r["volume"]:
                    warnings.append(
                        f"Заправка {_format_dt(r['when'])} на {r['volume']} л превышает "
                        f"свободный объём бака — учтено {_round(add, 1)} л."
                    )
                tank += add
                r["applied"] = True

        opening_fuel = tank
        opening_odo = odo

        max_fuel_by_km = (max_daily_km * shift.days) * c / 100
        target = remaining_burnable / shifts_left if shifts_left > 0 else 0.0
        max_by_reserve = max(0.0, tank - MIN_CLOSING_FUEL)

        burn = min(target, max_fuel_by_km, max_by_reserve)
        if burn < 0:
            burn = 0.0

        mileage = burn * 100 / c
        closing_fuel = _round(tank - burn, 2)
        closing_odo = _round(odo + mileage, 1)

        speed = AVG_SPEED.get(inp.видСообщения, 40)
        departure = datetime.combine(shift.start, time(DEFAULT_DEPART_HOUR, 0))

        if shift.days > 1:
            return_dt = datetime.combine(
                shift.start + timedelta(days=shift.days - 1), time(0, 0)
            )
            extra_hours = min(12, round(mileage / speed / shift.days))
            return_dt = return_dt.replace(hour=min(23, DEFAULT_DEPART_HOUR + extra_hours))
            total_hours = _round((return_dt - departure).total_seconds() / 3600, 1)
        else:
            drive_hours = mileage / speed
            total_hours = _round(drive_hours, 1)
            return_dt = departure + timedelta(hours=drive_hours)

        листы.append(
            ПутевойЛист(
                номер=i + 1,
                выпуск=_format_dt(departure),
                возвращение=_format_dt(return_dt),
                водитель=shift.driver,
                общееВремя=total_hours,
                одометрВыдача=_round(opening_odo, 1),
                одометрЗакрытие=closing_odo,
                пробег=_round(mileage, 1),
                остатокВыдача=_round(opening_fuel, 2),
                остатокЗакрытие=closing_fuel,
                расходНорма=_round(burn, 2),
                расходФакт=_round(burn, 2),
                видСообщения=inp.видСообщения,
            )
        )

        tank = closing_fuel
        odo = closing_odo
        remaining_burnable = max(0.0, remaining_burnable - burn)

    if tank > MIN_CLOSING_FUEL + 0.5:
        warnings.append(
            f"После распределения в баке осталось {_round(tank, 1)} л. Не всё топливо "
            f"реализовано в рамках лимитов пробега/смен — добавьте рабочие дни, "
            f"увеличьте срок рейса или скорректируйте данные."
        )

    return РезультатРасчёта(листы=листы, предупреждения=warnings, расход=consumption)
