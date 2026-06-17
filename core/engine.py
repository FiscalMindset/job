"""Core orchestration engine - the heart of the system."""
import time
from typing import List, Optional, Callable, Dict
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        phase_callback: Optional[Callable[[str, int, int], None]] = None,
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
        self.phase_callback = phase_callback
        logger.info(f"Engine initialized with {len(collectors)} collectors")
        if dry_run:
            logger.warning("DRY RUN MODE - No emails will be sent")

    def run(self, sources: Optional[List[str]] = None) -> PipelineResult:
        start_time = time.time()
        result = PipelineResult()
        phase_timings: Dict[str, float] = {}

        logger.info("=" * 80)
        logger.info("Starting Job Intelligence Pipeline")
        logger.info("=" * 80)

        try:
            # Phase 1: Collect
            t0 = time.time()
            self._notify_phase("collect", 0, 6)
            jobs = self._collect(sources, result)
            phase_timings["collect"] = time.time() - t0
            logger.info(f"Collected {len(jobs)} jobs in {phase_timings['collect']:.1f}s")

            # Phase 2: Clean & Dedupe
            t0 = time.time()
            self._notify_phase("deduplicate", 1, 6)
            jobs = self._deduplicate(jobs, result)
            phase_timings["deduplicate"] = time.time() - t0
            logger.info(f"After deduplication: {len(jobs)} new jobs")

            # Phase 3: Enrich
            t0 = time.time()
            self._notify_phase("enrich", 2, 6)
            jobs = self._enrich_with_progress(jobs, result)
            phase_timings["enrich"] = time.time() - t0
            logger.info(f"Enriched {result.jobs_enriched} jobs")

            # Phase 4: Score & Decide
            t0 = time.time()
            self._notify_phase("score", 3, 6)
            jobs = self._score_and_decide_with_progress(jobs, result)
            phase_timings["score"] = time.time() - t0
            logger.info(f"Scored {result.jobs_scored} jobs")

            # Phase 5: Outreach
            t0 = time.time()
            self._notify_phase("outreach", 4, 6)
            self._send_emails(jobs, result)
            phase_timings["outreach"] = time.time() - t0
            logger.info(f"Sent {result.emails_sent} emails")

            # Phase 6: Store
            t0 = time.time()
            self._notify_phase("store", 5, 6)
            self._store(jobs)
            phase_timings["store"] = time.time() - t0
            logger.info("Stored all jobs to CSV and SQLite")

            result.all_jobs = jobs
            result.phase_timings = phase_timings

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            self.notifier.send_error_notification(str(e))

        result.duration_seconds = time.time() - start_time
        logger.info("=" * 80)
        logger.info(result.summary())
        logger.info("=" * 80)

        self.metrics.record_pipeline_run(result)
        if config.SEND_COMPLETION_EMAIL:
            self.notifier.send_completion_notification(result)

        return result

    def _notify_phase(self, phase: str, current: int, total: int) -> None:
        if self.phase_callback:
            self.phase_callback(phase, current, total)

    def _collect(self, sources: Optional[List[str]], result: PipelineResult) -> List[Job]:
        active = [c for c in self.collectors if not sources or c.name in sources]
        all_jobs: List[Job] = []
        max_workers = min(config.CONCURRENT_COLLECTORS, len(active))

        if max_workers <= 1:
            for collector in active:
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
            return all_jobs

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            fut_map = {pool.submit(c.collect): c.name for c in active}
            for future in as_completed(fut_map):
                name = fut_map[future]
                try:
                    jobs = future.result(timeout=config.REQUEST_TIMEOUT + 10)
                    all_jobs.extend(jobs)
                    result.jobs_collected += len(jobs)
                    result.source_stats[name] = len(jobs)
                    logger.info(f"{name}: collected {len(jobs)} jobs")
                except Exception as e:
                    logger.error(f"{name} failed: {e}", exc_info=True)
                    result.errors += 1

        return all_jobs

    def _deduplicate(self, jobs: List[Job], result: PipelineResult) -> List[Job]:
        existing_ids = self.csv_store.get_existing_job_ids()
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

    def _enrich_with_progress(self, jobs: List[Job], result: PipelineResult) -> List[Job]:
        for job in jobs:
            try:
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
        return jobs

    def _score_and_decide_with_progress(self, jobs: List[Job], result: PipelineResult) -> List[Job]:
        for job in jobs:
            try:
                self.decider.decide(job)
                job.status = JobStatus.DECIDED
                job.updated_at = datetime.utcnow()
                result.jobs_scored += 1
                if job.decision not in result.decisions_made:
                    result.decisions_made[job.decision] = 0
                result.decisions_made[job.decision] += 1
                logger.info(f"{job.company} - {job.role}: {job.decision.value} (score={job.score}) - {job.reason}")
            except Exception as e:
                logger.error(f"Scoring failed for {job.job_id}: {e}")
                job.error_log += f"Scoring error: {str(e)}\n"
                job.decision = Decision.SKIP
                job.reason = f"Scoring failed: {str(e)}"
                result.errors += 1
        return jobs

    def _send_emails(self, jobs: List[Job], result: PipelineResult) -> None:
        jobs_to_email = [job for job in jobs if job.decision == Decision.APPLY and job.email]
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
                        job.status = JobStatus.DECIDED
                        logger.info(f"Email rejected by user for {job.company}")
                    else:
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
        if not jobs:
            return
        self.csv_store.save_jobs(jobs)
        self.sqlite_store.save_jobs(jobs)
        logger.info(f"Stored {len(jobs)} jobs")
