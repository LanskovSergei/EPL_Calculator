"""
Валидация кассовых чеков с АЗС через ОФД (проверка подлинности по данным
ФНС) — задача недели 4 плана.

Контекст из уточнений заказчика: «На первом этапе проверку подлинности
можно не проводить... В базовой версии калькулятора нам требуются только
данные об объёме заправки в литрах». Валидация чеков становится
актуальной на шаге формирования «Акта на списание ГСМ» (следующие этапы),
где чек — основание для бухгалтерского списания.

Поэтому этот модуль, как и geocoding.py, сделан «впрок»: интерфейс и
парсинг готовы и покрыты тестами на моках, а реальное обращение к сервису
проверки чеков (proverkacheka.com либо API ФНС/OFD) включается одной
переменной окружения, когда появится токен доступа. Пока токен не
задан — is_configured() == False, модуль ничего не ломает и не
используется в основном расчёте.

Формат QR-кода на кассовом чеке (стандарт ФНС) — строка вида:
    t=20250601T0800&s=1234.56&fn=9287440300123456&i=45678&fp=1234567890&n=1
где: t — дата/время, s — сумма чека (руб.), fn — номер фискального
накопителя, i — номер фискального документа, fp — фискальный признак,
n — тип операции (1 = приход).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Optional
from urllib.parse import parse_qs

import httpx

PROVERKACHEKA_URL = "https://proverkacheka.com/api/v1/check/get"
REQUEST_TIMEOUT = 10.0

_client: Optional[httpx.Client] = None


class ReceiptParseError(Exception):
    """QR-строка не соответствует стандартному формату ФНС."""


class ReceiptValidationError(Exception):
    """Ошибка обращения к сервису проверки чеков (сеть, лимиты, неверный токен)."""


@dataclass(frozen=True)
class РеквизитыЧека:
    дата: datetime
    сумма: float  # руб.
    фн: str  # номер фискального накопителя
    фд: str  # номер фискального документа
    фп: str  # фискальный признак
    типОперации: int = 1  # 1 = приход


@dataclass(frozen=True)
class РезультатПроверки:
    найден: bool
    сырыеДанные: Optional[dict] = None


def parse_qr(qr: str) -> РеквизитыЧека:
    """
    Разбирает строку QR-кода с чека в реквизиты для проверки.
    Бросает ReceiptParseError, если обязательные поля (t, s, fn, i, fp)
    отсутствуют или не парсятся.
    """
    try:
        parsed = parse_qs(qr.strip().lstrip("?"))
        t = parsed["t"][0]
        s = parsed["s"][0]
        fn = parsed["fn"][0]
        i = parsed["i"][0]
        fp = parsed["fp"][0]
        n = int(parsed.get("n", ["1"])[0])
    except (KeyError, IndexError, ValueError) as exc:
        raise ReceiptParseError(f"Не удалось разобрать QR чека: {exc}") from exc

    # Формат даты в QR — либо "20250601T0800", либо с секундами "...T080000"
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            dt = datetime.strptime(t, fmt)
            break
        except ValueError:
            continue
    else:
        raise ReceiptParseError(f"Не удалось разобрать дату/время чека: {t!r}")

    try:
        amount = float(s)
    except ValueError as exc:
        raise ReceiptParseError(f"Не удалось разобрать сумму чека: {s!r}") from exc

    return РеквизитыЧека(дата=dt, сумма=amount, фн=fn, фд=i, фп=fp, типОперации=n)


def _token() -> Optional[str]:
    return os.getenv("OFD_CHECK_TOKEN") or None


def is_configured() -> bool:
    """True, если задан токен сервиса проверки чеков (OFD_CHECK_TOKEN)."""
    return _token() is not None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=REQUEST_TIMEOUT)
    return _client


def set_client(client: httpx.Client) -> None:
    """Подменить HTTP-клиент (для тестов — httpx.MockTransport)."""
    global _client
    _client = client
    validate_receipt.cache_clear()


@lru_cache(maxsize=1024)
def validate_receipt(req: РеквизитыЧека) -> Optional[РезультатПроверки]:
    """
    Проверяет чек по реквизитам через сервис проверки чеков ФНС/ОФД.

    Возвращает None, если токен не настроен (is_configured() == False) —
    вызывающий код должен считать это «проверка недоступна», не ошибкой.
    Бросает ReceiptValidationError при сетевой ошибке или некорректном
    ответе сервиса.
    """
    token = _token()
    if token is None:
        return None

    try:
        resp = _get_client().post(
            PROVERKACHEKA_URL,
            data={
                "token": token,
                "qr": (
                    f"t={req.дата.strftime('%Y%m%dT%H%M')}&s={req.сумма}"
                    f"&fn={req.фн}&i={req.фд}&fp={req.фп}&n={req.типОперации}"
                ),
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise ReceiptValidationError(f"Ошибка запроса к сервису проверки чеков: {exc}") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise ReceiptValidationError("Некорректный ответ сервиса проверки чеков") from exc

    found = bool(data.get("code") == 1 or data.get("found") is True)
    return РезультатПроверки(найден=found, сырыеДанные=data)


def extract_fuel_volume_liters(check_payload: dict) -> Optional[float]:
    """
    Пытается вытащить объём топлива (л) из позиций чека, если сервис
    проверки вернул детализацию (поле "items"/"товары" — формат зависит
    от конкретного ОФД-провайдера, здесь — распространённый вариант).
    Возвращает None, если структура не распознана — вызывающий код в
    этом случае должен использовать объём, введённый пользователем вручную
    (как и раньше, по ТЗ — «какие данные вбили, тот подсчёт и получили»).
    """
    items = check_payload.get("items") or check_payload.get("data", {}).get("items")
    if not items:
        return None
    for item in items:
        name = str(item.get("name", "")).lower()
        if any(kw in name for kw in ("бензин", "дт", "дизел", "аи-", "газ")):
            qty = item.get("quantity")
            if qty is not None:
                try:
                    return float(qty)
                except (TypeError, ValueError):
                    return None
    return None
