import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import quote_plus

from sqlalchemy import Column, Integer, String, create_engine, text
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, declarative_base, sessionmaker


UPLOAD_DIR = Path("uploads")


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("mysql://"):
        return database_url.replace("mysql://", "mysql+mysqlconnector://", 1)
    return database_url


def _build_database_url() -> str:
    database_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    if database_url:
        return _normalize_database_url(database_url)

    host = os.getenv("DB_HOST") or os.getenv("MYSQLHOST") or "127.0.0.1"
    port = os.getenv("DB_PORT") or os.getenv("MYSQLPORT") or "3306"
    user = quote_plus(os.getenv("DB_USER") or os.getenv("MYSQLUSER") or "root")
    password = quote_plus(os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD") or "1234")
    database = os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE") or "AI_interview_simulator"
    return f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"


DATABASE_URL = _build_database_url()

engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    email = Column(String)


class QueryResult:
    def __init__(self, result: CursorResult[Any]):
        self.result = result
        self.lastrowid = result.lastrowid

    def fetchone(self) -> dict[str, Any] | None:
        row = self.result.mappings().fetchone()
        return dict(row) if row else None

    def fetchall(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.result.mappings().fetchall()]


class Database:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, sql: str, params: tuple[Any, ...] = ()):
        result = self.session.connection().exec_driver_sql(self._translate(sql), params)
        return QueryResult(result)

    def executescript(self, script: str) -> None:
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                self.session.execute(text(statement))

    def commit(self) -> None:
        self.session.commit()

    @staticmethod
    def _translate(sql: str) -> str:
        return sql.replace("?", "%s")


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


def ensure_database_exists() -> None:
    database = engine.url.database
    if not database:
        return

    admin_engine = create_engine(engine.url.set(database=None), pool_pre_ping=True)
    try:
        with admin_engine.begin() as conn:
            escaped_database = database.replace("`", "``")
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS `{escaped_database}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
    except OperationalError as exc:
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except OperationalError:
            raise exc
    finally:
        admin_engine.dispose()


def init_db() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)
    ensure_database_exists()
    Base.metadata.create_all(bind=engine)
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'candidate',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS resumes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                filename VARCHAR(500) NOT NULL,
                text LONGTEXT NOT NULL,
                skills TEXT NOT NULL,
                education TEXT NOT NULL,
                experience TEXT NOT NULL,
                projects TEXT NOT NULL,
                certifications TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS interviews (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                role VARCHAR(100) NOT NULL,
                level VARCHAR(50) NOT NULL,
                interview_type VARCHAR(100) NOT NULL,
                company VARCHAR(100) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                current_agent VARCHAR(100) NOT NULL DEFAULT 'Technical Interviewer',
                overall_score REAL NOT NULL DEFAULT 0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS interview_messages (
                id INT AUTO_INCREMENT PRIMARY KEY,
                interview_id INT NOT NULL,
                sender VARCHAR(50) NOT NULL,
                agent VARCHAR(100) NOT NULL,
                content LONGTEXT NOT NULL,
                score_json TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS coding_results (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                language VARCHAR(50) NOT NULL,
                problem_title VARCHAR(255) NOT NULL,
                code LONGTEXT NOT NULL,
                result_json TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

            CREATE TABLE IF NOT EXISTS reports (
                id INT AUTO_INCREMENT PRIMARY KEY,
                interview_id INT NOT NULL,
                report_html LONGTEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (interview_id) REFERENCES interviews(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
        )
