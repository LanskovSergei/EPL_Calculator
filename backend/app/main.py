import os

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import router

app = FastAPI(
    title="Калькулятор ГСМ — API",
    description="Бэкенд эндпоинтов расчёта пробега/расхода ГСМ (Шаг 1.1 ТЗ).",
    version="0.1.0",
)

# Разрешённые origin'ы для CORS: через переменную окружения, через запятую.
# По умолчанию — локальная разработка (Vite dev-сервер).
_origins = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _origins if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Человекочитаемые сообщения об ошибках валидации вместо сырого pydantic-дампа."""
    messages = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", []) if p != "body")
        msg = err.get("msg", "Некорректное значение")
        messages.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(status_code=422, content={"detail": messages})


app.include_router(router)
