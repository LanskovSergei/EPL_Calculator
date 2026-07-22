/*
 * Калькулятор ГСМ — движок расчёта пробега (Шаг 1.1, MVP).
 *
 * Чистые функции без обращения к DOM: принимают исходные данные,
 * возвращают массив путевых листов и предупреждения.
 *
 * Основная формула (ТЗ, раздел «Модель калькуляции»):
 *   Пробег в день (км) = затраты ГСМ в день (л) / (средний расход (л/100км) / 100)
 *                      = затраты ГСМ (л) * 100 / средний расход (л/100км)
 */

import type {
  ВходныеДанные,
  РезультатРасчёта,
  СводкаРасхода,
  ПутевойЛист,
  Смена,
  ВидСообщения,
  ТипТС,
  ВидТоплива,
} from './types';

// ------- Константы и справочные значения -------

/** Ограничения пробега за сутки (ТЗ: «предел разумного пробега»). */
export const MAX_DAILY_KM: Record<ТипТС, number> = {
  легковой: 300,
  грузовой: 250,
};

/** Минимальный остаток топлива на закрытии ПЛ (ТЗ). */
export const MIN_CLOSING_FUEL = 10; // литров

/** Базовый расход по умолчанию, если пользователь не задал средний расход. */
const DEFAULT_BASE_CONSUMPTION: Record<ВидТоплива, number> = {
  бензин: 11,
  дизель: 9,
};

/**
 * Коэффициенты надбавок (ориентированы на Распоряжение Минтранса АМ-23-р).
 * Для MVP усреднённые; на шаге 1.2/2.x заменяются справочником по моделям.
 */
const COEFF = {
  зима: 0.1,
  старше10лет: 0.05,
  прицепГруз: 0.1,
  сообщение: {
    городское: 0.1,
    пригородное: 0.05,
    междугородное: 0,
    международное: 0,
  } as Record<ВидСообщения, number>,
};

/** Средняя скорость для оценки времени в пути (км/ч) по виду сообщения. */
const AVG_SPEED: Record<ВидСообщения, number> = {
  городское: 25,
  пригородное: 45,
  междугородное: 65,
  международное: 65,
};

const DEFAULT_DEPART_HOUR = 8; // 08:00

// ------- Утилиты дат -------

function pad2(n: number): string {
  return String(n).padStart(2, '0');
}

export function toISODate(d: Date): string {
  return `${d.getFullYear()}-${pad2(d.getMonth() + 1)}-${pad2(d.getDate())}`;
}

export function parseISODate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}

export function addDays(d: Date, n: number): Date {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

export function isWeekend(d: Date): boolean {
  const wd = d.getDay();
  return wd === 0 || wd === 6;
}

/** Зимний месяц (ноябрь–март) — грубая эвристика сезона. */
function isWinterMonth(monthIndex0: number): boolean {
  return monthIndex0 >= 10 || monthIndex0 <= 2;
}

function formatDateTime(d: Date): string {
  return (
    `${pad2(d.getDate())}.${pad2(d.getMonth() + 1)}.${d.getFullYear()} ` +
    `${pad2(d.getHours())}:${pad2(d.getMinutes())}`
  );
}

function round(n: number, digits = 0): number {
  const p = Math.pow(10, digits);
  return Math.round(n * p) / p;
}

function num(v: number | '' | null | undefined): number {
  return typeof v === 'number' ? v : Number(v) || 0;
}

// ------- Эффективный расход топлива -------

export function computeConsumption(input: ВходныеДанные, periodStart: Date): СводкаРасхода {
  // Спецтехника: коэффициенты не применяются, средний расход обязателен.
  if (input.спецтехника) {
    const base = num(input.среднийРасход);
    return {
      effective: base,
      base,
      applied: [],
      note: 'Спецтехника: коэффициенты не применяются, задан ручной расход.',
    };
  }

  const manual = num(input.среднийРасход);
  const base = manual > 0 ? manual : DEFAULT_BASE_CONSUMPTION[input.видТоплива] ?? 10;

  const applied: СводкаРасхода['applied'] = [];
  let multiplier = 1;

  if (isWinterMonth(periodStart.getMonth())) {
    multiplier += COEFF.зима;
    applied.push({ name: 'Зима', value: COEFF.зима });
  }
  if (input.старше10лет) {
    multiplier += COEFF.старше10лет;
    applied.push({ name: 'Возраст > 10 лет', value: COEFF.старше10лет });
  }
  if (input.прицепГруз) {
    multiplier += COEFF.прицепГруз;
    applied.push({ name: 'Прицеп/груз', value: COEFF.прицепГруз });
  }
  const commCoeff = COEFF.сообщение[input.видСообщения] ?? 0;
  if (commCoeff > 0) {
    multiplier += commCoeff;
    applied.push({ name: `Вид сообщения: ${input.видСообщения}`, value: commCoeff });
  }

  return {
    effective: round(base * multiplier, 2),
    base,
    applied,
    note:
      manual > 0
        ? 'База — ручной средний расход, применены коэффициенты.'
        : `База — норматив по умолчанию для «${input.видТоплива}», применены коэффициенты.`,
  };
}

// ------- Генерация смен -------

export function buildShifts(input: ВходныеДанные): Смена[] {
  const drivers = input.водители;
  const multiDay = input.видСообщения === 'междугородное' || input.видСообщения === 'международное';
  const tripDays = multiDay ? Math.max(1, num(input.срокРейсаДней) || 1) : 1;

  // Карта: ISO-дата -> индексы водителей, отметивших день
  const dateMap = new Map<string, number[]>();
  drivers.forEach((drv, idx) => {
    drv.дни.forEach((iso) => {
      const arr = dateMap.get(iso);
      if (arr) arr.push(idx);
      else dateMap.set(iso, [idx]);
    });
  });

  const sortedDates = Array.from(dateMap.keys()).sort();
  const shifts: Смена[] = [];
  let rr = 0; // round-robin для балансировки водителей

  if (!multiDay) {
    for (const iso of sortedDates) {
      const available = dateMap.get(iso)!;
      const driverIdx = available[rr % available.length];
      rr++;
      shifts.push({
        start: parseISODate(iso),
        days: 1,
        driver: drivers[driverIdx].фио || `Водитель ${driverIdx + 1}`,
      });
    }
  } else {
    const used = new Set<string>();
    for (const iso of sortedDates) {
      if (used.has(iso)) continue;
      const available = dateMap.get(iso)!;
      const driverIdx = available[rr % available.length];
      rr++;
      const start = parseISODate(iso);
      for (let i = 0; i < tripDays; i++) used.add(toISODate(addDays(start, i)));
      shifts.push({
        start,
        days: tripDays,
        driver: drivers[driverIdx].фио || `Водитель ${driverIdx + 1}`,
      });
    }
  }

  shifts.sort((a, b) => a.start.getTime() - b.start.getTime());
  return shifts;
}

// ------- Основной расчёт -------

export function calculate(input: ВходныеДанные): РезультатРасчёта {
  const warnings: string[] = [];
  const periodStart = parseISODate(input.периодС);

  const consumption = computeConsumption(input, periodStart);
  const C = consumption.effective; // л/100км
  if (!C || C <= 0) {
    warnings.push('Не удалось определить средний расход. Укажите «Средний расход» вручную.');
    return { листы: [], предупреждения: warnings, расход: consumption };
  }

  const tankVolume = num(input.объёмБака);
  if (tankVolume <= 0) warnings.push('Не задан объём бака ТС.');

  const maxDailyKm = MAX_DAILY_KM[input.типТС] ?? MAX_DAILY_KM.легковой;

  const shifts = buildShifts(input);
  if (shifts.length === 0) {
    warnings.push('Не отмечено ни одного рабочего дня в календарях водителей.');
    return { листы: [], предупреждения: warnings, расход: consumption };
  }

  // Заправки, отсортированные по дате/времени
  const refuels = input.заправки
    .filter((r) => r.дата && num(r.объём) > 0)
    .map((r) => ({
      when: new Date(`${r.дата}T${r.время || '00:00'}`),
      volume: num(r.объём),
      applied: false,
    }))
    .sort((a, b) => a.when.getTime() - b.when.getTime());

  let tank = num(input.остатокНаНачало);
  if (tank > tankVolume && tankVolume > 0) {
    warnings.push('Начальный остаток топлива больше объёма бака — ограничено объёмом бака.');
    tank = tankVolume;
  }

  const odoKnown = input.одометрНаНачало !== '' && input.одометрНаНачало != null;
  let odo = odoKnown ? num(input.одометрНаНачало) : 2500; // ТЗ: неизвестен → от 2500 км
  if (!odoKnown) {
    warnings.push('Показания одометра на начало не заданы — расчёт начат с 2500 км (по ТЗ).');
  }

  const totalFuel = tank + refuels.reduce((s, r) => s + r.volume, 0);
  let remainingBurnable = Math.max(0, totalFuel - MIN_CLOSING_FUEL);

  const листы: ПутевойЛист[] = [];

  for (let i = 0; i < shifts.length; i++) {
    const shift = shifts[i];
    const shiftsLeft = shifts.length - i;

    // Применяем заправки до конца этой смены
    const shiftEndDate = addDays(shift.start, shift.days - 1);
    const shiftEndBoundary = new Date(`${toISODate(shiftEndDate)}T23:59`);
    for (const r of refuels) {
      if (!r.applied && r.when <= shiftEndBoundary) {
        const room = tankVolume > 0 ? tankVolume - tank : r.volume;
        const add = tankVolume > 0 ? Math.min(r.volume, Math.max(0, room)) : r.volume;
        if (tankVolume > 0 && add < r.volume) {
          warnings.push(
            `Заправка ${formatDateTime(r.when)} на ${r.volume} л превышает свободный объём бака — ` +
              `учтено ${round(add, 1)} л.`,
          );
        }
        tank += add;
        r.applied = true;
      }
    }

    const openingFuel = tank;
    const openingOdo = odo;

    const maxFuelByKm = ((maxDailyKm * shift.days) * C) / 100;
    const target = shiftsLeft > 0 ? remainingBurnable / shiftsLeft : 0;
    const maxByReserve = Math.max(0, tank - MIN_CLOSING_FUEL);

    let burn = Math.min(target, maxFuelByKm, maxByReserve);
    if (burn < 0) burn = 0;

    const mileage = (burn * 100) / C;
    const closingFuel = round(tank - burn, 2);
    const closingOdo = round(odo + mileage, 1);

    const speed = AVG_SPEED[input.видСообщения] ?? 40;
    const departure = new Date(shift.start);
    departure.setHours(DEFAULT_DEPART_HOUR, 0, 0, 0);

    let returnDt: Date;
    let totalHours: number;
    if (shift.days > 1) {
      returnDt = new Date(addDays(shift.start, shift.days - 1));
      const extraHours = Math.min(12, Math.round(mileage / speed / shift.days));
      returnDt.setHours(DEFAULT_DEPART_HOUR + extraHours, 0, 0, 0);
      totalHours = round((returnDt.getTime() - departure.getTime()) / 3600000, 1);
    } else {
      const driveHours = mileage / speed;
      totalHours = round(driveHours, 1);
      returnDt = new Date(departure.getTime() + driveHours * 3600000);
    }

    листы.push({
      номер: i + 1,
      выпуск: formatDateTime(departure),
      возвращение: formatDateTime(returnDt),
      водитель: shift.driver,
      общееВремя: totalHours,
      одометрВыдача: round(openingOdo, 1),
      одометрЗакрытие: closingOdo,
      пробег: round(mileage, 1),
      остатокВыдача: round(openingFuel, 2),
      остатокЗакрытие: closingFuel,
      расходНорма: round(burn, 2),
      расходФакт: round(burn, 2),
      видСообщения: input.видСообщения,
    });

    tank = closingFuel;
    odo = closingOdo;
    remainingBurnable = Math.max(0, remainingBurnable - burn);
  }

  if (tank > MIN_CLOSING_FUEL + 0.5) {
    warnings.push(
      `После распределения в баке осталось ${round(tank, 1)} л. Не всё топливо реализовано ` +
        `в рамках лимитов пробега/смен — добавьте рабочие дни, увеличьте срок рейса или скорректируйте данные.`,
    );
  }

  return { листы, предупреждения: warnings, расход: consumption };
}
