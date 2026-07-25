"""
Синхронизация Акта на списание ГСМ с 1С через OData (Шаг 2.3, неделя 5).

Как и geocoding.py / receipt_validation.py — сделано впрок: конкретной
базы 1С и её конфигурации (какой HTTP-сервис/OData-каталог принимает
документы списания) на момент разработки нет, поэтому здесь —
адаптер общего назначения поверх стандартного протокола обмена 1С
(HTTP-сервис или встроенный OData, Basic Auth) — тот же подход, что
используется в адаптере интеграции 1C по OData в других проектах:
конкретная точка входа (URL сущности) настраивается переменной
окружения, а не зашита в код, поэтому подключение к реальной базе — это
конфигурация, а не доработка кода.

Пока ONE_C_BASE_URL не задан — is_configured() == False, sync_act()
тихо возвращает None и не мешает получить сам Акт (эндпоинт всё равно
отдаёт JSON, который можно скачать/импортировать вручную).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx

from .schemas import АктСписанияГСМ

REQUEST_TIMEOUT = 15.0

_client: Optional[httpx.Client] = None


class OneCIntegrationError(Exception):
    """Ошибка обращения к 1С (сеть, авторизация, отказ сервиса)."""


@dataclass(frozen=True)
class ОтветСинхронизации1С:
    успех: bool
    идДокумента: Optional[str]
    сыройОтвет: dict


def _config() -> Optional[dict]:
    base_url = os.getenv("ONE_C_BASE_URL")
    if not base_url:
        return None
    return {
        "base_url": base_url.rstrip("/"),
        "entity": os.getenv("ONE_C_ENTITY", "Document_СписаниеГСМ"),
        "username": os.getenv("ONE_C_USERNAME", ""),
        "password": os.getenv("ONE_C_PASSWORD", ""),
        "verify_ssl": os.getenv("ONE_C_VERIFY_SSL", "true").lower() != "false",
    }


def is_configured() -> bool:
    """True, если задан ONE_C_BASE_URL (адрес OData/HTTP-сервиса 1С)."""
    return _config() is not None


def _get_client(verify_ssl: bool) -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=REQUEST_TIMEOUT, verify=verify_ssl)
    return _client


def set_client(client: httpx.Client) -> None:
    """Подменить HTTP-клиент (для тестов — httpx.MockTransport)."""
    global _client
    _client = client


def act_to_1c_payload(act: АктСписанияГСМ) -> dict:
    """
    Приводит Акт к плоской структуре, типичной для OData-документа 1С
    (поля с большой буквы, табличная часть отдельным массивом) — точный
    состав полей зависит от конфигурации приёмной базы и настраивается
    маппингом на стороне 1С при подключении; здесь — общий вид данных.
    """
    return {
        "Организация": act.организация.наименование,
        "ИНН": act.организация.инн,
        "ТС_Марка": act.марка,
        "ТС_Модель": act.модель,
        "ТС_ГосНомер": act.госномер,
        "ПериодС": act.периодС.isoformat(),
        "ПериодПо": act.периодПо.isoformat(),
        "ИтогоПробегКм": act.итогоПробегКм,
        "ИтогоРасходФактЛ": act.итогоРасходФактЛ,
        "ИтогоРасходНормаЛ": act.итогоРасходНормаЛ,
        "ИтогоЭкономияЛ": act.итогоЭкономияЛ,
        "ТабличнаяЧасть": [
            {
                "НомерПЛ": s.номерПЛ,
                "Дата": s.дата,
                "Водитель": s.водитель,
                "Пробег": s.пробег,
                "РасходФакт": s.расходФакт,
                "РасходНорма": s.расходНорма,
            }
            for s in act.строки
        ],
    }


def sync_act(act: АктСписанияГСМ) -> Optional[ОтветСинхронизации1С]:
    """
    Отправляет Акт в 1С (POST на OData-сущность). Возвращает None, если
    интеграция не настроена (is_configured() == False) — это не ошибка,
    просто синхронизация недоступна. Бросает OneCIntegrationError при
    сетевой ошибке, ошибке авторизации или отказе 1С принять документ.
    """
    cfg = _config()
    if cfg is None:
        return None

    url = f"{cfg['base_url']}/{cfg['entity']}"
    auth = (cfg["username"], cfg["password"]) if cfg["username"] else None

    try:
        resp = _get_client(cfg["verify_ssl"]).post(
            url,
            json=act_to_1c_payload(act),
            auth=auth,
            headers={"Content-Type": "application/json"},
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise OneCIntegrationError(f"Ошибка обращения к 1С: {exc}") from exc

    try:
        data = resp.json()
    except ValueError as exc:
        raise OneCIntegrationError("Некорректный ответ 1С (ожидался JSON)") from exc

    doc_id = data.get("Ref_Key") or data.get("id") or data.get("Number")
    return ОтветСинхронизации1С(успех=True, идДокумента=doc_id, сыройОтвет=data)
