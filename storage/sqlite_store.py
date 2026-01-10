"""SQLite storage - for querying and analytics."""
import sqlite3
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from core.models import Job, Decision, JobStatus
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class SQLiteStore:
    """
    SQLite-based storage for queryable job data.
    
    Why SQLite in addition to CSV?
    - Fast querying (stats, filters, aggregations)
    - SQL interface for complex queries
    - Still serverless and portable
    - CSV is still the source of truth
    """
    
    def __init__(self, db_file: Path = config.SQLITE_FILE):
        self.db_file = db_file
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize database schema."""
        self.db_file.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                company TEXT NOT NULL,
                role TEXT NOT NULL,
                source TEXT NOT NULL,
                job_url TEXT NOT NULL,
                description TEXT,
                location TEXT,
                salary_min INTEGER,
                salary_max INTEGER,
                company_size TEXT,
                company_stage TEXT,
                posted_date TEXT,
                email TEXT,
                email_confidence REAL,
                hiring_manager TEXT,
                score INTEGER,
                decision TEXT,
                reason TEXT,
                status TEXT,
                applied_on TEXT,
                followup_on TEXT,
                email_status TEXT,
                attempt_count INTEGER,
                scraped_at TEXT,
                updated_at TEXT,
                error_log TEXT,
                llm_analysis TEXT
            )
        """)
        
        # Create indexes for common queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_decision ON jobs(decision)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON jobs(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_scraped_at ON jobs(scraped_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_company ON jobs(company)")
        
        conn.commit()
        conn.close()
        
        logger.debug(f"SQLite database initialized: {self.db_file}")
    
    def save_jobs(self, jobs: List[Job]) -> None:
        """Insert or update jobs in database."""
        if not jobs:
            return
        
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        for job in jobs:
            data = job.to_dict()
            cursor.execute("""
                INSERT OR REPLACE INTO jobs VALUES (
                    :job_id, :company, :role, :source, :job_url,
                    :description, :location, :salary_min, :salary_max,
                    :company_size, :company_stage, :posted_date,
                    :email, :email_confidence, :hiring_manager,
                    :score, :decision, :reason,
                    :status, :applied_on, :followup_on,
                    :email_status, :attempt_count,
                    :scraped_at, :updated_at, :error_log, :llm_analysis
                )
            """, data)
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Saved {len(jobs)} jobs to SQLite")
    
    def get_stats(self, days: int = 30) -> Dict[str, Any]:
        """Get aggregated statistics."""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cutoff_date = (datetime.utcnow() - timedelta(days=days)).isoformat()
        
        # Decision counts
        cursor.execute("""
            SELECT decision, COUNT(*) 
            FROM jobs 
            WHERE scraped_at >= ?
            GROUP BY decision
        """, (cutoff_date,))
        decision_counts = dict(cursor.fetchall())
        
        # Source counts
        cursor.execute("""
            SELECT source, COUNT(*) 
            FROM jobs 
            WHERE scraped_at >= ?
            GROUP BY source
        """, (cutoff_date,))
        source_counts = dict(cursor.fetchall())
        
        # Email stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_emails,
                SUM(CASE WHEN email_status = 'SENT' THEN 1 ELSE 0 END) as sent,
                SUM(CASE WHEN email_status = 'FAILED' THEN 1 ELSE 0 END) as failed
            FROM jobs
            WHERE scraped_at >= ? AND decision = 'APPLY'
        """, (cutoff_date,))
        email_stats = cursor.fetchone()
        
        # Total jobs
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE scraped_at >= ?", (cutoff_date,))
        total_jobs = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "total_jobs": total_jobs,
            "decisions": decision_counts,
            "sources": source_counts,
            "emails": {
                "total": email_stats[0],
                "sent": email_stats[1],
                "failed": email_stats[2],
            },
            "days": days,
        }
    
    def get_jobs_by_decision(self, decision: Decision, limit: int = 100) -> List[Job]:
        """Get jobs by decision type."""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM jobs WHERE decision = ? ORDER BY scraped_at DESC LIMIT ?",
            (decision.value, limit)
        )
        
        jobs = []
        for row in cursor.fetchall():
            jobs.append(Job.from_dict(dict(row)))
        
        conn.close()
        return jobs
    
    def get_failed_jobs(self, limit: int = 100) -> List[Job]:
        """Get jobs with failed status."""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT * FROM jobs WHERE status = 'FAILED' ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        
        jobs = []
        for row in cursor.fetchall():
            jobs.append(Job.from_dict(dict(row)))
        
        conn.close()
        return jobs
    
    def search_jobs(
        self,
        company: Optional[str] = None,
        role: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100
    ) -> List[Job]:
        """Search jobs with filters."""
        conn = sqlite3.connect(self.db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []
        
        if company:
            query += " AND company LIKE ?"
            params.append(f"%{company}%")
        
        if role:
            query += " AND role LIKE ?"
            params.append(f"%{role}%")
        
        if source:
            query += " AND source = ?"
            params.append(source)
        
        query += " ORDER BY scraped_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        jobs = []
        for row in cursor.fetchall():
            jobs.append(Job.from_dict(dict(row)))
        
        conn.close()
        return jobs
