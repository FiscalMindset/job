"""Metrics tracking and reporting."""
from datetime import datetime
from typing import Dict, Any
from pathlib import Path
import json

from core.models import PipelineResult
import config


class Metrics:
    """
    Track system metrics for monitoring and debugging.
    
    Metrics stored:
    - Pipeline runs
    - Jobs collected per source
    - Decision distribution
    - Email success rate
    - Error counts
    """
    
    def __init__(self, metrics_file: Path = None):
        self.metrics_file = metrics_file or (config.DATA_DIR / "metrics.jsonl")
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)
    
    def record_pipeline_run(self, result: PipelineResult) -> None:
        """Record pipeline execution metrics."""
        metric = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "pipeline_run",
            "jobs_collected": result.jobs_collected,
            "jobs_new": result.jobs_deduplicated,
            "jobs_enriched": result.jobs_enriched,
            "jobs_scored": result.jobs_scored,
            "emails_sent": result.emails_sent,
            "errors": result.errors,
            "duration_seconds": result.duration_seconds,
            "decisions": {k.value: v for k, v in result.decisions_made.items()},
            "sources": result.source_stats,
        }
        
        self._write_metric(metric)
    
    def record_collector_run(
        self,
        collector_name: str,
        jobs_collected: int,
        success: bool,
        error: str = None
    ) -> None:
        """Record collector execution."""
        metric = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "collector_run",
            "collector": collector_name,
            "jobs_collected": jobs_collected,
            "success": success,
            "error": error,
        }
        
        self._write_metric(metric)
    
    def record_email_send(
        self,
        job_id: str,
        company: str,
        success: bool,
        error: str = None
    ) -> None:
        """Record email send attempt."""
        metric = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "email_send",
            "job_id": job_id,
            "company": company,
            "success": success,
            "error": error,
        }
        
        self._write_metric(metric)
    
    def _write_metric(self, metric: Dict[str, Any]) -> None:
        """Write metric to JSONL file."""
        with open(self.metrics_file, 'a') as f:
            f.write(json.dumps(metric) + '\n')
    
    def get_summary(self, days: int = 30) -> Dict[str, Any]:
        """Get metrics summary for last N days."""
        # This is a simple implementation
        # For production, consider using a time-series database
        
        if not self.metrics_file.exists():
            return {"error": "No metrics available"}
        
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        pipeline_runs = 0
        total_jobs = 0
        total_emails = 0
        total_errors = 0
        
        with open(self.metrics_file, 'r') as f:
            for line in f:
                try:
                    metric = json.loads(line)
                    metric_time = datetime.fromisoformat(metric['timestamp'])
                    
                    if metric_time < cutoff:
                        continue
                    
                    if metric['type'] == 'pipeline_run':
                        pipeline_runs += 1
                        total_jobs += metric.get('jobs_collected', 0)
                        total_emails += metric.get('emails_sent', 0)
                        total_errors += metric.get('errors', 0)
                
                except:
                    continue
        
        return {
            "days": days,
            "pipeline_runs": pipeline_runs,
            "total_jobs_collected": total_jobs,
            "total_emails_sent": total_emails,
            "total_errors": total_errors,
        }
