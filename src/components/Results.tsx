import type { РезультатРасчёта, ПутевойЛист, ВидСообщения } from '../types';
import { recalculateSheets, yandexMapsRouteUrl } from '../recalc';
import { ContactsBlock } from './Legal';

const ВИДЫ: ВидСообщения[] = ['городское', 'пригородное', 'междугородное', 'международное'];

interface ResultsProps {
  результат: РезультатРасчёта | null;
  onChange: (результат: РезультатРасчёта) => void;
  onOpenAgreement: () => void;
}

function Sheet({
  л,
  onPatch,
}: {
  л: ПутевойЛист;
  onPatch: (patch: Partial<ПутевойЛист>) => void;
}) {
  const mapUrl = л.маршрут ? yandexMapsRouteUrl(л.маршрут) : null;

  return (
    <div className="sheet">
      <div className="sheet-head">
        <span className="sheet-no">Путевой лист № {л.номер}</span>
        <input
          className="sheet-driver-input"
          type="text"
          value={л.водитель}
          onChange={(e) => onPatch({ водитель: e.target.value })}
          aria-label="ФИО водителя"
        />
      </div>
      <div className="sheet-grid editable">
        <label className="row">
          <span className="k">Выпуск на линию</span>
          <input type="text" value={л.выпуск} onChange={(e) => onPatch({ выпуск: e.target.value })} />
        </label>
        <label className="row">
          <span className="k">Возвращение с линии</span>
          <input type="text" value={л.возвращение} onChange={(e) => onPatch({ возвращение: e.target.value })} />
        </label>
        <label className="row">
          <span className="k">Общее время за выезд, ч</span>
          <input
            type="number"
            step={0.1}
            value={л.общееВремя}
            onChange={(e) => onPatch({ общееВремя: Number(e.target.value) || 0 })}
          />
        </label>
        <label className="row">
          <span className="k">Вид сообщения</span>
          <select
            value={л.видСообщения}
            onChange={(e) => onPatch({ видСообщения: e.target.value as ВидСообщения })}
          >
            {ВИДЫ.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
        <label className="row">
          <span className="k">Одометр на выдачу, км</span>
          <input
            type="number"
            step={0.1}
            value={л.одометрВыдача}
            onChange={(e) => onPatch({ одометрВыдача: Number(e.target.value) || 0 })}
          />
        </label>
        <label className="row">
          <span className="k">Одометр на закрытие, км</span>
          <input
            type="number"
            step={0.1}
            value={л.одометрЗакрытие}
            onChange={(e) => onPatch({ одометрЗакрытие: Number(e.target.value) || 0 })}
          />
        </label>
        <label className="row">
          <span className="k">Общий пробег за выезд, км</span>
          <input
            type="number"
            step={0.1}
            value={л.пробег}
            onChange={(e) => onPatch({ пробег: Number(e.target.value) || 0 })}
          />
        </label>
        <label className="row">
          <span className="k">Остаток ГСМ на выдачу, л</span>
          <input
            type="number"
            step={0.1}
            value={л.остатокВыдача}
            onChange={(e) => onPatch({ остатокВыдача: Number(e.target.value) || 0 })}
          />
        </label>
        <label className="row">
          <span className="k">Остаток ГСМ на закрытие, л</span>
          <input
            type="number"
            step={0.1}
            value={л.остатокЗакрытие}
            onChange={(e) => onPatch({ остатокЗакрытие: Number(e.target.value) || 0 })}
          />
        </label>
        <label className="row">
          <span className="k">Расход норма, л</span>
          <input
            type="number"
            step={0.1}
            value={л.расходНорма}
            onChange={(e) => onPatch({ расходНорма: Number(e.target.value) || 0 })}
          />
        </label>
        <label className="row">
          <span className="k">Расход факт, л</span>
          <input
            type="number"
            step={0.1}
            value={л.расходФакт}
            onChange={(e) => onPatch({ расходФакт: Number(e.target.value) || 0 })}
          />
        </label>
      </div>

      <div className="sheet-route">
        <div className="route-head">
          <span className="route-title">Маршрут</span>
          {mapUrl && (
            <a className="btn-secondary btn-sm" href={mapUrl} target="_blank" rel="noreferrer">
              Посмотреть на карте
            </a>
          )}
        </div>
        <textarea
          className="route-editor"
          rows={Math.max(3, (л.маршрут?.length || 0) + 1)}
          placeholder="По одному адресу на строку: стоянка → АЗС → … → стоянка"
          value={(л.маршрут || []).join('\n')}
          onChange={(e) => onPatch({ маршрут: e.target.value.split('\n') })}
        />
        <p className="hint">Редактируйте адреса построчно. Кнопка карты откроет маршрут в Яндекс.Картах.</p>
      </div>
    </div>
  );
}

export function Results({ результат, onChange, onOpenAgreement }: ResultsProps) {
  if (результат === null) {
    return (
      <section className="card" id="resultsCard" style={{ marginTop: 24 }}>
        <h2>Результаты — путевые листы</h2>
        <div className="empty-state">Заполните данные и нажмите «Посчитать».</div>
      </section>
    );
  }

  const patchSheet = (idx: number, patch: Partial<ПутевойЛист>) => {
    const листы = результат.листы.map((л, i) => (i === idx ? { ...л, ...patch } : л));
    onChange({ ...результат, листы });
  };

  const onRecalc = () => {
    const расход = результат.расход?.effective ?? null;
    onChange({
      ...результат,
      листы: recalculateSheets(результат.листы, расход),
      предупреждения: [
        ...результат.предупреждения.filter((w) => !w.startsWith('Результаты пересчитаны')),
        'Результаты пересчитаны с учётом ваших правок (цепочка одометра/остатков и расход по пробегу).',
      ],
    });
  };

  return (
    <section className="card" id="resultsCard" style={{ marginTop: 24 }}>
      <div className="results-head">
        <h2>Результаты — путевые листы</h2>
        {результат.листы.length > 0 && (
          <button type="button" className="btn-primary" onClick={onRecalc}>
            Пересчитать
          </button>
        )}
      </div>
      <p className="hint results-hint">
        Поля результата можно править вручную. «Пересчитать» синхронизирует пробег ↔ расход и протащит
        одометр/остатки на следующие листы.
      </p>

      {результат.предупреждения.length > 0 && (
        <div className="warnings">
          <span className="warn-title">Обратите внимание:</span>
          <ul>
            {результат.предупреждения.map((w, i) => (
              <li key={i}>{w}</li>
            ))}
          </ul>
        </div>
      )}

      {результат.расход && результат.расход.effective > 0 && (
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

      {результат.листы.length === 0 ? (
        <div className="empty-state">Путевые листы не сформированы. Проверьте предупреждения выше.</div>
      ) : (
        результат.листы.map((л, idx) => (
          <Sheet key={л.номер} л={л} onPatch={(patch) => patchSheet(idx, patch)} />
        ))
      )}

      {результат.листы.length > 0 && (
        <>
          <div className="pro-banner">
            <h3>Маршрут построен</h3>
            <p>
              Больше возможностей в PRO-версии Калькулятора ГСМ для транспортной бухгалтерии и
              диспетчерских служб.
            </p>
            <p className="pro-cta">
              У нашей клиентской службы уже есть ответы на ваши вопросы. Свяжитесь с нами:
            </p>
            <ContactsBlock compact />
          </div>

          <div className="disclaimer">
            <p>
              <strong>Внимание!</strong> Путевой лист без отметок о прохождении медицинского осмотра
              водителя и технического контроля транспортного средства недействителен.
            </p>
            <p>
              Правильно организовать выпуск автомобилей на линию и вести путевую документацию вам всегда
              помогут в <strong>ПРЕДРЕЙС</strong>. Свяжитесь с нами:
            </p>
            <ContactsBlock compact />
            <p className="disclaimer-legal">
              Сервис предоставляется в ознакомительных целях.{' '}
              <button type="button" className="link-btn" onClick={onOpenAgreement}>
                Пользовательское соглашение
              </button>
            </p>
          </div>
        </>
      )}
    </section>
  );
}
