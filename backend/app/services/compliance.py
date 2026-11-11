"""Similarity checks (FR-07), administrative requirements (FR-10) and system settings.

These are the inputs of the pre-defense gate: a thesis can only be approved for defense
when its latest similarity check is accepted and the student has every active
requirement certified (see app.services.workflow).
"""

import datetime as dt
from decimal import Decimal, InvalidOperation

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    PlagiarismCheck,
    RequirementStatus,
    RequirementType,
    SimilarityVerdict,
    Student,
    StudentRequirement,
    SystemSetting,
    Thesis,
    ThesisStatus,
    User,
)

SIMILARITY_KEY = "similarity_max_percentage"
DEFAULT_SIMILARITY_MAX = Decimal("10.00")
MIN_GRADE_KEY = "defense_min_passing_grade"
DEFAULT_MIN_GRADE = Decimal("7.00")
# A similarity check needs a manuscript: from Thesis II until the committee review ends.
SIMILARITY_STATUSES = {ThesisStatus.THESIS_II, ThesisStatus.IN_REVIEW}


def _now() -> dt.datetime:
    return dt.datetime.now().replace(microsecond=0)


# -------------------------------------------------------------------------- settings


def _number_between(low: int, high: int):
    def validate(value: str) -> str:
        try:
            number = Decimal(value).quantize(Decimal("0.01"))
        except InvalidOperation:
            raise ValueError("must be a number") from None
        if not Decimal(low) <= number <= Decimal(high):
            raise ValueError(f"must be between {low} and {high}")
        return str(number)

    return validate


# Known settings and how their value is validated and normalized.
SETTING_VALIDATORS = {
    SIMILARITY_KEY: _number_between(0, 100),
    MIN_GRADE_KEY: _number_between(0, 10),
}


def _decimal_setting(db: Session, key: str, default: Decimal) -> Decimal:
    setting = db.get(SystemSetting, key)
    return Decimal(setting.value) if setting else default


def similarity_threshold(db: Session) -> Decimal:
    return _decimal_setting(db, SIMILARITY_KEY, DEFAULT_SIMILARITY_MAX)


def min_passing_grade(db: Session) -> Decimal:
    return _decimal_setting(db, MIN_GRADE_KEY, DEFAULT_MIN_GRADE)


def update_setting(db: Session, key: str, value: str) -> SystemSetting:
    validator = SETTING_VALIDATORS.get(key)
    if validator is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown setting")
    try:
        normalized = validator(value)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"{key} {exc}") from None
    setting = db.get(SystemSetting, key)
    if setting is None:
        setting = SystemSetting(setting_key=key, value=normalized)
        db.add(setting)
    else:
        setting.value = normalized
    db.commit()
    db.refresh(setting)
    return setting


# ------------------------------------------------------------------- similarity check


def record_similarity_check(
    db: Session,
    user: User,
    thesis_id: int,
    percentage: Decimal,
    tool: str,
    checked_at: dt.datetime | None,
    report_url: str | None,
    notes: str | None,
) -> PlagiarismCheck:
    thesis = db.scalars(
        select(Thesis).where(Thesis.thesis_id == thesis_id).with_for_update()
    ).first()
    if thesis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Thesis not found")
    if thesis.status not in SIMILARITY_STATUSES:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Similarity checks are recorded during Thesis II or the committee review",
        )
    checked_at = (checked_at or _now()).replace(tzinfo=None, microsecond=0)
    if checked_at > _now():
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "checked_at cannot be in the future"
        )

    # The verdict follows the threshold in force, which is stored with the check, so
    # later threshold changes do not rewrite past verdicts.
    threshold = similarity_threshold(db)
    check = PlagiarismCheck(
        thesis_id=thesis_id,
        similarity_percentage=percentage,
        checked_at=checked_at,
        tool=tool,
        threshold_applied=threshold,
        verdict=(
            SimilarityVerdict.ACCEPTED if percentage <= threshold else SimilarityVerdict.REJECTED
        ),
        report_url=report_url,
        notes=notes,
        recorded_by=user.user_id,
    )
    db.add(check)
    db.commit()
    db.refresh(check)
    return check


def latest_similarity_check(thesis: Thesis) -> PlagiarismCheck | None:
    checks = thesis.similarity_checks
    return checks[-1] if checks else None


# ------------------------------------------------------------ administrative requirements


def active_requirement_types(db: Session) -> list[RequirementType]:
    query = (
        select(RequirementType)
        .where(RequirementType.is_active.is_(True))
        .order_by(RequirementType.sort_order, RequirementType.name)
    )
    return list(db.scalars(query))


def requirement_checklist(db: Session, student: Student) -> list[dict]:
    """Every active requirement with the student's status (PENDING when no row)."""
    rows = {r.requirement_type_id: r for r in student.requirements}
    items = []
    for rtype in active_requirement_types(db):
        row = rows.get(rtype.requirement_type_id)
        items.append(
            {
                "requirement_type": rtype,
                "status": row.status.value if row else "PENDING",
                "certified_at": row.certified_at if row else None,
                "certified_by_name": row.certified_by_name if row else None,
                "evidence_url": row.evidence_url if row else None,
                "notes": row.notes if row else None,
            }
        )
    return items


def missing_requirements(db: Session, student_id: int) -> list[str]:
    certified = set(
        db.scalars(
            select(StudentRequirement.requirement_type_id).where(
                StudentRequirement.student_id == student_id,
                StudentRequirement.status == RequirementStatus.CERTIFIED,
            )
        )
    )
    return [t.name for t in active_requirement_types(db) if t.requirement_type_id not in certified]


def set_requirement(
    db: Session,
    user: User,
    student_id: int,
    type_id: int,
    new_status: RequirementStatus,
    evidence_url: str | None,
    notes: str | None,
) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Student not found")
    if db.get(RequirementType, type_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Requirement type not found")

    row = db.get(StudentRequirement, (student_id, type_id))
    if row is None:
        row = StudentRequirement(student_id=student_id, requirement_type_id=type_id)
        db.add(row)
    # Who certified it and when is always the latest decision (I-12).
    row.status = new_status
    row.certified_by = user.user_id
    row.certified_at = _now()
    row.evidence_url = evidence_url
    row.notes = notes
    db.commit()
    db.refresh(student)
    return student


def clear_requirement(db: Session, student_id: int, type_id: int) -> Student:
    row = db.get(StudentRequirement, (student_id, type_id))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "The requirement is already pending")
    db.delete(row)
    db.commit()
    student = db.get(Student, student_id)
    db.refresh(student)
    return student
