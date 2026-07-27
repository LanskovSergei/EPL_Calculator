import { useState } from 'react';

const AGREEMENT_TEXT = `
Сервис «Калькулятор ГСМ» (далее — Сервис) предоставляется ООО «Предрейс» пользователям
исключительно в ознакомительных целях и не гарантирует соответствия фактически совершённым поездкам.

1. Общие положения
Использование Сервиса автоматически означает согласие пользователя с условиями настоящего
Пользовательского соглашения. Если вы не согласны с условиями — прекратите использование Сервиса.

2. Назначение
Сервис предназначен для ориентировочного расчёта пробега, остатков ГСМ и показателей одометра
по данным чеков АЗС в целях восстановления путевых листов на бумажных носителях.
Результаты не являются юридически значимым документом без оформления в установленном порядке.

3. Ответственность пользователя
Пользователь самостоятельно проверяет корректность введённых данных и полученных результатов.
Путевой лист без отметок о прохождении медицинского осмотра водителя и технического контроля
транспортного средства недействителен. Ответственность за оформление путевой документации
несёт организация-пользователь.

4. Ограничение ответственности
Администрация Сервиса не несёт ответственности за убытки, возникшие вследствие использования
или невозможности использования результатов расчёта, а также за ошибки в исходных данных.

5. Персональные данные
Сервис не требует обязательной регистрации. Данные, введённые в форму, обрабатываются
в браузере пользователя и/или на сервере расчёта исключительно для формирования результата
и не предназначены для долгосрочного хранения без согласия пользователя.

6. Контакты
По вопросам Сервиса: +7 (925) 028-87-55, predreis@predreis.info, https://предрейс.рф/
`.trim();

interface Props {
  open: boolean;
  onClose: () => void;
}

export function UserAgreementModal({ open, onClose }: Props) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="ua-title" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h2 id="ua-title">Пользовательское соглашение</h2>
          <button type="button" className="btn-ghost" onClick={onClose} aria-label="Закрыть">
            ✕
          </button>
        </div>
        <div className="modal-body">
          <pre className="agreement-text">{AGREEMENT_TEXT}</pre>
        </div>
        <div className="modal-foot">
          <button type="button" className="btn-primary" onClick={onClose}>
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
}

export function ConsentBanner({ onOpenAgreement }: { onOpenAgreement: () => void }) {
  return (
    <div className="consent-banner">
      <p>
        Сервис предоставляется исключительно в ознакомительных целях и не гарантирует соответствия
        фактически совершённым поездкам. Использование сервиса означает согласие с условиями{' '}
        <button type="button" className="link-btn" onClick={onOpenAgreement}>
          Пользовательского соглашения
        </button>
        .
      </p>
    </div>
  );
}

export function ContactsBlock({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`contacts ${compact ? 'contacts-compact' : ''}`}>
      <div className="brand-mark" aria-hidden="true">
        <span className="brand-mark-glyph">П</span>
        <span className="brand-mark-text">
          ПРЕДРЕЙС
          <small>ONLINE</small>
        </span>
      </div>
      <div className="contacts-list">
        <a href="tel:+79250288755">+7 (925) 028-87-55</a>
        <a href="mailto:predreis@predreis.info">predreis@predreis.info</a>
        <a href="https://предрейс.рф/" target="_blank" rel="noreferrer">
          предрейс.рф
        </a>
      </div>
    </div>
  );
}

export function useAgreementModal() {
  const [open, setOpen] = useState(false);
  return { open, openAgreement: () => setOpen(true), closeAgreement: () => setOpen(false) };
}
