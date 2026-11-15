"""Test fixtures. Tests run against an in-memory SQLite database built from the ORM
models, so they need neither Docker nor MySQL. MySQL-only objects (the max-3-reviewers
trigger) are verified against the real database, see README."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes.auth import limiter
from app.core.security import hash_password
from app.db import get_db
from app.main import app
from app.models import (
    Base,
    Professor,
    ReviewerAssignment,
    ReviewerRole,
    Student,
    Thesis,
    TutorAssignment,
    TutorRole,
    User,
    UserRole,
)
from app.schemas.users import username_from_email

PASSWORD = "correct-horse-battery"


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_connection, _record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db(engine) -> Iterator[Session]:
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()


@pytest.fixture
def client(engine) -> Iterator[TestClient]:
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    limiter.reset()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def world(db: Session) -> dict:
    """Small dataset: 1 admin, 3 professors, 3 students, 2 theses.

    thesis1: student s1, tutor pA, president pB
    thesis2: student s2, tutor pB, committee pA
    pC and s3 take part in no thesis.
    """
    pw = hash_password(PASSWORD)
    profs = {
        k: Professor(first_name=k, last_name="Prof", email=f"{k}@yachaytech.edu.ec")
        for k in ("pA", "pB", "pC")
    }
    studs = {
        k: Student(first_name=k, last_name="Student", email=f"{k}@yachaytech.edu.ec")
        for k in ("s1", "s2", "s3")
    }
    db.add_all([*profs.values(), *studs.values()])

    users = {"admin": User(username="admin", password_hash=pw, role=UserRole.ADMIN)}
    for k, p in profs.items():
        users[k] = User(
            username=username_from_email(p.email),
            password_hash=pw,
            role=UserRole.PROFESSOR,
            professor=p,
        )
    for k, s in studs.items():
        users[k] = User(
            username=username_from_email(s.email),
            password_hash=pw,
            role=UserRole.STUDENT,
            student=s,
        )
    db.add_all(users.values())

    t1 = Thesis(title="Thesis one", student=studs["s1"])
    t2 = Thesis(title="Thesis two", student=studs["s2"])
    db.add_all([t1, t2])
    db.add_all(
        [
            TutorAssignment(thesis=t1, professor=profs["pA"], role=TutorRole.TUTOR),
            ReviewerAssignment(thesis=t1, professor=profs["pB"], role=ReviewerRole.PRESIDENT),
            TutorAssignment(thesis=t2, professor=profs["pB"], role=TutorRole.TUTOR),
            ReviewerAssignment(thesis=t2, professor=profs["pA"], role=ReviewerRole.COMMITTEE),
        ]
    )
    db.commit()
    return {"users": users, "profs": profs, "students": studs, "t1": t1, "t2": t2}


def login(client: TestClient, username: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/api/auth/login", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}
