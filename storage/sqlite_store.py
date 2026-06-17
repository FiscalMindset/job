"""SQLite storage - for querying and analytics with connection pooling."""
import sqlite3
import threading
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import contextmanager

from core.models import Job, Decision
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class SQLiteStore:
    def __init__(self, db_file: Path = config.SQLITE_FILE):
        self.db_file = db_file
        self._local = threading.local()
        self._init_db()

    @contextmanager
    def _connect(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or not self._local.conn:
            self._local.conn = sqlite3.connect(self.db_file)
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield self._local.conn
        except Exception:
            self._local.conn.rollback()
            raise
        finally:
            pass

    def _init_db(self) -> None:
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_file) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    company TEXT NOT NULL, role TEXT NOT NULL,
                    source TEXT NOT NULL, job_url TEXT NOT NULL,
                    description TEXT, location TEXT,
                    salary_min INTEGER, salary_max INTEGER,
                    currency TEXT, salary_period TEXT,
                    company_size TEXT, company_stage TEXT,
                    company_industry TEXT, posted_date TEXT,
                    email TEXT, email_confidence REAL,
                    hiring_manager TEXT,
                    score INTEGER, decision TEXT, reason TEXT,
                    status TEXT, applied_on TEXT, followup_on TEXT,
                    email_status TEXT, attempt_count INTEGER,
                    scraped_at TEXT, updated_at TEXT,
                    error_log TEXT, llm_analysis TEXT, tags TEXT
                )
            """)
            for col in ["decision", "status", "source", "scraped_at", "company", "score"]:
                conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{col} ON jobs({col})")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_score_decision ON jobs(score, decision)")
            conn.commit()
        logger.debug(f"SQLite initialized: {self.db_file}")

    def save_jobs(self, jobs: List[Job]) -> None:
        if not jobs:
            return
        with self._connect() as conn:
            conn.executemany(
                """INSERT OR REPLACE INTO jobs VALUES (
                    :job_id, :company, :role, :source, :job_url,
                    :description, :location, :salary_min, :salary_max,
                    :currency, :salary_period,
                    :company_size, :company_stage, :company_industry, :posted_date,
                    :email, :email_confidence, :hiring_manager,
                    :score, :decision, :reason,
                    :status, :applied_on, :followup_on,
                    :email_status, :attempt_count,
                    :scraped_at, :updated_at, :error_log, :llm_analysis, :tags
                )""",
                [job.to_dict() for job in jobs],
            )
            conn.commit()

    def get_stats(self, days: int = 30) -> Dict[str, Any]:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        with self._connect() as conn:
            decisions = dict(conn.execute(
                "SELECT decision, COUNT(*) FROM jobs WHERE scraped_at >= ? GROUP BY decision", (cutoff,)
            ).fetchall())
            sources = dict(conn.execute(
                "SELECT source, COUNT(*) FROM jobs WHERE scraped_at >= ? GROUP BY source", (cutoff,)
            ).fetchall())
            email_row = conn.execute(
                """SELECT COUNT(*),
                          SUM(CASE WHEN email_status='SENT' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN email_status='FAILED' THEN 1 ELSE 0 END)
                   FROM jobs WHERE scraped_at >= ? AND decision='APPLY'""", (cutoff,)
            ).fetchone()
            total = conn.execute("SELECT COUNT(*) FROM jobs WHERE scraped_at >= ?", (cutoff,)).fetchone()[0]
            avg_score = conn.execute("SELECT AVG(score) FROM jobs WHERE scraped_at >= ?", (cutoff,)).fetchone()[0] or 0
            return {
                "total_jobs": total,
                "avg_score": round(avg_score, 1),
                "decisions": decisions,
                "sources": sources,
                "emails": {"total": email_row[0], "sent": email_row[1], "failed": email_row[2]},
                "days": days,
            }

    def get_jobs_by_decision(self, decision: Decision, limit: int = 100) -> List[Job]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE decision = ? ORDER BY scraped_at DESC LIMIT ?",
                (decision.value, limit),
            ).fetchall()
            return [Job.from_dict(dict(r)) for r in rows]

    def get_failed_jobs(self, limit: int = 100) -> List[Job]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = 'FAILED' ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
            return [Job.from_dict(dict(r)) for r in rows]

    def search_jobs(
        self, company: Optional[str] = None, role: Optional[str] = None,
        source: Optional[str] = None, decision: Optional[str] = None,
        min_score: Optional[int] = None, limit: int = 100,
    ) -> List[Job]:
        with self._connect() as conn:
            query = "SELECT * FROM jobs WHERE 1=1"
            params: list = []
            if company:
                query += " AND company LIKE ?"
                params.append(f"%{company}%")
            if role:
                query += " AND role LIKE ?"
                params.append(f"%{role}%")
            if source:
                query += " AND source = ?"
                params.append(source)
            if decision:
                query += " AND decision = ?"
                params.append(decision)
            if min_score is not None:
                query += " AND score >= ?"
                params.append(min_score)
            query += " ORDER BY score DESC, scraped_at DESC LIMIT ?"
            params.append(limit)
            return [Job.from_dict(dict(r)) for r in conn.execute(query, params).fetchall()]

    def get_top_companies(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT company, COUNT(*) as count, AVG(score) as avg_score FROM jobs GROUP BY company ORDER BY count DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_weekly_trend(self, weeks: int = 4) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute("""
                SELECT DATE(scraped_at) as day, COUNT(*) as jobs,
                       SUM(CASE WHEN decision='APPLY' THEN 1 ELSE 0 END) as applies
                FROM jobs WHERE scraped_at >= DATE('now', ?)
                GROUP BY day ORDER BY day
            """, (f"-{weeks * 7} days",)).fetchall()
            return [dict(r) for r in rows]

    def migrate_schema(self) -> None:
        with sqlite3.connect(self.db_file) as conn:
            existing = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
            new_columns = {
                "currency": "TEXT DEFAULT 'USD'",
                "salary_period": "TEXT DEFAULT 'yearly'",
                "company_industry": "TEXT DEFAULT ''",
                "tags": "TEXT DEFAULT ''",
            }
            for col, dtype in new_columns.items():
                if col not in existing:
                    conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {dtype}")
                    logger.info(f"SQLite migration: added column {col}")
            conn.commit()
