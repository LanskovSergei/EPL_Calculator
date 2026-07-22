import type { ReactNode } from 'react';
import type { РезультатРасчёта, ПутевойЛист } from '../types';

function Row({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="row">
      <span className="k">{k}</span>
      <span className="v">{v}</span>
    </div>
  );
}

function Sheet({ л }: { л: ПутевойЛист }) {
  return (
    <div className="sheet">
      <div className="sheet-head">
        <span className="sheet-no">Путевой лист № {л.номер}</span>
        <span className="sheet-driver">{л.водитель || '—'}</span>
      </div>
      <div className="sheet-grid">
        <Row k="Выпуск на линию" v={л.выпуск} />
        <Row k="Возвращение с линии" v={л.возвращение} />
        <Row k="Общее время за выезд" v={`${л.общееВремя} ч`} />
        <Row k="Вид сообщения" v={л.видСообщения} />
        <Row k="Одометр на выдачу" v={`${л.одометрВыдача} км`} />
        <Row k="Одометр на закрытие" v={`${л.одометрЗакрытие} км`} />
        <Row k="Общий пробег за выезд" v={<b>{л.пробег} км</b>} />
        <Row k="Остаток ГСМ на выдачу" v={`${л.остатокВыдача} л`} />
        <Row k="Остаток ГСМ на закрытие" v={`${л.остатокЗакрытие} л`} />
        <Row k="Расход горючего (норма/факт)" v={`${л.расходНорма} / ${л.расходФакт} л`} />
      </div>
    </div>
  );
}

interface ResultsProps {
  результат: РезультатРасчёта | null;
}

export function Results({ результат }: ResultsProps) {
  return (
    <section className="card" id="resultsCard" style={{ marginTop: 24 }}>
      <h2>Результаты — путевые листы</h2>

      {результат?.предупреждения && результат.предупреждения.length > 0 && (
        <div className="warnings">
          <span className="warn-title">Обратите внимание:</span>
          <ul>
            {результат.предупреждения.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {результат?.расход && результат.расход.effective > 0 && (
        <div className="consumption-summary">
          Эффективный расход: <b>{результат.расход.effective} л/100км</b> (база {результат.расход.base}).{' '}
          {результат.расход.note}
          <br />
          {результат.расход.applied.length > 0 && (
            <span className="chips">
              {результат.расход.applied.map((a, i) => (
                <span className="chip" key={i}>
                  {a.name} +{Math.round(a.value * 100)}%
                </span>
              ))}
            </span>
          )}
        </div>
      )}

      {результат === null ? (
        <div className="empty-state">Заполните данные и нажмите «Посчитать».</div>
      ) : результат.листы.length === 0 ? (
        <div className="empty-state">Путевые листы не сформированы. Проверьте предупреждения выше.</div>
      ) : (
        результат.листы.map((л) => <Sheet key={л.номер} л={л} />)
      )}

      {результат && результат.листы.length > 0 && (
        <div className="disclaimer">
          Внимание! Путевой лист без отметок о прохождении медицинского осмотра водителя и технического
          контроля транспортного средства недействителен. Инструмент носит расчётно-ознакомительный характер.
        </div>
      )}
    </section>
  );
}
