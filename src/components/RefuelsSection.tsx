import type { Заправка } from '../types';

interface RefuelsSectionProps {
  заправки: Заправка[];
  onChange: (заправки: Заправка[]) => void;
}

export function RefuelsSection({ заправки, onChange }: RefuelsSectionProps) {
  const update = (idx: number, patch: Partial<Заправка>) => {
    onChange(заправки.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  };
  const add = () => onChange([...заправки, { дата: '', время: '', объём: '' }]);
  const remove = (idx: number) => onChange(заправки.filter((_, i) => i !== idx));

  return (
    <section className="card">
      <h2>5. Данные о заправках (с чеков)</h2>
      <table className="refuel-table">
        <thead>
          <tr>
            <th style={{ width: '32%' }}>Дата заправки</th>
            <th style={{ width: '28%' }}>Время</th>
            <th style={{ width: '28%' }}>Объём, л</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {заправки.map((r, idx) => (
            <tr key={idx}>
              <td>
                <input
                  type="date"
                  value={r.дата}
                  onChange={(e) => update(idx, { дата: e.target.value })}
                />
              </td>
              <td>
                <input
                  type="time"
                  value={r.время}
                  onChange={(e) => update(idx, { время: e.target.value })}
                />
              </td>
              <td>
                <input
                  type="number"
                  min={0}
                  step={0.1}
                  value={r.объём}
                  onChange={(e) =>
                    update(idx, { объём: e.target.value === '' ? '' : Number(e.target.value) })
                  }
                />
              </td>
              <td className="actions">
                <button type="button" className="btn-danger" onClick={() => remove(idx)}>
                  ✕
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div style={{ marginTop: 12 }}>
        <button type="button" className="btn-secondary" onClick={add}>
          + Добавить заправку
        </button>
      </div>
    </section>
  );
}
