"""Schools and academic periods."""

import datetime as dt
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]
Code = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9-]{1,20}$")
]
PeriodName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class SchoolOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    school_id: int
    code: str
    name: str


class SchoolCreate(BaseModel):
    code: Code
    name: Name


class SchoolUpdate(BaseModel):
    code: Code | None = None
    name: Name | None = None


class PeriodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    period_id: int
    name: str
    start_date: dt.date | None
    end_date: dt.date | None


class PeriodCreate(BaseModel):
    name: PeriodName
    start_date: dt.date
    end_date: dt.date

    @model_validator(mode="after")
    def check_dates(self) -> "PeriodCreate":
        # Mirrors ck_academic_periods_dates (I-10).
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        return self


class PeriodUpdate(BaseModel):
    name: PeriodName | None = None
    start_date: dt.date | None = None
    end_date: dt.date | None = None
