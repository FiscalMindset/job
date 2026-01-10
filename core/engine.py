"""Core orchestration engine - the heart of the system."""
import time
from typing import List, Optional
from datetime import datetime

from core.models import Job, PipelineResult, Decision, JobStatus, EmailStatus
from collectors.base import BaseCollector
from intelligence.decider import JobDecider
from enrichment.email_finder import EmailFinder
from outreach.sender import EmailSender
from storage.csv_store import CSVStore
from storage.sqlite_store import SQLiteStore
from observability.logger import get_logger
from observability.metrics import Metrics
from observability.notifier import EmailNotifier
import config


logger = get_logger(__name__)


class JobEngine:
    """
    Main orchestration engine.
    
    Pipeline: collect → clean → dedupe → enrich → score → decide → outreach → store
    
    Design principles:
    - Each step is independent and can fail without crashing the pipeline
    - Idempotent: re-running with same input produces same output
    - Auditable: every decision has a reason
    - Fail-safe: partial failures are tolerated
    """
    
    def __init__(
        self,
        collectors: List[BaseCollector],
        decider: JobDecider,
        email_finder: EmailFinder,
        email_sender: EmailSender,
        csv_store: CSVStore,
        sqlite_store: SQLiteStore,
        metrics: Metrics,
        dry_run: bool = False,
    ):
        self.collectors = collectors
        self.decider = decider
        self.email_finder = email_finder
        self.email_sender = email_sender
        self.csv_store = csv_store
        self.sqlite_store = sqlite_store
        self.metrics = metrics
        self.notifier = EmailNotifier()
        self.dry_run = dry_run
        
        logger.info(f"Engine initialized with {len(collectors)} collectors")
        if dry_run:
            logger.warning("DRY RUN MODE - No emails will be sent")
    
    def run(self, sources: Optional[List[str]] = None) -> PipelineResult:
        """
        Execute the full pipeline.
        
        Args:
            sources: List of source names to collect from. None = all collectors.
        
        Returns:
            PipelineResult with execution statistics
        """
        start_time = time.time()
        result = PipelineResult()
        
        logger.info("=" * 80)
        logger.info("Starting Job Intelligence Pipeline")
        logger.info("=" * 80)
        
        try:
            # Step 1: Collect
            jobs = self._collect(sources, result)
            logger.info(f"Collected {len(jobs)} jobs")
            
            # Step 2: Clean & Dedupe
            jobs = self._deduplicate(jobs, result)
            logger.info(f"After deduplication: {len(jobs)} new jobs")
            
            # Step 3: Enrich
            jobs = self._enrich(jobs, result)
            logger.info(f"Enriched {result.jobs_enriched} jobs")
            
            # Step 4: Score & Decide
            jobs = self._score_and_decide(jobs, result)
            logger.info(f"Scored {result.jobs_scored} jobs")
            
            # Step 5: Outreach (only for APPLY decisions)
            self._send_emails(jobs, result)
            logger.info(f"Sent {result.emails_sent} emails")
            
            # Step 6: Store
            self._store(jobs)
            logger.info("Stored all jobs to CSV and SQLite")
            
            # Store jobs in result for detailed email
            result.all_jobs = jobs
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            
            # Send error notification
            self.notifier.send_error_notification(str(e))
        
        result.duration_seconds = time.time() - start_time
        
        logger.info("=" * 80)
        logger.info(result.summary())
        logger.info("=" * 80)
        
        # Record metrics
        self.metrics.record_pipeline_run(result)
        
        # Send completion notification
        self.notifier.send_completion_notification(result)
        
        return result
    
    def _collect(self, sources: Optional[List[str]], result: PipelineResult) -> List[Job]:
        """Collect jobs from all enabled collectors."""
        all_jobs = []
        
        for collector in self.collectors:
            # Filter by requested sources
            if sources and collector.name not in sources:
                continue
            
            try:
                logger.info(f"Collecting from {collector.name}...")
                jobs = collector.collect()
                all_jobs.extend(jobs)
                
                result.jobs_collected += len(jobs)
                result.source_stats[collector.name] = len(jobs)
                
                logger.info(f"{collector.name}: collected {len(jobs)} jobs")
                
            except Exception as e:
                logger.error(f"{collector.name} failed: {e}", exc_info=True)
                result.errors += 1
                # Continue with other collectors
        
        return all_jobs
    
    def _deduplicate(self, jobs: List[Job], result: PipelineResult) -> List[Job]:
        """Remove duplicates and already-processed jobs."""
        # Get existing job IDs
        existing_ids = self.csv_store.get_existing_job_ids()
        
        # Filter out duplicates
        new_jobs = []
        seen_ids = set()
        
        for job in jobs:
            if job.job_id in existing_ids:
                logger.debug(f"Skipping duplicate: {job.company} - {job.role}")
                continue
            
            if job.job_id in seen_ids:
                logger.debug(f"Skipping duplicate in batch: {job.company} - {job.role}")
                continue
            
            new_jobs.append(job)
            seen_ids.add(job.job_id)
        
        result.jobs_deduplicated = len(new_jobs)
        return new_jobs
    
    def _enrich(self, jobs: List[Job], result: PipelineResult) -> List[Job]:
        """Enrich jobs with contact info and company data."""
        for job in jobs:
            try:
                # Find email
                email_result = self.email_finder.find_email(job)
                if email_result:
                    job.email = email_result["email"]
                    job.email_confidence = email_result["confidence"]
                    job.hiring_manager = email_result.get("name", "")
                
                job.status = JobStatus.ENRICHED
                job.updated_at = datetime.utcnow()
                result.jobs_enriched += 1
                
            except Exception as e:
                logger.error(f"Enrichment failed for {job.job_id}: {e}")
                job.error_log += f"Enrichment error: {str(e)}\n"
                result.errors += 1
                # Continue with next job
        
        return jobs
    
    def _score_and_decide(self, jobs: List[Job], result: PipelineResult) -> List[Job]:
        """Score jobs and make application decisions."""
        for job in jobs:
            try:
                # Let decider handle both scoring and decision
                self.decider.decide(job)
                
                job.status = JobStatus.DECIDED
                job.updated_at = datetime.utcnow()
                result.jobs_scored += 1
                
                # Track decision
                if job.decision not in result.decisions_made:
                    result.decisions_made[job.decision] = 0
                result.decisions_made[job.decision] += 1
                
                logger.info(
                    f"{job.company} - {job.role}: "
                    f"{job.decision.value} (score={job.score}) - {job.reason}"
                )
                
            except Exception as e:
                logger.error(f"Scoring failed for {job.job_id}: {e}")
                job.error_log += f"Scoring error: {str(e)}\n"
                job.decision = Decision.SKIP
                job.reason = f"Scoring failed: {str(e)}"
                result.errors += 1
        
        return jobs
    
    def _send_emails(self, jobs: List[Job], result: PipelineResult) -> None:
        """Send outreach emails for APPLY decisions."""
        # Filter jobs that need emails
        jobs_to_email = [
            job for job in jobs
            if job.decision == Decision.APPLY and job.email
        ]
        
        if not jobs_to_email:
            logger.info("No jobs to email")
            return
        
        logger.info(f"Sending emails to {len(jobs_to_email)} jobs...")
        
        for job in jobs_to_email:
            try:
                if self.dry_run:
                    logger.info(f"[DRY RUN] Would send email to {job.email} for {job.company}")
                    job.status = JobStatus.EMAIL_SENT
                    result.emails_sent += 1
                else:
                    success = self.email_sender.send_application_email(job)
                    
                    if success:
                        job.status = JobStatus.EMAIL_SENT
                        job.applied_on = datetime.utcnow()
                        result.emails_sent += 1
                        logger.info(f"Email sent to {job.email} for {job.company}")
                    elif job.email_status == EmailStatus.NOT_SENT:
                        # User rejected the email
                        job.status = JobStatus.DECIDED
                        logger.info(f"Email rejected by user for {job.company}")
                    else:
                        # Failed to send (technical error)
                        job.status = JobStatus.FAILED
                        logger.error(f"Failed to send email for {job.company}")
                        result.errors += 1
                
                job.updated_at = datetime.utcnow()
                
            except Exception as e:
                logger.error(f"Email sending failed for {job.job_id}: {e}")
                job.error_log += f"Email error: {str(e)}\n"
                job.status = JobStatus.FAILED
                result.errors += 1
    
    def _store(self, jobs: List[Job]) -> None:
        """Store jobs in CSV and SQLite."""
        if not jobs:
            return
        
        # Store in CSV (primary)
        self.csv_store.save_jobs(jobs)
        
        # Store in SQLite (queryable)
        self.sqlite_store.save_jobs(jobs)
        
        logger.info(f"Stored {len(jobs)} jobs")
