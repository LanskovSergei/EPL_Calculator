import { describe, it, expect, vi, afterEach } from 'vitest';
import { calculateViaApi, calculateSmart, toApiPayload, ApiError } from './api';
import type { ВходныеДанные } from './types';

function baseInput(overrides: Partial<ВходныеДанные> = {}): ВходныеДанные {
  return {
    марка: 'Hyundai',
    модель: 'Porter 2',
    типТС: 'грузовой',
    видТоплива: 'дизель',
    объёмБака: 100,
    среднийРасход: '',
    старше10лет: false,
    прицепГруз: false,
    спецтехника: false,
    периодС: '2025-06-01',
    периодПо: '2025-06-30',
    видСообщения: 'городское',
    срокРейсаДней: '',
    одометрНаНачало: 32000,
    остатокНаНачало: 15,
    водители: [{ фио: 'Иванов И.И.', дни: new Set(['2025-06-02', '2025-06-04']) }],
    заправки: [{ дата: '2025-06-01', время: '08:00', объём: 40 }],
    ...overrides,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('toApiPayload', () => {
  it('превращает Set дней водителя в обычный массив', () => {
    const payload = toApiPayload(baseInput());
    const drv = (payload.водители as any[])[0];
    expect(Array.isArray(drv.дни)).toBe(true);
    expect(drv.дни.sort()).toEqual(['2025-06-02', '2025-06-04']);
  });

  it('превращает пустые числовые поля в null', () => {
    const payload = toApiPayload(baseInput({ среднийРасход: '', одометрНаНачало: '' }));
    expect(payload.среднийРасход).toBeNull();
    expect(payload.одометрНаНачало).toBeNull();
  });

  it('отфильтровывает заправки без даты/объёма', () => {
    const payload = toApiPayload(
      baseInput({
        заправки: [
          { дата: '2025-06-01', время: '08:00', объём: 40 },
          { дата: '', время: '', объём: '' },
        ],
      })
    );
    expect((payload.заправки as any[]).length).toBe(1);
  });

  it('передаёт адрес заправки и адрес стоянки, если заданы', () => {
    const payload = toApiPayload(
      baseInput({
        адресСтоянки: 'г. Москва, ул. Ленина, 1',
        заправки: [{ дата: '2025-06-01', время: '08:00', объём: 40, адрес: 'АЗС Лукойл' }],
      })
    );
    expect(payload.адресСтоянки).toBe('г. Москва, ул. Ленина, 1');
    expect((payload.заправки as any[])[0].адрес).toBe('АЗС Лукойл');
  });
});

describe('calculateViaApi', () => {
  it('возвращает результат при успешном ответе бэкенда', async () => {
    const fakeResult = { листы: [{ номер: 1 }], предупреждения: [], расход: null };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => fakeResult,
      })
    );

    const result = await calculateViaApi(baseInput());
    expect(result).toEqual(fakeResult);
  });

  it('бросает ApiError со списком сообщений при 422', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: ['Нужен хотя бы один водитель'] }),
      })
    );

    await expect(calculateViaApi(baseInput())).rejects.toBeInstanceOf(ApiError);
  });
});

describe('calculateSmart', () => {
  it('использует ответ бэкенда, если он доступен', async () => {
    const fakeResult = { листы: [{ номер: 1 }], предупреждения: [], расход: null };
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, json: async () => fakeResult })
    );

    const result = await calculateSmart(baseInput());
    expect(result).toEqual(fakeResult);
  });

  it('показывает ошибку валидации бэкенда без отката на офлайн-движок', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: async () => ({ detail: ['Нужен хотя бы один водитель'] }),
      })
    );

    const result = await calculateSmart(baseInput());
    expect(result.предупреждения).toContain('Нужен хотя бы один водитель');
    expect(result.листы).toEqual([]);
  });

  it('откатывается на офлайн-движок, если бэкенд недоступен по сети', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('Failed to fetch'))
    );

    const result = await calculateSmart(baseInput());
    // офлайн-движок должен был отработать и дать хотя бы один путевой лист
    expect(result.листы.length).toBeGreaterThan(0);
    expect(result.предупреждения.some((w) => w.includes('Бэкенд недоступен'))).toBe(true);
  });
});
