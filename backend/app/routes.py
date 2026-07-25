from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from .calc import calculate
from .forms import generate_form3_excel, generate_form3_pdf
from .schemas import ЗапросФормыПЛ, РезультатРасчёта, ВходныеДанные

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
