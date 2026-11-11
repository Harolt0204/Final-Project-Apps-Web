"""Closed value sets used by the schema. They replace the free-text VARCHAR fields
of the inherited database (finding I-5 in documentation.md)."""

from enum import StrEnum


class UserRole(StrEnum):
    """Global roles (DEC-07). Tutor, reviewer and president are NOT roles: they are
    derived per thesis from tutor_assignments / reviewer_assignments."""

    ADMIN = "admin"
    PROFESSOR = "professor"
    STUDENT = "student"


class ThesisStatus(StrEnum):
    """Single thesis state machine (default for open decision D-5, see docs/decisions.md).
    Replaces the inherited `status` + `stage` pair."""

    PROPOSED = "PROPOSED"
    TOPIC_APPROVED = "TOPIC_APPROVED"
    THESIS_I = "THESIS_I"
    THESIS_II = "THESIS_II"
    IN_REVIEW = "IN_REVIEW"
    READY_FOR_DEFENSE = "READY_FOR_DEFENSE"
    DEFENDED = "DEFENDED"
    REJECTED = "REJECTED"


class TutorRole(StrEnum):
    TUTOR = "Tutor"
    CO_TUTOR = "Co-Tutor"


class ReviewerRole(StrEnum):
    PRESIDENT = "President"
    COMMITTEE = "Committee"


class ObservationStatus(StrEnum):
    """Review observation cycle (FR-08): the reviewer opens it, the student answers it,
    and the reviewer resolves it or reopens it."""

    OPEN = "OPEN"
    ADDRESSED = "ADDRESSED"
    RESOLVED = "RESOLVED"


class SimilarityVerdict(StrEnum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


class RequirementStatus(StrEnum):
    """Status of an administrative requirement for a student. No row means pending."""

    CERTIFIED = "CERTIFIED"
    REJECTED = "REJECTED"


class DefenseModality(StrEnum):
    IN_PERSON = "In-person"
    VIRTUAL = "Virtual"
