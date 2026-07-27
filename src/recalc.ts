/*
 * Обратный пересчёт путевых листов после ручной правки полей результата (ТЗ).
 * Цепочка: закрытие листа i → выдача листа i+1; пробег ↔ расход через л/100км.
 */
import type { ПутевойЛист } from './types';

function round(n: number, digits: number): number {
  const f = 10 ** digits;
  return Math.round(n * f) / f;
}

/** Синхронизирует зависимые поля и протаскивает одометр/остаток по цепочке листов. */
export function recalculateSheets(
  листы: ПутевойЛист[],
  расходЛ100: number | null,
): ПутевойЛист[] {
  const out = листы.map((л) => ({
    ...л,
    маршрут: л.маршрут ? [...л.маршрут] : [],
  }));

  for (let i = 0; i < out.length; i++) {
    const л = out[i];
    const пробег = Math.max(0, Number(л.пробег) || 0);
    л.пробег = round(пробег, 1);

    if (расходЛ100 && расходЛ100 > 0) {
      const burn = round((пробег * расходЛ100) / 100, 2);
      л.расходФакт = burn;
      л.расходНорма = burn;
    }

    л.одометрЗакрытие = round((Number(л.одометрВыдача) || 0) + л.пробег, 1);

    if (i + 1 < out.length) {
      out[i + 1].одометрВыдача = л.одометрЗакрытие;
      out[i + 1].остатокВыдача = Number(л.остатокЗакрытие) || 0;
    }
  }

  return out;
}

/** Ссылка на маршрут в Яндекс.Картах по текстовым адресам. */
export function yandexMapsRouteUrl(stops: string[]): string | null {
  const clean = stops.map((s) => s.trim()).filter(Boolean);
  if (clean.length < 2) return null;
  const rtext = clean.map(encodeURIComponent).join('~');
  return `https://yandex.ru/maps/?rtext=${rtext}&rtt=auto`;
}
