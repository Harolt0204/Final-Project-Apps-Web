"""Similarity checks, administrative requirements and settings (Sprint 4)."""

import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from app.models import RequirementStatus, SimilarityVerdict

Text100 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Url = Annotated[AnyHttpUrl, Field(max_length=500)]
Code = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z0-9_-]{1,30}$")
]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------------- similarity


class SimilarityCheckCreate(BaseModel):
    similarity_percentage: Annotated[Decimal, Field(ge=0, le=100, max_digits=5, decimal_places=2)]
    tool: Text100
    # When the report was produced. Defaults to now; cannot be in the future.
    checked_at: dt.datetime | None = None
    report_url: Url | None = None
    notes: Notes | None = None


class SimilarityCheckOut(ORMModel):
    check_id: int
    similarity_percentage: Decimal
    checked_at: dt.datetime
    tool: str
    threshold_applied: Decimal
    verdict: SimilarityVerdict
    report_url: str | None
    notes: str | None
    recorded_by_name: str | None


class SimilarityOut(BaseModel):
    """History of checks plus the threshold currently in force."""

    threshold: Decimal
    checks: list[SimilarityCheckOut]


# ----------------------------------------------------------------------- requirements


class RequirementTypeOut(ORMModel):
    requirement_type_id: int
    code: str
    name: str
    description: str | None
    is_active: bool
    sort_order: int


class RequirementTypeCreate(BaseModel):
    code: Code
    name: Name
    description: Annotated[str, StringConstraints(max_length=2000)] | None = None
    is_active: bool = True
    sort_order: Annotated[int, Field(ge=0, le=9999)] = 0


class RequirementTypeUpdate(BaseModel):
    name: Name | None = None
    description: Annotated[str, StringConstraints(max_length=2000)] | None = None
    is_active: bool | None = None
    sort_order: Annotated[int, Field(ge=0, le=9999)] | None = None


class RequirementSet(BaseModel):
    status: RequirementStatus
    evidence_url: Url | None = None
    notes: Notes | None = None

    @model_validator(mode="after")
    def rejection_needs_note(self) -> "RequirementSet":
        # Mirrors ck_student_requirements_rejected_note.
        if self.status == RequirementStatus.REJECTED and not self.notes:
            raise ValueError("A rejected requirement needs a note explaining why")
        return self


class RequirementItemOut(BaseModel):
    requirement_type: RequirementTypeOut
    status: Literal["PENDING", "CERTIFIED", "REJECTED"]
    certified_at: dt.datetime | None
    certified_by_name: str | None
    evidence_url: str | None
    notes: str | None


class StudentRequirementsOut(BaseModel):
    student_id: int
    student_name: str
    complete: bool
    items: list[RequirementItemOut]


# --------------------------------------------------------------------------- settings


class SettingOut(ORMModel):
    setting_key: str
    value: str
    description: str | None


class SettingUpdate(BaseModel):
    value: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]


__all__ = [
    "RequirementItemOut",
    "RequirementSet",
    "RequirementTypeCreate",
    "RequirementTypeOut",
    "RequirementTypeUpdate",
    "SettingOut",
    "SettingUpdate",
    "SimilarityCheckCreate",
    "SimilarityCheckOut",
    "SimilarityOut",
    "StudentRequirementsOut",
]
