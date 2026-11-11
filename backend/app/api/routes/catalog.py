"""Schools and academic periods. Any logged-in user can read them; admins edit them."""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db import get_db
from app.models import AcademicPeriod, School, UserRole, thesis_period
from app.schemas.catalog import (
    PeriodCreate,
    PeriodOut,
    PeriodUpdate,
    SchoolCreate,
    SchoolOut,
    SchoolUpdate,
)

router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])
admin = [Depends(require_roles(UserRole.ADMIN))]


def _unique(db: Session, model, field: str, value, own_id: int | None, label: str) -> None:
    pk = model.__mapper__.primary_key[0]
    query = select(model).where(getattr(model, field) == value)
    if own_id is not None:
        query = query.where(pk != own_id)
    if db.scalars(query).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"{label} already exists")


def _get_or_404(db: Session, model, pk: int, label: str):
    obj = db.get(model, pk)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"{label} not found")
    return obj


# ----------------------------------------------------------------------------- schools


@router.get("/schools", response_model=list[SchoolOut], tags=["Schools"])
def list_schools(db: Session = Depends(get_db)) -> list[School]:
    return list(db.scalars(select(School).order_by(School.name)))


@router.post(
    "/schools", response_model=SchoolOut, status_code=201, tags=["Schools"], dependencies=admin
)
def create_school(data: SchoolCreate, db: Session = Depends(get_db)) -> School:
    _unique(db, School, "code", data.code, None, "A school with this code")
    _unique(db, School, "name", data.name, None, "A school with this name")
    school = School(**data.model_dump())
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


@router.patch(
    "/schools/{school_id}", response_model=SchoolOut, tags=["Schools"], dependencies=admin
)
def update_school(school_id: int, data: SchoolUpdate, db: Session = Depends(get_db)) -> School:
    school = _get_or_404(db, School, school_id, "School")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "code" in changes:
        _unique(db, School, "code", changes["code"], school_id, "A school with this code")
    if "name" in changes:
        _unique(db, School, "name", changes["name"], school_id, "A school with this name")
    for field, value in changes.items():
        setattr(school, field, value)
    db.commit()
    db.refresh(school)
    return school


# ----------------------------------------------------------------------------- periods


@router.get("/periods", response_model=list[PeriodOut], tags=["Academic periods"])
def list_periods(db: Session = Depends(get_db)) -> list[AcademicPeriod]:
    return list(db.scalars(select(AcademicPeriod).order_by(AcademicPeriod.start_date.desc())))


@router.post(
    "/periods",
    response_model=PeriodOut,
    status_code=201,
    tags=["Academic periods"],
    dependencies=admin,
)
def create_period(data: PeriodCreate, db: Session = Depends(get_db)) -> AcademicPeriod:
    _unique(db, AcademicPeriod, "name", data.name, None, "A period with this name")
    period = AcademicPeriod(**data.model_dump())
    db.add(period)
    db.commit()
    db.refresh(period)
    return period


@router.patch(
    "/periods/{period_id}",
    response_model=PeriodOut,
    tags=["Academic periods"],
    dependencies=admin,
)
def update_period(
    period_id: int, data: PeriodUpdate, db: Session = Depends(get_db)
) -> AcademicPeriod:
    period = _get_or_404(db, AcademicPeriod, period_id, "Period")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes:
        _unique(db, AcademicPeriod, "name", changes["name"], period_id, "A period with this name")
    start = changes.get("start_date", period.start_date)
    end = changes.get("end_date", period.end_date)
    if start and end and start >= end:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "start_date must be before end_date"
        )
    for field, value in changes.items():
        setattr(period, field, value)
    db.commit()
    db.refresh(period)
    return period


@router.delete(
    "/periods/{period_id}", status_code=204, tags=["Academic periods"], dependencies=admin
)
def delete_period(period_id: int, db: Session = Depends(get_db)) -> Response:
    period = _get_or_404(db, AcademicPeriod, period_id, "Period")
    if db.scalar(select(exists().where(thesis_period.c.period_id == period_id))):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "This period has theses and cannot be deleted"
        )
    db.delete(period)
    db.commit()
    return Response(status_code=204)
