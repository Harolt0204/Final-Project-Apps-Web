"""ORM models: the current (v2) state of the schema.

The real schema is built by the Alembic migrations in `alembic/versions/`:
0001 reproduces the inherited database exactly, and the following migrations apply
the corrections. These models must always describe the state after the latest one.
MySQL-only objects (the max-3-reviewers trigger) live only in the migrations.
"""

import datetime as dt
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    SmallInteger,
    String,
    Table,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.models.enums import (
    DefenseModality,
    ObservationStatus,
    RequirementStatus,
    ReviewerRole,
    SimilarityVerdict,
    ThesisStatus,
    TutorRole,
    UserRole,
)

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


def enum_column(enum_cls: type, **kwargs) -> Enum:
    """Store the enum *values* (e.g. 'Co-Tutor'), not the Python member names."""
    return Enum(
        enum_cls,
        values_callable=lambda members: [m.value for m in members],
        native_enum=True,
        validate_strings=True,
        **kwargs,
    )


class TimestampMixin:
    """created_at / updated_at on every table (DEC-08)."""

    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )


# --------------------------------------------------------------------------- people


class School(TimestampMixin, Base):
    """Catalog of schools (migration 0004). Needed for per-school reports."""

    __tablename__ = "schools"

    school_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)


class Student(TimestampMixin, Base):
    __tablename__ = "students"

    student_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    national_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.school_id", ondelete="RESTRICT")
    )
    institution: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True)
    phone: Mapped[str | None] = mapped_column(String(20))

    school: Mapped[School | None] = relationship()
    thesis: Mapped["Thesis | None"] = relationship(back_populates="student")
    account: Mapped["User | None"] = relationship(
        primaryjoin="Student.student_id == User.student_id", viewonly=True
    )
    requirements: Mapped[list["StudentRequirement"]] = relationship(viewonly=True)

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def has_account(self) -> bool:
        return self.account is not None

    @property
    def has_thesis(self) -> bool:
        return self.thesis is not None


class Professor(TimestampMixin, Base):
    __tablename__ = "professors"

    professor_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    national_id: Mapped[str | None] = mapped_column(String(20), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    school_id: Mapped[int | None] = mapped_column(
        ForeignKey("schools.school_id", ondelete="RESTRICT")
    )
    institution: Mapped[str | None] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True)  # I-7: now NOT NULL UNIQUE

    school: Mapped[School | None] = relationship()
    account: Mapped["User | None"] = relationship(
        primaryjoin="Professor.professor_id == User.professor_id", viewonly=True
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def has_account(self) -> bool:
        return self.account is not None


# --------------------------------------------------------------------- periods/theses


class AcademicPeriod(TimestampMixin, Base):
    __tablename__ = "academic_periods"
    __table_args__ = (CheckConstraint("start_date < end_date", name="dates"),)

    period_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    start_date: Mapped[dt.date | None] = mapped_column(Date)
    end_date: Mapped[dt.date | None] = mapped_column(Date)


thesis_period = Table(
    "thesis_period",
    Base.metadata,
    Column(
        "thesis_id",
        Integer,
        ForeignKey("theses.thesis_id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "period_id",
        Integer,
        ForeignKey("academic_periods.period_id", ondelete="RESTRICT"),
        primary_key=True,
    ),
    Column("created_at", DateTime, nullable=False, server_default=func.now()),
    Column("updated_at", DateTime, nullable=False, server_default=func.now(), onupdate=func.now()),
)


class Thesis(TimestampMixin, Base):
    __tablename__ = "theses"

    thesis_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255))
    abstract: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ThesisStatus] = mapped_column(
        enum_column(ThesisStatus, name="thesis_status"),
        default=ThesisStatus.PROPOSED,
        server_default=ThesisStatus.PROPOSED.value,
        index=True,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.student_id", ondelete="RESTRICT"), unique=True
    )

    student: Mapped[Student] = relationship(back_populates="thesis")
    periods: Mapped[list[AcademicPeriod]] = relationship(secondary=thesis_period)
    tutors: Mapped[list["TutorAssignment"]] = relationship(
        back_populates="thesis", cascade="all, delete-orphan"
    )
    reviewers: Mapped[list["ReviewerAssignment"]] = relationship(back_populates="thesis")
    similarity_checks: Mapped[list["PlagiarismCheck"]] = relationship(
        order_by="(PlagiarismCheck.checked_at, PlagiarismCheck.check_id)", viewonly=True
    )
    defense: Mapped["Defense | None"] = relationship(back_populates="thesis")
    observations: Mapped[list["ReviewObservation"]] = relationship(
        primaryjoin="Thesis.thesis_id == ReviewObservation.thesis_id",
        foreign_keys="ReviewObservation.thesis_id",
        order_by="ReviewObservation.observation_id",
        viewonly=True,
    )
    status_history: Mapped[list["ThesisStatusHistory"]] = relationship(
        back_populates="thesis", order_by="ThesisStatusHistory.changed_at"
    )


class TutorAssignment(TimestampMixin, Base):
    """DEC-03: PK (thesis_id, role) => at most one Tutor and one Co-Tutor per thesis;
    UNIQUE (thesis_id, professor_id) => tutor and co-tutor are different people."""

    __tablename__ = "tutor_assignments"
    __table_args__ = (
        UniqueConstraint("thesis_id", "professor_id", name="uq_tutor_thesis_professor"),
    )

    thesis_id: Mapped[int] = mapped_column(
        ForeignKey("theses.thesis_id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[TutorRole] = mapped_column(
        enum_column(TutorRole, name="tutor_role"), primary_key=True
    )
    professor_id: Mapped[int] = mapped_column(
        ForeignKey("professors.professor_id", ondelete="RESTRICT")
    )

    thesis: Mapped[Thesis] = relationship(back_populates="tutors")
    professor: Mapped[Professor] = relationship()


class ReviewerAssignment(TimestampMixin, Base):
    """DEC-04/05: max 3 reviewers (MySQL trigger + service), exactly one President
    (unique index over a generated column), and an individual defense grade."""

    __tablename__ = "reviewer_assignments"
    __table_args__ = (
        CheckConstraint("grade >= 0 AND grade <= 10", name="grade_range"),
        UniqueConstraint("president_thesis_id", name="uq_one_president_per_thesis"),
    )

    # thesis_id is the base column of a STORED generated column, so MySQL does not
    # allow ON DELETE CASCADE on its foreign key: theses with reviewers are RESTRICTed.
    thesis_id: Mapped[int] = mapped_column(
        ForeignKey("theses.thesis_id", ondelete="RESTRICT"), primary_key=True
    )
    professor_id: Mapped[int] = mapped_column(
        ForeignKey("professors.professor_id", ondelete="RESTRICT"), primary_key=True
    )
    role: Mapped[ReviewerRole] = mapped_column(
        enum_column(ReviewerRole, name="reviewer_role"),
        default=ReviewerRole.COMMITTEE,
        server_default=ReviewerRole.COMMITTEE.value,
    )
    # When the reviewer approved the manuscript (migration 0005). NULL = not approved.
    approved_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    grade: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))
    president_thesis_id: Mapped[int | None] = mapped_column(
        Integer,
        Computed("CASE WHEN role = 'President' THEN thesis_id END", persisted=True),
    )

    thesis: Mapped[Thesis] = relationship(back_populates="reviewers")
    professor: Mapped[Professor] = relationship()


class ReviewObservation(TimestampMixin, Base):
    """One observation of a reviewer on the manuscript, with the student's response
    (migration 0005). The composite foreign key means only a reviewer of the thesis
    can be the author."""

    __tablename__ = "review_observations"
    __table_args__ = (
        ForeignKeyConstraint(
            ["thesis_id", "professor_id"],
            ["reviewer_assignments.thesis_id", "reviewer_assignments.professor_id"],
            name="fk_review_observations_reviewer",
            ondelete="RESTRICT",
        ),
        CheckConstraint("status <> 'ADDRESSED' OR response IS NOT NULL", name="addressed"),
        CheckConstraint("status <> 'RESOLVED' OR resolved_at IS NOT NULL", name="resolved"),
        Index("ix_review_observations_thesis_status", "thesis_id", "status"),
    )

    observation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thesis_id: Mapped[int] = mapped_column(Integer)
    professor_id: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[ObservationStatus] = mapped_column(
        enum_column(ObservationStatus, name="observation_status"),
        default=ObservationStatus.OPEN,
        server_default=ObservationStatus.OPEN.value,
    )
    response: Mapped[str | None] = mapped_column(Text)
    responded_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    resolved_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    author: Mapped[Professor] = relationship(
        primaryjoin="ReviewObservation.professor_id == Professor.professor_id",
        foreign_keys="ReviewObservation.professor_id",
        viewonly=True,
    )

    @property
    def author_name(self) -> str:
        return self.author.full_name


class RequirementType(TimestampMixin, Base):
    """Catalog of administrative graduation requirements (migration 0007, D-6)."""

    __tablename__ = "requirement_types"

    requirement_type_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(150), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    sort_order: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")


class StudentRequirement(TimestampMixin, Base):
    """Certification (or documented rejection) of one requirement for one student.
    No row means the requirement is still pending."""

    __tablename__ = "student_requirements"
    __table_args__ = (
        CheckConstraint("status <> 'REJECTED' OR notes IS NOT NULL", name="rejected_note"),
    )

    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.student_id", ondelete="RESTRICT"), primary_key=True
    )
    requirement_type_id: Mapped[int] = mapped_column(
        ForeignKey("requirement_types.requirement_type_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    status: Mapped[RequirementStatus] = mapped_column(
        enum_column(RequirementStatus, name="requirement_status")
    )
    # NULL only for data migrated from the previous system.
    certified_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT")
    )
    certified_at: Mapped[dt.datetime] = mapped_column(DateTime)
    evidence_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)

    requirement_type: Mapped[RequirementType] = relationship()
    certifier: Mapped["User | None"] = relationship()

    @property
    def certified_by_name(self) -> str | None:
        return self.certifier.display_name if self.certifier else None


class SystemSetting(TimestampMixin, Base):
    """Configurable parameters, e.g. the maximum similarity accepted (D-8)."""

    __tablename__ = "system_settings"

    setting_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(255))


class PlagiarismCheck(TimestampMixin, Base):
    """Similarity check history (migration 0006): several checks per thesis. The verdict
    is derived from the percentage and the threshold in force, and a CHECK constraint
    keeps them consistent."""

    __tablename__ = "plagiarism_checks"
    __table_args__ = (
        CheckConstraint(
            "similarity_percentage >= 0 AND similarity_percentage <= 100", name="similarity_range"
        ),
        CheckConstraint(
            "threshold_applied >= 0 AND threshold_applied <= 100", name="threshold_range"
        ),
        CheckConstraint(
            "(verdict = 'ACCEPTED') = (similarity_percentage <= threshold_applied)",
            name="verdict",
        ),
        Index("ix_plagiarism_checks_thesis_time", "thesis_id", "checked_at"),
    )

    check_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thesis_id: Mapped[int] = mapped_column(ForeignKey("theses.thesis_id", ondelete="CASCADE"))
    similarity_percentage: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    checked_at: Mapped[dt.datetime] = mapped_column(DateTime)
    tool: Mapped[str] = mapped_column(String(100))
    threshold_applied: Mapped[Decimal] = mapped_column(Numeric(5, 2))
    verdict: Mapped[SimilarityVerdict] = mapped_column(
        enum_column(SimilarityVerdict, name="similarity_verdict")
    )
    report_url: Mapped[str | None] = mapped_column(String(500))
    notes: Mapped[str | None] = mapped_column(Text)
    # NULL only for data migrated from the previous system.
    recorded_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.user_id", ondelete="RESTRICT")
    )

    recorder: Mapped["User | None"] = relationship()

    @property
    def recorded_by_name(self) -> str | None:
        return self.recorder.display_name if self.recorder else None


class Room(TimestampMixin, Base):
    """Defense rooms (migration 0008, DEC-09)."""

    __tablename__ = "rooms"
    __table_args__ = (
        UniqueConstraint("building", "name", name="uq_rooms_building_name"),
        CheckConstraint("capacity IS NULL OR capacity > 0", name="capacity"),
    )

    room_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100))
    building: Mapped[str] = mapped_column(String(100))
    capacity: Mapped[int | None] = mapped_column(SmallInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")

    @property
    def label(self) -> str:
        return f"{self.name} ({self.building})"


class Defense(TimestampMixin, Base):
    """Scheduled oral defense (migration 0008). The jury is the reviewer committee
    (DEC-05); each member's grade is in reviewer_assignments.grade and final_grade is
    their average, set when the last grade is recorded."""

    __tablename__ = "defenses"
    __table_args__ = (
        CheckConstraint("final_grade >= 0 AND final_grade <= 10", name="final_grade_range"),
        CheckConstraint("duration_minutes BETWEEN 15 AND 480", name="duration"),
        CheckConstraint(
            "(modality = 'In-person' AND room_id IS NOT NULL AND meeting_url IS NULL) OR "
            "(modality = 'Virtual' AND room_id IS NULL AND meeting_url IS NOT NULL)",
            name="place",
        ),
        Index("ix_defenses_room_time", "room_id", "scheduled_at"),
        Index("ix_defenses_scheduled_at", "scheduled_at"),
    )

    defense_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thesis_id: Mapped[int] = mapped_column(
        ForeignKey("theses.thesis_id", ondelete="CASCADE"), unique=True
    )
    scheduled_at: Mapped[dt.datetime] = mapped_column(DateTime)
    duration_minutes: Mapped[int] = mapped_column(SmallInteger, default=60, server_default="60")
    modality: Mapped[DefenseModality] = mapped_column(
        enum_column(DefenseModality, name="defense_modality"),
        default=DefenseModality.IN_PERSON,
        server_default=DefenseModality.IN_PERSON.value,
    )
    # No ON DELETE: MySQL forbids referential actions on a column used by a CHECK.
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.room_id"))
    meeting_url: Mapped[str | None] = mapped_column(String(255))
    final_grade: Mapped[Decimal | None] = mapped_column(Numeric(4, 2))

    room: Mapped[Room | None] = relationship()
    thesis: Mapped["Thesis"] = relationship(back_populates="defense")

    @property
    def ends_at(self) -> dt.datetime:
        return self.scheduled_at + dt.timedelta(minutes=self.duration_minutes)


class DefenseEmail(Base):
    """Delivery record for one defense demo email."""

    __tablename__ = "defense_emails"
    __table_args__ = (Index("ix_defense_emails_pending", "status", "available_at", "email_id"),)

    email_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thesis_id: Mapped[int] = mapped_column(ForeignKey("theses.thesis_id", ondelete="CASCADE"))
    recipient: Mapped[str] = mapped_column(String(254))
    subject: Mapped[str] = mapped_column(String(150))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending")
    attempts: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    available_at: Mapped[dt.datetime] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(String(100))


# ----------------------------------------------------------------------- users/audit


class User(TimestampMixin, Base):
    """Login accounts (DEC-07). Each account is linked to the person its role implies."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "(role = 'student' AND student_id IS NOT NULL AND professor_id IS NULL) OR "
            "(role = 'professor' AND professor_id IS NOT NULL AND student_id IS NULL) OR "
            "(role = 'admin' AND student_id IS NULL AND professor_id IS NULL)",
            name="link",
        ),
    )

    user_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # name.lastname, without the @domain (migration 0010).
    username: Mapped[str] = mapped_column(String(100), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Tokens issued before this moment are rejected (migration 0009).
    password_changed_at: Mapped[dt.datetime | None] = mapped_column(DateTime)
    role: Mapped[UserRole] = mapped_column(enum_column(UserRole, name="user_role"))
    # No ON DELETE: MySQL forbids referential actions on columns used by a CHECK.
    student_id: Mapped[int | None] = mapped_column(ForeignKey("students.student_id"), unique=True)
    professor_id: Mapped[int | None] = mapped_column(
        ForeignKey("professors.professor_id"), unique=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1")
    last_login_at: Mapped[dt.datetime | None] = mapped_column(DateTime)

    student: Mapped[Student | None] = relationship()
    professor: Mapped[Professor | None] = relationship()

    @property
    def display_name(self) -> str:
        person = self.student or self.professor
        return person.full_name if person else "Administrator"


class ThesisStatusHistory(Base):
    """Immutable audit trail of status changes (DEC-08). Written by the service in the
    same transaction as the change, because a trigger cannot know the logged-in user."""

    __tablename__ = "thesis_status_history"
    __table_args__ = (Index("ix_tsh_thesis_time", "thesis_id", "changed_at"),)

    history_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thesis_id: Mapped[int] = mapped_column(ForeignKey("theses.thesis_id", ondelete="RESTRICT"))
    from_status: Mapped[ThesisStatus | None] = mapped_column(
        enum_column(ThesisStatus, name="tsh_from_status")
    )
    to_status: Mapped[ThesisStatus] = mapped_column(enum_column(ThesisStatus, name="tsh_to_status"))
    changed_by: Mapped[int] = mapped_column(ForeignKey("users.user_id", ondelete="RESTRICT"))
    changed_at: Mapped[dt.datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    comment: Mapped[str | None] = mapped_column(Text)

    thesis: Mapped[Thesis] = relationship(back_populates="status_history")
    author: Mapped[User] = relationship()

    @property
    def changed_by_name(self) -> str:
        return self.author.display_name


__all__ = [
    "AcademicPeriod",
    "Base",
    "Defense",
    "DefenseEmail",
    "DefenseModality",
    "PlagiarismCheck",
    "Professor",
    "ObservationStatus",
    "RequirementStatus",
    "RequirementType",
    "ReviewObservation",
    "School",
    "SimilarityVerdict",
    "StudentRequirement",
    "SystemSetting",
    "ReviewerAssignment",
    "ReviewerRole",
    "Room",
    "Student",
    "Thesis",
    "ThesisStatus",
    "ThesisStatusHistory",
    "TutorAssignment",
    "TutorRole",
    "User",
    "UserRole",
    "thesis_period",
]
