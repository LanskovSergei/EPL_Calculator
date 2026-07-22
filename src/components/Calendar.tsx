import type { ReactNode } from 'react';
import { toISODate, parseISODate, isWeekend } from '../calc';

const MONTH_NAMES = [
  'январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
  'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь',
];
const DOW = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'];

interface CalendarProps {
  периодС: string;
  периодПо: string;
  выбранные: Set<string>;
  onToggle: (iso: string) => void;
}

interface MonthProps {
  year: number;
  month: number;
  periodStart: Date;
  periodEnd: Date;
  выбранные: Set<string>;
  onToggle: (iso: string) => void;
}

function Month({ year, month, periodStart, periodEnd, выбранные, onToggle }: MonthProps) {
  const first = new Date(year, month, 1);
  const offset = (first.getDay() + 6) % 7; // понедельник первым
  const daysInMonth = new Date(year, month + 1, 0).getDate();

  const cells: ReactNode[] = [];
  for (let i = 0; i < offset; i++) {
    cells.push(<div key={`e${i}`} className="day empty" />);
  }
  for (let day = 1; day <= daysInMonth; day++) {
    const date = new Date(year, month, day);
    const iso = toISODate(date);
    const inPeriod = date >= periodStart && date <= periodEnd;
    const classes = ['day'];
    if (isWeekend(date)) classes.push('weekend');
    if (!inPeriod) classes.push('out');
    else if (выбранные.has(iso)) classes.push('selected');

    cells.push(
      <div
        key={iso}
        className={classes.join(' ')}
        onClick={inPeriod ? () => onToggle(iso) : undefined}
      >
        {day}
      </div>,
    );
  }

  return (
    <div className="month">
      <div className="month-title">{`${MONTH_NAMES[month]} ${year}`}</div>
      <div className="month-grid">
        {DOW.map((d) => (
          <div key={d} className="dow">{d}</div>
        ))}
        {cells}
      </div>
    </div>
  );
}

export function Calendar({ периодС, периодПо, выбранные, onToggle }: CalendarProps) {
  if (!периодС || !периодПо) {
    return <p className="hint">Задайте период расчёта, чтобы отметить рабочие дни.</p>;
  }
  const start = parseISODate(периодС);
  const end = parseISODate(периодПо);
  if (end < start) {
    return <p className="hint">Дата «по» раньше даты «с».</p>;
  }

  const months: { year: number; month: number }[] = [];
  let cursor = new Date(start.getFullYear(), start.getMonth(), 1);
  const last = new Date(end.getFullYear(), end.getMonth(), 1);
  while (cursor <= last) {
    months.push({ year: cursor.getFullYear(), month: cursor.getMonth() });
    cursor = new Date(cursor.getFullYear(), cursor.getMonth() + 1, 1);
  }

  return (
    <div className="calendars">
      {months.map((m) => (
        <Month
          key={`${m.year}-${m.month}`}
          year={m.year}
          month={m.month}
          periodStart={start}
          periodEnd={end}
          выбранные={выбранные}
          onToggle={onToggle}
        />
      ))}
    </div>
  );
}
