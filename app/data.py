from __future__ import annotations

import csv
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from time import monotonic
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = ROOT / "data" / "sample_sales.csv"


def _database_path() -> Path:
    path = Path(os.getenv("DATABASE_PATH", str(ROOT / "data" / "demo.sqlite3")))
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def initialize_database() -> None:
    path = _database_path()
    connection = sqlite3.connect(path)
    try:
        with connection:
            _initialize_connection(connection)
    finally:
        connection.close()


def _initialize_connection(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS sales (
            date TEXT NOT NULL, region TEXT NOT NULL, product TEXT NOT NULL,
            units INTEGER NOT NULL, revenue REAL NOT NULL, discount REAL NOT NULL
        )"""
    )
    if connection.execute("SELECT COUNT(*) FROM sales").fetchone()[0] == 0:
        with DEFAULT_CSV.open("r", encoding="utf-8", newline="") as source:
            rows = list(csv.DictReader(source))
        connection.executemany(
            "INSERT INTO sales(date, region, product, units, revenue, discount) VALUES (?, ?, ?, ?, ?, ?)",
            [(r["date"], r["region"], r["product"], int(r["units"]), float(r["revenue"]), float(r["discount"])) for r in rows],
        )


def _readonly_connection() -> sqlite3.Connection:
    path = _database_path().resolve()
    connection = sqlite3.connect(f"{path.as_uri()}?mode=ro", uri=True, timeout=5)
    connection.row_factory = sqlite3.Row
    allowed = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
    if hasattr(sqlite3, "SQLITE_RECURSIVE"):
        allowed.add(sqlite3.SQLITE_RECURSIVE)

    def authorize(action: int, arg1: str | None, arg2: str | None, _db: str | None, _trigger: str | None) -> int:
        if action not in allowed:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ and arg1 != "sales":
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or arg1 or "").lower() in {"load_extension", "readfile", "writefile"}:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    connection.set_authorizer(authorize)
    try:
        timeout_seconds = max(0.1, min(float(os.getenv("SQL_QUERY_TIMEOUT_SECONDS", "2")), 10))
    except ValueError:
        timeout_seconds = 2
    deadline = monotonic() + timeout_seconds
    connection.set_progress_handler(lambda: int(monotonic() > deadline), 1000)
    return connection


def inspect_dataset() -> dict[str, Any]:
    with closing(_readonly_connection()) as connection:
        count = connection.execute("SELECT COUNT(*) AS count FROM sales").fetchone()["count"]
    columns = [
        {"name": "date", "type": "TEXT"},
        {"name": "region", "type": "TEXT"},
        {"name": "product", "type": "TEXT"},
        {"name": "units", "type": "INTEGER"},
        {"name": "revenue", "type": "REAL"},
        {"name": "discount", "type": "REAL"},
    ]
    return {"table": "sales", "rows": count, "columns": columns}


def preview_rows(limit: int = 5) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit), 20))
    with closing(_readonly_connection()) as connection:
        rows = [dict(row) for row in connection.execute(f"SELECT * FROM sales LIMIT {safe_limit}").fetchall()]
    return {"rows": rows}


def run_readonly_query(query: str, max_rows: int = 100) -> dict[str, Any]:
    normalized = query.strip().rstrip(";").strip()
    if not normalized or ";" in normalized:
        raise ValueError("Provide exactly one SQL statement.")
    if normalized[:6].lower() != "select" and normalized[:4].lower() != "with":
        raise ValueError("Only SELECT or WITH queries are allowed.")
    limit = max(1, min(int(max_rows), 100))
    wrapped = f"SELECT * FROM ({normalized}) AS agent_result LIMIT {limit}"
    with closing(_readonly_connection()) as connection:
        cursor = connection.execute(wrapped)
        rows = [dict(row) for row in cursor.fetchall()]
        columns = [column[0] for column in cursor.description or []]
    return {"columns": columns, "rows": rows, "row_count": len(rows), "row_limit": limit}
