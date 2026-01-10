"""CSV storage - primary data persistence."""
import csv
from pathlib import Path
from typing import List, Set
from datetime import datetime

from core.models import Job
from observability.logger import get_logger
import config


logger = get_logger(__name__)


class CSVStore:
    """
    CSV-based storage for job data.
    
    Why CSV?
    - Simple, inspectable, version-control friendly
    - Easy to backup, transfer, audit
    - Can be opened in Excel/Google Sheets
    - No database dependencies
    
    CSV is the source of truth. SQLite is for querying.
    """
    
    def __init__(self, csv_file: Path = config.CSV_FILE):
        self.csv_file = csv_file
        self.fieldnames = [
            "job_id", "company", "role", "source", "job_url",
            "description", "location", "salary_min", "salary_max",
            "company_size", "company_stage", "posted_date",
            "email", "email_confidence", "hiring_manager",
            "score", "decision", "reason",
            "status", "applied_on", "followup_on",
            "email_status", "attempt_count",
            "scraped_at", "updated_at", "error_log", "llm_analysis"
        ]
        
        self._ensure_csv_exists()
    
    def _ensure_csv_exists(self) -> None:
        """Create CSV file with headers if it doesn't exist."""
        if not self.csv_file.exists():
            self.csv_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.csv_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()
            logger.info(f"Created CSV file: {self.csv_file}")
    
    def save_jobs(self, jobs: List[Job]) -> None:
        """Append new jobs to CSV file."""
        if not jobs:
            return
        
        with open(self.csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.fieldnames)
            
            for job in jobs:
                writer.writerow(job.to_dict())
        
        logger.info(f"Saved {len(jobs)} jobs to CSV")
    
    def get_existing_job_ids(self) -> Set[str]:
        """Get set of all existing job IDs for deduplication."""
        job_ids = set()
        
        if not self.csv_file.exists():
            return job_ids
        
        with open(self.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                job_ids.add(row['job_id'])
        
        logger.debug(f"Found {len(job_ids)} existing job IDs")
        return job_ids
    
    def load_all_jobs(self) -> List[Job]:
        """Load all jobs from CSV (use sparingly, can be slow)."""
        jobs = []
        
        if not self.csv_file.exists():
            return jobs
        
        with open(self.csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    job = Job.from_dict(row)
                    jobs.append(job)
                except Exception as e:
                    logger.error(f"Failed to parse job {row.get('job_id')}: {e}")
        
        logger.info(f"Loaded {len(jobs)} jobs from CSV")
        return jobs
    
    def backup(self) -> Path:
        """Create a timestamped backup of the CSV file."""
        if not self.csv_file.exists():
            logger.warning("No CSV file to backup")
            return None
        
        backup_dir = config.BACKUP_DIR
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"jobs_{timestamp}.csv"
        
        # Copy file
        import shutil
        shutil.copy2(self.csv_file, backup_file)
        
        logger.info(f"Created backup: {backup_file}")
        
        # Clean up old backups
        self._cleanup_old_backups()
        
        return backup_file
    
    def _cleanup_old_backups(self) -> None:
        """Keep only the last N backups."""
        backup_files = sorted(
            config.BACKUP_DIR.glob("jobs_*.csv"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        # Delete old backups
        for backup_file in backup_files[config.MAX_BACKUPS:]:
            backup_file.unlink()
            logger.debug(f"Deleted old backup: {backup_file}")
