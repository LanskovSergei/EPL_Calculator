import { useState } from 'react';
import type { ВходныеДанные, РезультатРасчёта } from './types';
import { parseISODate } from './calc';
import { calculateSmart } from './api';
import { начальныеДанные, демоДанные } from './defaults';
import { DriversSection } from './components/DriversSection';
import { RefuelsSection } from './components/RefuelsSection';
import { Results } from './components/Results';
import {
  ConsentBanner,
  ContactsBlock,
  UserAgreementModal,
  useAgreementModal,
} from './components/Legal';

function validate(input: ВходныеДанные): string[] {
  const errs: string[] = [];
  if (!input.периодС || !input.периодПо) errs.push('Укажите период расчёта (с и по).');
  if (input.периодС && input.периодПо && parseISODate(input.периодПо) < parseISODate(input.периодС))
    errs.push('Дата «по» не может быть раньше даты «с».');
  if (!(Number(input.объёмБака) > 0)) errs.push('Укажите объём бака ТС.');
  if (input.остатокНаНачало === '' || Number(input.остатокНаНачало) < 0)
    errs.push('Укажите остаток топлива в баке на начало периода.');
  if (input.спецтехника && !(Number(input.среднийРасход) > 0))
    errs.push('Для спецтехники поле «Средний расход» обязательно.');
  return errs;
}

/** Приводит числовое поле формы к number | ''. */
function numField(value: string): number | '' {
  return value === '' ? '' : Number(value);
}

export default function App() {
  const [data, setData] = useState<ВходныеДанные>(начальныеДанные);
  const [result, setResult] = useState<РезультатРасчёта | null>(null);
  const [loading, setLoading] = useState(false);
  const { open, openAgreement, closeAgreement } = useAgreementModal();

  const upd = <K extends keyof ВходныеДанные>(key: K, value: ВходныеДанные[K]) =>
    setData((d) => ({ ...d, [key]: value }));

  const multiDay = data.видСообщения === 'междугородное' || data.видСообщения === 'международное';

  const onCalc = async () => {
    const errs = validate(data);
    if (errs.length) {
      setResult({ листы: [], предупреждения: errs, расход: null });
      setTimeout(() => document.getElementById('resultsCard')?.scrollIntoView({ behavior: 'smooth' }), 0);
      return;
    }
    setLoading(true);
    try {
      const r = await calculateSmart(data);
      setResult(r);
    } finally {
      setLoading(false);
      setTimeout(() => document.getElementById('resultsCard')?.scrollIntoView({ behavior: 'smooth' }), 0);
    }
  };

  return (
    <>
      <header className="app-header">
        <div className="header-inner">
          <a className="brand" href="https://предрейс.рф/" target="_blank" rel="noreferrer">
            <span className="brand-mark-glyph">П</span>
            <span className="brand-copy">
              <strong>ПРЕДРЕЙС</strong>
              <span>Калькулятор ГСМ</span>
            </span>
          </a>
          <div className="header-meta">
            <a href="tel:+79250288755">+7 (925) 028-87-55</a>
            <span className="header-badge">открытая версия</span>
          </div>
        </div>
        <div className="header-title">
          <h1>Калькулятор пробега ГСМ</h1>
          <p>Восстановление путевых листов по чекам АЗС · для бухгалтерии и диспетчерских служб</p>
        </div>
      </header>

      <ConsentBanner onOpenAgreement={openAgreement} />

      <main className="container">
        <section className="card">
          <h2>1. Транспортное средство</h2>
          <div className="grid">
            <div className="field">
              <label>Марка ТС</label>
              <input type="text" placeholder="Напр., ГАЗ" value={data.марка}
                onChange={(e) => upd('марка', e.target.value)} />
            </div>
            <div className="field">
              <label>Модель ТС</label>
              <input type="text" placeholder="Напр., 3302" value={data.модель}
                onChange={(e) => upd('модель', e.target.value)} />
            </div>
            <div className="field">
              <label>Тип ТС <span className="hint">(влияет на лимит пробега)</span></label>
              <select value={data.типТС} onChange={(e) => upd('типТС', e.target.value as ВходныеДанные['типТС'])}>
                <option value="легковой">Легковой (до 300 км/сут)</option>
                <option value="грузовой">Грузовой (до 250 км/сут)</option>
              </select>
            </div>
            <div className="field">
              <label>Вид топлива</label>
              <select value={data.видТоплива} onChange={(e) => upd('видТоплива', e.target.value as ВходныеДанные['видТоплива'])}>
                <option value="бензин">Бензин</option>
                <option value="дизель">Дизель</option>
              </select>
            </div>
            <div className="field">
              <label>Объём бака ТС, л</label>
              <input type="number" min={0} step={1} placeholder="Напр., 64" value={data.объёмБака}
                onChange={(e) => upd('объёмБака', numField(e.target.value))} />
            </div>
            <div className="field">
              <label>Средний расход, л/100км <span className="hint">(необязательно)</span></label>
              <input type="number" min={0} step={0.1} placeholder="Авто, если пусто" value={data.среднийРасход}
                onChange={(e) => upd('среднийРасход', numField(e.target.value))} />
            </div>
          </div>
          <div className="checks">
            <div className="checkbox-row">
              <input type="checkbox" id="старше10лет" checked={data.старше10лет}
                onChange={(e) => upd('старше10лет', e.target.checked)} />
              <label htmlFor="старше10лет">Авто старше 10 лет</label>
            </div>
            <div className="checkbox-row">
              <input type="checkbox" id="прицепГруз" checked={data.прицепГруз}
                onChange={(e) => upd('прицепГруз', e.target.checked)} />
              <label htmlFor="прицепГруз">Наличие прицепа или груза</label>
            </div>
            <div className="checkbox-row">
              <input type="checkbox" id="спецтехника" checked={data.спецтехника}
                onChange={(e) => upd('спецтехника', e.target.checked)} />
              <label htmlFor="спецтехника">Спецтехника (расход вручную, без коэффициентов)</label>
            </div>
          </div>
        </section>

        <section className="card">
          <h2>2. Период и вид сообщения</h2>
          <div className="grid">
            <div className="field">
              <label>Период расчёта: с</label>
              <input type="date" value={data.периодС} onChange={(e) => upd('периодС', e.target.value)} />
            </div>
            <div className="field">
              <label>Период расчёта: по</label>
              <input type="date" value={data.периодПо} onChange={(e) => upd('периодПо', e.target.value)} />
            </div>
            <div className="field">
              <label>Вид сообщения</label>
              <select value={data.видСообщения}
                onChange={(e) => upd('видСообщения', e.target.value as ВходныеДанные['видСообщения'])}>
                <option value="городское">Городское (ПЛ на 1 день)</option>
                <option value="пригородное">Пригородное (ПЛ на 1 день)</option>
                <option value="междугородное">Междугородное (задать срок рейса)</option>
                <option value="международное">Международное (задать срок рейса)</option>
              </select>
            </div>
            {multiDay && (
              <div className="field">
                <label>Срок рейса, дней</label>
                <input type="number" min={1} step={1} value={data.срокРейсаДней}
                  onChange={(e) => upd('срокРейсаДней', numField(e.target.value))} />
              </div>
            )}
          </div>
        </section>

        <section className="card">
          <h2>3. Начальные показатели и стоянка</h2>
          <div className="grid">
            <div className="field">
              <label>Показания одометра, км <span className="hint">(необязательно)</span></label>
              <input type="number" min={0} step={1} placeholder="Если неизвестно — от 2500" value={data.одометрНаНачало}
                onChange={(e) => upd('одометрНаНачало', numField(e.target.value))} />
            </div>
            <div className="field">
              <label>Остаток топлива в баке, л</label>
              <input type="number" min={0} step={0.1} placeholder="Напр., 20" value={data.остатокНаНачало}
                onChange={(e) => upd('остатокНаНачало', numField(e.target.value))} />
            </div>
            <div className="field field-wide">
              <label>Адрес официальной стоянки <span className="hint">(точка выпуска и возврата)</span></label>
              <input
                type="text"
                placeholder="Город, улица, дом — где медосмотр и техконтроль"
                value={data.адресСтоянки ?? ''}
                onChange={(e) => upd('адресСтоянки', e.target.value)}
              />
            </div>
          </div>
        </section>

        <DriversSection
          водители={data.водители}
          периодС={data.периодС}
          периодПо={data.периодПо}
          onChange={(водители) => upd('водители', водители)}
        />

        <RefuelsSection заправки={data.заправки} onChange={(заправки) => upd('заправки', заправки)} />

        <div className="calc-actions">
          <button type="button" className="btn-primary" onClick={onCalc} disabled={loading}>
            {loading ? 'Считаю…' : 'Посчитать'}
          </button>
          <button type="button" className="btn-ghost" onClick={() => { setData(начальныеДанные()); setResult(null); }}>
            Сбросить
          </button>
          <button type="button" className="btn-ghost" onClick={() => { setData(демоДанные()); setResult(null); }}>
            Заполнить примером из ТЗ
          </button>
        </div>

        <Results
          результат={result}
          onChange={setResult}
          onOpenAgreement={openAgreement}
        />
      </main>

      <footer className="app-footer">
        <ContactsBlock />
        <p>
          © ПРЕДРЕЙС ·{' '}
          <button type="button" className="link-btn" onClick={openAgreement}>
            Пользовательское соглашение
          </button>
        </p>
      </footer>

      <UserAgreementModal open={open} onClose={closeAgreement} />
    </>
  );
}
