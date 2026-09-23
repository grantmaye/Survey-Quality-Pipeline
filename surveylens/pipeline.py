"""CSV validation and transactional ingestion with explicit duplicate semantics."""
from __future__ import annotations

import csv
import hashlib
import re
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path

FIELDS = ["response_id", "course", "term", "rating", "submitted_at"]
MAX_BYTES = 25 * 1024 * 1024


def connect(filename: str | Path) -> sqlite3.Connection:
    if str(filename) != ":memory:":
        Path(filename).parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(filename)
    db.row_factory = sqlite3.Row
    db.executescript("""
        PRAGMA foreign_keys=ON;
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY, file_hash TEXT NOT NULL UNIQUE,
            imported_at TEXT NOT NULL, accepted INTEGER NOT NULL DEFAULT 0,
            duplicates INTEGER NOT NULL DEFAULT 0, rejected INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS responses (
            response_id TEXT PRIMARY KEY, course TEXT NOT NULL, term TEXT NOT NULL,
            rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
            submitted_at TEXT NOT NULL, run_id INTEGER NOT NULL REFERENCES runs(id)
        );
        CREATE TABLE IF NOT EXISTS rejections (
            id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
            record_number INTEGER NOT NULL, reason TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS responses_term_course ON responses(term, course);
    """)
    return db


@dataclass(frozen=True)
class Response:
    response_id: str
    course: str
    term: str
    rating: int
    submitted_at: str


def validate(row: dict) -> Response:
    if None in row or any(row.get(field) is None for field in FIELDS):
        raise ValueError("incorrect_column_count")
    response_id = row["response_id"].strip()
    course = row["course"].strip().upper()
    term = row["term"].strip().lower()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", response_id):
        raise ValueError("invalid_response_id")
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9._-]{0,39}", course):
        raise ValueError("invalid_course")
    if not re.fullmatch(r"20\d{2}-(spring|summer|fall)", term):
        raise ValueError("invalid_term")
    if not re.fullmatch(r"[1-5]", row["rating"].strip()):
        raise ValueError("rating_out_of_range")
    try:
        submitted = datetime.fromisoformat(row["submitted_at"].strip().replace("Z", "+00:00"))
        if submitted.tzinfo is None:
            raise ValueError()
        submitted = submitted.astimezone(timezone.utc)
    except (ValueError, OverflowError) as exc:
        raise ValueError("invalid_timestamp_requires_timezone") from exc
    return Response(response_id, course, term, int(row["rating"]), submitted.isoformat())


def ingest(db: sqlite3.Connection, source: str | Path) -> dict:
    source = Path(source)
    # A bounded immutable snapshot makes the fingerprint describe exactly what is parsed.
    with source.open("rb") as handle:
        raw = handle.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Input exceeds the 25 MiB limit")
    fingerprint = hashlib.sha256(raw).hexdigest()
    import io
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    if reader.fieldnames is None or len(reader.fieldnames) != len(FIELDS) or set(reader.fieldnames) != set(FIELDS):
        raise ValueError("CSV must contain exactly: " + ",".join(FIELDS))
    # Explicit BEGIN IMMEDIATE serializes concurrent writers before checking the hash.
    db.execute("BEGIN IMMEDIATE")
    try:
        previous = db.execute("SELECT * FROM runs WHERE file_hash=?", (fingerprint,)).fetchone()
        if previous:
            db.commit()
            return {**dict(previous), "replayed": True}
        cursor = db.execute("INSERT INTO runs(file_hash, imported_at) VALUES (?, ?)",
                            (fingerprint, datetime.now(timezone.utc).isoformat()))
        run_id = cursor.lastrowid
        counts = {"accepted": 0, "duplicates": 0, "rejected": 0}
        for record_number, row in enumerate(reader, start=1):
            try:
                response = validate(row)
                existing = db.execute("SELECT response_id, course, term, rating, submitted_at FROM responses WHERE response_id=?",
                                      (response.response_id,)).fetchone()
                if existing:
                    if dict(existing) == asdict(response):
                        counts["duplicates"] += 1
                        continue
                    raise ValueError("conflicting_response_id")
                db.execute("INSERT INTO responses VALUES (?, ?, ?, ?, ?, ?)",
                           (*asdict(response).values(), run_id))
                counts["accepted"] += 1
            except ValueError as error:
                counts["rejected"] += 1
                # Never copy source row values into diagnostic output.
                db.execute("INSERT INTO rejections(run_id, record_number, reason) VALUES (?, ?, ?)",
                           (run_id, record_number, str(error)))
        db.execute("UPDATE runs SET accepted=?, duplicates=?, rejected=? WHERE id=?",
                   (counts["accepted"], counts["duplicates"], counts["rejected"], run_id))
        db.commit()
        return {"id": run_id, "file_hash": fingerprint, **counts, "replayed": False}
    except BaseException:
        db.rollback()
        raise


def report(db: sqlite3.Connection, minimum: int = 5) -> dict:
    if type(minimum) is not int or minimum < 3:
        raise ValueError("minimum must be an integer of at least 3")
    rows = db.execute("""
        SELECT term, course, COUNT(*) AS n, AVG(rating) AS mean_rating,
               SUM(CASE WHEN rating >= 4 THEN 1 ELSE 0 END) * 100.0 / COUNT(*) AS favorable_pct
        FROM responses GROUP BY term, course ORDER BY term, course
    """).fetchall()
    groups = []
    for row in rows:
        suppressed = row["n"] < minimum
        groups.append({
            "term": row["term"], "course": row["course"], "suppressed": suppressed,
            "responses": None if suppressed else row["n"],
            "mean_rating": None if suppressed else round(row["mean_rating"], 2),
            "favorable_pct": None if suppressed else round(row["favorable_pct"], 1),
        })
    return {"minimum_responses": minimum, "groups": groups}


def rejections(db: sqlite3.Connection, run_id: int) -> list[dict]:
    return [dict(row) for row in db.execute(
        "SELECT record_number, reason FROM rejections WHERE run_id=? ORDER BY record_number", (run_id,))]
