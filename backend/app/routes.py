from fastapi import APIRouter

from .calc import calculate
from .schemas import РезультатРасчёта, ВходныеДанные

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
