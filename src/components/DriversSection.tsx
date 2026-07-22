import type { Водитель } from '../types';
import { toISODate, parseISODate, addDays, isWeekend } from '../calc';
import { пустойВодитель } from '../defaults';
import { Calendar } from './Calendar';

interface DriversSectionProps {
  водители: Водитель[];
  периодС: string;
  периодПо: string;
  onChange: (водители: Водитель[]) => void;
}

export function DriversSection({ водители, периодС, периодПо, onChange }: DriversSectionProps) {
  const setCount = (n: number) => {
    const count = Math.max(1, Math.min(20, n || 1));
    const next: Водитель[] = [];
    for (let i = 0; i < count; i++) next.push(водители[i] ?? пустойВодитель());
    onChange(next);
  };

  const updateDriver = (idx: number, patch: Partial<Водитель>) => {
    onChange(водители.map((d, i) => (i === idx ? { ...d, ...patch } : d)));
  };

  const toggleDay = (idx: number, iso: string) => {
    const дни = new Set(водители[idx].дни);
    if (дни.has(iso)) дни.delete(iso);
    else дни.add(iso);
    updateDriver(idx, { дни });
  };

  const selectWeekdays = (idx: number) => {
    if (!периодС || !периодПо) return;
    const дни = new Set<string>();
    let cur = parseISODate(периодС);
    const end = parseISODate(периодПо);
    while (cur <= end) {
      if (!isWeekend(cur)) дни.add(toISODate(cur));
      cur = addDays(cur, 1);
    }
    updateDriver(idx, { дни });
  };

  const clearDays = (idx: number) => updateDriver(idx, { дни: new Set<string>() });

  return (
    <section className="card">
      <h2>4. Водители и рабочие дни</h2>
      <div className="field" style={{ maxWidth: 260, marginBottom: 14 }}>
        <label htmlFor="колВодителей">Количество водителей</label>
        <input
          type="number"
          id="колВодителей"
          min={1}
          max={20}
          step={1}
          value={водители.length}
          onChange={(e) => setCount(Number(e.target.value))}
        />
      </div>

      {водители.map((drv, idx) => (
        <div className="driver-block" key={idx}>
          <div className="driver-head">
            <span className="driver-tag">Водитель {idx + 1}</span>
            <input
              type="text"
              placeholder="ФИО водителя"
              value={drv.фио}
              onChange={(e) => updateDriver(idx, { фио: e.target.value })}
            />
          </div>
          <Calendar
            периодС={периодС}
            периодПо={периодПо}
            выбранные={drv.дни}
            onToggle={(iso) => toggleDay(idx, iso)}
          />
          <div className="driver-tools">
            <button type="button" className="btn-secondary" onClick={() => selectWeekdays(idx)}>
              Все будние дни
            </button>
            <button type="button" className="btn-ghost" onClick={() => clearDays(idx)}>
              Очистить
            </button>
          </div>
        </div>
      ))}

      <p className="hint" style={{ marginTop: 4 }}>
        Отметьте рабочие дни каждого водителя кликом по дате. «Все будние дни» отмечает пн–пт в пределах периода.
      </p>
    </section>
  );
}
