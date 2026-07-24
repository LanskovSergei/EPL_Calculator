/*
 * Клиент к бэкенду «Калькулятора ГСМ» (POST /api/calculate).
 *
 * Бэкенд ждёт те же поля, что и форма (см. src/types.ts / backend/app/schemas.py),
 * но:
 *  - Водитель.дни во фронте — Set<string>, бэкенду нужен обычный массив;
 *  - пустые числовые поля ('') нужно превращать в null для pydantic.
 *
 * Если бэкенд недоступен (сеть, CORS, сервер не запущен) — calculateSmart()
 * прозрачно откатывается на офлайн-движок calc.ts и добавляет об этом
 * предупреждение, чтобы пользователь понимал, что считалось локально.
 */
import type { ВходныеДанные, РезультатРасчёта } from './types';
import { calculate as calculateOffline } from './calc';

const API_BASE = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8000';

function numOrNull(v: number | '' | null | undefined): number | null {
  return v === '' || v === null || v === undefined ? null : v;
}

export function toApiPayload(input: ВходныеДанные): Record<string, unknown> {
  return {
    ...input,
    объёмБака: numOrNull(input.объёмБака),
    среднийРасход: numOrNull(input.среднийРасход),
    срокРейсаДней: numOrNull(input.срокРейсаДней),
    одометрНаНачало: numOrNull(input.одометрНаНачало),
    остатокНаНачало: numOrNull(input.остатокНаНачало) ?? 0,
    водители: input.водители.map((d) => ({
      фио: d.фио,
      дни: Array.from(d.дни),
    })),
    заправки: input.заправки
      .filter((r) => r.дата && r.объём !== '')
      .map((r) => ({
        дата: r.дата,
        время: r.время || null,
        объём: r.объём,
        адрес: r.адрес || null,
      })),
  };
}

export class ApiError extends Error {
  detail: string[];
  constructor(detail: string[]) {
    super(detail.join('; '));
    this.detail = detail;
  }
}

/** Прямой вызов бэкенда. Бросает ApiError при 4xx/5xx, обычный Error — при сетевой ошибке. */
export async function calculateViaApi(input: ВходныеДанные): Promise<РезультатРасчёта> {
  const resp = await fetch(`${API_BASE}/api/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(toApiPayload(input)),
  });

  if (!resp.ok) {
    const body = await resp.json().catch(() => null);
    const detail: string[] = Array.isArray(body?.detail)
      ? body.detail
      : [body?.detail ?? `Сервер вернул ошибку ${resp.status}`];
    throw new ApiError(detail);
  }

  return resp.json();
}

/**
 * «Умный» расчёт: сначала пробует бэкенд, при недоступности сервера
 * (не при ошибке валидации!) — считает локально через calc.ts и явно
 * предупреждает об этом в результате.
 */
export async function calculateSmart(input: ВходныеДанные): Promise<РезультатРасчёта> {
  try {
    return await calculateViaApi(input);
  } catch (err) {
    if (err instanceof ApiError) {
      // Ошибка валидации на бэкенде — это про данные, а не про доступность сервера.
      return { листы: [], предупреждения: err.detail, расход: null };
    }
    // Сеть/CORS/сервер не поднят — тихий откат на офлайн-движок.
    const offline = calculateOffline(input);
    return {
      ...offline,
      предупреждения: [
        'Бэкенд недоступен — расчёт выполнен локально (офлайн-движок). ' +
          'Маршрут по адресам АЗС в офлайн-режиме не строится.',
        ...offline.предупреждения,
      ],
    };
  }
}
