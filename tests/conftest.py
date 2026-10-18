import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.db import Base, get_db, User, Dataset, Report, ReportBlock
from app.services.auth import hash_password, create_session
from app.main import create_app

# Use a separate test database
TEST_DB_FILE = "./test_prooflytics.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_FILE}"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Remove old test DB if present
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass

    Base.metadata.create_all(bind=test_engine)
    yield
    # Cleanup after test suite
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass

@pytest.fixture
def db_session():
    connection = test_engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session):
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def test_users(db_session):
    # Seed User A
    user_a = User(
        email="user_a@test.com",
        password_hash=hash_password("PasswordA123!")
    )
    # Seed User B
    user_b = User(
        email="user_b@test.com",
        password_hash=hash_password("PasswordB123!")
    )
    db_session.add_all([user_a, user_b])
    db_session.flush()

    # Create dataset & report for User A
    dataset_a = Dataset(
        owner_id=user_a.id,
        name="Dataset A",
        status="ready",
        original_filename="a.csv",
        row_count=10
    )
    db_session.add(dataset_a)
    db_session.flush()

    report_a = Report(
        owner_id=user_a.id,
        dataset_id=dataset_a.id,
        title="Report A"
    )
    db_session.add(report_a)

    # Create dataset & report for User B
    dataset_b = Dataset(
        owner_id=user_b.id,
        name="Dataset B",
        status="ready",
        original_filename="b.csv",
        row_count=20
    )
    db_session.add(dataset_b)
    db_session.flush()

    report_b = Report(
        owner_id=user_b.id,
        dataset_id=dataset_b.id,
        title="Report B"
    )
    db_session.add(report_b)
    db_session.commit()

    return {
        "user_a": user_a,
        "dataset_a": dataset_a,
        "report_a": report_a,
        "user_b": user_b,
        "dataset_b": dataset_b,
        "report_b": report_b,
    }

def _create_authenticated_client(user, db_session):
    app = create_app()

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    c = TestClient(app)
    token, session_record = create_session(db_session, user.id)
    c.cookies.set(settings.SESSION_COOKIE_NAME, token)
    c.headers.update({"X-CSRF-Token": session_record.csrf_token})
    return c, token, session_record

@pytest.fixture
def auth_client_a(db_session, test_users):
    user_a = test_users["user_a"]
    client, token, session_record = _create_authenticated_client(user_a, db_session)
    yield client, token, session_record
    client.close()

@pytest.fixture
def auth_client_b(db_session, test_users):
    user_b = test_users["user_b"]
    client, token, session_record = _create_authenticated_client(user_b, db_session)
    yield client, token, session_record
    client.close()

