# PostgreSQL + Supabase database configuration

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    text as sql_text,
)
from sqlalchemy.engine import CursorResult
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker


UPLOAD_DIR = Path("uploads")


# =========================
# DATABASE CONFIG
# =========================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

database_url = make_url(DATABASE_URL)
if database_url.get_backend_name() != "postgresql":
    raise ValueError("DATABASE_URL must be a PostgreSQL/Supabase connection string")


engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


Base = declarative_base()


# =========================
# MODELS
# =========================
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="candidate")
    created_at = Column(DateTime, server_default=sql_text("CURRENT_TIMESTAMP"))


class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String(500), nullable=False)
    text = Column(Text, nullable=False)
    skills = Column(Text, nullable=False)
    education = Column(Text, nullable=False)
    experience = Column(Text, nullable=False)
    projects = Column(Text, nullable=False)
    certifications = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=sql_text("CURRENT_TIMESTAMP"))

    user = relationship("User")


class Interview(Base):
    __tablename__ = "interviews"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String(100), nullable=False)
    level = Column(String(50), nullable=False)
    interview_type = Column(String(100), nullable=False)
    company = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default="active")
    current_agent = Column(String(100), nullable=False, default="Technical Interviewer")
    overall_score = Column(Float, nullable=False, default=0)
    created_at = Column(DateTime, server_default=sql_text("CURRENT_TIMESTAMP"))
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User")


class InterviewMessage(Base):
    __tablename__ = "interview_messages"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    sender = Column(String(50), nullable=False)
    agent = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    score_json = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=sql_text("CURRENT_TIMESTAMP"))

    interview = relationship("Interview")


class CodingResult(Base):
    __tablename__ = "coding_results"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    language = Column(String(50), nullable=False)
    problem_title = Column(String(255), nullable=False)
    code = Column(Text, nullable=False)
    result_json = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=sql_text("CURRENT_TIMESTAMP"))

    user = relationship("User")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    interview_id = Column(Integer, ForeignKey("interviews.id"), nullable=False)
    report_html = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=sql_text("CURRENT_TIMESTAMP"))

    interview = relationship("Interview")


# =========================
# QUERY RESULT WRAPPER
# =========================
class QueryResult:
    def __init__(self, result: CursorResult[Any], lastrowid: Any | None = None):
        self.result = result
        self.lastrowid = lastrowid if lastrowid is not None else result.lastrowid

    def fetchone(self) -> dict[str, Any] | None:
        row = self.result.mappings().fetchone()
        return dict(row) if row else None

    def fetchall(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.result.mappings().fetchall()]


# =========================
# DATABASE SESSION
# =========================
class Database:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, sql: str, params: tuple[Any, ...] = ()):
        connection = self.session.connection()
        statement = sql.strip()

        if connection.dialect.name == "postgresql":
            statement = statement.replace("?", "%s")
            if statement.lower().startswith("insert ") and " returning " not in statement.lower():
                result = connection.exec_driver_sql(f"{statement} RETURNING id", params)
                row = result.fetchone()
                return QueryResult(result, row[0] if row else None)

        result = connection.exec_driver_sql(statement, params)
        return QueryResult(result)

    def commit(self) -> None:
        self.session.commit()


@contextmanager
def get_db() -> Iterator[Database]:
    session = SessionLocal()
    db = Database(session)

    try:
        yield db
        db.commit()

    except Exception:
        session.rollback()
        raise

    finally:
        session.close()


# =========================
# INITIALIZE DATABASE
# =========================
def init_db() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)
    Base.metadata.create_all(bind=engine)
