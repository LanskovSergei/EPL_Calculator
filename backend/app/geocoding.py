"""
Клиент Яндекс.Геокодера — превращает текстовый адрес в координаты.

Требует переменную окружения YANDEX_GEOCODER_API_KEY (см. backend/.env.example).
Пока ключ не задан — is_configured() == False, geocode_address() тихо
возвращает None и ничего не ломает: расчёт путевых листов (calc.py) не
зависит от геокодинга, маршрут остаётся текстовым списком адресов как в
неделе 2. Как только ключ появится — просто прописать его в .env, код
готов и протестирован на моках.

Получение ключа: https://developer.tech.yandex.ru/ → сервис
«Геокодер» (JavaScript API и HTTP Геокодер) → бесплатный лимит на старте
достаточен для MVP.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional

import httpx

GEOCODER_URL = "https://geocode-maps.yandex.ru/1.x/"
REQUEST_TIMEOUT = 5.0

_client: Optional[httpx.Client] = None


@dataclass(frozen=True)
class Координаты:
    широта: float
    долгота: float


class GeocoderError(Exception):
    """Ошибка обращения к Яндекс.Геокодеру (сеть, лимиты, неверный ключ, битый ответ)."""


def _api_key() -> Optional[str]:
    return os.getenv("YANDEX_GEOCODER_API_KEY") or None


def is_configured() -> bool:
    """True, если YANDEX_GEOCODER_API_KEY задан в окружении."""
    return _api_key() is not None


def _get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=REQUEST_TIMEOUT)
    return _client


def set_client(client: httpx.Client) -> None:
    """Подменить HTTP-клиент (используется в тестах — httpx.MockTransport)."""
    global _client
    _client = client
    geocode_address.cache_clear()


@lru_cache(maxsize=2048)
def geocode_address(address: str) -> Optional[Координаты]:
    """
    Координаты первого результата геокодирования, либо None, если:
    - адрес пустой;
    - ключ не настроен (is_configured() == False);
    - Яндекс не нашёл ничего по этому адресу.

    Бросает GeocoderError при сетевой ошибке или некорректном ответе API —
    вызывающий код должен её ловить и добавлять предупреждение в расчёт,
    а не прерывать его.
    """
    address = (address or "").strip()
    if not address:
        return None

    key = _api_key()
    if not key:
        return None

    try:
        resp = _get_client().get(
            GEOCODER_URL,
            params={
                "apikey": key,
                "geocode": address,
                "format": "json",
                "results": 1,
            },
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise GeocoderError(f"Ошибка запроса к Яндекс.Геокодеру: {exc}") from exc

    try:
        data = resp.json()
        members = data["response"]["GeoObjectCollection"]["featureMember"]
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocoderError("Некорректный ответ Яндекс.Геокодера") from exc

    if not members:
        return None

    pos = members[0]["GeoObject"]["Point"]["pos"]  # формат: "долгота широта"
    lon_str, lat_str = pos.split(" ")
    return Координаты(широта=float(lat_str), долгота=float(lon_str))


def geocode_many(addresses: List[str]) -> Dict[str, Optional[Координаты]]:
    """
    Геокодирует список адресов. Ошибки по отдельным адресам не прерывают
    остальные — такой адрес просто получит None в результате.
    """
    result: Dict[str, Optional[Координаты]] = {}
    for addr in addresses:
        try:
            result[addr] = geocode_address(addr)
        except GeocoderError:
            result[addr] = None
    return result


# ------- Геометрия: пригодится для валидации маршрута (неделя 3, след. шаг) -------

EARTH_RADIUS_KM = 6371.0


def haversine_km(a: Координаты, b: Координаты) -> float:
    """Расстояние по прямой между двумя точками (км), формула гаверсинуса."""
    import math

    lat1, lon1 = math.radians(a.широта), math.radians(a.долгота)
    lat2, lon2 = math.radians(b.широта), math.radians(b.долгота)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(h))
