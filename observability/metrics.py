"""Metrics tracking with JSONL, time-range summaries, and drift detection."""
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from collections import defaultdict

from core.models import PipelineResult
import config


class Metrics:
    def __init__(self, metrics_file: Optional[Path] = None):
        self.metrics_file = metrics_file or (config.DATA_DIR / "metrics.jsonl")
        self.metrics_file.parent.mkdir(parents=True, exist_ok=True)

    def record_pipeline_run(self, result: PipelineResult) -> None:
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
            "phase_timings": result.phase_timings,
            "apply_rate": result.apply_rate,
            "enrichment_rate": result.enrichment_rate,
        }
        self._write(metric)

    def record_collector_run(self, collector_name: str, jobs_collected: int, success: bool, error: str = None) -> None:
        self._write({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "collector_run",
            "collector": collector_name,
            "jobs_collected": jobs_collected,
            "success": success,
            "error": error,
        })

    def record_email_send(self, job_id: str, company: str, success: bool, error: str = None) -> None:
        self._write({
            "timestamp": datetime.utcnow().isoformat(),
            "type": "email_send",
            "job_id": job_id,
            "company": company,
            "success": success,
            "error": error,
        })

    def _write(self, metric: Dict[str, Any]) -> None:
        with open(self.metrics_file, "a") as f:
            f.write(json.dumps(metric) + "\n")

    def get_summary(self, days: int = 30) -> Dict[str, Any]:
        if not self.metrics_file.exists():
            return {"error": "No metrics available", "pipeline_runs": 0}

        cutoff = datetime.utcnow() - timedelta(days=days)
        runs = []
        total_jobs = 0
        total_emails = 0
        total_errors = 0
        durations: List[float] = []
        decisions_tracker: Dict[str, int] = defaultdict(int)
        collector_stats: Dict[str, List[int]] = defaultdict(list)
        last_5_trend: List[Dict] = []

        with open(self.metrics_file, "r") as f:
            for line in f:
                try:
                    m = json.loads(line)
                    mt = datetime.fromisoformat(m["timestamp"])
                    if mt < cutoff:
                        continue
                    if m["type"] == "pipeline_run":
                        runs.append(m)
                        total_jobs += m.get("jobs_collected", 0)
                        total_emails += m.get("emails_sent", 0)
                        total_errors += m.get("errors", 0)
                        durations.append(m.get("duration_seconds", 0))
                        for d, c in m.get("decisions", {}).items():
                            decisions_tracker[d] += c
                        last_5_trend.append(m)
                    elif m["type"] == "collector_run":
                        collector_stats[m["collector"]].append(m.get("jobs_collected", 0))
                except (json.JSONDecodeError, KeyError):
                    continue

        avg_duration = sum(durations) / len(durations) if durations else 0
        return {
            "days": days,
            "pipeline_runs": len(runs),
            "total_jobs_collected": total_jobs,
            "total_emails_sent": total_emails,
            "total_errors": total_errors,
            "avg_duration_seconds": round(avg_duration, 1),
            "decision_summary": dict(decisions_tracker),
            "collectors": {k: {"total": sum(v), "avg": round(sum(v) / len(v), 1) if v else 0} for k, v in collector_stats.items()},
            "trend": last_5_trend[-5:] if last_5_trend else [],
        }

    def detect_drift(self, days: int = 7) -> Dict[str, str]:
        recent = self.get_summary(days=days)
        older = self.get_summary(days=days * 3)
        drift: Dict[str, str] = {}
        if recent.get("pipeline_runs", 0) > 1 and older.get("pipeline_runs", 0) > 1:
            recent_avg_dur = recent.get("avg_duration_seconds", 0)
            older_avg_dur = older.get("avg_duration_seconds", 0)
            if older_avg_dur > 0:
                ratio = recent_avg_dur / older_avg_dur
                if ratio > 1.5:
                    drift["duration"] = f"↑ pipeline {ratio:.1f}x slower than usual"
                elif ratio < 0.5:
                    drift["duration"] = f"↓ pipeline {ratio:.1f}x faster than usual"
        return drift

    def clear(self) -> None:
        if self.metrics_file.exists():
            self.metrics_file.write_text("")
