import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import mysql.connector
from mysql.connector.connection import MySQLConnection


DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
DB_NAME = os.getenv("DB_NAME", "AI_interview_simulator")
UPLOAD_DIR = Path("uploads")


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
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
    )
    db = Database(conn)
    try:
        yield db
        db.commit()
    finally:
        conn.close()


def ensure_database_exists() -> None:
    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    cursor = conn.cursor()
    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    conn.commit()
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
