from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .act import build_act
from .calc import calculate
from .forms import generate_form3_excel, generate_form3_pdf
from .forms_4c import generate_form4c_excel, generate_form4c_pdf
from .integration_1c import OneCIntegrationError, is_configured as one_c_configured, sync_act
from .schemas import (
    АктСписанияГСМ,
    ЗапросСинхронизации1С,
    ЗапросФормыПЛ,
    ЗапросФормы4С,
    РезультатРасчёта,
    ВходныеДанные,
)

router = APIRouter(prefix="/api", tags=["calc"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.post("/calculate", response_model=РезультатРасчёта)
def calculate_endpoint(payload: ВходныеДанные) -> РезультатРасчёта:
    """
    Принимает исходные данные калькулятора (см. ВходныеДанные) и возвращает
    рассчитанные путевые листы + предупреждения.

    Валидация входных данных (обязательные поля, диапазоны, попадание дат
    заправок/рабочих дней в расчётный период) выполняется на уровне pydantic
    в схеме ВходныеДанные — при ошибке FastAPI вернёт 422 с деталями.
    """
    return calculate(payload)


@router.post("/form3/excel", tags=["forms"])
def form3_excel(payload: ЗапросФормыПЛ) -> Response:
    """
    Генерирует путевой лист форма №3 (легковой) в Excel — одна книга,
    один лист на каждый рассчитанный путевой лист.
    """
    result = calculate(payload.расчёт)
    if not result.листы:
        raise HTTPException(
            status_code=422,
            detail=["Нет путевых листов для печати: " + "; ".join(result.предупреждения)],
        )
    content = generate_form3_excel(payload, result)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=putevoy-list-forma-3.xlsx"},
    )


@router.post("/form3/pdf", tags=["forms"])
def form3_pdf(payload: ЗапросФормыПЛ) -> Response:
    """
    Генерирует путевой лист форма №3 (легковой) в PDF — одна страница
    на каждый рассчитанный путевой лист.
    """
    result = calculate(payload.расчёт)
    if not result.листы:
        raise HTTPException(
            status_code=422,
            detail=["Нет путевых листов для печати: " + "; ".join(result.предупреждения)],
        )
    content = generate_form3_pdf(payload, result)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=putevoy-list-forma-3.pdf"},
    )


@router.post("/form4c/excel", tags=["forms"])
def form4c_excel(payload: ЗапросФормы4С) -> Response:
    """
    Генерирует путевой лист форма №4-с (грузовой) в Excel — одна книга,
    один лист на каждый рассчитанный путевой лист.
    """
    result = calculate(payload.расчёт)
    if not result.листы:
        raise HTTPException(
            status_code=422,
            detail=["Нет путевых листов для печати: " + "; ".join(result.предупреждения)],
        )
    content = generate_form4c_excel(payload, result)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=putevoy-list-forma-4c.xlsx"},
    )


@router.post("/form4c/pdf", tags=["forms"])
def form4c_pdf(payload: ЗапросФормы4С) -> Response:
    """
    Генерирует путевой лист форма №4-с (грузовой) в PDF — одна страница
    на каждый рассчитанный путевой лист.
    """
    result = calculate(payload.расчёт)
    if not result.листы:
        raise HTTPException(
            status_code=422,
            detail=["Нет путевых листов для печати: " + "; ".join(result.предупреждения)],
        )
    content = generate_form4c_pdf(payload, result)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=putevoy-list-forma-4c.pdf"},
    )


@router.post("/act", response_model=АктСписанияГСМ, tags=["1c"])
def build_act_endpoint(payload: ЗапросСинхронизации1С) -> АктСписанияГСМ:
    """
    Строит сводный Акт на списание ГСМ за период по результату расчёта —
    без обращения к 1С. Полезно, чтобы посмотреть/скачать JSON вручную,
    даже если интеграция с 1С ещё не настроена.
    """
    result = calculate(payload.расчёт)
    if not result.листы:
        raise HTTPException(
            status_code=422,
            detail=["Нет путевых листов для акта: " + "; ".join(result.предупреждения)],
        )
    return build_act(payload, result)


@router.post("/1c/sync", tags=["1c"])
def sync_1c_endpoint(payload: ЗапросСинхронизации1С) -> dict:
    """
    Строит Акт и, если интеграция с 1С настроена (ONE_C_BASE_URL в .env),
    отправляет его в 1С через OData. Если не настроена — возвращает Акт
    с пометкой synced=false, ничего не ломая (см. app/integration_1c.py).
    """
    result = calculate(payload.расчёт)
    if not result.листы:
        raise HTTPException(
            status_code=422,
            detail=["Нет путевых листов для акта: " + "; ".join(result.предупреждения)],
        )
    act = build_act(payload, result)

    if not one_c_configured():
        return {
            "synced": False,
            "reason": "Интеграция с 1С не настроена (ONE_C_BASE_URL). Акт построен, но не отправлен.",
            "акт": act.model_dump(),
        }

    try:
        response = sync_act(act)
    except OneCIntegrationError as exc:
        raise HTTPException(status_code=502, detail=[str(exc)]) from exc

    return {
        "synced": True,
        "идДокумента1С": response.идДокумента if response else None,
        "акт": act.model_dump(),
    }
