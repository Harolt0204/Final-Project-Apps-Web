"""Similarity checks, administrative requirements and settings (Sprint 4)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db import get_db
from app.models import RequirementType, Student, SystemSetting, User, UserRole
from app.schemas.compliance import (
    RequirementSet,
    RequirementTypeCreate,
    RequirementTypeOut,
    RequirementTypeUpdate,
    SettingOut,
    SettingUpdate,
    SimilarityCheckCreate,
    SimilarityCheckOut,
    SimilarityOut,
    StudentRequirementsOut,
)
from app.services import compliance
from app.services.access import get_visible_thesis

router = APIRouter(prefix="/api")
admin_only = Depends(require_roles(UserRole.ADMIN))


def _checklist(db: Session, student: Student) -> StudentRequirementsOut:
    items = compliance.requirement_checklist(db, student)
    return StudentRequirementsOut(
        student_id=student.student_id,
        student_name=student.full_name,
        complete=all(i["status"] == "CERTIFIED" for i in items),
        items=items,
    )


# ------------------------------------------------------------------------- similarity


@router.get(
    "/theses/{thesis_id}/similarity-checks", response_model=SimilarityOut, tags=["Similarity"]
)
def list_similarity_checks(
    thesis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SimilarityOut:
    thesis = get_visible_thesis(db, user, thesis_id)
    return SimilarityOut(
        threshold=compliance.similarity_threshold(db),
        checks=[SimilarityCheckOut.model_validate(c) for c in thesis.similarity_checks],
    )


@router.post(
    "/theses/{thesis_id}/similarity-checks",
    response_model=SimilarityCheckOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Similarity"],
)
def record_similarity_check(
    thesis_id: int,
    data: SimilarityCheckCreate,
    user: User = admin_only,
    db: Session = Depends(get_db),
):
    """Record a check. The verdict is computed from the threshold in force."""
    return compliance.record_similarity_check(
        db,
        user,
        thesis_id,
        data.similarity_percentage,
        data.tool,
        data.checked_at,
        str(data.report_url) if data.report_url else None,
        data.notes,
    )


# ----------------------------------------------------------------------- requirements


@router.get("/requirement-types", response_model=list[RequirementTypeOut], tags=["Requirements"])
def list_requirement_types(
    include_inactive: bool = Query(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(RequirementType).order_by(RequirementType.sort_order, RequirementType.name)
    if not (include_inactive and user.role == UserRole.ADMIN):
        query = query.where(RequirementType.is_active.is_(True))
    return list(db.scalars(query))


@router.post(
    "/requirement-types",
    response_model=RequirementTypeOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Requirements"],
    dependencies=[admin_only],
)
def create_requirement_type(data: RequirementTypeCreate, db: Session = Depends(get_db)):
    for field in ("code", "name"):
        value = getattr(data, field)
        if db.scalars(
            select(RequirementType).where(getattr(RequirementType, field) == value)
        ).first():
            raise HTTPException(status.HTTP_409_CONFLICT, f"A requirement with this {field} exists")
    rtype = RequirementType(**data.model_dump())
    db.add(rtype)
    db.commit()
    db.refresh(rtype)
    return rtype


@router.patch(
    "/requirement-types/{type_id}",
    response_model=RequirementTypeOut,
    tags=["Requirements"],
    dependencies=[admin_only],
)
def update_requirement_type(
    type_id: int, data: RequirementTypeUpdate, db: Session = Depends(get_db)
):
    rtype = db.get(RequirementType, type_id)
    if rtype is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Requirement type not found")
    changes = data.model_dump(exclude_unset=True, exclude_none=True)
    if "name" in changes:
        clash = select(RequirementType).where(
            RequirementType.name == changes["name"], RequirementType.requirement_type_id != type_id
        )
        if db.scalars(clash).first():
            raise HTTPException(status.HTTP_409_CONFLICT, "A requirement with this name exists")
    for field, value in changes.items():
        setattr(rtype, field, value)
    db.commit()
    db.refresh(rtype)
    return rtype


@router.get(
    "/students/{student_id}/requirements",
    response_model=StudentRequirementsOut,
    tags=["Requirements"],
)
def student_requirements(
    student_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StudentRequirementsOut:
    """Administrators see anyone's checklist; a student only their own."""
    if user.role != UserRole.ADMIN and user.student_id != student_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    return _checklist(db, student)


@router.get(
    "/theses/{thesis_id}/requirements",
    response_model=StudentRequirementsOut,
    tags=["Requirements"],
)
def thesis_requirements(
    thesis_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> StudentRequirementsOut:
    """The student's checklist, for every participant of the thesis (e.g. the tutor)."""
    thesis = get_visible_thesis(db, user, thesis_id)
    return _checklist(db, thesis.student)


@router.put(
    "/students/{student_id}/requirements/{type_id}",
    response_model=StudentRequirementsOut,
    tags=["Requirements"],
)
def set_requirement(
    student_id: int,
    type_id: int,
    data: RequirementSet,
    user: User = admin_only,
    db: Session = Depends(get_db),
) -> StudentRequirementsOut:
    """Certify a requirement, or record that it was rejected (with a note)."""
    student = compliance.set_requirement(
        db,
        user,
        student_id,
        type_id,
        data.status,
        str(data.evidence_url) if data.evidence_url else None,
        data.notes,
    )
    return _checklist(db, student)


@router.delete(
    "/students/{student_id}/requirements/{type_id}",
    response_model=StudentRequirementsOut,
    tags=["Requirements"],
    dependencies=[admin_only],
)
def clear_requirement(
    student_id: int, type_id: int, db: Session = Depends(get_db)
) -> StudentRequirementsOut:
    """Back to pending."""
    return _checklist(db, compliance.clear_requirement(db, student_id, type_id))


# --------------------------------------------------------------------------- settings


@router.get("/settings", response_model=list[SettingOut], tags=["Settings"])
def list_settings(_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list(db.scalars(select(SystemSetting).order_by(SystemSetting.setting_key)))


@router.put(
    "/settings/{key}", response_model=SettingOut, tags=["Settings"], dependencies=[admin_only]
)
def update_setting(key: str, data: SettingUpdate, db: Session = Depends(get_db)):
    return compliance.update_setting(db, key, data.value)
