import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import unquote, urlparse

import mysql.connector
from mysql.connector import Error
from mysql.connector.connection import MySQLConnection


UPLOAD_DIR = Path("uploads")


def _database_config(include_database: bool = True) -> dict[str, Any]:
    """Build MySQL connection settings from local, Railway, or URL env vars."""
    database_url = os.getenv("MYSQL_URL") or os.getenv("DATABASE_URL")
    if database_url:
        parsed = urlparse(database_url)
        config: dict[str, Any] = {
            "host": parsed.hostname or "127.0.0.1",
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
        }
        database = parsed.path.lstrip("/")
        if include_database and database:
            config["database"] = unquote(database)
        return config

    config = {
        "host": os.getenv("DB_HOST") or os.getenv("MYSQLHOST") or "127.0.0.1",
        "port": int(os.getenv("DB_PORT") or os.getenv("MYSQLPORT") or "3306"),
        "user": os.getenv("DB_USER") or os.getenv("MYSQLUSER") or "root",
        "password": os.getenv("DB_PASSWORD") or os.getenv("MYSQLPASSWORD") or "1234",
    }
    database = os.getenv("DB_NAME") or os.getenv("MYSQLDATABASE") or "AI_interview_simulator"
    if include_database:
        config["database"] = database
    return config


def _database_name() -> str:
    config = _database_config(include_database=True)
    return str(config.get("database") or "AI_interview_simulator")


class Database:
    def __init__(self, conn: MySQLConnection):
        self.conn = conn

    def execute(self, sql: str, params: tuple[Any, ...] = ()):
        cursor = self.conn.cursor(dictionary=True)
        cursor.execute(self._translate(sql), params)
        return cursor

    def executescript(self, script: str) -> None:
        cursor = self.conn.cursor()
        for statement in script.split(";"):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)

    def commit(self) -> None:
        self.conn.commit()

    @staticmethod
    def _translate(sql: str) -> str:
        return sql.replace("?", "%s")


@contextmanager
def get_db() -> Iterator[Database]:
    conn = mysql.connector.connect(**_database_config(include_database=True))
    db = Database(conn)
    try:
        yield db
        db.commit()
    finally:
        conn.close()


def ensure_database_exists() -> None:
    config = _database_config(include_database=False)
    try:
        conn = mysql.connector.connect(**config)
    except Error as exc:
        try:
            # Managed databases such as Railway may require connecting directly
            # to the provisioned database and reject server-level connections.
            test_conn = mysql.connector.connect(**_database_config(include_database=True))
            test_conn.close()
            return
        except Error:
            raise exc
    try:
        cursor = conn.cursor()
        cursor.execute(
            f"CREATE DATABASE IF NOT EXISTS `{_database_name()}` "
            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
        )
        conn.commit()
    except Error as exc:
        try:
            test_conn = mysql.connector.connect(**_database_config(include_database=True))
            test_conn.close()
        except Error:
            raise exc
    finally:
        conn.close()


def init_db() -> None:
    UPLOAD_DIR.mkdir(exist_ok=True)
    ensure_database_exists()
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
