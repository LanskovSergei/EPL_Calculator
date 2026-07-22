"""
Pydantic-схемы «Калькулятора ГСМ».

Поля называются так же, как в src/types.ts фронтенда (кириллица),
чтобы объект формы можно было отправлять на бэкенд без перекладки ключей.
"""
from __future__ import annotations

from datetime import date, time
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class ТипТС(str, Enum):
    легковой = "легковой"
    грузовой = "грузовой"


class ВидТоплива(str, Enum):
    бензин = "бензин"
    дизель = "дизель"


class ВидСообщения(str, Enum):
    городское = "городское"
    пригородное = "пригородное"
    междугородное = "междугородное"
    международное = "международное"


class Водитель(BaseModel):
    фио: str = ""
    дни: List[date] = Field(default_factory=list)  # отмеченные рабочие дни


class Заправка(BaseModel):
    дата: date
    время: Optional[time] = None
    объём: float = Field(gt=0)

    @field_validator("объём")
    @classmethod
    def _volume_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Объём заправки должен быть больше нуля")
        return v


class ВходныеДанные(BaseModel):
    марка: str = ""
    модель: str = ""
    типТС: ТипТС = ТипТС.легковой
    видТоплива: ВидТоплива = ВидТоплива.бензин
    объёмБака: Optional[float] = Field(default=None, gt=0)
    среднийРасход: Optional[float] = Field(default=None, gt=0)
    старше10лет: bool = False
    прицепГруз: bool = False
    спецтехника: bool = False
    периодС: date
    периодПо: date
    видСообщения: ВидСообщения = ВидСообщения.городское
    срокРейсаДней: Optional[int] = Field(default=None, ge=1)
    одометрНаНачало: Optional[float] = Field(default=None, ge=0)
    остатокНаНачало: float = Field(default=0, ge=0)
    водители: List[Водитель] = Field(default_factory=list)
    заправки: List[Заправка] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_business_rules(self) -> "ВходныеДанные":
        if self.периодПо < self.периодС:
            raise ValueError("«Период по» не может быть раньше «Периода с»")

        if self.спецтехника and not self.среднийРасход:
            raise ValueError("Для спецтехники средний расход обязателен")

        if not self.водители:
            raise ValueError("Нужен хотя бы один водитель")

        multi_day = self.видСообщения in (
            ВидСообщения.междугородное,
            ВидСообщения.международное,
        )
        if multi_day and not self.срокРейсаДней:
            raise ValueError(
                "Для междугородного/международного сообщения укажите срок рейса в днях"
            )

        for drv in self.водители:
            for d in drv.дни:
                if d < self.периодС or d > self.периодПо:
                    raise ValueError(
                        f"Рабочий день {d.isoformat()} водителя «{drv.фио or '—'}» "
                        f"вне расчётного периода"
                    )

        for r in self.заправки:
            if r.дата < self.периодС or r.дата > self.периодПо:
                raise ValueError(
                    f"Заправка от {r.дата.isoformat()} вне расчётного периода"
                )

        return self


# ------- Результат -------


class ПутевойЛист(BaseModel):
    номер: int
    выпуск: str
    возвращение: str
    водитель: str
    общееВремя: float
    одометрВыдача: float
    одометрЗакрытие: float
    пробег: float
    остатокВыдача: float
    остатокЗакрытие: float
    расходНорма: float
    расходФакт: float
    видСообщения: ВидСообщения


class ПримененныйКоэффициент(BaseModel):
    name: str
    value: float


class СводкаРасхода(BaseModel):
    effective: float
    base: float
    applied: List[ПримененныйКоэффициент]
    note: str


class РезультатРасчёта(BaseModel):
    листы: List[ПутевойЛист]
    предупреждения: List[str]
    расход: Optional[СводкаРасхода] = None
