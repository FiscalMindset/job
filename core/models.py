"""Core data models for Job Intelligence OS."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
import hashlib
import json
import re


class Decision(str, Enum):
    APPLY = "APPLY"
    APPLY_LATER = "APPLY_LATER"
    WATCH = "WATCH"
    SKIP = "SKIP"


class JobStatus(str, Enum):
    NEW = "NEW"
    ENRICHED = "ENRICHED"
    SCORED = "SCORED"
    DECIDED = "DECIDED"
    EMAIL_SENT = "EMAIL_SENT"
    FOLLOW_UP_SENT = "FOLLOW_UP_SENT"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class EmailStatus(str, Enum):
    NOT_SENT = "NOT_SENT"
    SENT = "SENT"
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"


class Confidence(float, Enum):
    LOW = 0.3
    MEDIUM = 0.6
    HIGH = 0.85
    VERY_HIGH = 0.95


@dataclass
class Job:
    company: str
    role: str
    source: str
    job_url: str
    description: str = ""
    location: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    currency: str = "USD"
    salary_period: str = "yearly"
    company_size: str = ""
    company_stage: str = ""
    company_industry: str = ""
    posted_date: Optional[datetime] = None
    email: str = ""
    email_confidence: float = 0.0
    hiring_manager: str = ""
    score: int = 0
    decision: Decision = Decision.SKIP
    reason: str = ""
    job_id: str = field(default="", init=False)
    status: JobStatus = JobStatus.NEW
    applied_on: Optional[datetime] = None
    followup_on: Optional[datetime] = None
    email_status: EmailStatus = EmailStatus.NOT_SENT
    attempt_count: int = 0
    scraped_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error_log: str = ""
    llm_analysis: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.job_id:
            self.job_id = self.generate_id()

    def generate_id(self) -> str:
        company = self.company.lower().strip()
        role = self.role.lower().strip()
        url = self.job_url.lower().strip()
        content = f"{company}|{role}|{url}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "job_id": self.job_id,
            "company": self.company,
            "role": self.role,
            "source": self.source,
            "job_url": self.job_url,
            "description": self.description,
            "location": self.location,
            "salary_min": self.salary_min,
            "salary_max": self.salary_max,
            "currency": self.currency,
            "salary_period": self.salary_period,
            "company_size": self.company_size,
            "company_stage": self.company_stage,
            "company_industry": self.company_industry,
            "posted_date": self.posted_date.isoformat() if self.posted_date else None,
            "email": self.email,
            "email_confidence": self.email_confidence,
            "hiring_manager": self.hiring_manager,
            "score": self.score,
            "decision": self.decision.value,
            "reason": self.reason,
            "status": self.status.value,
            "applied_on": self.applied_on.isoformat() if self.applied_on else None,
            "followup_on": self.followup_on.isoformat() if self.followup_on else None,
            "email_status": self.email_status.value,
            "attempt_count": self.attempt_count,
            "scraped_at": self.scraped_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error_log": self.error_log,
            "llm_analysis": json.dumps(self.llm_analysis) if self.llm_analysis else "",
            "tags": ",".join(self.tags),
        }
        return {k: v for k, v in result.items() if v is not None}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        def _parse_dt(key: str) -> Optional[datetime]:
            v = data.get(key)
            if v:
                try:
                    return datetime.fromisoformat(v.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass
            return None

        tags_raw = data.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if isinstance(tags_raw, str) else (tags_raw or [])

        llm_raw = data.get("llm_analysis", "")
        llm_analysis = {}
        if llm_raw:
            if isinstance(llm_raw, str):
                try:
                    llm_analysis = json.loads(llm_raw)
                except json.JSONDecodeError:
                    pass
            elif isinstance(llm_raw, dict):
                llm_analysis = llm_raw

        return cls(
            company=data["company"],
            role=data["role"],
            source=data["source"],
            job_url=data.get("job_url", ""),
            description=data.get("description", ""),
            location=data.get("location", ""),
            salary_min=data.get("salary_min"),
            salary_max=data.get("salary_max"),
            currency=data.get("currency", "USD"),
            salary_period=data.get("salary_period", "yearly"),
            company_size=data.get("company_size", ""),
            company_stage=data.get("company_stage", ""),
            company_industry=data.get("company_industry", ""),
            posted_date=_parse_dt("posted_date"),
            email=data.get("email", ""),
            email_confidence=float(data.get("email_confidence", 0.0)),
            hiring_manager=data.get("hiring_manager", ""),
            score=int(data.get("score", 0)),
            decision=Decision(data.get("decision", "SKIP")),
            reason=data.get("reason", ""),
            status=JobStatus(data.get("status", "NEW")),
            applied_on=_parse_dt("applied_on"),
            followup_on=_parse_dt("followup_on"),
            email_status=EmailStatus(data.get("email_status", "NOT_SENT")),
            attempt_count=int(data.get("attempt_count", 0)),
            scraped_at=_parse_dt("scraped_at") or datetime.utcnow(),
            updated_at=_parse_dt("updated_at") or datetime.utcnow(),
            error_log=data.get("error_log", ""),
            llm_analysis=llm_analysis,
            tags=tags,
        )

    def is_remote(self) -> bool:
        return bool(self.location and "remote" in self.location.lower())

    def days_since_posted(self) -> Optional[int]:
        if self.posted_date:
            return (datetime.utcnow() - self.posted_date).days
        return None

    def has_email(self) -> bool:
        return bool(self.email and re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', self.email))

    def short_summary(self) -> str:
        return f"{self.company} - {self.role} ({self.score}/100, {self.decision.value})"

    def __lt__(self, other: "Job") -> bool:
        return self.score < other.score

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Job):
            return NotImplemented
        return self.job_id == other.job_id

    def __hash__(self) -> int:
        return hash(self.job_id)


@dataclass
class PipelineResult:
    jobs_collected: int = 0
    jobs_deduplicated: int = 0
    jobs_enriched: int = 0
    jobs_scored: int = 0
    decisions_made: Dict[Decision, int] = field(default_factory=dict)
    emails_sent: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    source_stats: Dict[str, int] = field(default_factory=dict)
    all_jobs: list = field(default_factory=list)
    phase_timings: Dict[str, float] = field(default_factory=dict)

    def summary(self) -> str:
        lines = [
            f"Pipeline completed in {self.duration_seconds:.1f}s",
            f"Collected: {self.jobs_collected} jobs",
            f"New after dedup: {self.jobs_deduplicated} jobs",
            f"Enriched: {self.jobs_enriched} jobs",
            f"Scored: {self.jobs_scored} jobs",
            "",
            "Decisions:",
        ]
        for decision, count in self.decisions_made.items():
            lines.append(f"  {decision.value}: {count}")
        lines.append(f"\nEmails sent: {self.emails_sent}")
        if self.errors > 0:
            lines.append(f"Errors: {self.errors}")
        if self.source_stats:
            lines.append("\nSources:")
            for source, count in self.source_stats.items():
                lines.append(f"  {source}: {count}")
        if self.phase_timings:
            lines.append("\nPhase Timings:")
            for phase, secs in sorted(self.phase_timings.items(), key=lambda x: -x[1]):
                lines.append(f"  {phase}: {secs:.1f}s")
        return "\n".join(lines)

    @property
    def apply_rate(self) -> float:
        total = sum(self.decisions_made.values())
        if total == 0:
            return 0.0
        applies = self.decisions_made.get(Decision.APPLY, 0)
        return (applies / total) * 100

    @property
    def enrichment_rate(self) -> float:
        if self.jobs_deduplicated == 0:
            return 0.0
        return (self.jobs_enriched / self.jobs_deduplicated) * 100
