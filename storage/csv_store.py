"""CSV storage - primary data persistence with locking and compressed backups."""
import csv
import gzip
import shutil
from pathlib import Path
from typing import List, Set, Optional
from datetime import datetime
import threading

from core.models import Job
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class CSVStore:
    FIELD_NAMES = [
        "job_id", "company", "role", "source", "job_url",
        "description", "location", "salary_min", "salary_max",
        "currency", "salary_period",
        "company_size", "company_stage", "company_industry", "posted_date",
        "email", "email_confidence", "hiring_manager",
        "score", "decision", "reason",
        "status", "applied_on", "followup_on",
        "email_status", "attempt_count",
        "scraped_at", "updated_at", "error_log", "llm_analysis", "tags",
    ]

    def __init__(self, csv_file: Path = config.CSV_FILE):
        self.csv_file = csv_file
        self._lock = threading.Lock()
        self._ensure_csv_exists()

    def _ensure_csv_exists(self) -> None:
        with self._lock:
            if not self.csv_file.exists():
                self.csv_file.parent.mkdir(parents=True, exist_ok=True)
                with open(self.csv_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=self.FIELD_NAMES)
                    writer.writeheader()
                logger.info(f"Created CSV: {self.csv_file}")

    def save_jobs(self, jobs: List[Job]) -> None:
        if not jobs:
            return
        with self._lock:
            with open(self.csv_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELD_NAMES)
                for job in jobs:
                    writer.writerow(job.to_dict())
        logger.info(f"Saved {len(jobs)} jobs to CSV")

    def get_existing_job_ids(self) -> Set[str]:
        ids: Set[str] = set()
        if not self.csv_file.exists():
            return ids
        with self._lock:
            with open(self.csv_file, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    ids.add(row["job_id"])
        return ids

    def load_all_jobs(self) -> List[Job]:
        jobs: List[Job] = []
        if not self.csv_file.exists():
            return jobs
        with open(self.csv_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    jobs.append(Job.from_dict(row))
                except Exception as e:
                    logger.error(f"Failed to parse job {row.get('job_id')}: {e}")
        return jobs

    def load_jobs_since(self, since: datetime) -> List[Job]:
        jobs: List[Job] = []
        if not self.csv_file.exists():
            return jobs
        with open(self.csv_file, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    scraped = row.get("scraped_at", "")
                    if scraped and datetime.fromisoformat(scraped.replace("Z", "+00:00")) >= since:
                        jobs.append(Job.from_dict(row))
                except Exception:
                    continue
        return jobs

    def backup(self, compress: bool = True) -> Optional[Path]:
        if not self.csv_file.exists():
            logger.warning("No CSV to backup")
            return None
        with self._lock:
            config.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_file = config.BACKUP_DIR / f"jobs_{ts}.csv"
            shutil.copy2(self.csv_file, backup_file)
            if compress:
                with open(backup_file, "rb") as src, gzip.open(str(backup_file) + ".gz", "wb") as dst:
                    shutil.copyfileobj(src, dst)
                backup_file.unlink()
                backup_file = config.BACKUP_DIR / f"jobs_{ts}.csv.gz"
            self._cleanup_old_backups()
            logger.info(f"Backup: {backup_file}")
            return backup_file

    def _cleanup_old_backups(self) -> None:
        pattern = "jobs_*.csv*"
        backups = sorted(config.BACKUP_DIR.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[config.MAX_BACKUPS:]:
            old.unlink()
            logger.debug(f"Removed old backup: {old}")

    @property
    def job_count(self) -> int:
        if not self.csv_file.exists():
            return 0
        with open(self.csv_file, "r", encoding="utf-8") as f:
            return sum(1 for _ in csv.DictReader(f))
