"""
db.py — F003 SQLite job store
All functions use parameterized queries. DB lives at webapp/jobs.db.
"""

import csv
import io
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "jobs.db"
PAGE_SIZE = 25


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT,
                company      TEXT,
                location     TEXT,
                job_type     TEXT,
                remote       BOOLEAN,
                description  TEXT,
                url          TEXT UNIQUE,
                source       TEXT,
                date_posted  TEXT,
                date_scraped TEXT,
                match_score  INTEGER DEFAULT 0,
                status       TEXT DEFAULT 'new'
            )
        """)
        conn.commit()


def insert_jobs(jobs: list) -> int:
    """Insert jobs, skipping duplicates by URL. Returns count of newly inserted rows."""
    if not jobs:
        return 0
    inserted = 0
    with _connect() as conn:
        for job in jobs:
            try:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO jobs
                       (title, company, location, job_type, remote, description,
                        url, source, date_posted, date_scraped, match_score, status)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        job.get("title", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                        job.get("job_type", ""),
                        1 if job.get("remote") else 0,
                        job.get("description", ""),
                        job.get("url", ""),
                        job.get("source", ""),
                        job.get("date_posted", ""),
                        job.get("date_scraped", datetime.now().strftime("%Y-%m-%d")),
                        int(job.get("match_score", 0)),
                        "new",
                    ),
                )
                inserted += cur.rowcount
            except Exception as e:
                print(f"[db] insert error for {job.get('url', '?')}: {e}")
        conn.commit()
    return inserted


def get_jobs(filters: dict) -> tuple:
    """
    Return (list[dict], total_count) for the given filters + page.
    Filters: source, status, min_score, job_type, remote, page (1-based).
    """
    where, params = [], []

    if filters.get("source") and filters["source"] != "all":
        sources = [s.strip() for s in filters["source"].split(",") if s.strip()]
        if len(sources) == 1:
            where.append("source = ?")
            params.append(sources[0])
        elif sources:
            placeholders = ",".join("?" * len(sources))
            where.append(f"source IN ({placeholders})")
            params.extend(sources)

    if filters.get("status") and filters["status"] != "all":
        where.append("status = ?")
        params.append(filters["status"])

    if filters.get("min_score"):
        try:
            where.append("match_score >= ?")
            params.append(int(filters["min_score"]))
        except (ValueError, TypeError):
            pass

    if filters.get("job_type") and filters["job_type"] != "all":
        where.append("job_type = ?")
        params.append(filters["job_type"])

    if filters.get("remote") in ("true", "1", True, 1):
        where.append("remote = 1")

    if filters.get("days_ago"):
        try:
            days = int(filters["days_ago"])
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            where.append("date_scraped >= ?")
            params.append(cutoff)
        except (ValueError, TypeError):
            pass

    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    page = max(1, int(filters.get("page", 1)))
    offset = (page - 1) * PAGE_SIZE

    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM jobs {where_clause}", params
        ).fetchone()[0]

        rows = conn.execute(
            f"""SELECT id, title, company, location, job_type, remote,
                       url, source, date_posted, date_scraped, match_score, status, description
                FROM jobs {where_clause}
                ORDER BY match_score DESC, id DESC
                LIMIT ? OFFSET ?""",
            params + [PAGE_SIZE, offset],
        ).fetchall()

    jobs = [dict(row) for row in rows]
    # Normalise remote to bool for JSON
    for j in jobs:
        j["remote"] = bool(j["remote"])
    return jobs, total


def update_status(job_id: int, status: str) -> None:
    with _connect() as conn:
        conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        conn.commit()


def update_scores(scores: dict) -> None:
    """Bulk update match_score by URL. scores = {url: score}."""
    with _connect() as conn:
        for url, score in scores.items():
            conn.execute(
                "UPDATE jobs SET match_score = ? WHERE url = ?",
                (int(score), url),
            )
        conn.commit()


def export_csv() -> str:
    """Return CSV string of all status='saved' rows."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT title, company, location, job_type, remote, url,
                      source, date_posted, match_score
               FROM jobs WHERE status = 'saved'
               ORDER BY match_score DESC"""
        ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Title", "Company", "Location", "Job Type", "Remote",
                     "URL", "Source", "Date Posted", "Match Score"])
    for row in rows:
        writer.writerow([
            row["title"], row["company"], row["location"], row["job_type"],
            "Yes" if row["remote"] else "No",
            row["url"], row["source"], row["date_posted"], row["match_score"],
        ])
    return output.getvalue()
